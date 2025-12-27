"""
Conservation Analysis API Router
跨物种保守性分析 API 端点

Endpoints:
- GET /conservation/overview - 保守性统计概览
- GET /conservation/matrix - 物种间保守性热图矩阵数据
- GET /conservation/regulations - 保守调控关系列表（分页）
- GET /conservation/venn - Venn 图数据
"""
import json
from typing import Optional, List, Dict, Set, Iterator, Any
from collections import defaultdict
from fastapi import APIRouter, Depends, Query, HTTPException, Request
from sqlalchemy.orm import Session, aliased
from sqlalchemy import func, distinct, String, text

from app.core.database import get_db
from app.routers.chipseq_rate_limit import rate_limit
from app.core.cache import cache, CacheService
from app.core.validators import compute_pagination_offset, parse_int_list
from app.core.utils import escape_like_pattern, compute_conservation_map
from app.models import CoreGene, Gene, Regulation, Species
from app.schemas.conservation import (
    SPECIES_MAP,
    SPECIES_IDS,
    ConservationSummary,
    ConservationDistribution,
    SpeciesCombinationStats,
    ConservationMatrix,
    ConservedRegulationList,
    ConservedRegulationItem,
    SpeciesBindingAffinity,
)
from app.utils.streaming_export import stream_csv_response

# Reverse mapping: species name -> species id (supports both English and Chinese)
SPECIES_NAME_TO_ID = {v: k for k, v in SPECIES_MAP.items()}
# Add Chinese names mapping (from database display_name)
SPECIES_NAME_TO_ID.update({
    "人类": 1,
    "黑猩猩": 2,
    "猕猴": 3,
    "狨猴": 4
})

router = APIRouter(prefix="/conservation", tags=["conservation"])

# CSV 导出硬限制（避免大查询导致 DoS / 长事务）
MAX_CONSERVED_REGULATIONS_EXPORT_LIMIT = 20000


# =============================================================================
# Helper Functions
# =============================================================================
def _pick_first_non_empty_str(*values: Optional[str]) -> Optional[str]:
    """返回第一个非空白字符串（strip 后非空），否则 None。"""
    for value in values:
        if value is None:
            continue
        normalized = value.strip()
        if normalized:
            return normalized
    return None


def _parse_species_ids_param(species_ids: Optional[str]) -> Optional[List[int]]:
    """解析并校验 species_ids（逗号分隔），仅允许 SPECIES_IDS 范围内的值。"""
    parsed = parse_int_list(species_ids, max_items=len(SPECIES_IDS), param_name="species_ids")
    if not parsed:
        return None

    unique_ids = sorted({int(x) for x in parsed})
    invalid_ids = [x for x in unique_ids if x not in SPECIES_IDS]
    if invalid_ids:
        raise HTTPException(
            status_code=400,
            detail=f"species_ids: invalid species IDs {invalid_ids}. Allowed values: {SPECIES_IDS}",
        )
    return unique_ids


def _compute_conservation_label(species_ids: List[int]) -> str:
    """根据出现的 species_ids 计算 4-bit label（顺序与 SPECIES_IDS 一致）。"""
    present = set(species_ids)
    return "".join("1" if sid in present else "0" for sid in SPECIES_IDS)


def _parse_species_ba_pairs(
    species_ba_pairs: Optional[str],
) -> tuple[List[int], List[SpeciesBindingAffinity], Optional[float]]:
    """
    将 string_agg 生成的 \"species_name:ba\" 列表解析为：
    - species_ids（去重）
    - species_binding_affinities（每物种平均 BA）
    - avg_binding_affinity（跨所有 BA 值的平均）
    """
    species_ba_dict: Dict[int, List[float]] = {}  # species_id -> list of BA values
    species_names_dict: Dict[int, str] = {}  # species_id -> species_name

    if species_ba_pairs:
        for pair in species_ba_pairs.split(","):
            if ":" not in pair:
                continue
            sp_name, ba_str = pair.split(":", 1)
            sp_name = sp_name.strip()
            sp_id = SPECIES_NAME_TO_ID.get(sp_name)
            if sp_id is None:
                continue

            if sp_id not in species_ba_dict:
                species_ba_dict[sp_id] = []
            species_names_dict.setdefault(sp_id, sp_name)

            try:
                ba_val = float(ba_str) if ba_str and ba_str != "None" else None
            except ValueError:
                ba_val = None

            if ba_val is not None:
                species_ba_dict[sp_id].append(ba_val)

    species_binding_affinities: List[SpeciesBindingAffinity] = []
    all_ba_values: List[float] = []
    for sp_id in sorted(species_ba_dict.keys()):
        ba_vals = species_ba_dict[sp_id]
        avg_species_ba = (sum(ba_vals) / len(ba_vals)) if ba_vals else None
        species_binding_affinities.append(
            SpeciesBindingAffinity(
                species_id=sp_id,
                species_name=species_names_dict.get(sp_id, SPECIES_MAP.get(sp_id, str(sp_id))),
                binding_affinity=round(avg_species_ba, 2) if avg_species_ba is not None else None,
            )
        )
        if ba_vals:
            all_ba_values.extend(ba_vals)

    species_ids_list = sorted(species_ba_dict.keys())
    avg_ba = (sum(all_ba_values) / len(all_ba_values)) if all_ba_values else None
    avg_ba_rounded = round(avg_ba, 2) if avg_ba is not None else None
    return species_ids_list, species_binding_affinities, avg_ba_rounded


