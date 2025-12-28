"""
ChIP-seq Gene Analysis API Router
基因级ChIP-seq分析端点
"""
import logging
import statistics
import time
from itertools import combinations
from typing import Optional, List, Dict, Any

from fastapi import APIRouter, Depends, HTTPException, Query, Request
from sqlalchemy.orm import Session
from sqlalchemy import bindparam, case, column, func, literal, select, values
from sqlalchemy.sql.expression import funcfilter

from app.core.database import get_db
from app.core.cache import cache, cached
from app.core.exceptions import sanitize_db_error
from app.core.utils import sanitize_for_log
from app.core.validators import normalize_optional_str, parse_comma_list
from app.models import Gene, ChIPSeqPeak, ChIPSeqExperiment, EpigeneticMarkType
from app.schemas.chipseq import (
    GeneChIPSeqResponse,
    GeneChIPSeqSummary,
    GenePeakAssociation,
    MarkSummaryStats,
    ChIPSeqComparisonResponse,
    MarkComparisonEntry,
    ChIPSeqPeakCompact,
    OverlapRegion,
    OverlapStatistics,
    CellLineComparisonResponse,
    CellLineComparisonEntry,
    CellLineOverlapRegion,
    CellLineOverlapStatistics,
    HeatmapMatrixResponse,
    CellMarkStats,
    BatchHeatmapMatrixRequest,
    BatchHeatmapMatrixResponse,
)

# 从工具模块导入分析函数
from app.utils.chipseq_analysis import (
    find_pairwise_overlaps,
    compute_mark_statistics,
    find_cell_line_overlaps,
    compute_jaccard_index,
    find_common_peaks,
)
from app.utils.chipseq_db import parse_mark_types

# 从共享模块导入 rate_limit 装饰器和常量（避免与主路由形成循环依赖）
from app.routers.chipseq_rate_limit import rate_limit, DEFAULT_FLANKING_REGION

logger = logging.getLogger(__name__)

router = APIRouter()

# Phase 9.12: 比较端点的最大项数限制（与 heatmap 一致）
MAX_COMPARE_MARKS = 8  # 与 heatmap marks 限制一致
MAX_COMPARE_CELL_TYPES = 10  # 与 heatmap cell_types 限制一致


@router.get("/genes/{gene_id}", response_model=GeneChIPSeqResponse)
@rate_limit("30/minute")
def get_gene_chipseq(
    request: Request,
    gene_id: int,
    mark_type: Optional[str] = Query(
        None,
        description="Filter by mark type(s), comma-separated (e.g., H3K27me3,H3K4me3)"
    ),
    mark_category: Optional[str] = Query(None, max_length=50, description="Filter by mark category"),
    experiment_id: Optional[int] = Query(None, description="Filter by specific experiment"),
    min_fold_enrichment: Optional[float] = Query(
        None,
        ge=0,
        description="Minimum fold enrichment threshold"
    ),
    max_qvalue: Optional[float] = Query(
        0.05,
        ge=0,
        le=1,
        description="Maximum q-value threshold (default: 0.05)"
    ),
    flanking: int = Query(
        DEFAULT_FLANKING_REGION,
        ge=0,
        le=100000,
        description="Flanking region size in bp"
    ),
    db: Session = Depends(get_db),
):
    """
    Get ChIP-seq peaks for a gene region

    Returns all peaks overlapping with the gene region (+/- flanking).
    Results are grouped by mark type.

    **Key Parameters:**
    - `mark_type`: Filter by one or more mark types (comma-separated)
    - `flanking`: Extend query region on each side (default: 10kb)
    - `max_qvalue`: Only return significant peaks (default: q < 0.05)

    **Example:**
    ```
    GET /features/chipseq/genes/12345?mark_type=H3K27me3,H3K4me3&flanking=20000
    ```
    """
    # 1. Query gene information
    gene = db.query(Gene).filter(Gene.gene_id == gene_id).first()
    if not gene:
        raise HTTPException(status_code=404, detail="Gene not found")

    # Check gene coordinates
    if gene.gene_start is None or gene.gene_end is None:
        raise HTTPException(
            status_code=400,
            detail=f"Gene {gene_id} has no coordinate information"
        )

    # 2. Calculate query region
    region_start = max(0, gene.gene_start - flanking)
    region_end = gene.gene_end + flanking
    tss = gene.gene_start if gene.strand == '+' else gene.gene_end

    # 3. Parse mark types
    mark_types = parse_mark_types(mark_type)
    normalized_mark_category = normalize_optional_str(mark_category)

    # 4. Build and execute query
    is_postgresql = db.get_bind().dialect.name == "postgresql"
    bp_region_start = bindparam("region_start")
    bp_region_end = bindparam("region_end")
    if is_postgresql:
        region_predicate = (
            func.int8range(ChIPSeqPeak.peak_start, ChIPSeqPeak.peak_end, "[)")
            .op("&&")(func.int8range(bp_region_start, bp_region_end, "[)"))
        )
    else:
        region_predicate = (ChIPSeqPeak.peak_start < bp_region_end) & (ChIPSeqPeak.peak_end > bp_region_start)

    params = {
        "species_id": gene.species_id,
        "chromosome": gene.chromosome,
        "region_start": region_start,
        "region_end": region_end,
        "gene_start": gene.gene_start,
        "gene_end": gene.gene_end,
        "tss": tss,
        "strand": gene.strand or '+',
    }
    where_conditions = [
        ChIPSeqPeak.species_id == bindparam("species_id"),
        ChIPSeqPeak.chromosome == bindparam("chromosome"),
        region_predicate,
        ChIPSeqExperiment.is_active.is_(True),
    ]
    if mark_types is not None:
        where_conditions.append(EpigeneticMarkType.mark_name.in_(bindparam("mark_types", expanding=True)))
        params["mark_types"] = mark_types
    if normalized_mark_category is not None:
        where_conditions.append(EpigeneticMarkType.mark_category == bindparam("mark_category"))
        params["mark_category"] = normalized_mark_category
    if experiment_id is not None:
        where_conditions.append(ChIPSeqExperiment.experiment_id == bindparam("experiment_id"))
        params["experiment_id"] = experiment_id
    if min_fold_enrichment is not None:
        where_conditions.append(ChIPSeqPeak.fold_enrichment >= bindparam("min_fold_enrichment"))
        params["min_fold_enrichment"] = min_fold_enrichment
    if max_qvalue is not None:
        where_conditions.append(
            (ChIPSeqPeak.qvalue.is_(None)) | (ChIPSeqPeak.qvalue <= bindparam("max_qvalue"))
        )
        params["max_qvalue"] = max_qvalue

    strand_is_plus = bindparam("strand") == "+"
    peak_midpoint = func.coalesce(ChIPSeqPeak.summit_position, (ChIPSeqPeak.peak_start + ChIPSeqPeak.peak_end) / 2)
    distance_to_tss_expr = case(
        (strand_is_plus, peak_midpoint - bindparam("tss")),
        else_=bindparam("tss") - peak_midpoint,
    ).label("distance_to_tss")

    peak_before_gene_expr = case(
        (strand_is_plus, literal("upstream")),
        else_=literal("downstream"),
    )
    peak_after_gene_expr = case(
        (strand_is_plus, literal("downstream")),
        else_=literal("upstream"),
    )
    overlap_type_expr = case(
        (
            (ChIPSeqPeak.peak_start <= bindparam("gene_start"))
            & (ChIPSeqPeak.peak_end >= bindparam("gene_end")),
            literal("overlapping"),
        ),
        (
            (ChIPSeqPeak.peak_start >= bindparam("gene_start"))
            & (ChIPSeqPeak.peak_end <= bindparam("gene_end")),
            literal("gene_body"),
        ),
        (ChIPSeqPeak.peak_end <= bindparam("gene_start"), peak_before_gene_expr),
        (ChIPSeqPeak.peak_start >= bindparam("gene_end"), peak_after_gene_expr),
        (func.abs(peak_midpoint - bindparam("tss")) <= 2000, literal("promoter")),
        else_=literal("gene_body"),
    ).label("overlap_type")

    overlap_bp_expr = func.greatest(
        0,
        func.least(ChIPSeqPeak.peak_end, bindparam("region_end"))
        - func.greatest(ChIPSeqPeak.peak_start, bindparam("region_start")),
    ).label("overlap_bp")

    peak_width_expr = (ChIPSeqPeak.peak_end - ChIPSeqPeak.peak_start).label("peak_width")

    stmt = (
        select(
            ChIPSeqPeak.peak_id,
            ChIPSeqPeak.experiment_id,
            EpigeneticMarkType.mark_name,
            EpigeneticMarkType.mark_category,
            EpigeneticMarkType.display_color,
            ChIPSeqPeak.chromosome,
            ChIPSeqPeak.peak_start,
            ChIPSeqPeak.peak_end,
            ChIPSeqPeak.summit_position,
            ChIPSeqPeak.fold_enrichment,
            ChIPSeqPeak.qvalue,
            peak_width_expr,
            distance_to_tss_expr,
            overlap_type_expr,
            overlap_bp_expr,
        )
        .select_from(ChIPSeqPeak)
        .join(ChIPSeqExperiment, ChIPSeqPeak.experiment_id == ChIPSeqExperiment.experiment_id)
        .join(EpigeneticMarkType, ChIPSeqExperiment.mark_type_id == EpigeneticMarkType.mark_type_id)
        .where(*where_conditions)
        .order_by(EpigeneticMarkType.sort_order, EpigeneticMarkType.mark_name, ChIPSeqPeak.fold_enrichment.desc())
    )

    rows = db.execute(stmt, params).fetchall()

    # 5. Group by mark type
    marks_dict = {}
    for row in rows:
        mark_name = row[2]
        if mark_name not in marks_dict:
            marks_dict[mark_name] = []

        marks_dict[mark_name].append(GenePeakAssociation(
            peak_id=row[0],
            chromosome=row[5],
            peak_start=row[6],
            peak_end=row[7],
            summit_position=row[8],
            fold_enrichment=float(row[9]) if row[9] else None,
            qvalue=float(row[10]) if row[10] else None,
            distance_to_tss=row[12],
            overlap_type=row[13],
            overlap_bp=row[14],
            mark_type=row[2],
            mark_category=row[3],
            experiment_id=row[1],
        ))

    return GeneChIPSeqResponse(
        gene_id=gene_id,
        gene_name=gene.gene_name or "Unknown",
        chromosome=gene.chromosome,
        gene_start=gene.gene_start,
        gene_end=gene.gene_end,
        strand=gene.strand or '.',
        region_start=region_start,
        region_end=region_end,
        marks=marks_dict,
        total_peaks=len(rows),
        marks_present=list(marks_dict.keys()),
    )


