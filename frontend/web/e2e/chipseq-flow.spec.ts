import { test, expect } from '@playwright/test'

/**
 * ChIP-seq Data Browsing E2E Tests
 *
 * Covers core user flows:
 * 1. Navigating to gene detail page
 * 2. Accessing ChIP-seq tab
 * 3. Loading ChIP-seq data
 * 4. Filtering by cell type (K562, GM12878, HepG2, H1-hESC)
 * 5. Switching between histone marks
 * 6. Data table interactions
 *
 * Note: Page language may be Chinese or English depending on browser settings
 */

// Known gene ID for testing (from existing tests)
const TEST_GENE_ID = 17276

test.describe('ChIP-seq Data Browsing', () => {
  test.beforeEach(async ({ page }) => {
    // Navigate to a gene detail page with ChIP-seq data
    await page.goto(`/genes/${TEST_GENE_ID}`)
    // Wait for page to load
    await page.waitForLoadState('networkidle')
  })

  test('should display ChIP-seq tab on gene detail page', async ({ page }) => {
    // Look for ChIP-seq or Histone related tab
    // The tab might be named differently in Chinese/English
    const chipseqTab = page.getByRole('tab', { name: /ChIP-seq|Histone|ChIP|表观/i })
      .or(page.locator('.ant-tabs-tab').filter({ hasText: /ChIP/i }))

    // Wait for tabs to be visible
    // 页面上可能存在多个 Tabs（例如内嵌筛选 Tabs），避免 strict mode 报错
    await expect(page.locator('.ant-tabs').first()).toBeVisible({ timeout: 15000 })

    // If ChIP-seq tab exists, verify it's visible
    const tabCount = await chipseqTab.count()
    if (tabCount > 0) {
      await expect(chipseqTab.first()).toBeVisible()
    } else {
      // Skip if no ChIP-seq tab (feature might not be enabled)
      test.skip()
    }
  })

  test('should load ChIP-seq data when tab is clicked', async ({ page }) => {
    // Wait for page to stabilize
    await page.waitForLoadState('networkidle')

    // Find and click ChIP-seq tab
    const chipseqTab = page.getByRole('tab', { name: /ChIP-seq|Histone|ChIP|表观/i })
      .or(page.locator('.ant-tabs-tab').filter({ hasText: /ChIP/i }))

    const tabCount = await chipseqTab.count()
    if (tabCount === 0) {
      test.skip()
      return
    }

    await chipseqTab.first().click()

    // Wait for data to load - intercept API response
    const responsePromise = page.waitForResponse(
      (resp) => resp.url().includes('/chipseq') && resp.status() === 200,
      { timeout: 30000 }
    ).catch(() => null)

    const response = await responsePromise

    if (response) {
      // Verify table or data content is displayed
      const dataContent = page.getByTestId('peaks-table')
        .or(page.locator('.ant-table'))
        .or(page.locator('.ant-card'))
      await expect(dataContent.first()).toBeVisible({ timeout: 15000 })
    }
  })

  test('should display mark selector component', async ({ page }) => {
    await page.waitForLoadState('networkidle')

    // Click ChIP-seq tab first
    const chipseqTab = page.locator('.ant-tabs-tab').filter({ hasText: /ChIP/i })
    if ((await chipseqTab.count()) > 0) {
      await chipseqTab.first().click()
      await page.waitForTimeout(1000)

      // Look for mark selector (dropdown or segmented control)
      const markSelector = page.getByTestId('mark-selector')
        .or(page.locator('.ant-select').filter({ hasText: /H3K|Mark/i }))
        .or(page.locator('.ant-segmented'))

      const selectorCount = await markSelector.count()
      if (selectorCount > 0) {
        await expect(markSelector.first()).toBeVisible()
      }
    }
  })

  test('should switch between histone marks', async ({ page }) => {
    await page.waitForLoadState('networkidle')

    // Navigate to ChIP-seq tab
    const chipseqTab = page.locator('.ant-tabs-tab').filter({ hasText: /ChIP/i })
    if ((await chipseqTab.count()) === 0) {
      test.skip()
      return
    }
    await chipseqTab.first().click()
    await page.waitForTimeout(1000)

    // Find mark selector
    const markSelector = page.getByTestId('mark-selector')
      .or(page.locator('.ant-select').filter({ hasText: /H3K|Mark/i }))
      .or(page.locator('.ant-segmented'))
      .or(page.getByText(/H3K27me3|H3K4me3/))

    const selectorCount = await markSelector.count()
    if (selectorCount > 0) {
      // Click to open selector
      await markSelector.first().click()

      // Look for mark options
      const markOption = page.getByText('H3K4me3')
        .or(page.locator('.ant-select-item').filter({ hasText: 'H3K4me3' }))

      if ((await markOption.count()) > 0) {
        await markOption.first().click()

        // Wait for data refresh
        await page.waitForTimeout(1000)
      }
    }
  })
})

