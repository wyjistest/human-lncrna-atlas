# Overlap Export Streaming & MV Fast Path Implementation Plan

> **For Codex:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** 让 `/api/v1/lncrna-chipseq-overlap/export` 在导出大结果集时避免 OFFSET 扫描，并在 MV 可用时走 MV 查询路径，从而显著降低数据库负载与尾延迟。

**Architecture:** 在 `generate_overlap_export()` 内根据 `use_materialized_view` 构建 MV/Join 两套 `SELECT`，统一使用 `stream_results=True` + `fetchmany()` 分批拉取，始终 `finally: result.close()` 防止 StreamingResponse 取消迭代时泄露 server-side cursor。

**Tech Stack:** FastAPI、SQLAlchemy 2.x、PostgreSQL（psycopg2）、pytest

---

### Task 1: 明确改动范围与基线验证

**Files:**
- Modify: `frontend/backend/app/routers/lncrna_chipseq_overlap.py`
- Test: `frontend/backend/tests/test_overlap_export_streaming_unit.py`

**Step 1: 跑后端单测基线（确保当前 worktree 干净）**

Run: `timeout 60 .venv/bin/pytest -q frontend/backend/tests`
Expected: `... passed, ... skipped`

---

### Task 2: 导出路径改为“单次 execute + 真流式 fetchmany”

**Files:**
- Modify: `frontend/backend/app/routers/lncrna_chipseq_overlap.py`

**Step 1: 写一个单元测试（先失败）**

- 目标断言：
  - `generate_overlap_export(..., use_materialized_view=False)` 只调用 `db.execute()` 一次
  - 结果对象 `close()` 在生成器结束时被调用（包含 `max_rows` 提前停止场景）

Run: `timeout 60 .venv/bin/pytest -q frontend/backend/tests/test_overlap_export_streaming_unit.py`
Expected: FAIL（当前实现每批都会 `db.execute()`，调用次数 > 1）

**Step 2: 最小实现改动：移除 `.offset()` 循环，改为 `stream_results=True` + `fetchmany()`**

- Join 路径：`SELECT ... ORDER BY ... LIMIT :limit`，不再使用 OFFSET
- 迭代方式：一次 `db.execute()`，循环 `fetchmany(EXPORT_BATCH_SIZE)`，直到空或达到 `max_rows`
- 资源释放：`try/finally` 里调用 `result.close()`

**Step 3: 运行单测并修到通过**

Run: `timeout 60 .venv/bin/pytest -q frontend/backend/tests/test_overlap_export_streaming_unit.py`
Expected: PASS

**Step 4: 提交一次 commit（仅覆盖该优化）**

```bash
git add frontend/backend/app/routers/lncrna_chipseq_overlap.py frontend/backend/tests/test_overlap_export_streaming_unit.py
git commit -m "perf(backend): stream overlap export without offset scans"
```

---

### Task 3: MV 可用时走 MV 查询（导出也享受 MV 加速）

**Files:**
- Modify: `frontend/backend/app/routers/lncrna_chipseq_overlap.py`
- Test: `frontend/backend/tests/test_overlap_export_streaming_unit.py`

**Step 1: 增量测试（先失败）**

- 目标断言：
  - `export_lncrna_chipseq_overlaps()` 将 `use_materialized_view` 结果透传给 `generate_overlap_export()`
  - `generate_overlap_export(use_materialized_view=True)` 仍然只 `execute()` 一次（不额外做 MV 探测）

**Step 2: 实现 MV 查询版本的 data_stmt**

- MV 路径：`FROM mv_lncrna_chipseq_overlaps`，复用 `_build_overlap_where_and_params()` 组装过滤条件
- 排序：`ORDER BY chromosome, overlap_start`
- 继续使用 `stream_results=True` + `fetchmany()` 真流式

**Step 3: 运行单测**

Run: `timeout 60 .venv/bin/pytest -q frontend/backend/tests/test_overlap_export_streaming_unit.py`
Expected: PASS

**Step 4: 提交一次 commit**

```bash
git add frontend/backend/app/routers/lncrna_chipseq_overlap.py frontend/backend/tests/test_overlap_export_streaming_unit.py
git commit -m "perf(backend): use MV fast path for overlap export when available"
```

---

### Task 4: 回归验证与文档更新

**Files:**
- Modify: `docs/CURRENT_STATUS.md`
- Modify: `docs/ROADMAP_2026-01-19.md`

**Step 1: 跑后端测试全集（对齐 CI）**

Run: `timeout 60 .venv/bin/pytest -q frontend/backend/tests`
Expected: PASS

**Step 2: 更新文档**

- `docs/CURRENT_STATUS.md`：补充后端导出性能优化条目（真流式 + MV fast path）
- `docs/ROADMAP_2026-01-19.md`：在进度区增加该项（如果仍沿用该 roadmap 文件）

**Step 3: 提交一次 commit**

```bash
git add docs/CURRENT_STATUS.md docs/ROADMAP_2026-01-19.md
git commit -m "docs: note overlap export streaming optimization"
```

---

### Task 5: 推送并确认 GitHub Actions 绿灯

**Step 1: 推送分支**

```bash
git push -u origin perf-backend
```

**Step 2: 检查 GitHub Actions `Tests` / `Security Audit` 全绿**

（如出现失败，仅修复与本次改动相关的问题，不扩散范围。）

