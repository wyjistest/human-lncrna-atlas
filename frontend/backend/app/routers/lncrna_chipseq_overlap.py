"""
lncRNA-ChIP-seq Overlap Analysis API

REST endpoints for querying overlaps between lncRNA binding sites and ChIP-seq peaks

Phase 3.0 Enhancements:
- Enhanced /statistics endpoint with by_mark_type and by_cell_type breakdowns
- New /heatmap endpoint for visualization matrices
- Redis caching for expensive aggregation queries
- Rate limiting for API protection
"""
from fastapi import APIRouter, Depends, Query, HTTPException, Request
from fastapi.responses import JSONResponse
from sqlalchemy import text
from sqlalchemy.orm import Session
from typing import Optional, List, Tuple, Literal
import logging

from app.core.database import get_db
from app.core.cache import cache, cached

# ============================================================================
# Rate Limiting Setup (slowapi)
# ============================================================================
try:
    from slowapi import Limiter
    from slowapi.util import get_remote_address
    from slowapi.errors import RateLimitExceeded
    SLOWAPI_AVAILABLE = True
except ImportError:
    SLOWAPI_AVAILABLE = False
    Limiter = None

# Initialize limiter if slowapi is available
if SLOWAPI_AVAILABLE:
    limiter = Limiter(key_func=get_remote_address)
else:
    limiter = None
from app.schemas.lncrna_chipseq_overlap import (
    OverlapFilters,
    OverlapResponse,
    OverlapResult,
    OverlapStatistics,
    MarkTypeStats,
    CellTypeStats,
    HeatmapCell,
    OverlapHeatmapResponse
)

logger = logging.getLogger(__name__)


# =============================================================================
# Rate Limiting Decorator Helper
# =============================================================================

def rate_limit(limit_string: str):
    """
    Rate limiting decorator that gracefully handles missing slowapi.

    Args:
        limit_string: Rate limit string (e.g., "30/minute", "5/minute")

    Usage:
        @rate_limit("30/minute")
        def my_endpoint(request: Request, ...):
            ...
    """
    def decorator(func):
        if SLOWAPI_AVAILABLE and limiter:
            # Apply slowapi rate limiting
            return limiter.limit(limit_string)(func)
        else:
            # No rate limiting - return function as-is
            return func
    return decorator


router = APIRouter(
    prefix="/lncrna-chipseq-overlap",
    tags=["lncrna-chipseq-overlap"]
)


def parse_comma_separated(value: Optional[str]) -> Optional[List[str]]:
    """Parse comma-separated string into list"""
    if not value:
        return None
    return [item.strip() for item in value.split(',') if item.strip()]


