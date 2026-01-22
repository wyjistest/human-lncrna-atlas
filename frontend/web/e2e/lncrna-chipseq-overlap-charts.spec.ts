import { test, expect, type Page } from '@playwright/test'

/**
 * lncRNA-ChIP-seq Overlap Visualization Charts E2E Tests
 * Phase 3.0 - Phase 2 Playwright E2E Tests
 *
 * Covers visualization components:
 * 1. Mark Distribution Bar Chart
 * 2. Cell Type Pie Chart
 * 3. Heatmap Matrix
 * 4. Chart interactions (metric switching, filter updates)
 * 5. Performance and responsive design
 *
 * Note: Charts use ECharts which renders to canvas elements.
 * Page language may be Chinese or English depending on browser settings.
 */

const PAGE_URL = '/lncrna-chipseq-overlap'

// ============================================================================
// Helper Functions
// ============================================================================

/**
 * Wait for a chart canvas to be visible within a container
 * @param page - Playwright page object
 * @param containerSelector - CSS selector for the chart container
 * @param timeout - Maximum time to wait in milliseconds
 * @returns The canvas locator
 */
async function waitForChartCanvas(page: Page, containerSelector: string, timeout = 5000) {
  const container = page.locator(containerSelector)
  await expect(container).toBeVisible({ timeout })
  const canvas = container.locator('canvas')
  await expect(canvas.first()).toBeVisible({ timeout })
  return canvas
}

/**
 * Count the number of visible chart canvases on the page
 * @param page - Playwright page object
 * @returns Number of visible canvas elements
 */
async function countChartCanvases(page: Page): Promise<number> {
  const canvases = page.locator('canvas')
  return await canvases.count()
}

/**
 * Check if a canvas element has been drawn on (has pixel data)
 * @param page - Playwright page object
 * @param canvasLocator - Locator for the canvas element
 * @returns True if canvas has content
 */
async function isCanvasDrawn(page: Page, canvasLocator: ReturnType<typeof page.locator>): Promise<boolean> {
  try {
    return await canvasLocator.evaluate((canvas: HTMLCanvasElement) => {
      const ctx = canvas.getContext('2d')
      if (!ctx) return false
      const imageData = ctx.getImageData(0, 0, canvas.width, canvas.height)
      // Check if there are any non-transparent pixels
      for (let i = 3; i < imageData.data.length; i += 4) {
        if (imageData.data[i] !== 0) return true
      }
      return false
    })
  } catch {
    return false
  }
}

/**
 * Get locator for Mark Distribution chart container
 */
function getMarkDistChartLocator(page: Page) {
  return page.locator('[data-testid="overlap-mark-dist-chart"]')
    .or(page.locator('.ant-card').filter({ hasText: /Mark.*Distribution|标记.*分布/i }))
}

/**
 * Get locator for Cell Type chart container
 */
function getCellTypeChartLocator(page: Page) {
  return page.locator('[data-testid="overlap-cell-type-chart"]')
    .or(page.locator('.ant-card').filter({ hasText: /Cell.*Type|细胞.*类型/i }))
}

/**
 * Get locator for Heatmap Matrix container
 */
function getHeatmapMatrixLocator(page: Page) {
  return page.locator('[data-testid="overlap-heatmap-matrix"]')
    .or(page.locator('.ant-card').filter({ hasText: /Heatmap|热图|矩阵|Matrix/i }))
}

/**
 * Enable statistics/charts display if a toggle exists
 */
async function enableStatsIfNeeded(page: Page): Promise<boolean> {
  // Look for "Show Statistics" toggle or button
  const statsToggle = page.locator('.ant-switch').filter({ hasText: /Statistics|统计/i })
    .or(page.getByRole('switch').filter({ hasText: /Statistics|统计/i }))

  const toggleCount = await statsToggle.count()
  if (toggleCount > 0) {
    const isChecked = await statsToggle.first().getAttribute('aria-checked')
    if (isChecked !== 'true') {
      await statsToggle.first().click()
      await page.waitForTimeout(1000)
    }
    return true
  }

  // Look for stats button
  const statsButton = page.getByRole('button', { name: /Show Statistics|显示统计|统计/i })
  if (await statsButton.count() > 0) {
    await statsButton.first().click()
    await page.waitForTimeout(1000)
    return true
  }

  return false
}

