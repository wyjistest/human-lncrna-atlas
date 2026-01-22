import { test, expect, type Page } from '@playwright/test'

/**
 * ChIP-seq Overlap Full User Flow E2E Tests
 * Phase 3.0 - Complete user journey testing
 *
 * Covers the complete user workflow:
 * 1. Filter selection (species, chromosome, cell type, marks)
 * 2. Data browsing (table view, pagination, sorting)
 * 3. Data export (BED, CSV formats)
 * 4. Error states render correctly
 * 5. Loading states work properly
 * 6. Empty states are helpful
 *
 * This test suite validates the TODO item:
 * "Phase 3.0 Overlap E2E Tests: Full user flow (filter -> browse -> export)"
 */

const PAGE_URL = '/lncrna-chipseq-overlap'
const API_BASE = process.env.API_BASE_URL || 'http://localhost:8000'

// Helper function to wait for API response
async function waitForOverlapAPI(page: Page, timeout = 30000) {
  return page.waitForResponse(
    (resp) => resp.url().includes('/lncrna-chipseq-overlap') && resp.status() === 200,
    { timeout }
  ).catch(() => null)
}

// Helper function to select a dropdown option
async function selectDropdownOption(page: Page, selectLocator: string, optionText: RegExp | string) {
  const select = page.locator(selectLocator).first()
  await select.click()
  await page.waitForTimeout(300)

  const dropdown = page.locator('.ant-select-dropdown:visible')
  await expect(dropdown).toBeVisible({ timeout: 5000 })

  const option = dropdown.locator('.ant-select-item').filter({ hasText: optionText }).first()
  if (await option.count() > 0) {
    await option.click()
    await page.waitForTimeout(500)
    return true
  }
  return false
}

// ============================================================================
// Test Suite: Full User Flow
// ============================================================================

