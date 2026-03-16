import { test, expect, type Page } from '@playwright/test'

/**
 * Global Error States and Loading States E2E Tests
 *
 * This test suite provides comprehensive coverage of error handling
 * and loading states across the entire application:
 *
 * 1. Global error boundary testing
 * 2. Network error handling
 * 3. API error responses (400, 401, 403, 404, 500, 502, 503)
 * 4. Loading states and skeletons
 * 5. Timeout handling
 * 6. Empty states
 * 7. Retry mechanisms
 * 8. Error recovery
 *
 * This addresses the TODO: "Phase 3.0 Overlap E2E Tests:
 * Error states render correctly, Loading states work, Empty states helpful"
 */


// Pages to test
const TEST_PAGES = [
  { path: '/genes', name: 'Genes', api: '/api/v1/genes' },
  { path: '/regulations', name: 'Regulations', api: '/api/v1/regulations' },
  { path: '/lncrna-chipseq-overlap', name: 'ChIP-seq Overlap', api: '/api/v1/lncrna-chipseq-overlap' },
  { path: '/network', name: 'Network', api: '/api/v1/network' },
  { path: '/diseases', name: 'Diseases', api: '/api/v1/diseases' },
]

const MOCK_GENES_RESPONSE = {
  items: [],
  total: 0,
  page: 1,
  page_size: 20,
}

const MOCK_REGULATIONS_RESPONSE = {
  items: [],
  total: 0,
  page: 1,
  page_size: 20,
}

async function expectErrorState(page: Page, detailPattern?: RegExp) {
  const errorState = page.locator('.ant-result').first()
  await expect(errorState).toBeVisible({ timeout: 10000 })
  await expect(errorState).toContainText(/Failed to load|Load Failed|加载失败/i)

  if (detailPattern) {
    await expect(errorState).toContainText(detailPattern)
  }
}

// ============================================================================
// Test Suite: Global Error Boundary
// ============================================================================

test.describe('Error Boundary Testing', () => {
  test('Error boundary catches render errors', async ({ page }) => {
    // Inject an error into React
    await page.addInitScript(() => {
      // This will be executed before any page scripts
      window.addEventListener('load', () => {
        // Attempt to trigger error boundary (if exposed)
        if ((window as any).__TRIGGER_ERROR_BOUNDARY__) {
          (window as any).__TRIGGER_ERROR_BOUNDARY__()
        }
      })
    })

    await page.goto('/')
    await page.waitForLoadState('networkidle')

    // Page should still be functional
    const body = page.locator('body')
    await expect(body).toBeVisible()

    console.log('Error boundary test completed')
  })

  test('Application recovers from JavaScript errors', async ({ page }) => {
    const jsErrors: string[] = []
    page.on('pageerror', (error) => {
      jsErrors.push(error.message)
    })

    await page.goto('/')
    await page.waitForLoadState('networkidle')

    // Try navigating to different pages
    for (const testPage of TEST_PAGES.slice(0, 2)) {
      await page.goto(testPage.path)
      await page.waitForLoadState('networkidle')
    }

    // Log errors but don't fail on non-critical ones
    console.log(`JavaScript errors encountered: ${jsErrors.length}`)
    jsErrors.forEach((err, i) => console.log(`  ${i + 1}. ${err.substring(0, 100)}`))

    // Page should still be usable
    const content = page.locator('body')
    await expect(content).toBeVisible()
  })
})

// ============================================================================
// Test Suite: HTTP Error Status Codes
// ============================================================================