def _build_conserved_regulations_base_query(
    db: Session,
    *,
    min_species: int,
    lncrna_symbol: Optional[str],
    target_symbol: Optional[str],
    species_ids: Optional[List[int]],
    min_ba: Optional[float],
):
    """构建 conserved regulations 的基础查询（供列表与导出复用）。"""
    LncRNAGene = aliased(Gene, name="lncrna_gene")
    TargetGene = aliased(Gene, name="target_gene")
    LncRNACore = aliased(CoreGene, name="lncrna_core")
    TargetCore = aliased(CoreGene, name="target_core")

    base_query = (
        db.query(
            LncRNAGene.core_id.label("lncrna_core_id"),
            TargetGene.core_id.label("target_core_id"),
            func.count(distinct(Regulation.species_id)).label("species_count"),
            func.min(LncRNACore.canonical_symbol).label("lncrna_symbol"),
            func.min(TargetCore.canonical_symbol).label("target_symbol"),
            func.string_agg(
                distinct(func.concat(Species.display_name, ":", func.cast(Regulation.binding_affinity, String))),
                ",",
            ).label("species_ba_pairs"),
        )
        .select_from(Regulation)
        .join(LncRNAGene, Regulation.lncrna_gene_id == LncRNAGene.gene_id)
        .join(TargetGene, Regulation.target_gene_id == TargetGene.gene_id)
        .join(LncRNACore, LncRNAGene.core_id == LncRNACore.core_id)
        .join(TargetCore, TargetGene.core_id == TargetCore.core_id)
        .join(Species, Regulation.species_id == Species.species_id)
        .filter(LncRNACore.gene_type == "lncRNA")
    )

    # Filter to selected species (or default to all supported species)
    if species_ids:
        base_query = base_query.filter(Regulation.species_id.in_(species_ids))
    else:
        base_query = base_query.filter(Regulation.species_id.in_(SPECIES_IDS))

    if min_ba is not None:
        base_query = base_query.filter(Regulation.binding_affinity >= min_ba)

    base_query = (
        base_query.group_by(LncRNAGene.core_id, TargetGene.core_id)
        .having(func.count(distinct(Regulation.species_id)) >= min_species)
    )

    if lncrna_symbol:
        escaped = escape_like_pattern(lncrna_symbol)
        base_query = base_query.filter(LncRNACore.canonical_symbol.ilike(f"%{escaped}%", escape="\\"))
    if target_symbol:
        escaped = escape_like_pattern(target_symbol)
        base_query = base_query.filter(TargetCore.canonical_symbol.ilike(f"%{escaped}%", escape="\\"))

    return base_query


def get_lncrna_core_ids(db: Session) -> List[int]:
    """Get all lncRNA core_ids from the database."""
    return [
        row[0] for row in
        db.query(CoreGene.core_id)
        .filter(CoreGene.gene_type == "lncRNA")
        .all()
    ]


