# lncRNA-ChIP-seq Overlap E2E Tests

## Overview

Comprehensive end-to-end tests for the lncRNA-ChIP-seq Overlap Analysis page using Playwright.

> 更新（2026-01-25）：本文档为早期 E2E 套件说明快照；请以 `docs/testing/README.md`（测试入口）与 `docs/CURRENT_STATUS.md`（当前进度）为准。

## Test Coverage

### P0 Tests (Must Pass)

#### 1. Routing and Page Access
- ✅ Page loads successfully via URL
- ✅ Correct page title displayed
- ✅ Breadcrumb navigation rendered
- ✅ Accessible from navigation menu

#### 2. Component Rendering
- ✅ Main component container renders
- ✅ Filter panel displays
- ✅ Mark type filter available
- ✅ Data table displays (or loading/empty state)
- ✅ Table columns render correctly

#### 3. Internationalization
- ✅ Language switching supported
- ✅ Chinese content displays
- ✅ English content displays

### P1 Tests (Enabled - Mocked Overlap API)

These tests validate the filter + table interaction wiring by intercepting
`GET /api/v1/lncrna-chipseq-overlap` and returning deterministic data. This keeps
the suite stable and independent of backend/DB datasets while still exercising
real UI interactions and query parameter composition.

#### 4. Filter Functionality
- ✅ Filter by mark type (H3K27me3, H3K4me3, etc.)
- ✅ Filter by cell type (K562, GM12878, ...)
- ✅ Filter by chromosome (chr1-chr22, chrX, chrY)
- ✅ Reset filters

#### 5. Table Interactions
- ✅ Pagination through results
- ✅ Sort by overlap length
- ✅ Sort by binding affinity
- ✅ Change page size

### Additional Test Suites

#### Performance Tests
- ✅ Page load time under 8 seconds (default budget)
- ✅ Initial render under 6 seconds (default budget)

#### Performance Budgets (Configurable)

Performance assertions are environment-dependent (dev server, CPU, cache). You can override budgets via env vars:

| Env var | Default | Meaning |
|--------|---------|---------|
| `BASE_URL` | `http://localhost:5173` | Frontend base URL |
| `E2E_OVERLAP_PAGE_LOAD_BUDGET_MS` | `8000` | SPA shell load budget (ms) |
| `E2E_OVERLAP_INITIAL_RENDER_BUDGET_MS` | `6000` | First meaningful content render budget (ms) |

Example:

```bash
E2E_OVERLAP_INITIAL_RENDER_BUDGET_MS=12000 npm run test:e2e -- e2e/lncrna-chipseq-overlap.spec.ts -g "initial render"
```

#### Error Handling
- ✅ API error gracefully handled
- ✅ Empty results displayed correctly
- ✅ Network timeout handled

#### API Integration
- ✅ Correct API calls on page load
- ✅ Correct query parameters

#### Accessibility
- ✅ Accessible table structure
- ✅ Keyboard navigation supported
- ✅ Focus management

#### Deep Links
- ✅ URL parameters for filters
- ✅ Filters preserved in URL

#### Mobile Responsiveness
- ✅ Responsive on mobile viewport
- ✅ Accessible navigation on mobile

## Prerequisites

### 1. Install Dependencies

```bash
# 在仓库任意子目录都可运行
REPO_ROOT="$(git rev-parse --show-toplevel)"
cd "$REPO_ROOT/frontend/web"
npm ci
```

### 2. Install Playwright Browsers

```bash
npx playwright install chromium
```

### 3. Start Frontend Development Server

```bash
REPO_ROOT="$(git rev-parse --show-toplevel)"
cd "$REPO_ROOT/frontend/web"
npm run dev
```

默认 Vite dev server 会在 `http://localhost:5173` 启动；如端口/host 不同，请设置 `BASE_URL`（例如 `BASE_URL=http://127.0.0.1:5173`），以保证 Playwright `baseURL` 与实际地址一致。

