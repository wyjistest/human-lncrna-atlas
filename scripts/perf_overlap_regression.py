#!/usr/bin/env python3
"""
Overlap 性能回归检查（基于 /api/v1/admin/metrics）。

目标：
- 针对 Overlap list/compare 两个端点做“可定位、可回滚”的性能门禁；
- 默认不阻塞 main push，仅用于手动 workflow_dispatch（self-hosted 友好）；
- 仅使用标准库（便于在任意环境快速运行）。

模式：
- generate-baseline：生成 baseline JSON（建议提交到仓库）
- check：与 baseline 对比，若出现明显回归则返回非 0

输出：
- <out-dir>/perf-overlap-<timestamp>.json（compact snapshot）
- <out-dir>/perf-overlap-<timestamp>.md（issue 友好摘要）
- <out-dir>/perf-overlap-raw-metrics-<timestamp>.json（原始 /admin/metrics）
"""

from __future__ import annotations

import argparse
import json
import os
import sys
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Optional
from urllib.error import HTTPError, URLError
from urllib.parse import urlencode
from urllib.request import Request, urlopen


REPO_ROOT = Path(__file__).resolve().parents[1]

OVERLAP_LIST_PATH = "/api/v1/lncrna-chipseq-overlap"
OVERLAP_COMPARE_PATH = "/api/v1/lncrna-chipseq-overlap/compare"

DEFAULT_BASELINE_FILE = REPO_ROOT / "docs" / "baselines" / "performance" / "overlap-admin-metrics.baseline.json"
DEFAULT_BASELINE_RAW_METRICS_FILE = (
    REPO_ROOT / "docs" / "baselines" / "performance" / "overlap-admin-metrics.baseline.raw.json"
)
DEFAULT_OUT_DIR = REPO_ROOT / "docs" / "reports"

DEFAULT_LNCRNA_GENE_ID = 17276
DEFAULT_SPECIES_IDS = "1,3"

DEFAULT_MIN_SAMPLES = 10

DEFAULT_RESPONSE_REGRESSION_PCT = 20.0
DEFAULT_RESPONSE_REGRESSION_ABS_MS = 10.0
DEFAULT_DB_REGRESSION_PCT = 20.0
DEFAULT_DB_REGRESSION_ABS_MS = 2.0


class WarmupRequestError(RuntimeError):
    def __init__(self, url: str, *, status_code: Optional[int], detail: str):
        super().__init__(f"Warmup request failed: {url}: {detail}".strip())
        self.url = url
        self.status_code = status_code
        self.detail = detail


@dataclass(frozen=True)
class JsonResult:
    status_code: int
    json: Any


def _iso_ts() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H-%M-%SZ")


def _stable_json_text(obj: Any) -> str:
    return json.dumps(obj, ensure_ascii=False, indent=2, sort_keys=True) + "\n"


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


def _ensure_default_no_proxy() -> None:
    # 兼容本地代理环境：默认绕过 localhost/127.0.0.1，避免请求走 http_proxy 导致连接失败/卡住。
    if not os.environ.get("NO_PROXY") and not os.environ.get("no_proxy"):
        default_no_proxy = "127.0.0.1,localhost,::1"
        os.environ["NO_PROXY"] = default_no_proxy
        os.environ["no_proxy"] = default_no_proxy


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


def _fetch_json_result(url: str, *, timeout_seconds: float) -> JsonResult:
    req = Request(url, headers={"Accept": "application/json"}, method="GET")
    try:
        with urlopen(req, timeout=timeout_seconds) as resp:
            body = resp.read()
            status_code = int(resp.getcode())
    except HTTPError as e:
        status_code = int(e.code)
        try:
            body = e.read()
        except Exception:
            body = b""
    except URLError as e:
        raise RuntimeError(f"Network error fetching {url}: {e}") from e

    text = body.decode("utf-8", errors="replace")
    if not text.strip():
        return JsonResult(status_code=status_code, json=None)

    try:
        return JsonResult(status_code=status_code, json=json.loads(text))
    except json.JSONDecodeError:
        return JsonResult(status_code=status_code, json=None)


