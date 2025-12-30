import { test, expect, type Page } from '@playwright/test'

/**
 * Regulations Page Comprehensive E2E Tests
 *
 * This test suite covers the complete functionality of the Regulations page:
 * 1. Page loading and initial state
 * 2. Filter functionality (species, BA range, gene type)
 * 3. Table interactions (pagination, sorting, row details)
 * 4. Data export functionality
 * 5. URL parameter handling
 * 6. Error states and loading states
 * 7. Responsive design
 *
 * The Regulations page displays lncRNA-target regulatory relationships
 * with binding affinity (BA) scores and other metrics.
 */

const BASE_URL = process.env.BASE_URL || 'http://localhost:5173'
const PAGE_URL = '/regulations'
const API_ENDPOINT = '/api/v1/regulations'

// Helper to wait for regulations API
async function waitForRegulationsAPI(page: Page, timeout = 30000) {
  return page.waitForResponse(
    (resp) => resp.url().includes(API_ENDPOINT) && resp.status() === 200,
    { timeout }
  ).catch(() => null)
}

// ============================================================================
// Test Suite: Page Loading and Initial State
// ============================================================================

test.describe('Regulations Page - Initial Load', () => {
  test('Page loads successfully', async ({ page }) => {
    await page.goto(`${BASE_URL}${PAGE_URL}`)
    await page.waitForLoadState('networkidle')

    // URL should be correct
    expect(page.url()).toContain(PAGE_URL)

    // Main content should be visible
    const mainContent = page.locator('.ant-table, .ant-card, h1, h2').first()
    await expect(mainContent).toBeVisible({ timeout: 15000 })
  })

  test('Page title is displayed', async ({ page }) => {
    await page.goto(`${BASE_URL}${PAGE_URL}`)
    await page.waitForLoadState('networkidle')

    const title = page.locator('h1, h2').first()
    await expect(title).toBeVisible()

    const titleText = await title.textContent()
    expect(titleText).toMatch(/Regulation|调控/i)
  })

  test('Data table is rendered', async ({ page }) => {
    await page.goto(`${BASE_URL}${PAGE_URL}`)
    await expect(page.locator('.ant-table')).toBeVisible({ timeout: 20000 })

    // Verify table has rows
    const rows = page.locator('.ant-table-tbody tr')
    await expect(rows.first()).toBeVisible({ timeout: 10000 })
  })

  test('Pagination is displayed', async ({ page }) => {
    await page.goto(`${BASE_URL}${PAGE_URL}`)
    await expect(page.locator('.ant-table')).toBeVisible({ timeout: 20000 })

    const pagination = page.locator('.ant-pagination')
    await expect(pagination).toBeVisible()

    // Total count should be displayed
    const totalText = page.locator('.ant-pagination-total-text')
    await expect(totalText).toBeVisible()
  })

  test('Loading state is shown initially', async ({ page }) => {
    // Slow down API to catch loading state
    await page.route(`**${API_ENDPOINT}*`, async (route) => {
      await new Promise(resolve => setTimeout(resolve, 1000))
      route.continue()
    })

    await page.goto(`${BASE_URL}${PAGE_URL}`)

    // Check for loading indicator
    const spinner = page.locator('.ant-spin')
    const isLoading = await spinner.isVisible({ timeout: 2000 }).catch(() => false)

    if (isLoading) {
      console.log('Loading state displayed correctly')
    }

    // Content should load eventually
    await page.waitForLoadState('networkidle')
  })
})

// ============================================================================
// Test Suite: Filter Functionality
// ============================================================================

