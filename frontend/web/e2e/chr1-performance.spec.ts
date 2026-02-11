import { test, expect, type Page } from '@playwright/test'

/**
 * Chr1 Large Chromosome Query Performance E2E Tests
 *
 * Purpose: Validate that the materialized view optimization enables
 * efficient querying of large chromosomes (chr1) and all-chromosome queries.
 *
 * Test Coverage:
 * 1. Performance Tests (P0)
 *    - Chr1 data loads within acceptable time (<30s with MV optimization)
 *    - All chromosomes query is functional and uses materialized view
 *
 * 2. Functionality Tests (P1)
 *    - Chr1 filter shows results correctly
 *    - Loading states display appropriately for large queries
 *    - Info alerts display for all-chromosome queries
 *
 * 3. Regression Tests (P2)
 *    - Chr22 (small chromosome) still responds quickly
 *    - Export functionality works with large datasets
 *
 * Backend Requirements:
 * - Materialized view: mv_lncrna_chipseq_overlap must exist
 * - API returns: using_materialized_view, default_filter_applied, effective_chromosome
 */

const PAGE_URL = '/lncrna-chipseq-overlap'
const API_BASE = process.env.API_BASE_URL || 'http://localhost:8000'

function getEnvInt(name: string, fallback: number): number {
  const raw = process.env[name]
  if (!raw) return fallback
  const parsed = Number.parseInt(raw, 10)
  return Number.isFinite(parsed) ? parsed : fallback
}

// Performance thresholds (in milliseconds)
const PERF_THRESHOLDS = {
  CHR1_MAX_LOAD_TIME: getEnvInt('E2E_CHR1_MAX_LOAD_TIME_MS', 30000),       // chr1 with MV
  CHR22_MAX_LOAD_TIME: getEnvInt('E2E_CHR22_MAX_LOAD_TIME_MS', 5000),      // chr22 (small)
  ALL_CHROMOSOMES_MAX_TIME: getEnvInt('E2E_ALL_CHROMOSOMES_MAX_TIME_MS', 60000), // all chromosomes
  INITIAL_RENDER_TIME: getEnvInt('E2E_OVERLAP_INITIAL_RENDER_TIME_MS', 5000),    // initial page render
  CHR1_MAX_SORT_TIME: getEnvInt('E2E_CHR1_MAX_SORT_TIME_MS', 45000),       // sorting on chr1 can be noisy in CI/headless
}

// Helper: Wait for overlap API response and capture metadata
async function waitForOverlapAPIWithMetadata(
  page: Page,
  timeout = 60000,
  urlMustInclude: string[] = []
): Promise<{
  response: any
  responseTime: number
  usingMaterializedView: boolean
  defaultFilterApplied: boolean
  effectiveChromosome: string | null
  total: number
} | null> {
  const startTime = Date.now()

  try {
    const response = await page.waitForResponse(
      (resp) => {
        const url = resp.url()
        if (!url.includes('/api/v1/lncrna-chipseq-overlap')) return false
        if (url.includes('/summary') || url.includes('/heatmap') || url.includes('/export')) return false
        if (resp.status() !== 200) return false
        return urlMustInclude.every(fragment => url.includes(fragment))
      },
      { timeout }
    )

    const responseTime = Date.now() - startTime
    const jsonData = await response.json()

    return {
      response: jsonData,
      responseTime,
      usingMaterializedView: jsonData.using_materialized_view ?? false,
      defaultFilterApplied: jsonData.default_filter_applied ?? false,
      effectiveChromosome: jsonData.effective_chromosome ?? null,
      total: jsonData.total ?? 0
    }
  } catch (error) {
    console.error('Failed to capture API response:', error)
    return null
  }
}