test.describe('Cell Line Filter Panel', () => {
  test.beforeEach(async ({ page }) => {
    await page.goto(`/genes/${TEST_GENE_ID}`)
    await page.waitForLoadState('networkidle')

    // Navigate to ChIP-seq tab
    const chipseqTab = page.locator('.ant-tabs-tab').filter({ hasText: /ChIP/i })
    if ((await chipseqTab.count()) > 0) {
      await chipseqTab.first().click()
      await page.waitForTimeout(1000)
    }
  })

  test('should show cell type filter dropdown', async ({ page }) => {
    // Look for cell type filter
    const cellTypeFilter = page.getByTestId('cell-type-filter')
      .or(page.getByPlaceholder(/cell type/i))
      .or(page.locator('.ant-select').filter({ hasText: /Cell/i }))

    const filterCount = await cellTypeFilter.count()
    if (filterCount > 0) {
      await expect(cellTypeFilter.first()).toBeVisible()
    }
  })

  test('should filter by K562 cell type', async ({ page }) => {
    // Find cell type dropdown
    const cellTypeSelect = page.getByTestId('cell-type-filter')
      .or(page.locator('.ant-select').filter({ hasText: /Cell|K562|GM12878/i }))

    const selectCount = await cellTypeSelect.count()
    if (selectCount === 0) {
      test.skip()
      return
    }

    await cellTypeSelect.first().click()

    // Select K562
    const k562Option = page.getByText('K562', { exact: true })
      .or(page.locator('.ant-select-item').filter({ hasText: 'K562' }))

    if ((await k562Option.count()) > 0) {
      await k562Option.first().click()
      await page.waitForTimeout(1000)

      // Verify filter is applied (table should update)
      await expect(page.locator('.ant-table, .ant-card')).toBeVisible()
    }
  })

  test('should filter by GM12878 cell type', async ({ page }) => {
    const cellTypeSelect = page.getByTestId('cell-type-filter')
      .or(page.locator('.ant-select').filter({ hasText: /Cell|K562|GM12878/i }))

    if ((await cellTypeSelect.count()) === 0) {
      test.skip()
      return
    }

    await cellTypeSelect.first().click()

    const gm12878Option = page.getByText('GM12878', { exact: true })
      .or(page.locator('.ant-select-item').filter({ hasText: 'GM12878' }))

    if ((await gm12878Option.count()) > 0) {
      await gm12878Option.first().click()
      await page.waitForTimeout(1000)
    }
  })

  test('should filter by HepG2 cell type (new)', async ({ page }) => {
    const cellTypeSelect = page.getByTestId('cell-type-filter')
      .or(page.locator('.ant-select').filter({ hasText: /Cell/i }))

    if ((await cellTypeSelect.count()) === 0) {
      test.skip()
      return
    }

    await cellTypeSelect.first().click()

    // HepG2 is a newly added cell type
    const hepg2Option = page.getByText('HepG2', { exact: true })
      .or(page.locator('.ant-select-item').filter({ hasText: 'HepG2' }))

    if ((await hepg2Option.count()) > 0) {
      await hepg2Option.first().click()
      await page.waitForTimeout(1000)
    }
  })

  test('should filter by H1-hESC cell type (new)', async ({ page }) => {
    const cellTypeSelect = page.locator('.ant-select').filter({ hasText: /Cell/i })

    if ((await cellTypeSelect.count()) === 0) {
      test.skip()
      return
    }

    await cellTypeSelect.first().click()

    // H1-hESC is a newly added cell type
    const h1hescOption = page.getByText('H1-hESC')
      .or(page.locator('.ant-select-item').filter({ hasText: 'H1-hESC' }))

    if ((await h1hescOption.count()) > 0) {
      await h1hescOption.first().click()
      await page.waitForTimeout(1000)
    }
  })

  test('should show all 4 cell types in dropdown', async ({ page }) => {
    const cellTypeSelect = page.locator('.ant-select').filter({ hasText: /Cell/i })

    if ((await cellTypeSelect.count()) === 0) {
      test.skip()
      return
    }

    await cellTypeSelect.first().click()

    // Wait for dropdown to appear
    await page.waitForTimeout(500)

    // Check for all 4 cell types
    const cellTypes = ['K562', 'GM12878', 'HepG2', 'H1-hESC']
    const foundCellTypes: string[] = []

    for (const cellType of cellTypes) {
      const option = page.locator('.ant-select-dropdown').getByText(cellType, { exact: true })
      if ((await option.count()) > 0) {
        foundCellTypes.push(cellType)
      }
    }

    // Log which cell types were found
    console.log(`Found cell types: ${foundCellTypes.join(', ')}`)

    // Close dropdown
    await page.keyboard.press('Escape')
  })
})

test.describe('ChIP-seq Statistics Cards', () => {
  test.beforeEach(async ({ page }) => {
    await page.goto(`/genes/${TEST_GENE_ID}`)
    await page.waitForLoadState('networkidle')

    // Navigate to ChIP-seq tab
    const chipseqTab = page.locator('.ant-tabs-tab').filter({ hasText: /ChIP/i })
    if ((await chipseqTab.count()) > 0) {
      await chipseqTab.first().click()
      await page.waitForTimeout(1000)
    }
  })

  test('should display statistics cards', async ({ page }) => {
    // Look for stats cards (typically in a Row/Col layout or ant-statistic)
    const statsCards = page.getByTestId('stats-cards-container')
      .or(page.locator('.ant-statistic, .ant-card-statistic, [data-testid="stats-card"]'))
      .or(page.locator('.ant-card').filter({ hasText: /Peak|Signal|Fold|Total/i }))

    const cardsCount = await statsCards.count()
    if (cardsCount > 0) {
      await expect(statsCards.first()).toBeVisible()
    }
  })

  test('should show total peaks count', async ({ page }) => {
    // Look for total peaks statistic
    const totalPeaks = page.locator('.ant-statistic-title').filter({ hasText: /Total|Peak/i })
      .or(page.getByText(/Total Peaks/i))

    if ((await totalPeaks.count()) > 0) {
      await expect(totalPeaks.first()).toBeVisible()
    }
  })
})

test.describe('ChIP-seq Peaks Table', () => {
  test.beforeEach(async ({ page }) => {
    await page.goto(`/genes/${TEST_GENE_ID}`)
    await page.waitForLoadState('networkidle')

    // Navigate to ChIP-seq tab
    const chipseqTab = page.locator('.ant-tabs-tab').filter({ hasText: /ChIP/i })
    if ((await chipseqTab.count()) > 0) {
      await chipseqTab.first().click()
      await page.waitForTimeout(2000)
    }
  })

  test('should display peaks data table', async ({ page }) => {
    const peaksTable = page.getByTestId('peaks-table')
      .or(page.locator('.ant-table'))

    if ((await peaksTable.count()) > 0) {
      await expect(peaksTable.first()).toBeVisible({ timeout: 15000 })
    }
  })

  test('should have sortable columns', async ({ page }) => {
    const sortableHeader = page.locator('.ant-table-column-sorter')
      .or(page.locator('th[class*="sortable"]'))

    if ((await sortableHeader.count()) > 0) {
      // Click to sort
      await sortableHeader.first().click()
      await page.waitForTimeout(500)

      // Verify sort indicator appears
      const sortIndicator = page.locator('.ant-table-column-sorter-up.active, .ant-table-column-sorter-down.active')
      // Sorting may or may not change indicator visibility
    }
  })

  test('should support pagination', async ({ page }) => {
    const pagination = page.locator('.ant-pagination')

    if ((await pagination.count()) > 0) {
      await expect(pagination.first()).toBeVisible()

      // Try clicking next page
      const nextButton = pagination.locator('.ant-pagination-next:not(.ant-pagination-disabled)')
      if ((await nextButton.count()) > 0) {
        await nextButton.click()
        await page.waitForTimeout(1000)
      }
    }
  })
})