def get_lncrna_chipseq_overlaps_query(
    db: Session,
    filters: OverlapFilters
) -> Tuple[List[dict], int]:
    """
    Query lncRNA binding sites overlapping with ChIP-seq peaks

    Args:
        db: Database session
        filters: Query filters

    Returns:
        Tuple of (results list, total count)
    """

    # Parse comma-separated filters
    mark_types_array = parse_comma_separated(filters.mark_type)
    cell_types_array = parse_comma_separated(filters.cell_type)

    # Build sort clause
    sort_field_map = {
        "binding_affinity": "r.binding_affinity",
        "overlap_length": "overlap_length",
        "peak_fold_enrichment": "p.fold_enrichment"
    }
    sort_field = sort_field_map.get(filters.sort_by, "r.binding_affinity")
    sort_direction = "DESC" if filters.sort_order.lower() == "desc" else "ASC"

    # Count query
    count_sql = text("""
        SELECT COUNT(*) AS total
        FROM regulations r
        JOIN chipseq_peaks_human p ON
            r.species_id = p.species_id
            AND r.best_peak_chr = p.chromosome
            AND r.best_peak_start < p.peak_end
            AND r.best_peak_end > p.peak_start
        JOIN chipseq_experiments e ON p.experiment_id = e.experiment_id
        JOIN epigenetic_mark_types m ON e.mark_type_id = m.mark_type_id
        WHERE
            r.species_id = 1
            AND e.is_active = TRUE
            AND (:lncrna_gene_id IS NULL OR r.lncrna_gene_id = :lncrna_gene_id)
            AND (:target_gene_id IS NULL OR r.target_gene_id = :target_gene_id)
            AND (:chromosome IS NULL OR r.best_peak_chr = :chromosome)
            AND (:mark_types IS NULL OR m.mark_name = ANY(:mark_types))
            AND (:cell_types IS NULL OR e.cell_type = ANY(:cell_types))
            AND (:min_binding_affinity IS NULL OR r.binding_affinity >= :min_binding_affinity)
            AND (:min_peak_strength IS NULL OR p.fold_enrichment >= :min_peak_strength)
            AND (:max_qvalue IS NULL OR p.qvalue IS NULL OR p.qvalue <= :max_qvalue)
            AND (:min_overlap_length IS NULL OR
                 (LEAST(r.best_peak_end, p.peak_end) - GREATEST(r.best_peak_start, p.peak_start)) >= :min_overlap_length)
    """)

    # Main data query
    data_sql = text(f"""
        SELECT
            CONCAT('reg_', r.regulation_id, '_peak_', p.peak_id) AS overlap_id,
            r.regulation_id,
            r.lncrna_gene_id,
            lnc.gene_name AS lncrna_name,
            r.target_gene_id,
            tgt.gene_name AS target_gene_name,
            m.mark_name AS mark_type,
            m.mark_category,
            e.cell_type,
            r.best_peak_chr AS chromosome,
            r.best_peak_start AS lncrna_binding_start,
            r.best_peak_end AS lncrna_binding_end,
            p.peak_start,
            p.peak_end,
            GREATEST(r.best_peak_start, p.peak_start) AS overlap_start,
            LEAST(r.best_peak_end, p.peak_end) AS overlap_end,
            LEAST(r.best_peak_end, p.peak_end) - GREATEST(r.best_peak_start, p.peak_start) AS overlap_length,
            r.binding_affinity,
            p.fold_enrichment AS peak_fold_enrichment,
            p.qvalue AS peak_qvalue
        FROM regulations r
        JOIN genes lnc ON r.lncrna_gene_id = lnc.gene_id
        JOIN genes tgt ON r.target_gene_id = tgt.gene_id
        JOIN chipseq_peaks_human p ON
            r.species_id = p.species_id
            AND r.best_peak_chr = p.chromosome
            AND r.best_peak_start < p.peak_end
            AND r.best_peak_end > p.peak_start
        JOIN chipseq_experiments e ON p.experiment_id = e.experiment_id
        JOIN epigenetic_mark_types m ON e.mark_type_id = m.mark_type_id
        WHERE
            r.species_id = 1
            AND e.is_active = TRUE
            AND (:lncrna_gene_id IS NULL OR r.lncrna_gene_id = :lncrna_gene_id)
            AND (:target_gene_id IS NULL OR r.target_gene_id = :target_gene_id)
            AND (:chromosome IS NULL OR r.best_peak_chr = :chromosome)
            AND (:mark_types IS NULL OR m.mark_name = ANY(:mark_types))
            AND (:cell_types IS NULL OR e.cell_type = ANY(:cell_types))
            AND (:min_binding_affinity IS NULL OR r.binding_affinity >= :min_binding_affinity)
            AND (:min_peak_strength IS NULL OR p.fold_enrichment >= :min_peak_strength)
            AND (:max_qvalue IS NULL OR p.qvalue IS NULL OR p.qvalue <= :max_qvalue)
            AND (:min_overlap_length IS NULL OR
                 (LEAST(r.best_peak_end, p.peak_end) - GREATEST(r.best_peak_start, p.peak_start)) >= :min_overlap_length)
        ORDER BY {sort_field} {sort_direction}
        LIMIT :page_size OFFSET :offset
    """)

    # Calculate offset
    offset = (filters.page - 1) * filters.page_size

    # Query parameters
    params = {
        "lncrna_gene_id": filters.lncrna_gene_id,
        "target_gene_id": filters.target_gene_id,
        "chromosome": filters.chromosome,
        "mark_types": mark_types_array,
        "cell_types": cell_types_array,
        "min_binding_affinity": filters.min_binding_affinity,
        "min_peak_strength": filters.min_peak_strength,
        "max_qvalue": filters.max_qvalue,
        "min_overlap_length": filters.min_overlap_length,
        "page_size": filters.page_size,
        "offset": offset
    }

    try:
        # Get total count
        count_result = db.execute(count_sql, params).fetchone()
        total = count_result[0] if count_result else 0

        # Get data
        results = db.execute(data_sql, params).fetchall()

        # Convert to dictionary list
        items = []
        for row in results:
            items.append({
                "overlap_id": row.overlap_id,
                "regulation_id": row.regulation_id,
                "lncrna_gene_id": row.lncrna_gene_id,
                "lncrna_name": row.lncrna_name,
                "target_gene_id": row.target_gene_id,
                "target_gene_name": row.target_gene_name,
                "mark_type": row.mark_type,
                "mark_category": row.mark_category,
                "cell_type": row.cell_type,
                "chromosome": row.chromosome,
                "lncrna_binding_start": row.lncrna_binding_start,
                "lncrna_binding_end": row.lncrna_binding_end,
                "peak_start": row.peak_start,
                "peak_end": row.peak_end,
                "overlap_start": row.overlap_start,
                "overlap_end": row.overlap_end,
                "overlap_length": row.overlap_length,
                "binding_affinity": row.binding_affinity,
                "peak_fold_enrichment": row.peak_fold_enrichment,
                "peak_qvalue": row.peak_qvalue
            })

        return items, total

    except Exception as e:
        logger.error(f"Error querying lncRNA-ChIP-seq overlaps: {e}")
        raise HTTPException(status_code=500, detail=f"Database query error: {str(e)}")


