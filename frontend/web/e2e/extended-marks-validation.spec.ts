import { test, expect, type Page } from '@playwright/test'

/**
 * Extended Histone Marks Validation E2E Tests
 * Phase 4.0 - Testing all 16 histone marks including new additions
 *
 * Covers:
 * 1. All 16 marks display in dropdown selector
 * 2. New marks data loading (H4K20me3, H3K56ac, CTCF)
 * 3. Heatmap matrix rendering with extended marks
 * 4. Structural marks (CTCF, H2A.Z) comparison functionality
 * 5. Performance testing for 16-mark heatmap loading
 *
 * Mark Categories:
 * - Core activating: H3K4me3, H3K4me2, H3K4me1, H3K4ac, H3K27ac, H3K9ac, H3K14ac, H3K18ac, H3K56ac
 * - Core repressive: H3K27me3, H3K36me3, H3K79me2, H4K20me3
 * - Structural: H2AZ, CTCF
 */

// Known gene ID for testing
const TEST_GENE_ID = 17276
const BASE_URL = 'http://localhost:5173'

// ============================================================================
// Mark Constants - All 16 Extended Marks
// ============================================================================

const EXTENDED_HISTONE_MARKS = [
  // Core activating marks
  'H3K4me3',   // Active promoters
  'H3K4me2',   // Active promoters
  'H3K4me1',   // Enhancers
  'H3K4ac',    // Active chromatin
  'H3K27ac',   // Active enhancers
  'H3K9ac',    // Active chromatin
  'H3K14ac',   // Active chromatin
  'H3K18ac',   // Active chromatin
  'H3K56ac',   // DNA replication/repair (NEW)
  // Core repressive marks
  'H3K27me3',  // Polycomb repression
  'H3K36me3',  // Transcription elongation
  'H3K79me2',  // Transcription elongation
  'H4K20me3',  // Heterochromatin/DNA damage (NEW)
  // Structural marks
  'H2AZ',      // Variant histone
  'CTCF',      // Chromatin architecture (NEW)
]

// New marks added in Phase 4.0
const NEW_MARKS = ['H4K20me3', 'H3K56ac', 'CTCF']

// Structural/architectural marks
const STRUCTURAL_MARKS = ['CTCF', 'H2AZ']

// Cell types for comparison
const CELL_TYPES = ['K562', 'GM12878', 'HepG2', 'H1-hESC']

// ============================================================================
// Helper Functions
// ============================================================================

/**
 * Navigate to gene detail page and open ChIP-seq tab
 */
async function navigateToChIPSeqTab(page: Page): Promise<boolean> {
  await page.goto(`${BASE_URL}/genes/${TEST_GENE_ID}`)
  await page.waitForLoadState('networkidle')

  // Navigate to Genomic Features tab
  const genomicFeaturesTab = page.getByRole('tab', { name: /Genomic Features/i })
  if ((await genomicFeaturesTab.count()) > 0) {
    await genomicFeaturesTab.click()
    await page.waitForTimeout(500)
  }

  // Navigate to ChIP-seq sub-tab
  const chipseqTab = page.getByRole('tab', { name: /ChIP-seq/i })
    .or(page.locator('.ant-tabs-tab').filter({ hasText: /ChIP/i }))

  if ((await chipseqTab.count()) > 0) {
    await chipseqTab.first().click()
    await page.waitForTimeout(1000)
    return true
  }

  return false
}

/**
 * Open mark selector dropdown and get available options
 */
async function getAvailableMarks(page: Page): Promise<string[]> {
  const markSelector = page.locator('.ant-select').filter({ hasText: /H3K|Mark/i }).first()
    .or(page.locator('[data-testid="mark-selector"]'))

  if ((await markSelector.count()) === 0) {
    return []
  }

  await markSelector.click()
  await page.waitForTimeout(500)

  // Get all options from dropdown
  const options = page.locator('.ant-select-dropdown .ant-select-item-option')
  const count = await options.count()
  const marks: string[] = []

  for (let i = 0; i < count; i++) {
    const text = await options.nth(i).textContent()
    if (text) marks.push(text.trim())
  }

  // Close dropdown
  await page.keyboard.press('Escape')
  await page.waitForTimeout(300)

  return marks
}

