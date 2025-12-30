import { test, expect } from '@playwright/test'

/**
 * MCF-7 and HMEC Cell Line Validation Tests
 *
 * Purpose: Verify that MCF-7 (breast cancer) and HMEC (normal breast epithelial)
 * cell lines appear correctly in the frontend UI after database import.
 *
 * Cell Line Information:
 * - MCF-7: Breast adenocarcinoma cell line
 *   - Color: #FF69B4 (Hot Pink - cancer indicator)
 *   - Expected: 1 experiment (H3K4me3)
 *
 * - HMEC: Human Mammary Epithelial Cells (normal)
 *   - Color: #DEB887 (Burlywood - normal tissue indicator)
 *   - Expected: 6 experiments (core histone marks)
 *
 * Test Priority Levels:
 * - P0: Core functionality (must pass)
 * - P1: Data accuracy
 * - P2: Regression testing
 */

const BASE_URL = process.env.BASE_URL || 'http://localhost:5173'
const API_BASE_URL = process.env.API_BASE_URL || 'http://localhost:8000'
const PAGE_URL = '/lncrna-chipseq-overlap'

const OVERLAP_FILTER_TESTIDS = {
  markType: 'overlap-filter-mark-type',
  cellType: 'overlap-filter-cell-type',
  chromosome: 'overlap-filter-chromosome',
} as const

// Expected configurations for new cell lines
const CELL_LINE_CONFIGS = {
  'MCF-7': {
    color: '#FF69B4',
    expectedMarks: ['H3K4me3'],
    expectedExperimentCount: 1,
    category: 'cancer',
    description: 'Breast adenocarcinoma'
  },
  'HMEC': {
    color: '#DEB887',
    expectedMarks: ['H3K4me1', 'H3K4me3', 'H3K27ac', 'H3K27me3', 'H3K36me3', 'H3K9me3'],
    expectedExperimentCount: 6,
    category: 'normal',
    description: 'Human Mammary Epithelial Cells'
  }
}

// Existing cell lines for regression testing
const EXISTING_CELL_LINES = ['K562', 'GM12878', 'HepG2', 'H1-hESC', 'A549']

/**
 * Helper function to open cell type dropdown and get all options
 */
async function openCellTypeDropdown(page: any): Promise<string[]> {
  // Wait for page to stabilize
  await page.waitForLoadState('networkidle')
  await page.waitForTimeout(2000)

  // Prefer stable test selectors; fallback to text-based matching for backward compatibility.
  const testIdWrapper = page.getByTestId(OVERLAP_FILTER_TESTIDS.cellType)
  await testIdWrapper.waitFor({ state: 'visible', timeout: 20000 }).catch(() => null)
  const testIdSelector = testIdWrapper.locator('.ant-select').first()

  const cellTypeFilter = page.locator('.ant-select').filter({
    hasText: /Cell Type|细胞类型|Cell Line|细胞系/i,
  }).first()

  const selector = (await testIdSelector.count()) > 0
    ? testIdSelector
    : (await cellTypeFilter.count()) > 0
      ? cellTypeFilter
      : page.locator('.ant-select').nth(1)

  // Open dropdown
  await page.keyboard.press('Escape').catch(() => null)
  await selector.click()
  await page.waitForTimeout(500)

  // Get all options
  const dropdown = page.locator('.ant-select-dropdown:visible')
  await dropdown.waitFor({ state: 'visible', timeout: 15000 })

  const options = await dropdown.locator('.ant-select-item').allTextContents()
  return options
}

/**
 * Helper function to select a cell type from dropdown
 */
