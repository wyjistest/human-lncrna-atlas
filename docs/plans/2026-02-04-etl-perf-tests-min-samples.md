# ETL Perf Regression Unit Tests Fix Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** 修复因 `scripts/perf_*_regression.py` 默认 `--min-samples=40` 导致的 ETL 单元测试失败，确保 GitHub Actions 的 Tests workflow 通过。

**Current Status:** 参考 `docs/CURRENT_STATUS.md`

**Architecture:** 保持 gate 脚本默认值不变，仅调整 ETL 单测的 mock `/api/v1/admin/metrics` payload，把 `requests` 提升到 `>=40`（给一定余量），避免 `insufficient samples` 误报；指标数值不变，确保阈值/回归逻辑测试仍有效。

**Tech Stack:** Python 3、pytest、subprocess 调用 `scripts/perf_overlap_regression.py` / `scripts/perf_genes_regulations_regression.py`

---

### Task 1: 修复 Overlap 单测的 mock samples

**Files:**
- Modify: `etl/tests/test_perf_overlap_regression_unit.py`
- Test: `etl/tests/test_perf_overlap_regression_unit.py`

**Step 1: Update mock metrics payload**
- 在 `_base_metrics_payload()` 中将两个 endpoint 的 `"requests": 20` 提升为 `60`（或至少 `40`）。

**Step 2: Run test**
- Run: `python3 -m pytest etl/tests/test_perf_overlap_regression_unit.py -q`
- Expected: PASS

---

### Task 2: 修复 Genes/Regulations 单测的 mock samples

**Files:**
- Modify: `etl/tests/test_perf_genes_regulations_regression_unit.py`
- Test: `etl/tests/test_perf_genes_regulations_regression_unit.py`

**Step 1: Update mock metrics payload**
- 在 `_base_metrics_payload()` 中将两个 endpoint 的 `"requests": 20` 提升为 `60`（或至少 `40`）。

**Step 2: Run test**
- Run: `python3 -m pytest etl/tests/test_perf_genes_regulations_regression_unit.py -q`
- Expected: PASS

---

### Task 3: 运行相关测试集合

**Files:**
- Test: `etl/tests/test_perf_overlap_regression_unit.py`
- Test: `etl/tests/test_perf_genes_regulations_regression_unit.py`

**Step 1: Run**
- Run: `python3 -m pytest etl/tests/test_perf_*_regression_unit.py -q`
- Expected: PASS

---

### Task 4: 提交变更

**Files:**
- Modify: `etl/tests/test_perf_overlap_regression_unit.py`
- Modify: `etl/tests/test_perf_genes_regulations_regression_unit.py`

**Step 1: Commit**
```bash
git add etl/tests/test_perf_overlap_regression_unit.py etl/tests/test_perf_genes_regulations_regression_unit.py
git commit -m "test(etl): bump perf regression mock sample counts"
```

---

### Task 5: 推送到 GitHub（网络不稳时走 API）

**Files:**
- Use: `scripts/gh_push_commit.py`

**Step 1: Push**
- Run: `python3 scripts/gh_push_commit.py --branch main --commit HEAD`
- Expected: 远端 `main` 快进到新 commit；若同路径在远端已被修改，会被脚本护栏拦截并提示冲突。

---

### Task 6: 核验 GitHub Actions（Tests workflow）

**Step 1: Find latest runs**
- Run: `gh run list -L 5`

**Step 2: Inspect Tests run**
- Run: `gh run view <run_id> --log-failed`
- Expected: Tests workflow SUCCESS（或仅与本变更无关的失败）。
