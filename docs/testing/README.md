# Testing Documentation

This directory contains testing strategies, scripts, and checklists for the Human lncRNA Atlas project.

> 更新（2026-01-25）：本目录包含测试策略/手工 checklist/历史测试报告；文中 `[ ]` 代表“验证步骤”，不代表开发待办；现状以 `docs/CURRENT_STATUS.md` 与 `scripts/run-tests.sh` 为准。
> 部分常用清单已迁移为可追踪的 GitHub Issues（用于实际勾选与记录结果）：https://github.com/wyjistest/human-lncrna-atlas/issues/71

## Phase 3.1: HepG2 × H3K9me3 Import Testing

### Quick Links

| Document | Purpose | Target Audience |
|----------|---------|-----------------|
| **[Testing Summary](phase-3-1-testing-summary.md)** | Quick overview & commands | Everyone |
| **[Testing Strategy](phase-3-1-testing-strategy.md)** | Comprehensive test plan | Developers, QA Lead |
| **[Manual Checklist](phase-3-1-manual-checklist.md)** | Step-by-step UI testing | QA Testers |

### Test Scripts

| Script | Location | Purpose |
|--------|----------|---------|
| Pre-import validation | `/scripts/phase_3_1_pre_import_validation.sh` | Validate data files before import |
| Post-import validation | `/scripts/phase_3_1_post_import_validation.py` | Validate database after import |
| Backend regression tests | `/frontend/backend/tests/test_phase_3_1_regression.py` | Ensure no API breakage |
| E2E validation tests | `/frontend/web/e2e/phase-3-1-validation.spec.ts` | Validate frontend integration |

---

## Quick Start

### For Developers

```bash
# 1. Pre-import validation
bash scripts/phase_3_1_pre_import_validation.sh data/HepG2_H3K9me3.narrowPeak.gz

# 2. Import data (using existing script)
python3 frontend/backend/scripts/import_chipseq.py \
  --input data/HepG2_H3K9me3.narrowPeak.gz \
  --mark-type H3K9me3 \
  --species human \
  --experiment-name "ENCODE_HepG2_H3K9me3" \
  --cell-type "HepG2"

# 3. Post-import validation
python3 scripts/phase_3_1_post_import_validation.py

# 4. Run automated tests
cd frontend/backend && pytest tests/test_phase_3_1_regression.py -v
cd frontend/web && npm run test:e2e -- phase-3-1-validation.spec.ts
```

### For QA Testers

1. Open `phase-3-1-manual-checklist.md`
2. Follow the step-by-step checklist (30-45 minutes)
3. Capture screenshots for each section
4. Document any issues found
5. Complete test report

---

## API Snapshot Baseline (Optional)

This repo includes a small, commit-friendly API snapshot baseline at `docs/baselines/api-snapshot.sample.json`.

Regenerate it (recommended):

```bash
# Local PostgreSQL + local backend venv (creates a temp DB, loads schema/v2.3 sample data, runs snapshot)
bash scripts/baselines/generate_api_snapshot_baseline_local.sh

# Or Docker Compose (if you have docker + docker compose available)
bash scripts/baselines/generate_api_snapshot_baseline.sh
```

Verify it (recommended):

```bash
# One command (local Postgres + local backend venv)
python3 scripts/verify_baselines.py --mode local
```

If the backend is already running (ideally on a fixed dataset), generate a stable snapshot manually:

```bash
python3 scripts/api_snapshot.py \
  --base-url http://localhost:8000 \
  --deterministic \
  --no-json \
  --pretty \
  --output /tmp/api-snapshot.json
```

---

## Test Coverage

