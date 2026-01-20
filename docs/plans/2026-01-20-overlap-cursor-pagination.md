# Overlap Cursor Pagination Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** 为 `/api/v1/lncrna-chipseq-overlap` 增加 cursor（keyset）分页能力，避免 deep OFFSET 扫描，同时保留现有 `page/page_size` 兼容。

**Architecture:** 新增 `GET /api/v1/lncrna-chipseq-overlap/cursor`，使用 `(sort_field, overlap_id)` 作为稳定排序键；服务端返回 `next_cursor/has_more`，客户端用 `next_cursor` 拉取下一页。实现 MV 路径与 NO-MV join 路径两套查询，并复用现有的 NO-MV broad query guard（chr1/2/3）与默认 `chr22` 回退策略。

**Tech Stack:** FastAPI + SQLAlchemy + Pydantic v2 + pytest（unit markers）+ Redis count cache（沿用现有 count 缓存）。

---

### Task 1: 增加 Cursor 响应模型

**Files:**
- Modify: `frontend/backend/app/schemas/lncrna_chipseq_overlap.py`
- Test: `frontend/backend/tests/test_overlap_cursor_pagination_unit.py`

**Step 1: Write the failing test**
- 断言 `OverlapCursorResponse` 存在并可实例化。

**Step 2: Run test to verify it fails**
- Run: `cd frontend/backend && pytest -q tests/test_overlap_cursor_pagination_unit.py::test_cursor_response_schema_exists`
- Expected: FAIL（schema 不存在）

**Step 3: Write minimal implementation**
- 新增 `OverlapCursorResponse`，包含 `total/page_size/items/next_cursor/has_more` 与 MV/默认过滤元信息字段。

**Step 4: Run test to verify it passes**
- Run: 同上
- Expected: PASS

---

### Task 2: 新增 /cursor 端点（MV 与 NO-MV）

**Files:**
- Modify: `frontend/backend/app/routers/lncrna_chipseq_overlap.py`
- Test: `frontend/backend/tests/test_overlap_cursor_pagination_unit.py`

**Step 1: Write the failing tests**
- cursor 端点存在、签名包含 `cursor/page_size/sort_by/sort_order`
- 能返回 `OverlapCursorResponse`
- 当返回 `page_size + 1` 行时：`has_more=true` 且 `next_cursor` 非空

**Step 2: Run tests to verify they fail**
- Run: `cd frontend/backend && pytest -q tests/test_overlap_cursor_pagination_unit.py`
- Expected: FAIL

**Step 3: Write minimal implementation**
- 新增 `get_lncrna_chipseq_overlaps_cursor()`（FastAPI 路由）
- 新增 `get_lncrna_chipseq_overlaps_cursor_from_mv()` 与 `get_lncrna_chipseq_overlaps_cursor_query()`
- 生成 `next_cursor`：base64url(JSON)；decode 时校验 `sort_by/sort_order` 一致
- NO-MV fallback：沿用现有的默认 `chr22` 与 chr1/2/3 broad query guard

**Step 4: Run tests to verify they pass**
- Run: `cd frontend/backend && pytest -m unit -q`
- Expected: PASS

---

### Task 3: 文档更新

**Files:**
- Modify: `docs/api/LNCRNA_CHIPSEQ_OVERLAP_API.md`
- Modify: `docs/CURRENT_STATUS.md`
- Modify: `docs/ROADMAP_2026-01-19.md`

**Step 1: 更新 API 文档**
- 增加 `/cursor` 端点说明、响应结构、以及 `sort_by=peak_qvalue` 暂不支持的原因。

**Step 2: 更新 CURRENT_STATUS**
- 将 “chr1 等大染色体查询优化” 标记为已完成，并补充 cursor 分页能力。

**Step 3: 更新 ROADMAP**
- 在进度区补齐 cursor 分页项。

---

### Task 4: 验证与交付

**Step 1: 运行 unit tests**
- Run: `cd frontend/backend && pytest -m unit -q`

**Step 2: 提交与 PR**
- Run:
  - `git status`
  - `git add frontend/backend/app/routers/lncrna_chipseq_overlap.py frontend/backend/app/schemas/lncrna_chipseq_overlap.py frontend/backend/tests/test_overlap_cursor_pagination_unit.py docs/api/LNCRNA_CHIPSEQ_OVERLAP_API.md docs/CURRENT_STATUS.md docs/ROADMAP_2026-01-19.md docs/plans/2026-01-20-overlap-cursor-pagination.md`
  - `git commit -m "perf(api): add overlap cursor pagination"`

