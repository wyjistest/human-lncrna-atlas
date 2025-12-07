# Phase 3.1: HepG2 × H3K9me3 Import - Comprehensive Testing Strategy

## Executive Summary

**Objective**: Import HepG2 × H3K9me3 ChIP-seq data and validate the "zero frontend code changes" hypothesis.

**Success Criteria**:
- Data import completes successfully (40K-80K peaks)
- Backend API auto-exposes new mark
- Frontend UI auto-displays new mark
- No code changes required in frontend
- All existing functionality remains intact

**Estimated Testing Time**: 4-6 hours total
- Automated: 2 hours (setup + execution)
- Manual: 2-4 hours (validation + documentation)

---

## Test Layer 1: Data Import Validation

### Pre-Import Checks

**Script**: `scripts/phase_3_1_pre_import_validation.sh`

**Purpose**: Validate data file quality before importing to database

**Checklist**:

```bash
# Run validation
bash scripts/phase_3_1_pre_import_validation.sh data/HepG2_H3K9me3.narrowPeak.gz

# Expected validations:
✓ [PASS] File exists
✓ [PASS] File size is reasonable (5-50 MB)
✓ [PASS] Peak format is valid (narrowPeak with 10 columns)
✓ [PASS] Peak count is reasonable (40K-80K)
✓ [PASS] All chromosomes use UCSC naming (chr1, chr2, ...)
✓ [PASS] All peak coordinates are valid (start < end, non-negative)
✓ [PASS] Signal values are within reasonable range (FE: 2-50)
✓ [PASS] No duplicate peaks found
```

**Data Quality Thresholds**:
- File size: 5-50 MB (compressed)
- Peak count: 20,000 - 150,000
- Average fold enrichment: 1.5 - 100
- Chromosome format: chr1-22, chrX, chrY, chrM

**Failure Handling**:
- If validation fails: DO NOT PROCEED with import
- Fix data issues at source (re-download or regenerate)
- Document any data quality concerns

---

### Post-Import Checks

**Script**: `scripts/phase_3_1_post_import_validation.py`

**Purpose**: Validate data integrity after import to database

**Checklist**:

```bash
# Run validation
python3 scripts/phase_3_1_post_import_validation.py

# Expected validations:
✓ [PASS] Experiment exists: HepG2_H3K9me3_ENCSR... (ID: XXX)
✓ [PASS] Peak count is within expected range (20K-150K)
✓ [PASS] No duplicate peaks found
✓ [PASS] All peaks have valid coordinate order (start < end)
✓ [PASS] Signal values are within reasonable range
✓ [PASS] Peaks found on all major chromosomes
✓ [PASS] Cell type is correct (HepG2)
✓ [PASS] HepG2 now has complete coverage (6/6 marks)
```

**Database Integrity Checks**:
1. **Experiment metadata**: Cell type, mark name, accession
2. **Peak data quality**: Coordinates, signal values, q-values
3. **Coverage matrix**: HepG2 should show 6/6 marks
4. **Chromosome distribution**: Peaks on chr1-22, chrX
5. **No duplicates**: Each peak coordinate is unique
6. **Foreign keys**: All references valid

**Expected Coverage Matrix After Import**:

```
Cell Type    H3K27me3  H3K4me3  H3K27ac  H3K4me1  H3K36me3  H3K9me3
-----------  --------  -------  -------  -------  --------  -------
K562         ✓         ✓        ✓        ✓        ✓         ✓
HepG2        ✓         ✓        ✓        ✓        ✓         ✓  ← NEW
GM12878      ✓         ✓        ✓        ✓        ---       ---
H1-hESC      ✓         ✓        ✓        ✓        ---       ---
```

**Validation Script**: `scripts/validate_additional_marks.py`

```bash
# Run comprehensive validation
python3 scripts/validate_additional_marks.py

# Expected output:
Coverage Matrix:
  HepG2: 6/6 marks complete
  Total peaks: +40K-80K from previous count
  Valid combinations: 23 → 24
```

---

## Test Layer 2: liftOver Quality (If Applicable)

**Only if hg38 → hg19 conversion is required**

### Coordinate Mapping Validation

**Purpose**: Ensure liftOver conversion maintains data integrity

**Validation Checklist**:

```bash
# Sample validation commands
# 1. Check mapping success rate
liftOver input.hg38.bed hg38ToHg19.over.chain.gz output.hg19.bed unmapped.bed
wc -l input.hg38.bed output.hg19.bed unmapped.bed

# Expected: >95% of peaks successfully mapped
# unmapped.bed should have <5% of total peaks
```

