#!/usr/bin/env python3
"""
Admin metrics 快照导出器（JSON + Issue 友好 Markdown）。

目标：
- 用 1 次导出在 issue 中复现“哪条端点慢、慢在 DB 还是业务/缓存、慢查询是什么”。
- 不依赖额外三方库（仅使用标准库），便于在任意环境快速跑。

用法示例：
  python3 scripts/admin_metrics_snapshot.py --base-url http://localhost:8000
  python3 scripts/admin_metrics_snapshot.py --base-url http://localhost:8000 --admin-api-key "$ADMIN_API_KEY"
  python3 scripts/admin_metrics_snapshot.py --compare docs/reports/admin-metrics-old.json docs/reports/admin-metrics-new.json

输出：
- docs/reports/admin-metrics-<timestamp>.json
- docs/reports/admin-metrics-<timestamp>.md
- docs/reports/admin-metrics-diff-<timestamp>.md
"""

from __future__ import annotations

import argparse
import json
import os
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Optional
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen


REPO_ROOT = Path(__file__).resolve().parents[1]


def _iso_ts() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H-%M-%SZ")


def _to_float(value: Any) -> Optional[float]:
    try:
        if value is None:
            return None
        return float(value)
    except Exception:
        return None


def _to_int(value: Any) -> Optional[int]:
    try:
        if value is None:
            return None
        return int(value)
    except Exception:
        return None


def _fetch_json(url: str, *, admin_api_key: Optional[str], timeout_seconds: float) -> dict[str, Any]:
    headers = {"Accept": "application/json"}
    if admin_api_key:
        headers["X-Admin-API-Key"] = admin_api_key

    req = Request(url, headers=headers, method="GET")
    try:
        with urlopen(req, timeout=timeout_seconds) as resp:
            body = resp.read()
            return json.loads(body.decode("utf-8"))
    except HTTPError as e:
        detail = ""
        try:
            detail = e.read().decode("utf-8", errors="replace")
        except Exception:
            detail = ""
        raise RuntimeError(f"HTTP {e.code} fetching {url}: {detail}".strip()) from e
    except URLError as e:
        raise RuntimeError(f"Network error fetching {url}: {e}") from e
    except json.JSONDecodeError as e:
        raise RuntimeError(f"Invalid JSON from {url}: {e}") from e


def _warmup_get(url: str, *, timeout_seconds: float) -> None:
    """
    Best-effort warmup request to generate a small amount of traffic.

    Notes:
    - Does NOT send Admin API Key (warmup targets should be public read-only endpoints).
    - Ignores response body format (JSON/non-JSON) as long as request succeeds.
    """
    req = Request(url, headers={"Accept": "application/json"}, method="GET")
    try:
        with urlopen(req, timeout=timeout_seconds) as resp:
            resp.read()
    except Exception as e:
        raise RuntimeError(f"Warmup request failed: {url}: {e}") from e


def _top_endpoints(
    endpoints: list[dict[str, Any]],
    *,
    percentile_key: str,
    source_key: str,
    top_n: int,
) -> list[dict[str, Any]]:
    items: list[dict[str, Any]] = []
    for ep in endpoints:
        if not isinstance(ep, dict):
            continue
        path = str(ep.get("path", "") or "")
        if not path:
            continue
        percentiles = ep.get(source_key) or {}
        if not isinstance(percentiles, dict):
            continue
        value = _to_float(percentiles.get(percentile_key))
        if value is None:
            continue
        items.append({"path": path, "value_ms": value, "raw": ep})

    items.sort(key=lambda x: float(x.get("value_ms", -1.0) or -1.0), reverse=True)
    return items[: max(0, int(top_n))]


def _truncate(text: str, *, max_len: int) -> str:
    if len(text) <= max_len:
        return text
    return text[: max(0, max_len - 1)] + "…"


def _md_kv(label: str, value: Any) -> str:
    return f"- **{label}**：{value}"