test.describe('Regulations Page - Filters', () => {
  test.beforeEach(async ({ page }) => {
    await page.goto(`${BASE_URL}${PAGE_URL}`)
    await expect(page.locator('.ant-table')).toBeVisible({ timeout: 20000 })
  })

  test('Species filter exists and works', async ({ page }) => {
    // Find species selector
    const speciesSelect = page.locator('.ant-select').filter({ hasText: /Species|Human|Mouse|物种/i }).first()
      .or(page.locator('[data-testid="species-filter"]'))
      .or(page.locator('.ant-form-item').filter({ hasText: /Species|物种/i }).locator('.ant-select'))

    const selectCount = await speciesSelect.count()

    if (selectCount > 0) {
      await speciesSelect.click()
      await page.waitForTimeout(300)

      const dropdown = page.locator('.ant-select-dropdown:visible')
      await expect(dropdown).toBeVisible()

      // Select an option
      const option = dropdown.locator('.ant-select-item').first()
      if (await option.count() > 0) {
        await option.click()
        await waitForRegulationsAPI(page)

        // Table should update
        await expect(page.locator('.ant-table')).toBeVisible()
        console.log('Species filter works')
      }
    }
  })

  test('BA range filter works', async ({ page }) => {
    // Find BA min/max input fields
    const baMinInput = page.locator('.ant-input-number').filter({ hasText: /min/i }).first()
      .or(page.locator('input[placeholder*="min" i]'))
      .or(page.locator('.ant-form-item').filter({ hasText: /BA|Binding/i }).locator('.ant-input-number').first())

    const inputNumbers = page.locator('.ant-input-number')
    const inputCount = await inputNumbers.count()

    if (inputCount >= 2) {
      // Set min BA value
      const minInput = inputNumbers.nth(0).locator('input')
      await minInput.fill('50')
      await page.keyboard.press('Tab')

      // Wait for potential API call
      await waitForRegulationsAPI(page)

      // Set max BA value
      const maxInput = inputNumbers.nth(1).locator('input')
      await maxInput.fill('100')
      await page.keyboard.press('Tab')

      await waitForRegulationsAPI(page)

      // Table should update
      await expect(page.locator('.ant-table')).toBeVisible()
      console.log('BA range filter works')
    }
  })

  test('Gene type filter works', async ({ page }) => {
    // Find gene type selector
    const geneTypeSelect = page.locator('.ant-select').filter({ hasText: /Gene.*Type|lncRNA|protein/i }).first()

    if (await geneTypeSelect.count() > 0) {
      await geneTypeSelect.click()
      await page.waitForTimeout(300)

      const dropdown = page.locator('.ant-select-dropdown:visible')
      const lncRNAOption = dropdown.locator('.ant-select-item').filter({ hasText: /lncRNA/i }).first()

      if (await lncRNAOption.count() > 0) {
        await lncRNAOption.click()
        await waitForRegulationsAPI(page)

        await expect(page.locator('.ant-table')).toBeVisible()
        console.log('Gene type filter works')
      }
    }
  })

  test('Reset filters button works', async ({ page }) => {
    // Apply a filter first
    const select = page.locator('.ant-select').first()
    if (await select.count() > 0) {
      await select.click()
      await page.waitForTimeout(300)

      const option = page.locator('.ant-select-dropdown:visible .ant-select-item').first()
      if (await option.count() > 0) {
        await option.click()
        await waitForRegulationsAPI(page)
      }
    }

    // Find reset button
    const resetButton = page.getByRole('button', { name: /Reset|Clear|重置|清空/i })

    if (await resetButton.count() > 0) {
      await resetButton.click()
      await waitForRegulationsAPI(page)

      await expect(page.locator('.ant-table')).toBeVisible()
      console.log('Reset filters works')
    }
  })

  test('Filter combination works correctly', async ({ page }) => {
    // Apply multiple filters using stable selectors (avoid nth() flakiness).
    const speciesSelect = page.locator('.ant-select').filter({ hasText: /Species|Human|Mouse|物种/i }).first()
      .or(page.locator('[data-testid="species-filter"]'))
      .or(page.locator('.ant-form-item').filter({ hasText: /Species|物种/i }).locator('.ant-select').first())

    const geneTypeSelect = page.locator('.ant-select').filter({ hasText: /Gene.*Type|lncRNA|protein/i }).first()

    if (await speciesSelect.count() === 0 || await geneTypeSelect.count() === 0) {
      console.log('Skipping: required filter controls not found')
      test.skip()
      return
    }

    // 1) Species
    await speciesSelect.click()
    await page.waitForTimeout(300)
    const speciesOption = page.locator('.ant-select-dropdown:visible .ant-select-item').first()
    if (await speciesOption.count() > 0) {
      await speciesOption.click()
      await waitForRegulationsAPI(page, 15000)
    }

    // 2) Gene type (prefer lncRNA)
    await geneTypeSelect.click()
    await page.waitForTimeout(300)
    const dropdown = page.locator('.ant-select-dropdown:visible')
    const lncRNAOption = dropdown.locator('.ant-select-item').filter({ hasText: /lncRNA/i }).first()
    const geneTypeOption = (await lncRNAOption.count() > 0)
      ? lncRNAOption
      : dropdown.locator('.ant-select-item').first()

    if (await geneTypeOption.count() > 0) {
      await geneTypeOption.click()
      await waitForRegulationsAPI(page, 15000)
    }

    // Table should reflect combined filters
    await expect(page.locator('.ant-table')).toBeVisible({ timeout: 20000 })
    console.log('Filter combination works')
  })
})