def _get_regulation_pair_pattern_counts(db: Session) -> Dict[str, int]:
    """
    Get conservation pattern counts for regulation pairs (lncRNA_core_id, target_core_id).

    Security/Perf:
    - Avoid materializing all distinct regulation pairs into Python (DoS risk).
    - Compute 4-bit species presence patterns in SQL and aggregate to at most 16 rows.
    - Cache the aggregated pattern counts for reuse by /matrix and /venn endpoints.
    """
    cache_key = cache.make_key("conservation:regulation_pair_patterns")
    cached = cache.get(cache_key)
    if cached is not None:
        return {str(k): int(v) for k, v in dict(cached).items()}

    # Dialect-agnostic SQL (works for PostgreSQL and SQLite demo mode):
    # - Use MAX(CASE WHEN ...) to compute per-species presence (0/1).
    # - Concatenate digits to form a 4-bit label like "1101".
    sql = text(
        """
        WITH pair_species AS (
            SELECT
                lnc.core_id AS lncrna_core_id,
                tgt.core_id AS target_core_id,
                MAX(CASE WHEN r.species_id = 1 THEN 1 ELSE 0 END) AS s1,
                MAX(CASE WHEN r.species_id = 2 THEN 1 ELSE 0 END) AS s2,
                MAX(CASE WHEN r.species_id = 3 THEN 1 ELSE 0 END) AS s3,
                MAX(CASE WHEN r.species_id = 4 THEN 1 ELSE 0 END) AS s4
            FROM regulations r
            JOIN genes lnc ON r.lncrna_gene_id = lnc.gene_id
            JOIN genes tgt ON r.target_gene_id = tgt.gene_id
            JOIN core_genes lnc_core ON lnc.core_id = lnc_core.core_id
            JOIN core_genes tgt_core ON tgt.core_id = tgt_core.core_id
            WHERE r.species_id IN (1, 2, 3, 4)
              AND lnc_core.gene_type = 'lncRNA'
            GROUP BY lnc.core_id, tgt.core_id
        )
        SELECT
            CAST(s1 AS TEXT) || CAST(s2 AS TEXT) || CAST(s3 AS TEXT) || CAST(s4 AS TEXT) AS label,
            COUNT(*) AS count
        FROM pair_species
        GROUP BY label
        """
    )

    rows = db.execute(sql).fetchall()
    pattern_counts = {str(row.label): int(row.count) for row in rows if row and row.label}

    cache.set(cache_key, pattern_counts, CacheService.TTL_STATS)
    return pattern_counts


def _build_regulation_matrix_from_pattern_counts(pattern_counts: Dict[str, int]) -> List[List[int]]:
    """
    Build a 4x4 regulation matrix from pattern counts.

    regulation_matrix[i][j] = number of regulation pairs present in both species i and j
    where species order follows SPECIES_IDS (1..4).
    """
    n = len(SPECIES_IDS)
    matrix = [[0] * n for _ in range(n)]

    for label, count in pattern_counts.items():
        if not label or len(label) != n:
            continue
        bits = [ch == "1" for ch in label]
        for i in range(n):
            if not bits[i]:
                continue
            for j in range(n):
                if bits[j]:
                    matrix[i][j] += int(count)

    return matrix


def _build_conserved_regulation_items(results: list, db: Session) -> List[ConservedRegulationItem]:
    """
    Build ConservedRegulationItem list from query results.

    Note:
    - `conservation_label` 表示调控关系在 4 个物种中的出现模式（顺序与 SPECIES_IDS 一致）。
    - 避免额外的 compute_conservation_map 调用，减少数据库压力。
    """
    items: List[ConservedRegulationItem] = []
    for row in results:
        species_ids, species_ba_list, avg_ba = _parse_species_ba_pairs(getattr(row, "species_ba_pairs", None))
        conservation_label = _compute_conservation_label(species_ids)

        items.append(ConservedRegulationItem(
            core_id=row.lncrna_core_id,
            lncrna_gene_name=row.lncrna_symbol,
            lncrna_ensembl_id=None,  # Not available in current query
            target_gene_name=row.target_symbol,
            target_ensembl_id=None,  # Not available in current query
            conservation_label=conservation_label,
            species_count=row.species_count,
            species_ids=species_ids,
            avg_binding_affinity=avg_ba,
            species_binding_affinities=species_ba_list
        ))

    return items