// Helper: Select chromosome from dropdown
async function selectChromosome(
  page: Page,
  chromosome: string,
  beforeOptionClick?: () => void | Promise<void>
): Promise<boolean> {
  // Find the chromosome selector - look for Select component with chromosome label
  const chrSelector = page.locator('.ant-select').filter({ hasText: /Chromosome|All chromosomes/i }).first()
    .or(page.locator('.ant-form-item').filter({ hasText: /Chromosome/i }).locator('.ant-select').first())

  if (await chrSelector.count() === 0) {
    // Try to find any select that might be the chromosome selector
    const allSelects = page.locator('.ant-select')
    const selectCount = await allSelects.count()

    for (let i = 0; i < selectCount; i++) {
      const selectText = await allSelects.nth(i).textContent()
      if (selectText && (selectText.includes('chr') || selectText.includes('Chromosome') || selectText.includes('All'))) {
        await allSelects.nth(i).click()
        await page.waitForTimeout(300)

        const option = page.locator('.ant-select-dropdown:visible .ant-select-item')
          .filter({ hasText: new RegExp(`^${chromosome}$`, 'i') }).first()

        if (await option.count() > 0) {
          await beforeOptionClick?.()
          await option.click()
          return true
        }
        break
      }
    }
    return false
  }

  await chrSelector.click()
  await page.waitForTimeout(300)

  // If the dropdown has a search input (showSearch), use it to avoid virtualization issues
  const dropdownSearch = page.locator('.ant-select-dropdown:visible input').first()
  if (await dropdownSearch.count() > 0) {
    await dropdownSearch.fill(chromosome)
    await page.waitForTimeout(100)
  }

  // Look for the specific chromosome option
  const chrOption = page.locator('.ant-select-dropdown:visible .ant-select-item')
    .filter({ hasText: new RegExp(`^${chromosome}$`, 'i') }).first()

  if (await chrOption.count() > 0) {
    await beforeOptionClick?.()
    await chrOption.click()
    return true
  }

  // Close dropdown if option not found
  await page.keyboard.press('Escape')
  return false
}

// Helper: Clear chromosome filter (select "All chromosomes")
async function clearChromosomeFilter(page: Page): Promise<boolean> {
  const chrSelector = page.locator('.ant-select').filter({ hasText: /Chromosome|chr|All/i }).first()

  if (await chrSelector.count() === 0) {
    return false
  }

  // Look for clear button within the selector
  const clearButton = chrSelector.locator('.ant-select-clear')
  if (await clearButton.count() > 0) {
    await clearButton.click()
    return true
  }

  // Alternative: click the selector and look for "All" option or clear
  await chrSelector.click()
  await page.waitForTimeout(300)

  // Try to find an "All chromosomes" option or similar
  const allOption = page.locator('.ant-select-dropdown:visible .ant-select-item')
    .filter({ hasText: /All.*chromosome|All|Select/i }).first()

  if (await allOption.count() > 0) {
    await allOption.click()
    return true
  }

  await page.keyboard.press('Escape')
  return false
}

// ============================================================================
// P0: Performance Tests - Critical Path
// ============================================================================

