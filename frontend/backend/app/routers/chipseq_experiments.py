"""
ChIP-seq Experiments API Router
管理ChIP-seq实验数据的端点
"""
import logging
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Path, Query, Request
from sqlalchemy.orm import Session
from sqlalchemy import text

from app.core.database import get_db
from app.core.exceptions import sanitize_db_error
from app.core.validators import compute_pagination_offset
from app.routers.chipseq_rate_limit import rate_limit
from app.utils.chipseq_db import parse_mark_types
from app.schemas.chipseq import (
    ChIPSeqExperimentListResponse,
    ChIPSeqExperimentResponse,
)

logger = logging.getLogger(__name__)

router = APIRouter()


@router.get("/experiments", response_model=ChIPSeqExperimentListResponse)
@rate_limit("30/minute")
def list_experiments(
    request: Request,
    species_id: Optional[int] = Query(None, ge=1, le=4, description="Filter by species"),
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

    where_clauses = []
    params = {}

    if species_id is not None:
        where_clauses.append("e.species_id = :species_id")
        params["species_id"] = species_id

    if mark_types is not None:
        where_clauses.append("m.mark_name = ANY(:mark_types)")
        params["mark_types"] = mark_types

    if mark_category is not None:
        where_clauses.append("m.mark_category = :mark_category")
        params["mark_category"] = mark_category

    if cell_type is not None:
        where_clauses.append("e.cell_type ILIKE '%' || :cell_type || '%'")
        params["cell_type"] = cell_type

    if source_database is not None:
        where_clauses.append("e.source_database = :source_database")
        params["source_database"] = source_database

    if active_only:
        where_clauses.append("e.is_active = TRUE")

    where_sql = " AND ".join(where_clauses) if where_clauses else "TRUE"

    # Avoid scanning the full chipseq_peaks table for all experiments:
    # only compute peak_count for experiments in the current page.
    query = text(
        f"""
        WITH filtered_experiments AS (
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
                e.created_at
            FROM chipseq_experiments e
            JOIN species s ON e.species_id = s.species_id
            JOIN epigenetic_mark_types m ON e.mark_type_id = m.mark_type_id
            WHERE {where_sql}
        ),
        paged_experiments AS (
            SELECT
                *,
                COUNT(*) OVER() as total_count
            FROM filtered_experiments
            ORDER BY created_at DESC
            LIMIT :limit OFFSET :offset
        ),
        peak_counts AS (
            SELECT
                p.experiment_id,
                COUNT(*) as peak_count
            FROM chipseq_peaks p
            WHERE p.experiment_id IN (SELECT experiment_id FROM paged_experiments)
            GROUP BY p.experiment_id
        )
        SELECT
            pe.experiment_id,
            pe.experiment_name,
            pe.species_id,
            pe.species_code,
            pe.mark_name,
            pe.mark_category,
            pe.display_color,
            pe.cell_type,
            pe.tissue_type,
            pe.cell_line,
            pe.treatment,
            pe.source_database,
            pe.source_accession,
            pe.peak_caller,
            pe.reference_genome,
            pe.total_reads,
            pe.mapped_reads,
            pe.frip_score,
            pe.is_active,
            pe.created_at,
            COALESCE(pc.peak_count, 0) as peak_count,
            pe.total_count
        FROM paged_experiments pe
        LEFT JOIN peak_counts pc ON pe.experiment_id = pc.experiment_id
        ORDER BY pe.created_at DESC
        """  # noqa: S608
    )

    offset = compute_pagination_offset(page, page_size)
    try:
        rows = db.execute(
            query,
            {
                **params,
                "limit": page_size,
                "offset": offset,
            },
        ).fetchall()
    except Exception as e:
        raise sanitize_db_error(e, logger)

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
@rate_limit("30/minute")
def get_experiment(
    request: Request,
    experiment_id: int = Path(..., ge=1, description="Experiment ID"),
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

    try:
        row = db.execute(query, {"experiment_id": experiment_id}).fetchone()
    except Exception as e:
        raise sanitize_db_error(e, logger)

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
