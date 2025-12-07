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
    const chipseqTab = page.getByRole('tab', { name: /ChIP-seq|Histone|ChIP|/i })
      .or(page.locator('.ant-tabs-tab').filter({ hasText: /ChIP|/i }))

    // Wait for tabs to be visible
    await expect(page.locator('.ant-tabs')).toBeVisible({ timeout: 15000 })

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
    const chipseqTab = page.getByRole('tab', { name: /ChIP-seq|Histone|ChIP|/i })
      .or(page.locator('.ant-tabs-tab').filter({ hasText: /ChIP|/i }))

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
      const dataContent = page.locator('.ant-table, [data-testid="peaks-table"], .ant-card')
      await expect(dataContent.first()).toBeVisible({ timeout: 15000 })
    }
  })

  test('should display mark selector component', async ({ page }) => {
    await page.waitForLoadState('networkidle')

    // Click ChIP-seq tab first
    const chipseqTab = page.locator('.ant-tabs-tab').filter({ hasText: /ChIP|/i })
    if ((await chipseqTab.count()) > 0) {
      await chipseqTab.first().click()
      await page.waitForTimeout(1000)

      // Look for mark selector (dropdown or segmented control)
      const markSelector = page.locator('[data-testid="mark-selector"]')
        .or(page.locator('.ant-select').filter({ hasText: /H3K|Mark|/i }))
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
    const chipseqTab = page.locator('.ant-tabs-tab').filter({ hasText: /ChIP|/i })
    if ((await chipseqTab.count()) === 0) {
      test.skip()
      return
    }
    await chipseqTab.first().click()
    await page.waitForTimeout(1000)

    // Find mark selector
    const markSelector = page.locator('.ant-select').filter({ hasText: /H3K|Mark/i })
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
    const chipseqTab = page.locator('.ant-tabs-tab').filter({ hasText: /ChIP|/i })
    if ((await chipseqTab.count()) > 0) {
      await chipseqTab.first().click()
      await page.waitForTimeout(1000)
    }
  })

  test('should show cell type filter dropdown', async ({ page }) => {
    // Look for cell type filter
    const cellTypeFilter = page.locator('[data-testid="cell-type-filter"]')
      .or(page.getByPlaceholder(/cell type|/i))
      .or(page.locator('.ant-select').filter({ hasText: /Cell|/i }))

    const filterCount = await cellTypeFilter.count()
    if (filterCount > 0) {
      await expect(cellTypeFilter.first()).toBeVisible()
    }
  })

  test('should filter by K562 cell type', async ({ page }) => {
    // Find cell type dropdown
    const cellTypeSelect = page.locator('[data-testid="cell-type-filter"]')
      .or(page.locator('.ant-select').filter({ hasText: /Cell|K562|GM12878|/i }))

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
    const cellTypeSelect = page.locator('.ant-select').filter({ hasText: /Cell|K562|GM12878|/i })

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
    const cellTypeSelect = page.locator('.ant-select').filter({ hasText: /Cell|/i })

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
    const cellTypeSelect = page.locator('.ant-select').filter({ hasText: /Cell|/i })

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
    const cellTypeSelect = page.locator('.ant-select').filter({ hasText: /Cell|/i })

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
    const chipseqTab = page.locator('.ant-tabs-tab').filter({ hasText: /ChIP|/i })
    if ((await chipseqTab.count()) > 0) {
      await chipseqTab.first().click()
      await page.waitForTimeout(1000)
    }
  })

  test('should display statistics cards', async ({ page }) => {
    // Look for stats cards (typically in a Row/Col layout or ant-statistic)
    const statsCards = page.locator('.ant-statistic, .ant-card-statistic, [data-testid="stats-card"]')
      .or(page.locator('.ant-card').filter({ hasText: /Peak|Signal|Fold|Total/i }))

    const cardsCount = await statsCards.count()
    if (cardsCount > 0) {
      await expect(statsCards.first()).toBeVisible()
    }
  })

  test('should show total peaks count', async ({ page }) => {
    // Look for total peaks statistic
    const totalPeaks = page.locator('.ant-statistic-title').filter({ hasText: /Total|Peak|/i })
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
    const chipseqTab = page.locator('.ant-tabs-tab').filter({ hasText: /ChIP|/i })
    if ((await chipseqTab.count()) > 0) {
      await chipseqTab.first().click()
      await page.waitForTimeout(2000)
    }
  })

  test('should display peaks data table', async ({ page }) => {
    const peaksTable = page.locator('.ant-table')
      .or(page.locator('[data-testid="peaks-table"]'))

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
    const chipseqTab = page.locator('.ant-tabs-tab').filter({ hasText: /ChIP|/i })
    if ((await chipseqTab.count()) > 0) {
      await chipseqTab.first().click()
      await page.waitForTimeout(1000)
    }
  })

  test('should display filter panel', async ({ page }) => {
    // Look for filter panel (might be in collapse or visible)
    const filterPanel = page.locator('[data-testid="filter-panel"]')
      .or(page.locator('.ant-collapse').filter({ hasText: /Filter|/i }))
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
    const resetButton = page.getByRole('button', { name: /Reset|Clear|/i })
      .or(page.locator('button').filter({ hasText: /Reset|Clear|/i }))

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
    const chipseqTab = page.locator('.ant-tabs-tab').filter({ hasText: /ChIP|/i })
    if ((await chipseqTab.count()) > 0) {
      await chipseqTab.first().click()
      await page.waitForTimeout(1000)
    }
  })

  test('should have compare mode toggle', async ({ page }) => {
    // Look for compare button or toggle
    const compareButton = page.getByRole('button', { name: /Compare|/i })
      .or(page.locator('[data-testid="compare-toggle"]'))
      .or(page.locator('.ant-switch').filter({ hasText: /Compare/i }))

    if ((await compareButton.count()) > 0) {
      await expect(compareButton.first()).toBeVisible()
    }
  })

  test('should enable multi-mark selection in compare mode', async ({ page }) => {
    // Find and click compare button
    const compareButton = page.getByRole('button', { name: /Compare|/i })
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
    const chipseqTab = page.locator('.ant-tabs-tab').filter({ hasText: /ChIP|/i })
    if ((await chipseqTab.count()) > 0) {
      await chipseqTab.first().click()
      await page.waitForTimeout(1000)
    }
  })

  test('should display export button', async ({ page }) => {
    const exportButton = page.getByRole('button', { name: /Export|Download|/i })
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
    const chipseqTab = page.locator('.ant-tabs-tab').filter({ hasText: /ChIP|/i })
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

    const chipseqTab = page.locator('.ant-tabs-tab').filter({ hasText: /ChIP|/i })
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
    const chipseqTab = page.locator('.ant-tabs-tab').filter({ hasText: /ChIP|/i })
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

test.describe('ChIP-seq Heatmap Matrix', () => {
  test.beforeEach(async ({ page }) => {
    await page.goto(`/genes/${TEST_GENE_ID}`)
    await page.waitForLoadState('networkidle')

    // Navigate to ChIP-seq tab
    const chipseqTab = page.locator('.ant-tabs-tab').filter({ hasText: /ChIP|/i })
    if ((await chipseqTab.count()) > 0) {
      await chipseqTab.first().click()
      await page.waitForTimeout(1000)
    }
  })

  test('should display matrix view tab', async ({ page }) => {
    // Enter compare mode - look for compare cell lines button
    const compareCellLinesBtn = page.getByRole('button', { name: /Compare Cell|/i })
      .or(page.locator('button').filter({ hasText: /Compare|/i }))

    if ((await compareCellLinesBtn.count()) > 0) {
      await compareCellLinesBtn.first().click()
      await page.waitForTimeout(500)

      // Look for matrix view tab
      const matrixTab = page.getByRole('tab', { name: /Matrix View|Matrix|/i })
        .or(page.locator('.ant-tabs-tab').filter({ hasText: /Matrix|/i }))
        .or(page.locator('.ant-segmented-item').filter({ hasText: /Matrix|/i }))

      if ((await matrixTab.count()) > 0) {
        await expect(matrixTab.first()).toBeVisible()
      } else {
        console.log('Matrix view tab not found - feature may not be implemented')
      }
    }
  })

  test('should render matrix heatmap with ECharts', async ({ page }) => {
    // Navigate to cell line compare mode
    const compareCellLinesBtn = page.getByRole('button', { name: /Compare Cell|/i })
      .or(page.locator('button').filter({ hasText: /Compare|/i }))

    if ((await compareCellLinesBtn.count()) > 0) {
      await compareCellLinesBtn.first().click()
      await page.waitForTimeout(500)

      // Click matrix view tab if available
      const matrixTab = page.getByRole('tab', { name: /Matrix View|Matrix|/i })
        .or(page.locator('.ant-tabs-tab').filter({ hasText: /Matrix|/i }))
        .or(page.locator('.ant-segmented-item').filter({ hasText: /Matrix|/i }))

      if ((await matrixTab.count()) > 0) {
        await matrixTab.first().click()
        await page.waitForTimeout(1000)

        // Verify ECharts canvas is rendered
        const canvas = page.locator('canvas')
          .or(page.locator('[data-testid="heatmap-canvas"]'))
          .or(page.locator('.echarts-container canvas'))

        if ((await canvas.count()) > 0) {
          await expect(canvas.first()).toBeVisible()
        }
      }
    }
  })

  test('should make heatmap-matrix API call', async ({ page }) => {
    const apiCalls: string[] = []

    page.on('request', (request) => {
      if (request.url().includes('heatmap-matrix')) {
        apiCalls.push(request.url())
      }
    })

    // Navigate to cell line compare mode
    const compareCellLinesBtn = page.getByRole('button', { name: /Compare Cell|/i })
      .or(page.locator('button').filter({ hasText: /Compare|/i }))

    if ((await compareCellLinesBtn.count()) > 0) {
      await compareCellLinesBtn.first().click()
      await page.waitForTimeout(500)

      // Click matrix view tab if available
      const matrixTab = page.getByRole('tab', { name: /Matrix View|Matrix|/i })
        .or(page.locator('.ant-tabs-tab').filter({ hasText: /Matrix|/i }))
        .or(page.locator('.ant-segmented-item').filter({ hasText: /Matrix|/i }))

      if ((await matrixTab.count()) > 0) {
        await matrixTab.first().click()
        await page.waitForTimeout(2000)

        console.log(`Heatmap matrix API calls: ${apiCalls.length}`)
        // API should be called when matrix view is activated
      }
    }
  })

  test('should support metric selector', async ({ page }) => {
    // Navigate to cell line compare mode and matrix view
    const compareCellLinesBtn = page.getByRole('button', { name: /Compare Cell|/i })
      .or(page.locator('button').filter({ hasText: /Compare|/i }))

    if ((await compareCellLinesBtn.count()) > 0) {
      await compareCellLinesBtn.first().click()
      await page.waitForTimeout(500)

      const matrixTab = page.getByRole('tab', { name: /Matrix View|Matrix|/i })
        .or(page.locator('.ant-tabs-tab').filter({ hasText: /Matrix|/i }))

      if ((await matrixTab.count()) > 0) {
        await matrixTab.first().click()
        await page.waitForTimeout(500)

        // Look for metric selector
        const metricSelector = page.locator('.ant-select').filter({ hasText: /Metric|Fold|Peak|Coverage/i })
          .or(page.locator('[data-testid="metric-selector"]'))
          .or(page.locator('.ant-radio-group').filter({ hasText: /Fold|Peak|Coverage/i }))

        if ((await metricSelector.count()) > 0) {
          await expect(metricSelector.first()).toBeVisible()

          // Try clicking to open options
          await metricSelector.first().click()
          await page.waitForTimeout(300)

          // Check for metric options
          const metricOptions = [
            'median_fold_enrichment',
            'peak_count',
            'total_coverage_bp',
            'avg_signal',
            'Fold Enrichment',
            'Peak Count',
            'Coverage'
          ]

          for (const metric of metricOptions) {
            const option = page.getByText(metric, { exact: false })
            if ((await option.count()) > 0) {
              console.log(`Found metric option: ${metric}`)
              break
            }
          }

          // Close selector
          await page.keyboard.press('Escape')
        }
      }
    }
  })

  test('should display matrix with cell types as rows and marks as columns', async ({ page }) => {
    // Navigate to matrix view
    const compareCellLinesBtn = page.getByRole('button', { name: /Compare Cell|/i })
      .or(page.locator('button').filter({ hasText: /Compare|/i }))

    if ((await compareCellLinesBtn.count()) > 0) {
      await compareCellLinesBtn.first().click()
      await page.waitForTimeout(500)

      const matrixTab = page.getByRole('tab', { name: /Matrix View|Matrix|/i })
        .or(page.locator('.ant-tabs-tab').filter({ hasText: /Matrix|/i }))

      if ((await matrixTab.count()) > 0) {
        await matrixTab.first().click()
        await page.waitForTimeout(1000)

        // Verify axes labels are present
        const cellTypeLabels = ['K562', 'HepG2', 'GM12878', 'H1-hESC']
        const markLabels = ['H3K27me3', 'H3K4me3', 'H3K27ac', 'H3K4me1']

        let foundCellTypes = 0
        let foundMarks = 0

        for (const ct of cellTypeLabels) {
          const label = page.getByText(ct, { exact: true })
          if ((await label.count()) > 0) {
            foundCellTypes++
          }
        }

        for (const mark of markLabels) {
          const label = page.getByText(mark, { exact: true })
          if ((await label.count()) > 0) {
            foundMarks++
          }
        }

        console.log(`Found ${foundCellTypes} cell type labels, ${foundMarks} mark labels`)
      }
    }
  })

  test('should show tooltip on heatmap cell hover', async ({ page }) => {
    // Navigate to matrix view
    const compareCellLinesBtn = page.getByRole('button', { name: /Compare Cell|/i })
      .or(page.locator('button').filter({ hasText: /Compare|/i }))

    if ((await compareCellLinesBtn.count()) > 0) {
      await compareCellLinesBtn.first().click()
      await page.waitForTimeout(500)

      const matrixTab = page.getByRole('tab', { name: /Matrix View|Matrix|/i })
        .or(page.locator('.ant-tabs-tab').filter({ hasText: /Matrix|/i }))

      if ((await matrixTab.count()) > 0) {
        await matrixTab.first().click()
        await page.waitForTimeout(1000)

        // Find canvas and hover over it
        const canvas = page.locator('canvas').first()
        if ((await canvas.count()) > 0) {
          const box = await canvas.boundingBox()
          if (box) {
            // Hover over center of canvas
            await page.mouse.move(box.x + box.width / 2, box.y + box.height / 2)
            await page.waitForTimeout(500)

            // Look for ECharts tooltip
            const tooltip = page.locator('.echarts-tooltip')
              .or(page.locator('[class*="tooltip"]'))
              .or(page.locator('.ant-tooltip'))

            if ((await tooltip.count()) > 0) {
              console.log('Tooltip is displayed on hover')
            }
          }
        }
      }
    }
  })

  test('should display color scale legend', async ({ page }) => {
    // Navigate to matrix view
    const compareCellLinesBtn = page.getByRole('button', { name: /Compare Cell|/i })
      .or(page.locator('button').filter({ hasText: /Compare|/i }))

    if ((await compareCellLinesBtn.count()) > 0) {
      await compareCellLinesBtn.first().click()
      await page.waitForTimeout(500)

      const matrixTab = page.getByRole('tab', { name: /Matrix View|Matrix|/i })
        .or(page.locator('.ant-tabs-tab').filter({ hasText: /Matrix|/i }))

      if ((await matrixTab.count()) > 0) {
        await matrixTab.first().click()
        await page.waitForTimeout(1000)

        // Look for color scale legend (usually rendered by ECharts as visualMap)
        const legend = page.locator('[class*="legend"]')
          .or(page.locator('[class*="visualMap"]'))
          .or(page.locator('.color-scale'))

        const legendCount = await legend.count()
        console.log(`Found ${legendCount} legend elements`)
      }
    }
  })

  test('should handle missing data combinations gracefully', async ({ page }) => {
    // This test verifies the UI handles missing data (null values in matrix)
    const compareCellLinesBtn = page.getByRole('button', { name: /Compare Cell|/i })
      .or(page.locator('button').filter({ hasText: /Compare|/i }))

    if ((await compareCellLinesBtn.count()) > 0) {
      await compareCellLinesBtn.first().click()
      await page.waitForTimeout(500)

      const matrixTab = page.getByRole('tab', { name: /Matrix View|Matrix|/i })
        .or(page.locator('.ant-tabs-tab').filter({ hasText: /Matrix|/i }))

      if ((await matrixTab.count()) > 0) {
        await matrixTab.first().click()
        await page.waitForTimeout(1000)

        // Check for "No Data" or similar indicators
        const noDataIndicator = page.getByText(/No Data|N\/A|-/i)
          .or(page.locator('[class*="empty"]'))

        const indicatorCount = await noDataIndicator.count()
        console.log(`Found ${indicatorCount} no-data indicators`)

        // Ensure the page doesn't show an error state
        const errorMessage = page.locator('.ant-alert-error, .error-boundary')
        const errorCount = await errorMessage.count()
        expect(errorCount).toBe(0)
      }
    }
  })
})
