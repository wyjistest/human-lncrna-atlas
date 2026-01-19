# lncRNA-ChIP-seq Overlap E2E Tests

## Overview

Comprehensive end-to-end tests for the lncRNA-ChIP-seq Overlap Analysis page using Playwright.

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

### P1 Tests (Optional - Backend Required)

#### 4. Filter Functionality
- ⏸️ Filter by mark type (H3K27me3, H3K4me3, etc.)
- ⏸️ Filter by cell line (K562, GM12878, HepG2, H1-hESC)
- ⏸️ Filter by chromosome (chr1-chr22, chrX, chrY)
- ⏸️ Reset filters

#### 5. Table Interactions
- ⏸️ Pagination through results
- ⏸️ Sort by overlap length
- ⏸️ Sort by chromosome
- ⏸️ Expand row details

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

Server should run at `http://localhost:5173`

### 4. Start Backend Server (Optional - for P1 tests)

```bash
REPO_ROOT="$(git rev-parse --show-toplevel)"
cd "$REPO_ROOT/frontend/backend"
source venv/bin/activate
python3 -m uvicorn main:app --host 0.0.0.0 --port 8000 --reload
```

API should run at `http://localhost:8000`

## Running Tests

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
   curl http://localhost:5173
   ```

3. Check for JavaScript errors in browser console (use `--headed` mode)

### Issue: Table Not Found

**Symptom**: `locator('.ant-table').first() not found`

**Solutions**:
1. Wait for route integration from frontend agent
2. Check if page route exists: `http://localhost:5173/lncrna-chipseq-overlap`
3. Verify component is mounted in route config

### Issue: API Errors

**Symptom**: `500 Internal Server Error` or `404 Not Found`

**Solutions**:
1. Check if backend server is running:
   ```bash
   curl http://localhost:8000/api/v1/lncrna-chipseq-overlap
   ```

2. Skip P1 tests that require backend:
   ```bash
   npm run test:e2e -- e2e/lncrna-chipseq-overlap.spec.ts --grep-invert "skip"
   ```

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

```yaml
name: E2E Tests

on: [push, pull_request]

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
          npx wait-on http://localhost:5173

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
5. Mark backend-dependent tests with `test.skip()`

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

### P1 Test Results (Skipped - Backend Not Ready)

- ⏸️ Filter Functionality (0/4 - skipped)
- ⏸️ Table Interactions (0/4 - skipped)

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

1. Enable P1 tests once backend API is ready
2. Add tests for data export functionality
3. Add tests for advanced filtering options
```

## Contact

For test-related questions or issues:
- Check Playwright documentation: https://playwright.dev
- Review existing test patterns in `e2e/` directory
- Contact frontend team for component-specific questions