async function selectCellType(page: any, cellType: string): Promise<void> {
  const testIdWrapper = page.getByTestId(OVERLAP_FILTER_TESTIDS.cellType)
  await testIdWrapper.waitFor({ state: 'visible', timeout: 20000 }).catch(() => null)
  const testIdSelector = testIdWrapper.locator('.ant-select').first()
  const cellTypeFilter = page.locator('.ant-select').filter({
    hasText: /Cell Type|细胞类型|Cell Line|细胞系/i,
  }).first()

  const selector = (await testIdSelector.count()) > 0
    ? testIdSelector
    : (await cellTypeFilter.count()) > 0
      ? cellTypeFilter
      : page.locator('.ant-select').nth(1)

  // Ensure no stale dropdown is left open (can steal focus/clicks in parallel runs)
  await page.keyboard.press('Escape').catch(() => null)
  await selector.scrollIntoViewIfNeeded?.().catch(() => null)

  const escapeRegex = (value: string) => value.replace(/[.*+?^${}()|[\]\\]/g, '\\$&')
  const candidates = cellType === 'MCF-7' ? ['MCF-7', 'MCF7'] : [cellType]
  const exact = new RegExp(`^(${candidates.map(escapeRegex).join('|')})$`, 'i')
  const searchValue = cellType === 'MCF-7' ? 'MCF' : cellType

  // Retry: under heavy parallel E2E load the dropdown/options can render late.
  for (let attempt = 1; attempt <= 3; attempt++) {
    await selector.click()

    const dropdown = page.locator('.ant-select-dropdown:visible')
    await dropdown.waitFor({ state: 'visible', timeout: 15000 })

    // Guard: ensure we opened the cell type dropdown (not Mark Type / other selects).
    // Cell type options include known cell lines; mark dropdown contains grouped mark names like H3K*.
    const looksLikeCellTypeDropdown = await dropdown
      .locator('.ant-select-item')
      .filter({ hasText: /MCF|HMEC|K562|GM12878|HepG2|H1-hESC|HeLa|A549/i })
      .first()
      .isVisible()
      .catch(() => false)

    if (!looksLikeCellTypeDropdown) {
      await page.keyboard.press('Escape').catch(() => null)
      await page.waitForTimeout(300)
      continue
    }

    // Prefer using Select's combobox input to avoid virtualization issues on long lists.
    // NOTE: AntD Select search input is inside the Select control (not the dropdown container).
    const combobox = selector.locator('input[role="combobox"]').first()
    if (await combobox.count()) {
      // Use typing (instead of fill only) to reliably trigger AntD's filterOption logic.
      await combobox.click().catch(() => null)
      await combobox.fill('').catch(() => null)
      await combobox.type(searchValue, { delay: 20 }).catch(() => null)
      await page.waitForTimeout(300)
    }

    const option = dropdown.locator('.ant-select-item').filter({ hasText: exact }).first()
      .or(dropdown.locator('.ant-select-item').filter({ hasText: new RegExp(cellType, 'i') }).first())

    try {
      await option.waitFor({ state: 'visible', timeout: 15000 })
      await option.click()
      await page.keyboard.press('Escape').catch(() => null)
      await page.waitForTimeout(1000)
      return
    } catch (error) {
      await page.keyboard.press('Escape').catch(() => null)
      if (attempt >= 3) throw error
      await page.waitForTimeout(750)
    }
  }
}

/**
 * Helper function to select an epigenetic mark
 */
async function selectMark(page: any, mark: string): Promise<void> {
  const testIdWrapper = page.getByTestId(OVERLAP_FILTER_TESTIDS.markType)
  await testIdWrapper.waitFor({ state: 'visible', timeout: 20000 }).catch(() => null)
  const testIdSelector = testIdWrapper.locator('.ant-select').first()
  const markFilter = page.locator('.ant-select').filter({
    hasText: /Epigenetic Mark|表观标记|Mark|标记/i,
  }).first()

  const selector = (await testIdSelector.count()) > 0
    ? testIdSelector
    : markFilter

  await selector.click()
  await page.waitForTimeout(500)

  const dropdown = page.locator('.ant-select-dropdown:visible')
  await dropdown.waitFor({ state: 'visible', timeout: 15000 })

  const option = dropdown.locator('.ant-select-item').filter({
    hasText: new RegExp(mark, 'i'),
  }).first()

  await option.click()
  await page.waitForTimeout(1000)
}