def _pick_lncrna_gene_id_with_core_id(
    *,
    base_url: str,
    species_id: int,
    timeout_seconds: float,
) -> Optional[int]:
    options_url = f"{base_url}/api/v1/genes/options?{urlencode({'species_id': species_id, 'gene_type': 'lncRNA', 'limit': 5})}"
    options = _fetch_json_result(options_url, timeout_seconds=timeout_seconds)
    if options.status_code != 200 or not isinstance(options.json, dict):
        return None

    genes = options.json.get("genes")
    if not isinstance(genes, list):
        return None

    candidate_gene_ids: list[int] = []
    for row in genes[:5]:
        if not isinstance(row, dict):
            continue
        gene_id = _to_int(row.get("gene_id"))
        if gene_id is None or gene_id < 1:
            continue
        candidate_gene_ids.append(gene_id)

    # 确定性：options 结果可能受后端排序/索引变化影响，这里统一按 gene_id 升序挑选。
    candidate_gene_ids = sorted(set(candidate_gene_ids))

    for gene_id in candidate_gene_ids:
        detail = _fetch_json_result(f"{base_url}/api/v1/genes/{gene_id}", timeout_seconds=timeout_seconds)
        if detail.status_code != 200 or not isinstance(detail.json, dict):
            continue
        if detail.json.get("core_id") is None:
            continue
        return gene_id

    return None


def _warmup_get(url: str, *, timeout_seconds: float) -> None:
    req = Request(url, headers={"Accept": "application/json"}, method="GET")
    try:
        with urlopen(req, timeout=timeout_seconds) as resp:
            resp.read()
    except HTTPError as e:
        raise WarmupRequestError(url, status_code=int(e.code), detail=str(e)) from e
    except Exception as e:
        raise WarmupRequestError(url, status_code=None, detail=str(e)) from e


def _parse_species_ids(text: str) -> list[int]:
    raw = (text or "").strip()
    if not raw:
        raise ValueError("species_ids is empty")

    parts = []
    for part in raw.replace(" ", "").split(","):
        if not part:
            continue
        parts.append(part)

    ids: list[int] = []
    for part in parts:
        try:
            value = int(part)
        except Exception as e:
            raise ValueError(f"Invalid species id: {part}") from e
        if value <= 0:
            raise ValueError(f"Invalid species id (must be positive): {value}")
        ids.append(value)

    if not ids:
        raise ValueError("species_ids parsed to empty list")
    return ids


@dataclass(frozen=True)
class EndpointCompact:
    path: str
    requests: int
    response_p95_ms: float
    response_p99_ms: float
    db_p95_ms: float
    db_p99_ms: float


def _extract_endpoint(metrics: dict[str, Any], path: str) -> Optional[EndpointCompact]:
    endpoints = metrics.get("endpoints") or []
    if not isinstance(endpoints, list):
        return None

    want = str(path or "").rstrip("/")
    for ep in endpoints:
        if not isinstance(ep, dict):
            continue
        got = str(ep.get("path", "") or "").rstrip("/")
        if got != want:
            continue

        requests = _to_int(ep.get("requests")) or 0
        percentiles = ep.get("percentiles") or {}
        db_percentiles = ep.get("db_percentiles") or {}
        if not isinstance(percentiles, dict) or not isinstance(db_percentiles, dict):
            return None

        resp_p95 = _to_float(percentiles.get("p95_ms"))
        resp_p99 = _to_float(percentiles.get("p99_ms"))
        db_p95 = _to_float(db_percentiles.get("p95_ms"))
        db_p99 = _to_float(db_percentiles.get("p99_ms"))
        if resp_p95 is None or resp_p99 is None or db_p95 is None or db_p99 is None:
            return None

        return EndpointCompact(
            path=want,
            requests=requests,
            response_p95_ms=float(resp_p95),
            response_p99_ms=float(resp_p99),
            db_p95_ms=float(db_p95),
            db_p99_ms=float(db_p99),
        )

    return None


