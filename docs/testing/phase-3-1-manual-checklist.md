# Phase 3.1: Manual Testing Checklist

> 更新（2026-01-24）：本文档为手工测试执行清单模板（可复制后逐项勾选），不代表当前开发待办；现状以 `docs/CURRENT_STATUS.md` 为准。
> 可追踪清单（用于实际勾选与记录结果）：https://github.com/wyjistest/human-lncrna-atlas/issues/72

**Purpose**: Quick reference for manual validation of HepG2 × H3K9me3 import

**Time Required**: 30-45 minutes

---

## Pre-Testing Setup

- [ ] Backend server is running (`http://localhost:8000`)
- [ ] Frontend dev server is running (`http://localhost:5175`)
- [ ] Data has been imported successfully
- [ ] Browser DevTools open (F12)
- [ ] Screenshot tool ready

---

## Section 1: Filter Panel (10 minutes)

### Mark Type Filter

- [ ] Navigate to `/lncrna-chipseq-overlap`
- [ ] Click on "Mark Type" dropdown
- [ ] **VERIFY**: H3K9me3 appears in the list
- [ ] Select "H3K9me3"
- [ ] **VERIFY**: Filter applies successfully (no error)
- [ ] **Screenshot**: `01-mark-type-filter.png`

### Cell Type Filter

- [ ] Click on "Cell Type" dropdown
- [ ] **VERIFY**: HepG2 appears in the list
- [ ] Select "HepG2"
- [ ] **VERIFY**: Filter applies successfully
- [ ] **Screenshot**: `02-cell-type-filter.png`

### Combined Filters

- [ ] With both H3K9me3 and HepG2 selected:
- [ ] **VERIFY**: No error messages appear
- [ ] **VERIFY**: Table shows loading indicator or data
- [ ] **VERIFY**: Browser console has no errors (check DevTools)
- [ ] **Screenshot**: `03-combined-filters.png`

### Chromosome Filter

- [ ] Select "chr22" from chromosome dropdown
- [ ] Wait for data to load (2-3 seconds)
- [ ] **VERIFY**: Results filtered to chr22 only
- [ ] **Screenshot**: `04-chromosome-filter.png`

---

## Section 2: Results Table (10 minutes)

### Data Display

- [ ] **VERIFY**: Table displays data rows
- [ ] **VERIFY**: Columns include:
  - Chromosome
  - lncRNA Name
  - Target Gene
  - Mark Type (showing "H3K9me3")
  - Cell Type (showing "HepG2")
  - Binding Affinity
  - Peak Signal
- [ ] **Screenshot**: `05-results-table.png`

### Data Quality Check

- [ ] Inspect first 5 rows:
- [ ] **VERIFY**: Mark Type column shows "H3K9me3"
- [ ] **VERIFY**: Cell Type column shows "HepG2"
- [ ] **VERIFY**: Chromosome column shows "chr22" (if filtered)
- [ ] **VERIFY**: Numeric values look reasonable (not NaN, null, or 0)

### Table Interactions

- [ ] Click on column header to sort
- [ ] **VERIFY**: Sorting works correctly
- [ ] Click "Next Page" button
- [ ] **VERIFY**: Pagination works
- [ ] Click on a row to expand/view details (if applicable)
- [ ] **VERIFY**: Detail view works
- [ ] **Screenshot**: `06-table-interactions.png`

---

## Section 3: Statistics & Visualization (10 minutes)

### Statistics Panel

- [ ] Locate statistics panel (usually top of page)
- [ ] **VERIFY**: Total count displays correctly
- [ ] **VERIFY**: Count increases when removing filters
- [ ] **VERIFY**: Count decreases when adding filters

### Heatmap (if available)

- [ ] Navigate to heatmap view/tab
- [ ] **VERIFY**: Heatmap displays 4 rows (cell types) × 6 columns (marks)
- [ ] **VERIFY**: HepG2 row has 6 filled cells (all marks including H3K9me3)
- [ ] **VERIFY**: H3K9me3 column has cells for K562 and HepG2
- [ ] Hover over HepG2 × H3K9me3 cell
- [ ] **VERIFY**: Tooltip shows value > 0
- [ ] **Screenshot**: `07-heatmap.png`

### Charts (if available)

- [ ] Locate bar charts or pie charts
- [ ] **VERIFY**: H3K9me3 appears in mark distribution chart
- [ ] **VERIFY**: HepG2 appears in cell type distribution chart
- [ ] **VERIFY**: Charts render correctly (no broken graphics)
- [ ] **Screenshot**: `08-charts.png`

---

## Section 4: Export Functionality (5 minutes)

### BED Export

- [ ] Apply filters: H3K9me3 + HepG2 + chr22
- [ ] Click "Export" button (or "Export BED")
- [ ] **VERIFY**: Browser prompts to download file
- [ ] **VERIFY**: File name includes "H3K9me3" and "HepG2"
- [ ] Open downloaded file in text editor
- [ ] **VERIFY**: File format is BED6 (6 tab-separated columns)
- [ ] **VERIFY**: All rows show chr22
- [ ] **Screenshot**: `09-bed-export.png` (export dialog)

### CSV Export

