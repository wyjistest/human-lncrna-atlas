"""
物化视图（Materialized Views）运维工具

提供给 Admin API 使用的安全刷新/状态查询能力。

设计目标：
- 安全：仅允许白名单内的 MV 名称，避免 SQL 标识符注入
- 正确：支持 Postgres 的 CONCURRENTLY 约束（必须在事务块外）
- 可用：跨进程互斥（advisory lock），避免多 worker 并发刷新
- 可控：刷新时临时提升 statement_timeout，并在结束后恢复默认值

注意：
- 该模块仅用于运维/管理端点，不应在高频业务请求路径中调用。
"""

from __future__ import annotations

import logging
import re
import time
from typing import Any, Optional

from sqlalchemy import text
from sqlalchemy.engine import Connection

from app.core.config import settings
from app.core.utils import sanitize_for_log

logger = logging.getLogger(__name__)


# 与 scripts/refresh_materialized_views.sh 保持一致（顺序用于处理依赖关系）
DEFAULT_MATERIALIZED_VIEWS: tuple[str, ...] = (
    "mv_analysis_high_affinity_stats_ba100",
    "mv_analysis_top_lncrnas_ba100",
    "mv_lncrna_chipseq_overlaps",
    "mv_lncrna_chipseq_overlaps_epigenetic_summary_ba100",
)

_ALLOWED_MV_SET = set(DEFAULT_MATERIALIZED_VIEWS)
_MV_NAME_PATTERN = re.compile(r"^[a-z0-9_]{1,63}$")

# Postgres advisory lock key（bigint）。
# 取 8 字节 ASCII: "LNCRNAMV" => 0x4C4E43524E414D56（< 2^63，正数）
_MV_REFRESH_LOCK_KEY = 0x4C4E43524E414D56


class MaterializedViewRefreshInProgress(RuntimeError):
    """当已有刷新任务进行中时抛出。"""


def normalize_mv_list(views: Optional[list[str]]) -> list[str]:
    """
    归一化并校验 MV 列表。

    - None => 默认全量（按 DEFAULT_MATERIALIZED_VIEWS 顺序）
    - 非空列表 => 视为选择子集（顺序仍按 DEFAULT_MATERIALIZED_VIEWS 保证依赖正确）
    """
    if views is None:
        return list(DEFAULT_MATERIALIZED_VIEWS)

    if not isinstance(views, list) or not views:
        raise ValueError("views must be a non-empty list or null")

    requested: set[str] = set()
    for mv in views:
        if not isinstance(mv, str) or not mv:
            raise ValueError("views must contain non-empty strings")
        if not _MV_NAME_PATTERN.match(mv):
            raise ValueError(f"Invalid materialized view name: {mv}")
        if mv not in _ALLOWED_MV_SET:
            raise ValueError(f"Materialized view not allowed: {mv}")
        requested.add(mv)

    # Preserve canonical dependency order from DEFAULT_MATERIALIZED_VIEWS.
    return [mv for mv in DEFAULT_MATERIALIZED_VIEWS if mv in requested]


def _require_postgresql(conn: Connection) -> None:
    if getattr(conn.dialect, "name", None) != "postgresql":
        raise RuntimeError("Materialized view operations require PostgreSQL")


_MV_STATUS_SQL = text(
    """
    SELECT
        c.relispopulated AS populated,
        pg_size_pretty(pg_total_relation_size(c.oid)) AS total_size,
        c.reltuples::bigint AS rows_estimate
    FROM pg_class c
    JOIN pg_namespace n ON n.oid = c.relnamespace
    WHERE c.relkind = 'm'
      AND n.nspname = 'public'
      AND c.relname = :mv_name
    """
)


def get_mv_status(conn: Connection, mv_name: str) -> dict[str, Any]:
    """查询单个 MV 的存在/填充/大小/行数估计信息（轻量，不做 COUNT(*)）。"""
    _require_postgresql(conn)

    row = conn.execute(_MV_STATUS_SQL, {"mv_name": mv_name}).fetchone()
    if not row:
        return {
            "name": mv_name,
            "exists": False,
            "populated": None,
            "rows_estimate": None,
            "total_size": None,
        }

    return {
        "name": mv_name,
        "exists": True,
        "populated": bool(getattr(row, "populated", False)),
        "rows_estimate": int(getattr(row, "rows_estimate", 0) or 0),
        "total_size": getattr(row, "total_size", None),
    }


def _set_statement_timeout(conn: Connection, timeout_ms: int) -> None:
    _require_postgresql(conn)
    conn.execute(text("SET statement_timeout = :ms"), {"ms": int(timeout_ms)})


def _try_advisory_lock(conn: Connection) -> bool:
    _require_postgresql(conn)
    return bool(
        conn.execute(
            text("SELECT pg_try_advisory_lock(:key)"),
            {"key": _MV_REFRESH_LOCK_KEY},
        ).scalar_one()
    )