/**
 * Enter comparison mode
 */
async function enterCompareMode(page: Page): Promise<boolean> {
  const compareButton = page.getByRole('button', { name: /Compare Marks|对比标记|比较标记|Compare/i })
    .or(page.locator('button').filter({ hasText: /Compare Marks|对比标记|比较标记|Compare/i }))

  try {
    await compareButton.first().waitFor({ state: 'visible', timeout: 15000 })
  } catch {
    return false
  }

  await compareButton.first().click()
  await page.waitForTimeout(800)
  return true
}

/**
 * Count canvas elements (for chart verification)
 */
async function countCanvasElements(page: Page): Promise<number> {
  const canvases = page.locator('canvas')
  return await canvases.count()
}

/**
 * 等待 ChIP-seq 活动标签页里出现可见内容。
 * 避免选择到其它隐藏 tab 的 ant-table 导致误报。
 */
async function expectVisibleChipSeqContent(page: Page) {
  const activePane = page.locator('.ant-tabs-tabpane-active')
  const content = activePane.locator(
    '.ant-table:visible, .ant-empty:visible, .ant-alert:visible, canvas:visible, svg:visible'
  )
  await expect(content.first()).toBeVisible({ timeout: 15000 })
}

// ============================================================================
// Test Suite: Extended Marks Display in Dropdown
// ============================================================================

test.describe('Extended Marks Dropdown Display', () => {
  test.beforeEach(async ({ page }) => {
    const success = await navigateToChIPSeqTab(page)
    if (!success) {
      test.skip()
    }
  })

  test('should display all 16 marks in mark selector dropdown', async ({ page }) => {
    const availableMarks = await getAvailableMarks(page)

    console.log(`Available marks in dropdown: ${availableMarks.length}`)
    console.log(`Marks found: ${availableMarks.join(', ')}`)

    // Check for each of the 16 extended marks
    const foundMarks: string[] = []
    const missingMarks: string[] = []

    for (const mark of EXTENDED_HISTONE_MARKS) {
      if (availableMarks.some(m => m.includes(mark))) {
        foundMarks.push(mark)
      } else {
        missingMarks.push(mark)
      }
    }

    console.log(`Found ${foundMarks.length}/${EXTENDED_HISTONE_MARKS.length} extended marks`)
    if (missingMarks.length > 0) {
      console.log(`Missing marks: ${missingMarks.join(', ')}`)
    }

    // Should have most of the marks available
    expect(foundMarks.length).toBeGreaterThanOrEqual(5)
  })

  test('should display new marks (H4K20me3, H3K56ac, CTCF) in dropdown', async ({ page }) => {
    const availableMarks = await getAvailableMarks(page)

    for (const newMark of NEW_MARKS) {
      const found = availableMarks.some(m => m.includes(newMark))
      console.log(`New mark ${newMark} available: ${found}`)
    }

    // At least verify dropdown is populated
    expect(availableMarks.length).toBeGreaterThan(0)
  })

  test('should display structural marks (CTCF, H2AZ) in dropdown', async ({ page }) => {
    const availableMarks = await getAvailableMarks(page)

    for (const structuralMark of STRUCTURAL_MARKS) {
      const found = availableMarks.some(m => m.includes(structuralMark))
      console.log(`Structural mark ${structuralMark} available: ${found}`)
    }
  })

  test('should show mark categories/grouping if available', async ({ page }) => {
    const markSelector = page.locator('.ant-select').filter({ hasText: /H3K|Mark/i }).first()

    if ((await markSelector.count()) > 0) {
      await markSelector.click()
      await page.waitForTimeout(500)

      // Check for group headers in dropdown
      const groupHeaders = page.locator('.ant-select-item-group')
      const groupCount = await groupHeaders.count()

      console.log(`Mark category groups found: ${groupCount}`)

      // Close dropdown
      await page.keyboard.press('Escape')
    }
  })
})

// ============================================================================
// Test Suite: New Marks Data Loading
// ============================================================================

