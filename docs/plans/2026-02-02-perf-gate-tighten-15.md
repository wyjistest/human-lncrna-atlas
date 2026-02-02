# Performance Regression Gate Tighten (15%) Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan.

**Goal:** 将 Overlap 与 Genes/Regulations 的性能回归门禁从 `>20%` 收紧到 `>15%`（仍保留绝对阈值：response `>10ms`、db `>2ms`，且门禁逻辑保持 `pct AND abs`），并同步更新 baseline 与文档，保证可审计/可回滚。

**Architecture:** 只改默认阈值与文档描述，不改采样/上报/计算逻辑；workflow_dispatch 仍允许通过 inputs 覆盖阈值，避免紧急情况下被门禁阻塞。

**Tech Stack:** Python（`scripts/perf_*_regression.py`）、GitHub Actions workflow、Markdown 文档与 baseline JSON。

---

### Task 1: 更新默认阈值（代码 + workflow）

**Files:**
- Modify: `scripts/perf_genes_regulations_regression.py`
- Modify: `scripts/perf_overlap_regression.py`
- Modify: `.github/workflows/performance-genes-regulations.yml`
- Modify: `.github/workflows/performance-overlap.yml`

**Steps:**
1. 将 `DEFAULT_*_REGRESSION_PCT` 从 `20.0` 改为 `15.0`，并同步 CLI help 文案中的 default 数值。
2. 将 workflow_dispatch inputs 与 env 默认 `response_regression_pct/db_regression_pct` 从 `20` 改为 `15`。

---

### Task 2: 同步 baseline 元数据阈值

**Files:**
- Modify: `docs/baselines/performance/genes-regulations-admin-metrics.baseline.json`
- Modify: `docs/baselines/performance/overlap-admin-metrics.baseline.json`

**Steps:**
1. 仅更新 `meta.thresholds.{response,db}.pct` 为 `15.0`（不改 base 值与样本）。

---

### Task 3: 更新性能门禁文档与历史文档清理

**Files:**
- Modify: `docs/testing/performance/GENES_REGULATIONS_PERF_REGRESSION.md`
- Modify: `docs/testing/performance/OVERLAP_PERF_REGRESSION.md`

**Steps:**
1. 将文档里的 `>20%` 规则更新为 `>15%`，并保留“可通过参数覆盖”的说明。
2. 仅在确认是过期/误导信息时，清理历史文档中的阈值描述（避免影响真实 TODO）。

---

### Task 4: 核验与提交

**Steps:**
1. 运行：`python3 scripts/perf_overlap_regression.py --help` 与 `python3 scripts/perf_genes_regulations_regression.py --help`，确认 default 文案一致。
2. 运行：`bash scripts/tests/test_checkout_tarball_script.sh`（快速回归）与 `bash scripts/tests/test_check_docs_status_markers.sh`（文档规则）。
3. Commit：`perf: tighten perf regression gate to 15%`

