#!/usr/bin/env python3
"""
Admin metrics 快照导出器（JSON + Issue 友好 Markdown）。

目标：
- 用 1 次导出在 issue 中复现“哪条端点慢、慢在 DB 还是业务/缓存、慢查询是什么”。
- 不依赖额外三方库（仅使用标准库），便于在任意环境快速跑。

用法示例：
  python3 scripts/admin_metrics_snapshot.py --base-url http://localhost:8000
  python3 scripts/admin_metrics_snapshot.py --base-url http://localhost:8000 --admin-api-key "$ADMIN_API_KEY"

输出：
- docs/reports/admin-metrics-<timestamp>.json
- docs/reports/admin-metrics-<timestamp>.md
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
        "- 如果 Response P95 很高但 DB P95 很低：优先看 cache namespaces 的 compute_* 与热点 keys（可能是回源/计算/IO）。",
        "- 如果 DB P95 很高：优先看慢查询榜单（fingerprint+route）定位具体 SQL 与触发端点。",
        "- `n=<samples>/10` 代表样本不足，建议先制造少量流量再导出。",
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
    args = parser.parse_args()

    base_url = str(args.base_url or "").rstrip("/")
    metrics_url = f"{base_url}/api/v1/admin/metrics"

    ts = _iso_ts()
    out_dir = Path(args.out_dir).expanduser()
    if not out_dir.is_absolute():
        out_dir = (REPO_ROOT / out_dir).resolve()
    out_dir.mkdir(parents=True, exist_ok=True)

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
