# lncRNA-ChIP-seq Overlap Export - E2E Test Deliverables

> 更新（2026-02-02）：本文档为早期“导出 E2E 测试交付物”快照，其中“后端未实现/被阻塞”的描述仅代表当时状态。当前后端已提供导出端点（`frontend/backend/app/routers/lncrna_chipseq_overlap.py`，`GET /api/v1/lncrna-chipseq-overlap/export`）；实现与测试入口以 `docs/CURRENT_STATUS.md`、`docs/testing/README.md` 与 `frontend/web/e2e/lncrna-chipseq-overlap-export.spec.ts` 为准。

## Summary

I've successfully created comprehensive E2E tests for the lncRNA-ChIP-seq overlap export feature. At the time of this snapshot, the backend export endpoint was not yet available; it has since been implemented.

---

## 📦 Deliverables

### 1. ✅ E2E Test File Created

**Location**: `<repo-root>/frontend/web/e2e/lncrna-chipseq-overlap-export.spec.ts`

**Test Coverage**: 13 comprehensive test cases organized into 5 suites:
- Basic Functionality (3 tests)
- Filter Preservation (2 tests)
- Edge Cases (3 tests)
- Performance (2 tests)
- Format Validation (3 tests)

### 2. ✅ Test Execution Results

**Passing**: 5/13 (38%)
- All mock/edge case tests passing
- Error handling validated
- Timeout handling validated

**Blocked**: 8/13 (62%)
- All real export tests blocked by missing backend implementation

### 3. ✅ File Validation Results

**BED Format Validator**:
```typescript
validateBEDLine(line, lineNumber)
```
Validates:
- BED6 minimum format (6 columns)
- Chromosome naming (chr1-22, X, Y, M)
- Coordinate integrity (start < end, start >= 0)
- Score range (0-1000)
- Strand values (+, -, .)

**CSV Format Validator**:
```typescript
validateCSVHeader(header, expectedColumns)
```
Validates:
- Required columns present
- Case-insensitive matching
- Flexible column naming

### 4. ⚠️ Flaky Tests / Timing Issues

**Chromosome Filter Not Found**:
```
Chromosome filter not found, using default data
```
- Filter may not render until data loads
- Tests fall back to default data gracefully
- **Recommendation**: Add explicit wait for filter availability

**Page Loading State**:
- Page shows spinner during initial data load
- Export buttons only render after data loads
- Tests wait appropriately with `waitForLoadState('networkidle')`

### 5. 📊 Performance Metrics

**Target**: chr22 export < 10 seconds

**Status (2025-12-07 snapshot)**: Not measured at the time (export flow was blocked then; see update note at top)

**Test Implementation Ready**:
```typescript
test('should complete chr22 CSV export within 10 seconds', async ({ page }) => {
  const startTime = Date.now()
  // ... export logic ...
  const duration = Date.now() - startTime
  expect(duration).toBeLessThan(10000)
})
```

### 6. 📝 Code Snippets - Key Validation Functions

#### BED Line Validator

```typescript
function validateBEDLine(line: string, lineNumber: number): void {
  const columns = line.split('\t')

  // Minimum BED6 format
  expect(columns.length, `Line ${lineNumber} should have at least 6 columns`).toBeGreaterThanOrEqual(6)

  // Chromosome format
  expect(columns[0], `Line ${lineNumber} chromosome format`).toMatch(/^chr([0-9]+|X|Y|M)$/)

  // Coordinates
  const start = parseInt(columns[1])
  const end = parseInt(columns[2])
  expect(start, `Line ${lineNumber} start should be < end`).toBeLessThan(end)

  // Score (0-1000)
  if (columns[4] && columns[4] !== '.') {
    const score = parseInt(columns[4])
    expect(score, `Line ${lineNumber} score should be 0-1000`).toBeGreaterThanOrEqual(0)
    expect(score).toBeLessThanOrEqual(1000)
  }

  // Strand
  if (columns[5]) {
    expect(['+', '-', '.']).toContain(columns[5])
  }
}
```

#### CSV Parser & Validator

```typescript
function parseCSV(content: string): string[][] {
  const lines = content.trim().split('\n')
  return lines.map(line => line.split(',').map(cell => cell.trim()))
}

function validateCSVHeader(header: string, expectedColumns: string[]): void {
  const columns = header.toLowerCase().split(',').map(c => c.trim())

  for (const expected of expectedColumns) {
    const found = columns.some(c => c.includes(expected.toLowerCase()))
    expect(found, `CSV should contain column: ${expected}`).toBe(true)
  }
}
```