# =============================================================================
# Endpoint 1: Overview Statistics
# =============================================================================
@router.get("/overview", response_model=ConservationSummary)
@rate_limit("30/minute")
def get_conservation_overview(request: Request, db: Session = Depends(get_db)):
    """
    Get conservation overview statistics.

    Returns distribution of lncRNAs by conservation level (1-4 species),
    top species combinations, and summary metrics.

    Cached for 1 hour.
    """
    # Try cache first
    cache_key = cache.make_key("conservation:overview")
    cached = cache.get(cache_key)
    if cached is not None:
        return ConservationSummary(**cached)

    # Get all lncRNA core_ids
    lncrna_core_ids = get_lncrna_core_ids(db)
    total_lncrnas = len(lncrna_core_ids)

    if total_lncrnas == 0:
        empty_result = ConservationSummary(
            total_lncrnas=0,
            total_regulations=0,
            distribution=[],
            top_combinations=[],
            fully_conserved_count=0,
            primate_specific_count=0
        )
        return empty_result

    # Compute conservation for all lncRNAs
    conservation_map = compute_conservation_map(lncrna_core_ids, db)

    # Count by conservation level and combination
    level_counts: Dict[int, int] = defaultdict(int)
    combination_counts: Dict[str, int] = defaultdict(int)
    core_ids_by_level: Dict[int, List[int]] = defaultdict(list)
    core_ids_by_label: Dict[str, List[int]] = defaultdict(list)

    for core_id, (label, count) in conservation_map.items():
        level_counts[count] += 1
        combination_counts[label] += 1
        core_ids_by_level[count].append(core_id)
        core_ids_by_label[label].append(core_id)

    # Get total regulations count
    total_regulations = db.query(func.count(Regulation.regulation_id)).scalar() or 0

    # Build distribution by conservation level (1-4)
    distribution = []
    for level in range(1, 5):
        lncrna_count = level_counts.get(level, 0)
        percentage = (lncrna_count / total_lncrnas * 100) if total_lncrnas > 0 else 0

        # Count regulations for lncRNAs at this conservation level
        core_ids_at_level = core_ids_by_level.get(level, [])

        if core_ids_at_level:
            # PERFORMANCE: 用 JOIN + 子条件替代 .all() 拉取 gene_ids 到 Python 再 in_(list)
            reg_count = (
                db.query(func.count(Regulation.regulation_id))
                .join(Gene, Regulation.lncrna_gene_id == Gene.gene_id)
                .filter(Gene.core_id.in_(core_ids_at_level))
                .scalar() or 0
            )
        else:
            reg_count = 0

        distribution.append(ConservationDistribution(
            conservation_count=level,
            lncrna_count=lncrna_count,
            regulation_count=reg_count,
            percentage=round(percentage, 2)
        ))

    # Build top combinations
    top_combinations = []
    for label, count in sorted(combination_counts.items(), key=lambda x: -x[1]):
        species_names = [
            SPECIES_MAP[sid]
            for i, sid in enumerate(SPECIES_IDS)
            if label[i] == "1"
        ]
        species_count = label.count("1")

        # Count regulations for this combination
        core_ids_for_combo = core_ids_by_label.get(label, [])

        if core_ids_for_combo:
            # PERFORMANCE: 用 JOIN 替代 gene_id 列表 materialize（避免大列表导致 DoS/慢查询）
            reg_count = (
                db.query(func.count(Regulation.regulation_id))
                .join(Gene, Regulation.lncrna_gene_id == Gene.gene_id)
                .filter(Gene.core_id.in_(core_ids_for_combo))
                .scalar() or 0
            )
        else:
            reg_count = 0

        top_combinations.append(SpeciesCombinationStats(
            combination_label=label,
            species_names=species_names,
            species_count=species_count,
            lncrna_count=count,
            regulation_count=reg_count
        ))

    # Summary metrics
    fully_conserved_count = level_counts.get(4, 0)  # In all 4 species
    primate_specific_count = level_counts.get(1, 0)  # Only in 1 species

    result = ConservationSummary(
        total_lncrnas=total_lncrnas,
        total_regulations=total_regulations,
        distribution=distribution,
        top_combinations=top_combinations,
        fully_conserved_count=fully_conserved_count,
        primate_specific_count=primate_specific_count
    )

    # Cache for 1 hour
    cache.set(cache_key, result.model_dump(), CacheService.TTL_STATS)

    return result