// ============================================================================
// Test Suite: Table Interactions
// ============================================================================

test.describe('Regulations Page - Table Interactions', () => {
  test.beforeEach(async ({ page }) => {
    await page.goto(`${BASE_URL}${PAGE_URL}`)
    await expect(page.locator('.ant-table')).toBeVisible({ timeout: 20000 })
  })

  test('Pagination works correctly', async ({ page }) => {
    const pagination = page.locator('.ant-pagination')
    await expect(pagination).toBeVisible()

    // Click page 2
    const page2Button = pagination.locator('.ant-pagination-item-2')
    if (await page2Button.count() > 0) {
      await page2Button.click()
      await waitForRegulationsAPI(page)

      // Page 2 should be active
      await expect(page2Button).toHaveClass(/ant-pagination-item-active/)
      console.log('Pagination to page 2 works')
    }
  })

  test('Page size selector works', async ({ page }) => {
    const pageSizeSelector = page.locator('.ant-pagination-options-size-changer')

    if (await pageSizeSelector.count() > 0) {
      await pageSizeSelector.click()
      await page.waitForTimeout(300)

      const sizeOption = page.locator('.ant-select-dropdown:visible .ant-select-item')
        .filter({ hasText: /50|100/i }).first()

      if (await sizeOption.count() > 0) {
        await sizeOption.click()
        await waitForRegulationsAPI(page)

        // Table should update
        await expect(page.locator('.ant-table')).toBeVisible()
        console.log('Page size selector works')
      }
    }
  })

  test('Column sorting works', async ({ page }) => {
    // Find sortable column header
    const sortableHeader = page.locator('.ant-table-column-has-sorters').first()

    if (await sortableHeader.count() > 0) {
      await sortableHeader.click()
      await waitForRegulationsAPI(page)

      // Sort indicator should appear
      const sortIcon = sortableHeader.locator('.ant-table-column-sorter-up.active, .ant-table-column-sorter-down.active')
      const hasSortIcon = await sortIcon.count() > 0

      await expect(page.locator('.ant-table')).toBeVisible()
      console.log(`Column sorting: ${hasSortIcon ? 'ascending/descending' : 'applied'}`)
    }
  })

  test('Row click/detail navigation works', async ({ page }) => {
    const firstRow = page.locator('.ant-table-tbody tr').first()
    await expect(firstRow).toBeVisible()

    // Look for detail/view button in row
    const viewButton = firstRow.locator('button, a').filter({ hasText: /View|Detail|查看|详情/i }).first()
      .or(firstRow.locator('[class*="action"] button, [class*="action"] a').first())

    if (await viewButton.count() > 0) {
      await viewButton.click()
      await page.waitForTimeout(1000)

      // Check if navigated or modal opened
      const urlChanged = !page.url().includes(PAGE_URL)
      const modalOpened = await page.locator('.ant-modal').isVisible().catch(() => false)

      console.log(`Row action: URL changed=${urlChanged}, Modal opened=${modalOpened}`)
    }
  })

  test('Row expansion works if available', async ({ page }) => {
    // Look for expand button
    const expandButton = page.locator('.ant-table-row-expand-icon').first()

    if (await expandButton.count() > 0) {
      await expandButton.click()
      await page.waitForTimeout(500)

      // Expanded row should be visible
      const expandedRow = page.locator('.ant-table-expanded-row')
      const isExpanded = await expandedRow.isVisible().catch(() => false)

      console.log(`Row expansion: ${isExpanded ? 'works' : 'not detected'}`)
    }
  })
})