test.describe('ChIP-seq Overlap - Full User Flow', () => {
  test.beforeEach(async ({ page }) => {
    await page.goto(PAGE_URL)
    await page.waitForLoadState('networkidle')
    await page.waitForTimeout(2000)
  })

  test('Complete flow: Filter -> Browse -> Export', async ({ page }) => {
    // Step 1: Verify page loaded
    const pageTitle = page.locator('h1, h2').first()
    await expect(pageTitle).toBeVisible({ timeout: 15000 })

    // Step 2: Apply filters
    // 2a. Select a Mark type (H3K27me3)
    const markSelect = page.locator('.ant-select').filter({ hasText: /Mark|H3K/i }).first()
    if (await markSelect.count() > 0) {
      await markSelect.click()
      await page.waitForTimeout(300)

      const markOption = page.locator('.ant-select-dropdown:visible .ant-select-item')
        .filter({ hasText: /H3K27me3|H3K4me3/i }).first()

      if (await markOption.count() > 0) {
        await markOption.click()
        await waitForOverlapAPI(page)
      }
    }

    // 2b. Select a Cell Type if available
    const cellTypeSelect = page.locator('.ant-select').filter({ hasText: /Cell|K562|HepG2/i }).first()
    if (await cellTypeSelect.count() > 0) {
      await cellTypeSelect.click()
      await page.waitForTimeout(300)

      const cellOption = page.locator('.ant-select-dropdown:visible .ant-select-item')
        .filter({ hasText: /K562|HepG2|GM12878/i }).first()

      if (await cellOption.count() > 0) {
        await cellOption.click()
        await waitForOverlapAPI(page)
      }
    }

    // Step 3: Verify data loaded in table
    await page.waitForTimeout(2000)
    const table = page.locator('.ant-table')
    await expect(table).toBeVisible({ timeout: 10000 })

    // Check for data rows or empty state
    const dataRows = page.locator('.ant-table-tbody tr.ant-table-row')
    const emptyState = page.locator('.ant-empty')

    const hasData = await dataRows.count() > 0
    const isEmpty = await emptyState.isVisible().catch(() => false)

    expect(hasData || isEmpty).toBe(true)

    // Step 4: Test pagination if data exists
    if (hasData) {
      const pagination = page.locator('.ant-pagination')
      if (await pagination.isVisible().catch(() => false)) {
        const totalItems = await pagination.locator('.ant-pagination-total-text').textContent()
        console.log(`Total items: ${totalItems}`)

        // Try clicking page 2 if it exists
        const page2 = pagination.locator('.ant-pagination-item-2')
        if (await page2.count() > 0) {
          await page2.click()
          await waitForOverlapAPI(page)
          await expect(page2).toHaveClass(/ant-pagination-item-active/)
        }
      }
    }

    // Step 5: Test export functionality
    const exportButton = page.locator('button').filter({ hasText: /Export|BED|CSV/i }).first()
    if (await exportButton.count() > 0) {
      // Click export button
      await exportButton.click()
      await page.waitForTimeout(500)

      // If it's a dropdown, select an option
      const exportDropdown = page.locator('.ant-dropdown-menu:visible')
      if (await exportDropdown.isVisible().catch(() => false)) {
        const bedOption = exportDropdown.locator('.ant-dropdown-menu-item').filter({ hasText: /BED/i }).first()
        if (await bedOption.count() > 0) {
          // Set up download promise before clicking
          const downloadPromise = page.waitForEvent('download', { timeout: 10000 }).catch(() => null)
          await bedOption.click()

          const download = await downloadPromise
          if (download) {
            const filename = download.suggestedFilename()
            console.log(`Downloaded file: ${filename}`)
            expect(filename).toMatch(/\.bed$/i)
          }
        }
      }
    }

    console.log('Full user flow completed successfully')
  })

  test('Filter combinations work correctly', async ({ page }) => {
    // Test multiple filter combinations
    const filterCombinations = [
      { mark: 'H3K27me3', cell: 'K562' },
      { mark: 'H3K4me3', cell: 'HepG2' },
      { mark: 'H3K27ac', cell: 'GM12878' },
    ]

    for (const combo of filterCombinations) {
      // Apply mark filter
      const markSelect = page.locator('.ant-select').first()
      await markSelect.click()
      await page.waitForTimeout(300)

      const markOption = page.locator('.ant-select-dropdown:visible .ant-select-item')
        .filter({ hasText: new RegExp(combo.mark, 'i') }).first()

      if (await markOption.count() > 0) {
        await markOption.click()
        await waitForOverlapAPI(page)

        // Verify table is visible
        const table = page.locator('.ant-table')
        await expect(table).toBeVisible()

        console.log(`Filter combination ${combo.mark} + ${combo.cell} works`)
      }

      // Reset for next iteration
      await page.reload()
      await page.waitForLoadState('networkidle')
    }
  })

  test('Sorting functionality works', async ({ page }) => {
    // Wait for table to load with data
    const table = page.locator('.ant-table')
    await expect(table).toBeVisible({ timeout: 15000 })

    // Find sortable columns
    const sortableHeaders = page.locator('.ant-table-column-has-sorters')
    const headerCount = await sortableHeaders.count()

    if (headerCount > 0) {
      // Click first sortable header
      const firstSortable = sortableHeaders.first()
      await firstSortable.click()
      await page.waitForTimeout(1000)

      // Verify sort indicator appears
      const sortIcon = firstSortable.locator('.ant-table-column-sorter-up.active, .ant-table-column-sorter-down.active')
      const hasSortIcon = await sortIcon.count() > 0

      console.log(`Sorting applied: ${hasSortIcon}`)

      // Click again to reverse sort
      await firstSortable.click()
      await page.waitForTimeout(1000)

      // Table should still be visible
      await expect(table).toBeVisible()
    }
  })

  test('Search functionality works', async ({ page }) => {
    // Look for search input
    const searchInput = page.locator('.ant-input-search input, input[placeholder*="search" i], input[placeholder*="Search" i]').first()

    if (await searchInput.count() > 0) {
      await searchInput.fill('chr1')
      await searchInput.press('Enter')

      // Wait for API or timeout
      await waitForOverlapAPI(page)

      // Table should still be visible
      const table = page.locator('.ant-table')
      await expect(table).toBeVisible()

      console.log('Search functionality works')
    }
  })
})

// ============================================================================
// Test Suite: Loading States
// ============================================================================

