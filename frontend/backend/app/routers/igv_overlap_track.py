"""
IGV Overlap Track 路由

提供 lncRNA 调控位点与 ChIP-seq 峰的重叠（overlap）轨道数据，用于 IGV.js webservice track。

设计目标：
- 与 IGV.js 常用参数对齐：支持 `chr`（标准）与 `chromosome`（别名）
- 强校验：缺失 chr/chromosome、start/end 非法、区域过大直接返回 400
- 输出格式：BED6（chr, start, end, name, score, strand），Content-Type=text/plain
- 性能：优先使用物化视图 `mv_lncrna_chipseq_overlaps`，避免大表 join
"""

from __future__ import annotations

import logging
from typing import Optional, Generator

from fastapi import APIRouter, Depends, HTTPException, Query, Request
from fastapi.responses import StreamingResponse
from sqlalchemy import bindparam, column, func, select, table
from sqlalchemy.orm import Session, aliased

from app.routers.chipseq_rate_limit import rate_limit

from app.core.database import get_db
from app.core.exceptions import sanitize_db_error
from app.core.mv_cache import mv_cache, is_mv_missing_error  # Phase 9.24: Thread-safe MV cache
from app.utils.bed import sanitize_bed_field
from app.models import Regulation, Gene, ChIPSeqExperiment, EpigeneticMarkType

logger = logging.getLogger(__name__)

router = APIRouter()

# 10Mb 以内允许 IGV 区域查询，避免拖垮数据库
MAX_REGION_SIZE_BP = 10_000_000

# 轨道返回上限：IGV 前端通常不需要一次加载过多特征
DEFAULT_LIMIT = 50_000
MAX_LIMIT = 200_000

# overlap 物化视图名称（由后端 SQL/ETL 构建）
MV_LNCRNA_CHIPSEQ_OVERLAPS = "mv_lncrna_chipseq_overlaps"

# Phase 9.24: MV cache moved to app.core.mv_cache for thread-safety and code reuse
# Old module-level cache and check functions removed (see mv_cache.py)


def reset_mv_cache():
    """
    重置 MV 可用性缓存。

    在创建/刷新 MV 后调用，强制下次查询重新检测。
    可通过 admin 端点触发。

    Phase 9.24: Delegates to centralized thread-safe cache.
    """
    mv_cache.reset()


def _check_mv_available(db: Session) -> bool:
    """
    检查 mv_lncrna_chipseq_overlaps 是否存在且已填充。

    仅 PostgreSQL 支持该检查；其他 dialect 直接视为不可用。
    Phase 9.12: 添加 TTL 支持，避免运行中创建 MV 后长期走 fallback。
    Phase 9.24: Delegates to centralized thread-safe cache.
    """
    return mv_cache.is_available(db)


def _normalize_chr(raw: str) -> str:
    """标准化染色体字符串：兼容 `1` -> `chr1`。"""
    value = raw.strip()
    if not value:
        return value
    if value.lower().startswith("chr"):
        return f"chr{value[3:]}"
    return f"chr{value}"


def _generate_overlap_bed6_stream(
    result,
) -> Generator[str, None, None]:
    """
    生成 overlap BED6 数据流。

    name 字段包含 mark_type，便于前端与测试做快速校验。

    Phase 9.24: Added MV error handling - auto-fallback if MV dropped during TTL.
    """
    close = getattr(result, "close", None)
    try:
        for row in result:
            chr_name = row.chromosome
            overlap_start = int(row.overlap_start)
            overlap_end = int(row.overlap_end)

            lncrna = row.lncrna_name or "unknown_lncRNA"
            target = row.target_gene_name or "unknown_target"
            mark = row.mark_type or "unknown_mark"
            cell_type = row.cell_type or "unknown_cell"

            # name: 保持简洁但包含 mark_type，满足 IGV 与测试场景
            name = sanitize_bed_field(f"{lncrna}->{target}|{mark}|{cell_type}")

            # score: 使用与 regulations BED 一致的 BA 缩放策略
            ba = float(row.binding_affinity) if row.binding_affinity else 0.0
            score = min(1000, max(0, int(ba * 10)))

            strand = "."
            yield f"{chr_name}\t{overlap_start}\t{overlap_end}\t{name}\t{score}\t{strand}\n"
    finally:
        if callable(close):
            close()