**Quality Metrics**:
1. **Mapping rate**: >95% of peaks successfully mapped
2. **Coordinate validity**: Start < end after conversion
3. **Chromosome consistency**: No cross-chromosome mappings
4. **Peak length preservation**: Δlength < 10% for most peaks
5. **No out-of-bounds**: All coordinates within chromosome limits

**Test Approach**:

```bash
# Validate mapped peaks
bedtools intersect -a original_hg38.bed -b lifted_hg19.bed -wo | \
  awk '{
    original_len = $3 - $2
    lifted_len = $9 - $8
    if (original_len > 0) {
      pct_change = (lifted_len - original_len) / original_len * 100
      if (pct_change > 10 || pct_change < -10) {
        print "Large length change: " pct_change "%"
      }
    }
  }'

# Check for chromosome mismatches
bedtools intersect -a original_hg38.bed -b lifted_hg19.bed -wo | \
  awk '$1 != $7 {print "Chromosome mismatch: " $1 " -> " $7}' | \
  wc -l

# Expected: 0 mismatches
```

**Failure Handling**:
- If <90% mapping rate: Review data quality, consider alternative source
- If length changes >20%: Investigate specific regions, may need manual curation
- If chromosome mismatches: CRITICAL ERROR - do not proceed

---

## Test Layer 3: Backend API Integration

### API Endpoint Tests

**Purpose**: Validate that backend APIs automatically expose new mark

**Test 1: Marks List Includes H3K9me3 for HepG2**

```bash
# Request available marks
curl "http://localhost:8000/api/v1/features/chipseq/marks/available?species=1" | jq

# Expected response:
{
  "marks": [
    {
      "mark_name": "H3K9me3",
      "mark_category": "Repressive",
      "cell_types": ["K562", "HepG2"],  ← HepG2 appears here
      "total_experiments": 2,
      "total_peaks": 180000
    },
    // ... other marks
  ]
}
```

**Success Criteria**: H3K9me3 appears in marks list with HepG2 in cell_types array

---

**Test 2: Query HepG2 × H3K9me3 Overlaps**

```bash
# Query overlaps for specific combination
curl "http://localhost:8000/api/v1/lncrna-chipseq-overlap?mark_type=H3K9me3&cell_type=HepG2&chromosome=chr22&page=1&page_size=10" | jq

# Expected response:
{
  "total": 1234,  ← Should be > 0
  "page": 1,
  "page_size": 10,
  "items": [
    {
      "overlap_id": 12345,
      "chromosome": "chr22",
      "mark_type": "H3K9me3",
      "cell_type": "HepG2",
      "lncrna_name": "MALAT1",
      // ... other fields
    },
    // ... more items
  ]
}
```

**Success Criteria**:
- HTTP 200 status
- Total count > 0
- Items array contains overlaps with correct mark_type and cell_type

---

**Test 3: Heatmap Matrix Completeness**

```bash
# Request heatmap data
curl "http://localhost:8000/api/v1/lncrna-chipseq-overlap/heatmap?x_axis=mark_type&y_axis=cell_type" | jq

# Expected response:
{
  "x_axis": ["H3K27me3", "H3K4me3", "H3K27ac", "H3K4me1", "H3K36me3", "H3K9me3"],
  "y_axis": ["K562", "HepG2", "GM12878", "H1-hESC"],
  "matrix": [
    [1234, 5678, 910, 1112, 1314, 1516],  // K562
    [2234, 6678, 1010, 2112, 2314, 2516], // HepG2 ← NEW: 6 values (was 5)
    [3234, 7678, 1110, 3112, 0, 0],       // GM12878
    [4234, 8678, 1210, 4112, 0, 0]        // H1-hESC
  ],
  "valid_combinations": 24,  ← Should increase from 23 to 24
  "total_combinations": 24
}
```

**Success Criteria**:
- valid_combinations = 24 (was 23 before import)
- HepG2 row has 6 non-zero values
- Matrix dimensions: 4 × 6

---

**Test 4: Filter Combinations Work**

```bash
# Test various filter combinations
curl "http://localhost:8000/api/v1/lncrna-chipseq-overlap?mark_type=H3K9me3" | jq '.total'
# Expected: > 0

curl "http://localhost:8000/api/v1/lncrna-chipseq-overlap?cell_type=HepG2" | jq '.total'
# Expected: > 0 (all HepG2 marks)

curl "http://localhost:8000/api/v1/lncrna-chipseq-overlap?mark_type=H3K9me3&cell_type=HepG2" | jq '.total'
# Expected: > 0 (only HepG2 × H3K9me3)
```

