# API Snapshot Regression Anchors Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan.

**Goal:** 扩展 API snapshot 回归锚点覆盖并保持基线稳定可审计。

**Architecture:** 在 `scripts/api_snapshot.py` 追加关键端点采样与摘要字段；通过现有 baseline 生成/校验脚本维护可 diff 快照；同步文档记录。

**Tech Stack:** Python, Bash, GitHub Actions

### Task 1: 补充 api_snapshot 回归锚点覆盖

**Files:**
- Modify: `scripts/api_snapshot.py`
- Test: `etl/tests/test_api_snapshot_baseline_check.py`
- Test: `frontend/backend/tests/test_api_snapshot_overlap_compare_unit.py`（若涉及端点覆盖断言扩展）

**Step 1: 写入失败测试（TDD）**

```python
def test_api_snapshot_includes_export_and_filtered_endpoints():
    # 断言新增端点 key 存在
    assert "overlap_export_basic" in generated["endpoints"]
```

**Step 2: 运行测试确认失败**

Run: `python3 -m pytest etl/tests/test_api_snapshot_baseline_check.py -q`
Expected: FAIL with missing endpoint key

**Step 3: 最小实现新增端点采样**

```python
endpoints["overlap_export_basic"] = _http_get_json(...)
```

**Step 4: 运行测试确认通过**

Run: `python3 -m pytest etl/tests/test_api_snapshot_baseline_check.py -q`
Expected: PASS

### Task 2: 更新 baseline 样例与文档记录

**Files:**
- Modify: `docs/baselines/api-snapshot.sample.json`
- Modify: `docs/baselines/README.md`
- Modify: `docs/ROADMAP_2026-01-21.md`
- Modify: `docs/CURRENT_STATUS.md`

**Step 1: 生成新的 baseline**

Run: `python3 scripts/verify_baselines.py --mode local`
Expected: PASS (或生成候选后对齐)

**Step 2: 同步文档**

记录新增锚点端点与覆盖范围。

### Task 3: 验证与提交

**Files:**
- Verify: `python3 scripts/verify_baselines.py --mode local`

**Step 1: 本地验证**

Run: `python3 scripts/verify_baselines.py --mode local`
Expected: PASS

**Step 2: Commit**

```bash
git add scripts/api_snapshot.py etl/tests/test_api_snapshot_baseline_check.py docs/baselines/api-snapshot.sample.json docs/baselines/README.md docs/ROADMAP_2026-01-21.md docs/CURRENT_STATUS.md
git commit -m "docs(baseline): extend api snapshot regression anchors"
```