### 4. Start Backend Server (Optional - for P1 tests)

```bash
REPO_ROOT="$(git rev-parse --show-toplevel)"
cd "$REPO_ROOT/frontend/backend"
source venv/bin/activate
python3 -m uvicorn main:app --host 0.0.0.0 --port 8000 --reload
```

默认 API 会在 `http://localhost:8000` 启动；如端口/host 不同，请设置 `API_BASE_URL`（例如 `API_BASE_URL=http://127.0.0.1:8000`）。

## Running Tests

### Run CI E2E Smoke (Mocked, No Backend/DB)

This mirrors the `.github/workflows/test.yml` `e2e-smoke` job (Vite build artifact + `vite preview` + mocked Playwright specs).

```bash
# From repo root
./scripts/run-tests.sh e2e-smoke
```

Notes:
- Requires port `5173` to be free (uses `--strictPort` like CI).
- In CI, `BASE_URL` is derived from the preview server host/port (see `.github/workflows/test.yml`) to avoid hard-coding `localhost:5173`.
- If Playwright reports missing browsers, install once:
  - `cd frontend/web && npx playwright install chromium`
- Current smoke specs (fully mocked):
  - `e2e/lncrna-chipseq-overlap-query-too-broad.spec.ts`
  - `e2e/genes-smoke.spec.ts`
  - `e2e/regulations-smoke.spec.ts`
  - `e2e/stats-smoke.spec.ts`
  - `e2e/diseases-smoke.spec.ts`
  - `e2e/analysis-smoke.spec.ts`
  - `e2e/conservation-smoke.spec.ts`
  - `e2e/visualization-hub-smoke.spec.ts`
  - `e2e/admin-monitoring-smoke.spec.ts`
  - `e2e/admin-cache-smoke.spec.ts`
  - `e2e/admin-materialized-views-smoke.spec.ts`

### Run All Tests

```bash
REPO_ROOT="$(git rev-parse --show-toplevel)"
cd "$REPO_ROOT/frontend/web"

# Run all tests in lncrna-chipseq-overlap.spec.ts
npm run test:e2e -- e2e/lncrna-chipseq-overlap.spec.ts
```

### Run QUERY_TOO_BROAD Guidance Test (Mocked)

This spec is designed to be independent of backend data by intercepting overlap API calls.

```bash
REPO_ROOT="$(git rev-parse --show-toplevel)"
cd "$REPO_ROOT/frontend/web"

npm run test:e2e -- e2e/lncrna-chipseq-overlap-query-too-broad.spec.ts
```

### Run Admin Monitoring Smoke Test (Mocked)

This spec is designed to be independent of backend/DB by intercepting the Admin metrics API.

```bash
REPO_ROOT="$(git rev-parse --show-toplevel)"
cd "$REPO_ROOT/frontend/web"

npm run test:e2e -- e2e/admin-monitoring-smoke.spec.ts
```

### Run Admin Cache Smoke Test (Mocked)

This spec is designed to be independent of backend/DB by intercepting the Admin cache stats API.

```bash
REPO_ROOT="$(git rev-parse --show-toplevel)"
cd "$REPO_ROOT/frontend/web"

npm run test:e2e -- e2e/admin-cache-smoke.spec.ts
```

### Run Admin Materialized Views Smoke Test (Mocked)

This spec is designed to be independent of backend/DB by intercepting the Admin materialized views status API.

```bash
REPO_ROOT="$(git rev-parse --show-toplevel)"
cd "$REPO_ROOT/frontend/web"

npm run test:e2e -- e2e/admin-materialized-views-smoke.spec.ts
```

### Run Genes Smoke Test (Mocked)

This spec is designed to be independent of backend/DB by intercepting the Genes list API.

```bash
REPO_ROOT="$(git rev-parse --show-toplevel)"
cd "$REPO_ROOT/frontend/web"

npm run test:e2e -- e2e/genes-smoke.spec.ts
```