---

**Test 5: Export API Includes New Mark**

```bash
# Export HepG2 × H3K9me3 overlaps as BED
curl "http://localhost:8000/api/v1/lncrna-chipseq-overlap/export?format=bed&mark_type=H3K9me3&cell_type=HepG2&chromosome=chr22&max_rows=100" -o test_export.bed

# Validate export file
head -20 test_export.bed

# Expected:
# - BED6 format (6 columns)
# - All rows have chr22
# - Score values 0-1000
# - No duplicate coordinates

# Export as CSV
curl "http://localhost:8000/api/v1/lncrna-chipseq-overlap/export?format=csv&mark_type=H3K9me3&cell_type=HepG2&chromosome=chr22&max_rows=100" -o test_export.csv

# Validate CSV
head -5 test_export.csv

# Expected:
# - 19 columns
# - mark_type column contains "H3K9me3"
# - cell_type column contains "HepG2"
```

---

### Backend Unit Tests

**Existing Test Suite**: `frontend/backend/tests/test_overlap_export.py`

```bash
# Run existing tests to ensure no regression
cd frontend/backend
pytest tests/test_overlap_export.py -v

# All 22 tests should pass:
# - test_export_bed_format_default ✓
# - test_export_csv_format ✓
# - test_export_with_mark_type_filter ✓
# - test_export_with_multiple_filters ✓
# - ... (18 more tests) ✓

# Expected: 22 passed, 0 failed
```

**Add New Test Case** (optional):

```python
# Add to test_overlap_export.py
def test_export_hepg2_h3k9me3_specific(api_client, api_assert):
    """Verify HepG2 × H3K9me3 exports correctly"""
    response = api_client.get("/api/v1/lncrna-chipseq-overlap/export", params={
        "format": "csv",
        "mark_type": "H3K9me3",
        "cell_type": "HepG2",
        "chromosome": "chr22",
        "max_rows": 50
    })

    api_assert.assert_successful_response(response)

    content = response.text
    headers, rows = parse_csv_content(content)

    # Verify all rows are HepG2 × H3K9me3
    for row in rows:
        assert row['mark_type'] == "H3K9me3"
        assert row['cell_type'] == "HepG2"
```

---

## Test Layer 4: Frontend UI Verification

### Playwright E2E Tests

**Test Suite**: `frontend/web/e2e/phase-3-1-validation.spec.ts`

**Purpose**: Validate frontend automatically displays new data WITHOUT code changes

```bash
# Run E2E tests
cd frontend/web
npm run test:e2e -- phase-3-1-validation.spec.ts

# Expected: 7 tests passed
```

**Test Coverage**:

#### Test 1: Mark Filter Includes H3K9me3

```typescript
// Verifies H3K9me3 appears in dropdown options
await markSelector.click()
const h3k9me3Option = page.locator('.ant-select-item').filter({ hasText: 'H3K9me3' })
await expect(h3k9me3Option).toBeVisible()
```

**Expected**: H3K9me3 option visible in mark type dropdown

---

#### Test 2: HepG2 × H3K9me3 Combination Works

```typescript
// Select mark type: H3K9me3
// Select cell type: HepG2
// Verify no error messages
const errorMessage = page.locator('.ant-message-error, .ant-alert-error')
expect(await errorMessage.isVisible()).toBe(false)
```

**Expected**: Filter combination works without errors

---

#### Test 3: Results Table Loads Data

```typescript
// Apply filters: H3K9me3 + HepG2 + chr22
// Wait for table to load
const tableRows = page.locator('.ant-table-tbody tr')
const rowCount = await tableRows.count()

expect(rowCount).toBeGreaterThan(0)
```

**Expected**: Table displays overlap data

---

#### Test 4: Heatmap Shows Complete Matrix

```typescript
// Navigate to heatmap view
// Verify HepG2 row has data for H3K9me3 column
const hepg2Label = page.locator('text=HepG2')
const h3k9me3Label = page.locator('text=H3K9me3')

await expect(hepg2Label).toBeVisible()
await expect(h3k9me3Label).toBeVisible()
```

**Expected**: Heatmap displays all 24 combinations (4 cell types × 6 marks)

---

#### Test 5: Export Includes New Mark