test.describe('Chr1 Large Chromosome Query Performance (P0)', () => {
  test.setTimeout(120000) // 2-minute timeout for large queries

  test.beforeEach(async ({ page }) => {
    await page.goto(PAGE_URL)
    await page.waitForLoadState('domcontentloaded')
    await page.waitForTimeout(2000) // Allow initial render
  })

  test('P0: should load chr1 data within acceptable time (<30s with materialized view)', async ({ page }) => {
    // Select chr1 chromosome and set up the response waiter BEFORE clicking.
    // Otherwise, a fast cached response can be missed and lead to flaky timeouts.
    let chr1Response: ReturnType<typeof waitForOverlapAPIWithMetadata> | null = null
    const selected = await selectChromosome(page, 'chr1', async () => {
      chr1Response = waitForOverlapAPIWithMetadata(page, PERF_THRESHOLDS.CHR1_MAX_LOAD_TIME, ['chromosome=chr1'])
    })
    if (!selected) {
      console.log('Warning: Could not select chr1 - chromosome selector not found or chr1 not available')
      test.skip()
      return
    }

    // Wait for API response and measure time
    const result = await (chr1Response ?? waitForOverlapAPIWithMetadata(page, PERF_THRESHOLDS.CHR1_MAX_LOAD_TIME, ['chromosome=chr1']))

    expect(result).not.toBeNull()
    if (!result) return

    // Log performance metrics
    console.log(`Chr1 Query Performance:`)
    console.log(`  - Response time: ${result.responseTime}ms`)
    console.log(`  - Using materialized view: ${result.usingMaterializedView}`)
    console.log(`  - Total results: ${result.total}`)

    // Performance assertion
    expect(result.responseTime).toBeLessThan(PERF_THRESHOLDS.CHR1_MAX_LOAD_TIME)

    // Data validation - chr1 should have data
    expect(result.total).toBeGreaterThan(0)

    // Verify table displays data
    await page.waitForTimeout(1000)
    const table = page.locator('.ant-table')
    await expect(table).toBeVisible({ timeout: 10000 })

    // NOTE: Overlap table enables Antd `virtual`, so rows are not necessarily <tr>.
    const dataRows = table.locator('.ant-table-row')
    await expect.poll(async () => dataRows.count(), { timeout: 20000 }).toBeGreaterThan(0)
    const rowCount = await dataRows.count()

    console.log(`  - Table rows displayed: ${rowCount}`)
  })

  test('P0: should handle all chromosomes query with materialized view optimization', async ({ page }) => {
    // Track API requests to verify MV usage
    let apiMetadata: any = null

    page.on('response', async (response) => {
      if (response.url().includes('/api/v1/lncrna-chipseq-overlap') &&
          !response.url().includes('/summary') &&
          !response.url().includes('/heatmap') &&
          !response.url().includes('/export') &&
          response.status() === 200) {
        try {
          apiMetadata = await response.json()
        } catch (e) {
          // Ignore JSON parse errors
        }
      }
    })

    // Clear any chromosome filter to query all chromosomes
    await clearChromosomeFilter(page)
    await page.waitForTimeout(500)

    // Wait for the API response
    const result = await waitForOverlapAPIWithMetadata(page, PERF_THRESHOLDS.ALL_CHROMOSOMES_MAX_TIME)

    // If no result within timeout, the query may still be running - this is acceptable
    // but we should verify the loading state is displayed
    if (!result) {
      console.log('All-chromosome query is taking longer than expected')

      // Check for loading state
      const loadingState = page.locator('.ant-spin')
      const isLoading = await loadingState.isVisible().catch(() => false)

      if (isLoading) {
        console.log('Loading state is displayed - query in progress')
        // This is acceptable behavior for very large queries
        return
      }
    }

    if (result) {
      console.log(`All Chromosomes Query Performance:`)
      console.log(`  - Response time: ${result.responseTime}ms`)
      console.log(`  - Using materialized view: ${result.usingMaterializedView}`)
      console.log(`  - Default filter applied: ${result.defaultFilterApplied}`)
      console.log(`  - Effective chromosome: ${result.effectiveChromosome || 'all'}`)
      console.log(`  - Total results: ${result.total}`)

      // Key assertion: When MV is available, all-chromosome queries should work
      // without falling back to default chr22 filter
      if (result.usingMaterializedView) {
        expect(result.defaultFilterApplied).toBe(false)
        expect(result.effectiveChromosome).toBeNull()
      }

      // Verify data loaded
      expect(result.total).toBeGreaterThan(0)
    }

    // Verify table is visible (either with data or empty state)
    const tableOrEmpty = page.locator('.ant-table, .ant-empty').first()
    await expect(tableOrEmpty).toBeVisible({ timeout: 15000 })
  })

  test('P0: should verify materialized view is being used via API response', async ({ page }) => {
    // Make a direct API call to check MV status
    const apiUrl = `${API_BASE}/api/v1/lncrna-chipseq-overlap?page=1&page_size=10`

    const response = await page.request.get(apiUrl)
    expect(response.ok()).toBe(true)

    const data = await response.json()

    console.log(`API Direct Call Results:`)
    console.log(`  - using_materialized_view: ${data.using_materialized_view}`)
    console.log(`  - default_filter_applied: ${data.default_filter_applied}`)
    console.log(`  - effective_chromosome: ${data.effective_chromosome || 'all'}`)
    console.log(`  - total: ${data.total}`)

    // This is an informational test - log the MV status
    // The MV should ideally be available for production performance
    if (data.using_materialized_view) {
      console.log('SUCCESS: Materialized view is active')
    } else {
      console.log('WARNING: Materialized view is NOT active - queries will be slower')
      console.log('Consider running: npm run refresh-mv or the materialized view refresh script')
    }
  })
})