def _execute_overlap_query(
    db: Session,
    chromosome: str,
    start: int,
    end: int,
    *,
    mark_type: Optional[str],
    min_ba: Optional[float],
    limit: int,
):
    """
    执行 overlap 查询并返回可迭代 result。

    设计：
    - 在返回 StreamingResponse 之前完成 db.execute()，确保 DB 执行期错误可被标准化为 sanitize_db_error
    - 若 MV 在 TTL 窗口内被删除，自动 reset 缓存并回退到 join 查询
    """
    use_mv = _check_mv_available(db)

    is_postgresql = db.get_bind().dialect.name == "postgresql"
    bp_chromosome = bindparam("chromosome")
    bp_start = bindparam("start")
    bp_end = bindparam("end")
    bp_mark_type = bindparam("mark_type")
    bp_min_ba = bindparam("min_ba")
    bp_limit = bindparam("limit")

    mv = table(
        "mv_lncrna_chipseq_overlaps",
        column("chromosome"),
        column("overlap_start"),
        column("overlap_end"),
        column("lncrna_name"),
        column("target_gene_name"),
        column("mark_name"),
        column("cell_type"),
        column("binding_affinity"),
    )
    if is_postgresql:
        mv_region_predicate = (
            func.int8range(mv.c.overlap_start, mv.c.overlap_end, "[)")
            .op("&&")(func.int8range(bp_start, bp_end, "[)"))
        )
    else:
        mv_region_predicate = (mv.c.overlap_start < bp_end) & (mv.c.overlap_end > bp_start)

    mv_where_conditions = [
        mv.c.chromosome == bp_chromosome,
        mv_region_predicate,
    ]
    if mark_type is not None:
        mv_where_conditions.append(mv.c.mark_name == bp_mark_type)
    if min_ba is not None:
        mv_where_conditions.append(mv.c.binding_affinity >= bp_min_ba)

    mv_stmt = (
        select(
            mv.c.chromosome,
            mv.c.overlap_start,
            mv.c.overlap_end,
            mv.c.lncrna_name,
            mv.c.target_gene_name,
            mv.c.mark_name.label("mark_type"),
            mv.c.cell_type,
            mv.c.binding_affinity,
        )
        .select_from(mv)
        .where(*mv_where_conditions)
        .order_by(mv.c.overlap_start)
        .limit(bp_limit)
    )

    # fallback：无 MV 时使用原始 join（仅在小窗口内使用，受 MAX_REGION_SIZE_BP 保护）
    p = table(
        "chipseq_peaks_human",
        column("species_id"),
        column("chromosome"),
        column("peak_start"),
        column("peak_end"),
        column("experiment_id"),
    )
    lnc = aliased(Gene)
    tgt = aliased(Gene)

    # 重要：必须同时限制 peak 与 region 重叠，否则会返回“peak 与 best_peak 相交但不在 region 内”的特征
    if is_postgresql:
        peak_region_predicate = (
            func.int8range(p.c.peak_start, p.c.peak_end, "[)")
            .op("&&")(func.int8range(bp_start, bp_end, "[)"))
        )
    else:
        peak_region_predicate = (p.c.peak_start < bp_end) & (p.c.peak_end > bp_start)

    fallback_where_conditions = [
        Regulation.species_id == 1,
        ChIPSeqExperiment.is_active.is_(True),
        Regulation.best_peak_chr == bp_chromosome,
        Regulation.best_peak_start < bp_end,
        Regulation.best_peak_end > bp_start,
        peak_region_predicate,
    ]
    if mark_type is not None:
        fallback_where_conditions.append(EpigeneticMarkType.mark_name == bp_mark_type)
    if min_ba is not None:
        fallback_where_conditions.append(Regulation.binding_affinity >= bp_min_ba)

    overlap_start_expr = func.greatest(Regulation.best_peak_start, p.c.peak_start).label("overlap_start")
    overlap_end_expr = func.least(Regulation.best_peak_end, p.c.peak_end).label("overlap_end")
    fallback_stmt = (
        select(
            Regulation.best_peak_chr.label("chromosome"),
            overlap_start_expr,
            overlap_end_expr,
            lnc.gene_name.label("lncrna_name"),
            tgt.gene_name.label("target_gene_name"),
            EpigeneticMarkType.mark_name.label("mark_type"),
            ChIPSeqExperiment.cell_type,
            Regulation.binding_affinity,
        )
        .select_from(Regulation)
        .join(lnc, Regulation.lncrna_gene_id == lnc.gene_id)
        .join(tgt, Regulation.target_gene_id == tgt.gene_id)
        .join(
            p,
            (Regulation.species_id == p.c.species_id)
            & (Regulation.best_peak_chr == p.c.chromosome)
            & (Regulation.best_peak_start < p.c.peak_end)
            & (Regulation.best_peak_end > p.c.peak_start),
        )
        .join(ChIPSeqExperiment, p.c.experiment_id == ChIPSeqExperiment.experiment_id)
        .join(EpigeneticMarkType, ChIPSeqExperiment.mark_type_id == EpigeneticMarkType.mark_type_id)
        .where(*fallback_where_conditions)
        .order_by(overlap_start_expr)
        .limit(bp_limit)
    )

    params = {
        "chromosome": chromosome,
        "start": start,
        "end": end,
        "mark_type": mark_type,
        "min_ba": min_ba,
        "limit": limit,
    }

    sql = mv_stmt if use_mv else fallback_stmt
    try:
        return db.execute(sql.execution_options(stream_results=True), params)
    except Exception as e:
        if use_mv and is_mv_missing_error(e):
            logger.warning(f"MV query failed (MV may have been dropped), falling back to join query: {e}")
            mv_cache.reset()
            try:
                return db.execute(fallback_stmt.execution_options(stream_results=True), params)
            except Exception as fallback_error:
                raise sanitize_db_error(fallback_error, logger)
        raise sanitize_db_error(e, logger)