```typescript
// Apply filters: H3K9me3 + HepG2
// Click export button
// Verify export URL contains correct parameters
expect(exportUrl).toContain('H3K9me3')
expect(exportUrl).toContain('HepG2')
```

**Expected**: Export function works with new mark

---

#### Test 6: No JavaScript Errors

```typescript
// Monitor console for errors during interactions
page.on('console', (msg) => {
  if (msg.type() === 'error') errors.push(msg.text())
})

// Perform interactions
// Verify no critical errors
expect(criticalErrors.length).toBe(0)
```

**Expected**: No JavaScript errors in browser console

---

#### Test 7: API Endpoint Returns Data

```typescript
// Direct API call
const response = await page.request.get(
  'http://localhost:8000/api/v1/lncrna-chipseq-overlap?mark_type=H3K9me3&cell_type=HepG2'
)

expect(response.ok()).toBe(true)
const data = await response.json()
expect(data.total).toBeGreaterThan(0)
```

**Expected**: API returns data successfully

---

### Manual UI Testing

**Checklist** (to be performed by human tester):

**1. Filter Panel**:
- [ ] Mark type dropdown includes "H3K9me3"
- [ ] Can select "H3K9me3" from dropdown
- [ ] Selection persists after page refresh
- [ ] Can combine with other filters (cell type, chromosome)

**2. Cell Type Filter**:
- [ ] HepG2 option is available
- [ ] Can select HepG2
- [ ] HepG2 + H3K9me3 combination works
- [ ] No error messages displayed

**3. Results Table**:
- [ ] Table loads data for HepG2 × H3K9me3
- [ ] Data displays correctly (mark_type, cell_type columns)
- [ ] Pagination works
- [ ] Sorting works
- [ ] No broken UI elements

**4. Statistics Display**:
- [ ] Total count updates when H3K9me3 is selected
- [ ] Cell type distribution includes HepG2
- [ ] Mark type distribution includes H3K9me3
- [ ] Charts/graphs render correctly

**5. Export Function**:
- [ ] Export button is enabled with data
- [ ] BED export works (downloads file)
- [ ] CSV export works (downloads file)
- [ ] Exported files contain correct data (HepG2, H3K9me3)
- [ ] File naming includes filter parameters

**6. Heatmap Visualization**:
- [ ] Heatmap displays 4 × 6 grid (4 cell types × 6 marks)
- [ ] HepG2 row is complete (all 6 marks)
- [ ] H3K9me3 column has data for K562 and HepG2
- [ ] Tooltips show correct values
- [ ] Color scale is appropriate

**7. Performance**:
- [ ] Page loads within 3 seconds
- [ ] Filter changes respond within 1 second
- [ ] Table pagination is smooth
- [ ] No UI lag or freezing

**8. Internationalization**:
- [ ] English labels display correctly
- [ ] Chinese labels display correctly (if applicable)
- [ ] Language toggle works

**Screenshots to Capture**:
1. Mark type dropdown showing H3K9me3
2. Results table with HepG2 × H3K9me3 data
3. Heatmap showing complete 24/24 matrix
4. Export dialog with H3K9me3 selected
5. Statistics panel with updated counts

---

## Test Layer 5: Performance & Regression Testing

### Performance Impact Assessment

**Purpose**: Ensure new data doesn't degrade system performance

**Baseline Metrics** (before import):

```bash
# Measure query performance
time curl "http://localhost:8000/api/v1/lncrna-chipseq-overlap?chromosome=chr22"
# Baseline: ~50-100ms

time curl "http://localhost:8000/api/v1/lncrna-chipseq-overlap/heatmap?x_axis=mark_type&y_axis=cell_type"
# Baseline: ~200-500ms
```

**Post-Import Metrics**:

```bash
# Re-run same queries
time curl "http://localhost:8000/api/v1/lncrna-chipseq-overlap?chromosome=chr22"
# Expected: Similar to baseline (~50-150ms)

time curl "http://localhost:8000/api/v1/lncrna-chipseq-overlap/heatmap?x_axis=mark_type&y_axis=cell_type"
# Expected: Similar to baseline (~200-600ms)
```

**Acceptable Performance**:
- Query time increase: <50% from baseline
- Absolute query time: <500ms for most queries
- Heatmap rendering: <1000ms

**Performance Test Script**:

```bash
#!/bin/bash
# performance_test.sh

echo "Performance Test: Before vs After Import"

for i in {1..10}; do
  time curl -s "http://localhost:8000/api/v1/lncrna-chipseq-overlap?chromosome=chr22" > /dev/null
done | grep real | awk '{sum+=$2} END {print "Avg time: " sum/10}'

# Run this before and after import, compare results
```

