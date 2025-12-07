"""
lncRNA-ChIP-seq Overlap Analysis API

REST endpoints for querying overlaps between lncRNA binding sites and ChIP-seq peaks
"""
from fastapi import APIRouter, Depends, Query, HTTPException
from sqlalchemy import text
from sqlalchemy.orm import Session
from typing import Optional, List, Tuple
import logging

from app.core.database import get_db
from app.schemas.lncrna_chipseq_overlap import (
    OverlapFilters,
    OverlapResponse,
    OverlapResult,
    OverlapStatistics
)

logger = logging.getLogger(__name__)

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
def get_overlap_statistics(
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

    Returns aggregate statistics including total overlaps, unique genes, and average metrics.
    """

    # Parse comma-separated filters
    mark_types_array = parse_comma_separated(mark_type)
    cell_types_array = parse_comma_separated(cell_type)

    # Statistics query
    stats_sql = text("""
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
        WHERE
            r.species_id = 1
            AND e.is_active = TRUE
            AND (:lncrna_gene_id IS NULL OR r.lncrna_gene_id = :lncrna_gene_id)
            AND (:target_gene_id IS NULL OR r.target_gene_id = :target_gene_id)
            AND (:chromosome IS NULL OR r.best_peak_chr = :chromosome)
            AND (:mark_types IS NULL OR m.mark_name = ANY(:mark_types))
            AND (:cell_types IS NULL OR e.cell_type = ANY(:cell_types))
            AND (:min_binding_affinity IS NULL OR r.binding_affinity >= :min_binding_affinity)
            AND (:max_qvalue IS NULL OR p.qvalue IS NULL OR p.qvalue <= :max_qvalue)
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
        result = db.execute(stats_sql, params).fetchone()

        if not result or result.total_overlaps == 0:
            return OverlapStatistics(
                total_overlaps=0,
                unique_lncrnas=0,
                unique_targets=0,
                unique_marks=0,
                avg_overlap_length=0.0,
                avg_binding_affinity=0.0,
                avg_peak_strength=0.0
            )

        return OverlapStatistics(
            total_overlaps=result.total_overlaps,
            unique_lncrnas=result.unique_lncrnas,
            unique_targets=result.unique_targets,
            unique_marks=result.unique_marks,
            avg_overlap_length=float(result.avg_overlap_length) if result.avg_overlap_length else 0.0,
            avg_binding_affinity=float(result.avg_binding_affinity) if result.avg_binding_affinity else 0.0,
            avg_peak_strength=float(result.avg_peak_strength) if result.avg_peak_strength else 0.0
        )

    except Exception as e:
        logger.error(f"Error calculating overlap statistics: {e}")
        raise HTTPException(status_code=500, detail=f"Database query error: {str(e)}")