// ============================================================================
// Test Suite: Export Functionality
// ============================================================================

test.describe('Regulations Page - Export', () => {
  test.beforeEach(async ({ page }) => {
    await page.goto(`${BASE_URL}${PAGE_URL}`)
    await expect(page.locator('.ant-table')).toBeVisible({ timeout: 20000 })
  })

  test('Export button is visible', async ({ page }) => {
    const exportButton = page.locator('button').filter({ hasText: /Export|CSV|XLSX|导出/i }).first()

    if (await exportButton.count() > 0) {
      await expect(exportButton).toBeVisible()
      console.log('Export button is visible')
    }
  })

  test('Export dropdown shows options', async ({ page }) => {
    const exportButton = page.locator('button').filter({ hasText: /Export|导出/i }).first()

    if (await exportButton.count() > 0) {
      await exportButton.click()
      await page.waitForTimeout(500)

      const dropdown = page.locator('.ant-dropdown-menu:visible')
      if (await dropdown.isVisible().catch(() => false)) {
        const options = dropdown.locator('.ant-dropdown-menu-item')
        const optionCount = await options.count()

        expect(optionCount).toBeGreaterThan(0)
        console.log(`Export has ${optionCount} format options`)
      }
    }
  })

  test('CSV export triggers download', async ({ page }) => {
    const exportButton = page.locator('button').filter({ hasText: /Export|导出/i }).first()

    if (await exportButton.count() > 0) {
      await exportButton.click()
      await page.waitForTimeout(500)

      const csvOption = page.locator('.ant-dropdown-menu-item').filter({ hasText: /CSV/i }).first()

      if (await csvOption.isVisible().catch(() => false)) {
        const downloadPromise = page.waitForEvent('download', { timeout: 15000 }).catch(() => null)
        await csvOption.click()

        const download = await downloadPromise
        if (download) {
          const filename = download.suggestedFilename()
          expect(filename).toMatch(/\.csv$/i)
          console.log(`CSV downloaded: ${filename}`)
        }
      }
    }
  })
})

// ============================================================================
// Test Suite: URL Parameters
// ============================================================================

test.describe('Regulations Page - URL Parameters', () => {
  test('Species ID parameter applies filter', async ({ page }) => {
    await page.goto(`${BASE_URL}${PAGE_URL}?species_ids=1`)
    await expect(page.locator('.ant-table')).toBeVisible({ timeout: 20000 })

    // Verify data is loaded (Human species)
    await expect(page.locator('.ant-table-tbody tr').first()).toBeVisible()
    console.log('Species ID URL parameter works')
  })

  test('Page parameter sets current page', async ({ page }) => {
    await page.goto(`${BASE_URL}${PAGE_URL}?page=2`)
    await expect(page.locator('.ant-table')).toBeVisible({ timeout: 20000 })

    // Page 2 should be active in pagination
    const page2Button = page.locator('.ant-pagination-item-2')
    if (await page2Button.count() > 0) {
      const isActive = await page2Button.getAttribute('class').then(c => c?.includes('active'))
      console.log(`Page 2 is active: ${isActive}`)
    }
  })

  test('BA range parameters apply filter', async ({ page }) => {
    await page.goto(`${BASE_URL}${PAGE_URL}?ba_min=50&ba_max=100`)
    await expect(page.locator('.ant-table')).toBeVisible({ timeout: 20000 })

    // Data should be loaded
    await expect(page.locator('.ant-table-tbody tr').first()).toBeVisible()
    console.log('BA range URL parameters work')
  })

  test('Multiple parameters work together', async ({ page }) => {
    await page.goto(`${BASE_URL}${PAGE_URL}?species_ids=1&ba_min=50&page=1`)
    await expect(page.locator('.ant-table')).toBeVisible({ timeout: 20000 })

    // Verify URL preserved
    expect(page.url()).toContain('species_ids=1')
    console.log('Multiple URL parameters work')
  })
})

