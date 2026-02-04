#!/usr/bin/env bash
set -euo pipefail

# 目的：
# - 确保 perf regression 报告包含“Scenario Drift（baseline vs current）”差异提示，
#   便于在门禁失败时快速判断是否存在“参数不一致导致对比失真”的情况。
#
# 覆盖：
# - Overlap / Genes-Regulations 两个 perf gate 脚本的 _build_markdown 输出

unset GIT_DIR GIT_WORK_TREE

REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"

if ! command -v python3 >/dev/null 2>&1; then
  echo "missing dependency: python3" >&2
  exit 1
fi

cd "$REPO_ROOT"

python3 - <<'PY'
import sys
from pathlib import Path

sys.path.insert(0, "scripts")

import perf_overlap_regression as overlap
import perf_genes_regulations_regression as genes_regs


def assert_contains(text: str, needle: str) -> None:
    if needle not in text:
        raise SystemExit(f"missing substring: {needle}\n---\n{text}\n---")


baseline_overlap = {
    "meta": {
        "scenario": {
            "lncrna_gene_id": 17276,
            "lncrna_gene_id_requested": 17276,
            "lncrna_gene_id_source": "default",
            "species_ids": [1, 3],
            "pre_warmup_rounds": 0,
            "warmup_rounds": 30,
            "warmup_max_retries": 2,
            "warmup_retry_base_sleep_ms": 200,
            "min_samples": 20,
        },
        "thresholds": {
            "response": {"pct": 8.0, "abs_ms": 4.0},
            "db": {"pct": 8.0, "abs_ms": 2.0},
        },
    },
    "endpoints": {
        "/api/v1/lncrna-chipseq-overlap": {
            "requests": 20,
            "response": {"p95_ms": 1.0, "p99_ms": 2.0},
            "db": {"p95_ms": 0.5, "p99_ms": 1.0},
        },
        "/api/v1/lncrna-chipseq-overlap/compare": {
            "requests": 20,
            "response": {"p95_ms": 1.2, "p99_ms": 2.2},
            "db": {"p95_ms": 0.6, "p99_ms": 1.1},
        },
    },
}

current_overlap = {
    "meta": {
        "scenario": {
            "lncrna_gene_id": 17276,
            "lncrna_gene_id_requested": 17276,
            "lncrna_gene_id_source": "default",
            "species_ids": [1, 3],
            "pre_warmup_rounds": 0,
            "warmup_rounds": 31,  # drift
            "warmup_max_retries": 2,
            "warmup_retry_base_sleep_ms": 200,
            "min_samples": 20,
        },
        "thresholds": {
            "response": {"pct": 9.0, "abs_ms": 4.0},  # drift
            "db": {"pct": 8.0, "abs_ms": 2.0},
        },
    },
    "endpoints": baseline_overlap["endpoints"],
}

md_overlap = overlap._build_markdown(
    mode="check",
    base_url="http://127.0.0.1:8000",
    generated_at="2026-02-04T00-00-00Z",
    baseline_file=Path("docs/baselines/performance/overlap-admin-metrics.baseline.json"),
    baseline=baseline_overlap,
    current=current_overlap,
    ok=True,
    failures=[],
    admin_metrics_diff_path=None,
    min_samples=20,
    response_regression_pct=9.0,
    response_regression_abs_ms=4.0,
    db_regression_pct=8.0,
    db_regression_abs_ms=2.0,
)

assert_contains(md_overlap, "## Scenario Drift")
assert_contains(md_overlap, "`warmup_rounds`")
assert_contains(md_overlap, "thresholds.response")


baseline_gr = {
    "meta": {
        "scenario": {
            "pre_warmup_rounds": 30,
            "warmup_rounds": 30,
            "warmup_max_retries": 2,
            "warmup_retry_base_sleep_ms": 200,
            "min_samples": 20,
            "genes": {"species_id": 1, "gene_type": "lncRNA", "page_size": 100},
            "regulations": {"species_id": 1, "page_size": 100},
        },
        "thresholds": {
            "response": {"pct": 8.0, "abs_ms": 4.0},
            "db": {"pct": 8.0, "abs_ms": 2.0},
        },
    },
    "endpoints": {
        "/api/v1/genes": {
            "requests": 20,
            "response": {"p95_ms": 1.0, "p99_ms": 2.0},
            "db": {"p95_ms": 0.5, "p99_ms": 1.0},
        },
        "/api/v1/regulations": {
            "requests": 20,
            "response": {"p95_ms": 1.2, "p99_ms": 2.2},
            "db": {"p95_ms": 0.6, "p99_ms": 1.1},
        },
    },
}

current_gr = {
    "meta": {
        "scenario": {
            **baseline_gr["meta"]["scenario"],
            "genes": {"species_id": 1, "gene_type": "lncRNA", "page_size": 50},  # drift
        },
        "thresholds": baseline_gr["meta"]["thresholds"],
    },
    "endpoints": baseline_gr["endpoints"],
}

md_gr = genes_regs._build_markdown(
    mode="check",
    base_url="http://127.0.0.1:8000",
    generated_at="2026-02-04T00-00-00Z",
    baseline_file=Path("docs/baselines/performance/genes-regulations-admin-metrics.baseline.json"),
    baseline=baseline_gr,
    current=current_gr,
    ok=True,
    failures=[],
    admin_metrics_diff_path=None,
    min_samples=20,
    response_regression_pct=8.0,
    response_regression_abs_ms=4.0,
    db_regression_pct=8.0,
    db_regression_abs_ms=2.0,
)

assert_contains(md_gr, "## Scenario Drift")
assert_contains(md_gr, "`genes`")
print("OK")
PY

echo "ok"

