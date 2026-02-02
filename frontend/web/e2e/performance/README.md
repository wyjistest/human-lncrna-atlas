# Performance Test Execution Guide

## Quick Start

Run all performance tests:
```bash
cd /data/wenyujianData/human-lncrna-atlas-github/frontend/web
npm run test:performance
```

Compare latest run with baseline:
```bash
cd /data/wenyujianData/human-lncrna-atlas-github/frontend/web
npm run test:performance:compare
```

Run tests + compare (one command):
```bash
cd /data/wenyujianData/human-lncrna-atlas-github/frontend/web
npm run test:performance:check
```

Run specific performance test:
```bash
npx playwright test e2e/performance/disease-dropdown-performance.spec.ts
```

Run with HTML report:
```bash
npx playwright test e2e/performance --reporter=html
```

---

## Test Execution Commands

### 1. Local Development Testing

```bash
REPO_ROOT="$(git rev-parse --show-toplevel)"

# Start backend (Terminal 1)
cd "$REPO_ROOT/frontend/backend"
source venv/bin/activate
uvicorn main:app --reload --port 8000

# Start frontend (Terminal 2)
cd "$REPO_ROOT/frontend/web"
npm run dev

# Run performance tests (Terminal 3)
cd "$REPO_ROOT/frontend/web"
npx playwright test e2e/performance
```

### 2. Baseline Performance Capture (Before Optimization)

```bash
# Run tests (writes JSON report to test-results/performance-latest-metrics.json by default)
npm run test:performance

# If you want to persist the baseline, copy the latest report:
cp test-results/performance-latest-metrics.json performance-baseline-metrics.json
```

### 3. After Optimization Performance Verification

```bash
# Run tests again (updates test-results/performance-latest-metrics.json)
npm run test:performance

# Compare with baseline
npm run test:performance:compare

# Or run both in one command
npm run test:performance:check
```

---

## Expected Output

### Successful Test Run Example:

```
📊 Performance Metrics Report
======================================================================
  api_/api/v1/diseases                              :     234.00ms
  render_.ant-select-dropdown:visible               :     156.00ms
  scroll_fps                                        :      58.34
======================================================================

✅ Disease API Performance Test PASSED
✅ Dropdown Render Performance Test PASSED
✅ Scroll Performance Test PASSED
✅ E2E Disease Selection Performance Test PASSED
✅ Cache Performance Test COMPLETED
✅ No significant memory leak detected

6 passed (45.3s)
```

### Failed Test Example (Performance Regression):

```
❌ Disease API Performance Test FAILED

Error: expect(received).toBeLessThan(expected)

Expected: < 1000
Received: 1523

  at disease-dropdown-performance.spec.ts:58:23

Suggestion: API response time exceeded threshold (1523ms > 1000ms)
- Check backend cache layer
- Review database query performance
- Verify network conditions
```

---

## Troubleshooting

### Test Timeout

If tests timeout, increase the timeout in playwright.config.ts:

```typescript
timeout: 120000, // 2 minutes
```

### Memory Measurement Not Available

If memory metrics show 0, launch Chrome with memory info flag:

```typescript
launchOptions: {
  args: ['--enable-precise-memory-info']
}
```

### Cache Headers Not Present

If cache tests show "UNKNOWN" status, ensure backend returns `X-Cache-Status` header:

```python
# backend/app/main.py
@app.get("/api/v1/diseases")
async def get_diseases(response: Response):
    # ... cache logic ...
    response.headers["X-Cache-Status"] = "HIT" if from_cache else "MISS"
    return data
```

---

## Performance Baseline Targets

### Before Optimization (Baseline)

| Metric | Target | Acceptable Range |
|--------|--------|------------------|
| Disease API Response | < 1000ms | 800-1500ms |
| Dropdown Render | < 500ms | 400-800ms |
| Network API Response | < 5000ms | 3000-8000ms |
| Graph Render | < 3000ms | 2000-5000ms |
| Total User Experience | < 8000ms | 6000-12000ms |
| Memory Usage | < 200 MB | 150-250 MB |
| Scroll FPS | > 30 FPS | 25-45 FPS |

### After Optimization (Goals)

| Metric | Target | Success Criteria |
|--------|--------|------------------|
| Disease API Response | < 200ms | 80% reduction |
| Dropdown Render | < 200ms | 60% reduction |
| Network API Response | < 2000ms | 60% reduction |
| Graph Render | < 1500ms | 50% reduction |
| Total User Experience | < 3000ms | 63% reduction |
| Memory Usage | < 150 MB | 25% reduction |
| Scroll FPS | > 55 FPS | 80% improvement |
| Cache Hit Rate | > 80% | New metric |

---

## Next Steps

1. **Establish Baseline**: Run tests before any optimization
2. **Implement Optimizations**: Apply backend caching, frontend optimizations
3. **Verify Improvements**: Re-run tests and compare metrics
4. **Integrate CI/CD**: Add performance tests to GitHub Actions
5. **Set up Monitoring**: Track performance metrics over time

---

## Additional Resources

- [Playwright Performance Testing Guide](https://playwright.dev/docs/test-advanced)
- [Web Vitals Documentation](https://web.dev/vitals/)
- [Chrome DevTools Performance](https://developer.chrome.com/docs/devtools/performance/)
- Project Strategy: `/data/wenyujianData/human-lncrna-atlas-github/frontend/web/e2e/PERFORMANCE_TEST_STRATEGY.md`

---

**Generated**: 2025-12-10
**Status**: Ready for execution