```
Phase 3.1 Testing Strategy
│
├── Layer 1: Data Import Validation
│   ├── Pre-import checks (8 validations)
│   │   ✓ File exists & size reasonable
│   │   ✓ Peak format valid (narrowPeak)
│   │   ✓ Peak count in range (40K-80K)
│   │   ✓ Chromosome names correct
│   │   ✓ Coordinates valid
│   │   ✓ Signal values reasonable
│   │   ✓ No duplicates
│   │
│   └── Post-import checks (8 validations)
│       ✓ Experiment exists
│       ✓ Peak count matches
│       ✓ No duplicates in DB
│       ✓ Coordinates valid
│       ✓ Signal values reasonable
│       ✓ Chromosome distribution
│       ✓ Metadata complete
│       ✓ Coverage matrix updated
│
├── Layer 2: liftOver Quality (if applicable)
│   ✓ Mapping success rate >95%
│   ✓ Coordinate validity
│   ✓ No chromosome mismatches
│
├── Layer 3: Backend API Integration
│   ├── Automated Tests (25 tests)
│   │   ✓ Marks list includes H3K9me3
│   │   ✓ Query overlaps works
│   │   ✓ Heatmap matrix updated (24/24)
│   │   ✓ Export BED/CSV works
│   │   ✓ All existing marks still work
│   │   ✓ All existing cell types still work
│   │   ✓ Performance regression check
│   │
│   └── Manual API Tests (5 tests)
│       ✓ Marks available endpoint
│       ✓ Overlap query endpoint
│       ✓ Heatmap endpoint
│       ✓ Export BED endpoint
│       ✓ Export CSV endpoint
│
├── Layer 4: Frontend UI Verification
│   ├── E2E Tests (7 tests)
│   │   ✓ Mark filter includes H3K9me3
│   │   ✓ HepG2 × H3K9me3 combination works
│   │   ✓ Results table loads data
│   │   ✓ Heatmap shows complete matrix
│   │   ✓ Export includes new mark
│   │   ✓ No JavaScript errors
│   │   ✓ API endpoint returns data
│   │
│   └── Manual Tests (40+ checks)
│       ✓ Filter panel (10 checks)
│       ✓ Results table (10 checks)
│       ✓ Statistics & visualization (8 checks)
│       ✓ Export functionality (6 checks)
│       ✓ Edge cases (3 checks)
│       ✓ Performance (3 checks)
│       ✓ Console errors (2 checks)
│       ✓ Internationalization (2 checks)
│
└── Layer 5: Performance & Regression
    ✓ Query performance (<500ms)
    ✓ Existing features work
    ✓ Database queries optimized
    ✓ No memory leaks
    ✓ Edge cases handled
```

---

## Test Execution Time

| Phase | Activity | Time |
|-------|----------|------|
| Setup | Prepare environment | 10 min |
| Pre-import | Validate data file | 5 min |
| Import | Run import script | 15-30 min |
| Post-import | Validate database | 10 min |
| Backend tests | Automated tests | 10 min |
| E2E tests | Automated UI tests | 10 min |
| Manual tests | UI validation | 30-45 min |
| Performance | Regression checks | 15 min |
| Documentation | Write report | 15 min |
| **Total** | **End-to-end** | **2-3 hours** |

---

## Success Metrics

### Must Pass (Critical)

- ✅ Pre-import validation: 0 critical errors
- ✅ Post-import validation: 8/8 checks pass
- ✅ Backend regression tests: 25/25 pass
- ✅ E2E tests: 7/7 pass
- ✅ Manual checklist: 100% complete
- ✅ No JavaScript errors in console

### Should Pass (Important)

- ⚠️ Performance: Query time <500ms
- ⚠️ Heatmap: Shows 24/24 combinations
- ⚠️ Export: Files download correctly
- ⚠️ All browsers: Chrome, Firefox, Safari

---

## Key Hypothesis

**Zero Frontend Code Changes**: The frontend should automatically display new ChIP-seq data without any code modifications.

**Validation Points**:
1. Mark filter dropdown automatically includes H3K9me3
2. HepG2 × H3K9me3 combination works without errors
3. Results table displays data correctly
4. Export functionality works without changes
5. No JavaScript errors occur

**Expected Result**: ALL validation points pass WITHOUT modifying frontend code.

---

## Common Issues & Solutions

### H3K9me3 Not in Dropdown

**Check**:
```bash
curl "http://localhost:8000/api/v1/features/chipseq/marks/available?species=1" | jq '.marks[] | select(.mark_name=="H3K9me3")'
```

**Solutions**:
1. Database import incomplete → Re-run import
2. Materialized views stale → Refresh views
3. Frontend cache → Clear cache, reload