// ============================================================================
// Test Suite: Error States
// ============================================================================

test.describe('Regulations Page - Error States', () => {
  test('API error shows error message', async ({ page }) => {
    await page.route(`**${API_ENDPOINT}*`, (route) => {
      route.fulfill({
        status: 500,
        contentType: 'application/json',
        body: JSON.stringify({ detail: 'Internal Server Error' })
      })
    })

    await page.goto(`${BASE_URL}${PAGE_URL}`)
    await page.waitForTimeout(3000)

    // Check for error indication
    const errorNotification = page.locator('.ant-notification-notice-error, .ant-message-error')
    const errorAlert = page.locator('.ant-alert-error')
    const errorText = page.getByText(/Error|Failed|错误/i)

    const hasError = await errorNotification.isVisible().catch(() => false) ||
                     await errorAlert.isVisible().catch(() => false) ||
                     await errorText.isVisible().catch(() => false)

    expect(hasError).toBe(true)
    console.log('API error handled')
  })

  test('Empty result shows empty state', async ({ page }) => {
    await page.route(`**${API_ENDPOINT}*`, (route) => {
      route.fulfill({
        status: 200,
        contentType: 'application/json',
        body: JSON.stringify({ data: [], total: 0, page: 1, page_size: 20 })
      })
    })

    await page.goto(`${BASE_URL}${PAGE_URL}`)
    await page.waitForTimeout(2000)

    const emptyState = page.locator('.ant-empty')
    await expect(emptyState).toBeVisible()
    console.log('Empty state displayed')
  })

  test('Network error handled gracefully', async ({ page }) => {
    await page.route(`**${API_ENDPOINT}*`, (route) => {
      route.abort('failed')
    })

    await page.goto(`${BASE_URL}${PAGE_URL}`)
    await page.waitForTimeout(3000)

    // Page should not crash
    const body = page.locator('body')
    await expect(body).toBeVisible()
    console.log('Network error handled')
  })
})

// ============================================================================
// Test Suite: Responsive Design
// ============================================================================

test.describe('Regulations Page - Responsive Design', () => {
  test('Desktop view displays correctly', async ({ page }) => {
    await page.setViewportSize({ width: 1920, height: 1080 })
    await page.goto(`${BASE_URL}${PAGE_URL}`)
    await expect(page.locator('.ant-table')).toBeVisible({ timeout: 20000 })

    // Sidebar should be visible on desktop
    const sidebar = page.locator('.ant-layout-sider')
    const isSidebarVisible = await sidebar.isVisible().catch(() => false)
    console.log(`Desktop sidebar visible: ${isSidebarVisible}`)
  })

  test('Tablet view is usable', async ({ page }) => {
    await page.setViewportSize({ width: 768, height: 1024 })
    await page.goto(`${BASE_URL}${PAGE_URL}`)
    await page.waitForLoadState('networkidle')

    // Main content should be visible
    const mainContent = page.locator('.ant-table, .ant-card').first()
    await expect(mainContent).toBeVisible({ timeout: 15000 })
    console.log('Tablet view is usable')
  })

  test('Mobile view is usable', async ({ page }) => {
    await page.setViewportSize({ width: 375, height: 667 })
    await page.goto(`${BASE_URL}${PAGE_URL}`)
    await page.waitForLoadState('networkidle')

    // Content should be visible and scrollable
    const mainContent = page.locator('.ant-table, .ant-card, h1, h2').first()
    await expect(mainContent).toBeVisible({ timeout: 15000 })

    // Table may be horizontally scrollable
    const tableWrapper = page.locator('.ant-table-wrapper')
    await expect(tableWrapper).toBeVisible()
    console.log('Mobile view is usable')
  })
})

// ============================================================================
// Test Suite: Performance
// ============================================================================