---

### Regression Testing

**Purpose**: Ensure existing functionality still works after data import

**Test Checklist**:

**1. Existing Filters Still Work**:
```bash
# Test each existing mark type
for mark in H3K27me3 H3K4me3 H3K27ac H3K4me1 H3K36me3; do
  echo "Testing $mark..."
  curl -s "http://localhost:8000/api/v1/lncrna-chipseq-overlap?mark_type=$mark" | jq '.total'
done

# Expected: All marks return data
```

**2. Existing Cell Types Still Work**:
```bash
# Test each existing cell type
for cell in K562 HepG2 GM12878 H1-hESC; do
  echo "Testing $cell..."
  curl -s "http://localhost:8000/api/v1/lncrna-chipseq-overlap?cell_type=$cell" | jq '.total'
done

# Expected: All cell types return data
```

**3. Existing Exports Still Work**:
```bash
# Test BED export for existing combination
curl "http://localhost:8000/api/v1/lncrna-chipseq-overlap/export?format=bed&mark_type=H3K27me3&cell_type=K562&chromosome=chr22&max_rows=100" -o regression_test.bed

# Validate: File should be valid BED6 format
head regression_test.bed
```

**4. Statistics Still Calculate Correctly**:
```bash
# Get statistics before and after
curl "http://localhost:8000/api/v1/lncrna-chipseq-overlap/stats" | jq

# Expected:
# - total_overlaps increased by ~40K-80K
# - valid_combinations = 24 (was 23)
# - all other stats still present
```

**5. Existing UI Pages Still Work**:
- [ ] Home page loads
- [ ] Gene detail pages load
- [ ] lncRNA search works
- [ ] ChIP-seq overlap page works
- [ ] Other analysis pages work

---

### Database Performance Checks

**Purpose**: Ensure database queries remain efficient

**Test Queries**:

```sql
-- 1. Check index usage (should use indexes, not full table scan)
EXPLAIN ANALYZE
SELECT * FROM chipseq_peaks
WHERE experiment_id IN (
  SELECT experiment_id FROM chipseq_experiments
  WHERE cell_type = 'HepG2'
)
AND chromosome = 'chr22'
LIMIT 100;

-- Expected: Index Scan (not Seq Scan), execution time < 50ms

-- 2. Check join performance
EXPLAIN ANALYZE
SELECT e.cell_type, m.mark_name, COUNT(*) as peaks
FROM chipseq_experiments e
JOIN chipseq_peaks p ON e.experiment_id = p.experiment_id
JOIN epigenetic_mark_types m ON e.mark_type_id = m.mark_type_id
WHERE e.is_active = TRUE
GROUP BY e.cell_type, m.mark_name;

-- Expected: Hash Join, execution time < 500ms

-- 3. Check table sizes
SELECT
  schemaname,
  tablename,
  pg_size_pretty(pg_total_relation_size(schemaname||'.'||tablename)) AS size,
  n_live_tup as rows
FROM pg_stat_user_tables
WHERE tablename IN ('chipseq_experiments', 'chipseq_peaks')
ORDER BY pg_total_relation_size(schemaname||'.'||tablename) DESC;

-- Monitor size growth, should be reasonable (< 500MB total for peaks)
```

---

## Edge Case Testing

### Edge Cases to Validate

**1. Empty Results Handling**:
```bash
# Query combination with no data (should return empty, not error)
curl "http://localhost:8000/api/v1/lncrna-chipseq-overlap?mark_type=H3K9me3&cell_type=GM12878"

# Expected: {"total": 0, "items": []}
# NOT: 500 Internal Server Error
```

**2. Invalid Filter Combinations**:
```bash
# Invalid mark type
curl "http://localhost:8000/api/v1/lncrna-chipseq-overlap?mark_type=InvalidMark"

# Expected: 400 Bad Request or empty results

# Invalid cell type
curl "http://localhost:8000/api/v1/lncrna-chipseq-overlap?cell_type=InvalidCell"

# Expected: 400 Bad Request or empty results
```

**3. Large Result Sets**:
```bash
# Query without filters (should paginate, not timeout)
curl "http://localhost:8000/api/v1/lncrna-chipseq-overlap?page=1&page_size=100"

# Expected: Returns first 100 results, includes pagination metadata
```

