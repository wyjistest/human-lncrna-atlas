"""
lncRNA-ChIP-seq Overlap Analysis API

REST endpoints for querying overlaps between lncRNA binding sites and ChIP-seq peaks

Phase 3.0 Enhancements:
- Enhanced /statistics endpoint with by_mark_type and by_cell_type breakdowns
- New /heatmap endpoint for visualization matrices
- Redis caching for expensive aggregation queries
- Rate limiting for API protection

Phase 3.1 Enhancements:
- Batch export endpoint (/export) with BED6 and CSV formats
- Streaming response for large datasets (up to 100K rows)
- Rate limiting (5/minute) for export operations

Phase 3.2 Enhancements (2025-12-09):
- Materialized view support for large chromosome queries (chr1, etc.)
- Auto-detection of materialized view availability
- Fallback to original query when materialized view is not available
- Removed DEFAULT_CHROMOSOME restriction when using materialized view
"""
from fastapi import APIRouter, Depends, Query, HTTPException, Request
from fastapi.responses import StreamingResponse
from sqlalchemy import bindparam, column, func, literal, select, table
from sqlalchemy.orm import Session, aliased
from typing import Optional, List, Tuple, Literal, Generator
import logging
import csv
from io import StringIO
from pydantic import ValidationError
import base64
import json
from decimal import Decimal, InvalidOperation

from app.core.database import get_db
from app.core.cache import cache, cached
from app.core.exceptions import sanitize_db_error, normalize_http_error_detail
from app.core.utils import sanitize_for_log
from app.core.validators import MAX_FIELD_LENGTH, compute_pagination_offset, parse_comma_list
from app.core.mv_cache import mv_cache, is_mv_missing_error  # Phase 9.24: Thread-safe MV cache
from app.utils.bed import sanitize_bed_field
from app.utils.http_headers import content_disposition_attachment
from app.utils.streaming_export import sanitize_csv_value

from app.models import Regulation, Gene, ChIPSeqExperiment, EpigeneticMarkType

# ============================================================================
# Rate Limiting Setup (reuse shared module from chipseq_rate_limit)
# Phase 9.3: 统一使用 ip_utils 处理反向代理场景的真实客户端 IP
# ============================================================================
from app.routers.chipseq_rate_limit import rate_limit
from app.schemas.lncrna_chipseq_overlap import (
    CHROMOSOME_PATTERN,
    OverlapFilters,
    OverlapResponse,
    OverlapCursorResponse,
    OverlapResult,
    OverlapSortField,
    OverlapSortOrder,
    OverlapStatistics,
    MarkTypeStats,
    CellTypeStats,
    HeatmapCell,
    OverlapHeatmapResponse
)

logger = logging.getLogger(__name__)


# =============================================================================
# Export Constants
# =============================================================================

# Batch size for streaming export (rows per chunk)
EXPORT_BATCH_SIZE = 1000

# Maximum rows to export (prevent abuse)
MAX_EXPORT_ROWS = 100000

# Default chromosome when no selective filter provided (performance optimization)
# NOTE: This is only used when materialized view is NOT available
DEFAULT_EXPORT_CHROMOSOME = 'chr22'
DEFAULT_QUERY_CHROMOSOME = 'chr22'

# Large chromosomes that can time out when MV is unavailable and the query is too broad.
# This guard is only applied in the NO-MV fallback path to prevent accidental full-scale joins.
LARGE_CHROMOSOMES_NO_MV_GUARD = {"chr1", "chr2", "chr3"}

# Materialized view name
MV_LNCRNA_CHIPSEQ_OVERLAPS = 'mv_lncrna_chipseq_overlaps'

# Phase 9.24: MV cache moved to app.core.mv_cache for thread-safety and code reuse
# Old module-level cache and check functions removed (see mv_cache.py)


def reset_mv_cache():
    """
    Reset materialized view availability cache.

    Call this after creating/refreshing the MV to force re-check on next query.
    Can be triggered via admin endpoint.

    Phase 9.24: Delegates to centralized thread-safe cache.
    """
    mv_cache.reset()


def check_materialized_view_exists(db: Session) -> bool:
    """
    Check if the materialized view mv_lncrna_chipseq_overlaps exists and is populated.

    Uses caching with TTL to avoid repeated database queries while still detecting
    MV creation/refresh during runtime (Phase 9.12).

    Phase 9.24: Delegates to centralized thread-safe cache.

    Args:
        db: Database session

    Returns:
        True if materialized view exists and is populated, False otherwise
    """
    return mv_cache.is_available(db)


def _raise_query_too_broad(chromosome: str, *, suggest_filters: list[str]) -> None:
    """
    Fail fast for overly broad queries in the NO-MV fallback path.

    Motivation:
    - Without MV, large chromosomes can trigger accidental full-scale joins and time out.
    - Provide a consistent, actionable error for clients to guide narrowing filters or MV setup.
    """
    suggested = "/".join([f for f in suggest_filters if f])
    raise HTTPException(
        status_code=400,
        detail={
            "error": "QUERY_TOO_BROAD",
            "suggest_filters": suggest_filters,
            "message": (
                f"Query for {chromosome} is too broad without materialized view '{MV_LNCRNA_CHIPSEQ_OVERLAPS}'. "
                f"Please add additional filters ({suggested}), or create/refresh the materialized view."
            ),
            "chromosome": chromosome,
            "using_materialized_view": False,
        },
    )


def _encode_overlap_cursor(payload: dict) -> str:
    raw = json.dumps(payload, separators=(",", ":"), ensure_ascii=False).encode("utf-8")
    return base64.urlsafe_b64encode(raw).decode("ascii").rstrip("=")


def _decode_overlap_cursor(token: str, *, sort_by: OverlapSortField, sort_order: OverlapSortOrder) -> dict:
    if not isinstance(token, str) or not token.strip():
        raise HTTPException(status_code=400, detail={"error": "CURSOR_INVALID", "message": "Cursor is empty"})
    if len(token) > 2048:
        raise HTTPException(status_code=400, detail={"error": "CURSOR_INVALID", "message": "Cursor is too long"})

    padded = token + "=" * (-len(token) % 4)
    try:
        raw = base64.urlsafe_b64decode(padded.encode("ascii"))
        payload = json.loads(raw.decode("utf-8"))
    except Exception:
        raise HTTPException(status_code=400, detail={"error": "CURSOR_INVALID", "message": "Cursor decode failed"})

    if not isinstance(payload, dict):
        raise HTTPException(status_code=400, detail={"error": "CURSOR_INVALID", "message": "Cursor payload invalid"})
    if payload.get("v") != 1:
        raise HTTPException(status_code=400, detail={"error": "CURSOR_INVALID", "message": "Cursor version invalid"})

    if payload.get("sort_by") != sort_by.value or payload.get("sort_order") != sort_order.value:
        raise HTTPException(
            status_code=400,
            detail={
                "error": "CURSOR_MISMATCH",
                "message": "Cursor sort parameters do not match request",
            },
        )

    overlap_id = payload.get("overlap_id")
    sort_value_raw = payload.get("sort_value")
    is_null_raw = payload.get("is_null", False)
    if not isinstance(is_null_raw, bool):
        raise HTTPException(status_code=400, detail={"error": "CURSOR_INVALID", "message": "Cursor is_null invalid"})
    if not isinstance(overlap_id, str) or not overlap_id.strip():
        raise HTTPException(status_code=400, detail={"error": "CURSOR_INVALID", "message": "Cursor overlap_id missing"})

    sort_value = None

    if sort_by == OverlapSortField.peak_qvalue:
        if is_null_raw:
            if sort_value_raw is not None:
                raise HTTPException(status_code=400, detail={"error": "CURSOR_INVALID", "message": "Cursor sort_value must be null"})
            sort_value = None
        else:
            if sort_value_raw is None:
                raise HTTPException(status_code=400, detail={"error": "CURSOR_INVALID", "message": "Cursor sort_value missing"})
            try:
                sort_value = Decimal(str(sort_value_raw))
            except (InvalidOperation, ValueError):
                raise HTTPException(status_code=400, detail={"error": "CURSOR_INVALID", "message": "Cursor sort_value invalid"})
    elif sort_by == OverlapSortField.overlap_length:
        if is_null_raw:
            raise HTTPException(status_code=400, detail={"error": "CURSOR_INVALID", "message": "Cursor is_null not allowed"})
        if sort_value_raw is None:
            raise HTTPException(status_code=400, detail={"error": "CURSOR_INVALID", "message": "Cursor sort_value missing"})
        try:
            sort_value = int(sort_value_raw)
        except Exception:
            raise HTTPException(status_code=400, detail={"error": "CURSOR_INVALID", "message": "Cursor sort_value invalid"})
    else:
        if is_null_raw:
            raise HTTPException(status_code=400, detail={"error": "CURSOR_INVALID", "message": "Cursor is_null not allowed"})
        if sort_value_raw is None:
            raise HTTPException(status_code=400, detail={"error": "CURSOR_INVALID", "message": "Cursor sort_value missing"})
        try:
            sort_value = Decimal(str(sort_value_raw))
        except (InvalidOperation, ValueError):
            raise HTTPException(status_code=400, detail={"error": "CURSOR_INVALID", "message": "Cursor sort_value invalid"})

    return {"overlap_id": overlap_id, "sort_value": sort_value, "is_null": is_null_raw}


def _get_cursor_sort_value(item: dict, sort_by: OverlapSortField):
    field_map = {
        OverlapSortField.binding_affinity: "binding_affinity",
        OverlapSortField.overlap_length: "overlap_length",
        OverlapSortField.peak_fold_enrichment: "peak_fold_enrichment",
        OverlapSortField.peak_qvalue: "peak_qvalue",
    }
    return item.get(field_map[sort_by])


# CSV export columns (in order)
CSV_EXPORT_COLUMNS = [
    'overlap_id', 'chromosome', 'overlap_start', 'overlap_end', 'overlap_length',
    'lncrna_gene_id', 'lncrna_name', 'target_gene_id', 'target_gene_name',
    'mark_type', 'mark_category', 'cell_type',
    'binding_affinity', 'peak_fold_enrichment', 'peak_qvalue',
    'lncrna_binding_start', 'lncrna_binding_end', 'peak_start', 'peak_end'
]


router = APIRouter(
    prefix="/lncrna-chipseq-overlap",
    tags=["lncrna-chipseq-overlap"]
)


def _normalize_array_param(values: Optional[List[str]]) -> Optional[List[str]]:
    """Normalize list parameters: treat [] as None (no filter)."""
    if not values:
        return None
    return values


def _build_overlap_where_and_params(
    *,
    lncrna_gene_id: Optional[int],
    target_gene_id: Optional[int],
    chromosome: Optional[str],
    mark_types: Optional[List[str]],
    cell_types: Optional[List[str]],
    min_binding_affinity: Optional[float],
    min_peak_strength: Optional[float],
    max_qvalue: Optional[float],
    min_overlap_length: Optional[int],
    lncrna_gene_col,
    target_gene_col,
    chromosome_col,
    mark_name_col,
    cell_type_col,
    binding_affinity_col,
    fold_enrichment_col,
    qvalue_col,
    overlap_length_expr,
) -> Tuple[List, dict]:
    """
    Build dynamic WHERE conditions to avoid the "(:param IS NULL OR ...)" anti-pattern.

    Rationale:
    - OR-NULL predicates often prevent PostgreSQL from choosing good index plans for large tables/MVs
      when using prepared statements.
    - Dynamic predicate assembly here is safe because all user values are passed as bound parameters
      and column/expression objects are defined in code (no user-controlled SQL fragments).
    """
    conditions: List = []
    params: dict = {}

    if lncrna_gene_id is not None:
        conditions.append(lncrna_gene_col == bindparam("lncrna_gene_id"))
        params["lncrna_gene_id"] = lncrna_gene_id

    if target_gene_id is not None:
        conditions.append(target_gene_col == bindparam("target_gene_id"))
        params["target_gene_id"] = target_gene_id

    if chromosome is not None:
        conditions.append(chromosome_col == bindparam("chromosome"))
        params["chromosome"] = chromosome

    mark_types = _normalize_array_param(mark_types)
    if mark_types is not None:
        conditions.append(mark_name_col.in_(bindparam("mark_types", expanding=True)))
        params["mark_types"] = mark_types

    cell_types = _normalize_array_param(cell_types)
    if cell_types is not None:
        conditions.append(cell_type_col.in_(bindparam("cell_types", expanding=True)))
        params["cell_types"] = cell_types

    if min_binding_affinity is not None:
        conditions.append(binding_affinity_col >= bindparam("min_binding_affinity"))
        params["min_binding_affinity"] = min_binding_affinity

    if min_peak_strength is not None:
        conditions.append(fold_enrichment_col >= bindparam("min_peak_strength"))
        params["min_peak_strength"] = min_peak_strength

    if max_qvalue is not None:
        conditions.append((qvalue_col.is_(None)) | (qvalue_col <= bindparam("max_qvalue")))
        params["max_qvalue"] = max_qvalue

    if min_overlap_length is not None:
        conditions.append(overlap_length_expr >= bindparam("min_overlap_length"))
        params["min_overlap_length"] = min_overlap_length

    return conditions, params