def _warmup_overlap(
    *,
    base_url: str,
    lncrna_gene_id: int,
    species_ids: list[int],
    warmup_rounds: int,
    timeout_seconds: float,
) -> None:
    if warmup_rounds <= 0:
        return

    first_species = species_ids[0]
    compare_species = ",".join(str(x) for x in species_ids)

    for _ in range(int(warmup_rounds)):
        list_url = f"{base_url}{OVERLAP_LIST_PATH}?{urlencode({'lncrna_gene_id': lncrna_gene_id, 'species_id': first_species})}"
        compare_url = f"{base_url}{OVERLAP_COMPARE_PATH}?{urlencode({'lncrna_gene_id': lncrna_gene_id, 'species_ids': compare_species})}"
        _warmup_get(list_url, timeout_seconds=timeout_seconds)
        _warmup_get(compare_url, timeout_seconds=timeout_seconds)


def _build_compact_snapshot(
    *,
    raw_metrics: dict[str, Any],
    base_url: str,
    mode: str,
    baseline_file: Path,
    baseline_raw_metrics_file: Optional[Path],
    lncrna_gene_id: int,
    lncrna_gene_id_requested: int,
    lncrna_gene_id_source: str,
    species_ids: list[int],
    warmup_rounds: int,
    min_samples: int,
    response_regression_pct: float,
    response_regression_abs_ms: float,
    db_regression_pct: float,
    db_regression_abs_ms: float,
    generated_at: str,
) -> dict[str, Any]:
    def path_meta(p: Optional[Path]) -> Optional[str]:
        if p is None:
            return None
        resolved = p.resolve()
        try:
            return resolved.relative_to(REPO_ROOT).as_posix()
        except ValueError:
            return resolved.as_posix()

    baseline_file_meta = path_meta(baseline_file)
    baseline_raw_metrics_file_meta = path_meta(baseline_raw_metrics_file)

    endpoints: dict[str, Any] = {}

    for path in (OVERLAP_LIST_PATH, OVERLAP_COMPARE_PATH):
        ep = _extract_endpoint(raw_metrics, path)
        if ep is None:
            endpoints[path] = None
            continue
        endpoints[path] = {
            "requests": ep.requests,
            "response": {"p95_ms": ep.response_p95_ms, "p99_ms": ep.response_p99_ms},
            "db": {"p95_ms": ep.db_p95_ms, "p99_ms": ep.db_p99_ms},
        }

    return {
        "meta": {
            "schema_version": 1,
            "status": "CANDIDATE" if mode == "check" else "SET",
            "generated_at": generated_at,
            "base_url": base_url,
            "baseline_file": baseline_file_meta,
            "baseline_raw_metrics_file": baseline_raw_metrics_file_meta,
            "scenario": {
                "lncrna_gene_id": lncrna_gene_id,
                "lncrna_gene_id_requested": lncrna_gene_id_requested,
                "lncrna_gene_id_source": lncrna_gene_id_source,
                "species_ids": species_ids,
                "warmup_rounds": warmup_rounds,
                "min_samples": min_samples,
            },
            "thresholds": {
                "response": {"pct": response_regression_pct, "abs_ms": response_regression_abs_ms},
                "db": {"pct": db_regression_pct, "abs_ms": db_regression_abs_ms},
            },
        },
        "endpoints": endpoints,
    }


def _require_endpoint_samples(snapshot: dict[str, Any], *, label: str, min_samples: int) -> None:
    endpoints = snapshot.get("endpoints")
    if not isinstance(endpoints, dict):
        raise RuntimeError(f"{label}: invalid endpoints field")

    for path in (OVERLAP_LIST_PATH, OVERLAP_COMPARE_PATH):
        row = endpoints.get(path)
        if not isinstance(row, dict):
            raise RuntimeError(f"{label}: missing endpoint stats: {path}")
        requests = _to_int(row.get("requests")) or 0
        if requests < min_samples:
            raise RuntimeError(f"{label}: insufficient samples for {path}: requests={requests} (<{min_samples})")

        resp = row.get("response")
        db = row.get("db")
        if not isinstance(resp, dict) or not isinstance(db, dict):
            raise RuntimeError(f"{label}: missing percentile fields for {path}")

        for k in ("p95_ms", "p99_ms"):
            if _to_float(resp.get(k)) is None:
                raise RuntimeError(f"{label}: missing response.{k} for {path}")
            if _to_float(db.get(k)) is None:
                raise RuntimeError(f"{label}: missing db.{k} for {path}")