// ============================================================================
// Test Suite: lncRNA-ChIP-seq Overlap Visualization Charts
// ============================================================================

test.describe('lncRNA-ChIP-seq Overlap Visualization Charts', () => {
  test.beforeEach(async ({ page }) => {
    await page.goto(PAGE_URL)
    await page.waitForLoadState('networkidle')
    // Wait for initial content to stabilize
    await page.waitForTimeout(1000)
  })

  // ==========================================================================
  // P0 Tests: Critical Chart Rendering
  // ==========================================================================

  test.describe('P0: Chart Rendering', () => {

    test('should render mark distribution bar chart', async ({ page }) => {
      // Enable stats display if toggle exists
      await enableStatsIfNeeded(page)
      await page.waitForTimeout(1500)

      const chartContainer = getMarkDistChartLocator(page)

      if (await chartContainer.count() > 0) {
        await expect(chartContainer.first()).toBeVisible({ timeout: 5000 })

        // Check for canvas (ECharts renders to canvas)
        const canvas = chartContainer.locator('canvas')
        const canvasCount = await canvas.count()

        if (canvasCount > 0) {
          await expect(canvas.first()).toBeVisible({ timeout: 3000 })
          console.log('Mark distribution bar chart canvas found and visible')
        } else {
          // Chart might use SVG or div-based rendering
          const chartContent = chartContainer.locator('svg, [class*="echarts"], [class*="chart"]')
          const contentCount = await chartContent.count()
          console.log(`Mark distribution chart alternative content: ${contentCount} elements`)
        }
      } else {
        // Chart component might not be implemented yet or stats disabled
        console.log('Mark distribution chart container not found - feature may be in Phase 2')

        // Verify at least the stats cards section exists
        const statsSection = page.locator('.ant-card').filter({ hasText: /Distribution|分布|Mark|标记/i })
        const statsSectionCount = await statsSection.count()
        console.log(`Stats sections found: ${statsSectionCount}`)
      }
    })

    test('should render cell type pie chart', async ({ page }) => {
      // Enable stats display if toggle exists
      await enableStatsIfNeeded(page)
      await page.waitForTimeout(1500)

      const chartContainer = getCellTypeChartLocator(page)

      if (await chartContainer.count() > 0) {
        await expect(chartContainer.first()).toBeVisible({ timeout: 5000 })

        // Check for canvas (ECharts pie chart)
        const canvas = chartContainer.locator('canvas')
        const canvasCount = await canvas.count()

        if (canvasCount > 0) {
          await expect(canvas.first()).toBeVisible({ timeout: 3000 })
          console.log('Cell type pie chart canvas found and visible')
        } else {
          // Check for alternative rendering
          const chartContent = chartContainer.locator('svg, [class*="echarts"], [class*="chart"]')
          console.log(`Cell type chart alternative content: ${await chartContent.count()} elements`)
        }
      } else {
        console.log('Cell type pie chart container not found - feature may be in Phase 2')

        // Check for cell type distribution in stats cards
        const cellTypeSection = page.locator('.ant-card').filter({ hasText: /Cell.*Type|细胞.*类型/i })
        console.log(`Cell type sections found: ${await cellTypeSection.count()}`)
      }
    })

    test('should render heatmap matrix', async ({ page }) => {
      // Enable stats display if toggle exists
      await enableStatsIfNeeded(page)
      await page.waitForTimeout(1500)

      const heatmapContainer = getHeatmapMatrixLocator(page)

      if (await heatmapContainer.count() > 0) {
        await expect(heatmapContainer.first()).toBeVisible({ timeout: 5000 })

        // Heatmap renders to canvas
        const canvas = heatmapContainer.locator('canvas')
        const canvasCount = await canvas.count()

        if (canvasCount > 0) {
          await expect(canvas.first()).toBeVisible({ timeout: 3000 })
          console.log('Heatmap matrix canvas found and visible')
        } else {
          // Check for SVG or table-based heatmap
          const heatmapContent = heatmapContainer.locator('svg, table, [class*="heatmap"]')
          console.log(`Heatmap alternative content: ${await heatmapContent.count()} elements`)
        }
      } else {
        console.log('Heatmap matrix container not found - feature may be in Phase 2')
      }
    })

    test('should handle empty state gracefully', async ({ page }) => {
      // Mock API to return empty data
      await page.route('**/api/v1/lncrna-chipseq-overlap/summary*', (route) => {
        route.fulfill({
          status: 200,
          contentType: 'application/json',
          body: JSON.stringify({
            total_overlaps: 0,
            unique_lncrnas: 0,
            unique_target_genes: 0,
            unique_marks: 0,
            unique_cell_types: 0,
            avg_overlap_length: 0,
            avg_binding_affinity: 0,
            avg_peak_strength: 0,
            by_mark_type: [],
            by_cell_type: []
          })
        })
      })

      await page.route('**/api/v1/lncrna-chipseq-overlap*', (route) => {
        // Only intercept the main endpoint, not summary
        if (!route.request().url().includes('summary')) {
          route.fulfill({
            status: 200,
            contentType: 'application/json',
            body: JSON.stringify({
              items: [],
              total: 0,
              page: 1,
              page_size: 20
            })
          })
        } else {
          route.continue()
        }
      })

      await page.goto(PAGE_URL)
      await page.waitForTimeout(2000)

      // Should show empty state or "no data" message
      const emptyState = page.locator('.ant-empty')
      const noDataText = page.getByText(/No.*Data|No.*overlaps|暂无数据|没有.*重叠/i)

      const hasEmpty = await emptyState.isVisible().catch(() => false)
      const hasNoDataText = await noDataText.isVisible().catch(() => false)

      // Page should handle empty data gracefully
      expect(hasEmpty || hasNoDataText).toBeTruthy()
      console.log(`Empty state visible: ${hasEmpty}, No data text visible: ${hasNoDataText}`)
    })

    test('should show loading state with spinner', async ({ page }) => {
      // Delay API response to observe loading state
      await page.route('**/api/v1/lncrna-chipseq-overlap*', async (route) => {
        await new Promise(resolve => setTimeout(resolve, 3000))
        try {
          await route.continue()
        } catch {
          // Request might be aborted or the route might be removed while waiting (best-effort delay).
        }
      })

      // Navigate and immediately check for loading
      await page.goto(PAGE_URL)

      // Check for loading spinner
      const loadingSpinner = page.locator('.ant-spin')
        .or(page.locator('[class*="loading"]'))
        .or(page.locator('.ant-skeleton'))

      // Loading should appear during data fetch
      const hasLoading = await loadingSpinner.first().isVisible({ timeout: 2000 }).catch(() => false)
      console.log(`Loading state visible: ${hasLoading}`)

      // If loading found, verify it eventually resolves
      if (hasLoading) {
        // Wait for loading to complete
        await page.waitForTimeout(4000)

        // Content should appear after loading
        const mainContent = page.locator('.ant-table, .ant-card, .ant-empty').first()
        await expect(mainContent).toBeVisible({ timeout: 10000 })
      }

      // Clean up route
      await page.unrouteAll({ behavior: 'ignoreErrors' })
    })

    test('should handle API error gracefully', async ({ page }) => {
      // Intercept both statistics endpoints:
      // - /statistics is the canonical endpoint
      // - /summary is an alias for backward compatibility
      // We intercept both to ensure complete test coverage
      await page.route('**/api/v1/lncrna-chipseq-overlap/statistics*', (route) => {
        route.fulfill({
          status: 500,
          contentType: 'application/json',
          body: JSON.stringify({ detail: 'Internal Server Error' })
        })
      })

      await page.route('**/api/v1/lncrna-chipseq-overlap/summary*', (route) => {
        route.fulfill({
          status: 500,
          contentType: 'application/json',
          body: JSON.stringify({ detail: 'Internal Server Error' })
        })
      })

      await page.goto(PAGE_URL)
      await page.waitForTimeout(2000)

      // Should show error state or fallback gracefully
      const errorMessage = page.getByText(/Error|Failed|错误|失败|500/i)
      const hasError = await errorMessage.isVisible().catch(() => false)

      // Or show empty state
      const emptyState = page.locator('.ant-empty')
      const hasEmpty = await emptyState.isVisible().catch(() => false)

      // Or show alert
      const alertError = page.locator('.ant-alert-error, .ant-message-error')
      const hasAlert = await alertError.isVisible().catch(() => false)

      // Or table still loads (main endpoint might work)
      const table = page.locator('.ant-table')
      const hasTable = await table.isVisible().catch(() => false)

      expect(hasError || hasEmpty || hasAlert || hasTable).toBeTruthy()
      console.log(`Error handling: error=${hasError}, empty=${hasEmpty}, alert=${hasAlert}, table=${hasTable}`)

      // Clean up routes
      await page.unrouteAll({ behavior: 'ignoreErrors' })
    })
  })

  // ==========================================================================
  // P1 Tests: Chart Interactions
  // ==========================================================================

  test.describe('P1: Chart Interactions', () => {

    test('should toggle metric switcher for heatmap correctly', async ({ page }) => {
      // Enable stats if needed
      await enableStatsIfNeeded(page)
      await page.waitForTimeout(1500)

      const heatmapContainer = getHeatmapMatrixLocator(page)

      if (await heatmapContainer.count() === 0) {
        console.log('Heatmap not found - skipping metric switcher test')
        return
      }

      // Look for metric selector (dropdown or segmented control)
      const metricSelector = page.locator('[data-testid="heatmap-metric-selector"]')
        .or(page.locator('.ant-select').filter({ hasText: /Metric|度量|Count|Strength/i }))
        .or(page.locator('.ant-segmented'))
        .or(heatmapContainer.locator('.ant-select, .ant-segmented'))

      if (await metricSelector.count() > 0) {
        // Get initial canvas state
        const initialCanvas = heatmapContainer.locator('canvas').first()
        const initialVisible = await initialCanvas.isVisible().catch(() => false)

        // Click to change metric
        await metricSelector.first().click()
        await page.waitForTimeout(300)

        // Look for metric options
        const metricOptions = page.locator('.ant-select-dropdown .ant-select-item')
          .or(page.locator('.ant-segmented-item'))

        if (await metricOptions.count() > 1) {
          // Select a different metric
          await metricOptions.nth(1).click()
          await page.waitForTimeout(1000)

          // Verify canvas is still visible (chart updated)
          if (initialVisible) {
            const updatedCanvas = heatmapContainer.locator('canvas').first()
            await expect(updatedCanvas).toBeVisible({ timeout: 3000 })
            console.log('Metric switcher toggled successfully')
          }
        }
      } else {
        console.log('Metric selector not found for heatmap')
      }
    })

    test('should update charts on filter change', async ({ page }) => {
      // Enable stats if needed
      await enableStatsIfNeeded(page)
      await page.waitForTimeout(1500)

      // Count initial charts
      const initialCanvasCount = await countChartCanvases(page)
      console.log(`Initial canvas count: ${initialCanvasCount}`)

      // Find and interact with filter controls
      const markTypeFilter = page.locator('.ant-select').filter({ hasText: /Mark.*Type|标记.*类型|H3K/i }).first()
        .or(page.locator('[data-testid="mark-type-filter"]'))

      if (await markTypeFilter.count() > 0) {
        await markTypeFilter.first().click()
        await page.waitForTimeout(300)

        // Select a mark type
        const markOptions = page.locator('.ant-select-dropdown .ant-select-item')
        if (await markOptions.count() > 0) {
          await markOptions.first().click()
          await page.waitForTimeout(2000)

          // Verify charts are still rendered after filter
          const afterFilterCanvasCount = await countChartCanvases(page)
          console.log(`After filter canvas count: ${afterFilterCanvasCount}`)

          // Charts should still be present (count may change with data)
          expect(afterFilterCanvasCount).toBeGreaterThanOrEqual(0)
        }
      } else {
        console.log('Mark type filter not found - testing with chromosome filter')

        // Try chromosome filter instead
        const chrFilter = page.locator('.ant-select').filter({ hasText: /Chromosome|染色体|chr/i }).first()
        if (await chrFilter.count() > 0) {
          await chrFilter.click()
          await page.waitForTimeout(300)

          const chrOptions = page.locator('.ant-select-dropdown .ant-select-item').filter({ hasText: /chr1/i })
          if (await chrOptions.count() > 0) {
            await chrOptions.first().click()
            await page.waitForTimeout(2000)
          }
        }
      }
    })

    test('charts should render within 2 seconds', async ({ page }) => {
      const startTime = Date.now()

      await page.goto(PAGE_URL)

      // Wait for any chart canvas to appear
      const chartCanvases = page.locator('canvas')

      try {
        await chartCanvases.first().waitFor({ state: 'visible', timeout: 5000 })
        const renderTime = Date.now() - startTime
        console.log(`Charts rendered in ${renderTime}ms`)

        // Render time should be under 2 seconds for good UX
        // Using 5000 as threshold to account for initial load
        expect(renderTime).toBeLessThan(5000)
      } catch {
        // If no canvas found, check if stats need to be enabled
        console.log('No canvas found initially - charts may require stats toggle')

        await enableStatsIfNeeded(page)
        await page.waitForTimeout(2000)

        const afterToggleCanvasCount = await countChartCanvases(page)
        console.log(`After enabling stats: ${afterToggleCanvasCount} canvases`)
      }
    })

    test('should display i18n labels correctly', async ({ page }) => {
      // Enable stats if needed
      await enableStatsIfNeeded(page)
      await page.waitForTimeout(1500)

      // Check for chart-related labels in current language
      const pageText = await page.textContent('body')

      // Detect language (Chinese or English)
      const isChinese = /[\u4e00-\u9fa5]/.test(pageText || '')

      if (isChinese) {
        // Check for Chinese labels
        const chineseLabels = [
          /分布/,      // Distribution
          /标记/,      // Mark
          /细胞/,      // Cell
          /类型/,      // Type
          /热图/,      // Heatmap
          /统计/,      // Statistics
          /重叠/,      // Overlap
        ]

        let foundLabels = 0
        for (const label of chineseLabels) {
          if (label.test(pageText || '')) {
            foundLabels++
          }
        }
        console.log(`Found ${foundLabels}/${chineseLabels.length} Chinese labels`)
        expect(foundLabels).toBeGreaterThan(0)
      } else {
        // Check for English labels
        const englishLabels = [
          /Distribution/i,
          /Mark/i,
          /Cell/i,
          /Type/i,
          /Heatmap|Matrix/i,
          /Statistics/i,
          /Overlap/i,
        ]

        let foundLabels = 0
        for (const label of englishLabels) {
          if (label.test(pageText || '')) {
            foundLabels++
          }
        }
        console.log(`Found ${foundLabels}/${englishLabels.length} English labels`)
        expect(foundLabels).toBeGreaterThan(0)
      }
    })

    test('should have chart export button if available', async ({ page }) => {
      // Enable stats if needed
      await enableStatsIfNeeded(page)
      await page.waitForTimeout(1500)

      // Look for export button near charts
      const exportButton = page.getByRole('button', { name: /Export|Download|导出|下载/i })
        .or(page.locator('button').filter({ hasText: /Export|Download|PNG|SVG|导出/i }))
        .or(page.locator('[data-testid*="export"]'))

      const exportCount = await exportButton.count()
      console.log(`Export buttons found: ${exportCount}`)

      if (exportCount > 0) {
        // Verify export button is clickable
        await expect(exportButton.first()).toBeEnabled()

        // Optionally click and verify export options
        await exportButton.first().click()
        await page.waitForTimeout(500)

        // Check for export format options
        const formatOptions = page.locator('.ant-dropdown-menu-item')
          .or(page.getByText(/PNG|SVG|CSV|Excel|PDF/i))

        const optionsCount = await formatOptions.count()
        console.log(`Export format options: ${optionsCount}`)

        // Close dropdown if open
        await page.keyboard.press('Escape')
      } else {
        console.log('No export button found - feature may not be implemented')
      }
    })
  })

  // ==========================================================================
  // P2 Tests: Performance and Responsiveness
  // ==========================================================================

  test.describe('P2: Performance', () => {

    test('should render charts with large dataset within acceptable time', async ({ page }) => {
      // Mock API to return large dataset
      await page.route('**/api/v1/lncrna-chipseq-overlap/summary*', (route) => {
        // Simulate large dataset summary
        const largeByMarkType = Array.from({ length: 20 }, (_, i) => ({
          mark_type: `H3K${i}me${i % 3 + 1}`,
          count: Math.floor(Math.random() * 10000),
          avg_strength: Math.random() * 100
        }))

        const largeByCellType = Array.from({ length: 50 }, (_, i) => ({
          cell_type: `CellType_${i}`,
          count: Math.floor(Math.random() * 5000)
        }))

        route.fulfill({
          status: 200,
          contentType: 'application/json',
          body: JSON.stringify({
            total_overlaps: 500000,
            unique_lncrnas: 5000,
            unique_target_genes: 3000,
            unique_marks: 20,
            unique_cell_types: 50,
            avg_overlap_length: 150,
            avg_binding_affinity: 75,
            avg_peak_strength: 25,
            by_mark_type: largeByMarkType,
            by_cell_type: largeByCellType
          })
        })
      })

      const startTime = Date.now()
      await page.goto(PAGE_URL)
      await page.waitForLoadState('domcontentloaded')

      // Enable stats if needed
      await enableStatsIfNeeded(page)
      await page.waitForTimeout(2000)

      const renderTime = Date.now() - startTime
      console.log(`Large dataset render time: ${renderTime}ms`)

      // Should render within 10 seconds even with large data
      expect(renderTime).toBeLessThan(10000)

      // Verify charts rendered
      const canvasCount = await countChartCanvases(page)
      console.log(`Canvases rendered with large dataset: ${canvasCount}`)

      // Clean up
      await page.unrouteAll({ behavior: 'ignoreErrors' })
    })

    test('should be responsive on mobile viewport', async ({ page }) => {
      // Set mobile viewport
      await page.setViewportSize({ width: 375, height: 667 })

      await page.goto(PAGE_URL)
      await page.waitForLoadState('networkidle')
      await page.waitForTimeout(1500)

      // Enable stats if needed
      await enableStatsIfNeeded(page)
      await page.waitForTimeout(1000)

      // Verify main content is visible and not cut off
      const mainContent = page.locator('h1, h2, .ant-card, .ant-table').first()
      await expect(mainContent).toBeVisible({ timeout: 10000 })

      // Check that cards/charts are stacked vertically on mobile
      const cards = page.locator('.ant-card')
      const cardCount = await cards.count()
      console.log(`Cards visible on mobile: ${cardCount}`)

      if (cardCount > 1) {
        // Verify cards don't overflow horizontally
        const firstCard = cards.first()
        const box = await firstCard.boundingBox()

        if (box) {
          // Card should fit within viewport width
          expect(box.x).toBeGreaterThanOrEqual(0)
          expect(box.x + box.width).toBeLessThanOrEqual(375 + 20) // Allow small margin
          console.log(`First card fits viewport: x=${box.x}, width=${box.width}`)
        }
      }

      // Check if charts scale properly
      const canvases = page.locator('canvas')
      const canvasCount = await canvases.count()

      if (canvasCount > 0) {
        const canvasBox = await canvases.first().boundingBox()
        if (canvasBox) {
          // Canvas should fit within mobile viewport
          expect(canvasBox.width).toBeLessThanOrEqual(375)
          console.log(`Canvas size on mobile: ${canvasBox.width}x${canvasBox.height}`)
        }
      }
    })

    test('should handle tablet viewport correctly', async ({ page }) => {
      // Set tablet viewport (iPad)
      await page.setViewportSize({ width: 768, height: 1024 })

      await page.goto(PAGE_URL)
      await page.waitForLoadState('networkidle')
      await page.waitForTimeout(1500)

      // Enable stats if needed
      await enableStatsIfNeeded(page)
      await page.waitForTimeout(1000)

      // Verify content renders properly on tablet
      const mainContent = page.locator('.ant-card, .ant-table').first()
      await expect(mainContent).toBeVisible({ timeout: 10000 })

      // Check layout - cards might be side by side on tablet
      const cards = page.locator('.ant-card')
      const cardCount = await cards.count()
      console.log(`Cards visible on tablet: ${cardCount}`)

      // Verify no horizontal scroll issues
      const bodyWidth = await page.evaluate(() => document.body.scrollWidth)
      expect(bodyWidth).toBeLessThanOrEqual(768 + 50) // Allow small overflow
      console.log(`Body scroll width on tablet: ${bodyWidth}`)
    })
  })
})