- [ ] Click "Export CSV" (or dropdown → CSV)
- [ ] **VERIFY**: Browser prompts to download CSV file
- [ ] Open downloaded file in Excel or text editor
- [ ] **VERIFY**: Headers include: chromosome, lncrna_name, mark_type, cell_type, etc.
- [ ] **VERIFY**: mark_type column shows "H3K9me3"
- [ ] **VERIFY**: cell_type column shows "HepG2"
- [ ] **VERIFY**: Data looks correct (no #N/A, no empty required fields)
- [ ] **Screenshot**: `10-csv-export.png` (opened in Excel)

---

## Section 5: Edge Cases (5 minutes)

### Empty Results

- [ ] Apply impossible filter combination (e.g., H3K9me3 + H1-hESC)
- [ ] **VERIFY**: Shows "No data" message (not error)
- [ ] **VERIFY**: Table shows empty state gracefully
- [ ] **VERIFY**: Export button is disabled or shows appropriate message

### Filter Reset

- [ ] Click "Reset" or "Clear Filters" button
- [ ] **VERIFY**: All filters reset to default
- [ ] **VERIFY**: Results table refreshes with all data
- [ ] **VERIFY**: No errors in console

### Page Refresh

- [ ] Apply filters: H3K9me3 + HepG2
- [ ] Refresh page (F5 or Ctrl+R)
- [ ] **VERIFY**: Filters persist (if designed to)
  - OR filters reset to default (if not designed to persist)
- [ ] **VERIFY**: Page loads without errors

---

## Section 6: Performance (5 minutes)

### Page Load Time

- [ ] Clear browser cache
- [ ] Navigate to `/lncrna-chipseq-overlap`
- [ ] **VERIFY**: Page loads within 3 seconds
- [ ] **VERIFY**: Filters populate within 2 seconds

### Filter Response Time

- [ ] Change mark type filter
- [ ] **VERIFY**: Table updates within 1-2 seconds
- [ ] **VERIFY**: No UI freezing or lag
- [ ] **VERIFY**: Loading indicator shows during data fetch

### Large Result Sets

- [ ] Remove all filters (query all data)
- [ ] **VERIFY**: Page remains responsive
- [ ] **VERIFY**: Pagination works smoothly
- [ ] **VERIFY**: Scrolling is smooth (no jank)

---

## Section 7: Browser Console Check (5 minutes)

### JavaScript Errors

- [ ] Open DevTools Console tab (F12)
- [ ] Perform all actions above again
- [ ] **VERIFY**: No red error messages
- [ ] **VERIFY**: No warnings about failed API calls
- [ ] Acceptable warnings:
  - Favicon 404 (harmless)
  - Sourcemap warnings (harmless)
  - DevTools extensions (harmless)
- [ ] **Screenshot**: `11-console-no-errors.png`

### Network Tab

- [ ] Open DevTools Network tab
- [ ] Select H3K9me3 filter
- [ ] **VERIFY**: API request sent to `/api/v1/lncrna-chipseq-overlap`
- [ ] **VERIFY**: Response status is 200 (green)
- [ ] **VERIFY**: Response time < 500ms
- [ ] Click on API call, view response
- [ ] **VERIFY**: Response JSON includes "mark_type": "H3K9me3"
- [ ] **Screenshot**: `12-network-tab.png`

---

## Section 8: Internationalization (Optional, 5 minutes)

### English Interface

- [ ] Set browser/app language to English
- [ ] **VERIFY**: "Mark Type" label in English
- [ ] **VERIFY**: "Cell Type" label in English
- [ ] **VERIFY**: H3K9me3 displays correctly
- [ ] **Screenshot**: `13-english-ui.png`

### Chinese Interface (if supported)

- [ ] Set browser/app language to Chinese
- [ ] **VERIFY**: Labels display in Chinese
- [ ] **VERIFY**: H3K9me3 still displays (not translated)
- [ ] **VERIFY**: Filters work correctly
- [ ] **Screenshot**: `14-chinese-ui.png`

---

## Final Verification

### Success Criteria (All must be checked)

- [ ] ✅ H3K9me3 appears in mark filter dropdown
- [ ] ✅ HepG2 × H3K9me3 combination works
- [ ] ✅ Results table displays data correctly
- [ ] ✅ Export functionality works (BED and CSV)
- [ ] ✅ No JavaScript errors in console
- [ ] ✅ Performance is acceptable (<3s page load)
- [ ] ✅ No UI bugs or broken elements
- [ ] ✅ All screenshots captured

---

## Issue Reporting Template

If you find any issues, document using this template:

```markdown
## Issue: [Brief description]

**Severity**: Critical / Major / Minor
**Component**: Filter / Table / Export / Heatmap / Other

**Steps to Reproduce**:
1.
2.
3.

**Expected Behavior**:


**Actual Behavior**:


**Screenshot**: [Attach screenshot]

**Browser**: Chrome 120 / Firefox 121 / Safari 17
**Console Errors**: [Copy any errors from console]

**Additional Context**:

```

---

## Post-Testing Actions

- [ ] Archive all screenshots to `/docs/testing/screenshots/phase-3-1/`
- [ ] Document any issues found in issue tracker
- [ ] Complete test report using template in `phase-3-1-testing-strategy.md`
- [ ] Notify team of test results
- [ ] Update CHANGELOG.md if tests passed

---

## Quick Commands Reference

```bash
# Check backend is running
curl http://localhost:8000/api/v1/health

# Check H3K9me3 is available
curl "http://localhost:8000/api/v1/features/chipseq/marks/available?species=1" | jq '.marks[] | select(.mark_name=="H3K9me3")'

# Query HepG2 × H3K9me3
curl "http://localhost:8000/api/v1/lncrna-chipseq-overlap?mark_type=H3K9me3&cell_type=HepG2&chromosome=chr22" | jq '.total'

# Check heatmap data
curl "http://localhost:8000/api/v1/lncrna-chipseq-overlap/heatmap?x_axis=mark_type&y_axis=cell_type" | jq '.valid_combinations'
```

---

**Checklist Version**: 1.0
**Last Updated**: 2025-12-07
**Estimated Time**: 30-45 minutes