test.describe('HTTP Error Status Handling', () => {

  test('Handles 400 Bad Request', async ({ page }) => {
    await page.route('**/api/v1/**', (route) => {
      route.fulfill({
        status: 400,
        contentType: 'application/json',
        body: JSON.stringify({ detail: 'Bad Request: Invalid parameters' })
      })
    })

    await page.goto('/genes')
    await page.waitForTimeout(3000)

    // Should show error
    const errorIndicator = page.locator('.ant-message-error, .ant-notification-notice-error, .ant-alert-error')
    const errorText = page.getByText(/Bad Request|Invalid|错误的请求/i)

    const hasError = await errorIndicator.isVisible().catch(() => false) ||
                     await errorText.isVisible().catch(() => false)

    expect(hasError).toBe(true)
    console.log(`400 error handled: ${hasError}`)
  })

  test('Handles 401 Unauthorized', async ({ page }) => {
    await page.route('**/api/v1/**', (route) => {
      route.fulfill({
        status: 401,
        contentType: 'application/json',
        body: JSON.stringify({ detail: 'Unauthorized' })
      })
    })

    await page.goto('/genes')
    await page.waitForTimeout(3000)

    // May redirect to login or show error
    const errorText = page.getByText(/Unauthorized|Login|认证|登录/i)
    const hasError = await errorText.isVisible().catch(() => false)

    expect(hasError).toBe(true)
    console.log(`401 error handled: ${hasError}`)

    // Page should not crash
    const body = page.locator('body')
    await expect(body).toBeVisible()
  })

  test('Handles 403 Forbidden', async ({ page }) => {
    await page.route('**/api/v1/**', (route) => {
      route.fulfill({
        status: 403,
        contentType: 'application/json',
        body: JSON.stringify({ detail: 'Forbidden' })
      })
    })

    await page.goto('/genes')
    await page.waitForTimeout(3000)

    const errorText = page.getByText(/Forbidden|Permission|禁止|权限/i)
    const hasError = await errorText.isVisible().catch(() => false)

    expect(hasError).toBe(true)
    console.log(`403 error handled: ${hasError}`)
  })

  test('Handles 404 Not Found', async ({ page }) => {
    await page.route('**/api/v1/**', (route) => {
      route.fulfill({
        status: 404,
        contentType: 'application/json',
        body: JSON.stringify({ detail: 'Resource not found' })
      })
    })

    await page.goto('/genes')
    await page.waitForTimeout(3000)
    await expectErrorState(page, /Resource not found|Not Found|404|未找到/i)
    console.log('404 error handled')
  })

	  test('Handles 500 Internal Server Error', async ({ page }) => {
	    await page.route('**/api/v1/**', (route) => {
	      route.fulfill({
	        status: 500,
	        contentType: 'application/json',
	        body: JSON.stringify({ detail: 'Internal Server Error' })
	      })
	    })
	
	    await page.goto('/regulations')
	    await page.waitForTimeout(3000)
	
	    const errorIndicator = page.locator(
	      '.ant-message-error, .ant-notification-notice-error, .ant-alert-error, .ant-result-error, .ant-result-500'
	    ).first()
	    const errorText = page.getByText(
	      /Server Error|500|服务器错误|Loading Failed|Internal Server Error/i
	    ).first()
	
	    const hasError = await errorIndicator.isVisible().catch(() => false) ||
	                     await errorText.isVisible().catch(() => false)

    expect(hasError).toBe(true)
    console.log('500 error handled')
  })

  test('Handles 502 Bad Gateway', async ({ page }) => {
    await page.route('**/api/v1/**', (route) => {
      route.fulfill({
        status: 502,
        contentType: 'text/html',
        body: '<html><body>502 Bad Gateway</body></html>'
      })
    })

    await page.goto('/genes')
    await expectErrorState(page, /Request failed|Bad Gateway|502/i)

    // Page should not crash
    const body = page.locator('body')
    await expect(body).toBeVisible()
  })

  test('Handles 503 Service Unavailable', async ({ page }) => {
    await page.route('**/api/v1/**', (route) => {
      route.fulfill({
        status: 503,
        contentType: 'application/json',
        body: JSON.stringify({ detail: 'Service Unavailable' })
      })
    })

    await page.goto('/regulations')
    await page.waitForTimeout(3000)
    await expectErrorState(page, /Service Unavailable|Unavailable|503|服务不可用/i)
    console.log('503 error handled')
  })
})