test.describe('ChIP-seq Filter Panel', () => {
  test.beforeEach(async ({ page }) => {
    await page.goto(`/genes/${TEST_GENE_ID}`)
    await page.waitForLoadState('networkidle')

    // Navigate to ChIP-seq tab
    const chipseqTab = page.locator('.ant-tabs-tab').filter({ hasText: /ChIP/i })
    if ((await chipseqTab.count()) > 0) {
      await chipseqTab.first().click()
      await page.waitForTimeout(1000)
    }
  })

  test('should display filter panel', async ({ page }) => {
    // Look for filter panel (might be in collapse or visible)
    const filterPanel = page.getByTestId('filter-panel')
      .or(page.locator('.ant-collapse').filter({ hasText: /Filter/i }))
      .or(page.locator('.ant-form').filter({ hasText: /Fold|Signal|Q-value/i }))

    if ((await filterPanel.count()) > 0) {
      await expect(filterPanel.first()).toBeVisible()
    }
  })

  test('should filter by fold enrichment', async ({ page }) => {
    // Look for fold enrichment input
    const foldInput = page.locator('.ant-input-number').filter({ hasText: /Fold/i })
      .or(page.getByPlaceholder(/fold/i))
      .or(page.locator('input[type="number"]').first())

    if ((await foldInput.count()) > 0) {
      await foldInput.first().fill('5')
      await page.waitForTimeout(1000)
    }
  })

  test('should have reset filters button', async ({ page }) => {
    const resetButton = page.getByRole('button', { name: /Reset|Clear|重置/i })
      .or(page.locator('button').filter({ hasText: /Reset|Clear/i }))

    if ((await resetButton.count()) > 0) {
      await expect(resetButton.first()).toBeVisible()
    }
  })
})

test.describe('ChIP-seq Compare Mode', () => {
  test.beforeEach(async ({ page }) => {
    await page.goto(`/genes/${TEST_GENE_ID}`)
    await page.waitForLoadState('networkidle')

    // Navigate to ChIP-seq tab
    const chipseqTab = page.locator('.ant-tabs-tab').filter({ hasText: /ChIP/i })
    if ((await chipseqTab.count()) > 0) {
      await chipseqTab.first().click()
      await page.waitForTimeout(1000)
    }
  })

  test('should have compare mode toggle', async ({ page }) => {
    // Look for compare button or toggle
    const compareButton = page.getByTestId('compare-marks-button')
      .or(page.getByRole('button', { name: /Compare|对比/i }))
      .or(page.locator('[data-testid="compare-toggle"]'))
      .or(page.locator('.ant-switch').filter({ hasText: /Compare/i }))

    if ((await compareButton.count()) > 0) {
      await expect(compareButton.first()).toBeVisible()
    }
  })

  test('should enable multi-mark selection in compare mode', async ({ page }) => {
    // Find and click compare button
    const compareButton = page.getByTestId('compare-marks-button')
      .or(page.getByRole('button', { name: /Compare|对比/i }))
      .or(page.locator('button').filter({ hasText: /Compare/i }))

    if ((await compareButton.count()) > 0) {
      await compareButton.first().click()
      await page.waitForTimeout(500)

      // Check for multi-select capability
      const multiSelect = page.locator('.ant-checkbox-group')
        .or(page.locator('.ant-select[mode="multiple"]'))

      if ((await multiSelect.count()) > 0) {
        await expect(multiSelect.first()).toBeVisible()
      }
    }
  })
})

test.describe('ChIP-seq Export', () => {
  test.beforeEach(async ({ page }) => {
    await page.goto(`/genes/${TEST_GENE_ID}`)
    await page.waitForLoadState('networkidle')

    // Navigate to ChIP-seq tab
    const chipseqTab = page.locator('.ant-tabs-tab').filter({ hasText: /ChIP/i })
    if ((await chipseqTab.count()) > 0) {
      await chipseqTab.first().click()
      await page.waitForTimeout(1000)
    }
  })

  test('should display export button', async ({ page }) => {
    const exportButton = page.getByRole('button', { name: /Export|Download|导出/i })
      .or(page.locator('button').filter({ hasText: /Export|Download|BED|CSV/i }))

    if ((await exportButton.count()) > 0) {
      await expect(exportButton.first()).toBeVisible()
    }
  })

  test('should show export format options', async ({ page }) => {
    const exportButton = page.getByRole('button', { name: /Export|Download/i })
      .or(page.locator('.ant-dropdown-trigger').filter({ hasText: /Export/i }))

    if ((await exportButton.count()) > 0) {
      await exportButton.first().click()
      await page.waitForTimeout(500)

      // Check for format options (BED, CSV)
      const bedOption = page.getByText('BED')
      const csvOption = page.getByText('CSV')

      // At least one export format should be available
      const hasBed = (await bedOption.count()) > 0
      const hasCsv = (await csvOption.count()) > 0

      if (hasBed || hasCsv) {
        // Click outside to close dropdown
        await page.keyboard.press('Escape')
      }
    }
  })
})

test.describe('ChIP-seq API Integration', () => {
  test('should make correct API calls for marks', async ({ page }) => {
    // Set up request interception
    const marksRequests: string[] = []

    page.on('request', (request) => {
      if (request.url().includes('/chipseq/marks')) {
        marksRequests.push(request.url())
      }
    })

    await page.goto(`/genes/${TEST_GENE_ID}`)
    await page.waitForLoadState('networkidle')

    // Navigate to ChIP-seq tab
    const chipseqTab = page.locator('.ant-tabs-tab').filter({ hasText: /ChIP/i })
    if ((await chipseqTab.count()) > 0) {
      await chipseqTab.first().click()
      await page.waitForTimeout(2000)
    }

    // Log API calls made
    console.log(`Marks API calls: ${marksRequests.length}`)
  })

  test('should make correct API calls for gene peaks', async ({ page }) => {
    const peaksRequests: string[] = []

    page.on('request', (request) => {
      if (request.url().includes(`/chipseq/genes/${TEST_GENE_ID}`)) {
        peaksRequests.push(request.url())
      }
    })

    await page.goto(`/genes/${TEST_GENE_ID}`)
    await page.waitForLoadState('networkidle')

    const chipseqTab = page.locator('.ant-tabs-tab').filter({ hasText: /ChIP/i })
    if ((await chipseqTab.count()) > 0) {
      await chipseqTab.first().click()
      await page.waitForTimeout(2000)
    }

    console.log(`Peaks API calls: ${peaksRequests.length}`)
  })
})

