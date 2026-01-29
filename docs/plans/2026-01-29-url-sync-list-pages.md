# URL Sync for List Pages (Regulations + Diseases) Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** 让 `/regulations` 与 `/diseases` 列表页的分页/筛选状态与 URL query params 双向同步，支持可分享、可复现的链接（便于排障与回归对比）。

**Architecture:** 以 React Router `useSearchParams()` 作为单一真源；页面渲染时从 URL 解析 `page/page_size/...` 形成 hook 入参；用户交互时用 `setSearchParams(..., { replace: true })` 更新 URL，并在筛选变更时将 `page` 归一到 1（或删除 `page` 参数）。

**Tech Stack:** React + TypeScript + React Router + TanStack Query + Ant Design + Vitest + Testing Library

---

### Task 1: Regulations URL params sync

**Files:**
- Modify: `frontend/web/src/pages/Regulations/index.tsx`
- Test: `frontend/web/src/pages/Regulations/index.test.tsx`

**Step 1: Write the failing test**

期望：当 URL 为 `/regulations?...` 时，`useRegulations(params)` 的 `params` 与 URL 一致（含数组/数字解析与范围校验）。

**Step 2: Run test to verify it fails**

Run: `cd "frontend/web" && npx vitest run "src/pages/Regulations/index.test.tsx"`
Expected: FAIL（params 仍来自本地 state，而不是 URL）

**Step 3: Write minimal implementation**

- 引入 `useSearchParams`
- 解析并校验 URL 参数：`page`、`page_size`、`min_ba`、`max_ba`、`species_ids`（逗号分隔）、`chromosomes`（逗号分隔）、`lncrna_gene_name`、`target_gene_name`
- `AdvancedFilters` 的 `onFilterChange/onReset` 改为更新 URL，并在变更时重置页码

**Step 4: Run test to verify it passes**

Run: `cd "frontend/web" && npx vitest run "src/pages/Regulations/index.test.tsx"`
Expected: PASS

**Step 5: Commit**

```bash
git add "frontend/web/src/pages/Regulations/index.tsx" "frontend/web/src/pages/Regulations/index.test.tsx"
git commit -m "feat(regulations): sync filters with URL params"
```

---

### Task 2: Diseases URL params sync

**Files:**
- Modify: `frontend/web/src/pages/Diseases/index.tsx`
- Test: `frontend/web/src/pages/Diseases/index.test.tsx`

**Step 1: Write the failing test**

期望：当 URL 为 `/diseases?page=...&page_size=...&search=...` 时，`useDiseases(params)` 的 `params` 与 URL 一致。

**Step 2: Run test to verify it fails**

Run: `cd "frontend/web" && npx vitest run "src/pages/Diseases/index.test.tsx"`
Expected: FAIL（params 仍来自本地 state，而不是 URL）

**Step 3: Write minimal implementation**

- 引入 `useSearchParams`
- URL 中的 `search` 作为真源；保留一个 `searchInput` 作为输入框即时状态（输入时不立即发请求，点击搜索/回车才写入 URL）
- 表格分页 `onChange` 写回 `page/page_size` 到 URL

**Step 4: Run test to verify it passes**

Run: `cd "frontend/web" && npx vitest run "src/pages/Diseases/index.test.tsx"`
Expected: PASS

**Step 5: Commit**

```bash
git add "frontend/web/src/pages/Diseases/index.tsx" "frontend/web/src/pages/Diseases/index.test.tsx"
git commit -m "feat(diseases): sync pagination/search with URL params"
```

---

### Task 3: Verification + integration

**Step 1: Run local CI smoke (same as pre-push hook)**

Run: `bash "scripts/run-tests.sh" ci`
Expected: PASS

**Step 2: Merge to main + push**

```bash
cd "/data/wenyujianData/human-lncrna-atlas-github"
git fetch origin
git rebase origin/main
git merge --ff-only feat/url-sync-list-pages
git push origin main
```
