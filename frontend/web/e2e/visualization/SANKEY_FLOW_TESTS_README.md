# Sankey Flow Visualization E2E Tests

## Overview

Comprehensive Playwright E2E test suite for the Sankey flow diagram visualization feature.

**Status**: Test framework completed, awaiting page implementation
**Created**: 2025-12-12
**Test File**: `e2e/visualization/sankey-flow.spec.ts`
**Target Route**: `/visualization/sankey-flow`

## Test Statistics

| Metric | Count |
|--------|-------|
| Test Suites | 4 |
| Test Cases | 22 |
| Lines of Code | 637 |
| Helper Functions | 6 |
| Coverage | P0 + P1 + P2 |

## Test Suite Structure

### P0: Critical Functionality (7 tests)

| Test | Description | Expected Result |
|------|-------------|-----------------|
| should load page correctly | Page URL and container validation | Page loads with correct route |
| should render Sankey chart canvas | Canvas element rendering and pixel validation | Canvas visible with drawn content |
| should support i18n switching | Language toggle between Chinese/English | Text changes based on language |
| should display page title | Page heading verification | Title contains "Sankey" or "Flow" |
| should handle empty data state | Empty dataset response handling | Shows empty state message |
| should show loading state | Loading spinner during data fetch | Spinner appears then resolves |
| should handle API error gracefully | API failure error handling | Error message displayed |

### P1: Feature Validation (9 tests)

| Test | Description | User Action | Expected Result |
|------|-------------|-------------|-----------------|
| should filter by species | Species dropdown selection | Select Chimp/Macaque | Chart updates with filtered data |
| should filter by BA threshold | Slider drag interaction | Adjust BA threshold | Chart updates dynamically |
| should show tooltip on node hover | Mouse hover over nodes | Hover on canvas nodes | Tooltip displays node details |
| should export chart as PNG | PNG export button click | Click Export > PNG | PNG file downloads |
| should export chart as SVG | SVG export button click | Click Export > SVG | SVG file downloads |
| should support node click interaction | Node click action | Click on node | Detail panel or highlight appears |
| should show legend | Legend component verification | Page load | Legend visible with colors |
| should support search/filter controls | Search input interaction | Enter gene name | Chart filters by search term |

### P2: Performance & Edge Cases (3 tests)

| Test | Description | Performance Target | Validation |
|------|-------------|-------------------|------------|
| should render chart within 5 seconds | Initial render performance | < 5000ms | Chart renders within timeout |
| should handle large dataset | 100 nodes, 200 links | < 10000ms | No performance degradation |
| should be responsive on mobile | 375x667 viewport | Canvas ≤ 375px | Mobile adaptation |
| should be responsive on tablet | 768x1024 viewport | Content visible | Tablet adaptation |

### Accessibility (3 tests)

| Test | Description | Validation |
|------|-------------|------------|
| should have proper heading hierarchy | H1 heading presence | At least one H1 exists |
| should have keyboard navigation support | Tab key navigation | Focus moves correctly |
| should have color contrast for text | Text visibility | Text color is not transparent |

## Helper Functions

### waitForSankeyChart(page)
Waits for Sankey chart container and canvas to be visible.

**Returns**: `{ container: Locator, canvas: Locator }`
**Timeout**: 10s for container, 5s for canvas

### isSankeyRendered(canvas)
Checks if canvas has been drawn on by inspecting pixel data.

**Returns**: `boolean` (true if non-transparent pixels exist)

### getSpeciesFilter(page)
Locates species filter dropdown using multiple selector strategies.

**Returns**: `Locator`

### getBAThresholdSlider(page)
Locates BA threshold slider control.

**Returns**: `Locator`

### getExportButton(page)
Locates export button for chart download.

**Returns**: `Locator`

### switchLanguage(page, language)
Switches UI language to 'en' or 'zh'.

**Parameters**: `language: 'en' | 'zh'`

## Test-ID Requirements

Once the Sankey flow page is implemented, add these `data-testid` attributes:

| Element | Test-ID | Purpose |
|---------|---------|---------|
| Page Container | `sankey-flow-page` | Root page container |
| Chart Container | `sankey-flow-chart` | ECharts Sankey container |
| Species Filter | `sankey-species-filter` | Species dropdown |
| BA Slider | `sankey-ba-slider` | Binding affinity slider |
| Export Button | `sankey-export-button` | Export dropdown button |
| Legend | `sankey-legend` | Chart legend container |
| Detail Panel | `node-detail-panel` | Node detail drawer/modal |

## Running Tests

### Run all Sankey tests
```bash
cd /data/wenyujianData/human-lncrna-atlas-github/frontend/web
npx playwright test e2e/visualization/sankey-flow.spec.ts
```