def build_markdown(metrics: dict[str, Any], *, base_url: str, fetched_at: str) -> str:
    request = metrics.get("request") or {}
    errors = metrics.get("errors") or {}
    response_time = metrics.get("response_time") or {}
    percentiles = metrics.get("percentiles") or {}
    endpoints = metrics.get("endpoints") or []
    cache_stats = metrics.get("cache_stats") or {}
    cache_breakdown = metrics.get("cache_breakdown") or {}
    cache_get_latency = metrics.get("cache_get_latency") or {}
    database = metrics.get("database") or {}

    endpoints_list: list[dict[str, Any]] = []
    if isinstance(endpoints, list):
        endpoints_list = [x for x in endpoints if isinstance(x, dict)]

    top_p95 = _top_endpoints(endpoints_list, percentile_key="p95_ms", source_key="percentiles", top_n=5)
    top_p99 = _top_endpoints(endpoints_list, percentile_key="p99_ms", source_key="percentiles", top_n=5)
    top_db_p95 = _top_endpoints(endpoints_list, percentile_key="p95_ms", source_key="db_percentiles", top_n=5)

    slow_queries = []
    if isinstance(database, dict):
        slow_queries = database.get("slow_queries") or []
    slow_queries_list: list[dict[str, Any]] = []
    if isinstance(slow_queries, list):
        slow_queries_list = [x for x in slow_queries if isinstance(x, dict)]

    def fmt_ms(value: Any) -> str:
        v = _to_float(value)
        if v is None:
            return "-"
        return f"{v:.2f}ms"

    def fmt_pct(value: Any) -> str:
        v = _to_float(value)
        if v is None:
            return "-"
        return f"{v:.2f}%"

    def endpoints_block(title: str, items: list[dict[str, Any]]) -> list[str]:
        if not items:
            return [f"### {title}", "", "_暂无足够样本（<10）或未采集到该百分位。_", ""]
        lines = [f"### {title}", ""]
        for item in items:
            raw = item.get("raw") or {}
            if not isinstance(raw, dict):
                raw = {}
            db_avg_ms = raw.get("db_avg_ms")
            db_query_avg = raw.get("db_query_avg")
            lines.append(
                f"- `{item['path']}`：{item['value_ms']:.2f}ms"
                f"（req={raw.get('requests', 0)}，db_avg={fmt_ms(db_avg_ms)}，db_q/req={_to_float(db_query_avg) if db_query_avg is not None else '-'}）"
            )
        lines.append("")
        return lines

    # Cache breakdown helpers
    namespaces_top = []
    if isinstance(cache_breakdown, dict):
        namespaces_top = (cache_breakdown.get("namespaces") or {}).get("top") or []
    namespaces_list: list[dict[str, Any]] = []
    if isinstance(namespaces_top, list):
        namespaces_list = [x for x in namespaces_top if isinstance(x, dict)]

    # Slow queries block (already sorted by backend: total_time desc)
    slow_lines = ["### DB 慢查询榜单（Top 10）", ""]
    if not slow_queries_list:
        slow_lines += ["_暂无慢查询样本（或阈值为 0）。_", ""]
    else:
        for row in slow_queries_list[:10]:
            fingerprint = str(row.get("fingerprint", "") or "")
            route = row.get("route")
            route_text = f"`{route}`" if route else "-"
            statement = _truncate(str(row.get("statement", "") or ""), max_len=240)
            slow_lines.append(
                f"- `{fingerprint}` / {route_text}：count={row.get('count', 0)}，"
                f"avg={fmt_ms(row.get('avg_ms'))}，max={fmt_ms(row.get('max_ms'))}，"
                f"total={fmt_ms(row.get('total_time_ms'))}\n"
                f"  - SQL: `{statement}`"
            )
        slow_lines.append("")

    # Cache latency block
    cache_latency_lines = ["### Cache get() 延迟（百分位）", ""]
    if not isinstance(cache_get_latency, dict) or not (cache_get_latency.get("hits") or cache_get_latency.get("misses")):
        cache_latency_lines += ["_暂无足够样本。_", ""]
    else:
        hits = cache_get_latency.get("hits") or {}
        misses = cache_get_latency.get("misses") or {}
        cache_latency_lines += [
            _md_kv("hits samples", cache_get_latency.get("hits_samples", 0)),
            _md_kv("misses samples", cache_get_latency.get("misses_samples", 0)),
            _md_kv("hits p95", fmt_ms(hits.get("p95_ms") if isinstance(hits, dict) else None)),
            _md_kv("hits p99", fmt_ms(hits.get("p99_ms") if isinstance(hits, dict) else None)),
            _md_kv("misses p95", fmt_ms(misses.get("p95_ms") if isinstance(misses, dict) else None)),
            _md_kv("misses p99", fmt_ms(misses.get("p99_ms") if isinstance(misses, dict) else None)),
            "",
        ]

    # Cache namespaces block
    cache_ns_lines = ["### Cache namespaces（Top）", ""]
    if not namespaces_list:
        cache_ns_lines += ["_暂无 namespaces 统计。_", ""]
    else:
        for ns in namespaces_list[:10]:
            name = str(ns.get("namespace", "") or "")
            cache_ns_lines.append(
                f"- `{name}`：req={ns.get('requests', 0)}，hit_rate={fmt_pct(ns.get('hit_rate_pct'))}，"
                f"compute_avg={fmt_ms(ns.get('compute_avg_ms'))}，compute_max={fmt_ms(ns.get('compute_max_ms'))}"
            )
        cache_ns_lines.append("")

    # Cache keys block
    keys_top = []
    if isinstance(cache_breakdown, dict):
        keys_top = (cache_breakdown.get("keys") or {}).get("top") or []
    keys_list: list[dict[str, Any]] = []
    if isinstance(keys_top, list):
        keys_list = [x for x in keys_top if isinstance(x, dict)]

    cache_keys_lines = ["### Cache keys（Top）", ""]
    if not keys_list:
        cache_keys_lines += ["_暂无 keys 统计。_", ""]
    else:
        for row in keys_list[:10]:
            key = str(row.get("key", "") or "")
            namespace = row.get("namespace")
            ns_text = str(namespace) if namespace else "-"
            compute_count = _to_int(row.get("compute_count")) or 0
            cache_keys_lines.append(
                f"- `{_truncate(key, max_len=120)}`：ns={ns_text}，req={row.get('requests', 0)}，"
                f"hit_rate={fmt_pct(row.get('hit_rate_pct'))}，hits={row.get('hits', 0)}，misses={row.get('misses', 0)}，"
                f"compute_n={compute_count}，compute_avg={fmt_ms(row.get('compute_avg_ms'))}，compute_max={fmt_ms(row.get('compute_max_ms'))}"
            )
        cache_keys_lines.append("")

    # Cache routes compute block
    routes_top = []
    if isinstance(cache_breakdown, dict):
        routes_top = (cache_breakdown.get("routes") or {}).get("top") or []
    routes_list: list[dict[str, Any]] = []
    if isinstance(routes_top, list):
        routes_list = [x for x in routes_top if isinstance(x, dict)]

    cache_routes_lines = ["### Cache routes（Compute Top）", ""]
    if not routes_list:
        cache_routes_lines += ["_暂无 routes compute 统计。_", ""]
    else:
        for row in routes_list[:10]:
            route = str(row.get("route", "") or "")
            compute_count = _to_int(row.get("compute_count")) or 0
            cache_routes_lines.append(
                f"- `{route}`：req={row.get('requests', 0)}，hit_rate={fmt_pct(row.get('hit_rate_pct'))}，"
                f"hits={row.get('hits', 0)}，misses={row.get('misses', 0)}，"
                f"compute_n={compute_count}，compute_avg={fmt_ms(row.get('compute_avg_ms'))}，compute_max={fmt_ms(row.get('compute_max_ms'))}"
            )
        cache_routes_lines.append("")

    md_lines = [
        "# Performance Snapshot (admin/metrics)",
        "",
        _md_kv("fetched_at", fetched_at),
        _md_kv("base_url", base_url),
        "",
        "## Request/Errors",
        "",
        _md_kv("total requests", request.get("total", 0)),
        _md_kv("last minute", request.get("last_minute", 0)),
        _md_kv("total errors (5xx)", errors.get("total", 0)),
        _md_kv("error rate", errors.get("rate", 0)),
        _md_kv("avg response", fmt_ms(response_time.get("avg_ms"))),
        "",
        "## Response Percentiles（全局）",
        "",
        _md_kv("p50", fmt_ms(percentiles.get("p50_ms") if isinstance(percentiles, dict) else None)),
        _md_kv("p95", fmt_ms(percentiles.get("p95_ms") if isinstance(percentiles, dict) else None)),
        _md_kv("p99", fmt_ms(percentiles.get("p99_ms") if isinstance(percentiles, dict) else None)),
        "",
        "## Cache",
        "",
        _md_kv("hit rate", fmt_pct(cache_stats.get("hit_rate_pct"))),
        _md_kv("hits", cache_stats.get("hits", 0)),
        _md_kv("misses", cache_stats.get("misses", 0)),
        "",
        *cache_latency_lines,
        *cache_ns_lines,
        *cache_keys_lines,
        *cache_routes_lines,
        "## Endpoints（Tail Latency）",
        "",
        *endpoints_block("Top endpoints by Response P95", top_p95),
        *endpoints_block("Top endpoints by Response P99", top_p99),
        *endpoints_block("Top endpoints by DB P95", top_db_p95),
        "## Database",
        "",
        _md_kv("total queries", database.get("total_queries", 0) if isinstance(database, dict) else 0),
        _md_kv("avg query", fmt_ms(database.get("avg_ms") if isinstance(database, dict) else None)),
        _md_kv("query p95", fmt_ms((database.get("percentiles") or {}).get("p95_ms") if isinstance(database, dict) else None)),
        _md_kv("query p99", fmt_ms((database.get("percentiles") or {}).get("p99_ms") if isinstance(database, dict) else None)),
        _md_kv("per-request DB avg", fmt_ms(database.get("request_avg_ms") if isinstance(database, dict) else None)),
        _md_kv("per-request DB p95", fmt_ms((database.get("request_percentiles") or {}).get("p95_ms") if isinstance(database, dict) else None)),
        _md_kv("per-request DB p99", fmt_ms((database.get("request_percentiles") or {}).get("p99_ms") if isinstance(database, dict) else None)),
        "",
        *slow_lines,
        "## Notes",
        "",
        "- 如果 Response P95 很高但 DB P95 很低：优先看 cache routes/namespaces 的 compute_* 与热点 keys（可能是回源/计算/IO）。",
        "- 如果 DB P95 很高：优先看慢查询榜单（fingerprint+route）定位具体 SQL 与触发端点。",
        "- `n=<samples>/10` 代表样本不足，建议先制造少量流量再导出。",
        "",
    ]

    return "\n".join(md_lines)