def _unlock_advisory_lock(conn: Connection) -> bool:
    _require_postgresql(conn)
    return bool(
        conn.execute(
            text("SELECT pg_advisory_unlock(:key)"),
            {"key": _MV_REFRESH_LOCK_KEY},
        ).scalar_one()
    )


def get_refresh_lock_available(conn: Connection) -> bool:
    """
    检测 MV 刷新锁是否可用。

    实现：尝试获取 advisory lock，若成功则立即释放；若失败表示当前有刷新进行中。
    """
    acquired = False
    try:
        acquired = _try_advisory_lock(conn)
        return acquired
    finally:
        if acquired:
            try:
                _unlock_advisory_lock(conn)
            except Exception as e:  # pragma: no cover
                logger.error("Failed to unlock MV refresh advisory lock: %s", sanitize_for_log(e, max_length=2000))


def refresh_materialized_views(
    conn: Connection,
    *,
    views: Optional[list[str]] = None,
    concurrently: bool = True,
    analyze: bool = True,
    timeout_seconds: Optional[int] = None,
) -> dict[str, Any]:
    """
    刷新物化视图（同步执行）。

    约束：
    - CONCURRENTLY 必须在事务块外执行：调用方应使用 AUTOCOMMIT connection
      （例如 engine.execution_options(isolation_level="AUTOCOMMIT")）。
    - 为避免污染连接池，会在结束时恢复 statement_timeout 到默认值（QUERY_TIMEOUT_MS）。
    """
    _require_postgresql(conn)

    mv_list = normalize_mv_list(views)

    if timeout_seconds is None:
        timeout_seconds = int(settings.MV_REFRESH_TIMEOUT)
    if timeout_seconds < 0:
        raise ValueError("timeout_seconds must be >= 0")

    timeout_ms = int(timeout_seconds) * 1000
    default_timeout_ms = int(settings.QUERY_TIMEOUT) * 1000

    acquired = False
    started_at = time.monotonic()
    results: list[dict[str, Any]] = []
    try:
        acquired = _try_advisory_lock(conn)
        if not acquired:
            raise MaterializedViewRefreshInProgress("Materialized view refresh is already running")

        # Temporarily relax statement_timeout for long-running refresh operations.
        _set_statement_timeout(conn, timeout_ms)

        for mv_name in mv_list:
            mv_started = time.monotonic()
            status = get_mv_status(conn, mv_name)
            if not status["exists"]:
                results.append(
                    {
                        "name": mv_name,
                        "ok": False,
                        "skipped": True,
                        "reason": "NOT_EXISTS",
                        "duration_seconds": 0.0,
                    }
                )
                continue

            use_concurrently = bool(concurrently and status.get("populated"))
            if concurrently and not status.get("populated"):
                note = "MV not populated; falling back to non-concurrent refresh for first population"
            else:
                note = None

            refresh_sql = f"REFRESH MATERIALIZED VIEW {'CONCURRENTLY ' if use_concurrently else ''}{mv_name}"
            try:
                conn.execute(text(refresh_sql))
                if analyze:
                    conn.execute(text(f"ANALYZE {mv_name}"))
                results.append(
                    {
                        "name": mv_name,
                        "ok": True,
                        "concurrently": use_concurrently,
                        "analyze": bool(analyze),
                        "note": note,
                        "duration_seconds": round(time.monotonic() - mv_started, 3),
                    }
                )
            except Exception as e:
                results.append(
                    {
                        "name": mv_name,
                        "ok": False,
                        "concurrently": use_concurrently,
                        "analyze": bool(analyze),
                        "error": sanitize_for_log(e, max_length=2000),
                        "duration_seconds": round(time.monotonic() - mv_started, 3),
                    }
                )
                logger.error("MV refresh failed for %s: %s", mv_name, sanitize_for_log(e, max_length=2000), exc_info=True)

        return {
            "status": "success" if all(r.get("ok") or r.get("skipped") for r in results) else "partial",
            "concurrently_requested": bool(concurrently),
            "timeout_seconds": int(timeout_seconds),
            "analyze": bool(analyze),
            "views": results,
            "total_duration_seconds": round(time.monotonic() - started_at, 3),
        }
    finally:
        # Always restore statement_timeout; otherwise it may pollute the pooled connection.
        try:
            _set_statement_timeout(conn, default_timeout_ms)
        except Exception as e:  # pragma: no cover
            logger.error("Failed to restore statement_timeout after MV refresh: %s", sanitize_for_log(e, max_length=2000))

        if acquired:
            try:
                _unlock_advisory_lock(conn)
            except Exception as e:  # pragma: no cover
                logger.error("Failed to unlock MV refresh advisory lock: %s", sanitize_for_log(e, max_length=2000))

