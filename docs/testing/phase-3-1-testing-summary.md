# Phase 3.1: HepG2 × H3K9me3 Import - Testing Summary

## Overview

This document provides a quick reference for all testing resources for Phase 3.1: HepG2 × H3K9me3 data import.

**Goal**: Validate that adding new ChIP-seq data requires ZERO frontend code changes.

---

## Testing Resources

### 1. Automated Scripts

| Script | Purpose | Time | Command |
|--------|---------|------|---------|
| Pre-import validation | Validate data file quality | 2 min | `bash scripts/phase_3_1_pre_import_validation.sh <file>` |
| Post-import validation | Validate database integrity | 5 min | `python3 scripts/phase_3_1_post_import_validation.py` |
| Backend unit tests | Regression testing | 5 min | `pytest tests/test_phase_3_1_regression.py -v` |
| E2E tests | Frontend integration | 10 min | `npm run test:e2e -- phase-3-1-validation.spec.ts` |

### 2. Manual Testing

| Document | Purpose | Time |
|----------|---------|------|
| `phase-3-1-manual-checklist.md` | Step-by-step UI validation | 30-45 min |
| `phase-3-1-testing-strategy.md` | Comprehensive test plan | Reference |

### 3. Test Coverage

```
Test Layers:
├── Layer 1: Data Import Validation ✓
│   ├── Pre-import checks (8 validations)
│   └── Post-import checks (8 validations)
│
├── Layer 2: liftOver Quality ✓ (if applicable)
│   ├── Mapping success rate
│   └── Coordinate validity
│
├── Layer 3: Backend API Integration ✓
│   ├── Marks list API
│   ├── Query overlaps API
│   ├── Heatmap matrix API
│   └── Export API (BED/CSV)
│
├── Layer 4: Frontend UI Verification ✓
│   ├── Automated E2E tests (7 tests)
│   └── Manual UI testing (40+ checks)
│
└── Layer 5: Performance & Regression ✓
    ├── Query performance
    ├── Existing features
    └── Edge cases
```

---

## Quick Start Guide

### For Developers

**Run all automated tests**:

```bash
# 1. Pre-import validation
bash scripts/phase_3_1_pre_import_validation.sh data/HepG2_H3K9me3.narrowPeak.gz

# 2. Post-import validation
python3 scripts/phase_3_1_post_import_validation.py

# 3. Backend tests
cd frontend/backend
pytest tests/test_phase_3_1_regression.py -v

# 4. E2E tests
cd frontend/web
npm run test:e2e -- phase-3-1-validation.spec.ts
```

**Expected**: All tests pass (0 failures)

---

### For QA Testers

1. **Read**: `phase-3-1-manual-checklist.md`
2. **Open**: Browser + DevTools
3. **Navigate**: `http://localhost:5175/lncrna-chipseq-overlap`
4. **Follow**: Checklist (30-45 minutes)
5. **Capture**: Screenshots for each section
6. **Document**: Any issues found

---

## Success Criteria

### Must Pass (Blockers)

- ✅ Pre-import validation: 0 critical errors
- ✅ Post-import validation: All 8 checks pass
- ✅ Backend API: H3K9me3 appears in marks list
- ✅ Frontend UI: H3K9me3 appears in dropdown
- ✅ E2E tests: 7/7 pass
- ✅ No JavaScript errors in console
- ✅ Export works (BED/CSV)

### Should Pass (Warnings acceptable)

- ⚠️ Performance: Query time <500ms (may be slower on first run)
- ⚠️ Heatmap: Shows 24/24 combinations (if heatmap implemented)
- ⚠️ All browsers: Chrome/Firefox/Safari (Chrome minimum)

---

## Test Results Template

