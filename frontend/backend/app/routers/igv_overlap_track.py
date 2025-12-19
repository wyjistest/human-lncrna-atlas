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
import time
from typing import Optional, Generator

from fastapi import APIRouter, Depends, HTTPException, Query, Request
from fastapi.responses import StreamingResponse
from sqlalchemy import text

from app.routers.chipseq_rate_limit import rate_limit
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.core.exceptions import sanitize_db_error

logger = logging.getLogger(__name__)

router = APIRouter()

# 10Mb 以内允许 IGV 区域查询，避免拖垮数据库
MAX_REGION_SIZE_BP = 10_000_000

# 轨道返回上限：IGV 前端通常不需要一次加载过多特征
DEFAULT_LIMIT = 50_000
MAX_LIMIT = 200_000

# overlap 物化视图名称（由后端 SQL/ETL 构建）
MV_LNCRNA_CHIPSEQ_OVERLAPS = "mv_lncrna_chipseq_overlaps"

# Phase 9.12: MV 可用性缓存增加 TTL，避免运行中创建/刷新 MV 后长期走 fallback
MV_CACHE_TTL_SECONDS = 300  # 5 minutes

# 缓存 MV 可用性检查，避免重复访问 pg_class
_mv_available_cache = {"checked": False, "available": False, "checked_at": 0.0}


def reset_mv_cache():
    """
    重置 MV 可用性缓存。

    在创建/刷新 MV 后调用，强制下次查询重新检测。
    可通过 admin 端点触发。
    """
    global _mv_available_cache
    _mv_available_cache = {"checked": False, "available": False, "checked_at": 0.0}
    logger.info("IGV overlap MV cache reset")


def _normalize_chr(raw: str) -> str:
    """标准化染色体字符串：兼容 `1` -> `chr1`。"""
    value = raw.strip()
    if not value:
        return value
    if value.lower().startswith("chr"):
        return f"chr{value[3:]}"
    return f"chr{value}"


def _check_mv_available(db: Session) -> bool:
    """
    检查 mv_lncrna_chipseq_overlaps 是否存在且已填充。

    仅 PostgreSQL 支持该检查；其他 dialect 直接视为不可用。
    Phase 9.12: 添加 TTL 支持，避免运行中创建 MV 后长期走 fallback。
    """
    global _mv_available_cache

    # Return cached result if still valid (within TTL)
    if _mv_available_cache["checked"]:
        elapsed = time.time() - _mv_available_cache["checked_at"]
        if elapsed < MV_CACHE_TTL_SECONDS:
            return _mv_available_cache["available"]
        # TTL expired, re-check
        logger.debug(f"MV cache TTL expired ({elapsed:.1f}s), re-checking...")

    try:
        bind = db.get_bind()
        if not bind or bind.dialect.name != "postgresql":
            _mv_available_cache = {"checked": True, "available": False, "checked_at": time.time()}
            return False

        sql = text(
            """
            SELECT c.relname, c.relispopulated
            FROM pg_class c
            JOIN pg_namespace n ON n.oid = c.relnamespace
            WHERE c.relkind = 'm'
              AND n.nspname = 'public'
              AND c.relname = :mv_name
            """
        )
        row = db.execute(sql, {"mv_name": MV_LNCRNA_CHIPSEQ_OVERLAPS}).fetchone()
        available = bool(row and getattr(row, "relispopulated", False))
        _mv_available_cache = {"checked": True, "available": available, "checked_at": time.time()}
        return available
    except Exception:
        _mv_available_cache = {"checked": True, "available": False, "checked_at": time.time()}
        return False


def _generate_overlap_bed6_stream(
    db: Session,
    chromosome: str,
    start: int,
    end: int,
    *,
    mark_type: Optional[str],
    min_ba: Optional[float],
    limit: int,
) -> Generator[str, None, None]:
    """
    生成 overlap BED6 数据流。

    name 字段包含 mark_type，便于前端与测试做快速校验。
    """
    use_mv = _check_mv_available(db)

    if use_mv:
        sql = text(
            """
            SELECT
                chromosome,
                overlap_start,
                overlap_end,
                lncrna_name,
                target_gene_name,
                mark_name AS mark_type,
                cell_type,
                binding_affinity
            FROM mv_lncrna_chipseq_overlaps
            WHERE chromosome = :chromosome
              AND overlap_start < :end
              AND overlap_end > :start
              AND (:mark_type IS NULL OR mark_name = :mark_type)
              AND (:min_ba IS NULL OR binding_affinity >= :min_ba)
            ORDER BY overlap_start
            LIMIT :limit
            """
        )
    else:
        # fallback：无 MV 时使用原始 join（仅在小窗口内使用，受 MAX_REGION_SIZE_BP 保护）
        sql = text(
            """
            SELECT
                r.best_peak_chr AS chromosome,
                GREATEST(r.best_peak_start, p.peak_start) AS overlap_start,
                LEAST(r.best_peak_end, p.peak_end) AS overlap_end,
                lnc.gene_name AS lncrna_name,
                tgt.gene_name AS target_gene_name,
                m.mark_name AS mark_type,
                e.cell_type,
                r.binding_affinity
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
                AND r.best_peak_chr = :chromosome
                AND r.best_peak_start < :end
                AND r.best_peak_end > :start
                AND (:mark_type IS NULL OR m.mark_name = :mark_type)
                AND (:min_ba IS NULL OR r.binding_affinity >= :min_ba)
            ORDER BY overlap_start
            LIMIT :limit
            """
        )

    params = {
        "chromosome": chromosome,
        "start": start,
        "end": end,
        "mark_type": mark_type,
        "min_ba": min_ba,
        "limit": limit,
    }

    result = db.execute(sql.execution_options(stream_results=True), params)

    for row in result:
        chr_name = row.chromosome
        overlap_start = int(row.overlap_start)
        overlap_end = int(row.overlap_end)

        lncrna = row.lncrna_name or "unknown_lncRNA"
        target = row.target_gene_name or "unknown_target"
        mark = row.mark_type or "unknown_mark"
        cell_type = row.cell_type or "unknown_cell"

        # name: 保持简洁但包含 mark_type，满足 IGV 与测试场景
        name = f"{lncrna}->{target}|{mark}|{cell_type}"

        # score: 使用与 regulations BED 一致的 BA 缩放策略
        ba = float(row.binding_affinity) if row.binding_affinity else 0.0
        score = min(1000, max(0, int(ba * 10)))

        strand = "."
        yield f"{chr_name}\t{overlap_start}\t{overlap_end}\t{name}\t{score}\t{strand}\n"


@router.get("/overlap-track")
@rate_limit("60/minute")
def get_overlap_track(
    request: Request,
    chr: Optional[str] = Query(None, description="IGV.js 标准染色体参数，如 chr1 或 1"),
    chromosome: Optional[str] = Query(None, description="chr 的别名参数，如 chr22 或 22"),
    start: int = Query(..., ge=0, description="区域起点 (0-based)"),
    end: int = Query(..., ge=0, description="区域终点"),
    mark_type: Optional[str] = Query(None, description="可选：按组蛋白标记过滤，如 H3K27me3"),
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

    try:
        stream = _generate_overlap_bed6_stream(
            db,
            norm_chr,
            start,
            end,
            mark_type=mark_type,
            min_ba=min_ba,
            limit=limit,
        )
        return StreamingResponse(
            stream,
            media_type="text/plain",
            headers={
                "Content-Type": "text/plain; charset=utf-8",
            },
        )
    except Exception as e:
        raise sanitize_db_error(e, logger)

