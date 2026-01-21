#!/usr/bin/env python3
"""
API Snapshot（最小基线快照）

用途：
- 在固定数据集（例如 schema/v2.3/03_sample_data.sql）下，对关键 API 端点生成“可 diff”的 JSON 快照
- 为后续重构/性能优化提供回归锚点（hash + 统计摘要）

示例：
  python3 scripts/api_snapshot.py --base-url http://localhost:8000 --output /tmp/api-snapshot.json

  # 生成更稳定的 baseline（去除波动元信息，并省略完整 JSON body）
  python3 scripts/api_snapshot.py --base-url http://localhost:8000 --deterministic --no-json --pretty \
    --output /tmp/api-snapshot.baseline.json

  # 校验当前后端输出是否与 baseline 一致（与 baseline 对比时会隐式启用 --deterministic --no-json）
  python3 scripts/api_snapshot.py --base-url http://localhost:8000 --check-baseline docs/baselines/api-snapshot.sample.json
"""

from __future__ import annotations

import argparse
import difflib
import hashlib
import json
import subprocess
import sys
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
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


def _stable_json_text(obj: Any) -> str:
    return json.dumps(obj, ensure_ascii=False, indent=2, sort_keys=True) + "\n"


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

    endpoints["genes_options_species_1_limit_5"] = _http_get_json(
        _join(
            base_url,
            "/api/v1/genes/options?"
            + urlencode({"species_id": 1, "gene_type": "lncRNA", "limit": 5}),
        ),
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

    endpoints["stats_top_genes_lncrna_limit_3"] = _http_get_json(
        _join(base_url, "/api/v1/stats/top-genes?" + urlencode({"limit": 3, "gene_type": "lncRNA"})),
        timeout_seconds=timeout_seconds,
    )

    endpoints["stats_top_diseases_limit_3"] = _http_get_json(
        _join(base_url, "/api/v1/stats/top-diseases?" + urlencode({"limit": 3})),
        timeout_seconds=timeout_seconds,
    )

    endpoints["analysis_summary"] = _http_get_json(
        _join(base_url, "/api/v1/analysis/summary"),
        timeout_seconds=timeout_seconds,
    )

    # High-risk list endpoints (sorting/filtering/pagination): keep page_size small for speed.
    endpoints["lncrna_chipseq_overlap_page_chr22_page_size_1_sort_peak_qvalue_asc"] = _http_get_json(
        _join(
            base_url,
            "/api/v1/lncrna-chipseq-overlap?"
            + urlencode(
                {
                    "chromosome": "chr22",
                    "page": 1,
                    "page_size": 1,
                    "sort_by": "peak_qvalue",
                    "sort_order": "asc",
                    # Include records with missing qvalue on small sample datasets.
                    "max_qvalue": 1.0,
                }
            ),
        ),
        timeout_seconds=timeout_seconds,
    )

    endpoints["lncrna_chipseq_overlap_cursor_chr22_page_size_1_sort_peak_qvalue_asc"] = _http_get_json(
        _join(
            base_url,
            "/api/v1/lncrna-chipseq-overlap/cursor?"
            + urlencode(
                {
                    "chromosome": "chr22",
                    "page_size": 1,
                    "sort_by": "peak_qvalue",
                    "sort_order": "asc",
                    "max_qvalue": 1.0,
                }
            ),
        ),
        timeout_seconds=timeout_seconds,
    )

    endpoints["lncrna_chipseq_overlap_statistics_chr22"] = _http_get_json(
        _join(
            base_url,
            "/api/v1/lncrna-chipseq-overlap/statistics?" + urlencode({"chromosome": "chr22", "max_qvalue": 1.0}),
        ),
        timeout_seconds=timeout_seconds,
    )

    # Summaries: keep snapshot stable even if response schema grows.
    def safe_len(value: Any) -> Optional[int]:
        try:
            return len(value)
        except Exception:
            return None

    def get_first_id(items: Any, *, keys: tuple[str, ...]) -> Optional[int]:
        if not isinstance(items, list):
            return None
        for item in items:
            if not isinstance(item, dict):
                continue
            for key in keys:
                value = item.get(key)
                if isinstance(value, int):
                    return value
                if isinstance(value, str) and value.isdigit():
                    return int(value)
        return None

    genes_first_id = None
    summaries: dict[str, Any] = {}
    if endpoints["genes_page_1"].json:
        summaries["genes_total"] = endpoints["genes_page_1"].json.get("total")
        summaries["genes_items_len"] = safe_len(endpoints["genes_page_1"].json.get("items"))
        genes_first_id = get_first_id(
            endpoints["genes_page_1"].json.get("items"),
            keys=("gene_id", "id"),
        )

    if genes_first_id is not None:
        endpoints["genes_detail_first"] = _http_get_json(
            _join(base_url, f"/api/v1/genes/{genes_first_id}"),
            timeout_seconds=timeout_seconds,
        )

    regulations_first_id = None
    if endpoints["regulations_page_1"].json:
        summaries["regulations_total"] = endpoints["regulations_page_1"].json.get("total")
        summaries["regulations_items_len"] = safe_len(endpoints["regulations_page_1"].json.get("items"))
        regulations_first_id = get_first_id(
            endpoints["regulations_page_1"].json.get("items"),
            keys=("regulation_id", "id"),
        )

    if regulations_first_id is not None:
        endpoints["regulation_detail_first"] = _http_get_json(
            _join(base_url, f"/api/v1/regulations/{regulations_first_id}"),
            timeout_seconds=timeout_seconds,
        )

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
    parser.add_argument(
        "--deterministic",
        action="store_true",
        help="Make output stable for baselining (strip varying metadata like timestamps/sha/base_url)",
    )
    parser.add_argument(
        "--no-json",
        action="store_true",
        help="Do not include full JSON bodies (keep status_code/sha256/error only)",
    )
    parser.add_argument(
        "--check-baseline",
        default="",
        help="Compare snapshot against a baseline JSON file and exit non-zero on diff",
    )
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    snap = _snapshot(args.base_url, timeout_seconds=float(args.timeout))

    deterministic = bool(args.deterministic) or bool(args.check_baseline)
    no_json = bool(args.no_json) or bool(args.check_baseline)

    if deterministic:
        # Normalize volatile metadata so outputs can be diffed and committed as baselines.
        snap["generated_at"] = "1970-01-01T00:00:00Z"
        snap["git_sha"] = None
        snap["base_url"] = ""

    if no_json:
        for r in snap.get("endpoints", {}).values():
            if isinstance(r, dict):
                r["json"] = None

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

    if args.check_baseline:
        baseline_path = args.check_baseline
        try:
            baseline_obj = json.loads(Path(baseline_path).read_text(encoding="utf-8"))
        except FileNotFoundError:
            print(f"ERROR: baseline file not found: {baseline_path}", file=sys.stderr)
            return 4
        except Exception as e:
            print(f"ERROR: failed to read baseline: {baseline_path}: {e}", file=sys.stderr)
            return 4

        if baseline_obj != snap:
            expected = _stable_json_text(baseline_obj)
            actual = _stable_json_text(snap)
            diff = "".join(
                difflib.unified_diff(
                    expected.splitlines(True),
                    actual.splitlines(True),
                    fromfile=baseline_path,
                    tofile="generated",
                )
            )
            print("ERROR: baseline mismatch", file=sys.stderr)
            if diff:
                sys.stderr.write(diff)
            return 3

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