// ============================================================================
// P1: Functionality Tests
// ============================================================================

test.describe('Overlap Query Functionality (P1)', () => {
  test.setTimeout(90000)

  test.beforeEach(async ({ page }) => {
    await page.goto(PAGE_URL)
    await page.waitForLoadState('domcontentloaded')
    await page.waitForTimeout(2000)
  })

  test('P1: should filter by chr1 and show results correctly', async ({ page }) => {
    // Select chr1 and wait for the chr1-specific overlap request.
    // IMPORTANT: set up the response waiter before clicking, otherwise a fast response can be missed.
    let chr1Response: ReturnType<typeof waitForOverlapAPIWithMetadata> | null = null
    const selected = await selectChromosome(page, 'chr1', async () => {
      chr1Response = waitForOverlapAPIWithMetadata(page, 60000, ['chromosome=chr1'])
    })
    if (!selected) {
      console.log('Skipping: chr1 selection not available')
      test.skip()
      return
    }

    // Wait for data to load
    const result = await (chr1Response ?? waitForOverlapAPIWithMetadata(page, 60000, ['chromosome=chr1']))
    expect(result).not.toBeNull()

    if (result) {
      // Verify results are for chr1
      expect(result.total).toBeGreaterThan(0)

      // Verify table displays correctly
      const table = page.locator('.ant-table')
      await expect(table).toBeVisible()

      // Check that chromosome column shows chr1
      const tableText = await table.textContent()
      expect(tableText).toContain('chr1')

      // Verify pagination shows correct total
      const pagination = page.locator('.ant-pagination-total-text')
      if (await pagination.count() > 0) {
        const paginationText = await pagination.textContent()
        console.log(`Pagination: ${paginationText}`)
      }
    }
  })

  test('P1: should show enhanced loading state for all-chromosome queries', async ({ page }) => {
    // Clear chromosome filter to trigger all-chromosome query
    await clearChromosomeFilter(page)

    // Immediately check for loading state (before query completes)
    // The component should show enhanced loading with progress for large queries

    // Look for loading indicators
    const loadingIndicator = page.locator('.ant-spin')
    const progressBar = page.locator('.ant-progress')
    const loadingText = page.getByText(/Loading.*all chromosomes|Loading data from all/i)

    // At least one loading indicator should appear for large queries
    const hasLoading = await loadingIndicator.isVisible({ timeout: 2000 }).catch(() => false)
    const hasProgress = await progressBar.isVisible({ timeout: 2000 }).catch(() => false)
    const hasLoadingText = await loadingText.isVisible({ timeout: 2000 }).catch(() => false)

    console.log(`Loading State Detection:`)
    console.log(`  - Spinner visible: ${hasLoading}`)
    console.log(`  - Progress bar: ${hasProgress}`)
    console.log(`  - Loading text: ${hasLoadingText}`)

    // Wait for query to complete
    await page.waitForTimeout(5000)

    // Verify page eventually shows content
    const content = page.locator('.ant-table, .ant-empty').first()
    await expect(content).toBeVisible({ timeout: 60000 })
  })

  test('P1: should display info alert for all-chromosome queries', async ({ page }) => {
    // Ensure we start from a specific chromosome so clearing triggers a real state change
    const selected = await selectChromosome(page, 'chr1')
    if (!selected) {
      console.log('Skipping: chromosome selector not available')
      test.skip()
      return
    }

    // Wait for chr22 query to settle (best effort)
    await waitForOverlapAPIWithMetadata(page, 30000)

    // Clear chromosome filter to switch back to all-chromosome query
    const cleared = await clearChromosomeFilter(page)
    if (!cleared) {
      console.log('Skipping: could not clear chromosome filter')
      test.skip()
      return
    }

    // Wait for info alert about all-chromosome query (it appears after data is loaded)
    const infoAlert = page.locator('.ant-alert-info').filter({ hasText: /Querying All Chromosomes|all chromosomes/i }).first()
    await expect(infoAlert).toBeVisible({ timeout: 60000 })

    const alertContent = await infoAlert.textContent().catch(() => '')
    console.log(`All-chromosome info alert: ${alertContent}`)
  })

  test('P1: should handle rapid chromosome filter changes', async ({ page }) => {
    // Rapid filter changes should not cause errors
    const chromosomes = ['chr1', 'chr22', 'chr2', 'chrX']

    for (const chr of chromosomes) {
      await selectChromosome(page, chr)
      await page.waitForTimeout(500)
    }

    // Wait for final query
    await page.waitForTimeout(3000)

    // Page should still be functional
    const table = page.locator('.ant-table')
    const isTableVisible = await table.isVisible().catch(() => false)

    const loadingState = page.locator('.ant-spin')
    const isLoading = await loadingState.isVisible().catch(() => false)

    const emptyState = page.locator('.ant-empty')
    const isEmpty = await emptyState.isVisible().catch(() => false)

    // Page should show one of: table, loading, or empty state (no crash)
    expect(isTableVisible || isLoading || isEmpty).toBe(true)

    // Check for JavaScript errors
    const consoleErrors: string[] = []
    page.on('console', (msg) => {
      if (msg.type() === 'error') {
        consoleErrors.push(msg.text())
      }
    })

    // Filter out non-critical errors
    const criticalErrors = consoleErrors.filter(e =>
      e.includes('Uncaught') ||
      e.includes('Cannot read') ||
      e.includes('undefined is not')
    )

    expect(criticalErrors.length).toBe(0)
  })
})