### Run Regulations Smoke Test (Mocked)

This spec is designed to be independent of backend/DB by intercepting the Regulations list API and BA range endpoint.

```bash
REPO_ROOT="$(git rev-parse --show-toplevel)"
cd "$REPO_ROOT/frontend/web"

npm run test:e2e -- e2e/regulations-smoke.spec.ts
```

### Run Stats Smoke Test (Mocked)

This spec is designed to be independent of backend/DB by intercepting the Stats overview and detailed endpoints.

```bash
REPO_ROOT="$(git rev-parse --show-toplevel)"
cd "$REPO_ROOT/frontend/web"

npm run test:e2e -- e2e/stats-smoke.spec.ts
```

### Run Diseases Smoke Test (Mocked)

This spec is designed to be independent of backend/DB by intercepting the Diseases list API.

```bash
REPO_ROOT="$(git rev-parse --show-toplevel)"
cd "$REPO_ROOT/frontend/web"

npm run test:e2e -- e2e/diseases-smoke.spec.ts
```

### Run Analysis Smoke Test (Mocked)

This spec is designed to be independent of backend/DB by intercepting the analysis summary and high-affinity export endpoints.

```bash
REPO_ROOT="$(git rev-parse --show-toplevel)"
cd "$REPO_ROOT/frontend/web"

npm run test:e2e -- e2e/analysis-smoke.spec.ts
```

### Run Conservation Smoke Test (Mocked)

This spec is designed to be independent of backend/DB by intercepting the conservation overview/matrix/regulations endpoints.

```bash
REPO_ROOT="$(git rev-parse --show-toplevel)"
cd "$REPO_ROOT/frontend/web"

npm run test:e2e -- e2e/conservation-smoke.spec.ts
```

### Run Specific Test

```bash
# Run single test by name
npm run test:e2e -- e2e/lncrna-chipseq-overlap.spec.ts -g "should load the page successfully"
```

### Run with UI Mode (Recommended for Development)

```bash
# Interactive test runner with time-travel debugging
npm run test:e2e:ui -- e2e/lncrna-chipseq-overlap.spec.ts
```

### Run in Headed Mode (See Browser)

```bash
# Watch tests execute in real browser
npx playwright test e2e/lncrna-chipseq-overlap.spec.ts --headed
```

### Run in Debug Mode

```bash
# Step-by-step debugging with Playwright Inspector
npm run test:e2e:debug -- e2e/lncrna-chipseq-overlap.spec.ts
```

### Run Only P0 Tests

```bash
# Run tests excluding skipped P1 tests
npm run test:e2e -- e2e/lncrna-chipseq-overlap.spec.ts --grep-invert "should filter|should paginate|should sort"
```

### Run on Multiple Browsers

```bash
# Run on Chromium, Firefox, and WebKit
npx playwright test e2e/lncrna-chipseq-overlap.spec.ts --project=chromium,firefox,webkit
```

## Viewing Test Reports

### Generate HTML Report

```bash
# Run tests and generate report
npm run test:e2e -- e2e/lncrna-chipseq-overlap.spec.ts --reporter=html

# View report
npm run test:e2e:report
```

### JSON Report

```bash
npx playwright test e2e/lncrna-chipseq-overlap.spec.ts --reporter=json --output=test-results/results.json
```

## Test Results Interpretation

### Success Output

```
Running 25 tests using 1 worker

  ✓ 1 lncRNA-ChIP-seq Overlap Analysis Page › should load the page successfully (1.2s)
  ✓ 2 lncRNA-ChIP-seq Overlap Analysis Page › should display correct page title (856ms)
  ✓ 3 lncRNA-ChIP-seq Overlap Analysis Page › should display breadcrumb navigation (734ms)
  ...

  25 passed (45.2s)
```

### Failure Output

