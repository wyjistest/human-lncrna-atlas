# Overlap QUERY_TOO_BROAD UX + MV Guide Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Make `QUERY_TOO_BROAD` errors actionable in the overlap UI (suggested filters + open filters) and document how to create/refresh the overlap materialized view (MV) to avoid broad-query timeouts.

**Architecture:** Backend returns a stable structured error payload (including `suggest_filters`). Frontend parses the payload via `parseError()` and renders a consistent, actionable UI across list/statistics/heatmap/export. Docs explain MV creation/refresh and how it relates to `QUERY_TOO_BROAD`.

**Tech Stack:** FastAPI + SQLAlchemy + pytest; React + TypeScript + Ant Design + React Query + Vitest; Markdown docs.

---

### Task 1: Backend structured suggestions for `QUERY_TOO_BROAD`

**Files:**
- Modify: `frontend/backend/app/routers/lncrna_chipseq_overlap.py`
- Modify: `frontend/backend/tests/test_overlap_chr1_guard_unit.py`

**Step 1: Write failing unit assertions**

Update tests to assert the error detail contains a stable `suggest_filters` list, e.g.:

```python
assert exc.value.detail.get("suggest_filters") == ["mark_type", "cell_type", ...]
```

Run: `pytest -m unit -q frontend/backend/tests/test_overlap_chr1_guard_unit.py`
Expected: FAIL (missing `suggest_filters`).

**Step 2: Implement backend payload field**

In `_raise_query_too_broad(...)`, include:

```python
"suggest_filters": suggest_filters,
```

Run: `pytest -m unit -q frontend/backend/tests/test_overlap_chr1_guard_unit.py`
Expected: PASS.

---

### Task 2: Frontend actionable error UI

**Files:**
- Modify: `frontend/web/src/utils/errorParser.ts`
- Modify: `frontend/web/src/components/LncRNAChIPSeqOverlapTable/index.tsx`
- Modify: `frontend/web/src/components/LncRNAChIPSeqOverlapTable/OverlapHeatmapMatrix.tsx`
- Modify: `frontend/web/src/components/LncRNAChIPSeqOverlapTable/OverlapFilterPanel.tsx` (optional: highlight support)
- Modify: `frontend/web/src/utils/errorParser.test.ts`
- Modify: `frontend/web/src/components/LncRNAChIPSeqOverlapTable/__tests__/LncRNAChIPSeqOverlapTable.error.test.tsx`
- Modify: `frontend/web/src/components/LncRNAChIPSeqOverlapTable/__tests__/OverlapHeatmapMatrix.error.test.tsx`

**Step 1: Write failing UI tests**

Update error tests to include `suggest_filters` in the mocked backend `detail`, then assert the UI renders those suggestions.

Run: `cd frontend/web && npm run test:run -- src/utils/errorParser.test.ts src/components/LncRNAChIPSeqOverlapTable/__tests__/LncRNAChIPSeqOverlapTable.error.test.tsx`
Expected: FAIL (suggestions not rendered / not parsed).

**Step 2: Extend `parseError` to extract suggestions**

Add optional fields to `ParsedError`:

```ts
suggestFilters?: string[]
chromosome?: string
usingMaterializedView?: boolean
```

Extract from `detail` when present.

**Step 3: Render actionable UI**

- For list error Alert: show suggestions as tags and add an action button to open the filter panel.
- For heatmap error Empty: render `parsed.message` and suggested filters when present.
- For export errors in the overlap page: ensure `parseError` is used so users see backend `detail.message`.

Run the same tests; Expected: PASS.

---

### Task 3: Document overlap MV operations

**Files:**
- Create: `docs/backend/OVERLAP_MATERIALIZED_VIEW.md`
- Modify: `docs/api/LNCRNA_CHIPSEQ_OVERLAP_API.md` (error payload example)
- Modify (optional): `README.md` (link to the new MV doc)

**Step 1: Add MV guide**

Document:
- Create: `psql -d <db> -f schema/v2.3/05_mv_lncrna_chipseq_overlaps.sql`
- Refresh: `REFRESH MATERIALIZED VIEW CONCURRENTLY mv_lncrna_chipseq_overlaps;` / `./scripts/refresh_materialized_views.sh`
- Troubleshooting and how it relates to `QUERY_TOO_BROAD`.

Run: `python3 scripts/check_docs_commands.py`
Expected: PASS.

---

### Task 4: Verification + integration

Run:
- `./scripts/run-tests.sh ci`

Then:
- `git add ...`
- `git commit -m "feat(overlap): actionable QUERY_TOO_BROAD guidance"`
- `git push`
- `gh run watch --exit-status` for `Tests` and `Security Audit`.