# =============================================================================
# Endpoint 2: Conservation Matrix (for Heatmap)
# =============================================================================
@router.get("/matrix", response_model=ConservationMatrix)
@rate_limit("30/minute")
def get_conservation_matrix(request: Request, db: Session = Depends(get_db)):
    """
    Get species-to-species conservation matrix for heatmap visualization.

    Returns 4x4 matrices for:
    - Shared lncRNA counts
    - Shared regulation counts
    - Jaccard similarity indices

    Cached for 1 hour.
    """
    # Try cache first
    cache_key = cache.make_key("conservation:matrix")
    cached = cache.get(cache_key)
    if cached is not None:
        return ConservationMatrix(**cached)

    # Build species -> set of core_ids mapping
    species_core_ids: Dict[int, Set[int]] = {sid: set() for sid in SPECIES_IDS}

    species_presence = (
        db.query(Gene.species_id, Gene.core_id)
        .join(CoreGene, Gene.core_id == CoreGene.core_id)
        .filter(CoreGene.gene_type == "lncRNA")
        .distinct()
        .all()
    )

    for species_id, core_id in species_presence:
        if species_id in species_core_ids:
            species_core_ids[species_id].add(core_id)

    # Build species info list
    species_info = [
        {"id": sid, "name": SPECIES_MAP[sid]}
        for sid in SPECIES_IDS
    ]

    # Initialize matrices
    n = len(SPECIES_IDS)
    lncrna_matrix = [[0] * n for _ in range(n)]
    regulation_matrix = [[0] * n for _ in range(n)]
    jaccard_matrix = [[0.0] * n for _ in range(n)]
    diagonal_totals = {}

    # Compute matrices
    for i, sid1 in enumerate(SPECIES_IDS):
        set1 = species_core_ids[sid1]
        diagonal_totals[sid1] = len(set1)

        for j, sid2 in enumerate(SPECIES_IDS):
            set2 = species_core_ids[sid2]

            # Shared lncRNAs
            shared = set1 & set2
            lncrna_matrix[i][j] = len(shared)

            # Jaccard index
            union = set1 | set2
            jaccard = len(shared) / len(union) if union else 0.0
            jaccard_matrix[i][j] = round(jaccard, 4)

    # Regulation matrix: compute in SQL to avoid materializing huge pair sets in Python (DoS risk).
    regulation_patterns = _get_regulation_pair_pattern_counts(db)
    regulation_matrix = _build_regulation_matrix_from_pattern_counts(regulation_patterns)
    # Backward-compatibility: keep diagonal values as total regulation rows per species.
    # Off-diagonal cells represent shared (lncRNA_core_id, target_core_id) pairs.
    reg_row_counts = dict(
        db.query(Regulation.species_id, func.count(Regulation.regulation_id))
        .join(Gene, Regulation.lncrna_gene_id == Gene.gene_id)
        .join(CoreGene, Gene.core_id == CoreGene.core_id)
        .filter(Regulation.species_id.in_(SPECIES_IDS))
        .filter(CoreGene.gene_type == "lncRNA")
        .group_by(Regulation.species_id)
        .all()
    )
    for idx, sid in enumerate(SPECIES_IDS):
        regulation_matrix[idx][idx] = int(reg_row_counts.get(sid, 0))

    result = ConservationMatrix(
        species=species_info,
        lncrna_matrix=lncrna_matrix,
        regulation_matrix=regulation_matrix,
        jaccard_matrix=jaccard_matrix,
        diagonal_totals=diagonal_totals
    )

    # Cache for 1 hour
    cache.set(cache_key, result.model_dump(), CacheService.TTL_STATS)

    return result


# =============================================================================
# Endpoint 3: Conserved Regulations List (Paginated)
# =============================================================================
@router.get("/regulations", response_model=ConservedRegulationList)
@rate_limit("30/minute")
def get_conserved_regulations(
    request: Request,
    min_species: int = Query(2, ge=2, le=4, description="Minimum number of species"),
    min_conservation: Optional[int] = Query(None, ge=2, le=4, description="Alias for min_species (frontend compatibility)"),
    page: int = Query(1, ge=1, description="Page number"),
    page_size: int = Query(50, ge=10, le=200, description="Items per page"),
    lncrna_symbol: Optional[str] = Query(None, max_length=100, description="Filter by lncRNA symbol"),
    lncrna_gene_name: Optional[str] = Query(None, max_length=100, description="Alias for lncrna_symbol (frontend compatibility)"),
    target_symbol: Optional[str] = Query(None, max_length=100, description="Filter by target symbol"),
    target_gene_name: Optional[str] = Query(None, max_length=100, description="Alias for target_symbol (frontend compatibility)"),
    species_ids: Optional[str] = Query(None, description="Comma-separated species IDs to include (e.g. '1,2,3,4')"),
    min_ba: Optional[float] = Query(None, ge=0, description="Minimum binding affinity threshold"),
    db: Session = Depends(get_db),
):
    """
    Get paginated list of conserved regulations (lncRNA-target pairs).

    A conserved regulation is defined as a (lncRNA core_id, target core_id) pair
    that exists in at least `min_species` species.

    Parameters:
    - min_species: Minimum number of species (2-4)
    - page: Page number
    - page_size: Items per page
    - lncrna_symbol: Optional filter by lncRNA symbol (partial match)
    - target_symbol: Optional filter by target symbol (partial match)
    """
    effective_min_species = min_conservation if min_conservation is not None else min_species
    species_id_list = _parse_species_ids_param(species_ids)
    if species_id_list is not None and len(species_id_list) < 2:
        raise HTTPException(status_code=400, detail="species_ids: at least 2 species IDs are required")
    if species_id_list is not None and effective_min_species > len(species_id_list):
        raise HTTPException(
            status_code=400,
            detail=f"min_species ({effective_min_species}) cannot be greater than the number of selected species ({len(species_id_list)})",
        )

    normalized_lncrna_symbol = _pick_first_non_empty_str(lncrna_symbol, lncrna_gene_name)
    normalized_target_symbol = _pick_first_non_empty_str(target_symbol, target_gene_name)

    base_query = _build_conserved_regulations_base_query(
        db,
        min_species=effective_min_species,
        lncrna_symbol=normalized_lncrna_symbol,
        target_symbol=normalized_target_symbol,
        species_ids=species_id_list,
        min_ba=min_ba,
    )

    # Count total (using subquery for efficiency)
    count_subq = base_query.subquery()
    total = db.query(func.count()).select_from(count_subq).scalar() or 0

    # Paginate
    offset = compute_pagination_offset(page, page_size)
    results = (
        base_query
        .order_by(func.count(distinct(Regulation.species_id)).desc())
        .offset(offset)
        .limit(page_size)
        .all()
    )

    items = _build_conserved_regulation_items(results, db)

    total_pages = (total + page_size - 1) // page_size

    return ConservedRegulationList(
        items=items,
        total=total,
        page=page,
        page_size=page_size,
        total_pages=total_pages,
        min_species=effective_min_species
    )


