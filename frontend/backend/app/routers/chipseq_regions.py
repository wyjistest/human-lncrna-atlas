"""
ChIP-seq Regions API Router
区域基因组查询端点
"""
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session
from sqlalchemy import text

from app.core.database import get_db
from app.models import Species
from app.utils.chipseq_db import parse_mark_types
from app.schemas.chipseq import (
    ChIPSeqPaginatedResponse,
    ChIPSeqPeak,
)

router = APIRouter()


@router.get("/regions/{species_id}", response_model=ChIPSeqPaginatedResponse)
def get_peaks_by_region(
    species_id: int,
    chromosome: str = Query(..., description="Chromosome name"),
    start: int = Query(..., ge=0, description="Region start position"),
    end: int = Query(..., ge=0, description="Region end position"),
    mark_type: Optional[str] = Query(None, description="Filter by mark type(s)"),
    min_fold_enrichment: Optional[float] = Query(None, ge=0),
    max_qvalue: Optional[float] = Query(0.05, ge=0, le=1),
    page: int = Query(1, ge=1),
    page_size: int = Query(100, ge=1, le=1000),
    db: Session = Depends(get_db),
):
    """
    Get ChIP-seq peaks for a specific genomic region

    Useful for browser-like views and custom region queries.
    """
    # Validate species
    species = db.query(Species).filter(Species.species_id == species_id).first()
    if not species:
        raise HTTPException(status_code=404, detail="Species not found")

    if end <= start:
        raise HTTPException(status_code=400, detail="end must be greater than start")

    mark_types = parse_mark_types(mark_type)

    # Count query
    count_query = text("""
        SELECT COUNT(*)
        FROM chipseq_peaks p
        JOIN chipseq_experiments e ON p.experiment_id = e.experiment_id
        JOIN epigenetic_mark_types m ON e.mark_type_id = m.mark_type_id
        WHERE p.species_id = :species_id
          AND p.chromosome = :chromosome
          AND p.peak_start < :end
          AND p.peak_end > :start
          AND e.is_active = TRUE
          AND (:mark_types IS NULL OR m.mark_name = ANY(:mark_types))
          AND (:min_fold_enrichment IS NULL OR p.fold_enrichment >= :min_fold_enrichment)
          AND (:max_qvalue IS NULL OR p.qvalue IS NULL OR p.qvalue <= :max_qvalue)
    """)

    total = db.execute(count_query, {
        "species_id": species_id,
        "chromosome": chromosome,
        "start": start,
        "end": end,
        "mark_types": mark_types,
        "min_fold_enrichment": min_fold_enrichment,
        "max_qvalue": max_qvalue,
    }).scalar() or 0

    # Data query
    offset = (page - 1) * page_size
    data_query = text("""
        SELECT
            p.peak_id,
            p.experiment_id,
            m.mark_name,
            m.mark_category,
            p.chromosome,
            p.peak_start,
            p.peak_end,
            p.summit_position,
            p.peak_name,
            p.strand,
            p.fold_enrichment,
            p.log2_fold_enrichment,
            p.pvalue,
            p.neg_log10_pvalue,
            p.qvalue,
            p.neg_log10_qvalue,
            p.signal_value,
            p.score,
            p.peak_width
        FROM chipseq_peaks p
        JOIN chipseq_experiments e ON p.experiment_id = e.experiment_id
        JOIN epigenetic_mark_types m ON e.mark_type_id = m.mark_type_id
        WHERE p.species_id = :species_id
          AND p.chromosome = :chromosome
          AND p.peak_start < :end
          AND p.peak_end > :start
          AND e.is_active = TRUE
          AND (:mark_types IS NULL OR m.mark_name = ANY(:mark_types))
          AND (:min_fold_enrichment IS NULL OR p.fold_enrichment >= :min_fold_enrichment)
          AND (:max_qvalue IS NULL OR p.qvalue IS NULL OR p.qvalue <= :max_qvalue)
        ORDER BY p.peak_start
        LIMIT :limit OFFSET :offset
    """)

    rows = db.execute(data_query, {
        "species_id": species_id,
        "chromosome": chromosome,
        "start": start,
        "end": end,
        "mark_types": mark_types,
        "min_fold_enrichment": min_fold_enrichment,
        "max_qvalue": max_qvalue,
        "limit": page_size,
        "offset": offset,
    }).fetchall()

    items = [
        ChIPSeqPeak(
            peak_id=row[0],
            experiment_id=row[1],
            mark_type=row[2],
            mark_category=row[3],
            chromosome=row[4],
            peak_start=row[5],
            peak_end=row[6],
            summit_position=row[7],
            peak_name=row[8],
            strand=row[9] or ".",
            fold_enrichment=float(row[10]) if row[10] else None,
            log2_fold_enrichment=float(row[11]) if row[11] else None,
            pvalue=float(row[12]) if row[12] else None,
            neg_log10_pvalue=float(row[13]) if row[13] else None,
            qvalue=float(row[14]) if row[14] else None,
            neg_log10_qvalue=float(row[15]) if row[15] else None,
            signal_value=float(row[16]) if row[16] else None,
            score=row[17],
            peak_width=row[18] or (row[6] - row[5]),
        )
        for row in rows
    ]

    return ChIPSeqPaginatedResponse(
        total=total,
        items=items,
        page=page,
        page_size=page_size,
    )