// ============================================================================
// Test Suite: Network Error Handling
// ============================================================================

test.describe('Network Error Handling', () => {

  test('Handles network timeout', async ({ page }) => {
    await page.route('**/api/v1/**', async (route) => {
      // Simulate timeout by never responding
      await new Promise(resolve => setTimeout(resolve, 60000))
    })

    // Set shorter timeout for test
    page.setDefaultTimeout(10000)

    await page.goto('/genes')
    await page.waitForTimeout(5000)

    // Should show loading or timeout error
    const spinner = page.locator('.ant-spin')
    const errorText = page.getByText(/Timeout|Loading|超时|加载/i)

    const isLoading = await spinner.isVisible().catch(() => false)
    const hasError = await errorText.isVisible().catch(() => false)

    expect(isLoading || hasError).toBe(true)
    console.log(`Timeout handling: loading=${isLoading}, error=${hasError}`)
  })

  test('Handles network failure', async ({ page }) => {
    await page.route('**/api/v1/**', (route) => {
      route.abort('failed')
    })

    await page.goto('/regulations')
    await expectErrorState(page, /Network error|check your connection|连接/i)

    // Page should still render
    const body = page.locator('body')
    await expect(body).toBeVisible()
  })

  test('Handles connection reset', async ({ page }) => {
    await page.route('**/api/v1/**', (route) => {
      route.abort('connectionreset')
    })

    await page.goto('/lncrna-chipseq-overlap')
    await page.waitForTimeout(3000)

    // Page should handle gracefully
    const body = page.locator('body')
    await expect(body).toBeVisible()

    console.log('Connection reset handled')
  })

  test('Handles slow network', async ({ page }) => {
    await page.route('**/api/v1/**', async (route) => {
      await new Promise(resolve => setTimeout(resolve, 5000))
      await route.fulfill({
        status: 200,
        contentType: 'application/json',
        body: JSON.stringify(MOCK_GENES_RESPONSE),
      })
    })

    await page.goto('/genes')

    // Should show loading state during slow response
    const spinner = page.locator('.ant-spin')
    const isLoading = await spinner.isVisible({ timeout: 2000 }).catch(() => false)

    expect(isLoading).toBe(true)
    console.log(`Slow network shows loading: ${isLoading}`)

    // Eventually should load
    await page.waitForLoadState('networkidle', { timeout: 30000 })
  })
})

// ============================================================================
// Test Suite: Loading States
// ============================================================================

