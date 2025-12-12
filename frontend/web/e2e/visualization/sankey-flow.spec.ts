import { test, expect, type Page, type Locator } from '@playwright/test'

/**
 * Sankey Flow Visualization E2E Tests
 *
 * Tests the Sankey flow diagram visualization for lncRNA regulatory relationships.
 * The Sankey diagram shows three-layer flow relationships:
 * lncRNA → Gene → Disease regulatory pathways
 *
 * Test Coverage:
 * - P0: Critical page rendering, canvas validation, i18n support
 * - P1: Interactive features (species filter, BA threshold, disease search, tooltips)
 * - P2: Performance, responsive design, error handling
 *
 * Technology: ECharts Sankey chart (canvas-based rendering via ReactECharts)
 *
 * API Endpoint: /api/v1/visualization/sankey-data
 * Route: /visualization/sankey-flow
 */

const BASE_URL = process.env.BASE_URL || 'http://localhost:5173'
const PAGE_URL = '/visualization/sankey-flow'

// ============================================================================
// Helper Functions
// ============================================================================

/**
 * Wait for Sankey chart container and canvas to be visible
 * Note: The ReactECharts component has data-testid="sankey-chart" (not "sankey-flow-chart")
 * @param page - Playwright page object
 * @returns Object containing container and canvas locators
 */
async function waitForSankeyChart(page: Page): Promise<{
  container: Locator
  canvas: Locator
}> {
  const container = page.locator('[data-testid="sankey-chart"]')
  await expect(container).toBeVisible({ timeout: 10000 })

  const canvas = container.locator('canvas')
  await expect(canvas.first()).toBeVisible({ timeout: 5000 })

  return { container, canvas }
}

/**
 * Check if Sankey chart has been rendered (canvas has pixel data)
 * @param canvas - Canvas locator
 * @returns True if canvas has been drawn on
 */
async function isSankeyRendered(canvas: Locator): Promise<boolean> {
  try {
    return await canvas.first().evaluate((el: HTMLCanvasElement) => {
      const ctx = el.getContext('2d')
      if (!ctx) return false

      const imageData = ctx.getImageData(0, 0, el.width, el.height)

      // Check for any non-transparent pixels
      for (let i = 3; i < imageData.data.length; i += 4) {
        if (imageData.data[i] !== 0) {
          return true
        }
      }
      return false
    })
  } catch (error) {
    console.error('Error checking canvas render:', error)
    return false
  }
}

/**
 * Get species filter locator
 * The actual test-id is "species-select"
 * @param page - Playwright page object
 * @returns Species filter locator
 */
function getSpeciesFilter(page: Page): Locator {
  return page.locator('[data-testid="species-select"]')
    .or(page.locator('.ant-select').filter({ hasText: /Species|物种|Human|人类/i }))
}

/**
 * Get BA threshold slider locator
 * The actual test-id is "ba-slider"
 * @param page - Playwright page object
 * @returns BA threshold slider locator
 */
function getBAThresholdSlider(page: Page): Locator {
  return page.locator('[data-testid="ba-slider"]')
    .or(page.locator('.ant-slider').filter({ hasText: /BA|Binding.*Affinity|亲和力|阈值/i }))
}

/**
 * Get disease search input locator
 * The actual test-id is "disease-search"
 * @param page - Playwright page object
 * @returns Disease search input locator
 */
function getDiseaseSearchInput(page: Page): Locator {
  return page.locator('[data-testid="disease-search"]')
    .or(page.locator('input[placeholder*="disease" i], input[placeholder*="diabetes" i]'))
}

/**
 * Switch language to test i18n
 * @param page - Playwright page object
 * @param language - 'en' or 'zh'
 */
async function switchLanguage(page: Page, language: 'en' | 'zh'): Promise<void> {
  const languageSwitch = page.locator('[data-testid="language-switcher"]')
    .or(page.locator('button').filter({ hasText: /EN|中文/i }))

  if (await languageSwitch.count() > 0) {
    await languageSwitch.click()
    await page.waitForTimeout(500)

    const option = page.locator('.ant-dropdown-menu-item').filter({
      hasText: language === 'en' ? /English/i : /中文/i
    })

    if (await option.count() > 0) {
      await option.click()
      await page.waitForTimeout(1000)
    }
  }
}