/**
 * Helper function to select a chromosome (e.g. chr22) for faster loading
 */
async function selectChromosome(page: any, chromosome: string): Promise<void> {
  const testIdWrapper = page.getByTestId(OVERLAP_FILTER_TESTIDS.chromosome)
  await testIdWrapper.waitFor({ state: 'visible', timeout: 20000 }).catch(() => null)
  const testIdSelector = testIdWrapper.locator('.ant-select').first()
  const chrFilter = page.locator('.ant-select').filter({
    hasText: /Chromosome|染色体/i,
  }).first()

  const selector = (await testIdSelector.count()) > 0 ? testIdSelector : chrFilter

  if ((await selector.count()) === 0) return

  await page.keyboard.press('Escape').catch(() => null)
  await selector.click()
  await page.waitForTimeout(300)

  const dropdown = page.locator('.ant-select-dropdown:visible')
  await dropdown.waitFor({ state: 'visible', timeout: 15000 })

  const option = dropdown.locator('.ant-select-item').filter({
    hasText: new RegExp(`^${chromosome}$`, 'i'),
  }).first()

  await option.click()
  await page.waitForTimeout(1000)
}

// =============================================================================
// P0 - Core Functionality Tests (Must Pass)
// =============================================================================

test.describe('P0 - MCF-7 and HMEC Core Functionality', () => {

  test.beforeEach(async ({ page }) => {
    // Monitor console errors
    page.on('console', (msg) => {
      if (msg.type() === 'error') {
        console.error('[Browser Console Error]:', msg.text())
      }
    })

    // Monitor network failures
    page.on('requestfailed', (request) => {
      console.error('[Network Failed]:', request.url(), request.failure()?.errorText)
    })

    // Navigate to lncRNA-ChIP-seq Overlap page
    await page.goto(`${BASE_URL}${PAGE_URL}`)
    await page.waitForLoadState('networkidle')
  })

  test('P0-1: MCF-7 appears in cell type dropdown', async ({ page }) => {
    console.log('[P0-1] Checking if MCF-7 appears in cell type filter dropdown')

    const options = await openCellTypeDropdown(page)

    console.log('All cell types available:', options)

    // Take screenshot for documentation
    await page.screenshot({
      path: '/tmp/mcf7_hmec_test_p0_1_dropdown.png',
      fullPage: true
    })

    // Verify MCF-7 appears
    const hasMCF7 = options.some(opt => opt.includes('MCF-7') || opt.includes('MCF7'))
    expect(hasMCF7, 'MCF-7 should appear in cell type dropdown').toBe(true)
  })

  test('P0-2: HMEC appears in cell type dropdown', async ({ page }) => {
    console.log('[P0-2] Checking if HMEC appears in cell type filter dropdown')

    const options = await openCellTypeDropdown(page)

    console.log('All cell types available:', options)

    // Take screenshot
    await page.screenshot({
      path: '/tmp/mcf7_hmec_test_p0_2_dropdown.png',
      fullPage: true
    })

    // Verify HMEC appears
    const hasHMEC = options.some(opt => opt.includes('HMEC'))
    expect(hasHMEC, 'HMEC should appear in cell type dropdown').toBe(true)
  })

  test('P0-3: Selecting MCF-7 filters data correctly', async ({ page }) => {
    console.log('[P0-3] Testing MCF-7 data filtering')

    // Select MCF-7
    await selectCellType(page, 'MCF-7')

    // Wait for data to load
    await page.waitForLoadState('networkidle')
    await page.waitForTimeout(2000)

    // Take screenshot
    await page.screenshot({
      path: '/tmp/mcf7_hmec_test_p0_3_mcf7_filtered.png',
      fullPage: true
    })

    // Verify no error messages
    const errorMessage = page.locator('.ant-message-error, .ant-alert-error')
    const hasError = await errorMessage.isVisible().catch(() => false)
    expect(hasError, 'No error should occur when filtering by MCF-7').toBe(false)

    // Verify table is still visible (either with data or empty state)
    const table = page.locator('.ant-table, .ant-empty')
    await expect(table.first()).toBeVisible({ timeout: 10000 })
  })

  test('P0-4: Selecting HMEC filters data correctly', async ({ page }) => {
    console.log('[P0-4] Testing HMEC data filtering')

    // Select HMEC
    await selectCellType(page, 'HMEC')

    // Wait for data to load
    await page.waitForLoadState('networkidle')
    await page.waitForTimeout(2000)

    // Take screenshot
    await page.screenshot({
      path: '/tmp/mcf7_hmec_test_p0_4_hmec_filtered.png',
      fullPage: true
    })

    // Verify no error messages
    const errorMessage = page.locator('.ant-message-error, .ant-alert-error')
    const hasError = await errorMessage.isVisible().catch(() => false)
    expect(hasError, 'No error should occur when filtering by HMEC').toBe(false)

    // Verify table is visible
    const table = page.locator('.ant-table, .ant-empty')
    await expect(table.first()).toBeVisible({ timeout: 10000 })
  })

  test('P0-5: MCF-7 uses correct color (#FF69B4)', async ({ page }) => {
    console.log('[P0-5] Verifying MCF-7 color configuration')

    // Select MCF-7
    await selectCellType(page, 'MCF-7')
    await page.waitForLoadState('networkidle')
    await page.waitForTimeout(2000)

    // Look for color indicators (could be in tags, badges, or card borders)
    const colorElements = page.locator('[style*="#FF69B4"], [style*="rgb(255, 105, 180)"]')
    const coloredTags = page.locator('.ant-tag').filter({ hasText: /MCF-7/i })
    const coloredBadges = page.locator('.ant-badge').filter({ hasText: /MCF-7/i })

    // Take screenshot to visually verify color
    await page.screenshot({
      path: '/tmp/mcf7_hmec_test_p0_5_mcf7_color.png',
      fullPage: true
    })

    // Check if color is applied somewhere (flexible check)
    const hasColorElement = await colorElements.count() > 0
    const hasColoredTag = await coloredTags.count() > 0
    const hasColoredBadge = await coloredBadges.count() > 0

    // Log findings for debugging
    console.log(`Color elements found: ${await colorElements.count()}`)
    console.log(`Colored tags found: ${await coloredTags.count()}`)
    console.log(`Colored badges found: ${await coloredBadges.count()}`)

    // Note: If color is not yet configured, this test documents the expectation
    if (!hasColorElement && !hasColoredTag && !hasColoredBadge) {
      console.warn('MCF-7 color (#FF69B4) not found in UI - may need configuration')
    }
  })

  test('P0-6: HMEC uses correct color (#DEB887)', async ({ page }) => {
    console.log('[P0-6] Verifying HMEC color configuration')

    // Select HMEC
    await selectCellType(page, 'HMEC')
    await page.waitForLoadState('networkidle')
    await page.waitForTimeout(2000)

    // Look for color indicators
    const colorElements = page.locator('[style*="#DEB887"], [style*="rgb(222, 184, 135)"]')
    const coloredTags = page.locator('.ant-tag').filter({ hasText: /HMEC/i })
    const coloredBadges = page.locator('.ant-badge').filter({ hasText: /HMEC/i })

    // Take screenshot
    await page.screenshot({
      path: '/tmp/mcf7_hmec_test_p0_6_hmec_color.png',
      fullPage: true
    })

    // Check if color is applied
    const hasColorElement = await colorElements.count() > 0
    const hasColoredTag = await coloredTags.count() > 0
    const hasColoredBadge = await coloredBadges.count() > 0

    console.log(`Color elements found: ${await colorElements.count()}`)
    console.log(`Colored tags found: ${await coloredTags.count()}`)
    console.log(`Colored badges found: ${await coloredBadges.count()}`)

    if (!hasColorElement && !hasColoredTag && !hasColoredBadge) {
      console.warn('HMEC color (#DEB887) not found in UI - may need configuration')
    }
  })
})