def get_lncrna_chipseq_overlaps_from_mv(
    db: Session,
    filters: OverlapFilters
) -> Tuple[List[dict], int]:
    """
    Query lncRNA-ChIP-seq overlaps from the materialized view.

    This is significantly faster than the base table join, especially for
    large chromosomes like chr1.

    Args:
        db: Database session
        filters: Query filters

    Returns:
        Tuple of (results list, total count)
    """

    # Parse comma-separated filters
    mark_types_array = _normalize_array_param(parse_comma_list(filters.mark_type, param_name="mark_type"))
    cell_types_array = _normalize_array_param(parse_comma_list(filters.cell_type, param_name="cell_type"))
    # Cache key normalization: order does not matter for "= ANY(:array)" semantics.
    cache_mark_types = sorted(set(mark_types_array)) if mark_types_array else None
    cache_cell_types = sorted(set(cell_types_array)) if cell_types_array else None

    mv = table(
        MV_LNCRNA_CHIPSEQ_OVERLAPS,
        column("overlap_id"),
        column("regulation_id"),
        column("lncrna_gene_id"),
        column("lncrna_name"),
        column("target_gene_id"),
        column("target_gene_name"),
        column("mark_name"),
        column("mark_category"),
        column("cell_type"),
        column("chromosome"),
        column("lncrna_binding_start"),
        column("lncrna_binding_end"),
        column("peak_start"),
        column("peak_end"),
        column("overlap_start"),
        column("overlap_end"),
        column("overlap_length"),
        column("binding_affinity"),
        column("fold_enrichment"),
        column("qvalue"),
    )

    # Build sort clause - SECURITY: Uses whitelist to prevent SQL injection
    sort_field_map = {
        OverlapSortField.binding_affinity: mv.c.binding_affinity,
        OverlapSortField.overlap_length: mv.c.overlap_length,
        OverlapSortField.peak_fold_enrichment: mv.c.fold_enrichment,
        OverlapSortField.peak_qvalue: mv.c.qvalue,
    }
    sort_field = sort_field_map[filters.sort_by]
    sort_expr = sort_field.desc() if filters.sort_order == OverlapSortOrder.desc else sort_field.asc()

    where_conditions, params = _build_overlap_where_and_params(
        lncrna_gene_id=filters.lncrna_gene_id,
        target_gene_id=filters.target_gene_id,
        chromosome=filters.chromosome,
        mark_types=mark_types_array,
        cell_types=cell_types_array,
        min_binding_affinity=filters.min_binding_affinity,
        min_peak_strength=filters.min_peak_strength,
        max_qvalue=filters.max_qvalue,
        min_overlap_length=filters.min_overlap_length,
        lncrna_gene_col=mv.c.lncrna_gene_id,
        target_gene_col=mv.c.target_gene_id,
        chromosome_col=mv.c.chromosome,
        mark_name_col=mv.c.mark_name,
        cell_type_col=mv.c.cell_type,
        binding_affinity_col=mv.c.binding_affinity,
        fold_enrichment_col=mv.c.fold_enrichment,
        qvalue_col=mv.c.qvalue,
        overlap_length_expr=mv.c.overlap_length,
    )

    count_stmt = select(func.count().label("total")).select_from(mv)
    data_stmt = select(
        mv.c.overlap_id,
        mv.c.regulation_id,
        mv.c.lncrna_gene_id,
        mv.c.lncrna_name,
        mv.c.target_gene_id,
        mv.c.target_gene_name,
        mv.c.mark_name.label("mark_type"),
        mv.c.mark_category,
        mv.c.cell_type,
        mv.c.chromosome,
        mv.c.lncrna_binding_start,
        mv.c.lncrna_binding_end,
        mv.c.peak_start,
        mv.c.peak_end,
        mv.c.overlap_start,
        mv.c.overlap_end,
        mv.c.overlap_length,
        mv.c.binding_affinity,
        mv.c.fold_enrichment.label("peak_fold_enrichment"),
        mv.c.qvalue.label("peak_qvalue"),
    ).select_from(mv)

    if where_conditions:
        count_stmt = count_stmt.where(*where_conditions)
        data_stmt = data_stmt.where(*where_conditions)

    data_stmt = data_stmt.order_by(sort_expr).limit(bindparam("page_size")).offset(bindparam("offset"))

    # Calculate offset (not part of count cache key)
    offset = compute_pagination_offset(filters.page, filters.page_size)

    params.update(
        {
            "page_size": filters.page_size,
            "offset": offset,
        }
    )

    try:
        def compute_total() -> int:
            count_result = db.execute(count_stmt, params).fetchone()
            return int(count_result[0] if count_result else 0)

        # Cache COUNT(*) separately (hot path for pagination) with singleflight stampede protection.
        total = int(
            cache.get_or_compute(
                "overlap:list_count",
                compute_total,
                ttl=cache.TTL_COUNT,
                source="mv",
                lncrna_gene_id=filters.lncrna_gene_id,
                target_gene_id=filters.target_gene_id,
                chromosome=filters.chromosome,
                mark_types=cache_mark_types,
                cell_types=cache_cell_types,
                min_binding_affinity=filters.min_binding_affinity,
                min_peak_strength=filters.min_peak_strength,
                max_qvalue=filters.max_qvalue,
                min_overlap_length=filters.min_overlap_length,
            )
            or 0
        )

        # Get data
        results = db.execute(data_stmt, params).fetchall()

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
        # Allow MV-missing errors to propagate so the router can auto-fallback to join query.
        if is_mv_missing_error(e):
            raise
        raise sanitize_db_error(e, logger)