@router.get("/regulations/export")
@rate_limit("10/minute")
def export_conserved_regulations(
    request: Request,
    min_species: int = Query(2, ge=2, le=4, description="Minimum number of species"),
    min_conservation: Optional[int] = Query(None, ge=2, le=4, description="Alias for min_species (frontend compatibility)"),
    lncrna_symbol: Optional[str] = Query(None, max_length=100, description="Filter by lncRNA symbol"),
    lncrna_gene_name: Optional[str] = Query(None, max_length=100, description="Alias for lncrna_symbol (frontend compatibility)"),
    target_symbol: Optional[str] = Query(None, max_length=100, description="Filter by target symbol"),
    target_gene_name: Optional[str] = Query(None, max_length=100, description="Alias for target_symbol (frontend compatibility)"),
    species_ids: Optional[str] = Query(None, description="Comma-separated species IDs to include (e.g. '1,2,3,4')"),
    min_ba: Optional[float] = Query(None, ge=0, description="Minimum binding affinity threshold"),
    limit: int = Query(10000, ge=1, le=MAX_CONSERVED_REGULATIONS_EXPORT_LIMIT, description="Maximum number of rows to export"),
    db: Session = Depends(get_db),
):
    """
    Export conserved regulations as CSV (streaming).

    Notes:
    - Uses streaming CSV generator to avoid memory spikes.
    - Applies the same filters as `/conservation/regulations` but without pagination.
    """
    effective_min_species = min_conservation if min_conservation is not None else min_species
    species_id_list = _parse_species_ids_param(species_ids)
    if species_id_list is not None and len(species_id_list) < 2:
        raise HTTPException(status_code=400, detail="species_ids: at least 2 species IDs are required")
    if species_id_list is not None and effective_min_species > len(species_id_list):
        raise HTTPException(
            status_code=400,
            detail=f"min_species ({effective_min_species}) cannot be greater than the number of selected species ({len(species_id_list)})",
        )

    normalized_lncrna_symbol = _pick_first_non_empty_str(lncrna_symbol, lncrna_gene_name)
    normalized_target_symbol = _pick_first_non_empty_str(target_symbol, target_gene_name)

    base_query = _build_conserved_regulations_base_query(
        db,
        min_species=effective_min_species,
        lncrna_symbol=normalized_lncrna_symbol,
        target_symbol=normalized_target_symbol,
        species_ids=species_id_list,
        min_ba=min_ba,
    )

    query = (
        base_query
        .order_by(func.count(distinct(Regulation.species_id)).desc())
        .limit(limit)
    )

    fieldnames = [
        "core_id",
        "lncrna_gene_name",
        "target_gene_name",
        "conservation_label",
        "species_count",
        "species_ids",
        "avg_binding_affinity",
        "species_binding_affinities",
    ]

    def row_generator() -> Iterator[Dict[str, Any]]:
        for row in query:
            row_species_ids, row_species_ba_list, row_avg_ba = _parse_species_ba_pairs(getattr(row, "species_ba_pairs", None))
            yield {
                "core_id": row.lncrna_core_id,
                "lncrna_gene_name": row.lncrna_symbol,
                "target_gene_name": row.target_symbol,
                "conservation_label": _compute_conservation_label(row_species_ids),
                "species_count": row.species_count,
                "species_ids": ",".join(str(x) for x in row_species_ids),
                "avg_binding_affinity": row_avg_ba,
                "species_binding_affinities": json.dumps(
                    [x.model_dump() for x in row_species_ba_list],
                    ensure_ascii=False,
                    default=str,
                ),
            }

    return stream_csv_response(
        row_generator(),
        fieldnames=fieldnames,
        filename="conserved_regulations.csv",
    )