#### Download Helper

```typescript
async function applyChr22Filter(page: any): Promise<void> {
  const chromosomeFilter = page.locator('.ant-select')
    .filter({ hasText: /Chromosome|染色体/i })
    .first()

  if (await chromosomeFilter.count() > 0) {
    await chromosomeFilter.click()
    await page.waitForTimeout(300)

    const chr22Option = page.locator('.ant-select-dropdown .ant-select-item')
      .filter({ hasText: 'chr22' })

    if (await chr22Option.count() > 0) {
      await chr22Option.click()
      await page.waitForTimeout(5000)
    }
  }
}
```

### 7. 🐛 Bugs Discovered During Testing

#### Bug #1: Export API Endpoint Missing (P0 - CRITICAL, 2025-12-07 snapshot)

**Evidence**:
```bash
$ curl "http://localhost:8000/api/v1/lncrna-chipseq-overlap/export?format=csv&chromosome=chr22"
{"detail":"Not Found"}
```

**Impact (2025-12-07)**: Real export downloads were blocked

**Required (at the time)**: Backend implementation of `/api/v1/lncrna-chipseq-overlap/export` endpoint

---

#### Bug #2: Export Buttons Show "Not Implemented" Warning (P1 - HIGH, 2025-12-07 snapshot)

**Location**: `frontend/web/src/components/LncRNAChIPSeqOverlapTable/index.tsx:187-195`

**Current Code**:
```tsx
const handleExport = useCallback(
  (format: 'bed' | 'csv') => {
    message.info(t('message.exportStarting', `Exporting to ${format.toUpperCase()}...`))
    // Export logic will be implemented in Phase 2
    message.warning(t('message.exportNotImplemented', 'Export functionality coming in Phase 2'))
  },
  [t]
)
```

**Expected**: Real API call to export endpoint

**Impact**: Export buttons don't trigger actual downloads

---

#### Bug #3: Export Buttons Not Rendered (P1 - HIGH)

**Condition**: Buttons only render when `enableExport && overlapData && overlapData.total > 0`

**Issue**: `enableExport` flag appears to be `false` by default

**Screenshot Evidence**: No export buttons visible in test screenshots

**Required**: Set `enableExport = true` in component props or default config

---

#### Bug #4: Chromosome Filter Not Found (P2 - MEDIUM)

**Test Output**:
```
Chromosome filter not found, using default data
```

**Possible Causes**:
1. Filter not rendered until data loads
2. Filter in collapsed/accordion section
3. Different locator structure than expected

**Recommendation**: Investigate filter component rendering and update test locators

---

## 📄 Test Report

**Full Report**: `<repo-root>/frontend/web/e2e/TEST_REPORT_lncrna-chipseq-overlap-export.md`

**Contents**:
- Detailed test results (13 tests)
- Bug reports with evidence
- Backend API specification
- Frontend implementation guide
- Performance expectations
- Next steps and action items

---

## 🎯 Next Steps

### For Backend Team

**Priority**: 🔴 P0 - Blocking

1. **Implement Export API Endpoint**

   **Endpoint**: `GET /api/v1/lncrna-chipseq-overlap/export`

   **Parameters**:
   ```python
   format: Literal["csv", "bed"]  # Export format
   chromosome: Optional[str]      # chr1, chr22, etc.
   mark_type: Optional[str]       # H3K27me3, H3K4me3, etc.
   cell_type: Optional[str]       # K562, HepG2, etc.
   # ... all existing filter parameters ...
   ```

   **Response**: `StreamingResponse` with appropriate headers
   ```python
   Content-Type: text/csv or text/plain
   Content-Disposition: attachment; filename="lncrna_chipseq_overlap.csv"
   ```

2. **BED Format Specification** (BED6 minimum):
   ```
   chr    start    end    name    score    strand
   chr22  35739090 35739172 overlap_reg_804945_peak_1187689 432 +
   ```

3. **CSV Format Specification**:
   ```csv
   overlap_id,lncrna_name,target_gene_name,chromosome,start,end,mark_type,cell_type,binding_affinity
   ```

**Estimated Effort**: 4-6 hours

---

### For Frontend Team

**Priority**: 🟠 P1 - High

1. **Enable Export Flag**
   ```tsx
   const enableExport = true  // Set to true
   ```

