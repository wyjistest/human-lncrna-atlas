# Perf Workflows Reset-Metrics Implementation Plan

> **For Codex:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** 让 `Performance Overlap` / `Performance Genes/Regulations` 两个 perf regression workflows 在使用 external backend 时支持可选的 `--reset-metrics`，降低长时间运行 backend 的样本混入导致的波动与误报；同时更新对应文档说明与复现命令。

**Architecture:** 在两个 workflow_dispatch 增加输入 `reset_metrics`（默认 `false`），仅在 `backend_mode=external` 时将其转化为 perf 脚本参数 `--reset-metrics`。docker-sample 路径保持现状（仍由 docker 脚本默认 `RESET_METRICS=true` 控制）。

**Tech Stack:** GitHub Actions、bash、Python perf scripts（`scripts/perf_*_regression.py`）、Admin metrics reset endpoint（`POST /api/v1/admin/metrics/reset-stats`）

---

### Task 1: Performance Overlap workflow 增加 reset_metrics input

**Files:**
- Modify: `.github/workflows/performance-overlap.yml`

**Step 1: 增加 workflow_dispatch 输入**

新增：
- `reset_metrics`（default: `"false"`）：是否在 warmup 前调用 `POST /api/v1/admin/metrics/reset-stats`。

**Step 2: 仅 external 模式追加参数**

在 `Run overlap perf regression` step 中：
- 以 bash 方式组装 `reset_args=(--reset-metrics)`（当 `RESET_METRICS == 'true'`）
- 调用 `python3 scripts/perf_overlap_regression.py ... "${reset_args[@]}" ...`

---

### Task 2: Performance Genes/Regulations workflow 增加 reset_metrics input

**Files:**
- Modify: `.github/workflows/performance-genes-regulations.yml`

**Steps:**
- 同 Task 1：新增 `reset_metrics` 输入；仅 external 模式追加 `--reset-metrics`。

---

### Task 3: 更新 perf regression 文档（Actions 使用方式）

**Files:**
- Modify: `docs/testing/performance/OVERLAP_PERF_REGRESSION.md`
- Modify: `docs/testing/performance/GENES_REGULATIONS_PERF_REGRESSION.md`

**Spec:**
- 在 GitHub Actions（workflow_dispatch）段落补充：
  - `reset_metrics=true`：external backend 时可选启用 reset（长时间运行的 backend 推荐）
  - docker-sample：默认已 reset（如需禁用可用 `RESET_METRICS=false`）

---

### Verification

Run:
- `timeout 60 bash scripts/run-tests.sh docs-check`

GitHub verification:
- 手动触发两套 perf workflows（`backend_mode=external` + `reset_metrics=true`），确认脚本参数正确生效（若没有权限，脚本应 warn 并继续；不应导致 workflow 崩溃）。

---

### Rollback

- `git revert <sha>` 回滚 workflow/doc 变更即可恢复原行为。
