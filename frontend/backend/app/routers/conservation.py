"""
Conservation Analysis API Router
跨物种保守性分析 API 端点

Endpoints:
- GET /conservation/overview - 保守性统计概览
- GET /conservation/matrix - 物种间保守性热图矩阵数据
- GET /conservation/regulations - 保守调控关系列表（分页）
- GET /conservation/venn - Venn 图数据
"""
from typing import Optional, List, Dict, Set
from collections import defaultdict
from fastapi import APIRouter, Depends, Query, HTTPException
from sqlalchemy.orm import Session, aliased
from sqlalchemy import func, distinct, String

from app.core.database import get_db
from app.core.cache import cache, CacheService
from app.core.utils import escape_like_pattern
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


# =============================================================================
# Helper Functions (reusing logic from network.py)
# =============================================================================
def compute_conservation_map(core_ids: list, db: Session) -> Dict[int, tuple]:
    """
    Compute conservation data for a list of core_ids
    Returns: {core_id: (conservation_label, conservation_count)}

    Based on network.py:compute_conservation_map()
    """
    if not core_ids:
        return {}

    # Batch query: get species presence for all core_ids
    species_presence_query = db.query(Gene.core_id, Gene.species_id).filter(
        Gene.core_id.in_(core_ids)
    ).distinct()

    # Build a map: core_id -> set of species_ids
    species_map: Dict[int, Set[int]] = {}
    for core_id, species_id in species_presence_query.all():
        if core_id not in species_map:
            species_map[core_id] = set()
        species_map[core_id].add(species_id)

    # Convert to conservation labels
    result = {}
    for core_id in core_ids:
        present_species = species_map.get(core_id, set())
        conservation_label = "".join(
            "1" if sid in present_species else "0"
            for sid in SPECIES_IDS  # [1, 2, 3, 4]
        )
        conservation_count = len(present_species)
        result[core_id] = (conservation_label, conservation_count)

    return result


def get_lncrna_core_ids(db: Session) -> List[int]:
    """Get all lncRNA core_ids from the database."""
    return [
        row[0] for row in
        db.query(CoreGene.core_id)
        .filter(CoreGene.gene_type == "lncRNA")
        .all()
    ]


def _build_conserved_regulation_items(results: list, db: Session) -> List[ConservedRegulationItem]:
    """
    Build ConservedRegulationItem list from query results.

    Performance: batch compute conservation_map for all core_ids to avoid N+1 queries.
    """
    # Batch compute conservation labels for all core_ids in this page
    core_ids: Set[int] = set()
    for row in results:
        if row.lncrna_core_id is not None:
            core_ids.add(row.lncrna_core_id)
        if row.target_core_id is not None:
            core_ids.add(row.target_core_id)

    conservation_map = compute_conservation_map(list(core_ids), db) if core_ids else {}

    items: List[ConservedRegulationItem] = []
    for row in results:
        # Parse species:ba pairs and build structured data (deduplicate by species)
        species_ba_dict: Dict[int, List[float]] = {}  # species_id -> list of BA values
        species_names_dict: Dict[int, str] = {}  # species_id -> species_name

        if row.species_ba_pairs:
            for pair in row.species_ba_pairs.split(','):
                if ':' in pair:
                    sp_name, ba_str = pair.split(':', 1)
                    sp_name = sp_name.strip()
                    sp_id = SPECIES_NAME_TO_ID.get(sp_name)
                    if sp_id is not None:
                        if sp_id not in species_ba_dict:
                            species_ba_dict[sp_id] = []
                            species_names_dict[sp_id] = sp_name
                        try:
                            ba_val = float(ba_str) if ba_str and ba_str != 'None' else None
                            if ba_val is not None:
                                species_ba_dict[sp_id].append(ba_val)
                        except ValueError:
                            pass

        # Build deduplicated species_ba_list
        species_ba_list: List[SpeciesBindingAffinity] = []
        all_ba_values: List[float] = []

        for sp_id in sorted(species_ba_dict.keys()):
            ba_vals = species_ba_dict[sp_id]
            avg_species_ba = sum(ba_vals) / len(ba_vals) if ba_vals else None
            species_ba_list.append(SpeciesBindingAffinity(
                species_id=sp_id,
                species_name=species_names_dict[sp_id],
                binding_affinity=round(avg_species_ba, 2) if avg_species_ba is not None else None
            ))
            if ba_vals:
                all_ba_values.extend(ba_vals)

        # Get unique species IDs
        species_ids = sorted(species_ba_dict.keys())

        # Calculate overall average binding affinity
        avg_ba = sum(all_ba_values) / len(all_ba_values) if all_ba_values else None

        lncrna_label, _ = conservation_map.get(row.lncrna_core_id, ("0000", 0))

        items.append(ConservedRegulationItem(
            core_id=row.lncrna_core_id,
            lncrna_gene_name=row.lncrna_symbol,
            lncrna_ensembl_id=None,  # Not available in current query
            target_gene_name=row.target_symbol,
            target_ensembl_id=None,  # Not available in current query
            conservation_label=lncrna_label,
            species_count=row.species_count,
            species_ids=species_ids,
            avg_binding_affinity=round(avg_ba, 2) if avg_ba is not None else None,
            species_binding_affinities=species_ba_list
        ))

    return items