**4. Special Characters in Cell Type** (H1-hESC has hyphen):
```bash
# Verify H1-hESC still works (regression test)
curl "http://localhost:8000/api/v1/lncrna-chipseq-overlap?cell_type=H1-hESC"

# Expected: Valid response, no encoding issues
```

**5. Partial Import Recovery**:
- If import fails midway, database should roll back (no partial data)
- Re-running import should be idempotent (safe to retry)

**6. Data Conflicts**:
- If HepG2 × H3K9me3 already exists, import should:
  - Option A: Skip (warn user)
  - Option B: Update (replace old data)
  - Option C: Fail (prevent duplicates)

---

## Test Execution Plan

### Phase 1: Pre-Import (30 minutes)

1. **Prepare test environment**:
   - [ ] Backend server running
   - [ ] Frontend dev server running
   - [ ] Database accessible
   - [ ] Test data downloaded

2. **Run pre-import validation**:
   ```bash
   bash scripts/phase_3_1_pre_import_validation.sh data/HepG2_H3K9me3.narrowPeak.gz
   ```

3. **Capture baseline metrics**:
   ```bash
   # Save current state
   python3 scripts/validate_additional_marks.py > before_import.log

   # Save performance baseline
   bash performance_test.sh > baseline_perf.log
   ```

---

### Phase 2: Import (15-30 minutes)

1. **Run data import**:
   ```bash
   cd frontend/backend
   python3 scripts/import_chipseq.py \
     --input ../../data/HepG2_H3K9me3.narrowPeak.gz \
     --mark-type H3K9me3 \
     --species human \
     --experiment-name "ENCODE_HepG2_H3K9me3" \
     --cell-type "HepG2" \
     --source "ENCODE" \
     --accession "ENCSR000..." \
     --format narrowPeak
   ```

2. **Monitor import progress**:
   - Watch console output for errors
   - Monitor database connection count
   - Check disk space usage

3. **Verify import completion**:
   ```bash
   # Check logs for success message
   # Expected: "Import completed: XXXXX peaks imported, X skipped"
   ```

---

### Phase 3: Post-Import Validation (1 hour)

1. **Run post-import validation**:
   ```bash
   python3 scripts/phase_3_1_post_import_validation.py
   ```
   **Expected**: All checks pass

2. **Run comprehensive validation**:
   ```bash
   python3 scripts/validate_additional_marks.py > after_import.log
   ```
   **Expected**: HepG2 shows 6/6 marks, valid_combinations = 24

3. **Backend API tests**:
   ```bash
   cd frontend/backend
   pytest tests/test_overlap_export.py -v
   pytest tests/test_chipseq_api.py -v
   ```
   **Expected**: All tests pass

4. **Manual API testing**:
   - Run all curl commands from Test Layer 3
   - Verify responses match expected format
   - Check for any error messages

---

### Phase 4: Frontend E2E Tests (1 hour)

1. **Run automated E2E tests**:
   ```bash
   cd frontend/web
   npm run test:e2e -- phase-3-1-validation.spec.ts
   ```
   **Expected**: 7/7 tests pass

2. **Manual UI testing**:
   - Follow manual testing checklist (Test Layer 4)
   - Capture screenshots at each step
   - Document any unexpected behavior

3. **Browser compatibility** (if time permits):
   - Test in Chrome
   - Test in Firefox
   - Test in Safari

---

### Phase 5: Performance & Regression (1 hour)

1. **Performance testing**:
   ```bash
   bash performance_test.sh > after_perf.log
   diff baseline_perf.log after_perf.log
   ```
   **Expected**: Performance degradation <50%

2. **Regression testing**:
   - Run existing E2E test suites
   - Test existing filter combinations
   - Verify existing exports work

3. **Database performance**:
   ```sql
   -- Run EXPLAIN ANALYZE queries from Test Layer 5
   ```

---

### Phase 6: Edge Cases & Cleanup (30 minutes)

1. **Test edge cases**:
   - Empty results
   - Invalid parameters
   - Special characters
   - Large result sets

2. **Documentation**:
   - Update CHANGELOG.md
   - Document any issues found
   - Create test report

3. **Cleanup**:
   - Remove test files
   - Archive logs
   - Commit test scripts

---

## Risk Mitigation

### What Could Go Wrong

**Risk 1: Data Quality Issues**

**Symptoms**:
- Peak count too low (<20K)
- Many peaks with invalid coordinates
- Signal values unrealistic

**Mitigation**:
- Pre-import validation script will catch most issues
- Have backup data source ready (alternative ENCODE accession)
- Manual inspection of first 100 peaks

