# Perf Regression 门禁可定位性增强 Implementation Plan

> **For Codex:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** 提升两套 perf regression 门禁（Overlap / Genes/Regulations）的“可定位、可回滚”体验：支持在 warmup 前重置 admin metrics、并确保在早期失败（基线缺失/UNSET/样本不足）时也能产出可贴 issue 的报告。

**Architecture:** 在 `scripts/perf_*_regression.py` 中新增 `--reset-metrics`（调用 `POST /api/v1/admin/metrics/reset-stats`），并把 check 模式重构为“无论失败在哪一步都输出 `docs/reports/perf-*.md`”。Docker sample 入口默认开启 reset（可用环境变量关闭），同时更新对应文档与状态入口。

**Tech Stack:** Python（标准库 urllib）、bash、GitHub Actions artifacts、FastAPI Admin metrics

---

## Task 1: Overlap perf gate 增强（reset + 早期报告）

**Files:**
- Modify: `scripts/perf_overlap_regression.py`

**Steps:**
1. 增加 `--reset-metrics` 参数（默认关闭）：调用 `POST /api/v1/admin/metrics/reset-stats`，并把结果写入 snapshot `meta.scenario.admin_metrics_reset`。
2. 重构 check 流程：baseline 缺失/UNSET/样本不足时仍写出 `docs/reports/perf-overlap-*.md`，并保持 exit code 语义（2=配置/运行错误，3=门禁失败）。
3. Markdown 报告增加 `Scenario` 段落：展示 warmup/样本/基因 ID 与 reset 状态。

---

## Task 2: Genes/Regulations perf gate 增强（reset + 早期报告）

**Files:**
- Modify: `scripts/perf_genes_regulations_regression.py`

**Steps:**
1. 增加 `--reset-metrics` 参数（默认关闭），并写入 snapshot `meta.scenario.admin_metrics_reset`。
2. generate-baseline 模式增加样本数校验（样本不足时拒绝写 baseline，仍产出报告）。
3. 重构 check 流程：baseline 缺失/UNSET/样本不足时仍写出 `docs/reports/perf-genes-regulations-*.md`。
4. Markdown 报告增加 `Scenario` 段落。

---

## Task 3: docker-sample 入口默认开启 reset

**Files:**
- Modify: `scripts/baselines/run_overlap_perf_regression_docker.sh`
- Modify: `scripts/baselines/run_genes_regulations_perf_regression_docker.sh`

**Spec:**
- 新增 `RESET_METRICS` 环境变量（默认 `true`），为 python 脚本追加 `--reset-metrics`（可 `RESET_METRICS=false` 禁用）。

---

## Task 4: 文档与入口更新

**Files:**
- Modify: `docs/testing/performance/OVERLAP_PERF_REGRESSION.md`
- Modify: `docs/testing/performance/GENES_REGULATIONS_PERF_REGRESSION.md`
- Modify: `docs/CURRENT_STATUS.md`
- Modify: `README.md`

**Spec:**
- perf 文档示例命令补充 `--reset-metrics`，并说明 docker-sample 默认启用、可通过 `RESET_METRICS=false` 关闭。
- `CURRENT_STATUS` 增加 2026-02-03 更新条目，记录 perf gate / docs 止损路径等进展。
- README 增加固定入口：`docs/CURRENT_STATUS.md` + `docs/ROADMAP_2026-02-03.md`。

---

## Verification

Run:
- `python3 -m py_compile scripts/perf_overlap_regression.py scripts/perf_genes_regulations_regression.py`
- `bash -n scripts/baselines/run_overlap_perf_regression_docker.sh scripts/baselines/run_genes_regulations_perf_regression_docker.sh`

GitHub verification (optional):
- 手动触发两套 perf workflows（docker-sample, check），确认 artifacts 包含报告与 json。

---

## Rollback

- 本变更为独立的脚本/文档更新：`git revert <sha>` 即可回滚到旧的门禁与文档行为。