@router.get("", response_model=OverlapResponse)
def get_lncrna_chipseq_overlaps(
    lncrna_gene_id: Optional[int] = Query(None, description="Filter by specific lncRNA gene ID"),
    target_gene_id: Optional[int] = Query(None, description="Filter by specific target gene ID"),
    mark_type: Optional[str] = Query(None, description="Filter by mark type(s), comma-separated (e.g., 'H3K27me3,H3K4me3')"),
    cell_type: Optional[str] = Query(None, description="Filter by cell type(s), comma-separated (e.g., 'K562,GM12878')"),
    chromosome: Optional[str] = Query(None, description="Filter by chromosome (e.g., 'chr1')"),
    min_overlap_length: Optional[int] = Query(None, ge=1, description="Minimum overlap length in bp"),
    min_binding_affinity: Optional[float] = Query(None, ge=0, description="Minimum binding affinity score"),
    min_peak_strength: Optional[float] = Query(None, ge=0, description="Minimum peak fold enrichment"),
    max_qvalue: Optional[float] = Query(0.05, ge=0, le=1, description="Maximum Q-value (FDR) for peaks"),
    page: int = Query(1, ge=1, description="Page number (starts from 1)"),
    page_size: int = Query(100, ge=1, le=1000, description="Items per page"),
    sort_by: Optional[str] = Query("binding_affinity", description="Sort field (binding_affinity, overlap_length, peak_fold_enrichment)"),
    sort_order: Optional[str] = Query("desc", description="Sort order (asc or desc)"),
    db: Session = Depends(get_db)
):
    """
    Get overlaps between lncRNA binding sites and ChIP-seq peaks (paginated)

    ## Overview
    This endpoint identifies genomic regions where lncRNA binding sites overlap with ChIP-seq peaks,
    enabling analysis of lncRNA-mediated epigenetic regulation mechanisms.

    ## Parameters
    - **lncrna_gene_id**: Optional, filter by specific lncRNA gene ID
    - **target_gene_id**: Optional, filter by specific target gene ID
    - **mark_type**: Optional, filter by histone mark type(s), comma-separated (e.g., "H3K27me3,H3K4me3")
    - **cell_type**: Optional, filter by cell type(s), comma-separated (e.g., "K562,GM12878")
    - **chromosome**: Optional, filter by chromosome (e.g., "chr1")
    - **min_overlap_length**: Optional, minimum overlap length in bp
    - **min_binding_affinity**: Optional, minimum lncRNA binding affinity score
    - **min_peak_strength**: Optional, minimum ChIP-seq peak fold enrichment
    - **max_qvalue**: Optional, maximum Q-value (FDR) for ChIP-seq peaks (default: 0.05)
    - **page**: Page number, starting from 1 (default: 1)
    - **page_size**: Items per page, max 1000 (default: 100)
    - **sort_by**: Sort field - "binding_affinity", "overlap_length", or "peak_fold_enrichment" (default: "binding_affinity")
    - **sort_order**: Sort direction - "asc" or "desc" (default: "desc")

    ## Response
    Returns paginated list of overlaps with genomic coordinates, signal metrics, and gene information.

    ## Example
    ```
    GET /api/v1/lncrna-chipseq-overlap?chromosome=chr1&mark_type=H3K27me3&min_binding_affinity=60&page=1&page_size=10
    ```
    """

    # Build filters object
    filters = OverlapFilters(
        lncrna_gene_id=lncrna_gene_id,
        target_gene_id=target_gene_id,
        mark_type=mark_type,
        cell_type=cell_type,
        chromosome=chromosome,
        min_overlap_length=min_overlap_length,
        min_binding_affinity=min_binding_affinity,
        min_peak_strength=min_peak_strength,
        max_qvalue=max_qvalue,
        page=page,
        page_size=page_size,
        sort_by=sort_by,
        sort_order=sort_order
    )

    # Execute query
    items, total = get_lncrna_chipseq_overlaps_query(db, filters)

    # Calculate total pages
    total_pages = OverlapResponse.calculate_total_pages(total, page_size)

    # Build response
    return OverlapResponse(
        total=total,
        page=page,
        page_size=page_size,
        total_pages=total_pages,
        items=[OverlapResult(**item) for item in items]
    )