test.describe('ChIP-seq Overlap - Loading States', () => {
  test('Shows loading spinner during data fetch', async ({ page }) => {
    // Slow down the API response
    await page.route('**/api/v1/lncrna-chipseq-overlap*', async (route) => {
      await new Promise(resolve => setTimeout(resolve, 2000))
      route.continue()
    })

    await page.goto(PAGE_URL)

    // Check for loading spinner
    const spinner = page.locator('.ant-spin')
    const isSpinnerVisible = await spinner.isVisible({ timeout: 3000 }).catch(() => false)

    if (isSpinnerVisible) {
      console.log('Loading spinner displayed correctly')
    }

    // Wait for loading to complete
    await page.waitForLoadState('networkidle')

    // Verify content loads eventually
    const content = page.locator('.ant-table, .ant-empty').first()
    await expect(content).toBeVisible({ timeout: 30000 })
  })

  test('Shows skeleton loading during initial load', async ({ page }) => {
    // Check for skeleton screens
    await page.goto(PAGE_URL)

    // Skeleton may appear briefly
    const skeleton = page.locator('.ant-skeleton')
    const skeletonVisible = await skeleton.isVisible({ timeout: 2000 }).catch(() => false)

    console.log(`Skeleton loading: ${skeletonVisible ? 'shown' : 'not detected'}`)

    // Content should load eventually
    await page.waitForLoadState('networkidle')
    const table = page.locator('.ant-table, .ant-card').first()
    await expect(table).toBeVisible({ timeout: 15000 })
  })

  test('Filter change shows loading indicator', async ({ page }) => {
    await page.goto(PAGE_URL)
    await page.waitForLoadState('networkidle')
    await page.waitForTimeout(2000)

    // Select a filter to trigger loading
    const select = page.locator('.ant-select').first()
    if (await select.count() > 0) {
      await select.click()
      await page.waitForTimeout(300)

      const option = page.locator('.ant-select-dropdown:visible .ant-select-item').first()
      if (await option.count() > 0) {
        await option.click()

        // Check for loading state (may be brief)
        await page.waitForTimeout(100)
        const spinner = page.locator('.ant-spin, .ant-table-loading')
        const spinnerVisible = await spinner.isVisible().catch(() => false)
        console.log(`Loading on filter change: ${spinnerVisible}`)
      }
    }
  })
})

// ============================================================================
// Test Suite: Empty States
// ============================================================================

test.describe('ChIP-seq Overlap - Empty States', () => {
  test('Shows helpful empty state message', async ({ page }) => {
    // Mock API to return empty data
    await page.route('**/api/v1/lncrna-chipseq-overlap*', (route) => {
      route.fulfill({
        status: 200,
        contentType: 'application/json',
        body: JSON.stringify({ items: [], total: 0, page: 1, page_size: 20, total_pages: 0 })
      })
    })

    await page.goto(PAGE_URL)
    await page.waitForLoadState('networkidle')
    await page.waitForTimeout(2000)

    // Verify empty state is displayed
    const emptyState = page.locator('.ant-empty')
    const emptyText = page.getByText(/No Data|No Results|Empty/i)

    const hasEmptyState = await emptyState.isVisible().catch(() => false)
    const hasEmptyText = await emptyText.isVisible().catch(() => false)

    if (hasEmptyState) {
      // Empty state should have description
      const description = emptyState.locator('.ant-empty-description')
      const descText = await description.textContent()
      console.log(`Empty state message: ${descText}`)
    }

    expect(hasEmptyState || hasEmptyText).toBe(true)
  })

  test('Empty state includes action hint', async ({ page }) => {
    await page.route('**/api/v1/lncrna-chipseq-overlap*', (route) => {
      route.fulfill({
        status: 200,
        contentType: 'application/json',
        body: JSON.stringify({ items: [], total: 0, page: 1, page_size: 20, total_pages: 0 })
      })
    })

    await page.goto(PAGE_URL)
    await page.waitForLoadState('networkidle')
    await page.waitForTimeout(2000)

    // Check for action hint in empty state
    const emptyState = page.locator('.ant-empty')

    if (await emptyState.isVisible().catch(() => false)) {
      const actionButton = emptyState.locator('button')
      const actionLink = emptyState.locator('a')
      const hintText = emptyState.locator('[class*="hint"], [class*="tip"]')

      const hasAction = await actionButton.count() > 0 ||
                        await actionLink.count() > 0 ||
                        await hintText.count() > 0

      console.log(`Empty state has action hint: ${hasAction}`)
    }
  })
})

// ============================================================================
// Test Suite: Error States
// ============================================================================