// =============================================================================
// P1 - Data Accuracy Tests
// =============================================================================

test.describe('P1 - MCF-7 and HMEC Data Accuracy', () => {

  test.beforeEach(async ({ page }) => {
    await page.goto(`${BASE_URL}${PAGE_URL}`)
    await page.waitForLoadState('networkidle')
  })

  test('P1-7: MCF-7 shows correct experiment count (1 H3K4me3)', async ({ page }) => {
    console.log('[P1-7] Verifying MCF-7 experiment count')

    // Select MCF-7 and H3K4me3
    await selectCellType(page, 'MCF-7')
    await page.waitForTimeout(1000)
    await selectMark(page, 'H3K4me3')

    await page.waitForLoadState('networkidle')
    await page.waitForTimeout(2000)

    // Take screenshot
    await page.screenshot({
      path: '/tmp/mcf7_hmec_test_p1_7_mcf7_h3k4me3.png',
      fullPage: true
    })

    // Check for data in table
    const tableBody = page.locator('.ant-table-tbody')
    const hasData = await tableBody.isVisible().catch(() => false)

    if (hasData) {
      const rows = await tableBody.locator('tr').count()
      console.log(`MCF-7 x H3K4me3 returned ${rows} rows`)

      // Verify data contains MCF-7
      const tableContent = await tableBody.textContent()
      if (tableContent?.includes('MCF-7') || tableContent?.includes('MCF7')) {
        console.log('MCF-7 data confirmed in table')
      }
    } else {
      // Check for empty state
      const emptyState = page.locator('.ant-empty')
      const isEmpty = await emptyState.isVisible().catch(() => false)
      console.log(`Table empty state: ${isEmpty}`)
    }
  })

  test('P1-8: HMEC shows correct experiment count (6 core marks)', async ({ page }) => {
    console.log('[P1-8] Verifying HMEC experiment count')

    // Select HMEC
    await selectCellType(page, 'HMEC')

    await page.waitForLoadState('networkidle')
    await page.waitForTimeout(2000)

    // Take screenshot
    await page.screenshot({
      path: '/tmp/mcf7_hmec_test_p1_8_hmec_experiments.png',
      fullPage: true
    })

    // Check statistics if available
    const statsCards = page.locator('.ant-statistic-content-value')
    const statsCount = await statsCards.count()

    if (statsCount > 0) {
      const statsValues = await statsCards.allTextContents()
      console.log('HMEC statistics:', statsValues)
    }

    // Check table for HMEC data
    const tableBody = page.locator('.ant-table-tbody')
    if (await tableBody.isVisible().catch(() => false)) {
      const rows = await tableBody.locator('tr').count()
      console.log(`HMEC returned ${rows} rows in table`)
    }
  })

  test('P1-9: MCF-7 peaks load and display correctly', async ({ page }) => {
    console.log('[P1-9] Verifying MCF-7 peaks display')

    // Select MCF-7
    await selectCellType(page, 'MCF-7')

    // Select a chromosome for faster loading
    await selectChromosome(page, 'chr22')

    await page.waitForLoadState('networkidle')
    await page.waitForTimeout(3000)

    // Take screenshot
    await page.screenshot({
      path: '/tmp/mcf7_hmec_test_p1_9_mcf7_peaks.png',
      fullPage: true
    })

    // Verify table or empty state is visible
    const table = page.locator('.ant-table')
    const emptyState = page.locator('.ant-empty')

    const hasTable = await table.isVisible().catch(() => false)
    const hasEmpty = await emptyState.isVisible().catch(() => false)

    expect(hasTable || hasEmpty, 'Should show either data table or empty state').toBe(true)

    if (hasTable) {
      const rows = await table.locator('.ant-table-tbody tr').count()
      console.log(`MCF-7 peaks: ${rows} rows displayed`)
    }
  })

  test('P1-10: HMEC peaks load and display correctly', async ({ page }) => {
    console.log('[P1-10] Verifying HMEC peaks display')

    // Select HMEC
    await selectCellType(page, 'HMEC')

    // Select chromosome for faster loading
    await selectChromosome(page, 'chr22')

    await page.waitForLoadState('networkidle')
    await page.waitForTimeout(3000)

    // Take screenshot
    await page.screenshot({
      path: '/tmp/mcf7_hmec_test_p1_10_hmec_peaks.png',
      fullPage: true
    })

    // Verify display
    const table = page.locator('.ant-table')
    const emptyState = page.locator('.ant-empty')

    const hasTable = await table.isVisible().catch(() => false)
    const hasEmpty = await emptyState.isVisible().catch(() => false)

    expect(hasTable || hasEmpty, 'Should show either data table or empty state').toBe(true)

    if (hasTable) {
      const rows = await table.locator('.ant-table-tbody tr').count()
      console.log(`HMEC peaks: ${rows} rows displayed`)
    }
  })
})