@router.get("/statistics", response_model=OverlapStatistics)
@rate_limit("60/minute")  # Rate limit: 60 requests per minute per IP
@cached("overlap:statistics", ttl=cache.TTL_LIST)  # Cache: 5 minutes
def get_overlap_statistics(
    request: Request,  # Required for rate limiting
    lncrna_gene_id: Optional[int] = Query(None, description="Filter by specific lncRNA gene ID"),
    target_gene_id: Optional[int] = Query(None, description="Filter by specific target gene ID"),
    mark_type: Optional[str] = Query(None, description="Filter by mark type(s), comma-separated"),
    cell_type: Optional[str] = Query(None, description="Filter by cell type(s), comma-separated"),
    chromosome: Optional[str] = Query(None, description="Filter by chromosome"),
    min_binding_affinity: Optional[float] = Query(None, ge=0, description="Minimum binding affinity"),
    max_qvalue: Optional[float] = Query(0.05, ge=0, le=1, description="Maximum Q-value"),
    db: Session = Depends(get_db)
):
    """
    Get summary statistics for lncRNA-ChIP-seq overlaps

    Returns aggregate statistics including:
    - Total overlaps and unique counts
    - Average metrics (overlap length, binding affinity, peak strength)
    - **by_mark_type**: Breakdown of overlaps by epigenetic mark type
    - **by_cell_type**: Breakdown of overlaps by cell type

    **Caching:** Results are cached for 5 minutes.
    **Rate Limit:** 60 requests per minute per IP.
    """

    # Parse comma-separated filters
    mark_types_array = parse_comma_separated(mark_type)
    cell_types_array = parse_comma_separated(cell_type)

    # Base WHERE clause for all queries
    base_where = """
        r.species_id = 1
        AND e.is_active = TRUE
        AND (:lncrna_gene_id IS NULL OR r.lncrna_gene_id = :lncrna_gene_id)
        AND (:target_gene_id IS NULL OR r.target_gene_id = :target_gene_id)
        AND (:chromosome IS NULL OR r.best_peak_chr = :chromosome)
        AND (:mark_types IS NULL OR m.mark_name = ANY(:mark_types))
        AND (:cell_types IS NULL OR e.cell_type = ANY(:cell_types))
        AND (:min_binding_affinity IS NULL OR r.binding_affinity >= :min_binding_affinity)
        AND (:max_qvalue IS NULL OR p.qvalue IS NULL OR p.qvalue <= :max_qvalue)
    """

    # Main statistics query
    stats_sql = text(f"""
        SELECT
            COUNT(*) AS total_overlaps,
            COUNT(DISTINCT r.lncrna_gene_id) AS unique_lncrnas,
            COUNT(DISTINCT r.target_gene_id) AS unique_targets,
            COUNT(DISTINCT m.mark_name) AS unique_marks,
            AVG(LEAST(r.best_peak_end, p.peak_end) - GREATEST(r.best_peak_start, p.peak_start)) AS avg_overlap_length,
            AVG(r.binding_affinity) AS avg_binding_affinity,
            AVG(p.fold_enrichment) AS avg_peak_strength
        FROM regulations r
        JOIN chipseq_peaks_human p ON
            r.species_id = p.species_id
            AND r.best_peak_chr = p.chromosome
            AND r.best_peak_start < p.peak_end
            AND r.best_peak_end > p.peak_start
        JOIN chipseq_experiments e ON p.experiment_id = e.experiment_id
        JOIN epigenetic_mark_types m ON e.mark_type_id = m.mark_type_id
        WHERE {base_where}
    """)

    # By mark type breakdown query
    by_mark_sql = text(f"""
        SELECT
            m.mark_name AS mark_type,
            COUNT(*) AS count,
            AVG(r.binding_affinity) AS avg_strength
        FROM regulations r
        JOIN chipseq_peaks_human p ON
            r.species_id = p.species_id
            AND r.best_peak_chr = p.chromosome
            AND r.best_peak_start < p.peak_end
            AND r.best_peak_end > p.peak_start
        JOIN chipseq_experiments e ON p.experiment_id = e.experiment_id
        JOIN epigenetic_mark_types m ON e.mark_type_id = m.mark_type_id
        WHERE {base_where}
        GROUP BY m.mark_name
        ORDER BY count DESC
    """)

    # By cell type breakdown query
    by_cell_sql = text(f"""
        SELECT
            e.cell_type,
            COUNT(*) AS count
        FROM regulations r
        JOIN chipseq_peaks_human p ON
            r.species_id = p.species_id
            AND r.best_peak_chr = p.chromosome
            AND r.best_peak_start < p.peak_end
            AND r.best_peak_end > p.peak_start
        JOIN chipseq_experiments e ON p.experiment_id = e.experiment_id
        JOIN epigenetic_mark_types m ON e.mark_type_id = m.mark_type_id
        WHERE {base_where}
        GROUP BY e.cell_type
        ORDER BY count DESC
    """)

    params = {
        "lncrna_gene_id": lncrna_gene_id,
        "target_gene_id": target_gene_id,
        "chromosome": chromosome,
        "mark_types": mark_types_array,
        "cell_types": cell_types_array,
        "min_binding_affinity": min_binding_affinity,
        "max_qvalue": max_qvalue
    }

    try:
        # Execute main statistics query
        result = db.execute(stats_sql, params).fetchone()

        if not result or result.total_overlaps == 0:
            return OverlapStatistics(
                total_overlaps=0,
                unique_lncrnas=0,
                unique_targets=0,
                unique_marks=0,
                avg_overlap_length=0.0,
                avg_binding_affinity=0.0,
                avg_peak_strength=0.0,
                by_mark_type=[],
                by_cell_type=[]
            )

        # Execute by_mark_type query
        mark_results = db.execute(by_mark_sql, params).fetchall()
        by_mark_type = [
            MarkTypeStats(
                mark_type=row.mark_type,
                count=row.count,
                avg_strength=float(row.avg_strength) if row.avg_strength else 0.0
            )
            for row in mark_results
        ]

        # Execute by_cell_type query
        cell_results = db.execute(by_cell_sql, params).fetchall()
        by_cell_type = [
            CellTypeStats(
                cell_type=row.cell_type,
                count=row.count
            )
            for row in cell_results
        ]

        return OverlapStatistics(
            total_overlaps=result.total_overlaps,
            unique_lncrnas=result.unique_lncrnas,
            unique_targets=result.unique_targets,
            unique_marks=result.unique_marks,
            avg_overlap_length=float(result.avg_overlap_length) if result.avg_overlap_length else 0.0,
            avg_binding_affinity=float(result.avg_binding_affinity) if result.avg_binding_affinity else 0.0,
            avg_peak_strength=float(result.avg_peak_strength) if result.avg_peak_strength else 0.0,
            by_mark_type=by_mark_type,
            by_cell_type=by_cell_type
        )

    except Exception as e:
        logger.error(f"Error calculating overlap statistics: {e}")
        raise HTTPException(status_code=500, detail=f"Database query error: {str(e)}")