@router.get("/genes/{gene_id}/summary", response_model=GeneChIPSeqSummary)
@rate_limit("60/minute")  # Rate limit: 60 requests per minute per IP
@cached("chipseq:summary", ttl=cache.TTL_LIST)  # Cache: 5 minutes (TTL_LIST=300)
def get_gene_chipseq_summary(
    request: Request,  # Required for rate limiting
    gene_id: int,
    flanking: int = Query(DEFAULT_FLANKING_REGION, ge=0, le=100000),
    max_qvalue: Optional[float] = Query(0.05, ge=0, le=1),
    db: Session = Depends(get_db),
):
    """
    Get ChIP-seq summary statistics for a gene

    Returns aggregated statistics for all mark types with peaks in the gene region.
    Includes bivalent domain detection.

    **Caching:** Results are cached for 5 minutes.
    **Rate Limit:** 60 requests per minute per IP.
    """
    # 1. Query gene
    gene = db.query(Gene).filter(Gene.gene_id == gene_id).first()
    if not gene:
        raise HTTPException(status_code=404, detail="Gene not found")

    # Check gene coordinates
    if gene.gene_start is None or gene.gene_end is None:
        raise HTTPException(
            status_code=400,
            detail=f"Gene {gene_id} has no coordinate information"
        )

    region_start = max(0, gene.gene_start - flanking)
    region_end = gene.gene_end + flanking
    region_length = region_end - region_start

    # 2. Query summary stats per mark
    bp_region_start = bindparam("region_start")
    bp_region_end = bindparam("region_end")
    is_postgresql = db.get_bind().dialect.name == "postgresql"
    if is_postgresql:
        region_predicate = (
            func.int8range(ChIPSeqPeak.peak_start, ChIPSeqPeak.peak_end, "[)")
            .op("&&")(func.int8range(bp_region_start, bp_region_end, "[)"))
        )
    else:
        region_predicate = (ChIPSeqPeak.peak_start < bp_region_end) & (ChIPSeqPeak.peak_end > bp_region_start)

    midpoint_expr = func.coalesce(ChIPSeqPeak.summit_position, (ChIPSeqPeak.peak_start + ChIPSeqPeak.peak_end) / 2)
    tss_expr = case(
        (bindparam("strand") == "+", bindparam("gene_start")),
        else_=bindparam("gene_end"),
    )
    overlap_type_expr = case(
        (
            (ChIPSeqPeak.peak_start >= bindparam("gene_start")) & (ChIPSeqPeak.peak_end <= bindparam("gene_end")),
            literal("gene_body"),
        ),
        (func.abs(midpoint_expr - tss_expr) <= 2000, literal("promoter")),
        else_=literal("flanking"),
    )

    coverage_expr = func.sum(
        func.greatest(
            0,
            func.least(ChIPSeqPeak.peak_end, bp_region_end) - func.greatest(ChIPSeqPeak.peak_start, bp_region_start),
        )
    ).label("coverage_bp")

    where_conditions = [
        ChIPSeqPeak.species_id == bindparam("species_id"),
        ChIPSeqPeak.chromosome == bindparam("chromosome"),
        region_predicate,
        ChIPSeqExperiment.is_active.is_(True),
    ]
    if max_qvalue is not None:
        where_conditions.append((ChIPSeqPeak.qvalue.is_(None)) | (ChIPSeqPeak.qvalue <= bindparam("max_qvalue")))

    stmt = (
        select(
            EpigeneticMarkType.mark_name,
            EpigeneticMarkType.mark_category,
            func.count().label("peak_count"),
            func.max(ChIPSeqPeak.fold_enrichment).label("max_fold_enrichment"),
            func.avg(ChIPSeqPeak.fold_enrichment).label("avg_fold_enrichment"),
            func.min(ChIPSeqPeak.qvalue).label("best_qvalue"),
            coverage_expr,
            func.array_agg(func.distinct(overlap_type_expr)).label("overlap_types"),
        )
        .select_from(ChIPSeqPeak)
        .join(ChIPSeqExperiment, ChIPSeqPeak.experiment_id == ChIPSeqExperiment.experiment_id)
        .join(EpigeneticMarkType, ChIPSeqExperiment.mark_type_id == EpigeneticMarkType.mark_type_id)
        .where(*where_conditions)
        .group_by(EpigeneticMarkType.mark_name, EpigeneticMarkType.mark_category)
        .order_by(EpigeneticMarkType.mark_category, EpigeneticMarkType.mark_name)
    )

    rows = db.execute(
        stmt,
        {
            "species_id": gene.species_id,
            "chromosome": gene.chromosome,
            "region_start": region_start,
            "region_end": region_end,
            "gene_start": gene.gene_start,
            "gene_end": gene.gene_end,
            "strand": gene.strand or "+",
            "max_qvalue": max_qvalue,
        },
    ).fetchall()

    # 3. Build summary
    mark_summaries = []
    mark_names = set()
    total_peaks = 0

    for row in rows:
        mark_names.add(row[0])
        total_peaks += row[2]
        mark_summaries.append(MarkSummaryStats(
            mark_type=row[0],
            mark_category=row[1],
            peak_count=row[2],
            max_fold_enrichment=float(row[3]) if row[3] else None,
            avg_fold_enrichment=float(row[4]) if row[4] else None,
            best_qvalue=float(row[5]) if row[5] else None,
            total_peak_coverage_bp=int(row[6]) if row[6] else 0,
            overlap_types=row[7] if row[7] else [],
        ))

    # 4. Check for bivalent domain
    has_bivalent = 'H3K4me3' in mark_names and 'H3K27me3' in mark_names

    return GeneChIPSeqSummary(
        gene_id=gene_id,
        gene_name=gene.gene_name or "Unknown",
        chromosome=gene.chromosome,
        gene_start=gene.gene_start,
        gene_end=gene.gene_end,
        region_start=region_start,
        region_end=region_end,
        region_length=region_length,
        mark_summaries=mark_summaries,
        total_marks=len(mark_names),
        total_peaks=total_peaks,
        has_bivalent_domain=has_bivalent,
    )