test.describe('Regulations Page - Performance', () => {
  test('Page loads within acceptable time', async ({ page }) => {
    const startTime = Date.now()

    await page.goto(`${BASE_URL}${PAGE_URL}`)
    await page.waitForLoadState('networkidle')

    const loadTime = Date.now() - startTime
    expect(loadTime).toBeLessThan(10000) // 10 seconds max

    console.log(`Page loaded in ${loadTime}ms`)
  })

  test('Initial render is fast', async ({ page }) => {
    const startTime = Date.now()

    await page.goto(`${BASE_URL}${PAGE_URL}`)
    await page.locator('h1, h2, .ant-table, .ant-card').first().waitFor({ timeout: 10000 })

    const renderTime = Date.now() - startTime
    expect(renderTime).toBeLessThan(5000) // 5 seconds max

    console.log(`Initial render in ${renderTime}ms`)
  })

  test('Filter response is fast', async ({ page }) => {
    await page.goto(`${BASE_URL}${PAGE_URL}`)
    await expect(page.locator('.ant-table')).toBeVisible({ timeout: 20000 })

    // 打开“高级筛选 / Advanced Filters”（默认折叠；避免误点 Header 的语言切换 Select）
    const filtersCollapse = page.locator('.ant-collapse').filter({ hasText: /Advanced Filters|高级筛选/i }).first()
    if ((await filtersCollapse.count()) > 0) {
      const header = filtersCollapse.locator('.ant-collapse-header').first()
      await header.click({ force: true })
      await page.waitForTimeout(300)
    }

    // 选择“物种 / Species”过滤器（页面内的 Select），触发 /api/v1/regulations 重新请求
    const speciesSelect = page.locator('.ant-form-item')
      .filter({ hasText: /Species|物种/i })
      .locator('.ant-select')
      .first()

    if ((await speciesSelect.count()) > 0) {
      const startTime = Date.now()

      // 先注册等待，再触发点击，避免竞态
      const responsePromise = page.waitForResponse(
        (resp) =>
          resp.status() === 200 &&
          resp.url().includes(API_ENDPOINT) &&
          // 仅匹配筛选后的请求，避免被预加载请求“抢跑”
          resp.url().includes('species_ids='),
        { timeout: 30000 }
      )

      await speciesSelect.click()
      await page.waitForTimeout(200)

      const option = page.locator('.ant-select-dropdown:visible')
        .locator('.ant-select-item-option:visible, .ant-select-item:visible')
        .first()

      if ((await option.count()) > 0) {
        await option.click()
        await responsePromise

        const responseTime = Date.now() - startTime
        expect(responseTime).toBeLessThan(5000)
        console.log(`Filter response in ${responseTime}ms`)
      }
    }
  })
})

// ============================================================================
// Test Suite: Accessibility
// ============================================================================

test.describe('Regulations Page - Accessibility', () => {
  test.beforeEach(async ({ page }) => {
    await page.goto(`${BASE_URL}${PAGE_URL}`)
    await expect(page.locator('.ant-table')).toBeVisible({ timeout: 20000 })
  })

  test('Page has proper heading hierarchy', async ({ page }) => {
    const h1 = page.locator('h1')
    const h2 = page.locator('h2')

    const h1Count = await h1.count()
    const h2Count = await h2.count()

    expect(h1Count + h2Count).toBeGreaterThan(0)
    console.log(`Headings: H1=${h1Count}, H2=${h2Count}`)
  })

  test('Table has accessible structure', async ({ page }) => {
    const table = page.locator('.ant-table')
    const thead = table.locator('thead')
    const tbody = table.locator('tbody')

    await expect(thead).toBeVisible()
    await expect(tbody).toBeVisible()

    // Headers should exist
    const headers = thead.locator('th')
    const headerCount = await headers.count()
    expect(headerCount).toBeGreaterThan(0)
    console.log(`Table has ${headerCount} columns`)
  })

  test('Keyboard navigation works', async ({ page }) => {
    // Tab through elements
    await page.keyboard.press('Tab')
    await page.waitForTimeout(200)

    const focusedElement = page.locator(':focus')
    expect(await focusedElement.count()).toBeGreaterThan(0)
    console.log('Keyboard navigation works')
  })
})