# =============================================================================
# Heatmap Endpoint (Phase 3.0)
# =============================================================================

@router.get("/heatmap", response_model=OverlapHeatmapResponse)
@rate_limit("30/minute")  # Rate limit: 30 requests per minute per IP (expensive query)
@cached("overlap:heatmap", ttl=cache.TTL_DETAIL)  # Cache: 10 minutes
def get_overlap_heatmap(
    request: Request,  # Required for rate limiting
    x_axis: Literal['mark_type', 'cell_type'] = Query(
        ...,
        description="X-axis dimension: 'mark_type' or 'cell_type'"
    ),
    y_axis: Literal['lncrna', 'target_gene'] = Query(
        ...,
        description="Y-axis dimension: 'lncrna' or 'target_gene'"
    ),
    metric: Literal['count', 'avg_binding_affinity', 'total_overlap_length'] = Query(
        'count',
        description="Value metric: 'count', 'avg_binding_affinity', or 'total_overlap_length'"
    ),
    top_n: int = Query(
        50,
        ge=1,
        le=100,
        description="Limit Y-axis items (max 100)"
    ),
    chromosome: Optional[str] = Query(None, description="Filter by chromosome (e.g., 'chr1')"),
    min_binding_affinity: Optional[float] = Query(None, ge=0, description="Minimum binding affinity score"),
    max_qvalue: Optional[float] = Query(0.05, ge=0, le=1, description="Maximum Q-value (FDR) for peaks"),
    db: Session = Depends(get_db)
):
    """
    Get heatmap matrix data for lncRNA-ChIP-seq overlap visualization.

    Returns a 2D matrix optimized for ECharts/D3 heatmap visualization.

    ## Parameters

    **Dimension Selection:**
    - **x_axis**: Choose X-axis dimension
      - `mark_type`: Group by epigenetic mark type (H3K27me3, H3K4me3, etc.)
      - `cell_type`: Group by cell type/line (K562, HepG2, etc.)
    - **y_axis**: Choose Y-axis dimension
      - `lncrna`: Group by lncRNA gene
      - `target_gene`: Group by target gene

    **Metric Selection:**
    - **metric**: Value to aggregate for each cell
      - `count`: Number of overlaps (default)
      - `avg_binding_affinity`: Average binding affinity score
      - `total_overlap_length`: Total overlap length in bp

    **Filtering:**
    - **top_n**: Limit Y-axis to top N items by total count (default: 50, max: 100)
    - **chromosome**: Filter by chromosome
    - **min_binding_affinity**: Minimum binding affinity threshold
    - **max_qvalue**: Maximum Q-value (FDR) threshold

    ## Response

    Returns:
    - **x_labels**: Sorted list of X-axis labels
    - **y_labels**: Top N Y-axis labels (sorted by total count)
    - **data**: Array of {x, y, value} objects for each cell with data
    - **metric**: The metric used
    - **total_combinations**: Total X * Y combinations
    - **valid_combinations**: Number of cells with actual data

    **Caching:** Results are cached for 10 minutes.
    **Rate Limit:** 30 requests per minute per IP.

    ## Example

    ```
    GET /api/v1/lncrna-chipseq-overlap/heatmap?x_axis=mark_type&y_axis=lncrna&metric=count&top_n=30
    ```
    """

    # Map x_axis to SQL column/expression
    x_axis_map = {
        'mark_type': ('m.mark_name', 'm.mark_name'),
        'cell_type': ('e.cell_type', 'e.cell_type')
    }

    # Map y_axis to SQL column/expression and gene join
    y_axis_map = {
        'lncrna': ('lnc.gene_name', 'r.lncrna_gene_id', 'JOIN genes lnc ON r.lncrna_gene_id = lnc.gene_id'),
        'target_gene': ('tgt.gene_name', 'r.target_gene_id', 'JOIN genes tgt ON r.target_gene_id = tgt.gene_id')
    }

    # Map metric to SQL aggregation
    metric_map = {
        'count': 'COUNT(*)',
        'avg_binding_affinity': 'AVG(r.binding_affinity)',
        'total_overlap_length': 'SUM(LEAST(r.best_peak_end, p.peak_end) - GREATEST(r.best_peak_start, p.peak_start))'
    }

    x_select, x_group = x_axis_map[x_axis]
    y_select, y_group_id, y_join = y_axis_map[y_axis]
    metric_agg = metric_map[metric]

    # Base filter conditions
    base_where = """
        r.species_id = 1
        AND e.is_active = TRUE
        AND (:chromosome IS NULL OR r.best_peak_chr = :chromosome)
        AND (:min_binding_affinity IS NULL OR r.binding_affinity >= :min_binding_affinity)
        AND (:max_qvalue IS NULL OR p.qvalue IS NULL OR p.qvalue <= :max_qvalue)
    """

    params = {
        "chromosome": chromosome,
        "min_binding_affinity": min_binding_affinity,
        "max_qvalue": max_qvalue,
        "top_n": top_n
    }

    try:
        # Step 1: Get all distinct X-axis values (ordered alphabetically)
        x_labels_sql = text(f"""
            SELECT DISTINCT {x_select} AS x_value
            FROM regulations r
            JOIN chipseq_peaks_human p ON
                r.species_id = p.species_id
                AND r.best_peak_chr = p.chromosome
                AND r.best_peak_start < p.peak_end
                AND r.best_peak_end > p.peak_start
            JOIN chipseq_experiments e ON p.experiment_id = e.experiment_id
            JOIN epigenetic_mark_types m ON e.mark_type_id = m.mark_type_id
            WHERE {base_where}
            ORDER BY x_value
        """)

        x_results = db.execute(x_labels_sql, params).fetchall()
        x_labels = [row.x_value for row in x_results if row.x_value]

        if not x_labels:
            return OverlapHeatmapResponse(
                x_labels=[],
                y_labels=[],
                data=[],
                metric=metric,
                total_combinations=0,
                valid_combinations=0
            )

        # Step 2: Get top N Y-axis values (by total count across all X values)
        y_labels_sql = text(f"""
            SELECT {y_select} AS y_value, COUNT(*) AS total_count
            FROM regulations r
            {y_join}
            JOIN chipseq_peaks_human p ON
                r.species_id = p.species_id
                AND r.best_peak_chr = p.chromosome
                AND r.best_peak_start < p.peak_end
                AND r.best_peak_end > p.peak_start
            JOIN chipseq_experiments e ON p.experiment_id = e.experiment_id
            JOIN epigenetic_mark_types m ON e.mark_type_id = m.mark_type_id
            WHERE {base_where}
                AND {y_select} IS NOT NULL
            GROUP BY {y_select}
            ORDER BY total_count DESC
            LIMIT :top_n
        """)

        y_results = db.execute(y_labels_sql, params).fetchall()
        y_labels = [row.y_value for row in y_results if row.y_value]

        if not y_labels:
            return OverlapHeatmapResponse(
                x_labels=x_labels,
                y_labels=[],
                data=[],
                metric=metric,
                total_combinations=0,
                valid_combinations=0
            )

        # Step 3: Get heatmap data for all X-Y combinations
        # Build the main aggregation query
        heatmap_sql = text(f"""
            SELECT
                {x_select} AS x_value,
                {y_select} AS y_value,
                {metric_agg} AS metric_value
            FROM regulations r
            {y_join}
            JOIN chipseq_peaks_human p ON
                r.species_id = p.species_id
                AND r.best_peak_chr = p.chromosome
                AND r.best_peak_start < p.peak_end
                AND r.best_peak_end > p.peak_start
            JOIN chipseq_experiments e ON p.experiment_id = e.experiment_id
            JOIN epigenetic_mark_types m ON e.mark_type_id = m.mark_type_id
            WHERE {base_where}
                AND {y_select} = ANY(:y_labels)
            GROUP BY {x_group}, {y_select}
            ORDER BY x_value, y_value
        """)

        params["y_labels"] = y_labels

        heatmap_results = db.execute(heatmap_sql, params).fetchall()

        # Build the data array
        data = []
        for row in heatmap_results:
            if row.x_value and row.y_value and row.metric_value is not None:
                data.append(HeatmapCell(
                    x=str(row.x_value),
                    y=str(row.y_value),
                    value=float(row.metric_value)
                ))

        # Calculate total and valid combinations
        total_combinations = len(x_labels) * len(y_labels)
        valid_combinations = len(data)

        return OverlapHeatmapResponse(
            x_labels=x_labels,
            y_labels=y_labels,
            data=data,
            metric=metric,
            total_combinations=total_combinations,
            valid_combinations=valid_combinations
        )

    except Exception as e:
        logger.error(f"Error generating heatmap data: {e}")
        raise HTTPException(status_code=500, detail=f"Database query error: {str(e)}")