# =============================================================================
# Multi-Mark Comparison Endpoint (Enhanced Phase 2.5)
# =============================================================================

@router.get("/genes/{gene_id}/compare", response_model=ChIPSeqComparisonResponse)
@rate_limit("30/minute")  # Rate limit: 30 requests per minute per IP (expensive query)
@cached("chipseq:compare", ttl=cache.TTL_DETAIL)  # Cache: 10 minutes (TTL_DETAIL=600)
def compare_gene_marks(
    request: Request,  # Required for rate limiting
    gene_id: int,
    marks: str = Query(
        ...,
        description="Comma-separated list of marks to compare (e.g., H3K27me3,H3K4me3)"
    ),
    flanking: int = Query(DEFAULT_FLANKING_REGION, ge=0, le=100000),
    max_qvalue: Optional[float] = Query(0.05, ge=0, le=1),
    include_all_overlaps: bool = Query(
        True,
        description="Include all pairwise overlaps (not just bivalent)"
    ),
    db: Session = Depends(get_db),
):
    """
    Compare multiple ChIP-seq marks for a gene (Enhanced Phase 2.5)

    Returns peaks for each specified mark with enhanced statistics:
    - median_fold_enrichment, std_fold_enrichment
    - total_coverage_bp (total base pairs covered)
    - peak_width_percentiles (p25, p50, p75)

    Also includes generalized overlap detection for any mark pair,
    not just H3K4me3 + H3K27me3 bivalent domains.

    **Example:**
    ```
    GET /features/chipseq/genes/12345/compare?marks=H3K27me3,H3K4me3,H3K27ac
    ```

    **Caching:** Results are cached for 10 minutes.
    **Rate Limit:** 30 requests per minute per IP.

    **New in Phase 2.5:**
    - Enhanced statistics per mark
    - Generalized pairwise overlap detection
    - Overlap statistics summary
    """
    # 1. Parse marks (Phase 9.12: 使用共享验证器，限制最大数量防止 O(n²) DoS)
    mark_list = parse_comma_list(marks, max_items=MAX_COMPARE_MARKS, param_name="marks")
    if not mark_list or len(mark_list) < 2:
        raise HTTPException(
            status_code=400,
            detail=f"2-{MAX_COMPARE_MARKS} marks are required for comparison"
        )

    # 2. Query gene
    gene = db.query(Gene).filter(Gene.gene_id == gene_id).first()
    if not gene:
        raise HTTPException(status_code=404, detail="Gene not found")

    # Check gene coordinates
    if gene.gene_start is None or gene.gene_end is None:
        raise HTTPException(
            status_code=400,
            detail=f"Gene {gene_id} has no coordinate information"
        )

    region_start = max(0, gene.gene_start - flanking)
    region_end = gene.gene_end + flanking

    # 3. Query peaks for each mark with peak_width
    bp_region_start = bindparam("region_start")
    bp_region_end = bindparam("region_end")
    is_postgresql = db.get_bind().dialect.name == "postgresql"
    if is_postgresql:
        region_predicate = (
            func.int8range(ChIPSeqPeak.peak_start, ChIPSeqPeak.peak_end, "[)")
            .op("&&")(func.int8range(bp_region_start, bp_region_end, "[)"))
        )
    else:
        region_predicate = (ChIPSeqPeak.peak_start < bp_region_end) & (ChIPSeqPeak.peak_end > bp_region_start)

    where_conditions = [
        ChIPSeqPeak.species_id == bindparam("species_id"),
        ChIPSeqPeak.chromosome == bindparam("chromosome"),
        region_predicate,
        ChIPSeqExperiment.is_active.is_(True),
        EpigeneticMarkType.mark_name.in_(bindparam("mark_list", expanding=True)),
    ]
    if max_qvalue is not None:
        where_conditions.append((ChIPSeqPeak.qvalue.is_(None)) | (ChIPSeqPeak.qvalue <= bindparam("max_qvalue")))

    peak_width_expr = (ChIPSeqPeak.peak_end - ChIPSeqPeak.peak_start).label("peak_width")
    stmt = (
        select(
            ChIPSeqPeak.peak_id,
            EpigeneticMarkType.mark_name,
            EpigeneticMarkType.mark_category,
            EpigeneticMarkType.display_color,
            ChIPSeqPeak.chromosome,
            ChIPSeqPeak.peak_start,
            ChIPSeqPeak.peak_end,
            ChIPSeqPeak.summit_position,
            ChIPSeqPeak.fold_enrichment,
            ChIPSeqPeak.qvalue,
            peak_width_expr,
        )
        .select_from(ChIPSeqPeak)
        .join(ChIPSeqExperiment, ChIPSeqPeak.experiment_id == ChIPSeqExperiment.experiment_id)
        .join(EpigeneticMarkType, ChIPSeqExperiment.mark_type_id == EpigeneticMarkType.mark_type_id)
        .where(*where_conditions)
        .order_by(EpigeneticMarkType.mark_name, ChIPSeqPeak.peak_start)
    )

    rows = db.execute(
        stmt,
        {
            "species_id": gene.species_id,
            "chromosome": gene.chromosome,
            "region_start": region_start,
            "region_end": region_end,
            "mark_list": mark_list,
            "max_qvalue": max_qvalue,
        },
    ).fetchall()

    # 4. Group by mark
    marks_data: Dict[str, Dict[str, Any]] = {}
    for row in rows:
        mark_name = row[1]
        if mark_name not in marks_data:
            marks_data[mark_name] = {
                "mark_category": row[2],
                "display_color": row[3],
                "peaks": [],
            }

        marks_data[mark_name]["peaks"].append({
            "peak_id": row[0],
            "chromosome": row[4],
            "peak_start": row[5],
            "peak_end": row[6],
            "summit": row[7],
            "fold_enrichment": float(row[8]) if row[8] else None,
            "qvalue": float(row[9]) if row[9] else None,
            "mark_type": mark_name,
            "peak_width": row[10],
        })

    # 5. Build comparison entries with enhanced statistics
    mark_entries = []
    for mark_name, data in marks_data.items():
        peaks = data["peaks"]

        # Compute enhanced statistics
        stats = compute_mark_statistics(peaks, region_start, region_end)

        mark_entries.append(MarkComparisonEntry(
            mark_type=mark_name,
            mark_category=data["mark_category"],
            display_color=data["display_color"],
            peaks=[ChIPSeqPeakCompact(**{k: v for k, v in p.items() if k != "peak_width"}) for p in peaks],
            peak_count=len(peaks),
            avg_fold_enrichment=stats["avg_fold_enrichment"],
            median_fold_enrichment=stats["median_fold_enrichment"],
            std_fold_enrichment=stats["std_fold_enrichment"],
            total_coverage_bp=stats["total_coverage_bp"],
            peak_width_percentiles=stats["peak_width_percentiles"],
        ))

    # 6. Find all pairwise overlapping regions (generalized algorithm)
    all_overlaps: List[OverlapRegion] = []
    overlap_stats: List[OverlapStatistics] = []
    bivalent_regions: List[Dict[str, Any]] = []

    mark_names = list(marks_data.keys())

    if include_all_overlaps and len(mark_names) >= 2:
        for mark_1, mark_2 in combinations(mark_names, 2):
            overlaps = find_pairwise_overlaps(
                marks_data[mark_1]["peaks"],
                marks_data[mark_2]["peaks"],
                mark_1,
                mark_2,
                gene.chromosome,
            )

            all_overlaps.extend(overlaps)

            # Compute overlap statistics for this pair
            if overlaps:
                total_bp = sum(o.length for o in overlaps)
                is_bivalent = (
                    (mark_1 == "H3K4me3" and mark_2 == "H3K27me3") or
                    (mark_1 == "H3K27me3" and mark_2 == "H3K4me3")
                )

                overlap_stats.append(OverlapStatistics(
                    mark_pair=f"{mark_1}:{mark_2}",
                    overlap_count=len(overlaps),
                    total_overlap_bp=total_bp,
                    avg_overlap_length=total_bp / len(overlaps),
                    is_bivalent=is_bivalent,
                ))

                # Build legacy bivalent_regions for backward compatibility
                if is_bivalent:
                    for o in overlaps:
                        bivalent_regions.append({
                            "chromosome": o.chromosome,
                            "start": o.start,
                            "end": o.end,
                            "length": o.length,
                            "h3k4me3_peak_id": o.mark_1_peak_id if o.mark_1 == "H3K4me3" else o.mark_2_peak_id,
                            "h3k27me3_peak_id": o.mark_1_peak_id if o.mark_1 == "H3K27me3" else o.mark_2_peak_id,
                        })

    return ChIPSeqComparisonResponse(
        gene_id=gene_id,
        gene_name=gene.gene_name or "Unknown",
        chromosome=gene.chromosome,
        region_start=region_start,
        region_end=region_end,
        marks=mark_entries,
        all_overlaps=all_overlaps if all_overlaps else None,
        overlap_statistics=overlap_stats if overlap_stats else None,
        overlapping_regions=None,  # Deprecated
        bivalent_regions=bivalent_regions if bivalent_regions else None,
    )