**Rollback**:
```sql
-- Delete imported data
DELETE FROM chipseq_peaks WHERE experiment_id = XXX;
DELETE FROM chipseq_experiments WHERE experiment_id = XXX;
-- Restore from backup if needed
```

---

**Risk 2: liftOver Conversion Fails**

**Symptoms**:
- <90% of peaks map successfully
- Large coordinate shifts
- Peaks mapping to wrong chromosomes

**Mitigation**:
- Use high-quality chain files from UCSC
- Validate mapping quality before import
- Consider using hg19 data directly if available

**Rollback**:
- Use original hg19 data from ENCODE
- Skip liftOver step entirely

---

**Risk 3: Frontend Doesn't Auto-Update**

**Symptoms**:
- H3K9me3 not appearing in dropdown
- Filters don't work
- UI shows errors

**Root Cause Analysis**:
1. Check API response: Does `/marks/available` include H3K9me3?
2. Check browser console: Any JavaScript errors?
3. Check network tab: Are requests successful?
4. Check Redux state: Is mark data loaded correctly?

**Mitigation**:
- Frontend is designed to be data-driven
- Mark list comes from API, not hardcoded
- If issue found, likely a bug in existing code (not related to import)

**Workaround**:
- Restart frontend dev server
- Clear browser cache
- Check for stale build artifacts

---

**Risk 4: Performance Degradation**

**Symptoms**:
- Queries take >2x longer
- Database CPU usage high
- Frontend becomes slow

**Mitigation**:
- Monitor database query plans
- Ensure indexes are present
- Consider VACUUM ANALYZE after import

**Fixes**:
```sql
-- Rebuild indexes
REINDEX TABLE chipseq_peaks;

-- Update statistics
ANALYZE chipseq_peaks;
ANALYZE chipseq_experiments;

-- Vacuum if needed
VACUUM ANALYZE chipseq_peaks;
```

---

**Risk 5: Import Fails Midway**

**Symptoms**:
- Script exits with error
- Partial data in database
- Transaction not committed

**Mitigation**:
- Import script uses database transactions
- Automatic rollback on failure
- Safe to re-run import after fixing issue

**Recovery**:
1. Check error message in logs
2. Fix underlying issue (disk space, data format, etc.)
3. Re-run import script
4. Verify data integrity after successful import

---

## Rollback Procedures

### Immediate Rollback (if critical issues found)

**Scenario**: Import completed but data is corrupt/wrong

**Steps**:

```sql
-- 1. Identify experiment_id
SELECT experiment_id, experiment_name, created_at
FROM chipseq_experiments
WHERE cell_type = 'HepG2' AND mark_type_id = (
  SELECT mark_type_id FROM epigenetic_mark_types WHERE mark_name = 'H3K9me3'
)
ORDER BY created_at DESC
LIMIT 1;

-- 2. Delete peaks (cascade will handle related data)
DELETE FROM chipseq_peaks WHERE experiment_id = <experiment_id>;

-- 3. Deactivate experiment (don't delete, preserve history)
UPDATE chipseq_experiments
SET is_active = FALSE
WHERE experiment_id = <experiment_id>;

-- 4. Refresh materialized views
REFRESH MATERIALIZED VIEW mv_chipseq_mark_stats;
REFRESH MATERIALIZED VIEW mv_gene_mark_summary;

-- 5. Verify rollback
SELECT * FROM chipseq_experiments WHERE experiment_id = <experiment_id>;
-- Should show is_active = FALSE
```

**Verification**:
```bash
# Re-run validation to confirm data removed
python3 scripts/validate_additional_marks.py

# Expected: HepG2 shows 5/6 marks (H3K9me3 missing)
```

---

### Database Backup (before import)

**Recommended**: Take database backup before import

```bash
# Backup entire database
pg_dump -U amax -d lncrna_production > backup_before_phase_3_1.sql

# Or backup specific tables only (faster)
pg_dump -U amax -d lncrna_production \
  -t chipseq_experiments \
  -t chipseq_peaks \
  -t epigenetic_mark_types \
  > backup_chipseq_tables.sql

# Restore if needed
psql -U amax -d lncrna_production < backup_before_phase_3_1.sql
```

---

## Success Metrics

### Quantitative Metrics

1. **Data Import**:
   - ✅ Peak count: 40,000 - 80,000
   - ✅ Import success rate: 100%
   - ✅ Data validation: 0 critical errors

2. **API Performance**:
   - ✅ Query response time: <500ms (95th percentile)
   - ✅ API success rate: 100% (no 500 errors)
   - ✅ valid_combinations: 24 (increase from 23)