# =============================================================================
# Endpoint 4: Venn Diagram Data
# =============================================================================
@router.get("/venn")
@rate_limit("30/minute")
def get_venn_data(
    request: Request,
    data_type: str = Query("lncrna", description="Data type: 'lncrna' or 'regulation'"),
    db: Session = Depends(get_db),
):
    """
    Get data for Venn diagram visualization.

    Returns counts for each species combination (for up to 4 sets).

    Parameters:
    - data_type: 'lncrna' for lncRNA counts, 'regulation' for regulation pair counts

    Returns:
    - sets: List of set labels (species names)
    - data: Dictionary mapping combination codes to counts
      - Keys are combination labels like "1000", "1100", "1111", etc.
      - Values are counts

    Cached for 1 hour.
    """
    if data_type not in ["lncrna", "regulation"]:
        raise HTTPException(
            status_code=400,
            detail="data_type must be 'lncrna' or 'regulation'"
        )

    # Try cache
    cache_key = cache.make_key(f"conservation:venn:{data_type}")
    cached = cache.get(cache_key)
    if cached is not None:
        return cached

    sets = [SPECIES_MAP[sid] for sid in SPECIES_IDS]

    if data_type == "lncrna":
        # Get conservation patterns for all lncRNAs
        lncrna_core_ids = get_lncrna_core_ids(db)
        conservation_map = compute_conservation_map(lncrna_core_ids, db)

        # Count each pattern
        pattern_counts: Dict[str, int] = defaultdict(int)
        for core_id, (label, _) in conservation_map.items():
            pattern_counts[label] += 1

        # Build venn data structure
        # Include only non-zero patterns
        venn_data = {
            label: count
            for label, count in pattern_counts.items()
            if count > 0
        }

    else:  # regulation
        pattern_counts = _get_regulation_pair_pattern_counts(db)
        venn_data = {label: count for label, count in pattern_counts.items() if count > 0}

    result = {
        "sets": sets,
        "data": venn_data,
        "data_type": data_type,
        "total_patterns": len(venn_data),
        "total_items": sum(venn_data.values())
    }

    # Cache for 1 hour
    cache.set(cache_key, result, CacheService.TTL_STATS)

    return result