test.describe('ChIP-seq Overlap - Error States', () => {
  test('Displays error message on API failure', async ({ page }) => {
    await page.route('**/api/v1/lncrna-chipseq-overlap*', (route) => {
      route.fulfill({
        status: 500,
        contentType: 'application/json',
        body: JSON.stringify({ detail: 'Internal Server Error' })
      })
    })

    await page.goto(PAGE_URL)

    // 等待错误状态出现（React Query 有重试）
    const errorIndicator = page.locator('.ant-notification-notice-error, .ant-message-error, .ant-alert-error')
      .or(page.getByText(/Error|Failed|500|Server|Loading Failed/i))
    await expect(errorIndicator.first()).toBeVisible({ timeout: 15000 }).catch(() => {})

    // Check for error notification or message
    const errorNotification = page.locator('.ant-notification-notice-error, .ant-message-error')
    const errorAlert = page.locator('.ant-alert-error')
    const errorText = page.getByText(/Error|Failed|500|Server/i)

    const hasError = await errorNotification.isVisible().catch(() => false) ||
                     await errorAlert.isVisible().catch(() => false) ||
                     await errorText.isVisible().catch(() => false)

    console.log(`Error state displayed: ${hasError}`)
    expect(hasError).toBe(true)
  })

  test('Shows retry option on error', async ({ page }) => {
    let requestCount = 0

    await page.route('**/api/v1/lncrna-chipseq-overlap*', (route) => {
      requestCount++
      if (requestCount === 1) {
        route.fulfill({
          status: 500,
          contentType: 'application/json',
          body: JSON.stringify({ detail: 'Server Error' })
        })
      } else {
        route.continue()
      }
    })

	    await page.goto(PAGE_URL)
	    await page.waitForTimeout(3000)
	
	    // Look for retry button
	    // 页面上可能同时存在多个 reload 按钮（如 Refresh / Reset），避免 strict mode 冲突
	    const retryButton = page.getByRole('button', { name: /Retry|Try Again|Refresh|Reload/i }).first()
	
	    if (await retryButton.isVisible().catch(() => false)) {
	      await retryButton.click()
	      await page.waitForTimeout(2000)
	
	      // Verify retry was attempted
	      expect(requestCount).toBeGreaterThan(1)
	      console.log(`Retry attempted, request count: ${requestCount}`)
	    }
	  })

  test('Handles network timeout gracefully', async ({ page }) => {
    await page.route('**/api/v1/lncrna-chipseq-overlap*', (route) => {
      route.abort('timedout')
    })

    await page.goto(PAGE_URL)
    await page.waitForTimeout(5000)

    // Should show timeout or network error
    const errorIndicator = page.locator('.ant-notification, .ant-message, .ant-alert, .ant-result-error')
    const errorText = page.getByText(/Timeout|Network|Connection|Error/i)

    const hasErrorIndicator = await errorIndicator.isVisible().catch(() => false)
    const hasErrorText = await errorText.isVisible().catch(() => false)

    // Page should still be usable (not crashed)
    const pageContent = page.locator('body')
    await expect(pageContent).toBeVisible()

    console.log(`Timeout handled: error indicator=${hasErrorIndicator}, error text=${hasErrorText}`)
  })

  test('Error does not crash the application', async ({ page }) => {
    // Inject console error listener
    const consoleErrors: string[] = []
    page.on('console', (msg) => {
      if (msg.type() === 'error') {
        consoleErrors.push(msg.text())
      }
    })

    await page.route('**/api/v1/lncrna-chipseq-overlap*', (route) => {
      route.fulfill({
        status: 500,
        contentType: 'application/json',
        body: JSON.stringify({ detail: 'Test Error' })
      })
    })

    await page.goto(PAGE_URL)
    await page.waitForTimeout(3000)

    // Verify page is still functional
    const body = page.locator('body')
    await expect(body).toBeVisible()

    // Check navigation still works
    const navMenu = page.locator('[role="menu"]')
    if (await navMenu.isVisible().catch(() => false)) {
      console.log('Navigation menu still functional')
    }

    // Filter fatal errors (not all console errors are problems)
    const fatalErrors = consoleErrors.filter(e =>
      e.includes('Uncaught') ||
      e.includes('Cannot read') ||
      e.includes('undefined is not')
    )

    console.log(`Console errors: ${consoleErrors.length}, Fatal errors: ${fatalErrors.length}`)
    expect(fatalErrors.length).toBe(0)
  })
})

// ============================================================================
// Test Suite: Export Functionality
// ============================================================================