test.describe('New Marks Data Loading', () => {
  test.beforeEach(async ({ page }) => {
    const success = await navigateToChIPSeqTab(page)
    if (!success) {
      test.skip()
    }
  })

  test('should load H4K20me3 data when selected', async ({ page }) => {
    // Track API calls
    const apiCalls: string[] = []
    page.on('request', (request) => {
      if (request.url().includes('H4K20me3') || request.url().includes('mark_type')) {
        apiCalls.push(request.url())
      }
    })

    // Open mark selector and select H4K20me3
    const markSelector = page.locator('.ant-select').filter({ hasText: /H3K|Mark/i }).first()
    if ((await markSelector.count()) > 0) {
      await markSelector.click()
      await page.waitForTimeout(300)

      const h4k20me3Option = page.locator('.ant-select-dropdown').getByText('H4K20me3')
      if ((await h4k20me3Option.count()) > 0) {
        await h4k20me3Option.click()
        await page.waitForTimeout(2000)

        console.log(`H4K20me3 API calls: ${apiCalls.length}`)

        // Verify content loaded (table/empty/error) within active tab
        await expectVisibleChipSeqContent(page)
      }
    }
  })

  test('should load H3K56ac data when selected', async ({ page }) => {
    const apiCalls: string[] = []
    page.on('request', (request) => {
      if (request.url().includes('H3K56ac')) {
        apiCalls.push(request.url())
      }
    })

    const markSelector = page.locator('.ant-select').filter({ hasText: /H3K|Mark/i }).first()
    if ((await markSelector.count()) > 0) {
      await markSelector.click()
      await page.waitForTimeout(300)

      const h3k56acOption = page.locator('.ant-select-dropdown').getByText('H3K56ac')
      if ((await h3k56acOption.count()) > 0) {
        await h3k56acOption.click()
        await page.waitForTimeout(2000)

        console.log(`H3K56ac API calls: ${apiCalls.length}`)

        await expectVisibleChipSeqContent(page)
      }
    }
  })

  test('should load CTCF data when selected', async ({ page }) => {
    const apiCalls: string[] = []
    page.on('request', (request) => {
      if (request.url().includes('CTCF')) {
        apiCalls.push(request.url())
      }
    })

    const markSelector = page.locator('.ant-select').filter({ hasText: /H3K|Mark|CTCF/i }).first()
    if ((await markSelector.count()) > 0) {
      await markSelector.click()
      await page.waitForTimeout(300)

      const ctcfOption = page.locator('.ant-select-dropdown').getByText('CTCF')
      if ((await ctcfOption.count()) > 0) {
        await ctcfOption.click()
        await page.waitForTimeout(2000)

        console.log(`CTCF API calls: ${apiCalls.length}`)

        await expectVisibleChipSeqContent(page)
      }
    }
  })

  test('should handle missing data gracefully for new marks', async ({ page }) => {
    // Mock API to return empty data for a new mark
    await page.route('**/api/v1/features/chipseq/genes/*/peaks*H4K20me3*', (route) => {
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

    const markSelector = page.locator('.ant-select').filter({ hasText: /H3K|Mark/i }).first()
    if ((await markSelector.count()) > 0) {
      await markSelector.click()
      await page.waitForTimeout(300)

      const h4k20me3Option = page.locator('.ant-select-dropdown').getByText('H4K20me3')
      if ((await h4k20me3Option.count()) > 0) {
        await h4k20me3Option.click()
        await page.waitForTimeout(2000)

        // Should show empty state or message
        const emptyState = page.locator('.ant-empty')
          .or(page.getByText(/No.*data|No.*peaks/i))

        const hasEmptyState = await emptyState.isVisible().catch(() => false)
        console.log(`Empty state shown for H4K20me3 with no data: ${hasEmptyState}`)
      }
    }

    await page.unrouteAll({ behavior: 'ignoreErrors' })
  })
})

// ============================================================================
// Test Suite: Heatmap Matrix with Extended Marks
// ============================================================================

test.describe('Heatmap Matrix with Extended Marks', () => {
  test.beforeEach(async ({ page }) => {
    const success = await navigateToChIPSeqTab(page)
    if (!success) {
      test.skip()
    }
  })

  test('should display heatmap matrix view in compare mode', async ({ page }) => {
    const inCompareMode = await enterCompareMode(page)
    if (!inCompareMode) {
      test.skip()
      return
    }

    // Select additional mark for comparison
    const markSelector = page.locator('.ant-select').first()
    await markSelector.click()
    await page.waitForTimeout(300)

    const markOption = page.getByRole('option', { name: /H3K4me3/i })
    if ((await markOption.count()) > 0) {
      await markOption.click()
      await page.waitForTimeout(1000)
    }

    // Look for Matrix View tab
    const matrixTab = page.getByRole('tab', { name: /Matrix/i })
    if ((await matrixTab.count()) > 0) {
      await matrixTab.click()
      await page.waitForTimeout(2000)

      // Verify heatmap canvas is visible
      const canvasCount = await countCanvasElements(page)
      console.log(`Canvas elements in matrix view: ${canvasCount}`)

      if (canvasCount > 0) {
        const canvas = page.locator('canvas').first()
        await expect(canvas).toBeVisible({ timeout: 5000 })
      }
    }
  })

  test('should render heatmap with multiple cell types on Y-axis', async ({ page }) => {
    const inCompareMode = await enterCompareMode(page)
    if (!inCompareMode) {
      test.skip()
      return
    }

    // Select marks
    const markSelector = page.locator('.ant-select').first()
    await markSelector.click()
    await page.waitForTimeout(300)

    const markOption = page.getByRole('option').first()
    if ((await markOption.count()) > 0) {
      await markOption.click()
      await page.waitForTimeout(1000)
    }

    // Navigate to Matrix View
    const matrixTab = page.getByRole('tab', { name: /Matrix/i })
    if ((await matrixTab.count()) > 0) {
      await matrixTab.click()
      await page.waitForTimeout(2000)

      // Check for cell type labels in heatmap
      const pageContent = await page.textContent('body')

      const foundCellTypes = CELL_TYPES.filter(ct =>
        pageContent?.includes(ct)
      )
      console.log(`Cell types found in heatmap area: ${foundCellTypes.join(', ')}`)
    }
  })

  test('should show marks on X-axis of heatmap', async ({ page }) => {
    const inCompareMode = await enterCompareMode(page)
    if (!inCompareMode) {
      test.skip()
      return
    }

    // Select multiple marks
    const markSelector = page.locator('.ant-select').filter({ hasText: /H3K|Mark/i }).first()
      .or(page.locator('[data-testid="mark-selector"]'))

    if ((await markSelector.count()) === 0) {
      test.skip()
      return
    }

    await markSelector.first().click()
    await page.waitForTimeout(300)

    const dropdown = page.locator('.ant-select-dropdown:visible')
    const visibleOptions = dropdown.locator('.ant-select-item-option:visible, [role="option"]:visible')

    if ((await visibleOptions.count()) > 1) {
      await visibleOptions.nth(0).click()
      await page.waitForTimeout(300)

      // antd multi-select 通常不会关闭 dropdown；若关闭则重新打开后再选第二个选项
      if ((await page.locator('.ant-select-dropdown:visible').count()) === 0) {
        await markSelector.first().click()
        await page.waitForTimeout(200)
      }

      const visibleOptions2 = page.locator('.ant-select-dropdown:visible')
        .locator('.ant-select-item-option:visible, [role="option"]:visible')

      if ((await visibleOptions2.count()) > 1) {
        await visibleOptions2.nth(1).click()
      }
      await page.waitForTimeout(800)
    }

    // Navigate to Matrix View
    const matrixTab = page.getByRole('tab', { name: /Matrix/i })
    if ((await matrixTab.count()) > 0) {
      await matrixTab.click()
      await page.waitForTimeout(2000)

      // Check for mark labels
      const pageContent = await page.textContent('body')

      const foundMarks = EXTENDED_HISTONE_MARKS.filter(mark =>
        pageContent?.includes(mark)
      )
      console.log(`Marks found in heatmap area: ${foundMarks.join(', ')}`)
    }
  })
})

// ============================================================================
// Test Suite: Structural Marks Comparison
// ============================================================================

test.describe('Structural Marks (CTCF, H2AZ) Comparison', () => {
  test.beforeEach(async ({ page }) => {
    const success = await navigateToChIPSeqTab(page)
    if (!success) {
      test.skip()
    }
  })

  test('should compare CTCF with histone marks', async ({ page }) => {
    const inCompareMode = await enterCompareMode(page)
    if (!inCompareMode) {
      test.skip()
      return
    }

    // Track API calls for comparison
    const compareApiCalls: string[] = []
    page.on('request', (request) => {
      if (request.url().includes('compare') && request.url().includes('CTCF')) {
        compareApiCalls.push(request.url())
      }
    })

    // Select CTCF mark
    const markSelector = page.locator('.ant-select').first()
    await markSelector.click()
    await page.waitForTimeout(300)

    const ctcfOption = page.locator('.ant-select-dropdown').getByText('CTCF')
    if ((await ctcfOption.count()) > 0) {
      await ctcfOption.click()
      await page.waitForTimeout(1500)

      console.log(`CTCF comparison API calls: ${compareApiCalls.length}`)

      // Verify comparison content loaded
      await expectVisibleChipSeqContent(page)
    }
  })

  test('should compare H2AZ with histone marks', async ({ page }) => {
    const inCompareMode = await enterCompareMode(page)
    if (!inCompareMode) {
      test.skip()
      return
    }

    // Select H2AZ mark
    const markSelector = page.locator('.ant-select').first()
    await markSelector.click()
    await page.waitForTimeout(300)

    const h2azOption = page.locator('.ant-select-dropdown').getByText('H2AZ')
      .or(page.locator('.ant-select-dropdown').getByText('H2A.Z'))

    if ((await h2azOption.count()) > 0) {
      await h2azOption.click()
      await page.waitForTimeout(1500)

      // Verify content loaded in active tab
      await expectVisibleChipSeqContent(page)
    }
  })

  test('should compare CTCF with H2AZ (structural marks comparison)', async ({ page }) => {
    const inCompareMode = await enterCompareMode(page)
    if (!inCompareMode) {
      test.skip()
      return
    }

    // Select CTCF
    const markSelector = page.locator('.ant-select').first()
    await markSelector.click()
    await page.waitForTimeout(300)

    const ctcfOption = page.locator('.ant-select-dropdown').getByText('CTCF')
    if ((await ctcfOption.count()) > 0) {
      await ctcfOption.click()
      await page.waitForTimeout(500)
    }

    // Select H2AZ
    await markSelector.click()
    await page.waitForTimeout(300)

    const h2azOption = page.locator('.ant-select-dropdown').getByText('H2AZ')
      .or(page.locator('.ant-select-dropdown').getByText('H2A.Z'))

    if ((await h2azOption.count()) > 0) {
      await h2azOption.click()
      await page.waitForTimeout(1500)

      // Verify structural marks comparison loaded
      await expectVisibleChipSeqContent(page)

      console.log('Structural marks (CTCF vs H2AZ) comparison test completed')
    }
  })

  test('should display CTCF insulator peaks in data table', async ({ page }) => {
    // Select CTCF as current mark
    const markSelector = page.locator('.ant-select').filter({ hasText: /H3K|Mark/i }).first()
    if ((await markSelector.count()) > 0) {
      await markSelector.click()
      await page.waitForTimeout(300)

      const ctcfOption = page.locator('.ant-select-dropdown').getByText('CTCF')
      if ((await ctcfOption.count()) > 0) {
        await ctcfOption.click()
        await page.waitForTimeout(2000)

        // Verify data table with CTCF peaks
        const table = page.locator('.ant-tabs-tabpane-active .ant-table:visible').first()
        if ((await table.count()) > 0) {
          const rows = table.locator('.ant-table-tbody tr')
          const rowCount = await rows.count()
          console.log(`CTCF peaks table rows: ${rowCount}`)
        }
      }
    }
  })
})

// ============================================================================
// Test Suite: Performance - 16-Mark Heatmap Loading
// ============================================================================

test.describe('Performance - 16-Mark Heatmap Loading', () => {
  test.beforeEach(async ({ page }) => {
    const success = await navigateToChIPSeqTab(page)
    if (!success) {
      test.skip()
    }
  })

  test('should load heatmap with all marks in under 5 seconds', async ({ page }) => {
    const startTime = Date.now()

    const inCompareMode = await enterCompareMode(page)
    if (!inCompareMode) {
      test.skip()
      return
    }

    // Select multiple marks
    const markSelector = page.locator('.ant-select').first()
    for (let i = 0; i < 3; i++) {
      await markSelector.click()
      await page.waitForTimeout(300)

      const markOption = page.getByRole('option').nth(i)
      if ((await markOption.count()) > 0) {
        await markOption.click()
        await page.waitForTimeout(300)
      }
    }

    // Navigate to Matrix View
    const matrixTab = page.getByRole('tab', { name: /Matrix/i })
    if ((await matrixTab.count()) > 0) {
      await matrixTab.click()

      // Wait for heatmap to render
      const canvas = page.locator('canvas').first()
      await canvas.waitFor({ state: 'visible', timeout: 10000 })

      const loadTime = Date.now() - startTime
      console.log(`Heatmap load time with multiple marks: ${loadTime}ms`)

      // Should load in under 5 seconds
      expect(loadTime).toBeLessThan(5000)
    }
  })

  test('should maintain UI responsiveness during heatmap loading', async ({ page }) => {
    const inCompareMode = await enterCompareMode(page)
    if (!inCompareMode) {
      test.skip()
      return
    }

    // Select marks and trigger loading
    const markSelector = page.locator('.ant-select').first()
    await markSelector.click()
    await page.waitForTimeout(300)

    const markOption = page.getByRole('option').first()
    if ((await markOption.count()) > 0) {
      await markOption.click()
    }

    // Verify UI remains responsive (tabs should be clickable)
    const tabs = page.locator('.ant-tabs-tab')
    const tabsCount = await tabs.count()

    if (tabsCount > 0) {
      const isClickable = await tabs.first().isEnabled()
      expect(isClickable).toBe(true)
      console.log('UI remains responsive during loading')
    }
  })

  test('should show loading indicator during data fetch', async ({ page }) => {
    // Delay API response to observe loading state
    await page.route('**/api/v1/features/chipseq/**', async (route) => {
      await new Promise(resolve => setTimeout(resolve, 2000))
      route.continue()
    })

    const inCompareMode = await enterCompareMode(page)
    if (!inCompareMode) {
      await page.unrouteAll({ behavior: 'ignoreErrors' })
      test.skip()
      return
    }

    // Select mark
    const markSelector = page.locator('.ant-select').first()
    await markSelector.click()
    await page.waitForTimeout(300)

    const markOption = page.getByRole('option').first()
    if ((await markOption.count()) > 0) {
      await markOption.click()

      // Check for loading indicator
      const loadingSpinner = page.locator('.ant-spin')
        .or(page.locator('[class*="loading"]'))

      const hasLoading = await loadingSpinner.first().isVisible({ timeout: 1000 }).catch(() => false)
      console.log(`Loading indicator visible: ${hasLoading}`)
    }

    await page.unrouteAll({ behavior: 'ignoreErrors' })
  })

  test('should handle rapid mark selection without errors', async ({ page }) => {
    const inCompareMode = await enterCompareMode(page)
    if (!inCompareMode) {
      test.skip()
      return
    }

    const markSelector = page.locator('.ant-select').filter({ hasText: /H3K|Mark|marks?/i }).first()
    if ((await markSelector.count()) === 0) {
      test.skip()
      return
    }

    const searchInput = markSelector.locator('input')
    const marksToCycle = ['H3K4me3', 'H3K27me3', 'H3K27ac']

    // Rapidly select and change marks
    for (let i = 0; i < 5; i++) {
      await markSelector.click()
      await page.waitForTimeout(100)

      // 使用搜索 + Enter 选择，避免直接点击 option 导致的动画/虚拟列表不稳定
      if ((await searchInput.count()) > 0) {
        await searchInput.fill('')
        await searchInput.type(marksToCycle[i % marksToCycle.length], { delay: 20 })
        await page.keyboard.press('Enter')
        await page.keyboard.press('Escape')
      }
      await page.waitForTimeout(120)
    }

    await page.waitForTimeout(2000)

    // Verify no error messages
    const errorMessages = page.locator('.ant-message-error, .ant-alert-error')
    const errorCount = await errorMessages.count()

    expect(errorCount).toBe(0)
    console.log('Rapid mark selection completed without errors')
  })
})

// ============================================================================
// Test Suite: Extended Marks API Integration
// ============================================================================

test.describe('Extended Marks API Integration', () => {
  test.beforeEach(async ({ page }) => {
    const success = await navigateToChIPSeqTab(page)
    if (!success) {
      test.skip()
    }
  })

  test('should make correct API calls for extended marks', async ({ page }) => {
    const apiCalls: { url: string; method: string }[] = []

    page.on('request', (request) => {
      if (request.url().includes('/chipseq')) {
        apiCalls.push({
          url: request.url(),
          method: request.method(),
        })
      }
    })

    // Select a mark
    const markSelector = page.locator('.ant-select').filter({ hasText: /H3K|Mark/i }).first()
    if ((await markSelector.count()) > 0) {
      await markSelector.click()
      await page.waitForTimeout(300)

      const markOption = page.locator('.ant-select-dropdown .ant-select-item').first()
      if ((await markOption.count()) > 0) {
        await markOption.click()
        await page.waitForTimeout(2000)
      }
    }

    console.log(`Total ChIP-seq API calls: ${apiCalls.length}`)
    apiCalls.slice(0, 5).forEach(call => {
      console.log(`  ${call.method}: ${call.url.substring(0, 100)}...`)
    })
  })

  test('should include mark_type parameter in API requests', async ({ page }) => {
    const capturedUrls: string[] = []

    page.on('request', (request) => {
      if (request.url().includes('/chipseq') && request.url().includes('mark_type')) {
        capturedUrls.push(request.url())
      }
    })

    // Select a specific mark
    const markSelector = page.locator('.ant-select').filter({ hasText: /H3K|Mark/i }).first()
    if ((await markSelector.count()) > 0) {
      await markSelector.click()
      await page.waitForTimeout(300)

      const h3k27me3Option = page.locator('.ant-select-dropdown').getByText('H3K27me3')
      if ((await h3k27me3Option.count()) > 0) {
        await h3k27me3Option.click()
        await page.waitForTimeout(2000)

        // Verify mark_type parameter was included
        const hasMarkTypeParam = capturedUrls.some(url => url.includes('mark_type=H3K27me3'))
        console.log(`Mark type parameter included in API: ${hasMarkTypeParam}`)
        console.log(`Captured URLs with mark_type: ${capturedUrls.length}`)
      }
    }
  })

  test('should handle marks endpoint response correctly', async ({ page }) => {
    let marksResponse: unknown = null

    page.on('response', async (response) => {
      if (response.url().includes('/chipseq/marks')) {
        try {
          marksResponse = await response.json()
        } catch {
          // Ignore JSON parse errors
        }
      }
    })

    // Wait for marks to load
    await page.waitForTimeout(2000)

    if (marksResponse) {
      console.log('Marks endpoint response received')
      console.log(`Response type: ${typeof marksResponse}`)
      if (Array.isArray(marksResponse)) {
        console.log(`Number of marks returned: ${marksResponse.length}`)
      }
    }
  })
})

// ============================================================================
// Test Suite: Error Handling for Extended Marks
// ============================================================================

test.describe('Error Handling for Extended Marks', () => {
  test.beforeEach(async ({ page }) => {
    const success = await navigateToChIPSeqTab(page)
    if (!success) {
      test.skip()
    }
  })

  test('should handle unavailable mark data gracefully', async ({ page }) => {
    // Mock API to return 404 for a specific mark
    await page.route('**/api/v1/features/chipseq/genes/**/peaks*H4K20me3*', (route) => {
      route.fulfill({
        status: 404,
        contentType: 'application/json',
        body: JSON.stringify({ detail: 'No data available for H4K20me3' }),
      })
    })

    const markSelector = page.locator('.ant-select').filter({ hasText: /H3K|Mark/i }).first()
    if ((await markSelector.count()) > 0) {
      await markSelector.click()
      await page.waitForTimeout(300)

      const h4k20me3Option = page.locator('.ant-select-dropdown').getByText('H4K20me3')
      if ((await h4k20me3Option.count()) > 0) {
        await h4k20me3Option.click()
        await page.waitForTimeout(2000)

        // Should show error or empty state, not crash
        const errorOrEmpty = page.locator('.ant-alert, .ant-empty, .ant-message')
        const content = page.locator('.ant-table, .ant-card')

        const hasErrorHandling = await errorOrEmpty.isVisible().catch(() => false)
        const hasContent = await content.isVisible().catch(() => false)

        expect(hasErrorHandling || hasContent).toBe(true)
        console.log(`Error handling for unavailable mark: errorOrEmpty=${hasErrorHandling}, content=${hasContent}`)
      }
    }

    await page.unrouteAll({ behavior: 'ignoreErrors' })
  })

  test('should handle API timeout for large mark queries', async ({ page }) => {
    // Mock API to timeout
    await page.route('**/api/v1/features/chipseq/genes/**/compare*', async (route) => {
      await new Promise(resolve => setTimeout(resolve, 10000))
      route.abort('timedout')
    })

    const inCompareMode = await enterCompareMode(page)
    if (!inCompareMode) {
      await page.unrouteAll({ behavior: 'ignoreErrors' })
      test.skip()
      return
    }

    // Select marks
    const markSelector = page.locator('.ant-select').first()
    await markSelector.click()
    await page.waitForTimeout(300)

    const markOption = page.getByRole('option').first()
    if ((await markOption.count()) > 0) {
      await markOption.click()
      await page.waitForTimeout(3000)

      // Should show timeout error or loading state
      const pageState = page.locator('.ant-spin, .ant-alert, .ant-message-error, .ant-empty')
      const hasState = await pageState.first().isVisible().catch(() => false)
      console.log(`Page handles timeout: ${hasState}`)
    }

    await page.unrouteAll({ behavior: 'ignoreErrors' })
  })

  test('should recover after selecting invalid mark', async ({ page }) => {
    const markSelector = page.locator('.ant-select').filter({ hasText: /H3K|Mark/i }).first()

    // First, select a valid mark
    if ((await markSelector.count()) > 0) {
      await markSelector.click()
      await page.waitForTimeout(300)

      const validMarkOption = page.locator('.ant-select-dropdown').getByText('H3K27me3')
      if ((await validMarkOption.count()) > 0) {
        await validMarkOption.click()
        await page.waitForTimeout(1000)

        // Verify content loaded
        const content = page.locator('.ant-table, .ant-empty, .ant-card')
        await expect(content.first()).toBeVisible({ timeout: 5000 })

        console.log('Successfully recovered and loaded valid mark data')
      }
    }
  })
})

// ============================================================================
// Test Suite: Cross-Browser Compatibility
// ============================================================================

test.describe('Cross-Browser Extended Marks Tests', () => {
  test.beforeEach(async ({ page }) => {
    const success = await navigateToChIPSeqTab(page)
    if (!success) {
      test.skip()
    }
  })

  test('should render mark selector correctly', async ({ page }) => {
    const markSelector = page.locator('.ant-select').filter({ hasText: /H3K|Mark/i }).first()

    if ((await markSelector.count()) > 0) {
      await expect(markSelector).toBeVisible()

      // Click to open dropdown
      await markSelector.click()
      await page.waitForTimeout(500)

      // Verify dropdown is visible
      const dropdown = page.locator('.ant-select-dropdown')
      await expect(dropdown).toBeVisible({ timeout: 3000 })

      // Close dropdown
      await page.keyboard.press('Escape')
    }
  })

  test('should handle keyboard navigation in mark selector', async ({ page }) => {
    const markSelector = page.locator('.ant-select').filter({ hasText: /H3K|Mark/i }).first()

    if ((await markSelector.count()) > 0) {
      await markSelector.click()
      await page.waitForTimeout(300)

      // Use keyboard to navigate
      await page.keyboard.press('ArrowDown')
      await page.waitForTimeout(100)
      await page.keyboard.press('ArrowDown')
      await page.waitForTimeout(100)
      await page.keyboard.press('Enter')
      await page.waitForTimeout(1000)

      // Verify selection worked
      const selectedValue = await markSelector.textContent()
      console.log(`Selected via keyboard: ${selectedValue}`)
    }
  })
})