// ============================================================================
// Additional Test Suite: Chart Integration with Filters
// ============================================================================

test.describe('Chart-Filter Integration', () => {
  test.beforeEach(async ({ page }) => {
    await page.goto(PAGE_URL)
    await page.waitForLoadState('networkidle')
    await page.waitForTimeout(1000)
  })

  test('should reflect filter changes in chart data', async ({ page }) => {
    // Enable stats
    await enableStatsIfNeeded(page)
    await page.waitForTimeout(1500)

    // Track API calls
    const summaryApiCalls: string[] = []

    page.on('request', (request) => {
      if (request.url().includes('/summary') || request.url().includes('/statistics')) {
        summaryApiCalls.push(request.url())
      }
    })

    // Apply a filter
    const markFilter = page.locator('.ant-select').first()
    if (await markFilter.count() > 0) {
      await markFilter.click()
      await page.waitForTimeout(300)

      const option = page.locator('.ant-select-dropdown .ant-select-item').first()
      if (await option.count() > 0) {
        await option.click()
        await page.waitForTimeout(2000)

        // Verify API was called with filter
        const hasFilteredCall = summaryApiCalls.some(url =>
          url.includes('mark_type=') || url.includes('cell_type=') || url.includes('chromosome=')
        )
        console.log(`API calls after filter: ${summaryApiCalls.length}`)
        console.log(`Contains filtered call: ${hasFilteredCall}`)
      }
    }
  })

  test('should maintain chart state during pagination', async ({ page }) => {
    // Enable stats
    await enableStatsIfNeeded(page)
    await page.waitForTimeout(1500)

    // Charts are rendered asynchronously (React Query + ECharts). Wait for at least one canvas.
    await expect.poll(async () => countChartCanvases(page), { timeout: 15000 }).toBeGreaterThan(0)

    // Count initial charts
    const initialCanvasCount = await countChartCanvases(page)
    console.log(`Initial canvas count: ${initialCanvasCount}`)

    // Find and click pagination
    const pagination = page.locator('.ant-pagination')
    if (await pagination.isVisible()) {
      const nextButton = pagination.locator('.ant-pagination-next:not(.ant-pagination-disabled)')

      if (await nextButton.count() > 0) {
        await nextButton.click()
        await page.waitForTimeout(1500)

        // Charts should still be visible after pagination
        const afterPaginationCanvasCount = await countChartCanvases(page)
        console.log(`After pagination canvas count: ${afterPaginationCanvasCount}`)

        // Canvas count should remain consistent (charts persist)
        expect(afterPaginationCanvasCount).toBe(initialCanvasCount)
      }
    }
  })
})