def get_lncrna_chipseq_overlaps_cursor_from_mv(
    db: Session,
    filters: OverlapFilters,
    *,
    cursor: Optional[dict],
    page_size: int,
    sort_by: OverlapSortField,
    sort_order: OverlapSortOrder,
) -> Tuple[List[dict], int]:
    """
    Cursor (keyset) pagination for MV-backed overlap list queries.

    Notes:
    - Uses (sort_field, overlap_id) as the stable ordering key.
    - Fetches page_size + 1 rows to determine has_more without COUNT(*) on hot path.
    """
    # Parse comma-separated filters
    mark_types_array = _normalize_array_param(parse_comma_list(filters.mark_type, param_name="mark_type"))
    cell_types_array = _normalize_array_param(parse_comma_list(filters.cell_type, param_name="cell_type"))
    cache_mark_types = sorted(set(mark_types_array)) if mark_types_array else None
    cache_cell_types = sorted(set(cell_types_array)) if cell_types_array else None

    mv = table(
        MV_LNCRNA_CHIPSEQ_OVERLAPS,
        column("overlap_id"),
        column("regulation_id"),
        column("lncrna_gene_id"),
        column("lncrna_name"),
        column("target_gene_id"),
        column("target_gene_name"),
        column("mark_name"),
        column("mark_category"),
        column("cell_type"),
        column("chromosome"),
        column("lncrna_binding_start"),
        column("lncrna_binding_end"),
        column("peak_start"),
        column("peak_end"),
        column("overlap_start"),
        column("overlap_end"),
        column("overlap_length"),
        column("binding_affinity"),
        column("fold_enrichment"),
        column("qvalue"),
    )

    sort_field_map = {
        OverlapSortField.binding_affinity: mv.c.binding_affinity,
        OverlapSortField.overlap_length: mv.c.overlap_length,
        OverlapSortField.peak_fold_enrichment: mv.c.fold_enrichment,
        OverlapSortField.peak_qvalue: mv.c.qvalue,
    }
    sort_field = sort_field_map[sort_by]
    if sort_by == OverlapSortField.peak_qvalue:
        is_null_expr = sort_field.is_(None)
        primary_order = is_null_expr.asc()
        qvalue_order = sort_field.desc() if sort_order == OverlapSortOrder.desc else sort_field.asc()
        tie_order = mv.c.overlap_id.desc() if sort_order == OverlapSortOrder.desc else mv.c.overlap_id.asc()
    else:
        primary_order = sort_field.desc() if sort_order == OverlapSortOrder.desc else sort_field.asc()
        tie_order = mv.c.overlap_id.desc() if sort_order == OverlapSortOrder.desc else mv.c.overlap_id.asc()

    where_conditions, params = _build_overlap_where_and_params(
        lncrna_gene_id=filters.lncrna_gene_id,
        target_gene_id=filters.target_gene_id,
        chromosome=filters.chromosome,
        mark_types=mark_types_array,
        cell_types=cell_types_array,
        min_binding_affinity=filters.min_binding_affinity,
        min_peak_strength=filters.min_peak_strength,
        max_qvalue=filters.max_qvalue,
        min_overlap_length=filters.min_overlap_length,
        lncrna_gene_col=mv.c.lncrna_gene_id,
        target_gene_col=mv.c.target_gene_id,
        chromosome_col=mv.c.chromosome,
        mark_name_col=mv.c.mark_name,
        cell_type_col=mv.c.cell_type,
        binding_affinity_col=mv.c.binding_affinity,
        fold_enrichment_col=mv.c.fold_enrichment,
        qvalue_col=mv.c.qvalue,
        overlap_length_expr=mv.c.overlap_length,
    )

    count_stmt = select(func.count().label("total")).select_from(mv)
    data_stmt = select(
        mv.c.overlap_id,
        mv.c.regulation_id,
        mv.c.lncrna_gene_id,
        mv.c.lncrna_name,
        mv.c.target_gene_id,
        mv.c.target_gene_name,
        mv.c.mark_name.label("mark_type"),
        mv.c.mark_category,
        mv.c.cell_type,
        mv.c.chromosome,
        mv.c.lncrna_binding_start,
        mv.c.lncrna_binding_end,
        mv.c.peak_start,
        mv.c.peak_end,
        mv.c.overlap_start,
        mv.c.overlap_end,
        mv.c.overlap_length,
        mv.c.binding_affinity,
        mv.c.fold_enrichment.label("peak_fold_enrichment"),
        mv.c.qvalue.label("peak_qvalue"),
    ).select_from(mv)

    if where_conditions:
        count_stmt = count_stmt.where(*where_conditions)
        data_stmt = data_stmt.where(*where_conditions)

    if cursor is not None:
        params["cursor_overlap_id"] = cursor["overlap_id"]
        if sort_by == OverlapSortField.peak_qvalue:
            cursor_is_null = bool(cursor.get("is_null"))
            is_null_expr = sort_field.is_(None)
            is_not_null_expr = sort_field.is_not(None)

            if cursor_is_null:
                if sort_order == OverlapSortOrder.desc:
                    data_stmt = data_stmt.where(is_null_expr & (mv.c.overlap_id < bindparam("cursor_overlap_id")))
                else:
                    data_stmt = data_stmt.where(is_null_expr & (mv.c.overlap_id > bindparam("cursor_overlap_id")))
            else:
                params["cursor_sort_value"] = cursor["sort_value"]
                if sort_order == OverlapSortOrder.desc:
                    data_stmt = data_stmt.where(
                        is_null_expr
                        | (
                            is_not_null_expr
                            & (
                                (sort_field < bindparam("cursor_sort_value"))
                                | (
                                    (sort_field == bindparam("cursor_sort_value"))
                                    & (mv.c.overlap_id < bindparam("cursor_overlap_id"))
                                )
                            )
                        )
                    )
                else:
                    data_stmt = data_stmt.where(
                        is_null_expr
                        | (
                            is_not_null_expr
                            & (
                                (sort_field > bindparam("cursor_sort_value"))
                                | (
                                    (sort_field == bindparam("cursor_sort_value"))
                                    & (mv.c.overlap_id > bindparam("cursor_overlap_id"))
                                )
                            )
                        )
                    )
        else:
            params["cursor_sort_value"] = cursor["sort_value"]
            if sort_order == OverlapSortOrder.desc:
                data_stmt = data_stmt.where(
                    (sort_field < bindparam("cursor_sort_value"))
                    | (
                        (sort_field == bindparam("cursor_sort_value"))
                        & (mv.c.overlap_id < bindparam("cursor_overlap_id"))
                    )
                )
            else:
                data_stmt = data_stmt.where(
                    (sort_field > bindparam("cursor_sort_value"))
                    | (
                        (sort_field == bindparam("cursor_sort_value"))
                        & (mv.c.overlap_id > bindparam("cursor_overlap_id"))
                    )
                )

    if sort_by == OverlapSortField.peak_qvalue:
        data_stmt = data_stmt.order_by(primary_order, qvalue_order, tie_order).limit(bindparam("limit"))
    else:
        data_stmt = data_stmt.order_by(primary_order, tie_order).limit(bindparam("limit"))
    params["limit"] = page_size + 1

    try:

        def compute_total() -> int:
            count_result = db.execute(count_stmt, params).fetchone()
            return int(count_result[0] if count_result else 0)

        total = int(
            cache.get_or_compute(
                "overlap:list_count",
                compute_total,
                ttl=cache.TTL_COUNT,
                source="mv",
                lncrna_gene_id=filters.lncrna_gene_id,
                target_gene_id=filters.target_gene_id,
                chromosome=filters.chromosome,
                mark_types=cache_mark_types,
                cell_types=cache_cell_types,
                min_binding_affinity=filters.min_binding_affinity,
                min_peak_strength=filters.min_peak_strength,
                max_qvalue=filters.max_qvalue,
                min_overlap_length=filters.min_overlap_length,
            )
            or 0
        )

        results = db.execute(data_stmt, params).fetchall()
        items: List[dict] = []
        for row in results:
            items.append(
                {
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
                    "peak_qvalue": row.peak_qvalue,
                }
            )

        return items, total

    except Exception as e:
        if is_mv_missing_error(e):
            raise
        raise sanitize_db_error(e, logger)


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
    mark_types_array = _normalize_array_param(parse_comma_list(filters.mark_type, param_name="mark_type"))
    cell_types_array = _normalize_array_param(parse_comma_list(filters.cell_type, param_name="cell_type"))
    # Cache key normalization: order does not matter for "= ANY(:array)" semantics.
    cache_mark_types = sorted(set(mark_types_array)) if mark_types_array else None
    cache_cell_types = sorted(set(cell_types_array)) if cell_types_array else None

    p = table(
        "chipseq_peaks_human",
        column("peak_id"),
        column("species_id"),
        column("chromosome"),
        column("peak_start"),
        column("peak_end"),
        column("experiment_id"),
        column("fold_enrichment"),
        column("qvalue"),
    )
    overlap_start_base = func.greatest(Regulation.best_peak_start, p.c.peak_start)
    overlap_end_base = func.least(Regulation.best_peak_end, p.c.peak_end)
    overlap_start_expr = overlap_start_base.label("overlap_start")
    overlap_end_expr = overlap_end_base.label("overlap_end")
    overlap_length_expr = (overlap_end_base - overlap_start_base).label("overlap_length")

    # Build sort clause - SECURITY: Uses whitelist to prevent SQL injection
    # Only allowed values from the map can be used in the SQL query
    sort_field_map = {
        OverlapSortField.binding_affinity: Regulation.binding_affinity,
        OverlapSortField.overlap_length: overlap_length_expr,
        OverlapSortField.peak_fold_enrichment: p.c.fold_enrichment,
        OverlapSortField.peak_qvalue: p.c.qvalue,
    }
    sort_field = sort_field_map[filters.sort_by]
    sort_expr = sort_field.desc() if filters.sort_order == OverlapSortOrder.desc else sort_field.asc()

    filter_conditions, params = _build_overlap_where_and_params(
        lncrna_gene_id=filters.lncrna_gene_id,
        target_gene_id=filters.target_gene_id,
        chromosome=filters.chromosome,
        mark_types=mark_types_array,
        cell_types=cell_types_array,
        min_binding_affinity=filters.min_binding_affinity,
        min_peak_strength=filters.min_peak_strength,
        max_qvalue=filters.max_qvalue,
        min_overlap_length=filters.min_overlap_length,
        lncrna_gene_col=Regulation.lncrna_gene_id,
        target_gene_col=Regulation.target_gene_id,
        chromosome_col=Regulation.best_peak_chr,
        mark_name_col=EpigeneticMarkType.mark_name,
        cell_type_col=ChIPSeqExperiment.cell_type,
        binding_affinity_col=Regulation.binding_affinity,
        fold_enrichment_col=p.c.fold_enrichment,
        qvalue_col=p.c.qvalue,
        overlap_length_expr=overlap_length_expr,
    )

    where_conditions = [Regulation.species_id == 1, ChIPSeqExperiment.is_active.is_(True), *filter_conditions]
    join_on_peak = (
        (Regulation.species_id == p.c.species_id)
        & (Regulation.best_peak_chr == p.c.chromosome)
        & (Regulation.best_peak_start < p.c.peak_end)
        & (Regulation.best_peak_end > p.c.peak_start)
    )

    count_stmt = (
        select(func.count().label("total"))
        .select_from(Regulation)
        .join(p, join_on_peak)
        .join(ChIPSeqExperiment, p.c.experiment_id == ChIPSeqExperiment.experiment_id)
        .join(EpigeneticMarkType, ChIPSeqExperiment.mark_type_id == EpigeneticMarkType.mark_type_id)
        .where(*where_conditions)
    )

    lnc = aliased(Gene)
    tgt = aliased(Gene)
    data_stmt = (
        select(
            func.concat(literal("reg_"), Regulation.regulation_id, literal("_peak_"), p.c.peak_id).label("overlap_id"),
            Regulation.regulation_id,
            Regulation.lncrna_gene_id,
            lnc.gene_name.label("lncrna_name"),
            Regulation.target_gene_id,
            tgt.gene_name.label("target_gene_name"),
            EpigeneticMarkType.mark_name.label("mark_type"),
            EpigeneticMarkType.mark_category,
            ChIPSeqExperiment.cell_type,
            Regulation.best_peak_chr.label("chromosome"),
            Regulation.best_peak_start.label("lncrna_binding_start"),
            Regulation.best_peak_end.label("lncrna_binding_end"),
            p.c.peak_start,
            p.c.peak_end,
            overlap_start_expr,
            overlap_end_expr,
            overlap_length_expr,
            Regulation.binding_affinity,
            p.c.fold_enrichment.label("peak_fold_enrichment"),
            p.c.qvalue.label("peak_qvalue"),
        )
        .select_from(Regulation)
        .join(lnc, Regulation.lncrna_gene_id == lnc.gene_id)
        .join(tgt, Regulation.target_gene_id == tgt.gene_id)
        .join(p, join_on_peak)
        .join(ChIPSeqExperiment, p.c.experiment_id == ChIPSeqExperiment.experiment_id)
        .join(EpigeneticMarkType, ChIPSeqExperiment.mark_type_id == EpigeneticMarkType.mark_type_id)
        .where(*where_conditions)
        .order_by(sort_expr)
        .limit(bindparam("page_size"))
        .offset(bindparam("offset"))
    )

    # Calculate offset (not part of count cache key)
    offset = compute_pagination_offset(filters.page, filters.page_size)

    params.update(
        {
            "page_size": filters.page_size,
            "offset": offset,
        }
    )

    try:
        def compute_total() -> int:
            count_result = db.execute(count_stmt, params).fetchone()
            return int(count_result[0] if count_result else 0)

        # Cache COUNT(*) separately (hot path for pagination) with singleflight stampede protection.
        total = int(
            cache.get_or_compute(
                "overlap:list_count",
                compute_total,
                ttl=cache.TTL_COUNT,
                source="join",
                lncrna_gene_id=filters.lncrna_gene_id,
                target_gene_id=filters.target_gene_id,
                chromosome=filters.chromosome,
                mark_types=cache_mark_types,
                cell_types=cache_cell_types,
                min_binding_affinity=filters.min_binding_affinity,
                min_peak_strength=filters.min_peak_strength,
                max_qvalue=filters.max_qvalue,
                min_overlap_length=filters.min_overlap_length,
            )
            or 0
        )

        # Get data
        results = db.execute(data_stmt, params).fetchall()

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
        raise sanitize_db_error(e, logger)