### Run specific test suite
```bash
# P0 tests only
npx playwright test -g "P0 Critical"

# P1 tests only
npx playwright test -g "P1 Features"

# Performance tests
npx playwright test -g "P2 Performance"
```

### Run single test
```bash
npx playwright test -g "should render Sankey chart canvas"
```

### Debug mode (headed browser)
```bash
npx playwright test e2e/visualization/sankey-flow.spec.ts --headed --workers=1
```

### Generate HTML report
```bash
npx playwright test e2e/visualization/sankey-flow.spec.ts
npx playwright show-report
```

## Current Status

**IMPORTANT**: The `/visualization/sankey-flow` page does not exist yet. These tests will fail with 404 errors until the page is implemented.

### TODO: Page Implementation Checklist

- [ ] Create `/src/pages/Visualization/SankeyFlow/index.tsx`
- [ ] Add route to `src/App.tsx`
- [ ] Implement ECharts Sankey chart component
- [ ] Add species filter dropdown
- [ ] Add BA threshold slider
- [ ] Implement tooltip on node hover
- [ ] Add export functionality (PNG/SVG)
- [ ] Add data-testid attributes (see table above)
- [ ] Implement i18n translations
- [ ] Add loading and error states
- [ ] Add empty data state handling

### TODO: After Page Implementation

1. **Verify test-ids**: Ensure all `data-testid` attributes match the test expectations
2. **Run tests**: Execute full test suite and fix any failures
3. **API endpoint**: Confirm the API route matches `**/api/v1/sankey*` pattern
4. **API response format**: Verify response structure `{ nodes: [], links: [] }`
5. **Adjust selectors**: Update locators if UI structure differs from expectations
6. **Remove TODO comments**: Clean up TODO comments in test file
7. **Performance baseline**: Run performance tests and adjust timeouts if needed

## API Expectations

The tests assume the following API endpoint and response format:

### Endpoint
```
GET /api/v1/sankey?species_id={id}&min_ba={threshold}
```

### Response Format
```json
{
  "nodes": [
    { "name": "lncRNA_A", "value": 100 },
    { "name": "H3K27me3", "value": 200 },
    { "name": "GENE_A", "value": 150 }
  ],
  "links": [
    { "source": "lncRNA_A", "target": "H3K27me3", "value": 50 },
    { "source": "H3K27me3", "target": "GENE_A", "value": 30 }
  ]
}
```

### Error Response
```json
{
  "detail": "Error message"
}
```

## References

### Similar Test Files (for patterns)
- `e2e/lncrna-chipseq-overlap-charts.spec.ts` - Canvas testing patterns
- `e2e/network-visualization.spec.ts` - Interactive graph testing
- `e2e/conservation.spec.ts` - Filter and i18n patterns

### ECharts Sankey Documentation
- https://echarts.apache.org/en/option.html#series-sankey
- https://echarts.apache.org/examples/en/editor.html?c=sankey-simple

### Playwright Documentation
- Canvas Testing: https://playwright.dev/docs/api/class-locator#locator-evaluate
- Download Testing: https://playwright.dev/docs/downloads
- i18n Testing: https://playwright.dev/docs/test-parameterize

## Test Quality Standards

All tests follow Playwright best practices:

- ✅ Use web-first assertions (`toBeVisible()`, not `isVisible().toBe(true)`)
- ✅ Auto-waiting (no arbitrary `waitForTimeout()` unless necessary)
- ✅ Reliable locators (prefer test-ids, role-based, text-based)
- ✅ Independent tests (no order dependency)
- ✅ Clear test descriptions (what + when pattern)
- ✅ Proper error handling (`.catch(() => false)` for optional checks)
- ✅ Console logging for debugging
- ✅ Comprehensive coverage (happy path + edge cases + errors)

## Maintenance

### When to Update Tests

1. **Page URL changes**: Update `PAGE_URL` constant
2. **Test-ID changes**: Update locator functions
3. **API endpoint changes**: Update route mocking patterns
4. **New features added**: Add corresponding test cases
5. **UI structure changes**: Update selectors in helper functions

### Performance Baselines

Current timeouts are conservative. After page implementation, measure actual performance and tighten:

| Operation | Current Timeout | Recommended Target |
|-----------|----------------|-------------------|
| Page load | 30s | < 5s |
| Chart render | 10s | < 3s |
| Filter update | 5s | < 2s |
| Export | 10s | < 5s |

## Contact

**Test Developer**: Playwright Testing Agent (Claude Sonnet 4.5)
**Project**: Human LncRNA Atlas
**Date**: 2025-12-12