# =============================================================================
# Endpoint 1: Overview Statistics
# =============================================================================
@router.get("/overview", response_model=ConservationSummary)
def get_conservation_overview(db: Session = Depends(get_db)):
    """
    Get conservation overview statistics.

    Returns distribution of lncRNAs by conservation level (1-4 species),
    top species combinations, and summary metrics.

    Cached for 1 hour.
    """
    # Try cache first
    cache_key = cache._make_key("conservation:overview")
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

    for core_id, (label, count) in conservation_map.items():
        level_counts[count] += 1
        combination_counts[label] += 1

    # Get total regulations count
    total_regulations = db.query(func.count(Regulation.regulation_id)).scalar() or 0

    # Build distribution by conservation level (1-4)
    distribution = []
    for level in range(1, 5):
        lncrna_count = level_counts.get(level, 0)
        percentage = (lncrna_count / total_lncrnas * 100) if total_lncrnas > 0 else 0

        # Count regulations for lncRNAs at this conservation level
        core_ids_at_level = [
            cid for cid, (_, cnt) in conservation_map.items() if cnt == level
        ]

        if core_ids_at_level:
            # Get gene_ids for these core_ids
            gene_ids = [
                row[0] for row in
                db.query(Gene.gene_id)
                .filter(Gene.core_id.in_(core_ids_at_level))
                .all()
            ]
            reg_count = (
                db.query(func.count(Regulation.regulation_id))
                .filter(Regulation.lncrna_gene_id.in_(gene_ids))
                .scalar() or 0
            ) if gene_ids else 0
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
        core_ids_for_combo = [
            cid for cid, (lbl, _) in conservation_map.items() if lbl == label
        ]

        if core_ids_for_combo:
            gene_ids = [
                row[0] for row in
                db.query(Gene.gene_id)
                .filter(Gene.core_id.in_(core_ids_for_combo))
                .all()
            ]
            reg_count = (
                db.query(func.count(Regulation.regulation_id))
                .filter(Regulation.lncrna_gene_id.in_(gene_ids))
                .scalar() or 0
            ) if gene_ids else 0
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
def get_conservation_matrix(db: Session = Depends(get_db)):
    """
    Get species-to-species conservation matrix for heatmap visualization.

    Returns 4x4 matrices for:
    - Shared lncRNA counts
    - Shared regulation counts
    - Jaccard similarity indices

    Cached for 1 hour.
    """
    # Try cache first
    cache_key = cache._make_key("conservation:matrix")
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

            # Shared regulations (lncRNA-target pairs present in both species)
            if i <= j:  # Only compute for upper triangle + diagonal
                if shared:
                    if i == j:
                        # Diagonal: total regulations for this species
                        # Get gene_ids for shared lncRNAs in this species
                        genes_sp1 = set(
                            row[0] for row in
                            db.query(Gene.gene_id)
                            .filter(Gene.core_id.in_(shared))
                            .filter(Gene.species_id == sid1)
                            .all()
                        )
                        if genes_sp1:
                            reg_count = (
                                db.query(func.count(Regulation.regulation_id))
                                .filter(Regulation.lncrna_gene_id.in_(genes_sp1))
                                .filter(Regulation.species_id == sid1)
                                .scalar() or 0
                            )
                        else:
                            reg_count = 0
                        regulation_matrix[i][j] = reg_count
                    else:
                        # Off-diagonal: count conserved regulation pairs
                        # This is a simplified count - regulations where lncRNA core_id
                        # is present in both species
                        LncRNAGene = aliased(Gene)
                        TargetGene = aliased(Gene)

                        # Get unique (lncrna_core_id, target_core_id) pairs per species
                        # then find intersection
                        pairs_sp1 = set(
                            db.query(LncRNAGene.core_id, TargetGene.core_id)
                            .select_from(Regulation)
                            .join(LncRNAGene, Regulation.lncrna_gene_id == LncRNAGene.gene_id)
                            .join(TargetGene, Regulation.target_gene_id == TargetGene.gene_id)
                            .filter(Regulation.species_id == sid1)
                            .distinct()
                            .all()
                        )

                        pairs_sp2 = set(
                            db.query(LncRNAGene.core_id, TargetGene.core_id)
                            .select_from(Regulation)
                            .join(LncRNAGene, Regulation.lncrna_gene_id == LncRNAGene.gene_id)
                            .join(TargetGene, Regulation.target_gene_id == TargetGene.gene_id)
                            .filter(Regulation.species_id == sid2)
                            .distinct()
                            .all()
                        )

                        shared_pairs = pairs_sp1 & pairs_sp2
                        regulation_matrix[i][j] = len(shared_pairs)
                        regulation_matrix[j][i] = len(shared_pairs)
                else:
                    regulation_matrix[i][j] = 0
                    if i != j:
                        regulation_matrix[j][i] = 0

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
def get_conserved_regulations(
    min_species: int = Query(2, ge=2, le=4, description="Minimum number of species"),
    page: int = Query(1, ge=1, description="Page number"),
    page_size: int = Query(50, ge=10, le=200, description="Items per page"),
    lncrna_symbol: Optional[str] = Query(None, description="Filter by lncRNA symbol"),
    target_symbol: Optional[str] = Query(None, description="Filter by target symbol"),
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
    LncRNAGene = aliased(Gene, name="lncrna_gene")
    TargetGene = aliased(Gene, name="target_gene")
    LncRNACore = aliased(CoreGene, name="lncrna_core")
    TargetCore = aliased(CoreGene, name="target_core")

    # Base query: group by (lncrna_core_id, target_core_id)
    base_query = (
        db.query(
            LncRNAGene.core_id.label("lncrna_core_id"),
            TargetGene.core_id.label("target_core_id"),
            func.count(distinct(Regulation.species_id)).label("species_count"),
            func.min(LncRNACore.canonical_symbol).label("lncrna_symbol"),
            func.min(TargetCore.canonical_symbol).label("target_symbol"),
            # Aggregate binding affinities per species using PostgreSQL array_agg
            func.string_agg(
                distinct(func.concat(Species.display_name, ':', func.cast(Regulation.binding_affinity, String))),
                ','
            ).label("species_ba_pairs")
        )
        .select_from(Regulation)
        .join(LncRNAGene, Regulation.lncrna_gene_id == LncRNAGene.gene_id)
        .join(TargetGene, Regulation.target_gene_id == TargetGene.gene_id)
        .join(LncRNACore, LncRNAGene.core_id == LncRNACore.core_id)
        .join(TargetCore, TargetGene.core_id == TargetCore.core_id)
        .join(Species, Regulation.species_id == Species.species_id)
        .filter(LncRNACore.gene_type == "lncRNA")
        .group_by(LncRNAGene.core_id, TargetGene.core_id)
        .having(func.count(distinct(Regulation.species_id)) >= min_species)
    )

    # Apply symbol filters if provided
    if lncrna_symbol:
        escaped = escape_like_pattern(lncrna_symbol)
        base_query = base_query.filter(
            LncRNACore.canonical_symbol.ilike(f"%{escaped}%", escape="\\")
        )
    if target_symbol:
        escaped = escape_like_pattern(target_symbol)
        base_query = base_query.filter(
            TargetCore.canonical_symbol.ilike(f"%{escaped}%", escape="\\")
        )

    # Count total (using subquery for efficiency)
    count_subq = base_query.subquery()
    total = db.query(func.count()).select_from(count_subq).scalar() or 0

    # Paginate
    offset = (page - 1) * page_size
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
        min_species=min_species
    )