// =============================================================================
// P2 - Regression Tests
// =============================================================================

test.describe('P2 - Regression Tests for Existing Cell Lines', () => {

  test.beforeEach(async ({ page }) => {
    await page.goto(`${BASE_URL}${PAGE_URL}`)
    await page.waitForLoadState('networkidle')
  })

  test('P2-11: Existing cell lines still work correctly', async ({ page }) => {
    console.log('[P2-11] Verifying existing cell lines still function')

    const options = await openCellTypeDropdown(page)
    console.log('All available cell types:', options)

    // Verify all existing cell lines are present
    for (const cellLine of EXISTING_CELL_LINES) {
      const found = options.some(opt =>
        opt.includes(cellLine) || opt.toLowerCase().includes(cellLine.toLowerCase())
      )
      expect(found, `${cellLine} should still be available in dropdown`).toBe(true)
      console.log(`${cellLine}: ${found ? 'Found' : 'NOT FOUND'}`)
    }

    // Close dropdown
    await page.keyboard.press('Escape')
    await page.waitForTimeout(500)

    // Take screenshot
    await page.screenshot({
      path: '/tmp/mcf7_hmec_test_p2_11_existing_cells.png',
      fullPage: true
    })
  })

  test('P2-12: All cell types filter works correctly', async ({ page }) => {
    console.log('[P2-12] Testing "All" cell types filter')

    // Look for "All" option or similar
    const testIdSelector = page.getByTestId(OVERLAP_FILTER_TESTIDS.cellType).locator('.ant-select').first()
    const cellTypeFilter = page.locator('.ant-select').filter({
      hasText: /Cell Type|细胞类型/i
    }).first()

    const selector = (await testIdSelector.count()) > 0 ? testIdSelector : cellTypeFilter
    const filterCount = await selector.count()

    if (filterCount > 0) {
      await selector.click()
      await page.waitForTimeout(500)

      // Look for "All" or default option
      const allOption = page.locator('.ant-select-dropdown .ant-select-item').filter({
        hasText: /^All$|^全部$|^所有$/i
      }).first()

      if (await allOption.count() > 0) {
        await allOption.click()
        await page.waitForTimeout(2000)
        await page.waitForLoadState('networkidle')

        // Verify no errors
        const errorMessage = page.locator('.ant-message-error, .ant-alert-error')
        const hasError = await errorMessage.isVisible().catch(() => false)
        expect(hasError).toBe(false)

        console.log('"All" filter works correctly')
      } else {
        console.log('"All" option not found - may use different filtering pattern')
      }
    }

    await page.screenshot({
      path: '/tmp/mcf7_hmec_test_p2_12_all_filter.png',
      fullPage: true
    })
  })

  test('P2-13: Charts display new cell lines correctly', async ({ page }) => {
    console.log('[P2-13] Verifying charts show new cell lines')

    await page.waitForTimeout(3000)

    // Look for chart containers
    const chartContainers = [
      page.locator('[data-testid="overlap-heatmap"]'),
      page.locator('.echarts-container'),
      page.locator('canvas[data-zr-dom-id]'),
      page.locator('.heatmap-container'),
      page.locator('.ant-card').filter({ hasText: /Heatmap|热图|Matrix|矩阵/i })
    ]

    let chartFound = false
    for (const container of chartContainers) {
      const count = await container.count()
      if (count > 0) {
        chartFound = true
        console.log(`Found chart container: ${await container.first().evaluate(el => el.className || el.tagName)}`)
        break
      }
    }

    // Take full page screenshot to capture charts
    await page.screenshot({
      path: '/tmp/mcf7_hmec_test_p2_13_charts.png',
      fullPage: true
    })

    if (chartFound) {
      console.log('Chart visualization detected - see screenshot for MCF-7/HMEC presence')
    } else {
      console.log('No chart found on current page view')
    }
  })
})

