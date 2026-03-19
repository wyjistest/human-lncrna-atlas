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
from datetime import datetime, timezone
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
_MV_STATS_STALE_THRESHOLD_SECONDS = 24 * 60 * 60
_MV_SEVERITY_ORDER = {
    "info": 0,
    "warning": 1,
    "critical": 2,
}

_MV_OPERABILITY_HINTS: dict[str, dict[str, Any]] = {
    "mv_analysis_high_affinity_stats_ba100": {
        "affected_features": ["Analysis summary: high-affinity overview"],
        "severity_if_missing": "warning",
        "missing_action": (
            "High-affinity summary fast path is missing. Recreate the analysis MV set before relying on "
            "dashboard-level high-affinity aggregates."
        ),
        "not_populated_action": (
            "Refresh this MV before using analysis summary high-affinity cards in production."
        ),
        "stale_action": "Run ANALYZE or refresh this MV to keep planner stats current for analysis summary queries.",
        "stats_unknown_action": "Run ANALYZE on this MV so Admin can report fresh planner statistics.",
    },
    "mv_analysis_top_lncrnas_ba100": {
        "affected_features": ["Analysis summary: top lncRNAs leaderboard"],
        "severity_if_missing": "warning",
        "missing_action": (
            "Top-lncRNA summary fast path is missing. Recreate the analysis MV set before relying on "
            "dashboard-level ranking cards."
        ),
        "not_populated_action": (
            "Refresh this MV before using analysis summary top-lncRNA aggregates in production."
        ),
        "stale_action": "Run ANALYZE or refresh this MV to keep planner stats current for summary ranking queries.",
        "stats_unknown_action": "Run ANALYZE on this MV so Admin can report fresh planner statistics.",
    },
    "mv_lncrna_chipseq_overlaps": {
        "affected_features": [
            "Overlap list / cursor / statistics",
            "Overlap compare",
            "Overlap export on broad chromosomes",
            "Analysis summary epigenetic fallback source",
        ],
        "severity_if_missing": "critical",
        "missing_action": (
            "Create this MV via schema/v2.3/05_mv_lncrna_chipseq_overlaps.sql, then refresh it before "
            "broad overlap / compare / export queries."
        ),
        "not_populated_action": (
            "Refresh this MV before broad overlap, compare, or export queries. Unpopulated state will force "
            "slow fallbacks or QUERY_TOO_BROAD guardrails."
        ),
        "stale_action": (
            "Run ANALYZE or refresh this MV after recent imports so planner stats stay aligned with broad "
            "overlap workloads."
        ),
        "stats_unknown_action": (
            "Run ANALYZE on this MV so Admin can assess whether overlap planner statistics are fresh enough."
        ),
    },
    "mv_lncrna_chipseq_overlaps_epigenetic_summary_ba100": {
        "affected_features": ["Analysis summary: epigenetic fast path"],
        "severity_if_missing": "warning",
        "missing_action": (
            "Optional epigenetic summary fast path is missing. Analysis summary will fall back to raw overlap "
            "aggregation or empty epigenetic data."
        ),
        "not_populated_action": (
            "Refresh this MV to restore fast epigenetic summary aggregation for the analysis dashboard."
        ),
        "stale_action": (
            "Run ANALYZE or refresh this MV after overlap data changes so epigenetic summary stats remain trustworthy."
        ),
        "stats_unknown_action": "Run ANALYZE on this MV so Admin can report epigenetic summary stats freshness.",
    },
}

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
        pg_total_relation_size(c.oid)::bigint AS total_size_bytes,
        pg_size_pretty(pg_relation_size(c.oid)) AS heap_size,
        pg_relation_size(c.oid)::bigint AS heap_size_bytes,
        pg_size_pretty(pg_indexes_size(c.oid)) AS index_size,
        pg_indexes_size(c.oid)::bigint AS index_size_bytes,
        c.reltuples::bigint AS rows_estimate,
        s.last_analyze AS last_analyze,
        s.last_autoanalyze AS last_autoanalyze
    FROM pg_class c
    JOIN pg_namespace n ON n.oid = c.relnamespace
    LEFT JOIN pg_stat_all_tables s ON s.relid = c.oid
    WHERE c.relkind = 'm'
      AND n.nspname = 'public'
      AND c.relname = :mv_name
    """
)


def _missing_mv_status(mv_name: str) -> dict[str, Any]:
    hint = _MV_OPERABILITY_HINTS.get(mv_name, {})
    return {
        "name": mv_name,
        "exists": False,
        "populated": None,
        "rows_estimate": None,
        "total_size": None,
        "total_size_bytes": None,
        "heap_size": None,
        "heap_size_bytes": None,
        "index_size": None,
        "index_size_bytes": None,
        "last_analyze_at": None,
        "last_autoanalyze_at": None,
        "last_stats_at": None,
        "last_stats_source": "none",
        "stats_age_seconds": None,
        "health_status": "missing",
        "severity": hint.get("severity_if_missing", "warning"),
        "recommended_action": hint.get("missing_action"),
        "affects_features": list(hint.get("affected_features", [])),
    }


def _to_utc_iso8601(value: Any) -> Optional[str]:
    if not isinstance(value, datetime):
        return None
    if value.tzinfo is None:
        value = value.replace(tzinfo=timezone.utc)
    else:
        value = value.astimezone(timezone.utc)
    return value.isoformat().replace("+00:00", "Z")


def _stats_age_seconds(value: Any) -> Optional[float]:
    if not isinstance(value, datetime):
        return None
    if value.tzinfo is None:
        value = value.replace(tzinfo=timezone.utc)
    else:
        value = value.astimezone(timezone.utc)
    return round((datetime.now(timezone.utc) - value).total_seconds(), 3)


def _pick_latest_stats_timestamp(row: Any) -> tuple[Any, str]:
    last_analyze = getattr(row, "last_analyze", None)
    last_autoanalyze = getattr(row, "last_autoanalyze", None)

    if last_analyze and last_autoanalyze:
        if last_autoanalyze >= last_analyze:
            return last_autoanalyze, "autoanalyze"
        return last_analyze, "analyze"
    if last_analyze:
        return last_analyze, "analyze"
    if last_autoanalyze:
        return last_autoanalyze, "autoanalyze"
    return None, "none"


def _evaluate_mv_health(
    mv_name: str,
    *,
    exists: bool,
    populated: Optional[bool],
    stats_age_seconds: Optional[float],
) -> tuple[str, str, Optional[str], list[str]]:
    hint = _MV_OPERABILITY_HINTS.get(mv_name, {})
    affected_features = list(hint.get("affected_features", []))

    if not exists:
        return (
            "missing",
            str(hint.get("severity_if_missing", "warning")),
            hint.get("missing_action"),
            affected_features,
        )

    if populated is False:
        return (
            "not_populated",
            "critical",
            hint.get("not_populated_action", "Refresh this materialized view before using dependent features."),
            affected_features,
        )

    if stats_age_seconds is None:
        return (
            "stats_unavailable",
            "warning",
            hint.get("stats_unknown_action", "Run ANALYZE so Admin can report planner stats freshness."),
            affected_features,
        )

    if stats_age_seconds >= _MV_STATS_STALE_THRESHOLD_SECONDS:
        return (
            "stale_stats",
            "warning",
            hint.get("stale_action", "Run ANALYZE or refresh this materialized view."),
            affected_features,
        )

    return ("healthy", "info", None, affected_features)


def build_attention_summary(
    views: list[dict[str, Any]],
    *,
    supported: bool,
    database_backend: str,
) -> dict[str, Any]:
    total_count = len(views)
    backend_label = (database_backend or "unknown").strip() or "unknown"

    if not supported:
        attention_view_names = [str(view.get("name")) for view in views if view.get("name")]
        return {
            "status": "degraded",
            "severity": "warning",
            "message": f"Materialized view operations are unavailable on {backend_label}.",
            "recommended_action": (
                "Switch the admin backend to PostgreSQL to refresh or inspect materialized views."
            ),
            "attention_count": len(attention_view_names),
            "total_count": total_count,
            "attention_view_names": attention_view_names,
        }

    attention_views = [view for view in views if str(view.get("health_status") or "") != "healthy"]
    attention_view_names = [str(view.get("name")) for view in attention_views if view.get("name")]

    if not attention_views:
        return {
            "status": "healthy",
            "severity": "info",
            "message": "All materialized views are healthy.",
            "recommended_action": None,
            "attention_count": 0,
            "total_count": total_count,
            "attention_view_names": [],
        }

    highest_severity = max(
        (
            str(view.get("severity") or "warning")
            for view in attention_views
        ),
        key=lambda severity: _MV_SEVERITY_ORDER.get(severity, _MV_SEVERITY_ORDER["warning"]),
    )
    unique_actions: list[str] = []
    for view in attention_views:
        action = str(view.get("recommended_action") or "").strip()
        if action and action not in unique_actions:
            unique_actions.append(action)

    if highest_severity == "critical":
        critical_count = sum(1 for view in attention_views if str(view.get("severity")) == "critical")
        message = (
            f"{critical_count} critical materialized view issue(s) detected; "
            f"{len(attention_views)}/{total_count} view(s) need attention."
        )
        status = "critical"
    else:
        message = f"{len(attention_views)}/{total_count} materialized view(s) need attention."
        status = "degraded"

    recommended_action = unique_actions[0] if len(unique_actions) == 1 else None
    if recommended_action is None and highest_severity != "info":
        recommended_action = (
            "Review the affected materialized views in Admin and refresh or ANALYZE the listed views."
        )

    return {
        "status": status,
        "severity": highest_severity,
        "message": message,
        "recommended_action": recommended_action,
        "attention_count": len(attention_views),
        "total_count": total_count,
        "attention_view_names": attention_view_names,
    }


def get_mv_status(conn: Connection, mv_name: str) -> dict[str, Any]:
    """查询单个 MV 的存在/填充/大小/行数估计信息（轻量，不做 COUNT(*)）。"""
    _require_postgresql(conn)

    row = conn.execute(_MV_STATUS_SQL, {"mv_name": mv_name}).fetchone()
    if not row:
        return _missing_mv_status(mv_name)

    latest_stats_at, latest_stats_source = _pick_latest_stats_timestamp(row)
    populated = bool(getattr(row, "populated", False))
    stats_age_seconds = _stats_age_seconds(latest_stats_at)
    health_status, severity, recommended_action, affects_features = _evaluate_mv_health(
        mv_name,
        exists=True,
        populated=populated,
        stats_age_seconds=stats_age_seconds,
    )

    return {
        "name": mv_name,
        "exists": True,
        "populated": populated,
        "rows_estimate": int(getattr(row, "rows_estimate", 0) or 0),
        "total_size": getattr(row, "total_size", None),
        "total_size_bytes": int(getattr(row, "total_size_bytes", 0) or 0),
        "heap_size": getattr(row, "heap_size", None),
        "heap_size_bytes": int(getattr(row, "heap_size_bytes", 0) or 0),
        "index_size": getattr(row, "index_size", None),
        "index_size_bytes": int(getattr(row, "index_size_bytes", 0) or 0),
        "last_analyze_at": _to_utc_iso8601(getattr(row, "last_analyze", None)),
        "last_autoanalyze_at": _to_utc_iso8601(getattr(row, "last_autoanalyze", None)),
        "last_stats_at": _to_utc_iso8601(latest_stats_at),
        "last_stats_source": latest_stats_source,
        "stats_age_seconds": stats_age_seconds,
        "health_status": health_status,
        "severity": severity,
        "recommended_action": recommended_action,
        "affects_features": affects_features,
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