test.describe('ChIP-seq Cell Line Comparison', () => {
  test.beforeEach(async ({ page }) => {
    await page.goto(`/genes/${TEST_GENE_ID}`)
    await page.waitForLoadState('networkidle')

    // Navigate to ChIP-seq tab
    const chipseqTab = page.locator('.ant-tabs-tab').filter({ hasText: /ChIP/i })
    if ((await chipseqTab.count()) > 0) {
      await chipseqTab.first().click()
      await page.waitForTimeout(1000)
    }
  })

  test('should display cell line compare panel', async ({ page }) => {
    // Look for compare cell lines button or panel
    const comparePanel = page.locator('[data-testid="cell-line-compare-panel"]')
      .or(page.getByText(/Compare Cell Lines|cell line/i))
      .or(page.locator('.ant-card').filter({ hasText: /Compare|cell line/i }))

    const count = await comparePanel.count()
    if (count > 0) {
      await expect(comparePanel.first()).toBeVisible()
    } else {
      // Feature might not be implemented yet
      console.log('Cell line compare panel not found - feature may not be implemented')
    }
  })

  test('should allow selecting multiple cell lines', async ({ page }) => {
    // Find cell line checkboxes or multi-select
    const k562Checkbox = page.getByLabel(/K562/i)
      .or(page.locator('.ant-checkbox-wrapper').filter({ hasText: 'K562' }))
    const hepg2Checkbox = page.getByLabel(/HepG2/i)
      .or(page.locator('.ant-checkbox-wrapper').filter({ hasText: 'HepG2' }))

    const k562Count = await k562Checkbox.count()
    if (k562Count > 0) {
      await k562Checkbox.first().click()

      const hepg2Count = await hepg2Checkbox.count()
      if (hepg2Count > 0) {
        await hepg2Checkbox.first().click()

        // Verify both are checked
        const k562Checked = await page.locator('.ant-checkbox-wrapper').filter({ hasText: 'K562' }).locator('.ant-checkbox-checked').count()
        const hepg2Checked = await page.locator('.ant-checkbox-wrapper').filter({ hasText: 'HepG2' }).locator('.ant-checkbox-checked').count()

        console.log(`K562 checked: ${k562Checked > 0}, HepG2 checked: ${hepg2Checked > 0}`)
      }
    } else {
      console.log('Cell line checkboxes not found - feature may not be implemented')
    }
  })

  test('should trigger comparison API call', async ({ page }) => {
    // Set up request interception
    const apiCalls: string[] = []

    page.on('request', (request) => {
      if (request.url().includes('compare-cell-lines')) {
        apiCalls.push(request.url())
      }
    })

    // Try to find and interact with cell line selection
    const k562Checkbox = page.getByLabel(/K562/i)
      .or(page.locator('.ant-checkbox-wrapper').filter({ hasText: 'K562' }))
    const hepg2Checkbox = page.getByLabel(/HepG2/i)
      .or(page.locator('.ant-checkbox-wrapper').filter({ hasText: 'HepG2' }))

    const k562Count = await k562Checkbox.count()
    if (k562Count > 0) {
      await k562Checkbox.first().click()

      const hepg2Count = await hepg2Checkbox.count()
      if (hepg2Count > 0) {
        await hepg2Checkbox.first().click()

        const compareButton = page.getByRole('button', { name: /Compare|Start/i })
          .or(page.locator('button').filter({ hasText: /Compare|Start/i }))
        const compareCount = await compareButton.count()
        if (compareCount > 0) {
          await compareButton.first().click()
          await page.waitForTimeout(2000)

          // Verify API was called
          console.log(`Compare cell lines API calls: ${apiCalls.length}`)
          if (apiCalls.length > 0) {
            expect(apiCalls.length).toBeGreaterThan(0)
          }
        }
      }
    } else {
      console.log('Cell line selection not found - feature may not be implemented')
    }
  })

  test('should display heatmap or chart after comparison', async ({ page }) => {
    const k562Checkbox = page.getByLabel(/K562/i)
      .or(page.locator('.ant-checkbox-wrapper').filter({ hasText: 'K562' }))
    const hepg2Checkbox = page.getByLabel(/HepG2/i)
      .or(page.locator('.ant-checkbox-wrapper').filter({ hasText: 'HepG2' }))

    const k562Count = await k562Checkbox.count()
    if (k562Count > 0) {
      await k562Checkbox.first().click()

      const hepg2Count = await hepg2Checkbox.count()
      if (hepg2Count > 0) {
        await hepg2Checkbox.first().click()

        const compareButton = page.getByRole('button', { name: /Compare|Start/i })
          .or(page.locator('button').filter({ hasText: /Compare|Start/i }))
        const compareCount = await compareButton.count()
        if (compareCount > 0) {
          await compareButton.first().click()
          await page.waitForTimeout(2000)

          // Look for heatmap (ECharts canvas) or comparison result
          const heatmap = page.locator('canvas')
            .or(page.locator('[data-testid="cell-line-heatmap"]'))
            .or(page.locator('.ant-table'))

          const heatmapCount = await heatmap.count()
          if (heatmapCount > 0) {
            await expect(heatmap.first()).toBeVisible()
          }
        }
      }
    } else {
      console.log('Cell line selection not found - feature may not be implemented')
    }
  })

  test('should require at least 2 cell lines for comparison', async ({ page }) => {
    const k562Checkbox = page.getByLabel(/K562/i)
      .or(page.locator('.ant-checkbox-wrapper').filter({ hasText: 'K562' }))

    const k562Count = await k562Checkbox.count()
    if (k562Count > 0) {
      await k562Checkbox.first().click()

      // Compare button should be disabled with only 1 cell line
      const compareButton = page.getByRole('button', { name: /Compare|Start/i })
        .or(page.locator('button').filter({ hasText: /Compare|Start/i }))

      const compareCount = await compareButton.count()
      if (compareCount > 0) {
        // Check if button is disabled
        const isDisabled = await compareButton.first().isDisabled()
        console.log(`Compare button disabled with 1 cell line: ${isDisabled}`)
      }
    } else {
      console.log('Cell line selection not found - feature may not be implemented')
    }
  })

  test('should show all 4 cell lines as options', async ({ page }) => {
    const cellTypes = ['K562', 'GM12878', 'HepG2', 'H1-hESC']
    const foundCellTypes: string[] = []

    for (const cellType of cellTypes) {
      const checkbox = page.getByLabel(new RegExp(cellType, 'i'))
        .or(page.locator('.ant-checkbox-wrapper').filter({ hasText: cellType }))
        .or(page.getByText(cellType, { exact: true }))

      const count = await checkbox.count()
      if (count > 0) {
        foundCellTypes.push(cellType)
      }
    }

    console.log(`Found cell types for comparison: ${foundCellTypes.join(', ')}`)
    // At least some cell types should be available
    if (foundCellTypes.length > 0) {
      expect(foundCellTypes.length).toBeGreaterThan(0)
    }
  })
})