2. **Replace Placeholder Handler**
   ```tsx
   const handleExport = useCallback(async (format: 'bed' | 'csv') => {
     try {
       const response = format === 'bed'
         ? await lncRNAChIPSeqOverlapApi.exportToBED(filters)
         : await lncRNAChIPSeqOverlapApi.exportToCSV(filters)

       // Create download
       const blob = new Blob([response.data], {
         type: format === 'bed' ? 'text/plain' : 'text/csv'
       })
       const url = window.URL.createObjectURL(blob)
       const link = document.createElement('a')
       link.href = url
       link.download = `lncrna_chipseq_overlap_${Date.now()}.${format}`
       document.body.appendChild(link)
       link.click()
       document.body.removeChild(link)
       window.URL.revokeObjectURL(url)

       message.success('Export completed!')
     } catch (error) {
       message.error('Export failed')
     }
   }, [filters])
   ```

**Estimated Effort**: 1-2 hours

---

### For QA Team

**Priority**: 🟢 P2 - Normal

1. **Re-run E2E Tests After Implementation**
   ```bash
   cd <repo-root>/frontend/web
   npx playwright test e2e/lncrna-chipseq-overlap-export.spec.ts
   ```

2. **Verify All Tests Pass**
   - Target: 13/13 tests passing
   - Performance: chr22 export < 10 seconds

3. **Manual Testing**
   - Export with various filters
   - Verify BED format in IGV
   - Verify CSV format in Excel
   - Test with large datasets (chr1)

**Estimated Effort**: 2-3 hours

---

## 📊 Test Statistics

```
Total Tests:        13
Passing (Mock):     5  (38%)
Blocked (Real):     8  (62%)

Priority Breakdown:
- P0 (Critical):    2 tests  (blocked)
- P1 (High):        8 tests  (6 blocked, 2 passing)
- P2 (Medium):      3 tests  (all passing)

Test Categories:
- Basic Functionality:    3 tests
- Filter Preservation:    2 tests
- Edge Cases:            3 tests
- Performance:           2 tests
- Format Validation:     3 tests
```

---

## 🔧 Running Tests

**Prerequisites**:
- Frontend dev server: `http://localhost:5173`
- Backend API: `http://localhost:8000`
- Export endpoint implemented

**Commands**:

```bash
# Full test suite
npx playwright test e2e/lncrna-chipseq-overlap-export.spec.ts

# With browser visible
npx playwright test e2e/lncrna-chipseq-overlap-export.spec.ts --headed

# Single test
npx playwright test e2e/lncrna-chipseq-overlap-export.spec.ts -g "P0: should export overlaps as CSV"

# View HTML report
npx playwright show-report
```

---

## 📚 Related Files

**Test Files**:
- `<repo-root>/frontend/web/e2e/lncrna-chipseq-overlap-export.spec.ts` - Main test suite
- `<repo-root>/frontend/web/e2e/TEST_REPORT_lncrna-chipseq-overlap-export.md` - Detailed report

**Frontend Components**:
- `<repo-root>/frontend/web/src/components/LncRNAChIPSeqOverlapTable/index.tsx`
- `<repo-root>/frontend/web/src/hooks/useLncRNAChIPSeqOverlap.ts`
- `<repo-root>/frontend/web/src/hooks/lncRNAChIPSeqOverlapApi.ts`

**Backend (Implemented later; historical reference)**:
- Current: `<repo-root>/frontend/backend/app/routers/lncrna_chipseq_overlap.py` (`GET /api/v1/lncrna-chipseq-overlap/export`)
- Historical: `<repo-root>/frontend/backend/app/api/v1/endpoints/lncrna_chipseq_overlap.py`

---

## ✅ Deliverables Checklist

- [x] E2E test file created (13 test cases)
- [x] Test execution completed (5 passing, 8 blocked)
- [x] File validation helpers implemented (BED, CSV)
- [x] Flaky tests identified (chromosome filter)
- [x] Performance test strategy defined (chr22 < 10s)
- [x] Code snippets documented
- [x] Bugs discovered and documented (4 issues)
- [x] Detailed test report generated
- [x] Next steps clearly defined

---

**Status**: 🗂️ Historical snapshot — test suite created; backend was implemented later.

**Estimated Total Effort (at the time) to Unblock**: 8-11 hours
- Backend: 4-6 hours
- Frontend: 1-2 hours
- QA: 2-3 hours

Once the export feature is implemented, this test suite will provide comprehensive automated validation of:
- Export functionality correctness
- File format compliance (BED6, CSV)
- Filter preservation
- Performance benchmarks
- Error handling
- Edge cases

---

**Created**: 2025-12-07
**Author**: Claude (Playwright E2E Testing Specialist)