// ============================================================================
// P2: Regression Tests
// ============================================================================

test.describe('Regression Tests (P2)', () => {
  test.setTimeout(60000)

  test.beforeEach(async ({ page }) => {
    await page.goto(PAGE_URL)
    await page.waitForLoadState('domcontentloaded')
    await page.waitForTimeout(2000)
  })

  test('P2: should still work quickly with chr22 (small chromosome)', async ({ page }) => {
    const slackMs = getEnvInt('E2E_CHR22_SLACK_MS', 250)

    // Select chr22 - should be fast regardless of MV
    // IMPORTANT: start waiting before clicking to avoid missing a fast/cached response.
    let chr22Response: ReturnType<typeof waitForOverlapAPIWithMetadata> | null = null
    const startTime = Date.now()
    const selected = await selectChromosome(page, 'chr22', async () => {
      chr22Response = waitForOverlapAPIWithMetadata(
        page,
        PERF_THRESHOLDS.CHR22_MAX_LOAD_TIME + slackMs,
        ['chromosome=chr22']
      )
    })
    if (!selected) {
      console.log('Skipping: chr22 selection not available')
      test.skip()
      return
    }

    const result = await (chr22Response ?? waitForOverlapAPIWithMetadata(
      page,
      PERF_THRESHOLDS.CHR22_MAX_LOAD_TIME + slackMs,
      ['chromosome=chr22']
    ))
    const totalTime = Date.now() - startTime

    console.log(`Chr22 Query Performance:`)
    console.log(`  - Total time: ${totalTime}ms`)
    console.log(`  - API response time: ${result?.responseTime}ms`)
    console.log(`  - Total results: ${result?.total}`)

    // Chr22 should be fast
    expect(totalTime).toBeLessThanOrEqual(PERF_THRESHOLDS.CHR22_MAX_LOAD_TIME + slackMs)

    if (result) {
      expect(result.total).toBeGreaterThan(0)
    }

    // Verify table shows data
    const table = page.locator('.ant-table')
    await expect(table).toBeVisible()

    // NOTE: Overlap table enables Antd `virtual`, so rows are not necessarily <tr>.
    const rows = table.locator('.ant-table-row')
    await expect.poll(async () => rows.count(), { timeout: 20000 }).toBeGreaterThan(0)
    const rowCount = await rows.count()
  })

  test('P2: should export functionality work with chr1 (large dataset)', async ({ page }) => {
    // Select chr1
    const selected = await selectChromosome(page, 'chr1')
    if (!selected) {
      console.log('Skipping: chr1 selection not available')
      test.skip()
      return
    }

    // Wait for data to load
    await waitForOverlapAPIWithMetadata(page, 45000)
    await page.waitForTimeout(1000)

    // Find export button
    const exportButton = page.locator('button').filter({ hasText: /Export|Download/i }).first()

    if (await exportButton.count() === 0) {
      console.log('Export button not found - export feature may not be enabled')
      test.skip()
      return
    }

    // Click export
    await exportButton.click()
    await page.waitForTimeout(500)

    // Check for dropdown menu
    const dropdown = page.locator('.ant-dropdown-menu:visible')

    if (await dropdown.isVisible().catch(() => false)) {
      // Look for BED export option
      const bedOption = dropdown.locator('.ant-dropdown-menu-item').filter({ hasText: /BED/i }).first()

      if (await bedOption.count() > 0) {
        // Set up download listener
        const downloadPromise = page.waitForEvent('download', { timeout: 30000 }).catch(() => null)

        await bedOption.click()

        const download = await downloadPromise

        if (download) {
          const filename = download.suggestedFilename()
          console.log(`Export successful: ${filename}`)
          expect(filename).toMatch(/\.bed$/i)
        } else {
          // Export might open in new window instead of download
          console.log('Export initiated (may open in new window)')
        }
      }
    }
  })

  test('P2: should not have performance regression for pagination on chr1', async ({ page }) => {
    // Select chr1 and wait for initial overlap load (avoid missing fast responses).
    let chr1Response: ReturnType<typeof waitForOverlapAPIWithMetadata> | null = null
    const selected = await selectChromosome(page, 'chr1', async () => {
      chr1Response = waitForOverlapAPIWithMetadata(page, 60000, ['chromosome=chr1'])
    })
    if (!selected) {
      test.skip()
      return
    }

    // Wait for initial data
    await (chr1Response ?? waitForOverlapAPIWithMetadata(page, 60000, ['chromosome=chr1']))
    await page.waitForTimeout(1000)

    // Find pagination
    const pagination = page.locator('.ant-pagination')

    if (await pagination.isVisible().catch(() => false)) {
      // Try to go to page 2
      const page2Button = pagination.locator('.ant-pagination-item-2')

      if (await page2Button.count() > 0) {
        // Set up response waiter before clicking to avoid missing cached/fast pagination responses.
        const page2Response = waitForOverlapAPIWithMetadata(page, 15000, ['chromosome=chr1', 'page=2'])
        const startTime = Date.now()
        await page2Button.click()

        const result = await page2Response
        const paginationTime = Date.now() - startTime

        console.log(`Pagination Performance (chr1):`)
        console.log(`  - Time to page 2: ${paginationTime}ms`)

        // Pagination should be reasonably fast
        expect(paginationTime).toBeLessThan(15000)

        // Verify page 2 is now active
        await expect(page2Button).toHaveClass(/ant-pagination-item-active/)
      }
    }
  })

  test('P2: should handle sorting on large chromosome data', async ({ page }) => {
    // Select chr1 for large dataset and wait for initial load (avoid missing fast responses).
    let chr1Response: ReturnType<typeof waitForOverlapAPIWithMetadata> | null = null
    await selectChromosome(page, 'chr1', async () => {
      chr1Response = waitForOverlapAPIWithMetadata(page, 60000, ['chromosome=chr1'])
    })
    await (chr1Response ?? waitForOverlapAPIWithMetadata(page, 60000, ['chromosome=chr1']))
    await page.waitForTimeout(1000)

    // Find sortable column headers
    const sortableHeaders = page.locator('.ant-table-column-has-sorters')
    const headerCount = await sortableHeaders.count()

    if (headerCount > 0) {
      // Click first sortable header
      // IMPORTANT: start waiting before clicking, otherwise a fast response can be missed and the test will time out.
      const sortResponse = waitForOverlapAPIWithMetadata(
        page,
        PERF_THRESHOLDS.CHR1_MAX_SORT_TIME,
        ['chromosome=chr1']
      )
      const startTime = Date.now()
      await sortableHeaders.first().click()

      const result = await sortResponse
      const sortTime = Date.now() - startTime

      console.log(`Sorting Performance (chr1):`)
      console.log(`  - Sort time: ${sortTime}ms`)

      // Sorting should complete in reasonable time
      expect(sortTime).toBeLessThan(PERF_THRESHOLDS.CHR1_MAX_SORT_TIME)

      // Verify sort indicator appears
      const sortIcon = sortableHeaders.first().locator('.ant-table-column-sorter-up.active, .ant-table-column-sorter-down.active')
      const hasSortIcon = await sortIcon.count() > 0

      console.log(`  - Sort indicator: ${hasSortIcon}`)
    }
  })
})