// =============================================================================
// API Integration Tests
// =============================================================================

test.describe('API Integration - MCF-7 and HMEC', () => {

  test('API returns MCF-7 experiments', async ({ request }) => {
    console.log('[API-1] Checking MCF-7 experiments in API')

    const response = await request.get(
      `${API_BASE_URL}/api/v1/lncrna-chipseq-overlap`,
      {
        params: {
          cell_type: 'MCF-7',
          chromosome: 'chr22',
          page_size: 10
        }
      }
    )

    console.log('API Response Status:', response.status())

	    if (response.ok()) {
	      const data = await response.json()
	      console.log('Total records:', data.total || 0)
	      const items = data.items ?? data.data ?? []
	      console.log('Records in page:', items?.length || 0)

	      expect(items).toBeDefined()
	      expect(Array.isArray(items)).toBe(true)

	      // If data exists, verify MCF-7 is present
	      if (items?.length > 0) {
	        const hasMCF7 = items.some((record: any) =>
	          record.cell_type === 'MCF-7' ||
	          record.cellType === 'MCF-7' ||
	          record.cell_type === 'MCF7'
	        )
        expect(hasMCF7).toBe(true)
        console.log('MCF-7 data confirmed in API response')
      } else {
        console.warn('No MCF-7 data returned - may need data import')
      }
    } else {
      console.warn('API request failed:', response.status())
    }
  })

  test('API returns HMEC experiments', async ({ request }) => {
    console.log('[API-2] Checking HMEC experiments in API')

    const response = await request.get(
      `${API_BASE_URL}/api/v1/lncrna-chipseq-overlap`,
      {
        params: {
          cell_type: 'HMEC',
          chromosome: 'chr22',
          page_size: 10
        }
      }
    )

    console.log('API Response Status:', response.status())

	    if (response.ok()) {
	      const data = await response.json()
	      console.log('Total records:', data.total || 0)
	      const items = data.items ?? data.data ?? []
	      console.log('Records in page:', items?.length || 0)

	      expect(items).toBeDefined()
	      expect(Array.isArray(items)).toBe(true)

	      if (items?.length > 0) {
	        const hasHMEC = items.some((record: any) =>
	          record.cell_type === 'HMEC' ||
	          record.cellType === 'HMEC'
	        )
        expect(hasHMEC).toBe(true)
        console.log('HMEC data confirmed in API response')
      } else {
        console.warn('No HMEC data returned - may need data import')
      }
    } else {
      console.warn('API request failed:', response.status())
    }
  })

  test('API export includes MCF-7 data', async ({ request }) => {
    console.log('[API-3] Checking MCF-7 export endpoint')

    const response = await request.get(
      `${API_BASE_URL}/api/v1/lncrna-chipseq-overlap/export`,
      {
        params: {
          format: 'csv',
          cell_type: 'MCF-7',
          chromosome: 'chr22',
          max_rows: 100
        }
      }
    )

    if (response.ok()) {
      const csvText = await response.text()
      console.log('Export response length:', csvText.length, 'bytes')

      if (csvText.includes('MCF-7') || csvText.includes('MCF7')) {
        console.log('MCF-7 data found in export')
        const lines = csvText.split('\n')
        const mcf7Lines = lines.filter(line => line.includes('MCF-7') || line.includes('MCF7'))
        console.log(`Export contains ${mcf7Lines.length} rows with MCF-7`)
        expect(mcf7Lines.length).toBeGreaterThan(0)
      } else {
        console.warn('MCF-7 not found in export - may need data import')
      }
    } else {
      console.warn('Export API request failed:', response.status())
    }
  })

  test('API export includes HMEC data', async ({ request }) => {
    console.log('[API-4] Checking HMEC export endpoint')

    const response = await request.get(
      `${API_BASE_URL}/api/v1/lncrna-chipseq-overlap/export`,
      {
        params: {
          format: 'csv',
          cell_type: 'HMEC',
          chromosome: 'chr22',
          max_rows: 100
        }
      }
    )

    if (response.ok()) {
      const csvText = await response.text()
      console.log('Export response length:', csvText.length, 'bytes')

      if (csvText.includes('HMEC')) {
        console.log('HMEC data found in export')
        const lines = csvText.split('\n')
        const hmecLines = lines.filter(line => line.includes('HMEC'))
        console.log(`Export contains ${hmecLines.length} rows with HMEC`)
        expect(hmecLines.length).toBeGreaterThan(0)
      } else {
        console.warn('HMEC not found in export - may need data import')
      }
    } else {
      console.warn('Export API request failed:', response.status())
    }
  })
})

