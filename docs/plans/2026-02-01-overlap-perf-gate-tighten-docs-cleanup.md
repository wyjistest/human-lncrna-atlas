# Tighten Overlap Perf Regression Gate + Docs Cleanup Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** 收紧 Overlap 性能回归门禁阈值，让“更小但可感知”的性能回归也能被拦截，并同步更新相关文档与测试，保持可审计与可回滚。

**Architecture:** 通过调整 `scripts/perf_overlap_regression.py` 内的阈值常量（响应/DB 的 pct 与 abs_ms），并新增单元测试覆盖“旧阈值不会失败、新阈值会失败”的回归场景；同步更新 `docs/testing/performance/OVERLAP_PERF_REGRESSION.md` 的门禁规则说明；最后只跑与改动文件强相关的最小验证集。

**Tech Stack:** Python (stdlib), pytest, Markdown docs

## Task 1: 补单测覆盖“更小回归也应失败”

**Files:**
- Modify: `etl/tests/test_perf_overlap_regression_unit.py`
- Reference: `scripts/perf_overlap_regression.py`

**Step 1: 写一个会失败的测试（旧阈值下应 PASS，但我们期望 FAIL）**

- 构造 baseline/current 两份 snapshot（只需要覆盖 overlap list/compare 的 p95/p99、requests 字段）。
- 选择一组 delta：满足“pct/abs 高于新阈值，但低于旧阈值”的组合，确保测试能证明“收紧生效”。

**Step 2: 运行该测试，确认它在当前实现下失败（RED）**

Run: `python3 -m pytest -q etl/tests/test_perf_overlap_regression_unit.py -k tighten`
Expected: FAIL（断言提示门禁应失败但实际未失败）

## Task 2: 收紧门禁阈值（最小改动）

**Files:**
- Modify: `scripts/perf_overlap_regression.py`

**Step 1: 调整阈值常量**

- 收紧 `RESPONSE_REGRESSION_PCT` / `RESPONSE_REGRESSION_ABS_MS`
- 收紧 `DB_REGRESSION_PCT` / `DB_REGRESSION_ABS_MS`

**Step 2: 再次运行测试，确认通过（GREEN）**

Run: `python3 -m pytest -q etl/tests/test_perf_overlap_regression_unit.py -k tighten`
Expected: PASS

## Task 3: 同步更新文档（避免“规则漂移”）

**Files:**
- Modify: `docs/testing/performance/OVERLAP_PERF_REGRESSION.md`

**Step 1: 更新“门禁规则（保守）”一节的阈值描述**

**Step 2: 全文搜索旧阈值关键字，避免遗漏**

Run: `rg -n "50%|500ms" docs/testing/performance/OVERLAP_PERF_REGRESSION.md`
Expected: 无匹配（或匹配点全部被更新）

## Task 4: 最小验证（只跑相关检查）

**Step 1: docs 状态标注检查**

Run: `python3 scripts/check_docs_status_markers.py`
Expected: PASS

**Step 2: docs-check（只读）**

Run: `bash scripts/run-tests.sh docs-check`
Expected: PASS

## Task 5: 提交与推送（小步可回滚）

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