def get_lncrna_chipseq_overlaps_cursor_query(
    db: Session,
    filters: OverlapFilters,
    *,
    cursor: Optional[dict],
    page_size: int,
    sort_by: OverlapSortField,
    sort_order: OverlapSortOrder,
) -> Tuple[List[dict], int]:
    """
    Cursor (keyset) pagination for base-table join overlap list queries.

    Notes:
    - Uses (sort_field, overlap_id) as the stable ordering key.
    - Fetches page_size + 1 rows to determine has_more.
    """
    mark_types_array = _normalize_array_param(parse_comma_list(filters.mark_type, param_name="mark_type"))
    cell_types_array = _normalize_array_param(parse_comma_list(filters.cell_type, param_name="cell_type"))
    cache_mark_types = sorted(set(mark_types_array)) if mark_types_array else None
    cache_cell_types = sorted(set(cell_types_array)) if cell_types_array else None

    p = table(
        "chipseq_peaks_human",
        column("peak_id"),
        column("species_id"),
        column("chromosome"),
        column("peak_start"),
        column("peak_end"),
        column("experiment_id"),
        column("fold_enrichment"),
        column("qvalue"),
    )
    overlap_start_base = func.greatest(Regulation.best_peak_start, p.c.peak_start)
    overlap_end_base = func.least(Regulation.best_peak_end, p.c.peak_end)
    overlap_start_expr = overlap_start_base.label("overlap_start")
    overlap_end_expr = overlap_end_base.label("overlap_end")
    overlap_length_expr = (overlap_end_base - overlap_start_base).label("overlap_length")

    sort_field_map = {
        OverlapSortField.binding_affinity: Regulation.binding_affinity,
        OverlapSortField.overlap_length: overlap_length_expr,
        OverlapSortField.peak_fold_enrichment: p.c.fold_enrichment,
        OverlapSortField.peak_qvalue: p.c.qvalue,
    }
    sort_field = sort_field_map[sort_by]

    overlap_id_expr = func.concat(literal("reg_"), Regulation.regulation_id, literal("_peak_"), p.c.peak_id)
    if sort_by == OverlapSortField.peak_qvalue:
        is_null_expr = sort_field.is_(None)
        primary_order = is_null_expr.asc()
        qvalue_order = sort_field.desc() if sort_order == OverlapSortOrder.desc else sort_field.asc()
        tie_order = overlap_id_expr.desc() if sort_order == OverlapSortOrder.desc else overlap_id_expr.asc()
    else:
        primary_order = sort_field.desc() if sort_order == OverlapSortOrder.desc else sort_field.asc()
        tie_order = overlap_id_expr.desc() if sort_order == OverlapSortOrder.desc else overlap_id_expr.asc()

    filter_conditions, params = _build_overlap_where_and_params(
        lncrna_gene_id=filters.lncrna_gene_id,
        target_gene_id=filters.target_gene_id,
        chromosome=filters.chromosome,
        mark_types=mark_types_array,
        cell_types=cell_types_array,
        min_binding_affinity=filters.min_binding_affinity,
        min_peak_strength=filters.min_peak_strength,
        max_qvalue=filters.max_qvalue,
        min_overlap_length=filters.min_overlap_length,
        lncrna_gene_col=Regulation.lncrna_gene_id,
        target_gene_col=Regulation.target_gene_id,
        chromosome_col=Regulation.best_peak_chr,
        mark_name_col=EpigeneticMarkType.mark_name,
        cell_type_col=ChIPSeqExperiment.cell_type,
        binding_affinity_col=Regulation.binding_affinity,
        fold_enrichment_col=p.c.fold_enrichment,
        qvalue_col=p.c.qvalue,
        overlap_length_expr=overlap_length_expr,
    )

    where_conditions = [Regulation.species_id == 1, ChIPSeqExperiment.is_active.is_(True), *filter_conditions]
    join_on_peak = (
        (Regulation.species_id == p.c.species_id)
        & (Regulation.best_peak_chr == p.c.chromosome)
        & (Regulation.best_peak_start < p.c.peak_end)
        & (Regulation.best_peak_end > p.c.peak_start)
    )

    count_stmt = (
        select(func.count().label("total"))
        .select_from(Regulation)
        .join(p, join_on_peak)
        .join(ChIPSeqExperiment, p.c.experiment_id == ChIPSeqExperiment.experiment_id)
        .join(EpigeneticMarkType, ChIPSeqExperiment.mark_type_id == EpigeneticMarkType.mark_type_id)
        .where(*where_conditions)
    )

    lnc = aliased(Gene)
    tgt = aliased(Gene)
    data_stmt = (
        select(
            overlap_id_expr.label("overlap_id"),
            Regulation.regulation_id,
            Regulation.lncrna_gene_id,
            lnc.gene_name.label("lncrna_name"),
            Regulation.target_gene_id,
            tgt.gene_name.label("target_gene_name"),
            EpigeneticMarkType.mark_name.label("mark_type"),
            EpigeneticMarkType.mark_category,
            ChIPSeqExperiment.cell_type,
            Regulation.best_peak_chr.label("chromosome"),
            Regulation.best_peak_start.label("lncrna_binding_start"),
            Regulation.best_peak_end.label("lncrna_binding_end"),
            p.c.peak_start,
            p.c.peak_end,
            overlap_start_expr,
            overlap_end_expr,
            overlap_length_expr,
            Regulation.binding_affinity,
            p.c.fold_enrichment.label("peak_fold_enrichment"),
            p.c.qvalue.label("peak_qvalue"),
        )
        .select_from(Regulation)
        .join(lnc, Regulation.lncrna_gene_id == lnc.gene_id)
        .join(tgt, Regulation.target_gene_id == tgt.gene_id)
        .join(p, join_on_peak)
        .join(ChIPSeqExperiment, p.c.experiment_id == ChIPSeqExperiment.experiment_id)
        .join(EpigeneticMarkType, ChIPSeqExperiment.mark_type_id == EpigeneticMarkType.mark_type_id)
        .where(*where_conditions)
    )

    if cursor is not None:
        params["cursor_overlap_id"] = cursor["overlap_id"]
        if sort_by == OverlapSortField.peak_qvalue:
            cursor_is_null = bool(cursor.get("is_null"))
            is_null_expr = sort_field.is_(None)
            is_not_null_expr = sort_field.is_not(None)

            if cursor_is_null:
                if sort_order == OverlapSortOrder.desc:
                    data_stmt = data_stmt.where(is_null_expr & (overlap_id_expr < bindparam("cursor_overlap_id")))
                else:
                    data_stmt = data_stmt.where(is_null_expr & (overlap_id_expr > bindparam("cursor_overlap_id")))
            else:
                params["cursor_sort_value"] = cursor["sort_value"]
                if sort_order == OverlapSortOrder.desc:
                    data_stmt = data_stmt.where(
                        is_null_expr
                        | (
                            is_not_null_expr
                            & (
                                (sort_field < bindparam("cursor_sort_value"))
                                | (
                                    (sort_field == bindparam("cursor_sort_value"))
                                    & (overlap_id_expr < bindparam("cursor_overlap_id"))
                                )
                            )
                        )
                    )
                else:
                    data_stmt = data_stmt.where(
                        is_null_expr
                        | (
                            is_not_null_expr
                            & (
                                (sort_field > bindparam("cursor_sort_value"))
                                | (
                                    (sort_field == bindparam("cursor_sort_value"))
                                    & (overlap_id_expr > bindparam("cursor_overlap_id"))
                                )
                            )
                        )
                    )
        else:
            params["cursor_sort_value"] = cursor["sort_value"]
            if sort_order == OverlapSortOrder.desc:
                data_stmt = data_stmt.where(
                    (sort_field < bindparam("cursor_sort_value"))
                    | (
                        (sort_field == bindparam("cursor_sort_value"))
                        & (overlap_id_expr < bindparam("cursor_overlap_id"))
                    )
                )
            else:
                data_stmt = data_stmt.where(
                    (sort_field > bindparam("cursor_sort_value"))
                    | (
                        (sort_field == bindparam("cursor_sort_value"))
                        & (overlap_id_expr > bindparam("cursor_overlap_id"))
                    )
                )

    if sort_by == OverlapSortField.peak_qvalue:
        data_stmt = data_stmt.order_by(primary_order, qvalue_order, tie_order).limit(bindparam("limit"))
    else:
        data_stmt = data_stmt.order_by(primary_order, tie_order).limit(bindparam("limit"))
    params["limit"] = page_size + 1

    try:

        def compute_total() -> int:
            count_result = db.execute(count_stmt, params).fetchone()
            return int(count_result[0] if count_result else 0)

        total = int(
            cache.get_or_compute(
                "overlap:list_count",
                compute_total,
                ttl=cache.TTL_COUNT,
                source="join",
                lncrna_gene_id=filters.lncrna_gene_id,
                target_gene_id=filters.target_gene_id,
                chromosome=filters.chromosome,
                mark_types=cache_mark_types,
                cell_types=cache_cell_types,
                min_binding_affinity=filters.min_binding_affinity,
                min_peak_strength=filters.min_peak_strength,
                max_qvalue=filters.max_qvalue,
                min_overlap_length=filters.min_overlap_length,
            )
            or 0
        )

        results = db.execute(data_stmt, params).fetchall()
        items: List[dict] = []
        for row in results:
            items.append(
                {
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
                    "peak_qvalue": row.peak_qvalue,
                }
            )

        return items, total

    except Exception as e:
        raise sanitize_db_error(e, logger)


@router.get("", response_model=OverlapResponse)
@rate_limit("60/minute")  # Rate limit: 60 requests per minute per IP
def get_lncrna_chipseq_overlaps(
    request: Request,  # Required for rate limiting
    lncrna_gene_id: Optional[int] = Query(None, description="Filter by specific lncRNA gene ID"),
    target_gene_id: Optional[int] = Query(None, description="Filter by specific target gene ID"),
    mark_type: Optional[str] = Query(
        None,
        max_length=MAX_FIELD_LENGTH,
        description="Filter by mark type(s), comma-separated (max 20 items)",
    ),
    cell_type: Optional[str] = Query(
        None,
        max_length=MAX_FIELD_LENGTH,
        description="Filter by cell type(s), comma-separated (max 20 items)",
    ),
    chromosome: Optional[str] = Query(None, max_length=64, description="Filter by chromosome (e.g., 'chr1')"),
    min_overlap_length: Optional[int] = Query(None, ge=1, description="Minimum overlap length in bp"),
    min_binding_affinity: Optional[float] = Query(None, ge=0, description="Minimum binding affinity score"),
    min_peak_strength: Optional[float] = Query(None, ge=0, description="Minimum peak fold enrichment"),
    max_qvalue: Optional[float] = Query(0.05, ge=0, le=1, description="Maximum Q-value (FDR) for peaks"),
    page: int = Query(1, ge=1, description="Page number (starts from 1)"),
    page_size: int = Query(100, ge=1, le=1000, description="Items per page"),
    sort_by: OverlapSortField = Query(
        OverlapSortField.binding_affinity,
        description="Sort field (binding_affinity, overlap_length, peak_fold_enrichment, peak_qvalue)",
    ),
    sort_order: OverlapSortOrder = Query(
        OverlapSortOrder.desc,
        description="Sort order (asc or desc)",
    ),
    db: Session = Depends(get_db)
):
    """
    Get overlaps between lncRNA binding sites and ChIP-seq peaks (paginated)

    ## Overview
    This endpoint identifies genomic regions where lncRNA binding sites overlap with ChIP-seq peaks,
    enabling analysis of lncRNA-mediated epigenetic regulation mechanisms.

    ## Performance Note
    **With Materialized View (recommended):**
    When the materialized view `mv_lncrna_chipseq_overlaps` is available, queries are fast for all
    chromosomes including chr1. No default chromosome filter is applied.

    **Without Materialized View (fallback):**
    If no selective filters are provided (lncrna_gene_id, target_gene_id, chromosome, mark_type,
    cell_type, or min_binding_affinity > 0), the query defaults to chromosome='chr22' to prevent
    timeout on the full spatial join of 4.6M peaks x 800K regulations.

    For large chromosomes (chr1/chr2/chr3) without MV, a chromosome-only query is rejected with
    `400 QUERY_TOO_BROAD` unless you add at least one additional narrowing filter.

    The response includes:
    - `default_filter_applied`: True if default chromosome filter was applied
    - `effective_chromosome`: The chromosome filter actually used
    - `using_materialized_view`: True if the optimized materialized view was used

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
    - **sort_by**: Sort field - "binding_affinity", "overlap_length", "peak_fold_enrichment", or "peak_qvalue" (default: "binding_affinity")
    - **sort_order**: Sort direction - "asc" or "desc" (default: "desc")

    ## Response
    Returns paginated list of overlaps with genomic coordinates, signal metrics, and gene information.
    Includes `default_filter_applied` (bool) and `effective_chromosome` (str) to indicate if default
    chromosome filter was applied.

    ## Example
    ```
    GET /api/v1/lncrna-chipseq-overlap?chromosome=chr1&mark_type=H3K27me3&min_binding_affinity=60&page=1&page_size=10
    ```
    """

    # Check if materialized view is available for optimized queries
    use_materialized_view = check_materialized_view_exists(db)

    # Initialize response metadata
    default_filter_applied = False
    effective_chromosome = chromosome

    if use_materialized_view:
        # Materialized view is available - no need for default chromosome restriction
        logger.debug("Using materialized view for overlap query")
    else:
        # Fallback: Apply default chromosome filter for performance
        has_selective_filter = any([
            lncrna_gene_id,
            target_gene_id,
            chromosome,
            mark_type,
            cell_type,
            min_binding_affinity and min_binding_affinity > 0,
        ])

        if not has_selective_filter:
            effective_chromosome = DEFAULT_QUERY_CHROMOSOME
            default_filter_applied = True
            logger.info(f"No selective filter provided and MV not available, applying default chromosome='{DEFAULT_QUERY_CHROMOSOME}'")
        else:
            # Guard: even with a chromosome filter, chr1/chr2/chr3 can still be too broad without MV.
            # Require at least one additional narrowing filter, otherwise fail fast with a clear message.
            has_narrowing_filter = any([
                lncrna_gene_id,
                target_gene_id,
                mark_type,
                cell_type,
                min_overlap_length,
                min_peak_strength and min_peak_strength > 0,
                min_binding_affinity and min_binding_affinity > 0,
            ])

            if chromosome in LARGE_CHROMOSOMES_NO_MV_GUARD and not has_narrowing_filter:
                _raise_query_too_broad(
                    chromosome,
                    suggest_filters=[
                        "mark_type",
                        "cell_type",
                        "lncrna_gene_id",
                        "target_gene_id",
                        "min_binding_affinity",
                        "min_peak_strength",
                        "min_overlap_length",
                    ],
                )

    # Build filters object with effective chromosome
    try:
        filters = OverlapFilters(
            lncrna_gene_id=lncrna_gene_id,
            target_gene_id=target_gene_id,
            mark_type=mark_type,
            cell_type=cell_type,
            chromosome=effective_chromosome,
            min_overlap_length=min_overlap_length,
            min_binding_affinity=min_binding_affinity,
            min_peak_strength=min_peak_strength,
            max_qvalue=max_qvalue,
            page=page,
            page_size=page_size,
            sort_by=sort_by,
            sort_order=sort_order,
        )
    except ValidationError as e:
        raise HTTPException(status_code=422, detail=normalize_http_error_detail(e.errors(), status_code=422))

    # Execute query using appropriate method
    # Phase 9.24: Add error handling for MV queries - auto-fallback if MV dropped during TTL
    if use_materialized_view:
        try:
            items, total = get_lncrna_chipseq_overlaps_from_mv(db, filters)
        except Exception as e:
            if is_mv_missing_error(e):
                logger.warning(
                    "MV query failed (MV may have been dropped), falling back to join query: %s",
                    sanitize_for_log(e, max_length=2000),
                )
                mv_cache.reset()
                use_materialized_view = False
                items, total = get_lncrna_chipseq_overlaps_query(db, filters)
            else:
                raise
    else:
        items, total = get_lncrna_chipseq_overlaps_query(db, filters)

    # Calculate total pages
    total_pages = OverlapResponse.calculate_total_pages(total, page_size)

    # Build response with metadata
    return OverlapResponse(
        total=total,
        page=page,
        page_size=page_size,
        total_pages=total_pages,
        items=[OverlapResult(**item) for item in items],
        default_filter_applied=default_filter_applied,
        effective_chromosome=effective_chromosome,
        using_materialized_view=use_materialized_view
    )