def _resolve_input_path(raw: str) -> Path:
    path = Path(raw).expanduser()
    if not path.is_absolute():
        path = (REPO_ROOT / path).resolve()
    return path


def _load_json_file(path: Path) -> dict[str, Any]:
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except FileNotFoundError as e:
        raise RuntimeError(f"JSON file not found: {path}") from e
    except json.JSONDecodeError as e:
        raise RuntimeError(f"Invalid JSON in {path}: {e}") from e
    except Exception as e:
        raise RuntimeError(f"Failed to read {path}: {e}") from e

    if not isinstance(data, dict):
        raise RuntimeError(f"Expected JSON object in {path}, got {type(data).__name__}")
    return data


def build_diff_markdown(
    old_metrics: dict[str, Any],
    new_metrics: dict[str, Any],
    *,
    old_label: str,
    new_label: str,
    generated_at: str,
) -> str:
    def fmt_ms(value: Any) -> str:
        v = _to_float(value)
        if v is None:
            return "-"
        return f"{v:.2f}ms"

    def fmt_pct(value: Any) -> str:
        v = _to_float(value)
        if v is None:
            return "-"
        return f"{v:.2f}%"

    def fmt_change(old: Any, new: Any, *, unit: str) -> str:
        old_v = _to_float(old)
        new_v = _to_float(new)
        if old_v is None and new_v is None:
            return "- → -"
        if unit == "ms":
            old_s = fmt_ms(old_v)
            new_s = fmt_ms(new_v)
        else:
            old_s = fmt_pct(old_v)
            new_s = fmt_pct(new_v)

        if old_v is None or new_v is None:
            return f"{old_s} → {new_s}"

        delta = new_v - old_v
        sign = "+" if delta > 0 else ""
        if unit == "ms":
            delta_s = f"{sign}{delta:.2f}ms"
        else:
            delta_s = f"{sign}{delta:.2f}%"
        return f"{old_s} → {new_s} ({delta_s})"

    def fmt_int_change(old: Any, new: Any) -> str:
        old_i = _to_int(old)
        new_i = _to_int(new)
        if old_i is None and new_i is None:
            return "- → -"
        if old_i is None or new_i is None:
            return f"{old_i if old_i is not None else '-'} → {new_i if new_i is not None else '-'}"
        delta = new_i - old_i
        sign = "+" if delta > 0 else ""
        return f"{old_i} → {new_i} ({sign}{delta})"

    old_request = old_metrics.get("request") or {}
    new_request = new_metrics.get("request") or {}
    old_errors = old_metrics.get("errors") or {}
    new_errors = new_metrics.get("errors") or {}
    old_response_time = old_metrics.get("response_time") or {}
    new_response_time = new_metrics.get("response_time") or {}
    old_percentiles = old_metrics.get("percentiles") or {}
    new_percentiles = new_metrics.get("percentiles") or {}
    old_cache_stats = old_metrics.get("cache_stats") or {}
    new_cache_stats = new_metrics.get("cache_stats") or {}
    old_cache_get_latency = old_metrics.get("cache_get_latency") or {}
    new_cache_get_latency = new_metrics.get("cache_get_latency") or {}
    old_cache_breakdown = old_metrics.get("cache_breakdown") or {}
    new_cache_breakdown = new_metrics.get("cache_breakdown") or {}

    if not isinstance(old_cache_get_latency, dict):
        old_cache_get_latency = {}
    if not isinstance(new_cache_get_latency, dict):
        new_cache_get_latency = {}
    if not isinstance(old_cache_breakdown, dict):
        old_cache_breakdown = {}
    if not isinstance(new_cache_breakdown, dict):
        new_cache_breakdown = {}

    def cache_latency_section() -> list[str]:
        old_hits = old_cache_get_latency.get("hits") or {}
        new_hits = new_cache_get_latency.get("hits") or {}
        old_misses = old_cache_get_latency.get("misses") or {}
        new_misses = new_cache_get_latency.get("misses") or {}

        if not isinstance(old_hits, dict):
            old_hits = {}
        if not isinstance(new_hits, dict):
            new_hits = {}
        if not isinstance(old_misses, dict):
            old_misses = {}
        if not isinstance(new_misses, dict):
            new_misses = {}

        has_any = bool(old_hits or old_misses or new_hits or new_misses)
        lines = ["### Cache get() 延迟（变化）", ""]
        if not has_any:
            return lines + ["_暂无足够样本（或字段缺失）。_", ""]

        return lines + [
            _md_kv("hits samples", fmt_int_change(old_cache_get_latency.get("hits_samples"), new_cache_get_latency.get("hits_samples"))),
            _md_kv(
                "misses samples",
                fmt_int_change(old_cache_get_latency.get("misses_samples"), new_cache_get_latency.get("misses_samples")),
            ),
            _md_kv("hits p95", fmt_change(old_hits.get("p95_ms"), new_hits.get("p95_ms"), unit="ms")),
            _md_kv("hits p99", fmt_change(old_hits.get("p99_ms"), new_hits.get("p99_ms"), unit="ms")),
            _md_kv("misses p95", fmt_change(old_misses.get("p95_ms"), new_misses.get("p95_ms"), unit="ms")),
            _md_kv("misses p99", fmt_change(old_misses.get("p99_ms"), new_misses.get("p99_ms"), unit="ms")),
            "",
        ]

    def _extract_breakdown_top(breakdown: dict[str, Any], kind: str) -> list[dict[str, Any]]:
        top = (breakdown.get(kind) or {}).get("top") or []
        if not isinstance(top, list):
            return []
        return [x for x in top if isinstance(x, dict)]

    def _index_rows(rows: list[dict[str, Any]], key_field: str) -> dict[str, dict[str, Any]]:
        out: dict[str, dict[str, Any]] = {}
        for row in rows:
            raw_key = row.get(key_field)
            key = str(raw_key) if raw_key is not None else ""
            key = key.strip()
            if not key:
                continue
            out[key] = row
        return out

    def cache_routes_section() -> list[str]:
        old_rows = _extract_breakdown_top(old_cache_breakdown, "routes")
        new_rows = _extract_breakdown_top(new_cache_breakdown, "routes")
        old_map = _index_rows(old_rows, "route")
        new_map = _index_rows(new_rows, "route")

        keys = sorted(set(old_map.keys()) | set(new_map.keys()))
        lines = ["### Cache routes（Compute 变化）", ""]
        if not keys:
            return lines + ["_暂无 routes compute 统计（或字段缺失）。_", ""]

        for route in keys[:10]:
            old_row = old_map.get(route) or {}
            new_row = new_map.get(route) or {}
            lines.append(
                f"- `{route}`："
                f"compute_avg={fmt_change(old_row.get('compute_avg_ms'), new_row.get('compute_avg_ms'), unit='ms')}，"
                f"compute_max={fmt_change(old_row.get('compute_max_ms'), new_row.get('compute_max_ms'), unit='ms')}，"
                f"compute_n={fmt_int_change(old_row.get('compute_count'), new_row.get('compute_count'))}，"
                f"hit_rate={fmt_change(old_row.get('hit_rate_pct'), new_row.get('hit_rate_pct'), unit='%')}，"
                f"req={fmt_int_change(old_row.get('requests'), new_row.get('requests'))}"
            )
        lines.append("")
        return lines

    def cache_keys_section() -> list[str]:
        old_rows = _extract_breakdown_top(old_cache_breakdown, "keys")
        new_rows = _extract_breakdown_top(new_cache_breakdown, "keys")
        old_map = _index_rows(old_rows, "key")
        new_map = _index_rows(new_rows, "key")

        keys = sorted(set(old_map.keys()) | set(new_map.keys()))
        lines = ["### Cache keys（变化）", ""]
        if not keys:
            return lines + ["_暂无 keys 统计（或字段缺失）。_", ""]

        for cache_key in keys[:10]:
            old_row = old_map.get(cache_key) or {}
            new_row = new_map.get(cache_key) or {}
            namespace = new_row.get("namespace") if new_row.get("namespace") else old_row.get("namespace")
            ns_text = str(namespace) if namespace else "-"
            lines.append(
                f"- `{_truncate(cache_key, max_len=160)}`：ns={ns_text}，"
                f"compute_avg={fmt_change(old_row.get('compute_avg_ms'), new_row.get('compute_avg_ms'), unit='ms')}，"
                f"compute_max={fmt_change(old_row.get('compute_max_ms'), new_row.get('compute_max_ms'), unit='ms')}，"
                f"compute_n={fmt_int_change(old_row.get('compute_count'), new_row.get('compute_count'))}，"
                f"hit_rate={fmt_change(old_row.get('hit_rate_pct'), new_row.get('hit_rate_pct'), unit='%')}，"
                f"req={fmt_int_change(old_row.get('requests'), new_row.get('requests'))}"
            )
        lines.append("")
        return lines

    def cache_namespaces_section() -> list[str]:
        old_rows = _extract_breakdown_top(old_cache_breakdown, "namespaces")
        new_rows = _extract_breakdown_top(new_cache_breakdown, "namespaces")
        old_map = _index_rows(old_rows, "namespace")
        new_map = _index_rows(new_rows, "namespace")

        keys = sorted(set(old_map.keys()) | set(new_map.keys()))
        lines = ["### Cache namespaces（变化）", ""]
        if not keys:
            return lines + ["_暂无 namespaces 统计（或字段缺失）。_", ""]

        for namespace in keys[:10]:
            old_row = old_map.get(namespace) or {}
            new_row = new_map.get(namespace) or {}
            lines.append(
                f"- `{namespace}`："
                f"compute_avg={fmt_change(old_row.get('compute_avg_ms'), new_row.get('compute_avg_ms'), unit='ms')}，"
                f"compute_max={fmt_change(old_row.get('compute_max_ms'), new_row.get('compute_max_ms'), unit='ms')}，"
                f"hit_rate={fmt_change(old_row.get('hit_rate_pct'), new_row.get('hit_rate_pct'), unit='%')}，"
                f"req={fmt_int_change(old_row.get('requests'), new_row.get('requests'))}"
            )
        lines.append("")
        return lines

    def endpoints_by_path(metrics: dict[str, Any]) -> dict[str, dict[str, Any]]:
        eps = metrics.get("endpoints") or []
        if not isinstance(eps, list):
            return {}
        out: dict[str, dict[str, Any]] = {}
        for ep in eps:
            if not isinstance(ep, dict):
                continue
            path = str(ep.get("path", "") or "")
            if not path:
                continue
            out[path] = ep
        return out

    old_eps = endpoints_by_path(old_metrics)
    new_eps = endpoints_by_path(new_metrics)

    def endpoint_percentile(ep: Optional[dict[str, Any]], *, source_key: str, percentile_key: str) -> Optional[float]:
        if not ep:
            return None
        percentiles = ep.get(source_key) or {}
        if not isinstance(percentiles, dict):
            return None
        return _to_float(percentiles.get(percentile_key))

    def endpoint_requests(ep: Optional[dict[str, Any]]) -> Optional[int]:
        if not ep:
            return None
        return _to_int(ep.get("requests"))

    def endpoint_changes(*, source_key: str, percentile_key: str) -> list[dict[str, Any]]:
        rows: list[dict[str, Any]] = []
        for path in sorted(set(old_eps.keys()) | set(new_eps.keys())):
            old_ep = old_eps.get(path)
            new_ep = new_eps.get(path)
            old_v = endpoint_percentile(old_ep, source_key=source_key, percentile_key=percentile_key)
            new_v = endpoint_percentile(new_ep, source_key=source_key, percentile_key=percentile_key)
            if old_v is None and new_v is None:
                continue
            delta = (new_v - old_v) if (old_v is not None and new_v is not None) else None
            rows.append(
                {
                    "path": path,
                    "old_ms": old_v,
                    "new_ms": new_v,
                    "delta_ms": delta,
                    "old_req": endpoint_requests(old_ep),
                    "new_req": endpoint_requests(new_ep),
                }
            )
        return rows

    def format_endpoint_row(row: dict[str, Any]) -> str:
        old_ms = row.get("old_ms")
        new_ms = row.get("new_ms")
        change = fmt_change(old_ms, new_ms, unit="ms")
        old_req = row.get("old_req")
        new_req = row.get("new_req")
        req_text = ""
        if old_req is not None or new_req is not None:
            req_text = f"（req {fmt_int_change(old_req, new_req)}）"
        return f"- `{row['path']}`：{change}{req_text}"

    def split_top(rows: list[dict[str, Any]], *, top_n: int) -> tuple[list[dict[str, Any]], list[dict[str, Any]], list[dict[str, Any]]]:
        regressions = [r for r in rows if isinstance(r.get("delta_ms"), float) and (r.get("delta_ms") or 0.0) > 0]
        improvements = [r for r in rows if isinstance(r.get("delta_ms"), float) and (r.get("delta_ms") or 0.0) < 0]
        unknown = [r for r in rows if r.get("delta_ms") is None]

        regressions.sort(key=lambda r: float(r.get("delta_ms") or 0.0), reverse=True)
        improvements.sort(key=lambda r: float(r.get("delta_ms") or 0.0))
        return (regressions[:top_n], improvements[:top_n], unknown[:top_n])

    # Slow queries diff
    def slow_queries_by_key(metrics: dict[str, Any]) -> dict[tuple[str, str], dict[str, Any]]:
        db = metrics.get("database") or {}
        if not isinstance(db, dict):
            return {}
        rows = db.get("slow_queries") or []
        if not isinstance(rows, list):
            return {}
        out: dict[tuple[str, str], dict[str, Any]] = {}
        for row in rows:
            if not isinstance(row, dict):
                continue
            fp = str(row.get("fingerprint", "") or "")
            route = str(row.get("route", "") or "")
            if not fp and not route:
                continue
            out[(fp, route)] = row
        return out

    old_sq = slow_queries_by_key(old_metrics)
    new_sq = slow_queries_by_key(new_metrics)
    slow_rows: list[dict[str, Any]] = []
    for key in sorted(set(old_sq.keys()) | set(new_sq.keys())):
        old_row = old_sq.get(key) or {}
        new_row = new_sq.get(key) or {}
        old_total = _to_float(old_row.get("total_time_ms"))
        new_total = _to_float(new_row.get("total_time_ms"))
        if old_total is None and new_total is None:
            continue
        slow_rows.append(
            {
                "fingerprint": key[0],
                "route": key[1],
                "old": old_row,
                "new": new_row,
                "delta_total": (new_total - old_total) if (old_total is not None and new_total is not None) else None,
            }
        )

    slow_rows.sort(key=lambda r: float(r.get("delta_total") or 0.0), reverse=True)

    md_lines = [
        "# Performance Snapshot Diff (admin/metrics)",
        "",
        _md_kv("generated_at", generated_at),
        _md_kv("old", old_label),
        _md_kv("new", new_label),
        "",
        "## Request/Errors（变化）",
        "",
        _md_kv("total requests", fmt_int_change((old_request or {}).get("total"), (new_request or {}).get("total"))),
        _md_kv("last minute", fmt_int_change((old_request or {}).get("last_minute"), (new_request or {}).get("last_minute"))),
        _md_kv("total errors (5xx)", fmt_int_change((old_errors or {}).get("total"), (new_errors or {}).get("total"))),
        _md_kv("error rate", fmt_change((old_errors or {}).get("rate"), (new_errors or {}).get("rate"), unit="%")),
        _md_kv("avg response", fmt_change((old_response_time or {}).get("avg_ms"), (new_response_time or {}).get("avg_ms"), unit="ms")),
        "",
        "## Response Percentiles（全局变化）",
        "",
        _md_kv("p50", fmt_change((old_percentiles or {}).get("p50_ms"), (new_percentiles or {}).get("p50_ms"), unit="ms")),
        _md_kv("p95", fmt_change((old_percentiles or {}).get("p95_ms"), (new_percentiles or {}).get("p95_ms"), unit="ms")),
        _md_kv("p99", fmt_change((old_percentiles or {}).get("p99_ms"), (new_percentiles or {}).get("p99_ms"), unit="ms")),
        "",
        "## Cache（变化）",
        "",
        _md_kv("hit rate", fmt_change((old_cache_stats or {}).get("hit_rate_pct"), (new_cache_stats or {}).get("hit_rate_pct"), unit="%")),
        _md_kv("hits", fmt_int_change((old_cache_stats or {}).get("hits"), (new_cache_stats or {}).get("hits"))),
        _md_kv("misses", fmt_int_change((old_cache_stats or {}).get("misses"), (new_cache_stats or {}).get("misses"))),
        "",
        *cache_latency_section(),
        *cache_routes_section(),
        *cache_keys_section(),
        *cache_namespaces_section(),
        "## Endpoints（Tail Latency 变化）",
        "",
    ]

    resp_p95 = endpoint_changes(source_key="percentiles", percentile_key="p95_ms")
    resp_p99 = endpoint_changes(source_key="percentiles", percentile_key="p99_ms")
    db_p95 = endpoint_changes(source_key="db_percentiles", percentile_key="p95_ms")
    db_p99 = endpoint_changes(source_key="db_percentiles", percentile_key="p99_ms")

    def endpoints_section(title: str, rows: list[dict[str, Any]]) -> list[str]:
        if not rows:
            return [f"### {title}", "", "_暂无足够样本或字段缺失。_", ""]

        regressions, improvements, unknown = split_top(rows, top_n=5)
        lines = [f"### {title}", ""]
        if regressions:
            lines.append("**Regressions（变慢 Top）**")
            lines += [format_endpoint_row(r) for r in regressions]
            lines.append("")
        if improvements:
            lines.append("**Improvements（变快 Top）**")
            lines += [format_endpoint_row(r) for r in improvements]
            lines.append("")
        if unknown:
            lines.append("**Other changes（新增/缺失）**")
            lines += [format_endpoint_row(r) for r in unknown]
            lines.append("")
        return lines

    md_lines += endpoints_section("Top endpoint changes by Response P95", resp_p95)
    md_lines += endpoints_section("Top endpoint changes by Response P99", resp_p99)
    md_lines += endpoints_section("Top endpoint changes by DB P95", db_p95)
    md_lines += endpoints_section("Top endpoint changes by DB P99", db_p99)

    md_lines += [
        "## Database（变化）",
        "",
        "### DB 慢查询变化（按 total_time_ms 增量排序，Top 10）",
        "",
    ]

    if not slow_rows:
        md_lines += ["_暂无慢查询样本（或字段缺失）。_", ""]
    else:
        for row in slow_rows[:10]:
            fp = row.get("fingerprint") or ""
            route = row.get("route") or ""
            old_row = row.get("old") or {}
            new_row = row.get("new") or {}
            statement = str(new_row.get("statement") or old_row.get("statement") or "")
            md_lines.append(
                f"- `{fp}` / `{route}`："
                f"total={fmt_change(old_row.get('total_time_ms'), new_row.get('total_time_ms'), unit='ms')}，"
                f"count={fmt_int_change(old_row.get('count'), new_row.get('count'))}，"
                f"avg={fmt_change(old_row.get('avg_ms'), new_row.get('avg_ms'), unit='ms')}，"
                f"max={fmt_change(old_row.get('max_ms'), new_row.get('max_ms'), unit='ms')}"
            )
            if statement:
                md_lines.append(f"  - SQL: `{_truncate(statement, max_len=240)}`")
        md_lines.append("")

    md_lines += [
        "## Notes",
        "",
        "- 该 diff 只对比两个 JSON 的关键字段；若某些字段缺失，会显示为 `-` 或落入“Other changes”。",
        "- 快照受流量/缓存热度影响：建议在导出前使用 `--warmup-rounds` 预热，并尽量保证两次快照的对比环境一致。",
        "",
    ]

    return "\n".join(md_lines)


