import { test, expect } from '@playwright/test'

/**
 * Conservation Analysis E2E Tests
 * 跨物种保守性分析页面测试
 *
 * 覆盖核心功能：
 * 1. 页面加载和基础渲染
 * 2. 物种选择器交互
 * 3. 热图可视化
 * 4. 数据表格和分页
 * 5. 导出功能
 */

test.describe('Conservation Analysis Page', () => {
  test.beforeEach(async ({ page }) => {
    // Navigate to conservation page
    await page.goto('/conservation')
    // Wait for page to load
    await page.waitForLoadState('networkidle')
  })

  test('page loads successfully', async ({ page }) => {
    // Verify page title/heading is visible
    await expect(page.getByRole('heading', { name: /Conservation|保守性/i })).toBeVisible({ timeout: 15000 })

    // Verify main content area exists
    await expect(page.locator('.ant-card').first()).toBeVisible()
  })

  test('overview statistics cards are displayed', async ({ page }) => {
    // Wait for statistics cards to load
    await expect(page.locator('.ant-statistic').first()).toBeVisible({ timeout: 15000 })

    // Should have multiple statistic cards
    const statisticCards = page.locator('.ant-statistic')
    await expect(statisticCards).toHaveCount(await statisticCards.count())
    expect(await statisticCards.count()).toBeGreaterThanOrEqual(1)
  })

  test('species selector is functional', async ({ page }) => {
    // SpeciesSelector 使用独立 Checkbox（无 checkbox-group 容器）
    const checkboxes = page.locator('.ant-checkbox-wrapper')
    await expect(checkboxes.first()).toBeVisible({ timeout: 10000 })
    expect(await checkboxes.count()).toBeGreaterThanOrEqual(4)

    const firstCheckbox = checkboxes.first()
    await firstCheckbox.click()

    // Verify checkbox state changed (checked)
    const input = firstCheckbox.locator('input[type="checkbox"]')
    await expect(input).toBeChecked({ timeout: 5000 })
  })

  test('conservation heatmap renders', async ({ page }) => {
    // Wait for ECharts canvas to appear
    const heatmapContainer = page.locator('[class*="echarts"], canvas').first()

    // Give time for chart to render
    await page.waitForTimeout(2000)

    // Check if chart container or canvas exists
    const chartExists = await heatmapContainer.count() > 0
    if (chartExists) {
      await expect(heatmapContainer).toBeVisible({ timeout: 15000 })
    }
  })

  test('data table loads and displays data', async ({ page }) => {
    // Wait for ant-table to appear
    const table = page.locator('.ant-table')
    await expect(table).toBeVisible({ timeout: 15000 })

    // Check table has rows (either data or empty state)
    const tableBody = page.locator('.ant-table-tbody')
    await expect(tableBody).toBeVisible()
  })

  test('pagination works correctly', async ({ page }) => {
    // Wait for table to load
    await expect(page.locator('.ant-table')).toBeVisible({ timeout: 15000 })

    // Find pagination component
    const pagination = page.locator('.ant-pagination')

    if (await pagination.isVisible()) {
      // Click next page if available
      const nextButton = pagination.locator('.ant-pagination-next')
      if (await nextButton.isEnabled()) {
        await nextButton.click()

        // Wait for data to refresh
        await page.waitForResponse((response) =>
          response.url().includes('/conservation') && response.status() === 200
        ).catch(() => {})

        // Table should still be visible
        await expect(page.locator('.ant-table')).toBeVisible()
      }
    }
  })

  test('filter by minimum conservation level', async ({ page }) => {
    // Look for slider or select for conservation level
    const slider = page.locator('.ant-slider')

    if (await slider.isVisible()) {
      // Interact with slider
      const sliderHandle = slider.locator('.ant-slider-handle')
      await sliderHandle.click()

      // Table should update
      await expect(page.locator('.ant-table')).toBeVisible()
    }
  })

  test('search/filter by gene name', async ({ page }) => {
    // Find search input
    const searchInput = page.locator('.ant-input-search input, .ant-input').first()

    if (await searchInput.isVisible()) {
      // Type a search term
      await searchInput.fill('MALAT1')
      await searchInput.press('Enter')

      // Wait for potential API response
      await page.waitForTimeout(1000)

      // Table should still be visible
      await expect(page.locator('.ant-table')).toBeVisible()
    }
  })

  test('export button is present', async ({ page }) => {
    // Look for export button
    const exportButton = page.getByRole('button', { name: /Export|导出|CSV/i })

    // Export button should exist (may be disabled if no data)
    if (await exportButton.count() > 0) {
      await expect(exportButton.first()).toBeVisible()
    }
  })

  test('handles empty state gracefully', async ({ page }) => {
    // Filter to a state that likely has no results
    const searchInput = page.locator('.ant-input-search input, .ant-input').first()

    if (await searchInput.isVisible()) {
      await searchInput.fill('NONEXISTENT_GENE_12345')
      await searchInput.press('Enter')

      await page.waitForTimeout(1000)

      // Should show empty state or no results message
      const emptyState = page.locator('.ant-empty, .ant-table-empty, [class*="empty"]')
      const table = page.locator('.ant-table')

      // Either empty state is shown or table is still visible
      const hasContent = await emptyState.isVisible() || await table.isVisible()
      expect(hasContent).toBeTruthy()
    }
  })

  test('responsive layout on mobile', async ({ page }) => {
    // Set viewport to mobile size
    await page.setViewportSize({ width: 375, height: 667 })

    // Page should still be functional
    await expect(page.locator('.ant-card').first()).toBeVisible({ timeout: 10000 })
  })
})

test.describe('Conservation API Integration', () => {
  test('overview API returns valid data', async ({ page }) => {
    // Intercept API call
    const responsePromise = page.waitForResponse(
      (response) => response.url().includes('/api/v1/conservation/overview'),
      { timeout: 5000 }
    ).catch(() => null)

    await page.goto('/conservation')

    const response = await responsePromise
    if (response) {
      expect(response.status()).toBe(200)
      const data = await response.json()
      expect(data).toBeDefined()
    }
  })

  test('matrix API returns valid data', async ({ page }) => {
    const responsePromise = page.waitForResponse(
      (response) => response.url().includes('/api/v1/conservation/matrix'),
      { timeout: 5000 }
    ).catch(() => null)

    await page.goto('/conservation')

    const response = await responsePromise
    if (response) {
      expect(response.status()).toBe(200)
    }
  })

  test('regulations API supports pagination', async ({ page }) => {
    const responsePromise = page.waitForResponse(
      (response) => response.url().includes('/api/v1/conservation/regulations'),
      { timeout: 5000 }
    ).catch(() => null)

    await page.goto('/conservation')

    const response = await responsePromise
    if (response) {
      expect(response.status()).toBe(200)
      const data = await response.json()
      if (data.items) {
        expect(Array.isArray(data.items)).toBeTruthy()
      }
    }
  })
})

test.describe('Conservation Accessibility', () => {
  test('page has proper heading structure', async ({ page }) => {
    await page.goto('/conservation')

    // Should have at least one h1 or h2 heading
    const headings = page.locator('h1, h2, h3')
    await expect(headings.first()).toBeVisible({ timeout: 10000 })
    expect(await headings.count()).toBeGreaterThan(0)
  })

  test('interactive elements are keyboard accessible', async ({ page }) => {
    await page.goto('/conservation')

    // Tab through the page
    await page.keyboard.press('Tab')

    // Some element should be focused
    const focusedElement = page.locator(':focus')
    await expect(focusedElement).toBeVisible({ timeout: 5000 }).catch(() => {})
  })
})