@router.get("/cursor", response_model=OverlapCursorResponse)
@rate_limit("60/minute")  # Rate limit: 60 requests per minute per IP
def get_lncrna_chipseq_overlaps_cursor(
    request: Request,  # Required for rate limiting
    lncrna_gene_id: Optional[int] = Query(None, description="Filter by specific lncRNA gene ID"),
    target_gene_id: Optional[int] = Query(None, description="Filter by specific target gene ID"),
    mark_type: Optional[str] = Query(
        None,
        max_length=MAX_FIELD_LENGTH,
        description="Filter by mark type(s), comma-separated (max 20 items)",
    ),
    cell_type: Optional[str] = Query(
        None,
        max_length=MAX_FIELD_LENGTH,
        description="Filter by cell type(s), comma-separated (max 20 items)",
    ),
    chromosome: Optional[str] = Query(
        None,
        max_length=10,
        pattern=CHROMOSOME_PATTERN,
        description="Filter by chromosome (e.g., 'chr1', 'chrX')",
    ),
    min_overlap_length: Optional[int] = Query(None, ge=1, description="Minimum overlap length in bp"),
    min_binding_affinity: Optional[float] = Query(None, ge=0, description="Minimum binding affinity score"),
    min_peak_strength: Optional[float] = Query(None, ge=0, description="Minimum peak fold enrichment"),
    max_qvalue: Optional[float] = Query(0.05, ge=0, le=1, description="Maximum Q-value (FDR) for peaks"),
    cursor: Optional[str] = Query(None, max_length=2048, description="Opaque cursor token for keyset pagination"),
    page_size: int = Query(100, ge=1, le=1000, description="Items per page"),
    sort_by: OverlapSortField = Query(
        OverlapSortField.binding_affinity,
        description="Sort field (binding_affinity, overlap_length, peak_fold_enrichment, peak_qvalue)",
    ),
    sort_order: OverlapSortOrder = Query(
        OverlapSortOrder.desc,
        description="Sort order (asc or desc)",
    ),
    db: Session = Depends(get_db),
):
    use_materialized_view = check_materialized_view_exists(db)

    default_filter_applied = False
    effective_chromosome = chromosome

    if use_materialized_view:
        logger.debug("Using materialized view for overlap cursor query")
    else:
        has_selective_filter = any(
            [
                lncrna_gene_id,
                target_gene_id,
                chromosome,
                mark_type,
                cell_type,
                min_binding_affinity and min_binding_affinity > 0,
            ]
        )

        if not has_selective_filter:
            effective_chromosome = DEFAULT_QUERY_CHROMOSOME
            default_filter_applied = True
            logger.info(
                "No selective filter provided and MV not available, applying default chromosome='%s' (cursor)",
                DEFAULT_QUERY_CHROMOSOME,
            )
        else:
            has_narrowing_filter = any(
                [
                    lncrna_gene_id,
                    target_gene_id,
                    mark_type,
                    cell_type,
                    min_overlap_length,
                    min_peak_strength and min_peak_strength > 0,
                    min_binding_affinity and min_binding_affinity > 0,
                ]
            )
            if effective_chromosome in LARGE_CHROMOSOMES_NO_MV_GUARD and not has_narrowing_filter:
                _raise_query_too_broad(
                    effective_chromosome,
                    suggest_filters=[
                        "mark_type",
                        "cell_type",
                        "lncrna_gene_id",
                        "target_gene_id",
                        "min_binding_affinity",
                        "min_peak_strength",
                        "min_overlap_length",
                    ],
                )

    try:
        filters = OverlapFilters(
            lncrna_gene_id=lncrna_gene_id,
            target_gene_id=target_gene_id,
            mark_type=mark_type,
            cell_type=cell_type,
            chromosome=effective_chromosome,
            min_overlap_length=min_overlap_length,
            min_binding_affinity=min_binding_affinity,
            min_peak_strength=min_peak_strength,
            max_qvalue=max_qvalue,
            page=1,
            page_size=page_size,
            sort_by=sort_by,
            sort_order=sort_order,
        )
    except ValidationError as e:
        raise HTTPException(status_code=422, detail=normalize_http_error_detail(e.errors(), status_code=422))

    cursor_payload = None
    if cursor:
        cursor_payload = _decode_overlap_cursor(cursor, sort_by=sort_by, sort_order=sort_order)

    if use_materialized_view:
        try:
            items, total = get_lncrna_chipseq_overlaps_cursor_from_mv(
                db,
                filters,
                cursor=cursor_payload,
                page_size=page_size,
                sort_by=sort_by,
                sort_order=sort_order,
            )
        except Exception as e:
            if is_mv_missing_error(e):
                logger.warning(
                    "MV cursor query failed (MV may have been dropped), falling back to join query: %s",
                    sanitize_for_log(e, max_length=2000),
                )
                mv_cache.reset()
                use_materialized_view = False
                items, total = get_lncrna_chipseq_overlaps_cursor_query(
                    db,
                    filters,
                    cursor=cursor_payload,
                    page_size=page_size,
                    sort_by=sort_by,
                    sort_order=sort_order,
                )
            else:
                raise
    else:
        items, total = get_lncrna_chipseq_overlaps_cursor_query(
            db,
            filters,
            cursor=cursor_payload,
            page_size=page_size,
            sort_by=sort_by,
            sort_order=sort_order,
        )

    has_more = len(items) > page_size
    page_items = items[:page_size]

    next_cursor = None
    if has_more and page_items:
        last = page_items[-1]
        sort_value = _get_cursor_sort_value(last, sort_by)
        next_cursor = _encode_overlap_cursor(
            {
                "v": 1,
                "sort_by": sort_by.value,
                "sort_order": sort_order.value,
                "is_null": sort_value is None,
                "sort_value": str(sort_value) if sort_value is not None else None,
                "overlap_id": last.get("overlap_id"),
            }
        )

    return OverlapCursorResponse(
        total=total,
        page_size=page_size,
        items=[OverlapResult(**item) for item in page_items],
        next_cursor=next_cursor,
        has_more=has_more,
        default_filter_applied=default_filter_applied,
        effective_chromosome=effective_chromosome,
        using_materialized_view=use_materialized_view,
    )


