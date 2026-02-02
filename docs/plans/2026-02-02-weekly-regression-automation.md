# Weekly Regression（Self-hosted）自动化 Implementation Plan

> **For Codex:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** 把“每周全量回归”落地为一个可 schedule + 可手动触发的 GitHub Actions workflow，在 self-hosted runner 上串行执行 `ci-plus` + 两套 Docker sample 性能回归，并通过仓库变量开关控制 schedule 是否真正执行。

**Architecture:** 新增 `.github/workflows/weekly-regression.yml`（schedule + workflow_dispatch）。`schedule` 默认不跑，只有当仓库变量 `CI_ENABLE_WEEKLY_REGRESSION=true` 时才会执行；`workflow_dispatch` 始终可手动触发并可覆盖 `runs_on`。

**Tech Stack:** GitHub Actions、GitHub repo variables（`vars`）、bash、docker compose、Python、Node.js、Playwright

---

## Task 1: 新增 weekly regression workflow

**Files:**
- Create: `.github/workflows/weekly-regression.yml`

**Spec:**
- Triggers:
  - `schedule`: `0 2 * * 1`（Monday 02:00 UTC）
  - `workflow_dispatch` input: `runs_on`（默认空）
- Gate:
  - job-level `if`: `${{ github.event_name == 'workflow_dispatch' || vars.CI_ENABLE_WEEKLY_REGRESSION == 'true' }}`
- Default runner:
  - `runs-on`: `${{ (github.event_name == 'workflow_dispatch' && github.event.inputs.runs_on) || 'self-hosted' }}`
- Jobs（串行）：
  1. `ci-plus`: `bash scripts/run-tests.sh ci-plus`（并预装 `npx playwright install chromium`）
  2. `perf-overlap`: `MODE=check bash scripts/baselines/run_overlap_perf_regression_docker.sh`
  3. `perf-genes-regulations`: `MODE=check bash scripts/baselines/run_genes_regulations_perf_regression_docker.sh`
- Artifacts:
  - Playwright：`frontend/web/playwright-report/`（always），`frontend/web/test-results/`（failure）
  - Perf reports：`docs/reports/perf-overlap-*.{md,json}`，`docs/reports/perf-genes-regulations-*.{md,json}`

---

## Task 2: 更新 self-hosted runner 文档

**Files:**
- Modify: `docs/CI_SELF_HOSTED_RUNNER.md`

**Spec:**
- 增加一节说明 `Weekly Regression (Self-hosted)`：
  - 文件位置：`.github/workflows/weekly-regression.yml`
  - schedule 时间：周一 02:00 UTC
  - 开关变量：`CI_ENABLE_WEEKLY_REGRESSION=true` 才会执行 schedule
  - 手动触发示例：`gh workflow run "Weekly Regression (Self-hosted)" --ref main`

---

## Verification

Run:
- `timeout 60 bash scripts/run-tests.sh docs-check`

GitHub verification:
- 手动触发一次 `Weekly Regression (Self-hosted)`，确认 3 个 jobs 串行执行并生成 artifacts

---

## Rollback

- `git revert <merge_sha>` 即可关闭 weekly regression（删除 workflow 文件会立即停止 schedule）

