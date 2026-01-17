#!/usr/bin/env python3
"""
API Snapshot（最小基线快照）

用途：
- 在固定数据集（例如 schema/v2.3/03_sample_data.sql）下，对关键 API 端点生成“可 diff”的 JSON 快照
- 为后续重构/性能优化提供回归锚点（hash + 统计摘要）

示例：
  python3 scripts/api_snapshot.py --base-url http://localhost:8000 --output /tmp/api-snapshot.json
"""

from __future__ import annotations

import argparse
import hashlib
import json
import subprocess
import sys
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Any, Optional
from urllib.parse import urlencode
from urllib.request import Request, urlopen


def _iso_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _git_sha() -> Optional[str]:
    try:
        sha = subprocess.check_output(["git", "rev-parse", "HEAD"], stderr=subprocess.DEVNULL).decode().strip()
        return sha or None
    except Exception:
        return None


def _stable_json_bytes(obj: Any) -> bytes:
    return json.dumps(obj, sort_keys=True, separators=(",", ":"), ensure_ascii=False).encode("utf-8")


def _sha256_hex(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


@dataclass(frozen=True)
class EndpointResult:
    status_code: int
    json: Optional[Any]
    sha256: Optional[str]
    error: Optional[str]


def _http_get_json(url: str, *, timeout_seconds: float) -> EndpointResult:
    req = Request(url, headers={"Accept": "application/json"}, method="GET")
    try:
        with urlopen(req, timeout=timeout_seconds) as resp:
            status = int(getattr(resp, "status", 200))
            body = resp.read()
        try:
            parsed = json.loads(body.decode("utf-8"))
        except Exception as e:
            return EndpointResult(status_code=status, json=None, sha256=None, error=f"invalid_json: {e}")
        digest = _sha256_hex(_stable_json_bytes(parsed))
        return EndpointResult(status_code=status, json=parsed, sha256=digest, error=None)
    except Exception as e:
        return EndpointResult(status_code=0, json=None, sha256=None, error=str(e))


def _join(base_url: str, path: str) -> str:
    return base_url.rstrip("/") + path


def _snapshot(base_url: str, *, timeout_seconds: float) -> dict[str, Any]:
    endpoints: dict[str, EndpointResult] = {}

    # Root health (no prefix)
    endpoints["health"] = _http_get_json(_join(base_url, "/health"), timeout_seconds=timeout_seconds)

    # Core API endpoints (should exist on minimal sample data)
    endpoints["stats_overview"] = _http_get_json(
        _join(base_url, "/api/v1/stats/overview"),
        timeout_seconds=timeout_seconds,
    )

    endpoints["genes_page_1"] = _http_get_json(
        _join(base_url, "/api/v1/genes?" + urlencode({"page": 1, "page_size": 1, "species_id": 1})),
        timeout_seconds=timeout_seconds,
    )

    endpoints["regulations_page_1"] = _http_get_json(
        _join(base_url, "/api/v1/regulations?" + urlencode({"page": 1, "page_size": 1, "species_id": 1})),
        timeout_seconds=timeout_seconds,
    )

    endpoints["diseases_options"] = _http_get_json(
        _join(base_url, "/api/v1/diseases/options"),
        timeout_seconds=timeout_seconds,
    )

    # Summaries: keep snapshot stable even if response schema grows.
    def safe_len(value: Any) -> Optional[int]:
        try:
            return len(value)
        except Exception:
            return None

    summaries: dict[str, Any] = {}
    if endpoints["genes_page_1"].json:
        summaries["genes_total"] = endpoints["genes_page_1"].json.get("total")
        summaries["genes_items_len"] = safe_len(endpoints["genes_page_1"].json.get("items"))
    if endpoints["regulations_page_1"].json:
        summaries["regulations_total"] = endpoints["regulations_page_1"].json.get("total")
        summaries["regulations_items_len"] = safe_len(endpoints["regulations_page_1"].json.get("items"))
    if endpoints["diseases_options"].json:
        summaries["traits_len"] = safe_len(endpoints["diseases_options"].json.get("traits"))

    return {
        "generated_at": _iso_now(),
        "git_sha": _git_sha(),
        "base_url": base_url,
        "summaries": summaries,
        "endpoints": {
            name: {
                "status_code": r.status_code,
                "sha256": r.sha256,
                "error": r.error,
                "json": r.json,
            }
            for name, r in endpoints.items()
        },
    }


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Generate deterministic API snapshot baseline (JSON).")
    parser.add_argument(
        "--base-url",
        default="http://localhost:8000",
        help="Backend base URL (default: http://localhost:8000)",
    )
    parser.add_argument(
        "--timeout",
        type=float,
        default=10.0,
        help="Per-request timeout seconds (default: 10)",
    )
    parser.add_argument(
        "--output",
        default="",
        help="Write snapshot to file (default: stdout)",
    )
    parser.add_argument(
        "--pretty",
        action="store_true",
        help="Pretty-print JSON (default: false)",
    )
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    snap = _snapshot(args.base_url, timeout_seconds=float(args.timeout))

    data = json.dumps(snap, ensure_ascii=False, indent=2 if args.pretty else None, sort_keys=True)
    if args.output:
        with open(args.output, "w", encoding="utf-8") as f:
            f.write(data)
            f.write("\n")
        print(f"Wrote snapshot: {args.output}")
    else:
        sys.stdout.write(data + "\n")

    # Non-zero exit if any endpoint failed (status_code==0 or error set).
    failures = [
        name
        for name, r in snap["endpoints"].items()
        if r["status_code"] == 0 or r["error"] is not None
    ]
    if failures:
        print(f"ERROR: snapshot failures: {', '.join(failures)}", file=sys.stderr)
        return 2
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