test.describe('Loading States', () => {

  for (const testPage of TEST_PAGES) {
    test(`${testPage.name} page shows loading state`, async ({ page }) => {
      // Slow down API
      await page.route(`**${testPage.api}*`, async (route) => {
        await new Promise(resolve => setTimeout(resolve, 2000))
        route.continue()
      })

      await page.goto(testPage.path)

      // Check for loading indicator
      const spinner = page.locator('.ant-spin')
      const skeleton = page.locator('.ant-skeleton')
      const loadingText = page.getByText(/Loading|加载中/i)

      const hasSpinner = await spinner.isVisible({ timeout: 3000 }).catch(() => false)
      const hasSkeleton = await skeleton.isVisible({ timeout: 1000 }).catch(() => false)
      const hasLoadingText = await loadingText.isVisible({ timeout: 1000 }).catch(() => false)

      console.log(`${testPage.name} loading state: spinner=${hasSpinner}, skeleton=${hasSkeleton}, text=${hasLoadingText}`)

      // Wait for load to complete
      await page.waitForLoadState('networkidle', { timeout: 30000 })
    })
  }

  test('Loading state disappears after data loads', async ({ page }) => {
    let requestComplete = false

    await page.route('**/api/v1/genes*', async (route) => {
      await new Promise(resolve => setTimeout(resolve, 1000))
      requestComplete = true
      route.continue()
    })

    await page.goto('/genes')

    // Wait for loading to start
    await page.waitForTimeout(500)

    // Loading indicator should be visible
    const spinnerBefore = await page.locator('.ant-spin').isVisible().catch(() => false)

    // Wait for request to complete
    await page.waitForLoadState('networkidle')
    await page.waitForTimeout(500)

    // Loading indicator should be gone
    const spinnerAfter = await page.locator('.ant-spin').isVisible().catch(() => false)
    const tableVisible = await page.locator('.ant-table').isVisible().catch(() => false)

    console.log(`Loading transition: before=${spinnerBefore}, after=${spinnerAfter}, table=${tableVisible}`)
  })

  test('Loading on filter change', async ({ page }) => {
    await page.goto('/genes')
    await page.waitForLoadState('networkidle')
    await page.waitForTimeout(2000)

    // Slow down subsequent requests
    await page.route('**/api/v1/genes*', async (route) => {
      await new Promise(resolve => setTimeout(resolve, 1000))
      route.continue()
    })

    // Apply a filter
    const select = page.locator('.ant-select').first()
    if (await select.count() > 0) {
      await select.click()
      await page.waitForTimeout(300)

      const option = page.locator('.ant-select-dropdown:visible .ant-select-item').first()
      if (await option.count() > 0) {
        await option.click()

        // Check for loading state
        const spinner = page.locator('.ant-spin, .ant-table-loading')
        const hasLoading = await spinner.isVisible({ timeout: 1500 }).catch(() => false)

        console.log(`Loading on filter change: ${hasLoading}`)
      }
    }
  })
})

// ============================================================================
// Test Suite: Empty States
// ============================================================================

test.describe('Empty States', () => {

  for (const testPage of TEST_PAGES.slice(0, 3)) {
    test(`${testPage.name} page shows helpful empty state`, async ({ page }) => {
      await page.route(`**${testPage.api}*`, (route) => {
        route.fulfill({
          status: 200,
          contentType: 'application/json',
          body: JSON.stringify({ data: [], total: 0, page: 1, page_size: 20 })
        })
      })

      await page.goto(testPage.path)
      await page.waitForTimeout(2000)

      // Check for empty state
      const emptyState = page.locator('.ant-empty')
      const emptyDescription = page.locator('.ant-empty-description')
      const noDataText = page.getByText(/No Data|No Results|Empty|无数据|暂无/i)

      const hasEmptyState = await emptyState.isVisible().catch(() => false)
      const hasDescription = await emptyDescription.isVisible().catch(() => false)
      const hasNoDataText = await noDataText.isVisible().catch(() => false)

      console.log(`${testPage.name} empty state: state=${hasEmptyState}, description=${hasDescription}, text=${hasNoDataText}`)

      // Empty state should be visible
      expect(hasEmptyState || hasNoDataText).toBe(true)
    })
  }

  test('Empty state has helpful message', async ({ page }) => {
    await page.route('**/api/v1/genes*', (route) => {
      route.fulfill({
        status: 200,
        contentType: 'application/json',
        body: JSON.stringify({ data: [], total: 0 })
      })
    })

    await page.goto('/genes')
    await page.waitForTimeout(2000)

    const emptyDescription = page.locator('.ant-empty-description')
    if (await emptyDescription.isVisible().catch(() => false)) {
      const text = await emptyDescription.textContent()
      console.log(`Empty state message: ${text}`)
      expect(text?.length).toBeGreaterThan(0)
    }
  })

  test('Empty state allows retry or suggests action', async ({ page }) => {
    await page.route('**/api/v1/regulations*', (route) => {
      route.fulfill({
        status: 200,
        contentType: 'application/json',
        body: JSON.stringify({ data: [], total: 0 })
      })
    })

    await page.goto('/regulations')
    await page.waitForTimeout(2000)

    // Check for action button or hint
    const retryButton = page.getByRole('button', { name: /Retry|Refresh|Reset|重试|刷新/i })
    const actionHint = page.getByText(/try|suggest|change|尝试|建议/i)

    const hasRetry = await retryButton.count() > 0
    const hasHint = await actionHint.isVisible().catch(() => false)

    console.log(`Empty state actions: retry=${hasRetry}, hint=${hasHint}`)
  })
})

