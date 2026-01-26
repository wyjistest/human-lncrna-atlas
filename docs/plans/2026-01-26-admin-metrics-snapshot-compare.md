# Admin Metrics Snapshot Compare Implementation Plan

> **For Codex:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** 为 `scripts/admin_metrics_snapshot.py` 增加离线对比模式：输入两份快照 JSON，输出一份 issue 友好的 Markdown diff。

**Architecture:** 在现有脚本内新增 `--compare OLD_JSON NEW_JSON` 分支，仅做本地 JSON 读取与对比格式化，不触网；输出写入 `docs/reports/`（或 `--out-dir`）。

**Tech Stack:** Python 标准库 + `pytest`（离线单测）。

## Task 1: 写 failing test（RED）

**Files:**
- Create: `etl/tests/test_admin_metrics_snapshot_compare_unit.py`

**Step 1: Write the failing test**

- 构造两份最小 metrics JSON（含 endpoints / cache_stats / database.slow_queries）。
- 使用 `subprocess` 调用脚本：`python3 scripts/admin_metrics_snapshot.py --compare old.json new.json --out-dir <tmp> --prefix admin-metrics-diff-test`。
- 断言：退出码为 0、生成 `admin-metrics-diff-test-*.md`，并包含关键变化片段（端点、hit rate、fingerprint）。

**Step 2: Run test to verify it fails**

Run: `python3 -m pytest -q etl/tests/test_admin_metrics_snapshot_compare_unit.py`
Expected: FAIL（`--compare` 未实现/参数不被识别）。

## Task 2: 实现 compare（GREEN）

**Files:**
- Modify: `scripts/admin_metrics_snapshot.py`

**Step 1: Add CLI**

- 新增参数：`--compare OLD_JSON NEW_JSON`（nargs=2），触发离线对比流程。

**Step 2: Implement diff formatting**

- 对比并输出（Markdown）：全局 percentiles、cache hit rate、端点 Response P95/DB P95、慢查询（fingerprint+route）。
- 字段缺失/样本不足时降级为 `-`，不抛异常。

**Step 3: Run tests to verify it passes**

Run:
- `python3 -m pytest -q etl/tests/test_admin_metrics_snapshot_compare_unit.py`
- `python3 -m pytest -q etl/tests/test_admin_metrics_snapshot.py`
- `python3 -m pytest -q etl/tests/test_admin_metrics_snapshot_env_defaults_unit.py`

Expected: PASS

## Task 3: 更新文档与 issue 模板

**Files:**
- Modify: `docs/PERFORMANCE_TRIAGE.md`
- Modify: `.github/ISSUE_TEMPLATE/performance-triage.md`

**Step 1: Add “导出 + 对比”最短路径**

- 文档新增对比两份导出 JSON 的命令示例与输出路径说明。
- issue 模板新增可选 diff 粘贴区，方便回归/优化对比。