```
  1) lncRNA-ChIP-seq Overlap Analysis Page › should display data table
     Error: expect(received).toBeVisible()

     Call log:
       - expect.toBeVisible with timeout 15000ms
       - waiting for locator('.ant-table').first()

     Screenshot: test-results/lncrna-chipseq-overlap-should-display-data-table/test-failed-1.png
     Video: test-results/lncrna-chipseq-overlap-should-display-data-table/video.webm
```

## Troubleshooting

### Issue: Tests Timeout

**Symptom**: `Timeout 60000ms exceeded`

**Solutions**:
1. Increase timeout in test:
   ```typescript
   test('my test', async ({ page }) => {
     test.setTimeout(120000) // 2 minutes
   })
   ```

2. Check if frontend server is running:
   ```bash
   curl "${BASE_URL:-http://localhost:5173}"
   ```

3. Check for JavaScript errors in browser console (use `--headed` mode)

### Issue: Table Not Found

**Symptom**: `locator('.ant-table').first() not found`

**Solutions**:
1. 确认路由已注册（例如 `frontend/web/src/App.tsx`）且页面组件可正常渲染
2. Check if page route exists: `http://localhost:5173/lncrna-chipseq-overlap`
   - 如需覆盖 base URL：`${BASE_URL:-http://localhost:5173}/lncrna-chipseq-overlap`
3. Verify component is mounted in route config

### Issue: API Errors

**Symptom**: `500 Internal Server Error` or `404 Not Found`

**Solutions**:
1. Check if backend server is running:
   ```bash
   curl "${API_BASE_URL:-http://localhost:8000}/api/v1/lncrna-chipseq-overlap"
   ```

2. Note: P1 interactions in `e2e/lncrna-chipseq-overlap.spec.ts` intercept the overlap API.
   If you still see API errors, they likely come from other endpoints (e.g. IGV) or missing services.
3. Mock API responses in tests (already configured for error handling tests)

### Issue: Language Detection Fails

**Symptom**: Language tests fail or skip

**Solutions**:
1. Manually set language before test:
   ```typescript
   await page.goto('/lncrna-chipseq-overlap?lang=zh')
   ```

2. Check i18n configuration in frontend
3. Verify translation files exist

## Debugging Tips

### 1. Use Playwright Inspector

```bash
npm run test:e2e:debug -- e2e/lncrna-chipseq-overlap.spec.ts -g "should load the page"
```

- Step through test line by line
- Inspect element locators
- View network requests
- Check console logs

### 2. Take Screenshots

```typescript
test('my test', async ({ page }) => {
  await page.goto('/lncrna-chipseq-overlap')
  await page.screenshot({ path: 'debug-screenshot.png' })
})
```

### 3. Enable Trace Viewer

```bash
# Traces saved on first retry
npm run test:e2e -- e2e/lncrna-chipseq-overlap.spec.ts --trace on

# View trace
npx playwright show-trace trace.zip
```

### 4. Console Logs

```typescript
page.on('console', (msg) => console.log('Browser log:', msg.text()))
```

### 5. Network Monitoring

```typescript
page.on('request', (request) => console.log('Request:', request.url()))
page.on('response', (response) => console.log('Response:', response.status(), response.url()))
```

## CI/CD Integration

### GitHub Actions Example

本仓库已在 `Tests` 工作流（`.github/workflows/test.yml`）内集成两层 E2E：

- `e2e-smoke`：默认 `ubuntu-latest`（可通过 repo variable `CI_RUNS_ON` 切换到 `self-hosted`），基于 build artifact + `vite preview`，仅跑完全 mock 的 smoke 用例（无需后端/数据库）。在 self-hosted 上需预装 Playwright 系统依赖（见 `docs/CI_SELF_HOSTED_RUNNER.md`）。
- `e2e-tests`：`self-hosted` + 手动触发（`workflow_dispatch`），用于跑依赖后端/数据库的关键用例子集。