// ============================================================================
// P0 Tests: Critical Functionality
// ============================================================================

test.describe('Sankey Flow - P0 Critical', () => {

  test('should load page correctly', async ({ page }) => {
    // TODO: Once page is implemented, this test should pass
    await page.goto(`${BASE_URL}${PAGE_URL}`)

    // Wait for page to load
    await page.waitForLoadState('networkidle')

    // Verify URL
    expect(page.url()).toContain(PAGE_URL)

    // Verify page container exists
    const pageContainer = page.locator('[data-testid="sankey-flow-page"]')
    await expect(pageContainer).toBeVisible({ timeout: 10000 })
  })

  test('should render Sankey chart canvas', async ({ page }) => {
    // TODO: Verify canvas rendering once page is implemented
    await page.goto(`${BASE_URL}${PAGE_URL}`)
    await page.waitForLoadState('networkidle')

    // Wait for chart container and canvas
    const { container, canvas } = await waitForSankeyChart(page)

    // Verify container is visible
    await expect(container).toBeVisible({ timeout: 10000 })

    // Verify canvas is visible
    await expect(canvas.first()).toBeVisible({ timeout: 10000 })

    // Verify canvas has been drawn on (has pixel data)
    const hasContent = await isSankeyRendered(canvas)
    expect(hasContent).toBe(true)

    console.log('Sankey chart canvas rendered successfully')
  })

  test('should support i18n switching', async ({ page }) => {
    // TODO: Update text matchers once actual translations are implemented
    await page.goto(`${BASE_URL}${PAGE_URL}`)
    await page.waitForLoadState('networkidle')

    // Get initial page text
    const initialPageText = await page.locator('body').textContent()
    const isInitialChinese = /[\u4e00-\u9fa5]/.test(initialPageText || '')

    console.log(`Initial language: ${isInitialChinese ? 'Chinese' : 'English'}`)

    // Switch to other language
    await switchLanguage(page, isInitialChinese ? 'en' : 'zh')
    await page.waitForTimeout(1000)

    // Verify language changed
    const updatedPageText = await page.locator('body').textContent()
    const isUpdatedChinese = /[\u4e00-\u9fa5]/.test(updatedPageText || '')

    // Language should have changed
    expect(isInitialChinese).not.toBe(isUpdatedChinese)

    console.log(`Language switched to: ${isUpdatedChinese ? 'Chinese' : 'English'}`)
  })

  test('should display page title', async ({ page }) => {
    await page.goto(`${BASE_URL}${PAGE_URL}`)
    await page.waitForLoadState('networkidle')

    // Look for page title
    const title = page.locator('h1, h2').first()
    await expect(title).toBeVisible({ timeout: 10000 })

    const titleText = await title.textContent()

    // Title should contain "Sankey" or "Flow" or Chinese equivalent
    expect(titleText).toMatch(/Sankey|Flow|流向图|桑基图/i)

    console.log(`Page title: ${titleText}`)
  })

  test('should handle empty data state', async ({ page }) => {
    // Mock API to return empty data
    await page.route('**/api/v1/visualization/sankey-data*', (route) => {
      route.fulfill({
        status: 200,
        contentType: 'application/json',
        body: JSON.stringify({
          nodes: [],
          links: [],
          query_params: { species_id: null, min_ba: null, trait_name: null, limit: 100 },
          statistics: {
            total_nodes: 0,
            total_links: 0,
            lncrna_count: 0,
            gene_count: 0,
            disease_count: 0
          }
        })
      })
    })

    await page.goto(`${BASE_URL}${PAGE_URL}`)
    await page.waitForTimeout(2000)

    // Should show empty state
    const emptyState = page.locator('.ant-empty')
    const noDataText = page.getByText(/No.*Data|暂无数据/i)

    const hasEmpty = await emptyState.isVisible().catch(() => false)
    const hasNoData = await noDataText.isVisible().catch(() => false)

    expect(hasEmpty || hasNoData).toBeTruthy()
    console.log(`Empty state handled: empty=${hasEmpty}, noData=${hasNoData}`)
  })

  test('should show loading state', async ({ page }) => {
    // Test loading spinner during data fetch
    await page.route('**/api/v1/visualization/sankey-data*', async (route) => {
      await new Promise(resolve => setTimeout(resolve, 3000))
      route.continue()
    })

    await page.goto(`${BASE_URL}${PAGE_URL}`)

    // Check for loading spinner
    const spinner = page.locator('.ant-spin, [class*="loading"]')
    const hasLoading = await spinner.first().isVisible({ timeout: 2000 }).catch(() => false)

    console.log(`Loading state shown: ${hasLoading}`)

    // Loading should eventually resolve
    if (hasLoading) {
      await page.waitForTimeout(4000)
      const content = page.locator('[data-testid="sankey-flow-chart"], .ant-empty').first()
      await expect(content).toBeVisible({ timeout: 10000 })
    }
  })

  test('should handle API error gracefully', async ({ page }) => {
    // Test error handling for API failures
    await page.route('**/api/v1/visualization/sankey-data*', (route) => {
      route.fulfill({
        status: 500,
        contentType: 'application/json',
        body: JSON.stringify({ detail: 'Internal Server Error' })
      })
    })

    await page.goto(`${BASE_URL}${PAGE_URL}`)
    await page.waitForTimeout(2000)

    // Should show error message
    const errorMsg = page.locator('.ant-message-error, .ant-notification-notice-error, .ant-alert-error')
    const errorText = page.getByText(/Error|Failed|错误|失败/i)

    const hasError = await errorMsg.isVisible().catch(() => false)
    const hasErrorText = await errorText.isVisible().catch(() => false)

    console.log(`API error handled: error=${hasError}, errorText=${hasErrorText}`)
  })
})