# =============================================================================
# Cross Cell-Line Comparison (Fixed Mark, Compare Cell Types)
# =============================================================================

@router.get("/genes/{gene_id}/compare-cell-lines", response_model=CellLineComparisonResponse)
@rate_limit("30/minute")  # Rate limit: 30 requests per minute per IP (expensive query)
@cached("chipseq:compare-cell-lines", ttl=cache.TTL_DETAIL)  # Cache: 10 minutes (TTL_DETAIL=600)
def compare_gene_cell_lines(
    request: Request,  # Required for rate limiting
    gene_id: int,
    mark_type: str = Query(
        ...,
        description="Mark type to compare across cell lines (e.g., H3K27me3)"
    ),
    cell_types: str = Query(
        ...,
        description="Comma-separated cell types to compare (e.g., K562,HepG2,H1-hESC)"
    ),
    flanking: int = Query(DEFAULT_FLANKING_REGION, ge=0, le=100000),
    max_qvalue: Optional[float] = Query(0.05, ge=0, le=1),
    include_overlaps: bool = Query(
        True,
        description="Include pairwise overlap analysis between cell lines"
    ),
    db: Session = Depends(get_db),
):
    """
    Compare same ChIP-seq mark across multiple cell lines for a gene.

    This endpoint provides a new dimension of analysis: instead of comparing
    multiple marks in one cell type, it compares the same mark across different
    cell types (e.g., K562, GM12878, HepG2, H1-hESC).

    Returns peaks and statistics for each cell line, plus overlap analysis
    to identify conserved or cell-type-specific regulatory regions.

    **Example:**
    ```
    GET /features/chipseq/genes/17276/compare-cell-lines?mark_type=H3K27me3&cell_types=K562,HepG2,H1-hESC
    ```

    **Caching:** Results are cached for 10 minutes.
    **Rate Limit:** 30 requests per minute per IP.

    **Returns:**
    - Peak data for each cell line
    - Statistics (median fold enrichment, coverage, etc.)
    - Pairwise overlap regions between cell lines
    - Jaccard similarity index for each cell line pair
    - Count of peaks present in all cell lines

    **Use cases:**
    - Identify cell-type-specific regulatory elements
    - Find conserved epigenetic marks across cell types
    - Compare chromatin states between differentiated and stem cells
    """
    # 1. Parse and validate cell types (Phase 9.12: 使用共享验证器，限制最大数量防止 O(n²) DoS)
    cell_type_list = parse_comma_list(cell_types, max_items=MAX_COMPARE_CELL_TYPES, param_name="cell_types")
    if not cell_type_list or len(cell_type_list) < 2:
        raise HTTPException(
            status_code=400,
            detail=f"2-{MAX_COMPARE_CELL_TYPES} cell types are required for comparison"
        )

    # 2. Query gene
    gene = db.query(Gene).filter(Gene.gene_id == gene_id).first()
    if not gene:
        raise HTTPException(status_code=404, detail=f"Gene {gene_id} not found")

    # Check gene coordinates
    if gene.gene_start is None or gene.gene_end is None:
        raise HTTPException(
            status_code=400,
            detail=f"Gene {gene_id} has no coordinate information"
        )

    region_start = max(0, gene.gene_start - flanking)
    region_end = gene.gene_end + flanking

    # 3. Query peaks for each cell type
    bp_region_start = bindparam("region_start")
    bp_region_end = bindparam("region_end")
    is_postgresql = db.get_bind().dialect.name == "postgresql"
    if is_postgresql:
        region_predicate = (
            func.int8range(ChIPSeqPeak.peak_start, ChIPSeqPeak.peak_end, "[)")
            .op("&&")(func.int8range(bp_region_start, bp_region_end, "[)"))
        )
    else:
        region_predicate = (ChIPSeqPeak.peak_start < bp_region_end) & (ChIPSeqPeak.peak_end > bp_region_start)

    where_conditions = [
        ChIPSeqPeak.species_id == bindparam("species_id"),
        ChIPSeqPeak.chromosome == bindparam("chromosome"),
        region_predicate,
        ChIPSeqExperiment.is_active.is_(True),
        EpigeneticMarkType.mark_name == bindparam("mark_type"),
        ChIPSeqExperiment.cell_type.in_(bindparam("cell_types", expanding=True)),
    ]
    if max_qvalue is not None:
        where_conditions.append((ChIPSeqPeak.qvalue.is_(None)) | (ChIPSeqPeak.qvalue <= bindparam("max_qvalue")))

    peak_width_expr = (ChIPSeqPeak.peak_end - ChIPSeqPeak.peak_start).label("peak_width")
    stmt = (
        select(
            ChIPSeqExperiment.cell_type,
            ChIPSeqExperiment.cell_line,
            ChIPSeqPeak.peak_id,
            ChIPSeqPeak.chromosome,
            ChIPSeqPeak.peak_start,
            ChIPSeqPeak.peak_end,
            ChIPSeqPeak.summit_position,
            ChIPSeqPeak.fold_enrichment,
            ChIPSeqPeak.qvalue,
            ChIPSeqPeak.signal_value,
            peak_width_expr,
            EpigeneticMarkType.mark_name,
        )
        .select_from(ChIPSeqPeak)
        .join(ChIPSeqExperiment, ChIPSeqPeak.experiment_id == ChIPSeqExperiment.experiment_id)
        .join(EpigeneticMarkType, ChIPSeqExperiment.mark_type_id == EpigeneticMarkType.mark_type_id)
        .where(*where_conditions)
        .order_by(ChIPSeqExperiment.cell_type, ChIPSeqPeak.peak_start)
    )

    rows = db.execute(
        stmt,
        {
            "species_id": gene.species_id,
            "chromosome": gene.chromosome,
            "region_start": region_start,
            "region_end": region_end,
            "mark_type": mark_type,
            "cell_types": cell_type_list,
            "max_qvalue": max_qvalue,
        },
    ).fetchall()

    # 4. Group peaks by cell type
    cell_lines_data: Dict[str, Dict[str, Any]] = {}
    for row in rows:
        cell_type = row[0]
        if cell_type not in cell_lines_data:
            cell_lines_data[cell_type] = {
                "cell_type": cell_type,
                "cell_line": row[1],
                "peaks": [],
            }

        cell_lines_data[cell_type]["peaks"].append({
            "peak_id": row[2],
            "chromosome": row[3],
            "peak_start": row[4],
            "peak_end": row[5],
            "summit_position": row[6],
            "fold_enrichment": float(row[7]) if row[7] else None,
            "qvalue": float(row[8]) if row[8] else None,
            "signal_value": float(row[9]) if row[9] else None,
            "peak_width": row[10],
            "mark_type": row[11],
        })

    # 5. Calculate statistics for each cell line and build response entries
    result_cell_lines = []
    for cell_type, data in cell_lines_data.items():
        peaks = data["peaks"]

        # Compute statistics using the existing helper
        stats = compute_mark_statistics(peaks, region_start, region_end)

        # Calculate average signal
        signal_values = [p["signal_value"] for p in peaks if p["signal_value"] is not None]
        avg_signal = statistics.mean(signal_values) if signal_values else None

        # Convert peaks to compact format for response
        compact_peaks = [
            ChIPSeqPeakCompact(
                peak_id=p["peak_id"],
                chromosome=p["chromosome"],
                peak_start=p["peak_start"],
                peak_end=p["peak_end"],
                summit_position=p["summit_position"],
                fold_enrichment=p["fold_enrichment"],
                qvalue=p["qvalue"],
                mark_type=p["mark_type"],
            )
            for p in peaks
        ]

        result_cell_lines.append(CellLineComparisonEntry(
            cell_type=cell_type,
            cell_line=data["cell_line"],
            peaks=compact_peaks,
            total_peaks=len(peaks),
            avg_signal=avg_signal,
            median_fold_enrichment=stats["median_fold_enrichment"],
            std_fold_enrichment=stats["std_fold_enrichment"],
            total_coverage_bp=stats["total_coverage_bp"],
            peak_width_percentiles=stats["peak_width_percentiles"],
        ))

    # 6. Find overlaps between cell lines (if requested)
    overlap_regions: List[CellLineOverlapRegion] = []
    overlap_stats: List[CellLineOverlapStatistics] = []

    if include_overlaps and len(cell_lines_data) >= 2:
        cell_type_names = list(cell_lines_data.keys())

        for cell_1, cell_2 in combinations(cell_type_names, 2):
            overlaps = find_cell_line_overlaps(
                cell_lines_data[cell_1]["peaks"],
                cell_lines_data[cell_2]["peaks"],
                cell_1,
                cell_2,
                gene.chromosome,
            )

            overlap_regions.extend(overlaps)

            # Compute overlap statistics for this pair
            total_bp = sum(o.length for o in overlaps)
            jaccard = compute_jaccard_index(
                cell_lines_data[cell_1]["peaks"],
                cell_lines_data[cell_2]["peaks"],
            )

            overlap_stats.append(CellLineOverlapStatistics(
                cell_pair=f"{cell_1}:{cell_2}",
                overlap_count=len(overlaps),
                total_overlap_bp=total_bp,
                avg_overlap_length=total_bp / len(overlaps) if overlaps else None,
                jaccard_index=round(jaccard, 4) if jaccard is not None else None,
            ))

    # 7. Find common peaks (present in all cell lines)
    common_peaks_count = find_common_peaks(cell_lines_data, gene.chromosome)

    # 8. Identify missing cell lines (requested but no data found)
    found_cell_types = set(cell_lines_data.keys())
    requested_cell_types = set(cell_type_list)
    missing_cell_lines = list(requested_cell_types - found_cell_types)

    return CellLineComparisonResponse(
        gene_id=gene.gene_id,
        gene_name=gene.gene_name or "Unknown",
        gene_ensembl_id=gene.gene_ensembl_id,
        chromosome=gene.chromosome,
        region_start=region_start,
        region_end=region_end,
        mark_type=mark_type,
        cell_lines=result_cell_lines,
        overlap_regions=overlap_regions if overlap_regions else None,
        overlap_statistics=overlap_stats if overlap_stats else None,
        total_cell_lines=len(result_cell_lines),
        common_peaks=common_peaks_count,
        missing_cell_lines=missing_cell_lines if missing_cell_lines else None,
    )


