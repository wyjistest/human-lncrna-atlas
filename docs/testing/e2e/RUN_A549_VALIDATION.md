# A549 Validation Test Suite - Execution Guide

## Overview

This document describes how to run validation tests for A549 cell line integration.

**Status**: WAITING FOR BACKEND IMPORT TO COMPLETE

## Prerequisites Check

Before running tests, verify backend import is complete:

```bash
# Check if A549 data exists in database
psql -U amax -d lncrna_production -c "
SELECT cell_type, mark_name, COUNT(*) as peaks
FROM chipseq_experiments e
JOIN chipseq_peaks p ON e.experiment_id = p.experiment_id
JOIN epigenetic_mark_types m ON e.mark_type_id = m.mark_type_id
WHERE cell_type = 'A549'
GROUP BY cell_type, mark_name
ORDER BY mark_name;
"
```

**Expected Output**: 6 rows showing A549 experiments for 6 marks (H3K27ac, H3K27me3, H3K36me3, H3K4me1, H3K4me3, H3K9me3)

**Current Status**: 0 rows (import not started)

## Services Required

Ensure the following services are running:

1. **Backend API** (port 8000)
   ```bash
   REPO_ROOT="$(git rev-parse --show-toplevel)"
   cd "$REPO_ROOT/frontend/backend"
   source venv/bin/activate
   uvicorn main:app --host 0.0.0.0 --port 8000 --reload
   ```

2. **Frontend Dev Server** (port 5173)
   ```bash
   REPO_ROOT="$(git rev-parse --show-toplevel)"
   cd "$REPO_ROOT/frontend/web"
   npm run dev
   ```

3. **PostgreSQL Database** (port 5432)
   - Database: `lncrna_production`
   - User: `amax`

## Running Tests

### Full Test Suite

```bash
REPO_ROOT="$(git rev-parse --show-toplevel)"
cd "$REPO_ROOT/frontend/web"
npx playwright test e2e/a549-validation.spec.ts --reporter=list
```

### Run with UI (Debug Mode)

```bash
npx playwright test e2e/a549-validation.spec.ts --ui
```

### Run Specific Test

```bash
# Test 1: Filter dropdown
npx playwright test e2e/a549-validation.spec.ts -g "A549 should appear in cell type filter"

# Test 2: Data loading
npx playwright test e2e/a549-validation.spec.ts -g "A549 data loads when selected"

# Test 3: Heatmap
npx playwright test e2e/a549-validation.spec.ts -g "A549 appears in heatmap"

# Test 4: Export
npx playwright test e2e/a549-validation.spec.ts -g "A549 data exports correctly"

# Test 5: Statistics
npx playwright test e2e/a549-validation.spec.ts -g "A549 statistics are displayed"

# Test 6: No errors
npx playwright test e2e/a549-validation.spec.ts -g "No JavaScript errors"

# API Test 1: API returns data
npx playwright test e2e/a549-validation.spec.ts -g "API returns A549 experiments"

# API Test 2: Export endpoint
npx playwright test e2e/a549-validation.spec.ts -g "API export includes A549 data"
```

### Generate HTML Report

```bash
npx playwright test e2e/a549-validation.spec.ts --reporter=html
npx playwright show-report
```

## Test Coverage

### UI Tests (6 tests)

1. **Cell Type Filter** - Verifies A549 appears in dropdown
2. **Data Loading** - Verifies A549 × H3K27me3 returns results
3. **Heatmap Visualization** - Verifies A549 appears in heatmap
4. **Data Export** - Verifies A549 data can be exported
5. **Statistics Display** - Verifies A549 statistics are shown
6. **Error Detection** - Verifies no JavaScript errors occur

### API Tests (2 tests)

1. **API Endpoint** - Verifies API returns A549 data
2. **Export Endpoint** - Verifies export includes A549 data

## Expected Results

All 8 tests should pass:

```
✓ A549 Cell Line Integration
  ✓ A549 should appear in cell type filter
  ✓ A549 data loads when selected (with H3K27me3)
  ✓ A549 appears in heatmap visualization
  ✓ A549 data exports correctly
  ✓ A549 statistics are displayed correctly
  ✓ No JavaScript errors when using A549

✓ A549 API Integration
  ✓ API returns A549 experiments
  ✓ API export includes A549 data

8 passed (Xm Xs)
```

## Screenshots Generated

Tests will generate screenshots in `/tmp/` for debugging:

- `a549_test_1_initial.png` - Initial page load
- `a549_test_1_dropdown.png` - Cell type dropdown with A549
- `a549_test_2_filtered.png` - Data table after filtering by A549
- `a549_test_3_heatmap.png` - Heatmap visualization
- `a549_test_4_export.png` - Export functionality
- `a549_test_5_statistics.png` - Statistics display

## Validation Checklist

After tests pass, manually verify:

- [ ] A549 appears in cell type dropdown (alongside existing 5 cell types)
- [ ] Selecting A549 + any mark loads data
- [ ] Data table displays A549 peaks with correct columns
- [ ] Statistics cards show non-zero counts for A549
- [ ] Heatmap shows 5×6 matrix (5 cell lines × 6 marks)
- [ ] Export includes A549 data in CSV/Excel format
- [ ] No JavaScript console errors
- [ ] Page performance is comparable to before (~5-10s load time)

## Troubleshooting

### Tests Fail: "A549 not found in dropdown"

**Cause**: Backend import not complete OR frontend cache not cleared

**Solution**:
1. Verify backend import status (see Prerequisites Check)
2. Clear browser cache: Ctrl+F5
3. Wait 1 hour for React Query cache to expire
4. Restart frontend dev server

### Tests Fail: "API returns 0 results"

**Cause**: Database does not contain A549 data

**Solution**:
1. Check database: `SELECT COUNT(*) FROM chipseq_experiments WHERE cell_type='A549'`
2. If 0, wait for backend agent to complete import
3. Verify import script completed successfully

### Tests Fail: "Network request failed"

**Cause**: Backend API not running

**Solution**:
```bash
cd /data/wenyujianData/humanLncAtlas/backend
poetry run uvicorn app.main:app --host 0.0.0.0 --port 8000
```

### Tests Fail: "Page not found (404)"

**Cause**: Frontend dev server not running

**Solution**:
```bash
cd /data/wenyujianData/humanLncAtlas/frontend/web
npm run dev
```

## Performance Benchmarks

Compare performance before/after A549 integration:

```bash
# Test chr22 query performance
time curl -s "http://localhost:8000/api/v1/lncrna-chipseq-overlap?chromosome=chr22&page_size=100" > /dev/null

# Expected: ~5-10 seconds (similar to before)
```

## Next Steps After Passing

Once all tests pass:

1. Document A549 statistics (total experiments, total peaks, coverage %)
2. Take final screenshots for documentation
3. Create summary report for project team
4. Mark A549 integration as validated
5. Plan next cell line integration (if any)

## Contact

If tests fail unexpectedly, review:
- Backend logs: Check FastAPI console output
- Frontend logs: Check browser console (F12)
- Database logs: Check PostgreSQL logs
- Network logs: Check browser Network tab (F12)