@router.get("/statistics", response_model=OverlapStatistics)
@rate_limit("60/minute")  # Rate limit: 60 requests per minute per IP
@cached("overlap:statistics", ttl=cache.TTL_LIST)  # Cache: 5 minutes
def get_overlap_statistics(
    request: Request,  # Required for rate limiting
    lncrna_gene_id: Optional[int] = Query(None, description="Filter by specific lncRNA gene ID"),
    target_gene_id: Optional[int] = Query(None, description="Filter by specific target gene ID"),
    # Phase 9.23: 添加 max_length 限制，防止 DoS 攻击
    mark_type: Optional[str] = Query(
        None,
        max_length=MAX_FIELD_LENGTH,
        description="Filter by mark type(s), comma-separated (max 20 items)"
    ),
    cell_type: Optional[str] = Query(
        None,
        max_length=MAX_FIELD_LENGTH,
        description="Filter by cell type(s), comma-separated (max 20 items)"
    ),
    chromosome: Optional[str] = Query(None, max_length=64, description="Filter by chromosome"),
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

    ## Performance Note
    For performance optimization, if no selective filters are provided (lncrna_gene_id, target_gene_id,
    chromosome, mark_type, cell_type, or min_binding_affinity > 0), the query defaults to chromosome='chr22'
    to prevent timeout.
    The response includes `default_filter_applied` and `effective_chromosome` fields to indicate this.

    **Caching:** Results are cached for 5 minutes.
    **Rate Limit:** 60 requests per minute per IP.
    """

    # If MV is available, large chromosome queries are safe to serve.
    use_materialized_view = check_materialized_view_exists(db)

    # Performance optimization: Check if any selective filter is provided
    # chr22 chosen as it's small enough for fast response (~9s) while having meaningful data (~87K overlaps)
    DEFAULT_CHROMOSOME = 'chr22'

    has_selective_filter = any([
        lncrna_gene_id,
        target_gene_id,
        chromosome,
        mark_type,
        cell_type,
        min_binding_affinity and min_binding_affinity > 0,
    ])

    # Apply default chromosome if no selective filter is provided
    effective_chromosome = chromosome or (DEFAULT_CHROMOSOME if not has_selective_filter else None)
    default_filter_applied = (effective_chromosome == DEFAULT_CHROMOSOME and not chromosome)

    if default_filter_applied:
        logger.info(f"Statistics: No selective filter provided, applying default chromosome='{DEFAULT_CHROMOSOME}' for performance")

    # Guard: even with a chromosome filter, chr1/chr2/chr3 can still be too broad without MV.
    # Require at least one additional narrowing filter, otherwise fail fast with a clear message.
    if not use_materialized_view and chromosome in LARGE_CHROMOSOMES_NO_MV_GUARD:
        has_narrowing_filter = any([
            lncrna_gene_id,
            target_gene_id,
            mark_type,
            cell_type,
            min_binding_affinity and min_binding_affinity > 0,
        ])
        if not has_narrowing_filter:
            _raise_query_too_broad(
                chromosome,
                suggest_filters=[
                    "mark_type",
                    "cell_type",
                    "lncrna_gene_id",
                    "target_gene_id",
                    "min_binding_affinity",
                ],
            )

    # Phase 9.23: 使用统一的 parse_comma_list 验证，防止 DoS 攻击
    mark_types_array = parse_comma_list(mark_type, param_name="mark_type")
    cell_types_array = parse_comma_list(cell_type, param_name="cell_type")

    p = table(
        "chipseq_peaks_human",
        column("peak_id"),
        column("species_id"),
        column("chromosome"),
        column("peak_start"),
        column("peak_end"),
        column("experiment_id"),
        column("fold_enrichment"),
        column("qvalue"),
    )
    overlap_start_base = func.greatest(Regulation.best_peak_start, p.c.peak_start)
    overlap_end_base = func.least(Regulation.best_peak_end, p.c.peak_end)
    overlap_length_base = overlap_end_base - overlap_start_base

    filter_conditions, params = _build_overlap_where_and_params(
        lncrna_gene_id=lncrna_gene_id,
        target_gene_id=target_gene_id,
        chromosome=effective_chromosome,
        mark_types=mark_types_array,
        cell_types=cell_types_array,
        min_binding_affinity=min_binding_affinity,
        min_peak_strength=None,
        max_qvalue=max_qvalue,
        min_overlap_length=None,
        lncrna_gene_col=Regulation.lncrna_gene_id,
        target_gene_col=Regulation.target_gene_id,
        chromosome_col=Regulation.best_peak_chr,
        mark_name_col=EpigeneticMarkType.mark_name,
        cell_type_col=ChIPSeqExperiment.cell_type,
        binding_affinity_col=Regulation.binding_affinity,
        fold_enrichment_col=p.c.fold_enrichment,
        qvalue_col=p.c.qvalue,
        overlap_length_expr=overlap_length_base,
    )
    where_conditions = [Regulation.species_id == 1, ChIPSeqExperiment.is_active.is_(True), *filter_conditions]
    join_on_peak = (
        (Regulation.species_id == p.c.species_id)
        & (Regulation.best_peak_chr == p.c.chromosome)
        & (Regulation.best_peak_start < p.c.peak_end)
        & (Regulation.best_peak_end > p.c.peak_start)
    )

    stats_stmt = (
        select(
            func.count().label("total_overlaps"),
            func.count(func.distinct(Regulation.lncrna_gene_id)).label("unique_lncrnas"),
            func.count(func.distinct(Regulation.target_gene_id)).label("unique_target_genes"),
            func.count(func.distinct(EpigeneticMarkType.mark_name)).label("unique_marks"),
            func.count(func.distinct(ChIPSeqExperiment.cell_type)).label("unique_cell_types"),
            func.avg(overlap_length_base).label("avg_overlap_length"),
            func.avg(Regulation.binding_affinity).label("avg_binding_affinity"),
            func.avg(p.c.fold_enrichment).label("avg_peak_strength"),
        )
        .select_from(Regulation)
        .join(p, join_on_peak)
        .join(ChIPSeqExperiment, p.c.experiment_id == ChIPSeqExperiment.experiment_id)
        .join(EpigeneticMarkType, ChIPSeqExperiment.mark_type_id == EpigeneticMarkType.mark_type_id)
        .where(*where_conditions)
    )

    by_mark_stmt = (
        select(
            EpigeneticMarkType.mark_name.label("mark_type"),
            func.count().label("count"),
            func.avg(Regulation.binding_affinity).label("avg_strength"),
        )
        .select_from(Regulation)
        .join(p, join_on_peak)
        .join(ChIPSeqExperiment, p.c.experiment_id == ChIPSeqExperiment.experiment_id)
        .join(EpigeneticMarkType, ChIPSeqExperiment.mark_type_id == EpigeneticMarkType.mark_type_id)
        .where(*where_conditions)
        .group_by(EpigeneticMarkType.mark_name)
        .order_by(func.count().desc())
    )

    by_cell_stmt = (
        select(
            ChIPSeqExperiment.cell_type,
            func.count().label("count"),
        )
        .select_from(Regulation)
        .join(p, join_on_peak)
        .join(ChIPSeqExperiment, p.c.experiment_id == ChIPSeqExperiment.experiment_id)
        .join(EpigeneticMarkType, ChIPSeqExperiment.mark_type_id == EpigeneticMarkType.mark_type_id)
        .where(*where_conditions)
        .group_by(ChIPSeqExperiment.cell_type)
        .order_by(func.count().desc())
    )

    try:
        # Execute main statistics query
        result = db.execute(stats_stmt, params).fetchone()

        if not result or result.total_overlaps == 0:
            return OverlapStatistics(
                total_overlaps=0,
                unique_lncrnas=0,
                unique_target_genes=0,
                unique_cell_types=0,
                unique_marks=0,
                avg_overlap_length=0.0,
                avg_binding_affinity=0.0,
                avg_peak_strength=0.0,
                by_mark_type=[],
                by_cell_type=[],
                default_filter_applied=default_filter_applied,
                effective_chromosome=effective_chromosome
            )

        # Execute by_mark_type query
        mark_results = db.execute(by_mark_stmt, params).fetchall()
        by_mark_type = [
            MarkTypeStats(
                mark_type=row.mark_type,
                count=row.count,
                avg_strength=float(row.avg_strength) if row.avg_strength else 0.0
            )
            for row in mark_results
        ]

        # Execute by_cell_type query
        cell_results = db.execute(by_cell_stmt, params).fetchall()
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
            unique_target_genes=result.unique_target_genes,
            unique_cell_types=result.unique_cell_types,
            unique_marks=result.unique_marks,
            avg_overlap_length=float(result.avg_overlap_length) if result.avg_overlap_length else 0.0,
            avg_binding_affinity=float(result.avg_binding_affinity) if result.avg_binding_affinity else 0.0,
            avg_peak_strength=float(result.avg_peak_strength) if result.avg_peak_strength else 0.0,
            by_mark_type=by_mark_type,
            by_cell_type=by_cell_type,
            default_filter_applied=default_filter_applied,
            effective_chromosome=effective_chromosome
        )

    except Exception as e:
        raise sanitize_db_error(e, logger)


@router.get("/summary", response_model=OverlapStatistics, include_in_schema=False)
@rate_limit("60/minute")
@cached("overlap:summary", ttl=cache.TTL_LIST)
def get_overlap_summary(
    request: Request,
    lncrna_gene_id: Optional[int] = Query(None, description="Filter by specific lncRNA gene ID"),
    target_gene_id: Optional[int] = Query(None, description="Filter by specific target gene ID"),
    mark_type: Optional[str] = Query(None, max_length=MAX_FIELD_LENGTH, description="Filter by mark type(s), comma-separated"),
    cell_type: Optional[str] = Query(None, max_length=MAX_FIELD_LENGTH, description="Filter by cell type(s), comma-separated"),
    chromosome: Optional[str] = Query(None, max_length=64, description="Filter by chromosome"),
    min_binding_affinity: Optional[float] = Query(None, ge=0, description="Minimum binding affinity"),
    min_overlap_length: Optional[int] = Query(None, ge=1, description="Minimum overlap length in bp"),
    min_peak_strength: Optional[float] = Query(None, ge=0, description="Minimum peak fold enrichment"),
    max_qvalue: Optional[float] = Query(0.05, ge=0, le=1, description="Maximum Q-value"),
    db: Session = Depends(get_db),
):
    """Alias for /statistics endpoint for backwards compatibility"""
    return get_overlap_statistics(
        request=request,
        lncrna_gene_id=lncrna_gene_id,
        target_gene_id=target_gene_id,
        mark_type=mark_type,
        cell_type=cell_type,
        chromosome=chromosome,
        min_binding_affinity=min_binding_affinity,
        max_qvalue=max_qvalue,
        db=db,
    )


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
    chromosome: Optional[str] = Query(None, max_length=64, description="Filter by chromosome (e.g., 'chr1')"),
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

    ## Performance Note
    For performance optimization, if no chromosome or min_binding_affinity filter is provided,
    the query defaults to chromosome='chr22' to prevent timeout on the full spatial join.
    The response includes `default_filter_applied` and `effective_chromosome` fields to indicate this.
    """

    # If MV is available, large chromosome queries are safe to serve.
    use_materialized_view = check_materialized_view_exists(db)

    # Guard: even with a chromosome filter, chr1/chr2/chr3 can still be too broad without MV.
    # Require at least one additional narrowing filter, otherwise fail fast with a clear message.
    if not use_materialized_view and chromosome in LARGE_CHROMOSOMES_NO_MV_GUARD:
        has_narrowing_filter = bool(min_binding_affinity and min_binding_affinity > 0)
        if not has_narrowing_filter:
            _raise_query_too_broad(
                chromosome,
                suggest_filters=[
                    "min_binding_affinity",
                ],
            )

    # Performance optimization: Check if any selective filter is provided
    # chr22 chosen as it's small enough for fast response (~9s) while having meaningful data (~87K overlaps)
    DEFAULT_CHROMOSOME = 'chr22'

    has_selective_filter = any([
        chromosome,
        min_binding_affinity and min_binding_affinity > 0,
    ])

    # Apply default chromosome if no selective filter is provided
    effective_chromosome = chromosome or (DEFAULT_CHROMOSOME if not has_selective_filter else None)
    default_filter_applied = (effective_chromosome == DEFAULT_CHROMOSOME and not chromosome)

    if default_filter_applied:
        logger.info(f"Heatmap: No selective filter provided, applying default chromosome='{DEFAULT_CHROMOSOME}' for performance")

    # SECURITY: All dimension/metric selectors use whitelisted SQLAlchemy expressions only.
    # User input (x_axis, y_axis, metric) is validated against these maps.
    p = table(
        "chipseq_peaks_human",
        column("peak_id"),
        column("species_id"),
        column("chromosome"),
        column("peak_start"),
        column("peak_end"),
        column("experiment_id"),
        column("fold_enrichment"),
        column("qvalue"),
    )
    join_on_peak = (
        (Regulation.species_id == p.c.species_id)
        & (Regulation.best_peak_chr == p.c.chromosome)
        & (Regulation.best_peak_start < p.c.peak_end)
        & (Regulation.best_peak_end > p.c.peak_start)
    )
    overlap_length_base = func.least(Regulation.best_peak_end, p.c.peak_end) - func.greatest(
        Regulation.best_peak_start, p.c.peak_start
    )

    x_axis_map = {
        "mark_type": EpigeneticMarkType.mark_name,
        "cell_type": ChIPSeqExperiment.cell_type,
    }
    x_expr = x_axis_map[x_axis]

    lnc = aliased(Gene)
    tgt = aliased(Gene)
    if y_axis == "lncrna":
        y_expr = lnc.gene_name
        y_join_on = Regulation.lncrna_gene_id == lnc.gene_id
    else:  # y_axis == "target_gene"
        y_expr = tgt.gene_name
        y_join_on = Regulation.target_gene_id == tgt.gene_id

    metric_map = {
        "count": func.count(),
        "avg_binding_affinity": func.avg(Regulation.binding_affinity),
        "total_overlap_length": func.sum(overlap_length_base),
    }
    metric_expr = metric_map[metric]

    filter_conditions, filter_params = _build_overlap_where_and_params(
        lncrna_gene_id=None,
        target_gene_id=None,
        chromosome=effective_chromosome,
        mark_types=None,
        cell_types=None,
        min_binding_affinity=min_binding_affinity,
        min_peak_strength=None,
        max_qvalue=max_qvalue,
        min_overlap_length=None,
        lncrna_gene_col=Regulation.lncrna_gene_id,
        target_gene_col=Regulation.target_gene_id,
        chromosome_col=Regulation.best_peak_chr,
        mark_name_col=EpigeneticMarkType.mark_name,
        cell_type_col=ChIPSeqExperiment.cell_type,
        binding_affinity_col=Regulation.binding_affinity,
        fold_enrichment_col=p.c.fold_enrichment,
        qvalue_col=p.c.qvalue,
        overlap_length_expr=overlap_length_base,
    )

    where_conditions = [Regulation.species_id == 1, ChIPSeqExperiment.is_active.is_(True), *filter_conditions]
    params = {**filter_params, "top_n": top_n}

    try:
        # Step 1: Get all distinct X-axis values (ordered alphabetically)
        x_labels_stmt = (
            select(x_expr.label("x_value"))
            .select_from(Regulation)
            .join(p, join_on_peak)
            .join(ChIPSeqExperiment, p.c.experiment_id == ChIPSeqExperiment.experiment_id)
            .join(EpigeneticMarkType, ChIPSeqExperiment.mark_type_id == EpigeneticMarkType.mark_type_id)
            .where(*where_conditions)
            .distinct()
            .order_by(x_expr)
        )

        x_results = db.execute(x_labels_stmt, params).fetchall()
        x_labels = [row.x_value for row in x_results if row.x_value]

        if not x_labels:
            return OverlapHeatmapResponse(
                x_labels=[],
                y_labels=[],
                data=[],
                metric=metric,
                total_combinations=0,
                valid_combinations=0,
                default_filter_applied=default_filter_applied,
                effective_chromosome=effective_chromosome
            )

        # Step 2: Get top N Y-axis values (by total count across all X values)
        y_labels_stmt = (
            select(
                y_expr.label("y_value"),
                func.count().label("total_count"),
            )
            .select_from(Regulation)
            .join(lnc if y_axis == "lncrna" else tgt, y_join_on)
            .join(p, join_on_peak)
            .join(ChIPSeqExperiment, p.c.experiment_id == ChIPSeqExperiment.experiment_id)
            .join(EpigeneticMarkType, ChIPSeqExperiment.mark_type_id == EpigeneticMarkType.mark_type_id)
            .where(*where_conditions)
            .where(y_expr.is_not(None))
            .group_by(y_expr)
            .order_by(func.count().desc())
            .limit(bindparam("top_n"))
        )

        y_results = db.execute(y_labels_stmt, params).fetchall()
        y_labels = [row.y_value for row in y_results if row.y_value]

        if not y_labels:
            return OverlapHeatmapResponse(
                x_labels=x_labels,
                y_labels=[],
                data=[],
                metric=metric,
                total_combinations=0,
                valid_combinations=0,
                default_filter_applied=default_filter_applied,
                effective_chromosome=effective_chromosome
            )

        # Step 3: Get heatmap data for all X-Y combinations
        # Build the main aggregation query
        params["y_labels"] = y_labels
        heatmap_stmt = (
            select(
                x_expr.label("x_value"),
                y_expr.label("y_value"),
                metric_expr.label("metric_value"),
            )
            .select_from(Regulation)
            .join(lnc if y_axis == "lncrna" else tgt, y_join_on)
            .join(p, join_on_peak)
            .join(ChIPSeqExperiment, p.c.experiment_id == ChIPSeqExperiment.experiment_id)
            .join(EpigeneticMarkType, ChIPSeqExperiment.mark_type_id == EpigeneticMarkType.mark_type_id)
            .where(*where_conditions)
            .where(y_expr.in_(bindparam("y_labels", expanding=True)))
            .group_by(x_expr, y_expr)
            .order_by(x_expr, y_expr)
        )

        heatmap_results = db.execute(heatmap_stmt, params).fetchall()

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
            valid_combinations=valid_combinations,
            default_filter_applied=default_filter_applied,
            effective_chromosome=effective_chromosome
        )

    except Exception as e:
        raise sanitize_db_error(e, logger)