```markdown
# Phase 3.1: Test Results

**Date**: 2025-12-XX
**Tester**: [Name]
**Duration**: X hours

## Automated Tests

| Test Suite | Status | Pass/Total | Notes |
|------------|--------|------------|-------|
| Pre-import validation | ✅ PASS | 8/8 | Peak count: 65,432 |
| Post-import validation | ✅ PASS | 8/8 | HepG2: 6/6 marks |
| Backend regression | ✅ PASS | 25/25 | All existing APIs work |
| E2E tests | ✅ PASS | 7/7 | No JS errors |

## Manual Tests

| Section | Status | Notes |
|---------|--------|-------|
| Filter panel | ✅ PASS | H3K9me3 visible |
| Results table | ✅ PASS | Data displays correctly |
| Export | ✅ PASS | BED & CSV work |
| Performance | ✅ PASS | Page loads <3s |

## Issues Found

**Critical**: None
**Major**: None
**Minor**: [List any]

## Recommendation

✅ APPROVED FOR PRODUCTION

**Signature**: _______________
**Date**: _______________
```

---

## Key Validation Points

### Pre-Import

```bash
# Expected validations
✓ File size: 5-50 MB
✓ Peak count: 40K-80K
✓ Format: narrowPeak (10 columns)
✓ Chromosomes: chr1-22, chrX, chrY
✓ Coordinates: start < end, non-negative
✓ Signal values: FE 2-50 (average)
✓ No duplicates
```

### Post-Import

```bash
# Expected database state
✓ Experiment exists: HepG2_H3K9me3_ENCSR...
✓ Peak count matches file (±1%)
✓ No duplicate peaks
✓ All coordinates valid
✓ Signal values reasonable
✓ Coverage matrix: HepG2 6/6 marks
✓ Valid combinations: 24 (was 23)
```

### Frontend UI

```bash
# Expected UI state
✓ Mark filter includes "H3K9me3"
✓ HepG2 + H3K9me3 combination works
✓ Results table displays data
✓ Export downloads files
✓ No console errors
✓ Performance acceptable
```

---

## Common Issues & Solutions

### Issue: H3K9me3 Not Appearing in Dropdown

**Diagnosis**:
```bash
# Check API
curl "http://localhost:8000/api/v1/features/chipseq/marks/available?species=1" | jq '.marks[] | select(.mark_name=="H3K9me3")'

# Should return H3K9me3 data
```

**Solution**:
- If API returns nothing: Database import failed or materialized views not refreshed
- If API returns data: Frontend cache issue, clear cache and reload
- If still broken: Check browser console for errors

---

### Issue: No Data for HepG2 × H3K9me3

**Diagnosis**:
```bash
# Check overlaps
curl "http://localhost:8000/api/v1/lncrna-chipseq-overlap?mark_type=H3K9me3&cell_type=HepG2&chromosome=chr22" | jq '.total'

# Should return > 0
```

**Solution**:
- If 0: Overlaps may not exist on chr22, try removing chromosome filter
- If still 0: Peak data imported but no overlaps calculated
- Run: `python3 scripts/calculate_overlaps.py` (if such script exists)

---

### Issue: Performance Degradation

**Diagnosis**:
```sql
-- Check query plans
EXPLAIN ANALYZE SELECT * FROM chipseq_peaks WHERE experiment_id = XXX LIMIT 100;

-- Should use Index Scan, not Seq Scan
```

**Solution**:
```sql
-- Refresh statistics
ANALYZE chipseq_peaks;
ANALYZE chipseq_experiments;

-- Rebuild indexes if needed
REINDEX TABLE chipseq_peaks;
```

---

## File Locations

```
human-lncrna-atlas-github/
├── scripts/
│   ├── phase_3_1_pre_import_validation.sh      ← Pre-import checks
│   ├── phase_3_1_post_import_validation.py     ← Post-import checks
│   └── validate_additional_marks.py            ← Comprehensive validation
│
├── frontend/backend/tests/
│   ├── test_phase_3_1_regression.py            ← Backend regression tests
│   └── test_overlap_export.py                  ← Existing export tests (22 tests)
│
├── frontend/web/e2e/
│   ├── phase-3-1-validation.spec.ts            ← E2E tests (7 tests)
│   └── lncrna-chipseq-overlap-export.spec.ts   ← Existing export E2E
│
└── docs/testing/
    ├── phase-3-1-testing-strategy.md           ← Comprehensive test plan
    ├── phase-3-1-manual-checklist.md           ← Manual testing checklist
    └── phase-3-1-testing-summary.md            ← This document
```

