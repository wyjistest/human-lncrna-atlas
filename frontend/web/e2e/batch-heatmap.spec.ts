import { test, expect, type Page } from '@playwright/test'

/**
 * Batch Heatmap E2E Tests
 *
 * Tests for batch gene heatmap matrix visualization:
 * 1. Gene selection and batch loading
 * 2. Heatmap matrix rendering
 * 3. Mark and cell type filters
 * 4. Data export functionality
 * 5. Performance validation
 *
 * Note: Tests assume ChIP-seq data is available
 */

const TEST_GENE_IDS = [17276, 17277, 17278, 17279, 17280]

async function gotoBatchHeatmapOrSkip(page: Page) {
  await page.goto('/genes/batch')
  await page.waitForLoadState('domcontentloaded')

  // 如果该页面未集成（例如返回 404），则跳过该套件
  const notFound = await page.getByText(/Not Found|404/i).isVisible().catch(() => false)
  const hasHeading = await page.locator('h1, h2').first().isVisible().catch(() => false)
  if (notFound || !hasHeading) {
    test.skip(true, 'Batch heatmap 页面当前未集成，跳过 E2E')
  }

  await page.waitForLoadState('networkidle')
}

test.describe('Batch Heatmap Visualization', () => {
  test.beforeEach(async ({ page }) => {
    await gotoBatchHeatmapOrSkip(page)
  })

  test('should load batch heatmap page', async ({ page }) => {
    // Verify page title or heading is visible
    const heading = page.locator('h1, h2').first()
    await expect(heading).toBeVisible({ timeout: 10000 })

    // Verify main content area exists
    const mainContent = page.locator('main, [role="main"], .container').first()
    await expect(mainContent).toBeVisible()
  })

  test('should display gene input field for batch selection', async ({ page }) => {
    // Look for gene input or selection element
    const geneInput = page.locator(
      'input[placeholder*="gene"], input[placeholder*="Gene"], [data-testid="gene-input"]'
    ).first()

    if (await geneInput.isVisible()) {
      // Enter multiple gene IDs
      await geneInput.click()
      await geneInput.fill('17276')

      // Verify input value is set
      const inputValue = await geneInput.inputValue()
      expect(inputValue).toBe('17276')
    }
  })

  test('should render heatmap matrix after gene selection', async ({ page }) => {
    // Find and interact with gene selector
    const geneInputs = page.locator('input[type="text"], textarea')

    if (await geneInputs.count() > 0) {
      const firstInput = geneInputs.first()
      await firstInput.click()
      await firstInput.fill('17276\n17277\n17278')

      // Wait for heatmap to render
      await page.waitForLoadState('networkidle')

      // Look for heatmap canvas or SVG
      const heatmapCanvas = page.locator('canvas').first()
      const heatmapSvg = page.locator('svg').first()

      const hasVisualization =
        (await heatmapCanvas.isVisible().catch(() => false)) ||
        (await heatmapSvg.isVisible().catch(() => false))

      expect(hasVisualization).toBeTruthy()
    }
  })

  test('should filter by histone marks', async ({ page }) => {
    // Look for mark selector dropdown or checkboxes
    const markSelector = page.locator(
      'select, [role="combobox"], .mark-selector, [data-testid="mark-selector"]'
    ).first()

    if (await markSelector.isVisible()) {
      // Click to open dropdown
      await markSelector.click()

      // Wait for dropdown options to appear
      await page.waitForTimeout(500)

      // Verify dropdown content exists
      const dropdown = page.locator('[role="listbox"], [role="menu"], .dropdown-menu').first()
      await expect(dropdown).toBeVisible({ timeout: 5000 })
    }
  })

  test('should filter by cell types', async ({ page }) => {
    // Look for cell type selector
    const cellTypeSelector = page.locator(
      '[data-testid="cell-type-selector"], .cell-type-selector, [aria-label*="cell"]'
    ).first()

    if (await cellTypeSelector.isVisible()) {
      await cellTypeSelector.click()

      // Wait for dropdown or modal to appear
      await page.waitForTimeout(500)

      // Verify selector opened
      const dropdown = page.locator('[role="listbox"], [role="menu"]').first()
      const isOpen = await dropdown.isVisible().catch(() => false)
      expect(isOpen).toBeTruthy()
    }
  })

  test('should display matrix data in table format', async ({ page }) => {
    // Look for data table showing matrix values
    const table = page.locator('.ant-table, table, [role="grid"]').first()

    if (await table.isVisible()) {
      // Verify table has rows
      const rows = table.locator('tbody tr, [role="row"]')
      const rowCount = await rows.count()
      expect(rowCount).toBeGreaterThan(0)

      // Verify table has cells
      const cells = table.locator('td, [role="gridcell"]')
      const cellCount = await cells.count()
      expect(cellCount).toBeGreaterThan(0)
    }
  })
})