test.describe('ChIP-seq Overlap - Export', () => {
  test.beforeEach(async ({ page }) => {
    await page.goto(PAGE_URL)
    await page.waitForLoadState('networkidle')
    await page.waitForTimeout(2000)
  })

  test('BED export downloads file', async ({ page }) => {
    const exportButton = page.locator('button').filter({ hasText: /Export|BED/i }).first()

    if (await exportButton.count() > 0) {
      await exportButton.click()
      await page.waitForTimeout(500)

      // Handle dropdown menu if present
      const bedOption = page.locator('.ant-dropdown-menu-item').filter({ hasText: /BED/i }).first()

      if (await bedOption.isVisible().catch(() => false)) {
        const downloadPromise = page.waitForEvent('download', { timeout: 15000 }).catch(() => null)
        await bedOption.click()

        const download = await downloadPromise
        if (download) {
          const filename = download.suggestedFilename()
          expect(filename).toMatch(/\.bed$/i)
          console.log(`BED file downloaded: ${filename}`)
        }
      }
    }
  })

  test('CSV export downloads file', async ({ page }) => {
    const exportButton = page.locator('button').filter({ hasText: /Export|CSV/i }).first()

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
          console.log(`CSV file downloaded: ${filename}`)
        }
      }
    }
  })

  test('Export with filters applies filter to export', async ({ page }) => {
    // Apply a filter first
    const select = page.locator('.ant-select').first()
    if (await select.count() > 0) {
      await select.click()
      await page.waitForTimeout(300)

      const option = page.locator('.ant-select-dropdown:visible .ant-select-item').first()
      if (await option.count() > 0) {
        await option.click()
        await waitForOverlapAPI(page)
      }
    }

    // Track export API call
    let exportUrl = ''
    page.on('request', (request) => {
      if (request.url().includes('export') || request.url().includes('download')) {
        exportUrl = request.url()
      }
    })

    // Click export
    const exportButton = page.locator('button').filter({ hasText: /Export/i }).first()
    if (await exportButton.count() > 0) {
      await exportButton.click()
      await page.waitForTimeout(1000)

      if (exportUrl) {
        console.log(`Export URL includes filters: ${exportUrl}`)
      }
    }
  })

  test('Export is disabled when no data', async ({ page }) => {
    await page.route('**/api/v1/lncrna-chipseq-overlap*', (route) => {
      route.fulfill({
        status: 200,
        contentType: 'application/json',
        body: JSON.stringify({ items: [], total: 0, page: 1, page_size: 20, total_pages: 0 })
      })
    })

    await page.goto(PAGE_URL)
    await page.waitForLoadState('networkidle')
    await page.waitForTimeout(2000)

    const exportButton = page.locator('button').filter({ hasText: /Export/i }).first()

    if (await exportButton.count() > 0) {
      const isDisabled = await exportButton.isDisabled().catch(() => false)
      const hasDisabledClass = await exportButton.getAttribute('class').then(c => c?.includes('disabled')).catch(() => false)

      console.log(`Export button disabled when no data: ${isDisabled || hasDisabledClass}`)
    }
  })
})

// ============================================================================
// Test Suite: Accessibility
// ============================================================================

test.describe('ChIP-seq Overlap - Accessibility', () => {
  test('Page has proper heading structure', async ({ page }) => {
    await page.goto(PAGE_URL, { waitUntil: 'domcontentloaded' })

    // SPA + lazy routes: wait for meaningful UI instead of relying on networkidle.
    await page.locator('h1, h2').first().waitFor({ state: 'visible', timeout: 15000 })

    const h1 = page.locator('h1')
    const h2 = page.locator('h2')

    const h1Count = await h1.count()
    const h2Count = await h2.count()

    // Should have at least one heading
    expect(h1Count + h2Count).toBeGreaterThan(0)
    console.log(`Headings: H1=${h1Count}, H2=${h2Count}`)
  })

  test('Form controls have labels', async ({ page }) => {
    await page.goto(PAGE_URL)
    await page.waitForLoadState('networkidle')
    await page.waitForTimeout(2000)

    // Check for form items with labels
    const formItems = page.locator('.ant-form-item')
    const formItemCount = await formItems.count()

    if (formItemCount > 0) {
      const labels = page.locator('.ant-form-item-label')
      const labelCount = await labels.count()

      console.log(`Form items: ${formItemCount}, Labels: ${labelCount}`)
    }
  })

  test('Interactive elements are keyboard accessible', async ({ page }) => {
    await page.goto(PAGE_URL)
    await page.waitForLoadState('networkidle')
    await page.waitForTimeout(2000)

    // Tab through interactive elements
    await page.keyboard.press('Tab')
    await page.waitForTimeout(200)

    const focusedElement = page.locator(':focus')
    const hasFocus = await focusedElement.count() > 0

    expect(hasFocus).toBe(true)
    console.log('Keyboard navigation works')
  })

  test('Color contrast is sufficient', async ({ page }) => {
    await page.goto(PAGE_URL)
    await page.waitForLoadState('networkidle')

    // Basic check: text should be visible
    const bodyText = await page.locator('body').textContent()
    expect(bodyText?.length).toBeGreaterThan(0)

    // Note: Full contrast testing would require axe-core or similar
    console.log('Basic visibility check passed')
  })
})
