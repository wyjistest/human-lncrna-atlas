# Quick Fix Guide: Performance Test Configuration

> 更新（2026-01-24）：本文档为测试排障/快速修复指引快照；现状以 `docs/CURRENT_STATUS.md` 与仓库实际测试代码为准。

**Issue**: Tests monitoring wrong API endpoint
**Impact**: All tests fail even though optimizations are deployed
**Fix Time**: ~5 minutes

---

## What Went Wrong

The test file `e2e/performance/disease-dropdown-performance.spec.ts` is hardcoded to monitor the **old** endpoint `/api/v1/diseases`, but the optimized frontend code calls `/api/v1/diseases/options`.

**Result**: Tests measure the wrong API call and fail.

---

## Quick Fix Steps

### Step 1: Update Test Endpoint (Line 46)

**File**: `e2e/performance/disease-dropdown-performance.spec.ts`

```diff
- const { response, time: apiTime, data, headers } = await metrics.measureAPIResponse(
-   '/api/v1/diseases',
+   '/api/v1/diseases/options',
    async () => {
      await page.goto(`${BASE_URL}${PAGE_URL}`)
      await page.waitForLoadState('networkidle')
    }
  )
```

### Step 2: Update Data Extraction Logic (Lines 54-56)

```diff
  // Extract data metrics
- const totalItems = data.total || 0
- const returnedItems = data.items?.length || 0
+ const totalItems = data.traits?.length || 0
+ const returnedItems = data.traits?.length || 0
  const payloadSize = parseInt(headers['content-length'] || '0', 10)
```

### Step 3: Update Console Output (Lines 59-64)

```diff
  console.log(`\n📊 API Performance Metrics:`)
  console.log(`  - Response Time: ${apiTime}ms`)
- console.log(`  - Total Items: ${totalItems}`)
- console.log(`  - Returned Items: ${returnedItems}`)
+ console.log(`  - Total Diseases: ${totalItems}`)
+ console.log(`  - Deduplicated Count: ${returnedItems}`)
  console.log(`  - Payload Size: ${(payloadSize / 1024).toFixed(2)} KB`)
```

### Step 4: Clear Browser Cache

```bash
cd <repo-root>/frontend/web

# Option A: Hard refresh (recommended)
# Just run tests with --headed to visually verify
npx playwright test e2e/performance/disease-dropdown-performance.spec.ts --headed

# Option B: Rebuild frontend (if Option A doesn't work)
npm run build
# Then restart dev server
```

### Step 5: Re-run Tests

```bash
npx playwright test e2e/performance/disease-dropdown-performance.spec.ts \
  --reporter=html,json \
  --output=test-results/performance-optimized.json
```

---

## Expected Results After Fix

### Before Fix
- API Response Time: 3404ms (measuring old endpoint)
- Test Pass Rate: 1/6 (16.7%)
- Dropdown: Timeout errors

### After Fix
- API Response Time: 7-50ms (measuring new endpoint)
- Test Pass Rate: 6/6 (100%)
- Dropdown: Loads instantly
- **Performance Improvement: 99% faster (50-700x speedup)**

---

## Verification Checklist

After making changes, verify:

- [ ] Test file line 46 now monitors `/api/v1/diseases/options`
- [ ] Data extraction uses `data.traits?.length`
- [ ] Console output updated to match new structure
- [ ] Browser cache cleared (hard reload or rebuild)
- [ ] Tests pass with API response time < 100ms
- [ ] All 6 tests pass (dropdown, scroll, cache, E2E, memory)

---

## Troubleshooting

### Issue: Tests still fail after fix

**Symptom**: Still seeing 3404ms response time

**Solution**:
1. Verify frontend server is running from correct directory:
   ```bash
   lsof -i :5173 | grep LISTEN
   # Get PID, then:
   pwdx <PID>
   # Should show: <repo-root>/frontend/web
   ```

2. Force rebuild frontend:
   ```bash
   cd <repo-root>/frontend/web
   rm -rf dist node_modules/.vite
   npm run build
   npm run dev
   ```

3. Verify correct API is being called in browser:
   ```bash
   # Open http://localhost:5173/network
   # Open DevTools > Network tab
   # Filter: "diseases"
   # Should see: GET /api/v1/diseases/options (NOT /api/v1/diseases)
   ```

### Issue: Backend endpoint doesn't exist

**Symptom**: 404 error on `/api/v1/diseases/options`

**Solution**:
```bash
# Verify backend has the endpoint
curl http://localhost:8000/api/v1/diseases/options

# If 404, check backend code needs to be updated
# Backend router file: frontend/backend/app/routers/diseases.py
# Should have @router.get("/options") endpoint
```

---

## Complete Test Configuration File

For reference, here's what the corrected test file should look like:

```typescript
test('P0: Disease options API should load within performance budget', async ({ page }) => {
  const metrics = new PerformanceMetrics(page)
  await page.context().clearCookies()

  console.log('\n🚀 Starting Disease API Performance Test...')

  // ✅ CORRECT: Monitor new optimized endpoint
  const { response, time: apiTime, data, headers } = await metrics.measureAPIResponse(
    '/api/v1/diseases/options',  // ✅ NEW endpoint
    async () => {
      await page.goto(`${BASE_URL}${PAGE_URL}`)
      await page.waitForLoadState('networkidle')
    }
  )

  // ✅ CORRECT: Extract data from new response structure
  const totalItems = data.traits?.length || 0
  const returnedItems = data.traits?.length || 0
  const payloadSize = parseInt(headers['content-length'] || '0', 10)
  const cacheStatus = headers['x-cache-status'] || 'MISS'

  console.log(`\n📊 API Performance Metrics:`)
  console.log(`  - Response Time: ${apiTime}ms`)
  console.log(`  - Total Diseases: ${totalItems}`)
  console.log(`  - Deduplicated Count: ${returnedItems}`)
  console.log(`  - Payload Size: ${(payloadSize / 1024).toFixed(2)} KB`)
  console.log(`  - Cache Status: ${cacheStatus}`)

  // Performance assertions (these should pass with new endpoint)
  expect(apiTime).toBeLessThan(THRESHOLDS.API_RESPONSE_TIME)  // Should be 7-50ms
  expect(response.status()).toBe(200)
  expect(returnedItems).toBeGreaterThan(0)  // Should be 273 diseases
  expect(payloadSize).toBeLessThan(100 * 1024)  // Should be ~20KB
})
```

---

**Fix Created**: 2025-12-10
**Estimated Fix Time**: 5 minutes
**Confidence Level**: 🟢 HIGH - Simple configuration change