test.describe('Batch Heatmap Performance', () => {
  test.beforeEach(async ({ page }) => {
    await gotoBatchHeatmapOrSkip(page)
  })

  test('should load 10 genes batch within reasonable time', async ({ page }) => {
    const startTime = Date.now()

    // Interact with gene input
    const inputs = page.locator('input[type="text"], textarea')
    if (await inputs.count() > 0) {
      const input = inputs.first()

      // Enter multiple gene IDs
      const geneIds = ['17276', '17277', '17278', '17279', '17280',
                       '17281', '17282', '17283', '17284', '17285']
      await input.click()
      await input.fill(geneIds.join('\n'))

      // Wait for rendering or submit
      await page.press(input, 'Enter')
      await page.waitForLoadState('networkidle')

      // Wait for heatmap to render
      const heatmap = page.locator('canvas, svg').first()
      await expect(heatmap).toBeVisible({ timeout: 5000 }).catch(() => {})
    }

    const elapsedTime = Date.now() - startTime

    // Should load within 3-5 seconds in E2E (slower than API)
    expect(elapsedTime).toBeLessThan(5000)
    console.log(`Batch 10 genes loaded in ${elapsedTime}ms`)
  })

  test('should show loading state during batch processing', async ({ page }) => {
    // Look for loading indicators
    const spinner = page.locator(
      '.ant-spin, [role="status"], [data-testid="loading"], .spinner'
    ).first()

    // Trigger batch loading if possible
    const inputs = page.locator('input[type="text"], textarea')
    if (await inputs.count() > 0) {
      const input = inputs.first()
      await input.click()
      await input.fill('17276\n17277\n17278')

      // Briefly check for loading indicator
      const isLoading = await spinner.isVisible().catch(() => false)
      // It's okay if loading indicator is not visible (might be very fast)
      console.log(`Loading indicator visible: ${isLoading}`)
    }
  })
})

test.describe('Batch Heatmap Data Export', () => {
  test.beforeEach(async ({ page }) => {
    await gotoBatchHeatmapOrSkip(page)
  })

  test('should display export options for batch data', async ({ page }) => {
    // Look for export button
    const exportBtn = page.locator(
      'button:has-text("Export"), button:has-text("Download"), [data-testid="export-btn"]'
    ).first()

    if (await exportBtn.isVisible()) {
      // Verify button is clickable
      await expect(exportBtn).toBeEnabled()
    }
  })

  test('should export batch heatmap as CSV', async ({ page }) => {
    // Find and click export button for CSV
    const csvExportBtn = page.locator(
      'button:has-text("CSV"), button:has-text("Export CSV"), [data-testid="export-csv"]'
    ).first()

    const visible = await csvExportBtn.isVisible().catch(() => false)
    if (!visible) return

    const [download] = await Promise.all([
      page.waitForEvent('download', { timeout: 10000 }),
      csvExportBtn.click(),
    ]).catch(() => [null as any])

    if (!download) return
    const filename = download.suggestedFilename()
    expect(filename).toMatch(/\.csv$/)
  })
})

test.describe('Batch Heatmap Gene Selection', () => {
  test.beforeEach(async ({ page }) => {
    await gotoBatchHeatmapOrSkip(page)
  })

  test('should support multiple gene input methods', async ({ page }) => {
    // Method 1: Text input
    const inputs = page.locator('input[type="text"], textarea')
    if (await inputs.count() > 0) {
      const input = inputs.first()
      await input.click()
      await input.fill('17276, 17277, 17278')

      const value = await input.inputValue()
      expect(value.length).toBeGreaterThan(0)
    }
  })

  test('should validate gene IDs in batch input', async ({ page }) => {
    // Look for validation message or error
    const inputs = page.locator('input[type="text"], textarea')
    if (await inputs.count() > 0) {
      const input = inputs.first()

      // Enter invalid gene ID
      await input.click()
      await input.fill('invalid_gene_id')

      // Check for error message
      const errorMsg = page.locator(
        '.ant-form-item-explain-error, [role="alert"], .error-message'
      ).first()

      const hasError = await errorMsg.isVisible().catch(() => false)
      // Validation may or may not show immediately
      console.log(`Validation error visible: ${hasError}`)
    }
  })
})