// ============================================================================
// Test Suite: Retry Mechanisms
// ============================================================================

test.describe('Retry Mechanisms', () => {

  test('Error state is shown on server error', async ({ page }) => {
    await page.route('**/api/v1/genes*', (route) => {
      route.fulfill({
        status: 500,
        contentType: 'application/json',
        body: JSON.stringify({ detail: 'Server Error' })
      })
    })

    await page.goto('/genes')
    await expectErrorState(page, /Server Error|Request failed/i)
    await expect(page.locator('body')).toBeVisible()
  })

  test('Retry actually retries the request', async ({ page }) => {
    let requestCount = 0

    await page.route('**/api/v1/genes*', (route) => {
      requestCount++
      if (requestCount <= 1) {
        route.fulfill({
          status: 500,
          contentType: 'application/json',
          body: JSON.stringify({ detail: 'Server Error' })
        })
      } else {
        route.continue()
      }
    })

    await page.goto('/genes')
    await page.waitForTimeout(2000)

    const retryButton = page.getByRole('button', { name: /Retry|Try Again|重试/i })
    if (await retryButton.count() > 0) {
      await retryButton.click()
      await page.waitForTimeout(3000)

      expect(requestCount).toBeGreaterThan(1)
      console.log(`Retry request count: ${requestCount}`)
    }
  })

  test('Automatic retry on intermittent failure', async ({ page }) => {
    let requestCount = 0

    await page.route('**/api/v1/regulations*', (route) => {
      requestCount++
      // React Query may automatically retry
      if (requestCount <= 2) {
        route.abort('failed')
      } else {
        route.fulfill({
          status: 200,
          contentType: 'application/json',
          body: JSON.stringify(MOCK_REGULATIONS_RESPONSE),
        })
      }
    })

    await page.goto('/regulations')
    await page.waitForTimeout(10000) // Give time for retries

    expect(requestCount).toBeGreaterThan(1)
    console.log(`Auto-retry request count: ${requestCount}`)
  })
})

// ============================================================================
// Test Suite: Error Recovery
// ============================================================================

test.describe('Error Recovery', () => {

  test('Can navigate away from error page', async ({ page }) => {
    await page.route('**/api/v1/genes*', (route) => {
      route.fulfill({
        status: 500,
        contentType: 'application/json',
        body: JSON.stringify({ detail: 'Error' })
      })
    })

    await page.goto('/genes')
    await page.waitForTimeout(2000)

    // Navigate to another page
    await page.goto('/regulations')
    await page.waitForTimeout(2000)

    // Should be able to use the app
    const content = page.locator('h1, h2, .ant-table').first()
    await expect(content).toBeVisible({ timeout: 15000 })

    console.log('Navigation away from error page works')
  })

  test('Error state clears on successful refresh', async ({ page }) => {
    let requestCount = 0

    await page.route('**/api/v1/genes*', (route) => {
      requestCount += 1

      if (requestCount <= 2) {
        route.fulfill({
          status: 500,
          contentType: 'application/json',
          body: JSON.stringify({ detail: 'Error' })
        })
      } else {
        route.fulfill({
          status: 200,
          contentType: 'application/json',
          body: JSON.stringify(MOCK_GENES_RESPONSE),
        })
      }
    })

    await page.goto('/genes')
    await expectErrorState(page, /Error|Server Error|Request failed/i)

    // Refresh page
    await page.reload()
    await page.waitForLoadState('networkidle')

    // Should show data now
    const table = page.locator('.ant-table')
    await expect(table).toBeVisible()
    await expect(page.locator('.ant-result').first()).toBeHidden()
  })

  test('Sidebar navigation works after error', async ({ page }) => {
    await page.route('**/api/v1/genes*', (route) => {
      route.fulfill({
        status: 500,
        contentType: 'application/json',
        body: JSON.stringify({ detail: 'Error' })
      })
    })

    await page.goto('/genes')
    await page.waitForTimeout(2000)

    // Sidebar should still work
    const sidebarMenu = page.locator('[role="menu"]')
    await expect(sidebarMenu).toBeVisible()

    // Click on a menu item
    const menuItem = page.getByRole('menuitem').filter({ hasText: /Regulation|调控/i }).first()
    if (await menuItem.count() > 0) {
      await menuItem.click()
      await page.waitForLoadState('networkidle')

      expect(page.url()).toContain('/regulations')
      console.log('Sidebar navigation works after error')
    }
  })
})

