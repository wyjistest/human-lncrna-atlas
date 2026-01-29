# URL Sync for More Pages (Stats + Conservation + Analysis) Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** 将 `/stats`、`/conservation`、`/analysis`（含 4 个 tabs）关键筛选/分页状态与 URL query params 双向同步，支持可分享、可复现的链接。

**Architecture:** 统一以 React Router `useSearchParams()` 为单一真源（source of truth）：页面渲染从 URL 解析参数形成 hooks/API 入参；用户交互通过 `setSearchParams((prev)=>next, { replace: true })` 写回 URL；默认值尽量不写入 URL（用 `delete()` 维持 URL 干净）。

**Tech Stack:** React + TypeScript + React Router + TanStack Query + Ant Design + Vitest + Testing Library

---

### Task 1: Stats 从 URL 读取 detailed stats 参数（buckets/top_limit）

**Files:**
- Modify: `frontend/web/src/pages/Stats/index.tsx`
- Test: `frontend/web/src/pages/Stats/index.test.tsx`

**Step 1: Write the failing test**

期望：当 URL 为 `/stats?buckets=50&top_limit=20` 时，`useDetailedStats({ buckets: 50, topLimit: 20 })` 被调用。

**Step 2: Run test to verify it fails**

Run: `cd "frontend/web" && npx vitest run "src/pages/Stats/index.test.tsx"`
Expected: FAIL（当前未从 URL 读取参数）

**Step 3: Write minimal implementation**

- 引入 `useSearchParams`
- 解析 `buckets`（范围校验）与 `top_limit`（映射到 `topLimit`）后传入 `useDetailedStats`

**Step 4: Run test to verify it passes**

Run: `cd "frontend/web" && npx vitest run "src/pages/Stats/index.test.tsx"`
Expected: PASS

**Step 5: Commit**

```bash
git add "frontend/web/src/pages/Stats/index.tsx" "frontend/web/src/pages/Stats/index.test.tsx"
git commit -m "feat(stats): read detailed stats params from URL"
```

---

### Task 2: Conservation 页分页/筛选与 URL 同步

**Files:**
- Modify: `frontend/web/src/pages/Conservation/index.tsx`
- Test: `frontend/web/src/pages/Conservation/__tests__/index.test.tsx`

**Step 1: Write the failing test**

期望：当 URL 为 `/conservation?...` 时，`conservationApi.getConservedRegulations(params)` 使用 URL 派生出的参数（`species_ids`、`page`、`page_size`、`min_conservation`、`min_ba`、`lncrna_gene_name`、`target_gene_name`）。

**Step 2: Run test to verify it fails**

Run: `cd "frontend/web" && npx vitest run "src/pages/Conservation/__tests__/index.test.tsx"`
Expected: FAIL（当前 params 仍来自本地 state 默认值）

**Step 3: Write minimal implementation**

- 引入 `useSearchParams`
- 从 URL 解析：`species_ids`（逗号分隔）、`page`、`page_size`、`min_conservation`、`min_ba`、`lncrna_gene_name`、`target_gene_name`
- 输入/滑块/物种选择/表格分页交互写回 URL，并在筛选变化时重置页码（删除 `page`）

**Step 4: Run test to verify it passes**

Run: `cd "frontend/web" && npx vitest run "src/pages/Conservation/__tests__/index.test.tsx"`
Expected: PASS

**Step 5: Commit**

```bash
git add "frontend/web/src/pages/Conservation/index.tsx" "frontend/web/src/pages/Conservation/__tests__/index.test.tsx"
git commit -m "feat(conservation): sync filters with URL params"
```

---

### Task 3: Analysis 页 tab 与各 tab 的筛选/分页与 URL 同步

**Files:**
- Modify: `frontend/web/src/pages/Analysis/index.tsx`
- Modify: `frontend/web/src/pages/Analysis/components/HighAffinityTab.tsx`
- Modify: `frontend/web/src/pages/Analysis/components/ConservationTab.tsx`
- Modify: `frontend/web/src/pages/Analysis/components/EpigeneticTab.tsx`
- Modify: `frontend/web/src/pages/Analysis/components/DiseaseTab.tsx`
- Test: `frontend/web/src/pages/Analysis/__tests__/index.test.tsx`

**Step 1: Write the failing test**

期望：
- `/analysis?tab=epigenetic` 初始化时选中 Epigenetic tab；
- `/analysis?tab=highAffinity&min_ba=150&species_id=2` 时，`analysisApi.getHighAffinity` 的 params 中包含 `min_ba=150`、`species_id=2`。

**Step 2: Run test to verify it fails**

Run: `cd "frontend/web" && npx vitest run "src/pages/Analysis/__tests__/index.test.tsx"`
Expected: FAIL（当前 tab/filters 未从 URL 初始化）

**Step 3: Write minimal implementation**

- `Analysis/index.tsx`：用 `tab` query param 驱动 `activeTab`，并在切换 tab 时写回 URL
- HighAffinityTab：从 URL 解析 `min_ba`、`species_id`、`page`；交互写回 URL
- ConservationTab：从 URL 解析 `min_species_count`、`page`；交互写回 URL
- EpigeneticTab：从 URL 解析 `mark_names`（重复 key）与 `page`；交互写回 URL（空数组删除 `mark_names`）
- DiseaseTab：从 URL 解析 `trait_name`（+ 输入框本地态同步）；应用筛选写回 URL

**Step 4: Run test to verify it passes**

Run: `cd "frontend/web" && npx vitest run "src/pages/Analysis/__tests__/index.test.tsx"`
Expected: PASS

**Step 5: Commit**

```bash
git add "frontend/web/src/pages/Analysis/index.tsx" \
  "frontend/web/src/pages/Analysis/components/HighAffinityTab.tsx" \
  "frontend/web/src/pages/Analysis/components/ConservationTab.tsx" \
  "frontend/web/src/pages/Analysis/components/EpigeneticTab.tsx" \
  "frontend/web/src/pages/Analysis/components/DiseaseTab.tsx" \
  "frontend/web/src/pages/Analysis/__tests__/index.test.tsx"
git commit -m "feat(analysis): sync tab filters with URL params"
```

---

### Task 4: Verification + integration

**Step 1: Run local CI smoke (same as pre-push hook)**

Run: `bash "scripts/run-tests.sh" ci`
Expected: PASS

**Step 2: Merge to main + push**

```bash
cd "/data/wenyujianData/human-lncrna-atlas-github"
git fetch origin
git rebase origin/main
git merge --ff-only feat/url-sync-more-pages
git push origin main
```

