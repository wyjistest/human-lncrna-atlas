"""
ChIP-seq Regions API Router
区域基因组查询端点
"""
import logging
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Path, Query, Request
from sqlalchemy.orm import Session
from sqlalchemy import select, func

from app.core.database import get_db
from app.core.exceptions import sanitize_db_error
from app.core.validators import compute_pagination_offset
from app.routers.chipseq_rate_limit import rate_limit
from app.models import Species, ChIPSeqPeak as ChIPSeqPeakModel, ChIPSeqExperiment, EpigeneticMarkType
from app.utils.chipseq_db import parse_mark_types
from app.schemas.chipseq import (
    ChIPSeqPaginatedResponse,
    ChIPSeqPeak,
)

logger = logging.getLogger(__name__)

router = APIRouter()

# Maximum region size in base pairs (10 Mb)
# Prevents excessive queries that could time out or consume too many resources
MAX_REGION_SIZE_BP = 10_000_000


@router.get("/regions/{species_id}", response_model=ChIPSeqPaginatedResponse)
@rate_limit("30/minute")
def get_peaks_by_region(
    request: Request,
    species_id: int = Path(..., ge=1, le=4, description="Species ID"),
    chromosome: str = Query(..., description="Chromosome name"),
    start: int = Query(..., ge=0, description="Region start position"),
    end: int = Query(..., ge=0, description="Region end position"),
    mark_type: Optional[str] = Query(None, description="Filter by mark type(s)"),
    min_fold_enrichment: Optional[float] = Query(None, ge=0),
    max_qvalue: Optional[float] = Query(0.05, ge=0, le=1),
    page: int = Query(1, ge=1),
    page_size: int = Query(100, ge=1, le=1000),
    # Phase 9.16: 可选 COUNT(*) 查询，提升拖动/浏览场景性能
    # 参考: Codex 代码审查 - COUNT(*) 在高频请求场景是性能热点
    include_total: bool = Query(True, description="Include total count (set false for faster scrolling)"),
    db: Session = Depends(get_db),
):
    """
    Get ChIP-seq peaks for a specific genomic region

    Useful for browser-like views and custom region queries.
    Maximum region size is 10 Mb to prevent excessive queries.
    """
    # Validate species
    species = db.query(Species).filter(Species.species_id == species_id).first()
    if not species:
        raise HTTPException(status_code=404, detail="Species not found")

    if end <= start:
        raise HTTPException(status_code=400, detail="end must be greater than start")

    # Validate region size to prevent excessive queries
    region_size = end - start
    if region_size > MAX_REGION_SIZE_BP:
        raise HTTPException(
            status_code=400,
            detail=f"Region size ({region_size:,} bp) exceeds maximum allowed ({MAX_REGION_SIZE_BP:,} bp). "
                   f"Please narrow your region to 10 Mb or less."
        )

    mark_types = parse_mark_types(mark_type)

    is_postgresql = db.get_bind().dialect.name == "postgresql"
    if is_postgresql:
        # PostgreSQL: use int8range overlap for efficient range filtering.
        region_predicate = (
            func.int8range(ChIPSeqPeakModel.peak_start, ChIPSeqPeakModel.peak_end, "[)")
            .op("&&")(func.int8range(start, end, "[)"))
        )
    else:
        # Generic fallback for SQLite/demo mode.
        region_predicate = (ChIPSeqPeakModel.peak_start < end) & (ChIPSeqPeakModel.peak_end > start)

    where_conditions = [
        ChIPSeqPeakModel.species_id == species_id,
        ChIPSeqPeakModel.chromosome == chromosome,
        region_predicate,
        ChIPSeqExperiment.is_active.is_(True),
    ]
    if mark_types is not None:
        where_conditions.append(EpigeneticMarkType.mark_name.in_(mark_types))
    if min_fold_enrichment is not None:
        where_conditions.append(ChIPSeqPeakModel.fold_enrichment >= min_fold_enrichment)
    if max_qvalue is not None:
        where_conditions.append(
            (ChIPSeqPeakModel.qvalue.is_(None)) | (ChIPSeqPeakModel.qvalue <= max_qvalue)
        )

    # Phase 9.16: 条件性 COUNT 查询 - 当 include_total=false 时跳过
    total = 0
    if include_total:
        try:
            count_stmt = (
                select(func.count())
                .select_from(ChIPSeqPeakModel)
                .join(ChIPSeqExperiment, ChIPSeqPeakModel.experiment_id == ChIPSeqExperiment.experiment_id)
                .join(EpigeneticMarkType, ChIPSeqExperiment.mark_type_id == EpigeneticMarkType.mark_type_id)
                .where(*where_conditions)
            )
            total = db.execute(count_stmt).scalar() or 0
        except Exception as e:
            raise sanitize_db_error(e, logger)

    # Data query
    offset = compute_pagination_offset(page, page_size)
    try:
        peak_width_expr = (ChIPSeqPeakModel.peak_end - ChIPSeqPeakModel.peak_start).label("peak_width")
        data_stmt = (
            select(
                ChIPSeqPeakModel.peak_id,
                ChIPSeqPeakModel.experiment_id,
                EpigeneticMarkType.mark_name,
                EpigeneticMarkType.mark_category,
                ChIPSeqPeakModel.chromosome,
                ChIPSeqPeakModel.peak_start,
                ChIPSeqPeakModel.peak_end,
                ChIPSeqPeakModel.summit_position,
                ChIPSeqPeakModel.peak_name,
                ChIPSeqPeakModel.strand,
                ChIPSeqPeakModel.fold_enrichment,
                ChIPSeqPeakModel.log2_fold_enrichment,
                ChIPSeqPeakModel.pvalue,
                ChIPSeqPeakModel.neg_log10_pvalue,
                ChIPSeqPeakModel.qvalue,
                ChIPSeqPeakModel.neg_log10_qvalue,
                ChIPSeqPeakModel.signal_value,
                ChIPSeqPeakModel.score,
                peak_width_expr,
            )
            .select_from(ChIPSeqPeakModel)
            .join(ChIPSeqExperiment, ChIPSeqPeakModel.experiment_id == ChIPSeqExperiment.experiment_id)
            .join(EpigeneticMarkType, ChIPSeqExperiment.mark_type_id == EpigeneticMarkType.mark_type_id)
            .where(*where_conditions)
            .order_by(ChIPSeqPeakModel.peak_start)
            .limit(page_size)
            .offset(offset)
        )
        rows = db.execute(
            data_stmt,
        ).fetchall()
    except Exception as e:
        raise sanitize_db_error(e, logger)

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