```yaml
name: E2E Tests

# 说明：本仓库目前默认关闭 push/PR 自动触发（额度/账单原因），主要使用 workflow_dispatch 手动触发。
# 该示例展示如何通过环境变量统一 Playwright baseURL（避免硬编码 localhost:5173）。
on:
  workflow_dispatch:
    inputs:
      base_url:
        description: "Playwright BASE_URL（默认 http://localhost:5173）"
        required: false
        default: "http://localhost:5173"

env:
  BASE_URL: ${{ github.event.inputs.base_url }}

jobs:
  test:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v3
      - uses: actions/setup-node@v3
        with:
          node-version: '18'

      - name: Install dependencies
        run: |
          cd frontend/web
          npm ci
          npx playwright install --with-deps chromium

      - name: Start frontend
        run: |
          cd frontend/web
          npm run dev &
          npx wait-on "$BASE_URL"

      - name: Run E2E tests
        run: |
          cd frontend/web
          npm run test:e2e -- e2e/lncrna-chipseq-overlap.spec.ts

      - name: Upload test results
        if: always()
        uses: actions/upload-artifact@v3
        with:
          name: playwright-report
          path: frontend/web/playwright-report/
```

## Test Maintenance

### Adding New Tests

1. Follow existing patterns in `lncrna-chipseq-overlap.spec.ts`
2. Use descriptive test names: `should [action] when [condition]`
3. Group related tests in `test.describe()` blocks
4. Use `test.beforeEach()` for common setup
5. Prefer mocking backend/DB dependencies via `page.route()`; only use `test.skip()` when a feature is not implemented yet

### Updating Tests After Frontend Changes

1. Component refactoring: Update selectors
2. API changes: Update expected responses
3. New features: Add new test cases
4. Removed features: Remove or skip obsolete tests

### Best Practices

1. **Prefer User-Facing Selectors**
   - ✅ `page.getByRole('button', { name: 'Submit' })`
   - ✅ `page.getByText('Hello')`
   - ❌ `page.locator('.btn-submit-123')`

2. **Use Web-First Assertions**
   - ✅ `await expect(locator).toBeVisible()`
   - ❌ `expect(await locator.isVisible()).toBe(true)`

3. **Avoid Hard Waits**
   - ✅ `await page.waitForResponse(resp => resp.url().includes('/api'))`
   - ❌ `await page.waitForTimeout(5000)`

4. **Test Behavior, Not Implementation**
   - ✅ Test that clicking button submits form
   - ❌ Test that onClick handler was called

## Test Report Template

After running tests, provide a summary using this template:

```markdown
## Test Execution Summary

**Date**: 2025-12-07
**Test Suite**: lncRNA-ChIP-seq Overlap E2E Tests
**Environment**: Local Development

### Results

- **Total Tests**: 25
- **Passed**: 20 ✅
- **Failed**: 0 ❌
- **Skipped**: 5 ⏸️
- **Duration**: 45.2s

### P0 Test Results

- ✅ Routing and Page Access (4/4)
- ✅ Component Rendering (6/6)
- ✅ Internationalization (3/3)

### P1 Test Results

- ✅ Filter Functionality (4/4)
- ✅ Table Interactions (4/4)

### Additional Tests

- ✅ Performance (2/2)
- ✅ Error Handling (3/3)
- ✅ API Integration (2/2)
- ✅ Accessibility (3/3)
- ✅ Deep Links (2/2)
- ✅ Mobile Responsiveness (2/2)

### Issues Found

None - all P0 tests passed.

### Next Steps

1. Add optional real-backend integration coverage for overlaps (seeded dataset)
2. Add tests for data export functionality
3. Add tests for advanced numeric filtering options
```

## Contact

For test-related questions or issues:
- Check Playwright documentation: https://playwright.dev
- Review existing test patterns in `e2e/` directory
- Contact frontend team for component-specific questions