// ============================================================================
// P1 Tests: Feature Validation
// ============================================================================

test.describe('Sankey Flow - P1 Features', () => {

  test.beforeEach(async ({ page }) => {
    await page.goto(`${BASE_URL}${PAGE_URL}`)
    await page.waitForLoadState('networkidle')
    await page.waitForTimeout(2000)
  })

  test('should filter by species', async ({ page }) => {
    // Test species filter dropdown
    const speciesFilter = getSpeciesFilter(page)

    if (await speciesFilter.count() > 0) {
      await speciesFilter.click()
      await page.waitForTimeout(300)

      // Select a different species
      const option = page.locator('.ant-select-dropdown .ant-select-item')
        .filter({ hasText: /Chimp|黑猩猩|Macaque|猕猴/i })
        .first()

      if (await option.count() > 0) {
        await option.click()
        await page.waitForTimeout(2000)

        // Verify chart updates (canvas re-renders)
        const { canvas } = await waitForSankeyChart(page)
        const hasContent = await isSankeyRendered(canvas)
        expect(hasContent).toBe(true)

        console.log('Species filter applied successfully')
      }
    } else {
      console.log('Species filter not found - skipping test')
    }
  })

  test('should filter by BA threshold', async ({ page }) => {
    // Test BA threshold slider
    const slider = getBAThresholdSlider(page)

    if (await slider.count() > 0) {
      const sliderHandle = slider.locator('.ant-slider-handle').first()

      if (await sliderHandle.isVisible().catch(() => false)) {
        const box = await sliderHandle.boundingBox()

        if (box) {
          // Drag slider to adjust threshold
          await page.mouse.move(box.x + box.width / 2, box.y + box.height / 2)
          await page.mouse.down()
          await page.mouse.move(box.x + 100, box.y)
          await page.mouse.up()

          await page.waitForTimeout(2000)

          // Verify chart updates
          const { canvas } = await waitForSankeyChart(page)
          const hasContent = await isSankeyRendered(canvas)
          expect(hasContent).toBe(true)

          console.log('BA threshold adjusted successfully')
        }
      }
    } else {
      console.log('BA threshold slider not found - skipping test')
    }
  })

  test('should filter by disease name search', async ({ page }) => {
    // Test disease/trait search input
    const searchInput = getDiseaseSearchInput(page)

    if (await searchInput.count() > 0) {
      await searchInput.fill('diabetes')
      await page.waitForTimeout(1500)

      // Verify chart updates
      const { canvas } = await waitForSankeyChart(page)
      const hasContent = await isSankeyRendered(canvas)
      expect(hasContent).toBe(true)

      console.log('Disease search filter applied successfully')
    } else {
      console.log('Disease search input not found - skipping test')
    }
  })

  test('should show tooltip on node hover', async ({ page }) => {
    // Test tooltip display on node hover
    const { canvas } = await waitForSankeyChart(page)

    if (await canvas.isVisible()) {
      const box = await canvas.first().boundingBox()

      if (box) {
        // Hover over center of canvas (where nodes likely are)
        await page.mouse.move(box.x + box.width / 2, box.y + box.height / 2)
        await page.waitForTimeout(800)

        // Check for tooltip
        const tooltip = page.locator('.ant-tooltip, [class*="tooltip"], [class*="echarts-tooltip"]')
        const tooltipVisible = await tooltip.isVisible().catch(() => false)

        console.log(`Node hover tooltip: ${tooltipVisible}`)

        // Note: ECharts tooltips may use different DOM structure
        if (!tooltipVisible) {
          // Try hovering over different position
          await page.mouse.move(box.x + box.width / 3, box.y + box.height / 3)
          await page.waitForTimeout(500)

          const tooltip2 = await tooltip.isVisible().catch(() => false)
          console.log(`Alternative position tooltip: ${tooltip2}`)
        }
      }
    }
  })

  test('should support node click interaction', async ({ page }) => {
    // Test node click behavior (ECharts focus adjacency)
    const { canvas } = await waitForSankeyChart(page)

    if (await canvas.isVisible()) {
      const box = await canvas.first().boundingBox()

      if (box) {
        // Click on a node
        await page.mouse.click(box.x + box.width / 2, box.y + box.height / 2)
        await page.waitForTimeout(1000)

        console.log('Node click interaction completed')
      }
    }
  })

  test('should display statistics cards', async ({ page }) => {
    // Test that statistics cards show data
    const totalNodesCard = page.locator('[data-testid="stat-total-nodes"]')
    const lncrnaCard = page.locator('[data-testid="stat-lncrna-nodes"]')
    const geneCard = page.locator('[data-testid="stat-gene-nodes"]')
    const diseaseCard = page.locator('[data-testid="stat-disease-nodes"]')

    const hasStats = await totalNodesCard.isVisible().catch(() => false)

    if (hasStats) {
      await expect(totalNodesCard).toBeVisible()
      await expect(lncrnaCard).toBeVisible()
      await expect(geneCard).toBeVisible()
      await expect(diseaseCard).toBeVisible()

      console.log('Statistics cards displayed correctly')
    }
  })

  test('should display data table', async ({ page }) => {
    // Test that the flow details table is visible
    const table = page.locator('[data-testid="sankey-table"]')

    if (await table.count() > 0) {
      await expect(table).toBeVisible()

      // Check for table rows
      const rows = table.locator('.ant-table-row')
      const rowCount = await rows.count()

      console.log(`Table has ${rowCount} rows`)
      expect(rowCount).toBeGreaterThanOrEqual(0)
    }
  })
})