---

### No Data for HepG2 × H3K9me3

**Check**:
```bash
curl "http://localhost:8000/api/v1/lncrna-chipseq-overlap?mark_type=H3K9me3&cell_type=HepG2&chromosome=chr22" | jq '.total'
```

**Solutions**:
1. Try different chromosome (overlaps may not exist on chr22)
2. Check peak count in database
3. Verify overlaps calculated

---

### Performance Degradation

**Check**:
```sql
EXPLAIN ANALYZE SELECT * FROM chipseq_peaks WHERE experiment_id = XXX LIMIT 100;
```

**Solutions**:
```sql
ANALYZE chipseq_peaks;
REINDEX TABLE chipseq_peaks;
VACUUM ANALYZE chipseq_peaks;
```

---

## Rollback Procedure

If critical issues are found:

```sql
-- 1. Identify experiment_id
SELECT experiment_id FROM chipseq_experiments
WHERE cell_type = 'HepG2' AND mark_type_id = (
  SELECT mark_type_id FROM epigenetic_mark_types WHERE mark_name = 'H3K9me3'
)
ORDER BY created_at DESC LIMIT 1;

-- 2. Delete peaks
DELETE FROM chipseq_peaks WHERE experiment_id = XXX;

-- 3. Deactivate experiment
UPDATE chipseq_experiments SET is_active = FALSE WHERE experiment_id = XXX;

-- 4. Refresh views
REFRESH MATERIALIZED VIEW mv_chipseq_mark_stats;
REFRESH MATERIALIZED VIEW mv_gene_mark_summary;
```

---

## File Structure

```
human-lncrna-atlas-github/
│
├── docs/testing/                              ← Testing documentation
│   ├── README.md                              ← This file
│   ├── phase-3-1-testing-summary.md          ← Quick reference
│   ├── phase-3-1-testing-strategy.md         ← Comprehensive plan
│   └── phase-3-1-manual-checklist.md         ← Manual testing guide
│
├── scripts/                                   ← Validation scripts
│   ├── phase_3_1_pre_import_validation.sh    ← Pre-import checks
│   ├── phase_3_1_post_import_validation.py   ← Post-import checks
│   └── validate_additional_marks.py          ← Coverage matrix validation
│
├── frontend/backend/tests/                    ← Backend tests
│   ├── test_phase_3_1_regression.py          ← Regression test suite
│   ├── test_overlap_export.py                ← Export tests (existing)
│   └── test_chipseq_api.py                   ← ChIP-seq API tests
│
└── frontend/web/e2e/                          ← E2E tests
    ├── phase-3-1-validation.spec.ts          ← Phase 3.1 E2E tests
    └── lncrna-chipseq-overlap-export.spec.ts ← Export E2E (existing)
```

---

## Additional Resources

### Import Scripts (Existing)

- **Single import**: `frontend/backend/scripts/import_chipseq.py`
- **Batch import**: `frontend/backend/scripts/batch_import_chipseq.py`
- **Download script**: `frontend/backend/scripts/download_encode_chipseq.py`

### Validation Scripts (Existing)

- **Coverage validation**: `scripts/validate_additional_marks.py`
- **Test data generation**: `frontend/backend/scripts/generate_test_chipseq.py`

### Backend Tests (Existing)

- **API contracts**: `frontend/backend/tests/test_api_contracts.py`
- **Performance**: `frontend/backend/tests/test_performance.py`
- **Smoke tests**: `frontend/backend/tests/test_api_smoke.py`

### E2E Tests (Existing)

- **ChIP-seq flow**: `frontend/web/e2e/chipseq-flow.spec.ts`
- **Overlap page**: `frontend/web/e2e/lncrna-chipseq-overlap.spec.ts`
- **Export**: `frontend/web/e2e/lncrna-chipseq-overlap-export.spec.ts`

---

## Contact & Support

**Questions**: Testing Team
**Documentation**: `/docs/testing/`
**Issue Tracker**: [Link to issue tracker]

---

**Last Updated**: 2025-12-07
**Maintained by**: Testing Team