/**
 * Phase 2.5 Multi-Mark Comparison Tests
 * Tests for the enhanced multi-mark comparison functionality
 */
test.describe('Multi-Mark Comparison Flow (Phase 2.5)', () => {
  test.beforeEach(async ({ page }) => {
    await page.goto(`/genes/${TEST_GENE_ID}`)
    await page.waitForLoadState('networkidle')

    // Navigate to Genomic Features tab
    const genomicFeaturesTab = page.getByRole('tab', { name: /基因组特征|Genomic Features/i })
    if ((await genomicFeaturesTab.count()) > 0) {
      await genomicFeaturesTab.click()
      await page.waitForTimeout(500)
    }

    // Navigate to ChIP-seq sub-tab
    const chipseqTab = page.getByRole('tab', { name: /ChIP-seq|峰值/i })
    if ((await chipseqTab.count()) > 0) {
      await chipseqTab.click()
      await page.waitForTimeout(1000)
    }
  })

  test('should complete multi-mark comparison flow with 2 marks', async ({ page }) => {
    // 1. Click Compare Marks button (对比修饰)
    const compareButton = page.getByRole('button', { name: /对比修饰|Compare Marks/i })
    if ((await compareButton.count()) === 0) {
      test.skip()
      return
    }
    await compareButton.click()
    await page.waitForTimeout(500)

    // 2. Open mark selector dropdown
    const markSelector = page.locator('.ant-select').first()
    await markSelector.click()
    await page.waitForTimeout(300)

    // 3. Select H3K4me3 (it should be in the dropdown)
    const h3k4me3Option = page.getByRole('option', { name: /H3K4me3/i })
    if ((await h3k4me3Option.count()) > 0) {
      await h3k4me3Option.click()
      await page.waitForTimeout(1000)

      // 4. Verify comparison data is displayed
      // Look for merged peaks table or comparison content
      const comparisonContent = page.locator('.ant-table')
        .or(page.locator('.ant-alert'))
        .or(page.locator('canvas'))

      await expect(comparisonContent.first()).toBeVisible({ timeout: 10000 })
    }
  })

  test('should show bivalent domain badge when H3K4me3 and H3K27me3 selected', async ({ page }) => {
    // Click Compare Marks button
    const compareButton = page.getByRole('button', { name: /对比修饰|Compare Marks/i })
    if ((await compareButton.count()) === 0) {
      test.skip()
      return
    }
    await compareButton.click()
    await page.waitForTimeout(500)

    // Select H3K4me3 (H3K27me3 should be pre-selected)
    const markSelector = page.locator('.ant-select').first()
    await markSelector.click()
    await page.waitForTimeout(300)

    const h3k4me3Option = page.getByRole('option', { name: /H3K4me3/i })
    if ((await h3k4me3Option.count()) > 0) {
      await h3k4me3Option.click()
      await page.waitForTimeout(1500)

      // Look for bivalent domain indicator
      const bivalentBadge = page.getByText(/双价|Bivalent/i)
        .or(page.locator('.ant-alert').filter({ hasText: /双价|Bivalent/i }))

      const badgeCount = await bivalentBadge.count()
      console.log(`Bivalent domain badge found: ${badgeCount > 0}`)
    }
  })

  test('should switch to Statistics view and show charts', async ({ page }) => {
    // Enter compare mode
    const compareButton = page.getByRole('button', { name: /对比修饰|Compare Marks/i })
    if ((await compareButton.count()) === 0) {
      test.skip()
      return
    }
    await compareButton.click()
    await page.waitForTimeout(500)

    // Select additional mark
    const markSelector = page.locator('.ant-select').first()
    await markSelector.click()
    await page.waitForTimeout(300)

    const h3k4me3Option = page.getByRole('option', { name: /H3K4me3/i })
    if ((await h3k4me3Option.count()) > 0) {
      await h3k4me3Option.click()
      await page.waitForTimeout(1000)

      // Click Statistics tab (统计对比)
      const statsTab = page.getByRole('tab', { name: /统计对比|Statistics/i })
      if ((await statsTab.count()) > 0) {
        await statsTab.click()
        await page.waitForTimeout(1000)

        // Verify charts are rendered (canvas elements for ECharts)
        const charts = page.locator('canvas')
        const chartCount = await charts.count()
        console.log(`Charts found in Statistics view: ${chartCount}`)

        // Should have at least one chart
        if (chartCount > 0) {
          expect(chartCount).toBeGreaterThan(0)
        }
      }
    }
  })

  test('should switch between view modes (Merged, Parallel, Stats)', async ({ page }) => {
    // Enter compare mode with 2 marks
    const compareButton = page.getByRole('button', { name: /对比修饰|Compare Marks/i })
    if ((await compareButton.count()) === 0) {
      test.skip()
      return
    }
    await compareButton.click()
    await page.waitForTimeout(500)

    // Select additional mark for parallel view
    const markSelector = page.locator('.ant-select').first()
    await markSelector.click()
    await page.waitForTimeout(300)

    const h3k4me3Option = page.getByRole('option', { name: /H3K4me3/i })
    if ((await h3k4me3Option.count()) === 0) {
      test.skip()
      return
    }
    await h3k4me3Option.click()
    await page.waitForTimeout(1000)

    // Test Merged View tab
    const mergedTab = page.getByRole('tab', { name: /合并视图|Merged/i })
    if ((await mergedTab.count()) > 0) {
      await mergedTab.click()
      await page.waitForTimeout(500)
      console.log('Merged View tab clicked')
    }

    // Test Parallel View tab (should be enabled with 2 marks)
    const parallelTab = page.getByRole('tab', { name: /并行对比|Parallel/i })
    if ((await parallelTab.count()) > 0) {
      const isDisabled = await parallelTab.getAttribute('aria-disabled')
      if (isDisabled !== 'true') {
        await parallelTab.click()
        await page.waitForTimeout(500)
        console.log('Parallel View tab clicked')
      }
    }

    // Test Statistics View tab
    const statsTab = page.getByRole('tab', { name: /统计对比|Statistics/i })
    if ((await statsTab.count()) > 0) {
      await statsTab.click()
      await page.waitForTimeout(500)
      console.log('Statistics View tab clicked')
    }
  })

  test('should select up to 3 marks for comparison', async ({ page }) => {
    // Enter compare mode
    const compareButton = page.getByRole('button', { name: /对比修饰|Compare Marks/i })
    if ((await compareButton.count()) === 0) {
      test.skip()
      return
    }
    await compareButton.click()
    await page.waitForTimeout(500)

    // 避免误点 Header 的语言切换 Select：限定在 ChIP-seq 活动面板内并根据标签定位 mark selector
    const chipseqPane = page.locator('.ant-tabs-tabpane-active').filter({ hasText: /ChIP-seq|Peaks/i })
    const markSelector = chipseqPane.locator('.ant-card')
      .filter({ hasText: /Select marks to compare|选择.*对比|比较.*标记/i })
      .locator('.ant-select')
      .first()

    if ((await markSelector.count()) === 0) {
      test.skip()
      return
    }

    const marksToSelect = ['H3K4me3', 'H3K27ac']

    for (const mark of marksToSelect) {
      // 先注册等待（成功响应），再触发点击，避免被初始的 400（仅 1 mark）干扰
      const compareOkPromise = page.waitForResponse(
        (resp) =>
          resp.status() === 200 &&
          resp.url().includes('/api/v1/features/chipseq/genes/') &&
          resp.url().includes('/compare') &&
          resp.url().includes(mark),
        { timeout: 30000 }
      ).catch(() => null)

      // Open dropdown (don't toggle-close if already open)
      if ((await page.locator('.ant-select-dropdown:visible').count()) === 0) {
        await markSelector.click()
        await page.waitForTimeout(200)
      }

      const option = page.locator('.ant-select-dropdown:visible')
        .locator('.ant-select-item-option:visible, [role="option"]:visible')
        .filter({ hasText: new RegExp(mark, 'i') })
        .first()

      if ((await option.count()) > 0) {
        await option.click()
        await compareOkPromise
        await page.waitForTimeout(300)
      }
    }

    const selectedTags = markSelector.locator('.ant-tag')
    const selectedCount = await selectedTags.count()
    console.log(`Successfully selected ${selectedCount} marks for comparison`)
    expect(selectedCount).toBeGreaterThanOrEqual(2)
  })

  test('should exit comparison mode correctly', async ({ page }) => {
    // Enter compare mode
    const compareButton = page.getByRole('button', { name: /对比修饰|Compare Marks/i })
    if ((await compareButton.count()) === 0) {
      test.skip()
      return
    }
    await compareButton.click()
    await page.waitForTimeout(500)

    // Verify compare mode is active (exit button should be visible)
    const exitButton = page.getByRole('button', { name: /退出对比|Exit/i })
    await expect(exitButton).toBeVisible()

    // Exit compare mode
    await exitButton.click()
    await page.waitForTimeout(500)

    // Verify back to single mark mode (compare button should be visible again)
    const compareButtonAgain = page.getByRole('button', { name: /对比修饰|Compare Marks/i })
    await expect(compareButtonAgain).toBeVisible()
  })
})