def _fmt_ms(v: Optional[float]) -> str:
    if v is None:
        return "-"
    return f"{v:.2f}ms"


def _fmt_change(old: float, new: float) -> str:
    delta = new - old
    pct = (delta / old * 100.0) if old > 0 else float("inf")
    sign = "+" if delta > 0 else ""
    pct_s = f"{pct:.1f}%" if pct != float("inf") else "inf%"
    return f"{_fmt_ms(old)} → {_fmt_ms(new)} ({sign}{_fmt_ms(delta)}, {sign}{pct_s})"


def _gate_regressions(
    baseline: dict[str, Any],
    current: dict[str, Any],
    *,
    response_pct_th: float,
    response_abs_th: float,
    db_pct_th: float,
    db_abs_th: float,
) -> tuple[bool, list[str]]:
    failures: list[str] = []

    base_eps = baseline.get("endpoints") or {}
    cur_eps = current.get("endpoints") or {}
    if not isinstance(base_eps, dict) or not isinstance(cur_eps, dict):
        return False, ["Invalid snapshot endpoints field"]

    def check_one(path: str, *, kind: str, metric: str, pct_th: float, abs_th: float) -> None:
        base_row = base_eps.get(path) or {}
        cur_row = cur_eps.get(path) or {}
        if not isinstance(base_row, dict) or not isinstance(cur_row, dict):
            failures.append(f"[ERROR] missing endpoint stats for {path}")
            return

        base_v = _to_float(((base_row.get(kind) or {}).get(metric) if isinstance(base_row.get(kind), dict) else None))
        cur_v = _to_float(((cur_row.get(kind) or {}).get(metric) if isinstance(cur_row.get(kind), dict) else None))
        if base_v is None or cur_v is None or base_v <= 0:
            failures.append(f"[ERROR] missing/invalid baseline/current value for {path} {kind}.{metric}")
            return

        delta = cur_v - base_v
        if delta <= 0:
            return

        pct = delta / base_v * 100.0
        if pct > pct_th and delta > abs_th:
            failures.append(
                f"[REGRESSION] {path} {kind}.{metric}: {_fmt_ms(base_v)} -> {_fmt_ms(cur_v)} "
                f"(+{delta:.2f}ms, +{pct:.1f}%; gate: >{pct_th:.0f}% and >{abs_th:.0f}ms)"
            )

    for path in (OVERLAP_LIST_PATH, OVERLAP_COMPARE_PATH):
        for metric in ("p95_ms", "p99_ms"):
            check_one(path, kind="response", metric=metric, pct_th=response_pct_th, abs_th=response_abs_th)
            check_one(path, kind="db", metric=metric, pct_th=db_pct_th, abs_th=db_abs_th)

    return not failures, failures