def main() -> int:
    env_base_url = os.environ.get("API_BASE_URL") or ""
    default_base_url = env_base_url.strip() or "http://localhost:8000"

    env_admin_api_key = os.environ.get("ADMIN_API_KEY")
    default_admin_api_key = env_admin_api_key.strip() if isinstance(env_admin_api_key, str) and env_admin_api_key.strip() else None

    # 兼容本地代理环境：默认绕过 localhost/127.0.0.1，避免请求走 http_proxy 导致连接失败/卡住。
    if not os.environ.get("NO_PROXY") and not os.environ.get("no_proxy"):
        default_no_proxy = "127.0.0.1,localhost,::1"
        os.environ["NO_PROXY"] = default_no_proxy
        os.environ["no_proxy"] = default_no_proxy

    parser = argparse.ArgumentParser(description="Export /api/v1/admin/metrics snapshot (JSON + Markdown).")
    parser.add_argument(
        "--base-url",
        default=default_base_url,
        help="Backend base url (default: $API_BASE_URL or http://localhost:8000)",
    )
    parser.add_argument(
        "--admin-api-key",
        default=default_admin_api_key,
        help="Admin API Key (sent as X-Admin-API-Key; default: $ADMIN_API_KEY)",
    )
    parser.add_argument(
        "--timeout-seconds",
        type=float,
        default=10.0,
        help="HTTP timeout seconds (default: 10)",
    )
    parser.add_argument(
        "--out-dir",
        default=str(REPO_ROOT / "docs" / "reports"),
        help="Output directory for snapshot files (default: docs/reports)",
    )
    parser.add_argument(
        "--prefix",
        default="admin-metrics",
        help="Output file name prefix (default: admin-metrics)",
    )
    parser.add_argument(
        "--warmup-rounds",
        type=int,
        default=0,
        help=(
            "Best-effort warmup rounds before snapshot (default: 0=disabled). "
            "Each round hits a small fixed set of read-only endpoints once, to help fill percentile samples."
        ),
    )
    parser.add_argument(
        "--warmup-timeout-seconds",
        type=float,
        default=None,
        help="Warmup HTTP timeout seconds (default: same as --timeout-seconds)",
    )
    parser.add_argument(
        "--compare",
        nargs=2,
        metavar=("OLD_JSON", "NEW_JSON"),
        default=None,
        help="Compare two exported snapshot JSON files and emit a Markdown diff (no network).",
    )
    args = parser.parse_args()

    base_url = str(args.base_url or "").rstrip("/")
    metrics_url = f"{base_url}/api/v1/admin/metrics"

    ts = _iso_ts()
    out_dir = Path(args.out_dir).expanduser()
    if not out_dir.is_absolute():
        out_dir = (REPO_ROOT / out_dir).resolve()
    out_dir.mkdir(parents=True, exist_ok=True)

    if args.compare:
        old_path = _resolve_input_path(str(args.compare[0]))
        new_path = _resolve_input_path(str(args.compare[1]))

        try:
            old_metrics = _load_json_file(old_path)
            new_metrics = _load_json_file(new_path)
        except Exception as e:
            print(f"[ERROR] {e}", file=sys.stderr)
            return 1

        prefix = str(args.prefix or "").strip() or "admin-metrics-diff"
        if prefix == "admin-metrics":
            prefix = "admin-metrics-diff"

        md_path = out_dir / f"{prefix}-{ts}.md"
        md = build_diff_markdown(
            old_metrics,
            new_metrics,
            old_label=str(old_path),
            new_label=str(new_path),
            generated_at=ts,
        )
        try:
            md_path.write_text(md, encoding="utf-8")
        except Exception as e:
            print(f"[ERROR] Failed to write Markdown diff: {e}", file=sys.stderr)
            return 1

        print("Diff exported:")

        def _format_path(p: Path) -> str:
            try:
                return str(p.relative_to(REPO_ROOT))
            except Exception:
                return str(p)

        print(f"- MD:   {_format_path(md_path)}")
        return 0

    json_path = out_dir / f"{args.prefix}-{ts}.json"
    md_path = out_dir / f"{args.prefix}-{ts}.md"

    warmup_rounds = max(0, int(args.warmup_rounds or 0))
    if warmup_rounds > 0:
        warmup_timeout = float(args.warmup_timeout_seconds) if args.warmup_timeout_seconds is not None else float(args.timeout_seconds)

        warmup_paths = [
            "/health",
            "/api/v1/stats/overview",
            "/api/v1/genes?page=1&page_size=1&species_id=1",
            "/api/v1/regulations?page=1&page_size=1&species_id=1",
        ]
        for _ in range(warmup_rounds):
            for path in warmup_paths:
                try:
                    _warmup_get(f"{base_url}{path}", timeout_seconds=warmup_timeout)
                except Exception as e:
                    print(f"[WARN] {e}", file=sys.stderr)

    try:
        metrics = _fetch_json(metrics_url, admin_api_key=args.admin_api_key, timeout_seconds=float(args.timeout_seconds))
    except Exception as e:
        # 最常见：403（非内网/未带 key）或后端未启动
        print(f"[ERROR] {e}", file=sys.stderr)
        print("", file=sys.stderr)
        print("Troubleshooting:", file=sys.stderr)
        print(f"- Ensure backend is running and reachable: {base_url}", file=sys.stderr)
        print("- If you see 403:", file=sys.stderr)
        print("  - Provide --admin-api-key, OR", file=sys.stderr)
        print("  - Run from a private IP and set ADMIN_REQUIRE_API_KEY=false for local dev only", file=sys.stderr)
        return 1

    try:
        json_path.write_text(json.dumps(metrics, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    except Exception as e:
        print(f"[ERROR] Failed to write JSON: {e}", file=sys.stderr)
        return 1

    md = build_markdown(metrics, base_url=base_url, fetched_at=ts)
    try:
        md_path.write_text(md, encoding="utf-8")
    except Exception as e:
        print(f"[ERROR] Failed to write Markdown: {e}", file=sys.stderr)
        return 1

    print("Snapshot exported:")
    def _format_path(p: Path) -> str:
        try:
            return str(p.relative_to(REPO_ROOT))
        except Exception:
            return str(p)

    print(f"- JSON: {_format_path(json_path)}")
    print(f"- MD:   {_format_path(md_path)}")
    print(f"- URL:  {metrics_url}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