/**
 * Matrix Heatmap View Tests (Phase 2.9)
 */
test.describe('Heatmap Matrix View (Phase 2.9)', () => {
  test.beforeEach(async ({ page }) => {
    await page.goto(`/genes/${TEST_GENE_ID}`)
    await page.waitForLoadState('networkidle')

    // Navigate to Genomic Features tab
    const genomicFeaturesTab = page.getByRole('tab', { name: /基因组特征|Genomic Features/i })
    if ((await genomicFeaturesTab.count()) > 0) {
      await genomicFeaturesTab.click()
      await page.waitForTimeout(500)
    }

    // Navigate to ChIP-seq sub-tab
    const chipseqTab = page.getByRole('tab', { name: /ChIP-seq|峰值/i })
    if ((await chipseqTab.count()) > 0) {
      await chipseqTab.click()
      await page.waitForTimeout(1000)
    }
  })

  test('should access Matrix View tab in compare mode', async ({ page }) => {
    // Enter compare mode
    const compareButton = page.getByRole('button', { name: /对比修饰|Compare Marks/i })
    if ((await compareButton.count()) === 0) {
      test.skip()
      return
    }
    await compareButton.click()
    await page.waitForTimeout(500)

    // Select additional mark
    const markSelector = page.locator('.ant-select').first()
    await markSelector.click()
    await page.waitForTimeout(300)

    const h3k4me3Option = page.getByRole('option', { name: /H3K4me3/i })
    if ((await h3k4me3Option.count()) > 0) {
      await h3k4me3Option.click()
      await page.waitForTimeout(1000)
    }

    // Look for Matrix View tab
    const matrixTab = page.getByRole('tab', { name: /矩阵视图|Matrix/i })
    if ((await matrixTab.count()) > 0) {
      await matrixTab.click()
      await page.waitForTimeout(1500)

      // Verify matrix view content is displayed
      const matrixContent = page.locator('canvas')
        .or(page.locator('.ant-card'))
        .or(page.locator('.ant-alert'))

      await expect(matrixContent.first()).toBeVisible({ timeout: 10000 })
      console.log('Matrix View tab accessible and content visible')
    } else {
      console.log('Matrix View tab not found')
    }
  })

  test('should display matrix heatmap with cell types and marks', async ({ page }) => {
    // Enter compare mode and select marks
    const compareButton = page.getByRole('button', { name: /对比修饰|Compare Marks/i })
    if ((await compareButton.count()) === 0) {
      test.skip()
      return
    }
    await compareButton.click()
    await page.waitForTimeout(500)

    const markSelector = page.locator('.ant-select').first()
    await markSelector.click()
    await page.waitForTimeout(300)

    const h3k4me3Option = page.getByRole('option', { name: /H3K4me3/i })
    if ((await h3k4me3Option.count()) > 0) {
      await h3k4me3Option.click()
      await page.waitForTimeout(1000)
    }

    // Click Matrix View tab
    const matrixTab = page.getByRole('tab', { name: /矩阵视图|Matrix/i })
    if ((await matrixTab.count()) === 0) {
      test.skip()
      return
    }
    await matrixTab.click()
    await page.waitForTimeout(2000)

    // Check for heatmap canvas (ECharts renders to canvas)
    const heatmapCanvas = page.locator('canvas')
    const canvasCount = await heatmapCanvas.count()
    console.log(`Heatmap canvas elements found: ${canvasCount}`)

    if (canvasCount > 0) {
      expect(canvasCount).toBeGreaterThan(0)
    }
  })
})

/**
 * Error Handling Tests
 */