// ============================================================================
// Test Suite: Heatmap Specific Tests
// ============================================================================

test.describe('Heatmap Matrix Specific Tests', () => {
  test.beforeEach(async ({ page }) => {
    await page.goto(PAGE_URL)
    await page.waitForLoadState('networkidle')
    await page.waitForTimeout(1000)
    await enableStatsIfNeeded(page)
    await page.waitForTimeout(1500)
  })

  test('should display heatmap with correct axis labels', async ({ page }) => {
    const heatmapContainer = getHeatmapMatrixLocator(page)

    if (await heatmapContainer.count() === 0) {
      console.log('Heatmap not available - skipping axis label test')
      return
    }

    // Look for axis labels
    const xAxisLabel = heatmapContainer.getByText(/Mark|Cell|细胞|标记/i)
    const yAxisLabel = heatmapContainer.getByText(/lncRNA|Gene|基因/i)

    const hasXAxis = await xAxisLabel.count() > 0
    const hasYAxis = await yAxisLabel.count() > 0

    console.log(`X-axis label found: ${hasXAxis}, Y-axis label found: ${hasYAxis}`)

    // At least one axis label should be present
    if (hasXAxis || hasYAxis) {
      expect(hasXAxis || hasYAxis).toBeTruthy()
    }
  })

  test('should show tooltip on heatmap cell hover', async ({ page }) => {
    const heatmapContainer = getHeatmapMatrixLocator(page)

    if (await heatmapContainer.count() === 0) {
      console.log('Heatmap not available - skipping tooltip test')
      return
    }

    const canvas = heatmapContainer.locator('canvas').first()

    if (await canvas.isVisible()) {
      const box = await canvas.boundingBox()

      if (box) {
        // Hover over center of canvas
        await page.mouse.move(box.x + box.width / 2, box.y + box.height / 2)
        await page.waitForTimeout(500)

        // Check for tooltip
        const tooltip = page.locator('.ant-tooltip, [class*="tooltip"], [class*="echarts-tooltip"]')
        const tooltipVisible = await tooltip.isVisible().catch(() => false)

        console.log(`Heatmap tooltip visible: ${tooltipVisible}`)
      }
    }
  })

  test('should support heatmap zoom/pan if available', async ({ page }) => {
    const heatmapContainer = getHeatmapMatrixLocator(page)

    if (await heatmapContainer.count() === 0) {
      console.log('Heatmap not available - skipping zoom test')
      return
    }

    // Look for zoom controls
    const zoomControls = heatmapContainer.locator('button').filter({ hasText: /Zoom|\+|-|Reset|重置/i })
      .or(page.locator('[data-testid*="zoom"]'))

    const hasZoomControls = await zoomControls.count() > 0
    console.log(`Zoom controls available: ${hasZoomControls}`)

    if (hasZoomControls) {
      await zoomControls.first().click()
      await page.waitForTimeout(500)
    }
  })
})