# =============================================================================
# Export Helper Functions
# =============================================================================

def format_bed_row(row: dict) -> str:
    """
    Format a single overlap row as BED6 format line.

    BED6 format: chrom, chromStart, chromEnd, name, score, strand
    - chrom: chromosome name (e.g., chr22)
    - chromStart: 0-based start position (overlap_start)
    - chromEnd: 0-based end position (overlap_end)
    - name: {lncrna_name}_{target_gene_name}_{mark_type}
    - score: binding_affinity * 10, clamped to 0-1000
    - strand: '.' (unknown/unstranded)

    Args:
        row: Dictionary containing overlap data

    Returns:
        BED6 formatted line with newline
    """
    chrom = row.get('chromosome', 'chr?')
    start = row.get('overlap_start', 0)
    end = row.get('overlap_end', 0)

    # Build name: lncrna_target_mark
    lncrna = row.get('lncrna_name', 'unknown')
    target = row.get('target_gene_name', 'unknown')
    mark = row.get('mark_type', 'unknown')
    name = sanitize_bed_field(f"{lncrna}_{target}_{mark}")

    # Convert binding_affinity (0-100 scale) to BED score (0-1000)
    binding_affinity = float(row.get('binding_affinity', 0))
    score = min(1000, max(0, int(binding_affinity * 10)))

    # Strand is unknown for ChIP-seq peaks
    strand = '.'

    return f"{chrom}\t{start}\t{end}\t{name}\t{score}\t{strand}\n"


def format_csv_row(row: dict) -> str:
    """
    Format a single overlap row as CSV line.

    Uses CSV_EXPORT_COLUMNS order (19 columns total).

    Args:
        row: Dictionary containing overlap data

    Returns:
        CSV formatted line with newline
    """
    # Extract values in column order
    values = []
    for col in CSV_EXPORT_COLUMNS:
        raw_value = row.get(col)
        # Convert None to empty string
        if raw_value is None:
            values.append('')
            continue

        # SECURITY: CSV 公式注入防护（仅对字符串做前缀转义，数值类型保持原样）
        safe_value = sanitize_csv_value(raw_value)
        values.append(str(safe_value))

    # Use StringIO and csv.writer for proper CSV escaping
    output = StringIO()
    writer = csv.writer(output)
    writer.writerow(values)
    return output.getvalue()


def generate_overlap_export(
    db: Session,
    format: Literal['bed', 'csv'],
    lncrna_gene_id: Optional[int] = None,
    target_gene_id: Optional[int] = None,
    mark_type: Optional[str] = None,
    cell_type: Optional[str] = None,
    chromosome: Optional[str] = None,
    min_overlap_length: Optional[int] = None,
    min_binding_affinity: Optional[float] = None,
    min_peak_strength: Optional[float] = None,
    max_qvalue: Optional[float] = 0.05,
    max_rows: int = MAX_EXPORT_ROWS,
    use_materialized_view: bool | None = None,
) -> Generator[str, None, None]:
    """
    Generate streaming export of lncRNA-ChIP-seq overlaps in BED or CSV format.

    Yields data in batches to support large result sets without memory issues.

    Args:
        db: Database session
        format: Export format ('bed' or 'csv')
        All filter parameters: Same as main query endpoint
        max_rows: Maximum rows to export (default: 100,000)

    Yields:
        Formatted lines (BED6 or CSV) as strings
    """

    # Performance optimization: Apply default chromosome if no selective filter
    has_selective_filter = any([
        lncrna_gene_id,
        target_gene_id,
        chromosome,
        mark_type,
        cell_type,
        min_binding_affinity and min_binding_affinity > 0,
    ])

    effective_chromosome = chromosome or (DEFAULT_EXPORT_CHROMOSOME if not has_selective_filter else None)

    if not has_selective_filter:
        logger.info(f"Export: No selective filter provided, applying default chromosome='{DEFAULT_EXPORT_CHROMOSOME}'")

    # Yield header
    if format == 'bed':
        # BED track header (optional but recommended)
        yield 'track name="lncRNA-ChIPseq-Overlap" description="lncRNA binding sites overlapping with ChIP-seq peaks" useScore=1\n'
    elif format == 'csv':
        # CSV header row
        yield format_csv_row({col: col for col in CSV_EXPORT_COLUMNS})

    # Phase 9.23: 使用统一的 parse_comma_list 验证，防止 DoS 攻击
    mark_types_array = parse_comma_list(mark_type, param_name="mark_type")
    cell_types_array = parse_comma_list(cell_type, param_name="cell_type")

    if use_materialized_view is None:
        use_materialized_view = check_materialized_view_exists(db)

    if use_materialized_view:
        mv = table(
            MV_LNCRNA_CHIPSEQ_OVERLAPS,
            column("overlap_id"),
            column("regulation_id"),
            column("lncrna_gene_id"),
            column("lncrna_name"),
            column("target_gene_id"),
            column("target_gene_name"),
            column("mark_name"),
            column("mark_category"),
            column("cell_type"),
            column("chromosome"),
            column("lncrna_binding_start"),
            column("lncrna_binding_end"),
            column("peak_start"),
            column("peak_end"),
            column("overlap_start"),
            column("overlap_end"),
            column("overlap_length"),
            column("binding_affinity"),
            column("fold_enrichment"),
            column("qvalue"),
        )

        filter_conditions, params = _build_overlap_where_and_params(
            lncrna_gene_id=lncrna_gene_id,
            target_gene_id=target_gene_id,
            chromosome=effective_chromosome,
            mark_types=mark_types_array,
            cell_types=cell_types_array,
            min_binding_affinity=min_binding_affinity,
            min_peak_strength=min_peak_strength,
            max_qvalue=max_qvalue,
            min_overlap_length=min_overlap_length,
            lncrna_gene_col=mv.c.lncrna_gene_id,
            target_gene_col=mv.c.target_gene_id,
            chromosome_col=mv.c.chromosome,
            mark_name_col=mv.c.mark_name,
            cell_type_col=mv.c.cell_type,
            binding_affinity_col=mv.c.binding_affinity,
            fold_enrichment_col=mv.c.fold_enrichment,
            qvalue_col=mv.c.qvalue,
            overlap_length_expr=mv.c.overlap_length,
        )

        data_stmt = (
            select(
                mv.c.overlap_id,
                mv.c.regulation_id,
                mv.c.lncrna_gene_id,
                mv.c.lncrna_name,
                mv.c.target_gene_id,
                mv.c.target_gene_name,
                mv.c.mark_name.label("mark_type"),
                mv.c.mark_category,
                mv.c.cell_type,
                mv.c.chromosome,
                mv.c.lncrna_binding_start,
                mv.c.lncrna_binding_end,
                mv.c.peak_start,
                mv.c.peak_end,
                mv.c.overlap_start,
                mv.c.overlap_end,
                mv.c.overlap_length,
                mv.c.binding_affinity,
                mv.c.fold_enrichment.label("peak_fold_enrichment"),
                mv.c.qvalue.label("peak_qvalue"),
            )
            .select_from(mv)
            .order_by(mv.c.chromosome, mv.c.overlap_start)
            .limit(bindparam("limit"))
        )
        if filter_conditions:
            data_stmt = data_stmt.where(*filter_conditions)

    else:
        p = table(
            "chipseq_peaks_human",
            column("peak_id"),
            column("species_id"),
            column("chromosome"),
            column("peak_start"),
            column("peak_end"),
            column("experiment_id"),
            column("fold_enrichment"),
            column("qvalue"),
        )
        overlap_start_base = func.greatest(Regulation.best_peak_start, p.c.peak_start)
        overlap_end_base = func.least(Regulation.best_peak_end, p.c.peak_end)
        overlap_start_expr = overlap_start_base.label("overlap_start")
        overlap_end_expr = overlap_end_base.label("overlap_end")
        overlap_length_expr = (overlap_end_base - overlap_start_base).label("overlap_length")

        filter_conditions, params = _build_overlap_where_and_params(
            lncrna_gene_id=lncrna_gene_id,
            target_gene_id=target_gene_id,
            chromosome=effective_chromosome,
            mark_types=mark_types_array,
            cell_types=cell_types_array,
            min_binding_affinity=min_binding_affinity,
            min_peak_strength=min_peak_strength,
            max_qvalue=max_qvalue,
            min_overlap_length=min_overlap_length,
            lncrna_gene_col=Regulation.lncrna_gene_id,
            target_gene_col=Regulation.target_gene_id,
            chromosome_col=Regulation.best_peak_chr,
            mark_name_col=EpigeneticMarkType.mark_name,
            cell_type_col=ChIPSeqExperiment.cell_type,
            binding_affinity_col=Regulation.binding_affinity,
            fold_enrichment_col=p.c.fold_enrichment,
            qvalue_col=p.c.qvalue,
            overlap_length_expr=overlap_length_expr,
        )

        where_conditions = [Regulation.species_id == 1, ChIPSeqExperiment.is_active.is_(True), *filter_conditions]
        join_on_peak = (
            (Regulation.species_id == p.c.species_id)
            & (Regulation.best_peak_chr == p.c.chromosome)
            & (Regulation.best_peak_start < p.c.peak_end)
            & (Regulation.best_peak_end > p.c.peak_start)
        )
        lnc = aliased(Gene)
        tgt = aliased(Gene)
        data_stmt = (
            select(
                func.concat(literal("reg_"), Regulation.regulation_id, literal("_peak_"), p.c.peak_id).label("overlap_id"),
                Regulation.regulation_id,
                Regulation.lncrna_gene_id,
                lnc.gene_name.label("lncrna_name"),
                Regulation.target_gene_id,
                tgt.gene_name.label("target_gene_name"),
                EpigeneticMarkType.mark_name.label("mark_type"),
                EpigeneticMarkType.mark_category,
                ChIPSeqExperiment.cell_type,
                Regulation.best_peak_chr.label("chromosome"),
                Regulation.best_peak_start.label("lncrna_binding_start"),
                Regulation.best_peak_end.label("lncrna_binding_end"),
                p.c.peak_start,
                p.c.peak_end,
                overlap_start_expr,
                overlap_end_expr,
                overlap_length_expr,
                Regulation.binding_affinity,
                p.c.fold_enrichment.label("peak_fold_enrichment"),
                p.c.qvalue.label("peak_qvalue"),
            )
            .select_from(Regulation)
            .join(lnc, Regulation.lncrna_gene_id == lnc.gene_id)
            .join(tgt, Regulation.target_gene_id == tgt.gene_id)
            .join(p, join_on_peak)
            .join(ChIPSeqExperiment, p.c.experiment_id == ChIPSeqExperiment.experiment_id)
            .join(EpigeneticMarkType, ChIPSeqExperiment.mark_type_id == EpigeneticMarkType.mark_type_id)
            .where(*where_conditions)
            .order_by(Regulation.best_peak_chr, overlap_start_expr)
            .limit(bindparam("limit"))
        )

    # Stream data in batches
    batch_size = EXPORT_BATCH_SIZE
    rows_exported = 0

    result = None
    close_result = None
    try:
        executable = data_stmt.execution_options(stream_results=True)
        result = db.execute(executable, {**params, "limit": max_rows})
        close_result = getattr(result, "close", None)

        while rows_exported < max_rows:
            batch_limit = min(batch_size, max_rows - rows_exported)
            batch = result.fetchmany(batch_limit)
            if not batch:
                break

            for row in batch:
                if rows_exported >= max_rows:
                    break

                row_dict = {
                    'overlap_id': row.overlap_id,
                    'regulation_id': row.regulation_id,
                    'lncrna_gene_id': row.lncrna_gene_id,
                    'lncrna_name': row.lncrna_name,
                    'target_gene_id': row.target_gene_id,
                    'target_gene_name': row.target_gene_name,
                    'mark_type': row.mark_type,
                    'mark_category': row.mark_category,
                    'cell_type': row.cell_type,
                    'chromosome': row.chromosome,
                    'lncrna_binding_start': row.lncrna_binding_start,
                    'lncrna_binding_end': row.lncrna_binding_end,
                    'peak_start': row.peak_start,
                    'peak_end': row.peak_end,
                    'overlap_start': row.overlap_start,
                    'overlap_end': row.overlap_end,
                    'overlap_length': row.overlap_length,
                    'binding_affinity': row.binding_affinity,
                    'peak_fold_enrichment': row.peak_fold_enrichment,
                    'peak_qvalue': row.peak_qvalue
                }

                if format == 'bed':
                    yield format_bed_row(row_dict)
                elif format == 'csv':
                    yield format_csv_row(row_dict)

                rows_exported += 1

    except Exception as e:
        logger.error(
            "Error during export generation: %s",
            sanitize_for_log(e, max_length=2000),
            exc_info=True,
        )
        raise
    finally:
        if callable(close_result):
            close_result()