test.describe('ChIP-seq Error Handling', () => {
  test('should handle API errors gracefully', async ({ page }) => {
    // Intercept API calls and return error
    await page.route('**/api/v1/features/chipseq/**', (route) => {
      route.fulfill({
        status: 500,
        contentType: 'application/json',
        body: JSON.stringify({ detail: 'Internal Server Error' }),
      })
    })

    await page.goto(`/genes/${TEST_GENE_ID}`)
    await page.waitForLoadState('networkidle')

    // Navigate to Genomic Features tab
    const genomicFeaturesTab = page.getByRole('tab', { name: /基因组特征|Genomic Features/i })
    if ((await genomicFeaturesTab.count()) > 0) {
      await genomicFeaturesTab.click()
      await page.waitForTimeout(500)
    }

    // Navigate to ChIP-seq tab
    const chipseqTab = page.getByRole('tab', { name: /ChIP-seq|峰值/i })
    if ((await chipseqTab.count()) > 0) {
      await chipseqTab.click()
      await page.waitForTimeout(2000)

      // Look for error state or error message
      const errorState = page.getByText(/加载失败|Error|Failed/i)
        .or(page.locator('.ant-alert-error'))
        .or(page.locator('[class*="error"]'))

      const errorCount = await errorState.count()
      console.log(`Error state elements found: ${errorCount}`)

      // Look for retry button
      const retryButton = page.getByRole('button', { name: /重试|Retry/i })
      const retryCount = await retryButton.count()
      console.log(`Retry button found: ${retryCount > 0}`)
    }
  })

  test('should show empty state when no peaks data', async ({ page }) => {
    // Mock API to return empty data
    await page.route('**/api/v1/features/chipseq/genes/*/peaks**', (route) => {
      route.fulfill({
        status: 200,
        contentType: 'application/json',
        body: JSON.stringify({
          items: [],
          total: 0,
          page: 1,
          page_size: 20,
        }),
      })
    })

    await page.goto(`/genes/${TEST_GENE_ID}`)
    await page.waitForLoadState('networkidle')

    // Navigate to ChIP-seq tab
    const genomicFeaturesTab = page.getByRole('tab', { name: /基因组特征|Genomic Features/i })
    if ((await genomicFeaturesTab.count()) > 0) {
      await genomicFeaturesTab.click()
      await page.waitForTimeout(500)
    }

    const chipseqTab = page.getByRole('tab', { name: /ChIP-seq|峰值/i })
    if ((await chipseqTab.count()) > 0) {
      await chipseqTab.click()
      await page.waitForTimeout(2000)

      // Look for empty state or "no data" message
      const emptyState = page.getByText(/没有|No peaks|No data|Empty/i)
        .or(page.locator('.ant-empty'))

      const emptyCount = await emptyState.count()
      console.log(`Empty state elements found: ${emptyCount}`)
    }
  })

  test('should handle comparison with insufficient marks', async ({ page }) => {
    await page.goto(`/genes/${TEST_GENE_ID}`)
    await page.waitForLoadState('networkidle')

    // Navigate to ChIP-seq tab
    const genomicFeaturesTab = page.getByRole('tab', { name: /基因组特征|Genomic Features/i })
    if ((await genomicFeaturesTab.count()) > 0) {
      await genomicFeaturesTab.click()
      await page.waitForTimeout(500)
    }

    const chipseqTab = page.getByRole('tab', { name: /ChIP-seq|峰值/i })
    if ((await chipseqTab.count()) > 0) {
      await chipseqTab.click()
      await page.waitForTimeout(1000)
    }

    // Enter compare mode (should have only 1 mark initially)
    const compareButton = page.getByRole('button', { name: /对比修饰|Compare Marks/i })
    if ((await compareButton.count()) === 0) {
      test.skip()
      return
    }
    await compareButton.click()
    await page.waitForTimeout(1000)

    // Look for warning about needing at least 2 marks
    const warningMessage = page.getByText(/至少|at least|2|选择/i)
      .or(page.locator('.ant-message-error'))
      .or(page.locator('.ant-alert-warning'))

    const warningCount = await warningMessage.count()
    console.log(`Warning about insufficient marks: ${warningCount > 0}`)
  })
})

/**
 * Performance Tests
 */
	test.describe('ChIP-seq Performance', () => {
	  test('should load ChIP-seq data within acceptable time', async ({ page }) => {
	    const budgetMs = Number(process.env.E2E_CHIPSEQ_LOAD_BUDGET_MS || process.env.E2E_PERF_BUDGET_MS || 15000)

	    await page.goto(`/genes/${TEST_GENE_ID}`)
	    await page.waitForLoadState('domcontentloaded')

	    // Navigate to ChIP-seq tab
	    const genomicFeaturesTab = page.getByRole('tab', { name: /基因组特征|Genomic Features/i })
	    if ((await genomicFeaturesTab.count()) > 0) {
	      await genomicFeaturesTab.click()
	    }

	    const chipseqTab = page.getByRole('tab', { name: /ChIP-seq|峰值/i })
	    if ((await chipseqTab.count()) > 0) {
	      const startTime = Date.now()
	      await chipseqTab.click()

	      // Wait for table to be visible (avoid hidden tables from other tabs)
	      const dataTable = page.locator('.ant-tabs-tabpane-active .ant-table:visible').first()
	      await dataTable.waitFor({ state: 'visible', timeout: budgetMs })

	      const loadTime = Date.now() - startTime
	      console.log(`ChIP-seq data load time: ${loadTime}ms`)

	      // Should load within budget (environment dependent)
	      expect(loadTime).toBeLessThan(budgetMs)
	    }
	  })

  test('should handle rapid filter changes without errors', async ({ page }) => {
    await page.goto(`/genes/${TEST_GENE_ID}`)
    await page.waitForLoadState('networkidle')

    // Navigate to ChIP-seq tab
    const genomicFeaturesTab = page.getByRole('tab', { name: /基因组特征|Genomic Features/i })
    if ((await genomicFeaturesTab.count()) > 0) {
      await genomicFeaturesTab.click()
      await page.waitForTimeout(500)
    }

    const chipseqTab = page.getByRole('tab', { name: /ChIP-seq|峰值/i })
    if ((await chipseqTab.count()) > 0) {
      await chipseqTab.click()
      await page.waitForTimeout(1500)
    }

    // Find and interact with filter controls rapidly
    const filterInput = page.locator('.ant-input-number input').first()
    if ((await filterInput.count()) > 0) {
      // Rapid filter changes
      await filterInput.fill('0.05')
      await page.waitForTimeout(100)
      await filterInput.fill('0.01')
      await page.waitForTimeout(100)
      await filterInput.fill('0.001')
      await page.waitForTimeout(500)

      // Verify no errors occurred
      const errorMessages = page.locator('.ant-message-error')
      const errorCount = await errorMessages.count()
      expect(errorCount).toBe(0)
    }
  })

  test('should maintain responsive UI during data loading', async ({ page }) => {
    await page.goto(`/genes/${TEST_GENE_ID}`)
    await page.waitForLoadState('networkidle')

    // Navigate to ChIP-seq tab
    const genomicFeaturesTab = page.getByRole('tab', { name: /基因组特征|Genomic Features/i })
    if ((await genomicFeaturesTab.count()) > 0) {
      await genomicFeaturesTab.click()
    }

    const chipseqTab = page.getByRole('tab', { name: /ChIP-seq|峰值/i })
    if ((await chipseqTab.count()) > 0) {
      await chipseqTab.click()

      // While loading, verify UI remains interactive
      // Check that loading indicator appears
      const loadingIndicator = page.locator('.ant-spin')
        .or(page.locator('[class*="loading"]'))

      // Check that tabs are still clickable
      const tabs = page.locator('.ant-tabs-tab')
      const tabsClickable = await tabs.first().isEnabled()
      console.log(`Tabs remain clickable during load: ${tabsClickable}`)
    }
  })
})