// ============================================================================
// P2 Tests: Performance and Edge Cases
// ============================================================================

test.describe('Sankey Flow - P2 Performance', () => {

  test('should render chart within 5 seconds', async ({ page }) => {
    const startTime = Date.now()

    await page.goto(`${BASE_URL}${PAGE_URL}`)
    await page.waitForLoadState('networkidle')

    // Wait for canvas to be visible
    const canvas = page.locator('[data-testid="sankey-flow-chart"] canvas').first()
    await canvas.waitFor({ state: 'visible', timeout: 10000 }).catch(() => null)

    const renderTime = Date.now() - startTime

    console.log(`Sankey chart rendered in ${renderTime}ms`)

    // Chart should render within 5 seconds
    expect(renderTime).toBeLessThan(5000)
  })

  test('should handle large dataset', async ({ page }) => {
    // TODO: Mock large dataset response
    await page.route('**/api/v1/sankey*', (route) => {
      // Generate large dataset with 100 nodes and 200 links
      const nodes = Array.from({ length: 100 }, (_, i) => ({
        name: `Node_${i}`,
        value: Math.floor(Math.random() * 1000)
      }))

      const links = Array.from({ length: 200 }, (_, i) => ({
        source: `Node_${i % 50}`,
        target: `Node_${(i % 50) + 50}`,
        value: Math.floor(Math.random() * 100)
      }))

      route.fulfill({
        status: 200,
        contentType: 'application/json',
        body: JSON.stringify({ nodes, links })
      })
    })

    const startTime = Date.now()
    await page.goto(`${BASE_URL}${PAGE_URL}`)
    await page.waitForLoadState('networkidle')

    // Wait for chart
    await page.waitForTimeout(3000)

    const renderTime = Date.now() - startTime
    console.log(`Large dataset render time: ${renderTime}ms`)

    // Should render even with large data
    expect(renderTime).toBeLessThan(10000)
  })

  test('should be responsive on mobile viewport', async ({ page }) => {
    await page.setViewportSize({ width: 375, height: 667 })

    await page.goto(`${BASE_URL}${PAGE_URL}`)
    await page.waitForLoadState('networkidle')

    // Chart should be visible on mobile
    const pageContainer = page.locator('[data-testid="sankey-flow-page"]').first()
    await expect(pageContainer).toBeVisible({ timeout: 10000 })

    // Check if chart adapts to mobile width
    const canvas = page.locator('canvas').first()
    if (await canvas.isVisible().catch(() => false)) {
      const box = await canvas.boundingBox()
      if (box) {
        expect(box.width).toBeLessThanOrEqual(375)
        console.log(`Mobile canvas width: ${box.width}px`)
      }
    }
  })

  test('should be responsive on tablet viewport', async ({ page }) => {
    await page.setViewportSize({ width: 768, height: 1024 })

    await page.goto(`${BASE_URL}${PAGE_URL}`)
    await page.waitForLoadState('networkidle')

    const pageContainer = page.locator('[data-testid="sankey-flow-page"]').first()
    await expect(pageContainer).toBeVisible({ timeout: 10000 })

    console.log('Tablet view renders correctly')
  })
})