def _build_markdown(
    *,
    mode: str,
    base_url: str,
    generated_at: str,
    baseline_file: Path,
    baseline: Optional[dict[str, Any]],
    current: dict[str, Any],
    ok: bool,
    failures: list[str],
    admin_metrics_diff_path: Optional[Path],
    min_samples: int,
    response_regression_pct: float,
    response_regression_abs_ms: float,
    db_regression_pct: float,
    db_regression_abs_ms: float,
) -> str:
    lines: list[str] = [
        "# Overlap Performance Regression",
        "",
        f"- **mode**: `{mode}`",
        f"- **generated_at**: `{generated_at}`",
        f"- **base_url**: `{base_url}`",
        f"- **baseline_file**: `{baseline_file}`",
        f"- **admin_metrics_diff**: `{admin_metrics_diff_path}`" if admin_metrics_diff_path else None,
        f"- **result**: {'✅ PASS' if ok else '❌ FAIL'}",
        "",
        "## Gate",
        "",
        f"- min_samples: `{min_samples}`",
        f"- response: `>{response_regression_pct:.0f}%` AND `>{response_regression_abs_ms:.0f}ms`",
        f"- db: `>{db_regression_pct:.0f}%` AND `>{db_regression_abs_ms:.0f}ms`",
        "",
        "## Endpoints",
        "",
    ]

    def row(snapshot: dict[str, Any], path: str) -> dict[str, Any]:
        eps = snapshot.get("endpoints") or {}
        if not isinstance(eps, dict):
            return {}
        raw = eps.get(path) or {}
        return raw if isinstance(raw, dict) else {}

    for path in (OVERLAP_LIST_PATH, OVERLAP_COMPARE_PATH):
        cur = row(current, path)
        base = row(baseline, path) if baseline else {}

        lines.append(f"### `{path}`")
        lines.append("")
        lines.append(f"- requests: `{_to_int(base.get('requests')) if baseline else '-'} → {_to_int(cur.get('requests'))}`")

        for kind, label in (("response", "response"), ("db", "db")):
            base_kind = base.get(kind) if isinstance(base.get(kind), dict) else {}
            cur_kind = cur.get(kind) if isinstance(cur.get(kind), dict) else {}
            base_p95 = _to_float((base_kind or {}).get("p95_ms")) if baseline else None
            base_p99 = _to_float((base_kind or {}).get("p99_ms")) if baseline else None
            cur_p95 = _to_float((cur_kind or {}).get("p95_ms"))
            cur_p99 = _to_float((cur_kind or {}).get("p99_ms"))

            if baseline and base_p95 is not None and cur_p95 is not None and base_p95 > 0:
                lines.append(f"- {label}.p95_ms: {_fmt_change(base_p95, cur_p95)}")
            else:
                lines.append(f"- {label}.p95_ms: {_fmt_ms(base_p95)} → {_fmt_ms(cur_p95)}")

            if baseline and base_p99 is not None and cur_p99 is not None and base_p99 > 0:
                lines.append(f"- {label}.p99_ms: {_fmt_change(base_p99, cur_p99)}")
            else:
                lines.append(f"- {label}.p99_ms: {_fmt_ms(base_p99)} → {_fmt_ms(cur_p99)}")

        lines.append("")

    lines.append("## Findings")
    lines.append("")
    if ok:
        lines.append("- ✅ No gated regressions detected.")
    else:
        for f in failures:
            lines.append(f"- {f}")
    lines.append("")

    return "\n".join([x for x in lines if x is not None])