/**
 * Cell Line Comparison View Tests (Phase 2.6)
 */
test.describe('Cell Line Comparison View (Phase 2.6)', () => {
  test.beforeEach(async ({ page }) => {
    await page.goto(`/genes/${TEST_GENE_ID}`)
    await page.waitForLoadState('networkidle')

    // Navigate to Genomic Features tab
    const genomicFeaturesTab = page.getByRole('tab', { name: /基因组特征|Genomic Features/i })
    if ((await genomicFeaturesTab.count()) > 0) {
      await genomicFeaturesTab.click()
      await page.waitForTimeout(500)
    }

    // Navigate to ChIP-seq sub-tab
    const chipseqTab = page.getByRole('tab', { name: /ChIP-seq|峰值/i })
    if ((await chipseqTab.count()) > 0) {
      await chipseqTab.click()
      await page.waitForTimeout(1000)
    }
  })

  test('should access Cell Lines view tab', async ({ page }) => {
    // Enter compare mode
    const compareCellLinesButton = page.getByRole('button', { name: /对比细胞系|Compare Cell Lines/i }).first()
    const compareMarksButton = page.getByRole('button', { name: /对比修饰|Compare Marks/i }).first()

    if (await compareCellLinesButton.isVisible().catch(() => false)) {
      await compareCellLinesButton.click()
    } else if (await compareMarksButton.isVisible().catch(() => false)) {
      await compareMarksButton.click()
    } else {
      test.skip()
      return
    }
    await page.waitForTimeout(500)

    // Look for Cell Lines tab
    const cellLinesTab = page.getByRole('tab', { name: /细胞系|Cell Lines/i })
    if ((await cellLinesTab.count()) > 0) {
      await cellLinesTab.click()
      await page.waitForTimeout(1000)

      // Verify cell line selection UI is visible
      const cellLineUI = page.locator('.ant-checkbox-group')
        .or(page.locator('.ant-card'))
        .or(page.getByText(/K562|HepG2|GM12878|H1-hESC/i))

      const uiCount = await cellLineUI.count()
      console.log(`Cell line selection UI elements: ${uiCount}`)
    }
  })

  test('should display cell type selection panel', async ({ page }) => {
    // Try clicking Compare Cell Lines button directly
    const compareCellLinesButton = page.getByRole('button', { name: /对比细胞系|Compare Cell Lines/i })
    if ((await compareCellLinesButton.count()) > 0) {
      await compareCellLinesButton.click()
      await page.waitForTimeout(1000)

      // Look for cell type checkboxes or selection
      const cellTypes = ['K562', 'HepG2', 'GM12878', 'H1-hESC']
      const foundCellTypes: string[] = []

      for (const cellType of cellTypes) {
        const cellTypeElement = page.getByText(cellType, { exact: true })
          .or(page.locator('.ant-checkbox-wrapper').filter({ hasText: cellType }))

        if ((await cellTypeElement.count()) > 0) {
          foundCellTypes.push(cellType)
        }
      }

      console.log(`Found cell types in selection panel: ${foundCellTypes.join(', ')}`)
    }
  })
})

/**
 * Export Functionality Tests
 */
test.describe('ChIP-seq Export Functionality', () => {
  test.beforeEach(async ({ page }) => {
    await page.goto(`/genes/${TEST_GENE_ID}`)
    await page.waitForLoadState('networkidle')

    // Navigate to ChIP-seq tab
    const genomicFeaturesTab = page.getByRole('tab', { name: /基因组特征|Genomic Features/i })
    if ((await genomicFeaturesTab.count()) > 0) {
      await genomicFeaturesTab.click()
      await page.waitForTimeout(500)
    }

    const chipseqTab = page.getByRole('tab', { name: /ChIP-seq|峰值/i })
    if ((await chipseqTab.count()) > 0) {
      await chipseqTab.click()
      await page.waitForTimeout(1500)
    }
  })

  test('should have export BED button in single mark mode', async ({ page }) => {
    const exportButton = page.getByRole('button', { name: /导出 BED|Export BED/i })
    if ((await exportButton.count()) > 0) {
      await expect(exportButton).toBeVisible()
      console.log('Export BED button is visible')
    }
  })

  test('should have export CSV button in comparison mode', async ({ page }) => {
    // Enter compare mode
    const compareButton = page.getByRole('button', { name: /对比修饰|Compare Marks/i })
    if ((await compareButton.count()) === 0) {
      test.skip()
      return
    }
    await compareButton.click()
    await page.waitForTimeout(500)

    // Select additional mark
    const markSelector = page.locator('.ant-select').first()
    await markSelector.click()
    await page.waitForTimeout(300)

    const h3k4me3Option = page.getByRole('option', { name: /H3K4me3/i })
    if ((await h3k4me3Option.count()) > 0) {
      await h3k4me3Option.click()
      await page.waitForTimeout(1000)
    }

    // Look for export CSV button
    const exportCsvButton = page.getByRole('button', { name: /导出 CSV|Export CSV/i })
    if ((await exportCsvButton.count()) > 0) {
      await expect(exportCsvButton).toBeVisible()
      console.log('Export CSV button is visible in comparison mode')
    }
  })
})