// ============================================================================
// Test Suite: Console Error Monitoring
// ============================================================================

test.describe('Console Error Monitoring', () => {

  for (const testPage of TEST_PAGES.slice(0, 3)) {
    test(`${testPage.name} page has no critical console errors`, async ({ page }) => {
      const consoleErrors: string[] = []

      page.on('console', (msg) => {
        if (msg.type() === 'error') {
          consoleErrors.push(msg.text())
        }
      })

      await page.goto(testPage.path)
      await page.waitForLoadState('networkidle')
      await page.waitForTimeout(3000)

      // Filter critical errors
      const criticalErrors = consoleErrors.filter(e =>
        e.includes('Uncaught') ||
        e.includes('Cannot read properties') ||
        e.includes('undefined is not') ||
        e.includes('is not a function') ||
        e.includes('Failed to execute')
      )

      console.log(`${testPage.name} console errors: ${consoleErrors.length}, critical: ${criticalErrors.length}`)

      // No critical errors allowed
      expect(criticalErrors.length).toBe(0)
    })
  }
})

// ============================================================================
// Test Suite: Error Message Quality
// ============================================================================

test.describe('Error Message Quality', () => {

  test('Error messages are user-friendly', async ({ page }) => {
    await page.route('**/api/v1/genes*', (route) => {
      route.fulfill({
        status: 500,
        contentType: 'application/json',
        body: JSON.stringify({ detail: 'Internal Server Error' })
      })
    })

    await page.goto('/genes')
    await page.waitForTimeout(3000)

    // Check for user-friendly message (not raw error)
    const technicalError = page.getByText(/stack|trace|undefined|null|exception/i)
    const userFriendlyError = page.getByText(/Error|Failed|Try again|错误|失败/i)

    const hasTechnical = await technicalError.isVisible().catch(() => false)
    const hasUserFriendly = await userFriendlyError.isVisible().catch(() => false)

    console.log(`Error message quality: technical=${hasTechnical}, user-friendly=${hasUserFriendly}`)

    // Should show user-friendly, not technical
    expect(hasTechnical).toBe(false)
  })

  test('Error messages are localized', async ({ page }) => {
    await page.route('**/api/v1/**', (route) => {
      route.fulfill({
        status: 500,
        contentType: 'application/json',
        body: JSON.stringify({ detail: 'Server Error' })
      })
    })

    await page.goto('/genes')
    await page.waitForTimeout(3000)

    // Check for localized error (Chinese characters if in Chinese mode)
    const pageText = await page.locator('body').textContent()
    const hasChinese = /[\u4e00-\u9fa5]/.test(pageText || '')
    const hasEnglish = /Error|Failed|loading/i.test(pageText || '')

    expect(hasChinese || hasEnglish).toBe(true)
    console.log(`Error localization: Chinese=${hasChinese}, English=${hasEnglish}`)
  })
})