# =============================================================================
# Export Endpoint
# =============================================================================

@router.get("/export")
@rate_limit("5/minute")  # Rate limit: 5 requests per minute per IP
def export_lncrna_chipseq_overlaps(
    request: Request,  # Required for rate limiting
    format: Literal['bed', 'csv'] = Query('bed', description="Export format: 'bed' (BED6) or 'csv'"),
    lncrna_gene_id: Optional[int] = Query(None, description="Filter by specific lncRNA gene ID"),
    target_gene_id: Optional[int] = Query(None, description="Filter by specific target gene ID"),
    # Phase 9.23: 添加 max_length 限制，防止 DoS 攻击
    mark_type: Optional[str] = Query(
        None,
        max_length=MAX_FIELD_LENGTH,
        description="Filter by mark type(s), comma-separated (e.g., 'H3K27me3,H3K4me3', max 20 items)"
    ),
    cell_type: Optional[str] = Query(
        None,
        max_length=MAX_FIELD_LENGTH,
        description="Filter by cell type(s), comma-separated (e.g., 'K562,GM12878', max 20 items)"
    ),
    chromosome: Optional[str] = Query(None, max_length=64, description="Filter by chromosome (e.g., 'chr1')"),
    min_overlap_length: Optional[int] = Query(None, ge=1, description="Minimum overlap length in bp"),
    min_binding_affinity: Optional[float] = Query(None, ge=0, description="Minimum binding affinity score"),
    min_peak_strength: Optional[float] = Query(None, ge=0, description="Minimum peak fold enrichment"),
    max_qvalue: Optional[float] = Query(0.05, ge=0, le=1, description="Maximum Q-value (FDR) for peaks"),
    max_rows: int = Query(MAX_EXPORT_ROWS, ge=1, le=MAX_EXPORT_ROWS, description=f"Maximum rows to export (max: {MAX_EXPORT_ROWS})"),
    db: Session = Depends(get_db)
):
    """
    Export lncRNA-ChIP-seq overlaps in BED6 or CSV format.

    ## Overview

    This endpoint exports overlap data between lncRNA binding sites and ChIP-seq peaks
    in standard genomic file formats for downstream analysis and visualization.

    **Supported Formats:**
    - **BED6**: Standard genomic interval format (6 columns: chr, start, end, name, score, strand)
    - **CSV**: Full data export with all 19 columns from OverlapResult schema

    ## Performance & Limits

    - **Rate Limit**: 5 requests per minute per IP
    - **Max Rows**: 100,000 per export (configurable via max_rows parameter)
    - **Streaming**: Large exports are streamed in batches (1000 rows/batch) to minimize memory usage
    - **Default Filter**: If no selective filters are provided (lncrna_gene_id, target_gene_id,
      chromosome, or min_binding_affinity > 0), the query defaults to chromosome='chr22' to prevent timeout

    ## BED6 Format

    Standard BED format with 6 tab-separated columns:

    1. **chrom**: Chromosome (e.g., chr22)
    2. **chromStart**: Overlap start position (0-based)
    3. **chromEnd**: Overlap end position (0-based, exclusive)
    4. **name**: Feature name format: `{lncrna_name}_{target_gene_name}_{mark_type}`
    5. **score**: Binding affinity scaled to 0-1000 (binding_affinity * 10)
    6. **strand**: Always '.' (ChIP-seq peaks are unstranded)

    **Example BED6 output:**
    ```
    track name="lncRNA-ChIPseq-Overlap" description="lncRNA binding sites overlapping with ChIP-seq peaks" useScore=1
    chr22   10518945   10519856   ENSG00000224116_ENSG00000100316   850   .
    chr22   10520010   10520455   ENSG00000224116_ENSG00000100316   850   .
    ```

    ## CSV Format

    Full data export with 19 columns (all fields from OverlapResult schema):

    - Identifiers: overlap_id
    - Coordinates: chromosome, overlap_start, overlap_end, overlap_length
    - Genes: lncrna_gene_id, lncrna_name, target_gene_id, target_gene_name
    - ChIP-seq: mark_type, mark_category, cell_type
    - Metrics: binding_affinity, peak_fold_enrichment, peak_qvalue
    - Binding site: lncrna_binding_start, lncrna_binding_end
    - Peak: peak_start, peak_end

    ## Parameters

    All filters from the main query endpoint are supported:
    - **format**: Export format ('bed' or 'csv'), default: 'bed'
    - **lncrna_gene_id**: Filter by lncRNA gene ID
    - **target_gene_id**: Filter by target gene ID
    - **mark_type**: Filter by epigenetic mark(s), comma-separated
    - **cell_type**: Filter by cell type(s), comma-separated
    - **chromosome**: Filter by chromosome
    - **min_overlap_length**: Minimum overlap length in bp
    - **min_binding_affinity**: Minimum binding affinity score
    - **min_peak_strength**: Minimum peak fold enrichment
    - **max_qvalue**: Maximum Q-value (FDR), default: 0.05
    - **max_rows**: Maximum rows to export, default: 100,000

    ## Examples

    ```bash
    # Export chr22 overlaps as BED6
    curl "http://localhost:8000/api/v1/lncrna-chipseq-overlap/export?format=bed&chromosome=chr22" -o overlaps_chr22.bed

    # Export H3K27me3 overlaps as CSV
    curl "http://localhost:8000/api/v1/lncrna-chipseq-overlap/export?format=csv&mark_type=H3K27me3&chromosome=chr22" -o overlaps_H3K27me3.csv

    # Export high-affinity overlaps (limit to 10,000 rows)
    curl "http://localhost:8000/api/v1/lncrna-chipseq-overlap/export?format=csv&min_binding_affinity=80&max_rows=10000" -o overlaps_high_affinity.csv
    ```

    ## Returns

    StreamingResponse with appropriate Content-Type and Content-Disposition headers for file download.
    """

    # Validate format
    if format not in ['bed', 'csv']:
        raise HTTPException(status_code=400, detail="format must be 'bed' or 'csv'")

    # If MV is available, large chromosome exports are safe to serve.
    use_materialized_view = check_materialized_view_exists(db)

    # Guard: even with a chromosome filter, chr1/chr2/chr3 can still be too broad without MV.
    # Require at least one additional narrowing filter, otherwise fail fast with a clear message.
    if not use_materialized_view and chromosome in LARGE_CHROMOSOMES_NO_MV_GUARD:
        has_narrowing_filter = any([
            lncrna_gene_id,
            target_gene_id,
            mark_type,
            cell_type,
            min_overlap_length,
            min_peak_strength and min_peak_strength > 0,
            min_binding_affinity and min_binding_affinity > 0,
        ])
        if not has_narrowing_filter:
            _raise_query_too_broad(
                chromosome,
                suggest_filters=[
                    "mark_type",
                    "cell_type",
                    "lncrna_gene_id",
                    "target_gene_id",
                    "min_binding_affinity",
                    "min_peak_strength",
                    "min_overlap_length",
                ],
            )

    logger.info(
        f"Export requested: format={format}, chromosome={chromosome}, "
        f"mark_type={mark_type}, cell_type={cell_type}, max_rows={max_rows}"
    )

    # Generate export stream
    export_stream = generate_overlap_export(
        db=db,
        format=format,
        lncrna_gene_id=lncrna_gene_id,
        target_gene_id=target_gene_id,
        mark_type=mark_type,
        cell_type=cell_type,
        chromosome=chromosome,
        min_overlap_length=min_overlap_length,
        min_binding_affinity=min_binding_affinity,
        min_peak_strength=min_peak_strength,
        max_qvalue=max_qvalue,
        max_rows=max_rows,
        use_materialized_view=use_materialized_view,
    )

    # Build filename
    filename_parts = ["lncrna_chipseq_overlap"]

    if chromosome:
        filename_parts.append(chromosome)
    if mark_type:
        # Clean up comma-separated values for filename
        mark_clean = mark_type.replace(',', '_')
        filename_parts.append(mark_clean)
    if cell_type:
        cell_clean = cell_type.replace(',', '_')
        filename_parts.append(cell_clean)

    filename = "_".join(filename_parts)

    # Add extension
    if format == 'bed':
        filename += ".bed"
        media_type = "text/plain"
    else:  # csv
        filename += ".csv"
        media_type = "text/csv"

    # Return streaming response
    return StreamingResponse(
        export_stream,
        media_type=media_type,
        headers={
            # SECURITY: 防止 CRLF 注入/响应拆分，统一使用安全的 Content-Disposition 构造
            "Content-Disposition": content_disposition_attachment(filename),
            "Content-Type": f"{media_type}; charset=utf-8",
        }
    )