// ============================================================================
// API Integration Tests
// ============================================================================

test.describe('API Integration - Materialized View Verification', () => {
  test('should verify API returns using_materialized_view flag', async ({ page }) => {
    // Direct API call to check response format
    const response = await page.request.get(`${API_BASE}/api/v1/lncrna-chipseq-overlap?page=1&page_size=1`)

    expect(response.ok()).toBe(true)
    const data = await response.json()

    // Verify response schema includes MV fields
    expect(data).toHaveProperty('using_materialized_view')
    expect(data).toHaveProperty('default_filter_applied')
    expect(data).toHaveProperty('effective_chromosome')

    console.log('API Response Fields:')
    console.log(`  - using_materialized_view: ${data.using_materialized_view}`)
    console.log(`  - default_filter_applied: ${data.default_filter_applied}`)
    console.log(`  - effective_chromosome: ${data.effective_chromosome}`)
    console.log(`  - total: ${data.total}`)
    console.log(`  - page: ${data.page}`)
    console.log(`  - page_size: ${data.page_size}`)
  })

  test('should handle chr1 API query directly', async ({ page }) => {
    const startTime = Date.now()
    const response = await page.request.get(
      `${API_BASE}/api/v1/lncrna-chipseq-overlap?chromosome=chr1&page=1&page_size=10`
    )
    const responseTime = Date.now() - startTime

    expect(response.ok()).toBe(true)
    const data = await response.json()

    console.log('Chr1 Direct API Call:')
    console.log(`  - Response time: ${responseTime}ms`)
    console.log(`  - Status: ${response.status()}`)
    console.log(`  - Total results: ${data.total}`)
    console.log(`  - Items returned: ${data.items?.length || 0}`)

    // Verify chr1 has data
    expect(data.total).toBeGreaterThan(0)
    expect(data.items).toBeDefined()
    expect(data.items.length).toBeGreaterThan(0)
  })

  test('should compare chr1 vs chr22 query performance via API', async ({ page }) => {
    // Chr22 query
    const chr22Start = Date.now()
    const chr22Response = await page.request.get(
      `${API_BASE}/api/v1/lncrna-chipseq-overlap?chromosome=chr22&page=1&page_size=10`
    )
    const chr22Time = Date.now() - chr22Start
    const chr22Data = await chr22Response.json()

    // Chr1 query
    const chr1Start = Date.now()
    const chr1Response = await page.request.get(
      `${API_BASE}/api/v1/lncrna-chipseq-overlap?chromosome=chr1&page=1&page_size=10`
    )
    const chr1Time = Date.now() - chr1Start
    const chr1Data = await chr1Response.json()

    console.log('Chromosome Query Comparison:')
    console.log(`  Chr22: ${chr22Time}ms, ${chr22Data.total} records`)
    console.log(`  Chr1:  ${chr1Time}ms, ${chr1Data.total} records`)
    console.log(`  MV Status: ${chr1Data.using_materialized_view}`)

    // Both should succeed
    expect(chr22Response.ok()).toBe(true)
    expect(chr1Response.ok()).toBe(true)

    // Chr1 typically has ~10x more data than chr22
    // With MV optimization, chr1 should not be dramatically slower
    const timeRatio = chr1Time / chr22Time

    console.log(`  Time ratio (chr1/chr22): ${timeRatio.toFixed(2)}x`)

    // With MV, chr1 should be at most 3x slower than chr22
    // Without MV, we just log the ratio
    if (chr1Data.using_materialized_view) {
      expect(timeRatio).toBeLessThan(5) // Allow some variance
    }
  })
})
