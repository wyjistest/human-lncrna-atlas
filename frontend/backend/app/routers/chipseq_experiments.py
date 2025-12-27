"""
ChIP-seq Experiments API Router
管理ChIP-seq实验数据的端点
"""
import logging
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Path, Query, Request
from sqlalchemy.orm import Session
from sqlalchemy import bindparam, func, literal, select

from app.core.database import get_db
from app.core.exceptions import sanitize_db_error
from app.core.utils import escape_like_pattern
from app.core.validators import compute_pagination_offset, normalize_optional_str
from app.routers.chipseq_rate_limit import rate_limit
from app.utils.chipseq_db import parse_mark_types
from app.models import ChIPSeqExperiment, ChIPSeqPeak, EpigeneticMarkType, Species
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
    mark_category: Optional[str] = Query(None, max_length=100, description="Filter by mark category"),
    cell_type: Optional[str] = Query(None, max_length=100, description="Filter by cell type"),
    source_database: Optional[str] = Query(None, max_length=32, description="Filter by source (ENCODE, GEO)"),
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
    normalized_mark_category = normalize_optional_str(mark_category)
    normalized_cell_type = normalize_optional_str(cell_type)
    normalized_source_database = normalize_optional_str(source_database)

    params = {}

    # NOTE: 避免使用反斜杠作为 ESCAPE 字符，减少 PostgreSQL/驱动/编译器在字符串转义上的歧义。
    # '^' 是单字符且不常见，适合作为 LIKE/ILIKE 的 escape 字符。
    like_escape_char = "^"

    where_conditions = []
    if species_id is not None:
        where_conditions.append(ChIPSeqExperiment.species_id == bindparam("species_id"))
        params["species_id"] = species_id

    if mark_types is not None:
        where_conditions.append(EpigeneticMarkType.mark_name.in_(bindparam("mark_types", expanding=True)))
        params["mark_types"] = mark_types

    if normalized_mark_category is not None:
        where_conditions.append(EpigeneticMarkType.mark_category == bindparam("mark_category"))
        params["mark_category"] = normalized_mark_category

    if normalized_cell_type is not None:
        # SECURITY/PERF: 统一 LIKE 转义，避免通配符绕过导致意外全表扫描
        # PostgreSQL: ESCAPE 子句必须是单字符；这里使用 '^' 作为转义字符
        where_conditions.append(
            ChIPSeqExperiment.cell_type.ilike(
                literal("%") + bindparam("cell_type") + literal("%"),
                escape=like_escape_char,
            )
        )
        params["cell_type"] = escape_like_pattern(normalized_cell_type, escape_char=like_escape_char)

    if normalized_source_database is not None:
        where_conditions.append(ChIPSeqExperiment.source_database == bindparam("source_database"))
        params["source_database"] = normalized_source_database

    if active_only:
        where_conditions.append(ChIPSeqExperiment.is_active.is_(True))

    # Avoid scanning the full chipseq_peaks table for all experiments:
    # only compute peak_count for experiments in the current page.
    filtered_experiments = (
        select(
            ChIPSeqExperiment.experiment_id,
            ChIPSeqExperiment.experiment_name,
            ChIPSeqExperiment.species_id,
            Species.species_code,
            EpigeneticMarkType.mark_name,
            EpigeneticMarkType.mark_category,
            EpigeneticMarkType.display_color,
            ChIPSeqExperiment.cell_type,
            ChIPSeqExperiment.tissue_type,
            ChIPSeqExperiment.cell_line,
            ChIPSeqExperiment.treatment,
            ChIPSeqExperiment.source_database,
            ChIPSeqExperiment.source_accession,
            ChIPSeqExperiment.peak_caller,
            ChIPSeqExperiment.reference_genome,
            ChIPSeqExperiment.total_reads,
            ChIPSeqExperiment.mapped_reads,
            ChIPSeqExperiment.frip_score,
            ChIPSeqExperiment.is_active,
            ChIPSeqExperiment.created_at,
        )
        .select_from(ChIPSeqExperiment)
        .join(Species, ChIPSeqExperiment.species_id == Species.species_id)
        .join(EpigeneticMarkType, ChIPSeqExperiment.mark_type_id == EpigeneticMarkType.mark_type_id)
    )
    if where_conditions:
        filtered_experiments = filtered_experiments.where(*where_conditions)

    filtered_experiments_cte = filtered_experiments.cte("filtered_experiments")

    paged_experiments_cte = (
        select(
            filtered_experiments_cte,
            func.count().over().label("total_count"),
        )
        .select_from(filtered_experiments_cte)
        .order_by(filtered_experiments_cte.c.created_at.desc())
        .limit(bindparam("limit"))
        .offset(bindparam("offset"))
        .cte("paged_experiments")
    )

    peak_counts_cte = (
        select(
            ChIPSeqPeak.experiment_id,
            func.count().label("peak_count"),
        )
        .select_from(ChIPSeqPeak)
        .where(
            ChIPSeqPeak.experiment_id.in_(
                select(paged_experiments_cte.c.experiment_id)
            )
        )
        .group_by(ChIPSeqPeak.experiment_id)
        .cte("peak_counts")
    )

    query = (
        select(
            paged_experiments_cte.c.experiment_id,
            paged_experiments_cte.c.experiment_name,
            paged_experiments_cte.c.species_id,
            paged_experiments_cte.c.species_code,
            paged_experiments_cte.c.mark_name,
            paged_experiments_cte.c.mark_category,
            paged_experiments_cte.c.display_color,
            paged_experiments_cte.c.cell_type,
            paged_experiments_cte.c.tissue_type,
            paged_experiments_cte.c.cell_line,
            paged_experiments_cte.c.treatment,
            paged_experiments_cte.c.source_database,
            paged_experiments_cte.c.source_accession,
            paged_experiments_cte.c.peak_caller,
            paged_experiments_cte.c.reference_genome,
            paged_experiments_cte.c.total_reads,
            paged_experiments_cte.c.mapped_reads,
            paged_experiments_cte.c.frip_score,
            paged_experiments_cte.c.is_active,
            paged_experiments_cte.c.created_at,
            func.coalesce(peak_counts_cte.c.peak_count, 0).label("peak_count"),
            paged_experiments_cte.c.total_count,
        )
        .select_from(paged_experiments_cte)
        .outerjoin(peak_counts_cte, paged_experiments_cte.c.experiment_id == peak_counts_cte.c.experiment_id)
        .order_by(paged_experiments_cte.c.created_at.desc())
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
    bp_experiment_id = bindparam("experiment_id")
    experiment_counts_cte = (
        select(
            ChIPSeqPeak.experiment_id,
            func.count().label("peak_count"),
        )
        .select_from(ChIPSeqPeak)
        .where(ChIPSeqPeak.experiment_id == bp_experiment_id)
        .group_by(ChIPSeqPeak.experiment_id)
        .cte("experiment_counts")
    )

    query = (
        select(
            ChIPSeqExperiment.experiment_id,
            ChIPSeqExperiment.experiment_name,
            ChIPSeqExperiment.species_id,
            Species.species_code,
            EpigeneticMarkType.mark_name,
            EpigeneticMarkType.mark_category,
            EpigeneticMarkType.display_color,
            ChIPSeqExperiment.cell_type,
            ChIPSeqExperiment.tissue_type,
            ChIPSeqExperiment.cell_line,
            ChIPSeqExperiment.treatment,
            ChIPSeqExperiment.source_database,
            ChIPSeqExperiment.source_accession,
            ChIPSeqExperiment.peak_caller,
            ChIPSeqExperiment.reference_genome,
            ChIPSeqExperiment.total_reads,
            ChIPSeqExperiment.mapped_reads,
            ChIPSeqExperiment.frip_score,
            ChIPSeqExperiment.is_active,
            ChIPSeqExperiment.created_at,
            func.coalesce(experiment_counts_cte.c.peak_count, 0).label("peak_count"),
        )
        .select_from(ChIPSeqExperiment)
        .join(Species, ChIPSeqExperiment.species_id == Species.species_id)
        .join(EpigeneticMarkType, ChIPSeqExperiment.mark_type_id == EpigeneticMarkType.mark_type_id)
        .outerjoin(experiment_counts_cte, ChIPSeqExperiment.experiment_id == experiment_counts_cte.c.experiment_id)
        .where(ChIPSeqExperiment.experiment_id == bp_experiment_id)
    )

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