---

## Commands Cheat Sheet

### Import

```bash
# Import data
python3 scripts/import_chipseq.py \
  --input data/HepG2_H3K9me3.narrowPeak.gz \
  --mark-type H3K9me3 \
  --species human \
  --experiment-name "ENCODE_HepG2_H3K9me3" \
  --cell-type "HepG2"
```

### Validation

```bash
# Pre-import
bash scripts/phase_3_1_pre_import_validation.sh <file>

# Post-import
python3 scripts/phase_3_1_post_import_validation.py

# Comprehensive
python3 scripts/validate_additional_marks.py
```

### API Testing

```bash
# Check marks
curl "http://localhost:8000/api/v1/features/chipseq/marks/available?species=1" | jq

# Query overlaps
curl "http://localhost:8000/api/v1/lncrna-chipseq-overlap?mark_type=H3K9me3&cell_type=HepG2" | jq

# Export BED
curl "http://localhost:8000/api/v1/lncrna-chipseq-overlap/export?format=bed&mark_type=H3K9me3&cell_type=HepG2&chromosome=chr22" -o test.bed

# Export CSV
curl "http://localhost:8000/api/v1/lncrna-chipseq-overlap/export?format=csv&mark_type=H3K9me3&cell_type=HepG2&chromosome=chr22" -o test.csv
```

### Backend Tests

```bash
cd frontend/backend

# Run regression tests
pytest tests/test_phase_3_1_regression.py -v

# Run all overlap tests
pytest tests/test_overlap_export.py -v

# Run with coverage
pytest tests/ --cov=app --cov-report=html
```

### E2E Tests

```bash
cd frontend/web

# Run Phase 3.1 tests only
npm run test:e2e -- phase-3-1-validation.spec.ts

# Run all overlap tests
npm run test:e2e -- lncrna-chipseq-overlap

# Run with UI (debug mode)
npm run test:e2e -- --ui
```

---

## Estimated Time Breakdown

| Activity | Time |
|----------|------|
| Pre-import validation | 5 min |
| Data import | 15-30 min |
| Post-import validation | 10 min |
| Backend automated tests | 10 min |
| E2E automated tests | 10 min |
| Manual UI testing | 30-45 min |
| Performance testing | 15 min |
| Documentation | 15 min |
| **Total** | **2-3 hours** |

**Note**: Time estimates assume:
- Test environment is ready
- Data files are prepared
- No issues found during testing
- Experienced tester

---

## Acceptance Criteria

### Data Import

- [x] Data file passes pre-import validation
- [x] Import completes successfully (no errors)
- [x] Post-import validation: 8/8 checks pass
- [x] Peak count: 40K-80K
- [x] No duplicate peaks
- [x] Coordinates valid

### Backend API

- [x] `/marks/available` includes H3K9me3
- [x] Query API returns data for H3K9me3
- [x] HepG2 × H3K9me3 combination works
- [x] Heatmap shows 24 valid combinations
- [x] Export BED/CSV works
- [x] All regression tests pass

### Frontend UI

- [x] Mark filter dropdown includes H3K9me3
- [x] Can select HepG2 + H3K9me3
- [x] Results table displays data
- [x] Export button works
- [x] No JavaScript errors
- [x] All E2E tests pass
- [x] Manual checklist 100% complete

### Performance

- [x] Page load time <3s
- [x] Query response time <500ms
- [x] No performance degradation >50%
- [x] Database queries use indexes

---

## Contact

**Questions**: [Your Team/Email]
**Documentation**: `/docs/testing/`
**Issue Tracker**: [Link]

---

**Document Version**: 1.0
**Last Updated**: 2025-12-07
**Maintainer**: Testing Team