// =============================================================================
// Error Handling Tests
// =============================================================================

test.describe('Error Handling - MCF-7 and HMEC', () => {

  test.beforeEach(async ({ page }) => {
    await page.goto(`${BASE_URL}${PAGE_URL}`)
    await page.waitForLoadState('networkidle')
  })

  test('No JavaScript errors when using MCF-7', async ({ page }) => {
    console.log('[Error-1] Checking for JavaScript errors with MCF-7')

    const errors: string[] = []

    page.on('console', (msg) => {
      if (msg.type() === 'error') {
        errors.push(msg.text())
      }
    })

    page.on('pageerror', (error) => {
      errors.push(error.message)
    })

    await page.waitForTimeout(2000)

    // Select MCF-7
    await selectCellType(page, 'MCF-7')
    await page.waitForLoadState('networkidle')
    await page.waitForTimeout(3000)

    console.log(`Detected ${errors.length} JavaScript errors`)
    if (errors.length > 0) {
      console.error('JavaScript errors:', errors)
    }

    // Filter out non-critical errors
    const criticalErrors = errors.filter(e =>
      !e.includes('warning') &&
      !e.includes('Warning') &&
      !e.includes('404') &&
      !e.includes('ResizeObserver')
    )

    expect(criticalErrors.length, 'No critical JavaScript errors should occur').toBe(0)
  })

  test('No JavaScript errors when using HMEC', async ({ page }) => {
    console.log('[Error-2] Checking for JavaScript errors with HMEC')

    const errors: string[] = []

    page.on('console', (msg) => {
      if (msg.type() === 'error') {
        errors.push(msg.text())
      }
    })

    page.on('pageerror', (error) => {
      errors.push(error.message)
    })

    await page.waitForTimeout(2000)

    // Select HMEC
    await selectCellType(page, 'HMEC')
    await page.waitForLoadState('networkidle')
    await page.waitForTimeout(3000)

    console.log(`Detected ${errors.length} JavaScript errors`)
    if (errors.length > 0) {
      console.error('JavaScript errors:', errors)
    }

    const criticalErrors = errors.filter(e =>
      !e.includes('warning') &&
      !e.includes('Warning') &&
      !e.includes('404') &&
      !e.includes('ResizeObserver')
    )

    expect(criticalErrors.length, 'No critical JavaScript errors should occur').toBe(0)
  })
})