# =============================================================================
# Endpoint 5: Single LncRNA Conservation Detail
# =============================================================================
@router.get("/lncrna/{core_id}")
@rate_limit("30/minute")
def get_lncrna_conservation(
    request: Request,
    core_id: int,
    db: Session = Depends(get_db),
):
    """
    Get detailed conservation information for a single lncRNA.

    Parameters:
    - core_id: The core_id of the lncRNA

    Returns:
    - Conservation pattern and per-species regulation statistics
    """
    # Verify the core_id exists and is an lncRNA
    core_gene = (
        db.query(CoreGene)
        .filter(CoreGene.core_id == core_id)
        .filter(CoreGene.gene_type == "lncRNA")
        .first()
    )

    if not core_gene:
        raise HTTPException(status_code=404, detail="LncRNA not found")

    # Get conservation data
    conservation_map = compute_conservation_map([core_id], db)
    conservation_label, conservation_count = conservation_map.get(core_id, ("0000", 0))

    # Get per-species information (batch to avoid per-species N+1 queries)
    genes = (
        db.query(Gene)
        .filter(Gene.core_id == core_id)
        .filter(Gene.species_id.in_(SPECIES_IDS))
        .all()
    )
    genes_by_species = {gene.species_id: gene for gene in genes}

    gene_ids = [gene.gene_id for gene in genes]
    stats_by_gene_id: Dict[int, Any] = {}
    if gene_ids:
        stats_rows = (
            db.query(
                Regulation.lncrna_gene_id.label("gene_id"),
                func.count(distinct(Regulation.target_gene_id)).label("target_count"),
                func.avg(Regulation.binding_affinity).label("avg_binding_affinity"),
            )
            .filter(Regulation.lncrna_gene_id.in_(gene_ids))
            .group_by(Regulation.lncrna_gene_id)
            .all()
        )
        stats_by_gene_id = {int(row.gene_id): row for row in stats_rows}

    species_info = []
    for sid in SPECIES_IDS:
        gene = genes_by_species.get(sid)
        if gene:
            stats = stats_by_gene_id.get(gene.gene_id)
            target_count = int(getattr(stats, "target_count", 0) or 0) if stats else 0
            avg_ba = getattr(stats, "avg_binding_affinity", None) if stats else None
            species_info.append({
                "species_id": sid,
                "species_name": SPECIES_MAP[sid],
                "gene_id": gene.gene_id,
                "gene_name": gene.gene_name,
                "gene_ensembl_id": gene.gene_ensembl_id,
                "target_count": target_count,
                "avg_binding_affinity": float(avg_ba) if avg_ba is not None else None
            })
        else:
            species_info.append({
                "species_id": sid,
                "species_name": SPECIES_MAP[sid],
                "gene_id": None,
                "gene_name": None,
                "gene_ensembl_id": None,
                "target_count": 0,
                "avg_binding_affinity": None
            })

    # Get conserved targets (targets regulated in 2+ species)
    LncRNAGene = aliased(Gene, name="lncrna_gene")
    TargetGene = aliased(Gene, name="target_gene")
    TargetCore = aliased(CoreGene, name="target_core")

    # Total unique targets (core-level)
    total_unique_targets = (
        db.query(func.count(distinct(TargetGene.core_id)))
        .select_from(Regulation)
        .join(LncRNAGene, Regulation.lncrna_gene_id == LncRNAGene.gene_id)
        .join(TargetGene, Regulation.target_gene_id == TargetGene.gene_id)
        .filter(LncRNAGene.core_id == core_id)
        .scalar() or 0
    )

    # Top conserved targets (2+ species), computed in SQL to avoid loading all regulation rows into memory
    target_counts_subq = (
        db.query(
            TargetGene.core_id.label("target_core_id"),
            func.min(TargetCore.canonical_symbol).label("target_symbol"),
            func.count(distinct(Regulation.species_id)).label("species_count"),
        )
        .select_from(Regulation)
        .join(LncRNAGene, Regulation.lncrna_gene_id == LncRNAGene.gene_id)
        .join(TargetGene, Regulation.target_gene_id == TargetGene.gene_id)
        .join(TargetCore, TargetGene.core_id == TargetCore.core_id)
        .filter(LncRNAGene.core_id == core_id)
        .group_by(TargetGene.core_id)
        .having(func.count(distinct(Regulation.species_id)) >= 2)
        .subquery()
    )

    conserved_target_count = db.query(func.count()).select_from(target_counts_subq).scalar() or 0

    top_targets = (
        db.query(
            target_counts_subq.c.target_core_id,
            target_counts_subq.c.target_symbol,
            target_counts_subq.c.species_count,
        )
        .order_by(target_counts_subq.c.species_count.desc(), target_counts_subq.c.target_symbol.asc())
        .limit(50)
        .all()
    )

    top_target_core_ids = [int(row.target_core_id) for row in top_targets]
    species_ba_by_target: Dict[int, Dict[int, Optional[float]]] = defaultdict(dict)
    if top_target_core_ids:
        ba_rows = (
            db.query(
                TargetGene.core_id.label("target_core_id"),
                Regulation.species_id.label("species_id"),
                func.avg(Regulation.binding_affinity).label("avg_binding_affinity"),
            )
            .select_from(Regulation)
            .join(LncRNAGene, Regulation.lncrna_gene_id == LncRNAGene.gene_id)
            .join(TargetGene, Regulation.target_gene_id == TargetGene.gene_id)
            .filter(LncRNAGene.core_id == core_id)
            .filter(TargetGene.core_id.in_(top_target_core_ids))
            .group_by(TargetGene.core_id, Regulation.species_id)
            .all()
        )
        for row in ba_rows:
            species_ba_by_target[int(row.target_core_id)][int(row.species_id)] = (
                float(row.avg_binding_affinity) if row.avg_binding_affinity is not None else None
            )

    conserved_targets = []
    for row in top_targets:
        target_core_id = int(row.target_core_id)
        species_ba = species_ba_by_target.get(target_core_id, {})
        present_species = set(species_ba.keys())
        target_label = "".join("1" if sid in present_species else "0" for sid in SPECIES_IDS)
        conserved_targets.append({
            "target_core_id": target_core_id,
            "target_symbol": row.target_symbol,
            "conservation_label": target_label,
            "conservation_count": int(row.species_count),
            "species_binding_affinities": {
                SPECIES_MAP[sid]: species_ba.get(sid)
                for sid in SPECIES_IDS
                if sid in present_species
            }
        })

    return {
        "core_id": core_id,
        "canonical_symbol": core_gene.canonical_symbol,
        "human_ensembl_id": core_gene.human_ensembl_id,
        "conservation_label": conservation_label,
        "conservation_count": conservation_count,
        "species_info": species_info,
        "total_unique_targets": int(total_unique_targets),
        "conserved_targets": conserved_targets,  # 已在 SQL 层 limit 50
        "conserved_target_count": int(conserved_target_count)
    }
