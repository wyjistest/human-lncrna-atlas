# Tighten Overlap Perf Regression Gate + Docs Cleanup Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** 收紧 Overlap 性能回归门禁阈值，让“更小但可感知”的性能回归也能被拦截，并同步更新相关文档与测试，保持可审计与可回滚。

**Architecture:** 通过调整 `scripts/perf_overlap_regression.py` 的门禁阈值常量（本轮目标：`pct=30%` 不变，`response.abs_ms` 收紧到 `10ms`、`db.abs_ms` 收紧到 `2ms`），并新增单元测试覆盖“旧 abs_ms 阈值下 PASS、新 abs_ms 阈值下 FAIL”的回归场景；同步更新 baseline 元数据与门禁文档，避免规则漂移；顺手修复 docs 重定向文件被误插入的 `# 1:# ...` 标题噪音，并加入一个轻量 docs-check 防止回归。

**Tech Stack:** Python (stdlib), pytest, Markdown docs

## Task 1: 补单测覆盖“更小回归也应失败”

**Files:**
- Modify: `etl/tests/test_perf_overlap_regression_unit.py`
- Reference: `scripts/perf_overlap_regression.py`

**Step 1: 写一个会失败的测试（旧阈值下应 PASS，但我们期望 FAIL）**

- 构造 baseline/current 两份 snapshot（覆盖 overlap list/compare 的 p95/p99、requests 字段即可）。
- 选择一组 delta：满足 “pct > 30% 且 abs > 10ms/2ms”，但同时 **abs 低于旧阈值（response 20ms / db 5ms）**。
  - baseline: response=`33/35ms`、db=`6/6.5ms`
  - current: response=`45/50ms`（+12ms/+15ms）、db=`9/10ms`（+3ms/+3.5ms）

**Step 2: 运行该测试，确认它在当前实现下失败（RED）**

Run: `python3 -m pytest -q etl/tests/test_perf_overlap_regression_unit.py -k tighten`
Expected: FAIL（断言提示门禁应失败但实际未失败）

## Task 2: 收紧门禁阈值（最小改动）

**Files:**
- Modify: `scripts/perf_overlap_regression.py`

**Step 1: 调整阈值常量**

- 保持 `*_REGRESSION_PCT = 30.0`
- 设置 `RESPONSE_REGRESSION_ABS_MS = 10.0`
- 设置 `DB_REGRESSION_ABS_MS = 2.0`

**Step 2: 再次运行测试，确认通过（GREEN）**

Run: `python3 -m pytest -q etl/tests/test_perf_overlap_regression_unit.py -k tighten`
Expected: PASS

## Task 3: 同步更新文档（避免“规则漂移”）

**Files:**
- Modify: `docs/testing/performance/OVERLAP_PERF_REGRESSION.md`
- Modify: `docs/baselines/performance/overlap-admin-metrics.baseline.json`
- Modify: `docs/plans/2026-01-30-overlap-perf-regression.md`
- Modify: `docs/plans/2026-02-01-overlap-perf-gate-tighten-docs-cleanup.md`

**Step 1: 更新“门禁规则（保守）”一节的阈值描述**

**Step 2: 全文搜索旧阈值关键字，避免遗漏**

Run: `rg -n "20ms|5ms" docs`
Expected: 无匹配（或仅剩历史上下文并明确标注“已过期”）

## Task 4: 清理 docs 重定向文件的标题噪音（文档可读性）

**Files:**
- Modify: `docs/*.md`（仅重定向文件的首行标题）

**Step 1: 修复被误插入的 `# 1:# ...`**

Run: `rg -n "^# \\d+:#" docs`
Expected: 无匹配

## Task 5: docs-check 防回归（避免再次引入）

**Files:**
- Create: `scripts/check_docs_heading_artifacts.py`
- Modify: `scripts/run-tests.sh`

**Step 1: 新增检查脚本，扫描 git 跟踪的 docs/*.md**

规则：若出现 `^# \\d+:#`（或同类“带行号前缀的标题”）则 FAIL。

**Step 2: 把该检查接入 `bash scripts/run-tests.sh docs-check`**

## Task 6: 最小验证（只跑相关检查）

**Step 1: docs 状态标注检查**

Run: `python3 scripts/check_docs_status_markers.py`
Expected: PASS

**Step 2: docs-check（只读）**

Run: `bash scripts/run-tests.sh docs-check`
Expected: PASS

## Task 7: 提交与推送（小步可回滚）

**Step 1: commit**

Run:
```bash
git add scripts/perf_overlap_regression.py etl/tests/test_perf_overlap_regression_unit.py docs/testing/performance/OVERLAP_PERF_REGRESSION.md docs/plans/2026-02-01-overlap-perf-gate-tighten-docs-cleanup.md
git commit -m "perf(overlap): tighten perf regression gate thresholds"
```

**Step 2: push**

Run (如遇 TLS/代理问题可按需加 http_proxy/https_proxy):
```bash
git push -u origin HEAD
```