# =============================================================================
# Heatmap Matrix Endpoint (Multi-Cell-Line x Multi-Mark Analysis)
# =============================================================================

@router.get("/genes/{gene_id}/heatmap-matrix", response_model=HeatmapMatrixResponse)
@rate_limit("30/minute")  # Rate limit: 30 requests per minute per IP (expensive query)
@cached("chipseq:heatmap-matrix", ttl=cache.TTL_DETAIL)  # Cache: 10 minutes (TTL_DETAIL=600)
def get_gene_heatmap_matrix(
    request: Request,  # Required for rate limiting
    gene_id: int,
    marks: str = Query(
        ...,
        description="Comma-separated marks (e.g., H3K27me3,H3K4me3,H3K27ac)",
        examples={
            "default": {
                "summary": "常用组蛋白标记",
                "value": "H3K27me3,H3K4me3,H3K27ac,H3K4me1",
            }
        },
    ),
    cell_types: str = Query(
        ...,
        description="Comma-separated cell types (e.g., K562,HepG2)",
        examples={
            "default": {
                "summary": "常用细胞系",
                "value": "K562,HepG2,GM12878,H1-hESC",
            }
        },
    ),
    metric: str = Query(
        "median_fold_enrichment",
        description="Matrix metric to use",
        enum=["median_fold_enrichment", "peak_count", "total_coverage_bp", "avg_signal"]
    ),
    flanking: int = Query(DEFAULT_FLANKING_REGION, ge=0, le=100000),
    max_qvalue: Optional[float] = Query(0.05, ge=0, le=1),
    include_details: bool = Query(True, description="Include detailed statistics for tooltips"),
    db: Session = Depends(get_db),
):
    """
    Get heatmap matrix data for multiple cell lines x multiple marks.

    Returns a 2D matrix optimized for ECharts heatmap visualization.
    Matrix values can be fold enrichment, signal, peak count, or coverage.

    **Caching:** Results are cached for 10 minutes.
    **Rate Limit:** 30 requests per minute per IP.

    **Parameters:**
    - `marks`: Comma-separated list of marks (1-8 items)
    - `cell_types`: Comma-separated list of cell types (1-10 items)
    - `metric`: Value to use for matrix cells
        - `median_fold_enrichment`: Median fold enrichment (default)
        - `peak_count`: Number of peaks
        - `total_coverage_bp`: Total base pairs covered
        - `avg_signal`: Average signal value
    - `include_details`: Include detailed statistics per combination

    **Example:**
    ```
    GET /features/chipseq/genes/17276/heatmap-matrix
        ?marks=H3K27me3,H3K4me3,H3K27ac
        &cell_types=K562,HepG2,GM12878
        &metric=median_fold_enrichment
    ```

    **Response structure:**
    - `matrix[cell_index][mark_index]`: 2D array of metric values
    - `cell_types`: Y-axis labels (ordered)
    - `marks`: X-axis labels (ordered)
    - `details[cell_type][mark]`: Detailed statistics for tooltips
    """
    # 1. Parse and validate inputs
    mark_list = parse_comma_list(marks, max_items=8, param_name="marks") or []
    cell_type_list = parse_comma_list(cell_types, max_items=10, param_name="cell_types") or []

    if not mark_list:
        raise HTTPException(status_code=400, detail="marks must have 1-8 items")
    if not cell_type_list:
        raise HTTPException(status_code=400, detail="cell_types must have 1-10 items")

    # 2. Query gene
    gene = db.query(Gene).filter(Gene.gene_id == gene_id).first()
    if not gene:
        raise HTTPException(status_code=404, detail=f"Gene {gene_id} not found")

    # Check gene coordinates
    if gene.gene_start is None or gene.gene_end is None:
        raise HTTPException(
            status_code=400,
            detail=f"Gene {gene_id} has no coordinate information"
        )

    region_start = max(0, gene.gene_start - flanking)
    region_end = gene.gene_end + flanking

    # 3. Single SQL query for all combinations
    bp_region_start = bindparam("region_start")
    bp_region_end = bindparam("region_end")
    is_postgresql = db.get_bind().dialect.name == "postgresql"
    if is_postgresql:
        region_predicate = (
            func.int8range(ChIPSeqPeak.peak_start, ChIPSeqPeak.peak_end, "[)")
            .op("&&")(func.int8range(bp_region_start, bp_region_end, "[)"))
        )
    else:
        region_predicate = (ChIPSeqPeak.peak_start < bp_region_end) & (ChIPSeqPeak.peak_end > bp_region_start)

    where_conditions = [
        ChIPSeqPeak.species_id == bindparam("species_id"),
        ChIPSeqPeak.chromosome == bindparam("chromosome"),
        region_predicate,
        ChIPSeqExperiment.is_active.is_(True),
        EpigeneticMarkType.mark_name.in_(bindparam("marks", expanding=True)),
        ChIPSeqExperiment.cell_type.in_(bindparam("cell_types", expanding=True)),
    ]
    if max_qvalue is not None:
        where_conditions.append((ChIPSeqPeak.qvalue.is_(None)) | (ChIPSeqPeak.qvalue <= bindparam("max_qvalue")))

    stmt = (
        select(
            ChIPSeqExperiment.cell_type,
            EpigeneticMarkType.mark_name,
            ChIPSeqPeak.peak_id,
            ChIPSeqPeak.fold_enrichment,
            ChIPSeqPeak.signal_value,
            ChIPSeqPeak.qvalue,
            ChIPSeqPeak.peak_start,
            ChIPSeqPeak.peak_end,
        )
        .select_from(ChIPSeqPeak)
        .join(ChIPSeqExperiment, ChIPSeqPeak.experiment_id == ChIPSeqExperiment.experiment_id)
        .join(EpigeneticMarkType, ChIPSeqExperiment.mark_type_id == EpigeneticMarkType.mark_type_id)
        .where(*where_conditions)
        .order_by(ChIPSeqExperiment.cell_type, EpigeneticMarkType.mark_name)
    )

    rows = db.execute(
        stmt,
        {
            "species_id": gene.species_id,
            "chromosome": gene.chromosome,
            "region_start": region_start,
            "region_end": region_end,
            "marks": mark_list,
            "cell_types": cell_type_list,
            "max_qvalue": max_qvalue,
        },
    ).fetchall()

    # 4. Group by (cell_type, mark) and compute statistics
    # combo_stats[cell_type][mark] = {"peaks": [...], "coverage": int}
    combo_stats: Dict[str, Dict[str, Dict]] = {}

    for row in rows:
        cell_type, mark_name = row[0], row[1]
        if cell_type not in combo_stats:
            combo_stats[cell_type] = {}
        if mark_name not in combo_stats[cell_type]:
            combo_stats[cell_type][mark_name] = {"peaks": [], "coverage": 0}

        combo_stats[cell_type][mark_name]["peaks"].append({
            "fold_enrichment": float(row[3]) if row[3] else None,
            "signal_value": float(row[4]) if row[4] else None,
            "width": row[7] - row[6],
        })
        combo_stats[cell_type][mark_name]["coverage"] += (row[7] - row[6])

    # 5. Build matrix[cell_type_index][mark_index]
    matrix: List[List[Optional[float]]] = []
    details: Optional[Dict[str, Dict[str, CellMarkStats]]] = {} if include_details else None

    for cell_type in cell_type_list:
        row_values: List[Optional[float]] = []
        if include_details and cell_type not in details:
            details[cell_type] = {}

        for mark in mark_list:
            stats = combo_stats.get(cell_type, {}).get(mark, None)

            if stats:
                peaks = stats["peaks"]
                fold_enrichments = [p["fold_enrichment"] for p in peaks if p["fold_enrichment"] is not None]
                signals = [p["signal_value"] for p in peaks if p["signal_value"] is not None]

                # Calculate value based on metric
                value: Optional[float] = None
                if metric == "median_fold_enrichment" and fold_enrichments:
                    value = float(statistics.median(fold_enrichments))
                elif metric == "peak_count":
                    value = float(len(peaks))
                elif metric == "total_coverage_bp":
                    value = float(stats["coverage"])
                elif metric == "avg_signal" and signals:
                    value = float(statistics.mean(signals))

                row_values.append(value)

                if include_details:
                    details[cell_type][mark] = CellMarkStats(
                        median_fold_enrichment=float(statistics.median(fold_enrichments)) if fold_enrichments else None,
                        peak_count=len(peaks),
                        total_coverage_bp=stats["coverage"],
                        avg_signal=float(statistics.mean(signals)) if signals else None,
                        std_fold_enrichment=float(statistics.stdev(fold_enrichments)) if len(fold_enrichments) > 1 else None,
                    )
            else:
                row_values.append(None)

        matrix.append(row_values)

    # 6. Find missing combinations
    missing: List[Dict[str, str]] = []
    for cell_type in cell_type_list:
        for mark in mark_list:
            if combo_stats.get(cell_type, {}).get(mark) is None:
                missing.append({"cell_type": cell_type, "mark": mark})

    total_combos = len(cell_type_list) * len(mark_list)

    return HeatmapMatrixResponse(
        gene_id=gene.gene_id,
        gene_name=gene.gene_name or "Unknown",
        gene_ensembl_id=gene.gene_ensembl_id,
        chromosome=gene.chromosome,
        region_start=region_start,
        region_end=region_end,
        cell_types=cell_type_list,
        marks=mark_list,
        metric=metric,
        matrix=matrix,
        details=details,
        missing_combinations=missing if missing else None,
        total_combinations=total_combos,
        valid_combinations=total_combos - len(missing),
    )