def _load_json_file(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def _resolve_path(path_str: str) -> Path:
    path = Path(path_str).expanduser()
    if path.is_absolute():
        return path
    return (REPO_ROOT / path).resolve()


def _parse_args() -> argparse.Namespace:
    env_base_url = os.environ.get("API_BASE_URL") or ""
    default_base_url = env_base_url.strip() or "http://localhost:8000"

    env_admin_api_key = os.environ.get("ADMIN_API_KEY") or ""
    default_admin_api_key = env_admin_api_key.strip() or None

    parser = argparse.ArgumentParser(description="Overlap performance regression gate (based on /api/v1/admin/metrics).")
    parser.add_argument(
        "cmd",
        choices=["check", "generate-baseline"],
        help="Run mode: check (gate regressions) | generate-baseline (write baseline JSON).",
    )
    parser.add_argument(
        "--base-url",
        default=default_base_url,
        help="Backend base url (default: $API_BASE_URL or http://localhost:8000)",
    )
    parser.add_argument(
        "--admin-api-key",
        default=default_admin_api_key,
        help="Admin API Key for /api/v1/admin/metrics (sent as X-Admin-API-Key; default: $ADMIN_API_KEY)",
    )
    parser.add_argument(
        "--out-dir",
        default=str(DEFAULT_OUT_DIR),
        help="Output directory for reports (default: docs/reports)",
    )
    parser.add_argument(
        "--baseline-file",
        default=str(DEFAULT_BASELINE_FILE),
        help="Baseline JSON file (default: docs/baselines/performance/overlap-admin-metrics.baseline.json)",
    )
    parser.add_argument(
        "--baseline-raw-metrics-file",
        default="",
        help=(
            "Optional: committed baseline raw /api/v1/admin/metrics JSON for localization diff. "
            "Empty disables. Recommended: docs/baselines/performance/overlap-admin-metrics.baseline.raw.json"
        ),
    )
    parser.add_argument(
        "--emit-admin-metrics-diff",
        action="store_true",
        help="Emit admin-metrics diff even when gate passes (requires --baseline-raw-metrics-file).",
    )
    parser.add_argument("--warmup-rounds", type=int, default=20, help="Warmup rounds before snapshot (default: 20).")
    parser.add_argument(
        "--lncrna-gene-id",
        type=int,
        default=DEFAULT_LNCRNA_GENE_ID,
        help=f"lncRNA gene id for warmup (default: {DEFAULT_LNCRNA_GENE_ID})",
    )
    parser.add_argument(
        "--species-ids",
        default=DEFAULT_SPECIES_IDS,
        help=f"CSV species ids for compare warmup (default: {DEFAULT_SPECIES_IDS})",
    )
    parser.add_argument("--timeout-seconds", type=float, default=10.0, help="HTTP timeout seconds (default: 10).")
    parser.add_argument(
        "--min-samples",
        type=int,
        default=DEFAULT_MIN_SAMPLES,
        help="Minimum samples required per endpoint in /api/v1/admin/metrics (default: 10).",
    )
    parser.add_argument(
        "--response-regression-pct",
        type=float,
        default=DEFAULT_RESPONSE_REGRESSION_PCT,
        help="Gate response regressions when delta_pct > this threshold (default: 20).",
    )
    parser.add_argument(
        "--response-regression-abs-ms",
        type=float,
        default=DEFAULT_RESPONSE_REGRESSION_ABS_MS,
        help="Gate response regressions when delta_ms > this threshold (default: 10).",
    )
    parser.add_argument(
        "--db-regression-pct",
        type=float,
        default=DEFAULT_DB_REGRESSION_PCT,
        help="Gate DB regressions when delta_pct > this threshold (default: 20).",
    )
    parser.add_argument(
        "--db-regression-abs-ms",
        type=float,
        default=DEFAULT_DB_REGRESSION_ABS_MS,
        help="Gate DB regressions when delta_ms > this threshold (default: 2).",
    )
    return parser.parse_args()


def main() -> int:
    _ensure_default_no_proxy()
    args = _parse_args()

    base_url = str(args.base_url or "").rstrip("/")
    admin_api_key = str(args.admin_api_key).strip() if args.admin_api_key else None

    out_dir = _resolve_path(str(args.out_dir))
    out_dir.mkdir(parents=True, exist_ok=True)

    baseline_file = _resolve_path(str(args.baseline_file))
    baseline_file.parent.mkdir(parents=True, exist_ok=True)

    raw_baseline_str = str(args.baseline_raw_metrics_file or "").strip()
    baseline_raw_metrics_file = _resolve_path(raw_baseline_str) if raw_baseline_str else None
    if baseline_raw_metrics_file is not None:
        baseline_raw_metrics_file.parent.mkdir(parents=True, exist_ok=True)

    try:
        species_ids = _parse_species_ids(str(args.species_ids))
    except Exception as e:
        print(f"[ERROR] {e}", file=sys.stderr)
        return 2

    ts = _iso_ts()
    min_samples = max(1, int(args.min_samples))
    response_regression_pct = float(args.response_regression_pct)
    response_regression_abs_ms = float(args.response_regression_abs_ms)
    db_regression_pct = float(args.db_regression_pct)
    db_regression_abs_ms = float(args.db_regression_abs_ms)

    # 1) Warmup traffic (best effort but required for stable percentiles)
    requested_lncrna_gene_id = int(args.lncrna_gene_id)
    resolved_lncrna_gene_id = requested_lncrna_gene_id
    lncrna_gene_id_source = "requested"
    try:
        _warmup_overlap(
            base_url=base_url,
            lncrna_gene_id=resolved_lncrna_gene_id,
            species_ids=species_ids,
            warmup_rounds=int(args.warmup_rounds),
            timeout_seconds=float(args.timeout_seconds),
        )
    except WarmupRequestError as e:
        is_compare = OVERLAP_COMPARE_PATH in (e.url or "")
        if is_compare and e.status_code in (400, 404, 422):
            picked = _pick_lncrna_gene_id_with_core_id(
                base_url=base_url,
                species_id=species_ids[0],
                timeout_seconds=float(args.timeout_seconds),
            )
            if picked is not None:
                resolved_lncrna_gene_id = picked
                lncrna_gene_id_source = "auto"
                print(
                    f"[WARN] warmup compare failed for gene_id={requested_lncrna_gene_id} "
                    f"(HTTP {e.status_code}); auto-picking gene_id={picked} from /api/v1/genes/options",
                    file=sys.stderr,
                )
                try:
                    _warmup_overlap(
                        base_url=base_url,
                        lncrna_gene_id=resolved_lncrna_gene_id,
                        species_ids=species_ids,
                        warmup_rounds=int(args.warmup_rounds),
                        timeout_seconds=float(args.timeout_seconds),
                    )
                except Exception as e2:
                    print(f"[ERROR] {e2}", file=sys.stderr)
                    return 2
            else:
                print(f"[ERROR] {e}", file=sys.stderr)
                print(
                    "[HINT] The provided lncrna_gene_id may not exist in this DB. "
                    "Provide a valid --lncrna-gene-id, or ensure /api/v1/genes/options is available.",
                    file=sys.stderr,
                )
                return 2
        else:
            print(f"[ERROR] {e}", file=sys.stderr)
            return 2
    except Exception as e:
        print(f"[ERROR] {e}", file=sys.stderr)
        return 2

    # 2) Fetch metrics
    metrics_url = f"{base_url}/api/v1/admin/metrics"
    try:
        raw_metrics = _fetch_json(metrics_url, admin_api_key=admin_api_key, timeout_seconds=float(args.timeout_seconds))
    except Exception as e:
        print(f"[ERROR] {e}", file=sys.stderr)
        return 2

    raw_path = out_dir / f"perf-overlap-raw-metrics-{ts}.json"
    raw_path.write_text(_stable_json_text(raw_metrics), encoding="utf-8")
    if args.cmd == "generate-baseline" and baseline_raw_metrics_file is not None:
        baseline_raw_metrics_file.write_text(_stable_json_text(raw_metrics), encoding="utf-8")

    # 3) Build compact snapshot
    current = _build_compact_snapshot(
        raw_metrics=raw_metrics,
        base_url=base_url,
        mode=str(args.cmd),
        baseline_file=baseline_file,
        baseline_raw_metrics_file=baseline_raw_metrics_file,
        lncrna_gene_id=resolved_lncrna_gene_id,
        lncrna_gene_id_requested=requested_lncrna_gene_id,
        lncrna_gene_id_source=lncrna_gene_id_source,
        species_ids=species_ids,
        warmup_rounds=int(args.warmup_rounds),
        min_samples=min_samples,
        response_regression_pct=response_regression_pct,
        response_regression_abs_ms=response_regression_abs_ms,
        db_regression_pct=db_regression_pct,
        db_regression_abs_ms=db_regression_abs_ms,
        generated_at=ts,
    )

    snap_path = out_dir / f"perf-overlap-{ts}.json"
    snap_path.write_text(_stable_json_text(current), encoding="utf-8")

    if args.cmd == "generate-baseline":
        try:
            _require_endpoint_samples(current, label="current", min_samples=min_samples)
        except Exception as e:
            print(f"[ERROR] {e}", file=sys.stderr)
            return 3

        baseline = json.loads(_stable_json_text(current))
        baseline_meta = baseline.get("meta") if isinstance(baseline.get("meta"), dict) else {}
        if isinstance(baseline_meta, dict):
            baseline_meta["status"] = "SET"
            baseline_meta["generated_at"] = ts
            baseline["meta"] = baseline_meta

        baseline_file.write_text(_stable_json_text(baseline), encoding="utf-8")

        md = _build_markdown(
            mode="generate-baseline",
            base_url=base_url,
            generated_at=ts,
            baseline_file=baseline_file,
            baseline=None,
            current=current,
            ok=True,
            failures=[],
            admin_metrics_diff_path=None,
            min_samples=min_samples,
            response_regression_pct=response_regression_pct,
            response_regression_abs_ms=response_regression_abs_ms,
            db_regression_pct=db_regression_pct,
            db_regression_abs_ms=db_regression_abs_ms,
        )
        md_path = out_dir / f"perf-overlap-{ts}.md"
        md_path.write_text(md, encoding="utf-8")
        print(f"[OK] Baseline generated: {baseline_file}")
        if baseline_raw_metrics_file is not None:
            print(f"[OK] Baseline raw metrics: {baseline_raw_metrics_file}")
        print(f"[OK] Report: {md_path}")
        return 0

    # check mode
    if not baseline_file.exists():
        print(f"[ERROR] baseline file not found: {baseline_file}", file=sys.stderr)
        return 2

    try:
        baseline = _load_json_file(baseline_file)
    except Exception as e:
        print(f"[ERROR] failed to read baseline: {baseline_file}: {e}", file=sys.stderr)
        return 2

    meta = baseline.get("meta") or {}
    status = str((meta.get("status") if isinstance(meta, dict) else "") or "").strip().upper()
    if status == "UNSET":
        print(f"[ERROR] baseline is UNSET: {baseline_file}", file=sys.stderr)
        print("[HINT] Run: python3 scripts/perf_overlap_regression.py generate-baseline ... then commit baseline.", file=sys.stderr)
        return 3

    try:
        _require_endpoint_samples(baseline, label="baseline", min_samples=min_samples)
        _require_endpoint_samples(current, label="current", min_samples=min_samples)
    except Exception as e:
        print(f"[ERROR] {e}", file=sys.stderr)
        return 3

    ok, failures = _gate_regressions(
        baseline,
        current,
        response_pct_th=response_regression_pct,
        response_abs_th=response_regression_abs_ms,
        db_pct_th=db_regression_pct,
        db_abs_th=db_regression_abs_ms,
    )

    admin_metrics_diff_path: Optional[Path] = None
    emit_diff = bool(args.emit_admin_metrics_diff) or (not ok)
    if emit_diff and baseline_raw_metrics_file is not None:
        if baseline_raw_metrics_file.exists():
            try:
                # Import lazily to avoid any accidental side effects and keep check fast when diff is disabled.
                from admin_metrics_snapshot import build_diff_markdown  # type: ignore

                old_raw = _load_json_file(baseline_raw_metrics_file)
                diff_md = build_diff_markdown(
                    old_raw,
                    raw_metrics,
                    old_label=str(baseline_raw_metrics_file),
                    new_label=str(raw_path),
                    generated_at=ts,
                )
                admin_metrics_diff_path = out_dir / f"perf-overlap-admin-metrics-diff-{ts}.md"
                admin_metrics_diff_path.write_text(diff_md, encoding="utf-8")
            except Exception as e:
                print(f"[WARN] Failed to generate admin-metrics diff: {e}", file=sys.stderr)
        else:
            print(
                f"[WARN] baseline raw metrics file not found (skip diff): {baseline_raw_metrics_file}",
                file=sys.stderr,
            )

    md = _build_markdown(
        mode="check",
        base_url=base_url,
        generated_at=ts,
        baseline_file=baseline_file,
        baseline=baseline,
        current=current,
        ok=ok,
        failures=failures,
        admin_metrics_diff_path=admin_metrics_diff_path,
        min_samples=min_samples,
        response_regression_pct=response_regression_pct,
        response_regression_abs_ms=response_regression_abs_ms,
        db_regression_pct=db_regression_pct,
        db_regression_abs_ms=db_regression_abs_ms,
    )
    md_path = out_dir / f"perf-overlap-{ts}.md"
    md_path.write_text(md, encoding="utf-8")

    if ok:
        print(f"[OK] No gated regressions. Report: {md_path}")
        if admin_metrics_diff_path is not None:
            print(f"[OK] Admin metrics diff: {admin_metrics_diff_path}")
        return 0

    for f in failures:
        print(f, file=sys.stderr)
    print(f"[FAIL] Gated regressions detected. Report: {md_path}", file=sys.stderr)
    if admin_metrics_diff_path is not None:
        print(f"[INFO] Admin metrics diff: {admin_metrics_diff_path}", file=sys.stderr)
    return 3


if __name__ == "__main__":
    raise SystemExit(main())
