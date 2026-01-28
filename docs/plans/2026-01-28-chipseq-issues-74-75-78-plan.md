# ChIP-seq Issues 74/75/78 Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** 完成 #74 SVG 导出、#75 data-testid + E2E 选择器更新、#78 用户旅程 smoke spec 与文档/工作流更新。

**Architecture:** 以最小侵入方式为现有 ChIP-seq 组件补齐 data-testid，E2E 改为优先使用 testid；新增 SVG 导出函数与 heatmap 入口按钮；新增一条用户旅程 smoke spec 并接入 e2e-smoke。

**Tech Stack:** React + Ant Design + ECharts + Vitest + Playwright

---

### Task 1: data-testid 覆盖（#75）

**Files:**
- Modify: `frontend/web/src/components/ChIPSeqPeaksTable/index.tsx`
- Modify: `frontend/web/src/components/ChIPSeqPeaksTable/MarkSelector.tsx`
- Modify: `frontend/web/src/components/ChIPSeqPeaksTable/FilterPanel.tsx`
- Modify: `frontend/web/src/components/ChIPSeqPeaksTable/PeaksTable.tsx`
- Modify: `frontend/web/src/components/ChIPSeqPeaksTable/StatsCards.tsx`
- Modify: `frontend/web/src/components/ChIPSeqPeaksTable/CompareCharts.tsx`
- Modify: `frontend/web/src/components/ChIPSeqPeaksTable/CellLineHeatmapMatrix.tsx`
- Modify: `frontend/web/src/components/ChIPSeqPeaksTable/BivalentDomainBadge.tsx`
- Create: `frontend/web/src/components/ChIPSeqPeaksTable/__tests__/dataTestIds.test.ts`
- Modify: `frontend/web/e2e/chipseq-flow.spec.ts`
- Modify: `frontend/web/e2e/pages/chipseq-compare.spec.ts`
- Modify: `frontend/web/e2e/extended-marks-validation.spec.ts`
- Modify: `docs/testing/e2e/DATA_TESTID_REQUIREMENTS.md`

**Step 1: Write failing tests (data-testid presence)**

```ts
// frontend/web/src/components/ChIPSeqPeaksTable/__tests__/dataTestIds.test.ts
expect(source).toContain('data-testid="chipseq-container"')
```

**Step 2: Run test to verify it fails**

Run: `npm run test:run -- src/components/ChIPSeqPeaksTable/__tests__/dataTestIds.test.ts`
Expected: FAIL (missing data-testid strings)

**Step 3: Add data-testid attributes in components**

```tsx
<Space data-testid="chipseq-container" ...>
<Button data-testid={compareMode ? 'exit-compare-button' : 'compare-marks-button'} ... />
```

**Step 4: Update E2E locators to prefer data-testid**

```ts
const compareButton = page.getByTestId('compare-marks-button')
```

**Step 5: Re-run test to verify it passes**

Run: `npm run test:run -- src/components/ChIPSeqPeaksTable/__tests__/dataTestIds.test.ts`
Expected: PASS

**Step 6: Update data-testid checklist doc**

Mark high/medium items as completed.

**Step 7: Commit**

```bash
git add frontend/web/src/components/ChIPSeqPeaksTable frontend/web/e2e docs/testing/e2e/DATA_TESTID_REQUIREMENTS.md
git commit -m "testid: add chipseq testids and update e2e locators"
```

---

### Task 2: SVG 导出（#74）

**Files:**
- Modify: `frontend/web/src/utils/echarts.ts`
- Modify: `frontend/web/src/utils/chart-export.ts`
- Create: `frontend/web/src/utils/chart-export.test.ts`
- Modify: `frontend/web/src/components/ChIPSeqPeaksTable/CellLineHeatmapMatrix.tsx`
- Modify: `docs/PHASE_2.9_HEATMAP_MATRIX.md`

**Step 1: Write failing test for exportChartToSVG**

```ts
// frontend/web/src/utils/chart-export.test.ts
expect(exportChartToSVG(mockInstance, 'heatmap')).toBe(true)
```

**Step 2: Run test to verify it fails**

Run: `npm run test:run -- src/utils/chart-export.test.ts`
Expected: FAIL (function missing)

**Step 3: Register SVG renderer + add exportChartToSVG**

```ts
import { SVGRenderer } from 'echarts/renderers'
```

**Step 4: Add SVG export入口到 heatmap matrix**

```tsx
<Button data-testid="export-button" onClick={...}>Export SVG</Button>
```

**Step 5: Re-run test to verify it passes**

Run: `npm run test:run -- src/utils/chart-export.test.ts`
Expected: PASS

**Step 6: Update heatmap matrix doc**

勾选“导出 SVG”已完成。

**Step 7: Commit**

```bash
git add frontend/web/src/utils frontend/web/src/components/ChIPSeqPeaksTable/CellLineHeatmapMatrix.tsx docs/PHASE_2.9_HEATMAP_MATRIX.md
git commit -m "feat: add svg export for heatmap matrix"
```

---

### Task 3: 用户旅程 smoke spec（#78）

**Files:**
- Create: `frontend/web/e2e/chipseq-compare-journey-smoke.spec.ts`
- Modify: `.github/workflows/test.yml`
- Modify: `docs/testing/e2e/ACCEPTANCE_CHECKLIST.md`

**Step 1: Write new smoke spec**

```ts
test('chipseq compare journey', async ({ page }) => { /* steps */ })
```

**Step 2: Run the spec to verify it fails/passes**

Run: `npm run test:e2e -- e2e/chipseq-compare-journey-smoke.spec.ts`
Expected: FAIL before data ready / PASS after selectors updated

**Step 3: Add spec to e2e-smoke workflow list**

```yaml
e2e/chipseq-compare-journey-smoke.spec.ts \
```

**Step 4: Update acceptance checklist doc**

勾选“用户旅程测试”。

**Step 5: Commit**

```bash
git add frontend/web/e2e .github/workflows/test.yml docs/testing/e2e/ACCEPTANCE_CHECKLIST.md
git commit -m "test(e2e): add chipseq compare journey smoke"
```

---

### Task 4: 汇总验证与推送

**Files:**
- Verify: `scripts/check_docs_commands.py`
- Verify: `scripts/check_docs_status_markers.py`

**Step 1: Run doc checks**

Run: `python3 scripts/check_docs_commands.py`
Run: `python3 scripts/check_docs_status_markers.py`

**Step 2: Final commit (if needed)**

```bash
git add -A
git commit -m "chore: sync docs and tests"
```

**Step 3: Push**

```bash
git push -u origin close-issues-71-78
```