# =============================================================================
# Endpoint 4: Venn Diagram Data
# =============================================================================
@router.get("/venn")
def get_venn_data(
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
    cache_key = cache._make_key(f"conservation:venn:{data_type}")
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
        # Get conservation patterns for regulation pairs (lncrna_core_id, target_core_id)
        LncRNAGene = aliased(Gene, name="lncrna_gene")
        TargetGene = aliased(Gene, name="target_gene")

        # Get all unique (lncrna_core_id, target_core_id, species_id) combinations
        regulation_species = (
            db.query(
                LncRNAGene.core_id.label("lncrna_core_id"),
                TargetGene.core_id.label("target_core_id"),
                Regulation.species_id
            )
            .select_from(Regulation)
            .join(LncRNAGene, Regulation.lncrna_gene_id == LncRNAGene.gene_id)
            .join(TargetGene, Regulation.target_gene_id == TargetGene.gene_id)
            .distinct()
            .all()
        )

        # Build (lncrna_core_id, target_core_id) -> set of species_ids
        pair_species: Dict[tuple, Set[int]] = defaultdict(set)
        for lncrna_cid, target_cid, species_id in regulation_species:
            pair_species[(lncrna_cid, target_cid)].add(species_id)

        # Count each pattern
        pattern_counts: Dict[str, int] = defaultdict(int)
        for (lncrna_cid, target_cid), species_set in pair_species.items():
            label = "".join(
                "1" if sid in species_set else "0"
                for sid in SPECIES_IDS
            )
            pattern_counts[label] += 1

        venn_data = {
            label: count
            for label, count in pattern_counts.items()
            if count > 0
        }

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
def get_lncrna_conservation(
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

    # Get per-species information
    species_info = []
    for sid in SPECIES_IDS:
        # Get gene info in this species
        gene = (
            db.query(Gene)
            .filter(Gene.core_id == core_id)
            .filter(Gene.species_id == sid)
            .first()
        )

        if gene:
            # Count targets in this species
            target_count = (
                db.query(func.count(distinct(Regulation.target_gene_id)))
                .filter(Regulation.lncrna_gene_id == gene.gene_id)
                .scalar() or 0
            )

            # Average binding affinity
            avg_ba = (
                db.query(func.avg(Regulation.binding_affinity))
                .filter(Regulation.lncrna_gene_id == gene.gene_id)
                .scalar()
            )

            species_info.append({
                "species_id": sid,
                "species_name": SPECIES_MAP[sid],
                "gene_id": gene.gene_id,
                "gene_name": gene.gene_name,
                "gene_ensembl_id": gene.gene_ensembl_id,
                "target_count": target_count,
                "avg_binding_affinity": float(avg_ba) if avg_ba else None
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

    # Find all target core_ids and their species presence
    target_species_data = (
        db.query(
            TargetGene.core_id.label("target_core_id"),
            TargetCore.canonical_symbol.label("target_symbol"),
            Regulation.species_id,
            Regulation.binding_affinity
        )
        .select_from(Regulation)
        .join(LncRNAGene, Regulation.lncrna_gene_id == LncRNAGene.gene_id)
        .join(TargetGene, Regulation.target_gene_id == TargetGene.gene_id)
        .join(TargetCore, TargetGene.core_id == TargetCore.core_id)
        .filter(LncRNAGene.core_id == core_id)
        .all()
    )

    # Group by target core_id
    target_map: Dict[int, Dict] = {}
    for target_cid, target_symbol, species_id, ba in target_species_data:
        if target_cid not in target_map:
            target_map[target_cid] = {
                "target_core_id": target_cid,
                "target_symbol": target_symbol,
                "species": set(),
                "species_ba": {}
            }
        target_map[target_cid]["species"].add(species_id)
        target_map[target_cid]["species_ba"][species_id] = float(ba) if ba else None

    # Filter to conserved targets (2+ species)
    conserved_targets = []
    for target_cid, data in target_map.items():
        if len(data["species"]) >= 2:
            target_label = "".join(
                "1" if sid in data["species"] else "0"
                for sid in SPECIES_IDS
            )
            conserved_targets.append({
                "target_core_id": data["target_core_id"],
                "target_symbol": data["target_symbol"],
                "conservation_label": target_label,
                "conservation_count": len(data["species"]),
                "species_binding_affinities": {
                    SPECIES_MAP[sid]: ba
                    for sid, ba in data["species_ba"].items()
                }
            })

    # Sort by conservation count descending
    conserved_targets.sort(key=lambda x: -x["conservation_count"])

    return {
        "core_id": core_id,
        "canonical_symbol": core_gene.canonical_symbol,
        "human_ensembl_id": core_gene.human_ensembl_id,
        "conservation_label": conservation_label,
        "conservation_count": conservation_count,
        "species_info": species_info,
        "total_unique_targets": len(target_map),
        "conserved_targets": conserved_targets[:50],  # Limit to top 50
        "conserved_target_count": len(conserved_targets)
    }