def _build_batch_heatmap_gene_result(
    *,
    gene_id: int,
    gene_name: str,
    gene_ensembl_id: str,
    chromosome: str,
    region_start: int,
    region_end: int,
    mark_list: List[str],
    cell_type_list: List[str],
    metric: str,
    include_details: bool,
    stats_by_cell_mark: Dict[str, Dict[str, CellMarkStats]],
) -> HeatmapMatrixResponse:
    """
    构建单个 gene 的 HeatmapMatrixResponse（供 batch endpoint 复用）。

    Args:
        gene_id/gene_name/gene_ensembl_id/chromosome: 基因元数据
        region_start/region_end: 查询区域
        mark_list/cell_type_list: 请求的维度顺序
        metric/include_details: 矩阵值与 tooltip 细节开关
        stats_by_cell_mark: stats[cell_type][mark] = CellMarkStats（缺失表示无数据）
    """
    details: Optional[Dict[str, Dict[str, CellMarkStats]]] = {} if include_details else None
    matrix: List[List[Optional[float]]] = []

    for cell_type in cell_type_list:
        if include_details:
            details.setdefault(cell_type, {})

        row_values: List[Optional[float]] = []
        for mark in mark_list:
            cell_mark_stats = stats_by_cell_mark.get(cell_type, {}).get(mark)
            if cell_mark_stats is None:
                row_values.append(None)
                continue

            if metric == "median_fold_enrichment":
                value = cell_mark_stats.median_fold_enrichment
            elif metric == "peak_count":
                value = float(cell_mark_stats.peak_count)
            elif metric == "total_coverage_bp":
                value = float(cell_mark_stats.total_coverage_bp)
            elif metric == "avg_signal":
                value = cell_mark_stats.avg_signal
            else:
                value = None

            row_values.append(value)

            if include_details:
                details[cell_type][mark] = cell_mark_stats

        matrix.append(row_values)

    missing: List[Dict[str, str]] = []
    for cell_type in cell_type_list:
        for mark in mark_list:
            if stats_by_cell_mark.get(cell_type, {}).get(mark) is None:
                missing.append({"cell_type": cell_type, "mark": mark})

    total_combos = len(cell_type_list) * len(mark_list)
    return HeatmapMatrixResponse(
        gene_id=gene_id,
        gene_name=gene_name or "Unknown",
        gene_ensembl_id=gene_ensembl_id,
        chromosome=chromosome,
        region_start=region_start,
        region_end=region_end,
        cell_types=cell_type_list,
        marks=mark_list,
        metric=metric,
        matrix=matrix,
        details=details,
        missing_combinations=missing if missing else None,
        total_combinations=total_combos,
        valid_combinations=total_combos - len(missing),
    )