@router.get("/overlap-track")
@rate_limit("60/minute")
def get_overlap_track(
    request: Request,
    chr: Optional[str] = Query(None, max_length=64, description="IGV.js 标准染色体参数，如 chr1 或 1"),
    chromosome: Optional[str] = Query(None, max_length=64, description="chr 的别名参数，如 chr22 或 22"),
    start: int = Query(..., ge=0, description="区域起点 (0-based)"),
    end: int = Query(..., ge=0, description="区域终点"),
    mark_type: Optional[str] = Query(None, max_length=64, description="可选：按组蛋白标记过滤，如 H3K27me3"),
    min_ba: Optional[float] = Query(None, ge=0, description="可选：最小结合亲和力阈值"),
    limit: int = Query(DEFAULT_LIMIT, ge=1, le=MAX_LIMIT, description="最大返回条目数（防止 IGV 一次拉取过多数据）"),
    db: Session = Depends(get_db),
):
    """
    IGV webservice track：返回指定区域内的 overlap 作为 BED6 文本流。

    - 必须提供 `chr` 或 `chromosome`（`chr` 优先级更高）
    - start < end 且 end-start <= 10Mb
    """
    raw_chr = chr or chromosome
    if not raw_chr:
        raise HTTPException(status_code=400, detail="chr or chromosome parameter is required")

    if start >= end:
        raise HTTPException(status_code=400, detail="start must be less than end")

    if (end - start) > MAX_REGION_SIZE_BP:
        raise HTTPException(status_code=400, detail=f"region too large (max {MAX_REGION_SIZE_BP} bp)")

    norm_chr = _normalize_chr(raw_chr)

    logger.info(
        "IGV overlap-track requested: chr=%s, start=%s, end=%s, mark_type=%s, min_ba=%s, limit=%s",
        norm_chr,
        start,
        end,
        mark_type,
        min_ba,
        limit,
    )

    result = _execute_overlap_query(
        db,
        norm_chr,
        start,
        end,
        mark_type=mark_type,
        min_ba=min_ba,
        limit=limit,
    )

    return StreamingResponse(
        _generate_overlap_bed6_stream(result),
        media_type="text/plain",
        headers={
            "Content-Type": "text/plain; charset=utf-8",
        },
    )