3. **Frontend Tests**:
   - ✅ E2E tests: 7/7 passed
   - ✅ Manual tests: 100% checklist completed
   - ✅ JavaScript errors: 0

4. **Performance**:
   - ✅ Performance degradation: <50% from baseline
   - ✅ Database query time: <100ms for simple queries
   - ✅ Frontend load time: <3 seconds

5. **Regression**:
   - ✅ Existing tests: 100% pass rate
   - ✅ Existing features: All working
   - ✅ No new bugs introduced

---

### Qualitative Metrics

1. **Zero Frontend Code Changes**:
   - ✅ No changes to React components
   - ✅ No changes to API client
   - ✅ No changes to routing
   - ✅ Frontend auto-adapts to new data

2. **Data Quality**:
   - ✅ Peak coordinates valid
   - ✅ Signal values reasonable
   - ✅ No duplicate peaks
   - ✅ Chromosome distribution normal

3. **User Experience**:
   - ✅ Filters work intuitively
   - ✅ Results display correctly
   - ✅ No error messages
   - ✅ UI remains responsive

---

## Test Report Template

```markdown
# Phase 3.1: HepG2 × H3K9me3 Import - Test Report

**Date**: YYYY-MM-DD
**Tester**: [Name]
**Environment**: Production / Staging

## Summary

- **Import Status**: ✅ Success / ❌ Failed
- **Peak Count**: [XX,XXX]
- **Tests Passed**: [X/Y]
- **Critical Issues**: [None / List]

## Test Results

### Layer 1: Data Import Validation
- Pre-import validation: ✅ Pass
- Post-import validation: ✅ Pass
- Peak count: [XX,XXX] (expected: 40K-80K)
- Data quality: ✅ No issues

### Layer 2: liftOver Quality
- N/A (used hg19 data directly)

### Layer 3: Backend API
- Marks list: ✅ H3K9me3 appears
- Query overlaps: ✅ Returns data
- Heatmap matrix: ✅ Shows 24/24 combinations
- Export: ✅ Works correctly

### Layer 4: Frontend UI
- E2E tests: ✅ 7/7 passed
- Manual tests: ✅ All items checked
- Screenshots: [Attached]

### Layer 5: Performance & Regression
- Performance: ✅ <50% degradation
- Regression: ✅ No issues found
- Database: ✅ Queries optimized

## Issues Found

### Critical (Blockers)
- None

### Major (Should Fix)
- None

### Minor (Nice to Have)
- [List any minor issues]

## Recommendations

1. [Any recommendations for future imports]
2. [Performance optimization suggestions]
3. [Documentation updates needed]

## Conclusion

✅ **APPROVED FOR PRODUCTION**

The import was successful, all tests passed, and the "zero frontend code changes" hypothesis is validated.

---

**Signed**: [Name]
**Date**: YYYY-MM-DD
```

---

## Appendix: Quick Reference

### Commands Cheat Sheet

```bash
# Pre-import validation
bash scripts/phase_3_1_pre_import_validation.sh <file>

# Import data
python3 scripts/import_chipseq.py --config config.json

# Post-import validation
python3 scripts/phase_3_1_post_import_validation.py

# Comprehensive validation
python3 scripts/validate_additional_marks.py

# Backend tests
pytest tests/test_overlap_export.py -v

# E2E tests
npm run test:e2e -- phase-3-1-validation.spec.ts

# Performance test
bash performance_test.sh

# Rollback
psql -U amax -d lncrna_production -c "DELETE FROM chipseq_peaks WHERE experiment_id = XXX"
```

---

### Expected Test Execution Time

| Phase | Activity | Time |
|-------|----------|------|
| 1 | Pre-import validation | 30 min |
| 2 | Data import | 15-30 min |
| 3 | Post-import validation | 1 hour |
| 4 | Frontend E2E tests | 1 hour |
| 5 | Performance & regression | 1 hour |
| 6 | Edge cases & cleanup | 30 min |
| **Total** | **Automated + Manual** | **4-6 hours** |

**Breakdown**:
- Automated: ~2 hours (running scripts + tests)
- Manual: ~2-4 hours (validation + documentation)

---

### Contact & Support

**Questions**: [Your contact info]
**Documentation**: `/docs/testing/`
**Issue Tracker**: [Link to issue tracker]

---

**Document Version**: 1.0
**Last Updated**: 2025-12-07
**Author**: Testing Team