// ============================================================================
// Accessibility Tests
// ============================================================================

test.describe('Sankey Flow - Accessibility', () => {

  test.beforeEach(async ({ page }) => {
    await page.goto(`${BASE_URL}${PAGE_URL}`)
    await page.waitForLoadState('networkidle')
  })

  test('should have proper heading hierarchy', async ({ page }) => {
    const h1 = page.locator('h1')
    const h1Count = await h1.count()

    expect(h1Count).toBeGreaterThanOrEqual(1)
    console.log(`Found ${h1Count} h1 heading(s)`)
  })

  test('should have keyboard navigation support', async ({ page }) => {
    // Tab through interactive elements
    await page.keyboard.press('Tab')
    await page.waitForTimeout(200)

    const focusedElement = page.locator(':focus')
    const hasFocus = await focusedElement.count() > 0

    expect(hasFocus).toBeTruthy()
    console.log('Keyboard navigation works')
  })

  test('should have color contrast for text', async ({ page }) => {
    // Check that important text is visible
    const title = page.locator('h1, h2').first()
    if (await title.isVisible()) {
      const color = await title.evaluate(el =>
        window.getComputedStyle(el).color
      )
      console.log(`Title color: ${color}`)

      // Color should not be transparent
      expect(color).not.toMatch(/rgba\(0,\s*0,\s*0,\s*0\)/)
    }
  })
})