@router.post("/genes/batch-heatmap-matrix", response_model=BatchHeatmapMatrixResponse)
@rate_limit("10/minute")  # Rate limit: 10 requests per minute per IP (batch is resource-intensive)
def get_batch_gene_heatmap_matrix(
    http_request: Request,  # Required for rate limiting (renamed to avoid conflict with body param)
    request: BatchHeatmapMatrixRequest,
    db: Session = Depends(get_db),
):
    """
    Get heatmap matrix data for multiple genes with the same marks and cell types.

    This endpoint efficiently retrieves ChIP-seq heatmap matrices for multiple genes,
    allowing comparison of epigenetic patterns across genes.

    **Rate Limit:** 10 requests per minute per IP (batch endpoints are resource-intensive).

    **Parameters:**
    - `gene_ids`: List of gene IDs (1-100 genes)
    - `marks`: List of histone modification marks (1-8 marks)
    - `cell_types`: List of cell types (1-10 cell types)
    - `metric`: Value to use for matrix cells
        - `median_fold_enrichment`: Median fold enrichment (default)
        - `peak_count`: Number of peaks
        - `total_coverage_bp`: Total base pairs covered
        - `avg_signal`: Average signal value
    - `flanking`: Flanking region in base pairs (0-100000)
    - `max_qvalue`: Maximum q-value for peak filtering (0-1)
    - `include_details`: Include detailed statistics per combination

    **Example:**
    ```
    POST /features/chipseq/genes/batch-heatmap-matrix
    {
        "gene_ids": [17276, 17277, 17278],
        "marks": ["H3K27me3", "H3K4me3", "H3K27ac"],
        "cell_types": ["K562", "HepG2", "GM12878"],
        "metric": "median_fold_enrichment",
        "flanking": 10000,
        "include_details": false
    }
    ```

    **Returns:**
    A BatchHeatmapMatrixResponse containing:
    - `genes`: List of HeatmapMatrixResponse for each requested gene
    - `total_genes`: Total number of requested genes
    - `successful_genes`: Number of genes with valid data
    - `failed_genes`: List of gene IDs not found or with errors
    - `query_time_ms`: Query execution time in milliseconds
    """
    start_time = time.time()

    # 1. Validate inputs
    if not request.gene_ids:
        raise HTTPException(status_code=400, detail="gene_ids cannot be empty")
    if not request.marks:
        raise HTTPException(status_code=400, detail="marks cannot be empty")
    if not request.cell_types:
        raise HTTPException(status_code=400, detail="cell_types cannot be empty")

    logger.info(f"Batch heatmap query: {len(request.gene_ids)} genes, {len(request.marks)} marks, {len(request.cell_types)} cell types")

    # 2. Fetch all genes
    genes = db.query(Gene).filter(Gene.gene_id.in_(request.gene_ids)).all()
    gene_dict = {g.gene_id: g for g in genes}

    # 3. Prepare regions in request order (and capture invalid/missing genes)
    mark_list = list(request.marks)
    cell_type_list = list(request.cell_types)

    gene_regions_rows: List[tuple] = []
    gene_region_bounds: Dict[int, tuple[int, int]] = {}
    valid_gene_ids: List[int] = []
    failed_gene_ids: List[int] = []

    params: Dict[str, Any] = {
        "marks": mark_list,
        "cell_types": cell_type_list,
        "max_qvalue": request.max_qvalue,
    }

    for gene_id in request.gene_ids:
        gene = gene_dict.get(gene_id)
        if not gene:
            logger.warning(f"Gene {gene_id} not found")
            failed_gene_ids.append(gene_id)
            continue

        if gene.gene_start is None or gene.gene_end is None or not gene.chromosome:
            logger.warning(f"Gene {gene_id} missing coordinate/chromosome information")
            failed_gene_ids.append(gene_id)
            continue

        region_start = max(0, gene.gene_start - request.flanking)
        region_end = gene.gene_end + request.flanking

        gene_region_bounds[gene_id] = (region_start, region_end)
        valid_gene_ids.append(gene_id)

        gene_regions_rows.append((gene.gene_id, gene.species_id, gene.chromosome, region_start, region_end))

    if not valid_gene_ids:
        query_time_ms = int((time.time() - start_time) * 1000)
        return BatchHeatmapMatrixResponse(
            genes=[],
            total_genes=len(request.gene_ids),
            successful_genes=0,
            failed_genes=failed_gene_ids,
            query_time_ms=query_time_ms,
        )

    # 4. Single aggregated query for all genes (avoid N+1 queries)
    gene_regions = (
        values(
            column("gene_id"),
            column("species_id"),
            column("chromosome"),
            column("region_start"),
            column("region_end"),
            name="gene_regions",
        )
        .data(gene_regions_rows)
        .alias("gene_regions")
    )

    peak_join = (
        (ChIPSeqPeak.species_id == gene_regions.c.species_id)
        & (ChIPSeqPeak.chromosome == gene_regions.c.chromosome)
        & (ChIPSeqPeak.peak_start < gene_regions.c.region_end)
        & (ChIPSeqPeak.peak_end > gene_regions.c.region_start)
    )

    total_coverage_bp_expr = func.coalesce(
        func.sum(
            case(
                (
                    (ChIPSeqPeak.peak_start.is_not(None)) & (ChIPSeqPeak.peak_end.is_not(None)),
                    ChIPSeqPeak.peak_end - ChIPSeqPeak.peak_start,
                ),
                else_=0,
            )
        ),
        0,
    ).label("total_coverage_bp")

    median_fold_enrichment_expr = funcfilter(
        func.percentile_cont(0.5).within_group(ChIPSeqPeak.fold_enrichment),
        ChIPSeqPeak.fold_enrichment.is_not(None),
    ).label("median_fold_enrichment")

    std_fold_enrichment_expr = func.stddev_samp(ChIPSeqPeak.fold_enrichment).filter(
        ChIPSeqPeak.fold_enrichment.is_not(None)
    ).label("std_fold_enrichment")

    where_conditions = [
        ChIPSeqExperiment.is_active.is_(True),
        EpigeneticMarkType.mark_name.in_(bindparam("marks", expanding=True)),
        ChIPSeqExperiment.cell_type.in_(bindparam("cell_types", expanding=True)),
    ]
    if request.max_qvalue is not None:
        where_conditions.append((ChIPSeqPeak.qvalue.is_(None)) | (ChIPSeqPeak.qvalue <= bindparam("max_qvalue")))

    stmt = (
        select(
            gene_regions.c.gene_id,
            ChIPSeqExperiment.cell_type,
            EpigeneticMarkType.mark_name.label("mark_name"),
            func.count().label("peak_count"),
            total_coverage_bp_expr,
            func.avg(ChIPSeqPeak.signal_value).label("avg_signal"),
            median_fold_enrichment_expr,
            std_fold_enrichment_expr,
        )
        .select_from(gene_regions)
        .join(ChIPSeqPeak, peak_join)
        .join(ChIPSeqExperiment, ChIPSeqPeak.experiment_id == ChIPSeqExperiment.experiment_id)
        .join(EpigeneticMarkType, ChIPSeqExperiment.mark_type_id == EpigeneticMarkType.mark_type_id)
        .where(*where_conditions)
        .group_by(gene_regions.c.gene_id, ChIPSeqExperiment.cell_type, EpigeneticMarkType.mark_name)
        .order_by(gene_regions.c.gene_id, ChIPSeqExperiment.cell_type, EpigeneticMarkType.mark_name)
    )

    try:
        rows = db.execute(stmt, params).fetchall()
    except Exception as e:
        raise sanitize_db_error(e, logger)

    # 5. Index results: stats[gene_id][cell_type][mark] = CellMarkStats
    stats_by_gene: Dict[int, Dict[str, Dict[str, CellMarkStats]]] = {}
    for row in rows:
        gene_id = int(row.gene_id)
        cell_type = str(row.cell_type)
        mark_name = str(row.mark_name)

        stats_by_gene.setdefault(gene_id, {}).setdefault(cell_type, {})[mark_name] = CellMarkStats(
            median_fold_enrichment=float(row.median_fold_enrichment) if row.median_fold_enrichment is not None else None,
            peak_count=int(row.peak_count) if row.peak_count is not None else 0,
            total_coverage_bp=int(row.total_coverage_bp) if row.total_coverage_bp is not None else 0,
            avg_signal=float(row.avg_signal) if row.avg_signal is not None else None,
            std_fold_enrichment=float(row.std_fold_enrichment) if row.std_fold_enrichment is not None else None,
        )

    # 6. Build per-gene responses (preserve request ordering)
    successful_results: List[HeatmapMatrixResponse] = []
    for gene_id in valid_gene_ids:
        try:
            gene = gene_dict[gene_id]
            region_start, region_end = gene_region_bounds[gene_id]
            successful_results.append(
                _build_batch_heatmap_gene_result(
                    gene_id=gene.gene_id,
                    gene_name=gene.gene_name or "Unknown",
                    gene_ensembl_id=gene.gene_ensembl_id,
                    chromosome=gene.chromosome,
                    region_start=region_start,
                    region_end=region_end,
                    mark_list=mark_list,
                    cell_type_list=cell_type_list,
                    metric=request.metric,
                    include_details=request.include_details,
                    stats_by_cell_mark=stats_by_gene.get(gene_id, {}),
                )
            )
        except Exception as e:
            logger.error(
                "Error building batch heatmap result for gene %s: %s",
                gene_id,
                sanitize_for_log(e, max_length=2000),
                exc_info=True,
            )
            failed_gene_ids.append(gene_id)

    # 9. Calculate query time
    query_time_ms = int((time.time() - start_time) * 1000)

    logger.info(f"Batch query completed: {len(successful_results)} successful, {len(failed_gene_ids)} failed in {query_time_ms}ms")

    return BatchHeatmapMatrixResponse(
        genes=successful_results,
        total_genes=len(request.gene_ids),
        successful_genes=len(successful_results),
        failed_genes=failed_gene_ids,
        query_time_ms=query_time_ms,
    )
