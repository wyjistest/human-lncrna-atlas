"""
ChIP-seq Experiments API Router
管理ChIP-seq实验数据的端点
"""
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session
from sqlalchemy import text

from app.core.database import get_db
from app.utils.chipseq_db import parse_mark_types
from app.schemas.chipseq import (
    ChIPSeqExperimentListResponse,
    ChIPSeqExperimentResponse,
)

router = APIRouter()


@router.get("/experiments", response_model=ChIPSeqExperimentListResponse)
def list_experiments(
    species_id: Optional[int] = Query(None, description="Filter by species"),
    mark_type: Optional[str] = Query(None, description="Filter by mark type(s), comma-separated"),
    mark_category: Optional[str] = Query(None, description="Filter by mark category"),
    cell_type: Optional[str] = Query(None, description="Filter by cell type"),
    source_database: Optional[str] = Query(None, description="Filter by source (ENCODE, GEO)"),
    active_only: bool = Query(True, description="Only return active experiments"),
    page: int = Query(1, ge=1, description="Page number"),
    page_size: int = Query(20, ge=1, le=100, description="Items per page"),
    db: Session = Depends(get_db),
):
    """
    List ChIP-seq experiments with filtering options

    Supports filtering by species, mark type, cell type, and data source.
    """
    mark_types = parse_mark_types(mark_type)

    # Build query
    query = text("""
        WITH experiment_counts AS (
            SELECT experiment_id, COUNT(*) as peak_count
            FROM chipseq_peaks
            GROUP BY experiment_id
        )
        SELECT
            e.experiment_id,
            e.experiment_name,
            e.species_id,
            s.species_code,
            m.mark_name,
            m.mark_category,
            m.display_color,
            e.cell_type,
            e.tissue_type,
            e.cell_line,
            e.treatment,
            e.source_database,
            e.source_accession,
            e.peak_caller,
            e.reference_genome,
            e.total_reads,
            e.mapped_reads,
            e.frip_score,
            e.is_active,
            e.created_at,
            COALESCE(ec.peak_count, 0) as peak_count,
            COUNT(*) OVER() as total_count
        FROM chipseq_experiments e
        JOIN species s ON e.species_id = s.species_id
        JOIN epigenetic_mark_types m ON e.mark_type_id = m.mark_type_id
        LEFT JOIN experiment_counts ec ON e.experiment_id = ec.experiment_id
        WHERE (:species_id IS NULL OR e.species_id = :species_id)
          AND (:mark_types IS NULL OR m.mark_name = ANY(:mark_types))
          AND (:mark_category IS NULL OR m.mark_category = :mark_category)
          AND (:cell_type IS NULL OR e.cell_type ILIKE '%' || :cell_type || '%')
          AND (:source_database IS NULL OR e.source_database = :source_database)
          AND (:active_only = FALSE OR e.is_active = TRUE)
        ORDER BY e.created_at DESC
        LIMIT :limit OFFSET :offset
    """)

    offset = (page - 1) * page_size
    rows = db.execute(query, {
        "species_id": species_id,
        "mark_types": mark_types,
        "mark_category": mark_category,
        "cell_type": cell_type,
        "source_database": source_database,
        "active_only": active_only,
        "limit": page_size,
        "offset": offset,
    }).fetchall()

    if not rows:
        return ChIPSeqExperimentListResponse(total=0, items=[], page=page, page_size=page_size)

    total = rows[0][21] if rows else 0

    items = [
        ChIPSeqExperimentResponse(
            experiment_id=row[0],
            experiment_name=row[1],
            species_id=row[2],
            species_code=row[3],
            mark_type=row[4],
            mark_category=row[5],
            mark_display_color=row[6],
            cell_type=row[7],
            tissue_type=row[8],
            cell_line=row[9],
            treatment=row[10],
            source_database=row[11],
            source_accession=row[12],
            peak_caller=row[13],
            reference_genome=row[14],
            total_reads=row[15],
            mapped_reads=row[16],
            frip_score=float(row[17]) if row[17] else None,
            is_active=row[18],
            created_at=row[19],
            peak_count=row[20],
        )
        for row in rows
    ]

    return ChIPSeqExperimentListResponse(
        total=total,
        items=items,
        page=page,
        page_size=page_size,
    )


@router.get("/experiments/{experiment_id}", response_model=ChIPSeqExperimentResponse)
def get_experiment(
    experiment_id: int,
    db: Session = Depends(get_db),
):
    """
    Get details for a specific ChIP-seq experiment
    """
    query = text("""
        WITH experiment_counts AS (
            SELECT experiment_id, COUNT(*) as peak_count
            FROM chipseq_peaks
            WHERE experiment_id = :experiment_id
            GROUP BY experiment_id
        )
        SELECT
            e.experiment_id,
            e.experiment_name,
            e.species_id,
            s.species_code,
            m.mark_name,
            m.mark_category,
            m.display_color,
            e.cell_type,
            e.tissue_type,
            e.cell_line,
            e.treatment,
            e.source_database,
            e.source_accession,
            e.peak_caller,
            e.reference_genome,
            e.total_reads,
            e.mapped_reads,
            e.frip_score,
            e.is_active,
            e.created_at,
            COALESCE(ec.peak_count, 0) as peak_count
        FROM chipseq_experiments e
        JOIN species s ON e.species_id = s.species_id
        JOIN epigenetic_mark_types m ON e.mark_type_id = m.mark_type_id
        LEFT JOIN experiment_counts ec ON e.experiment_id = ec.experiment_id
        WHERE e.experiment_id = :experiment_id
    """)

    row = db.execute(query, {"experiment_id": experiment_id}).fetchone()

    if not row:
        raise HTTPException(status_code=404, detail="Experiment not found")

    return ChIPSeqExperimentResponse(
        experiment_id=row[0],
        experiment_name=row[1],
        species_id=row[2],
        species_code=row[3],
        mark_type=row[4],
        mark_category=row[5],
        mark_display_color=row[6],
        cell_type=row[7],
        tissue_type=row[8],
        cell_line=row[9],
        treatment=row[10],
        source_database=row[11],
        source_accession=row[12],
        peak_caller=row[13],
        reference_genome=row[14],
        total_reads=row[15],
        mapped_reads=row[16],
        frip_score=float(row[17]) if row[17] else None,
        is_active=row[18],
        created_at=row[19],
        peak_count=row[20],
    )