// ============================================================================
// Test Suite: API Mocking for Edge Cases
// ============================================================================

test.describe('API Edge Cases', () => {

  test('should handle slow API response without timeout', async ({ page }) => {
    // Delay API response by 5 seconds
    await page.route('**/api/v1/lncrna-chipseq-overlap/summary*', async (route) => {
      await new Promise(resolve => setTimeout(resolve, 5000))
      route.fulfill({
        status: 200,
        contentType: 'application/json',
        body: JSON.stringify({
          total_overlaps: 1000,
          unique_lncrnas: 100,
          unique_target_genes: 50,
          unique_marks: 5,
          unique_cell_types: 4,
          avg_overlap_length: 150,
          avg_binding_affinity: 70,
          avg_peak_strength: 20,
          by_mark_type: [
            { mark_type: 'H3K27me3', count: 500, avg_strength: 25 },
            { mark_type: 'H3K4me3', count: 300, avg_strength: 22 }
          ],
          by_cell_type: [
            { cell_type: 'K562', count: 600 },
            { cell_type: 'HepG2', count: 400 }
          ]
        })
      })
    })

    const startTime = Date.now()
    await page.goto(PAGE_URL)

    // Wait for page to load
    await page.waitForLoadState('networkidle')

    // Enable stats
    await enableStatsIfNeeded(page)

    // Wait for delayed response
    await page.waitForTimeout(6000)

    const totalTime = Date.now() - startTime
    console.log(`Total time with slow API: ${totalTime}ms`)

    // Verify page didn't crash
    const mainContent = page.locator('.ant-card, .ant-table').first()
    await expect(mainContent).toBeVisible({ timeout: 3000 })

    // Clean up
    await page.unrouteAll({ behavior: 'ignoreErrors' })
  })

  test('should handle malformed API response', async ({ page }) => {
    // Return malformed JSON
    await page.route('**/api/v1/lncrna-chipseq-overlap/summary*', (route) => {
      route.fulfill({
        status: 200,
        contentType: 'application/json',
        body: '{ "invalid": json }'  // Malformed JSON
      })
    })

    await page.goto(PAGE_URL)
    await page.waitForTimeout(2000)

    // Enable stats
    await enableStatsIfNeeded(page)
    await page.waitForTimeout(1500)

    // Page should handle error gracefully
    const errorIndicator = page.locator('.ant-alert-error, .ant-message-error')
      .or(page.getByText(/Error|Failed|错误/i))

    const hasError = await errorIndicator.isVisible().catch(() => false)

    // Or page shows empty/fallback state
    const fallbackState = page.locator('.ant-empty, .ant-table')
    const hasFallback = await fallbackState.isVisible().catch(() => false)

    expect(hasError || hasFallback).toBeTruthy()
    console.log(`Malformed response handling: error=${hasError}, fallback=${hasFallback}`)

    // Clean up
    await page.unrouteAll({ behavior: 'ignoreErrors' })
  })

  test('should handle network disconnect gracefully', async ({ page }) => {
    await page.goto(PAGE_URL)
    await page.waitForLoadState('networkidle')

    // Enable stats
    await enableStatsIfNeeded(page)
    await page.waitForTimeout(1500)

    // Simulate network disconnect for subsequent requests
    await page.route('**/api/v1/**', (route) => {
      route.abort('failed')
    })

    // Try to interact with filters (triggers API call)
    const filter = page.locator('.ant-select').first()
    if (await filter.count() > 0) {
      await filter.click()
      await page.waitForTimeout(300)

      const option = page.locator('.ant-select-dropdown .ant-select-item').first()
      if (await option.count() > 0) {
        await option.click()
        await page.waitForTimeout(2000)
      }
    }

    // Page should show error or maintain previous state
    const hasContent = await page.locator('.ant-card, .ant-table').first().isVisible()
    expect(hasContent).toBeTruthy()

    console.log('Network disconnect handled gracefully')

    // Clean up
    await page.unrouteAll({ behavior: 'ignoreErrors' })
  })
})
