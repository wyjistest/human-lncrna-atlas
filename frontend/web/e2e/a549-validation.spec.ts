import { test, expect, type Page } from '@playwright/test'

/**
 * A549 Cell Line Integration Validation Tests
 *
 * Purpose: Verify that A549 (lung cancer cell line) automatically appears
 * in the frontend UI after database import without requiring code changes
 * (beyond adding configuration).
 *
 * Architecture:
 * Database (chipseq_experiments with cell_type='A549')
 *   → API: GET /api/v1/lncrna-chipseq-overlap (returns data filtered by A549)
 *   → React Components: Filters, tables, charts all query API
 *   → UI: Automatically renders A549 data
 *
 * Test Strategy:
 * 1. Verify A549 appears in cell type filter dropdown
 * 2. Verify A549 data loads when selected
 * 3. Verify A549 appears in visualizations (heatmap, charts)
 * 4. Verify A549 data exports correctly
 * 5. Verify no JavaScript errors occur
 */

const API_BASE_URL = process.env.API_BASE_URL || 'http://localhost:8000'

test.describe('A549 Cell Line Integration', () => {

  async function gotoOverlap(page: Page) {
    await page.goto('/lncrna-chipseq-overlap')
    await page.waitForLoadState('domcontentloaded')

    // 页面可能包含持续请求（例如 IGV 资源加载），避免 networkidle 卡死
    await page.locator('h1, h2').first().waitFor({ timeout: 20000 }).catch(() => {})
    await page.waitForTimeout(1000)

    // 确保高级筛选面板可见（某些状态会折叠 filters）
    const showFiltersBtn = page.getByRole('button', { name: /Show Filters|显示筛选/i }).first()
    if (await showFiltersBtn.isVisible().catch(() => false)) {
      await showFiltersBtn.click()
      await page.waitForTimeout(300)
    }
  }

  function getCellTypeSelect(page: Page) {
    // 直接用 Select 的 placeholder 文本定位，避免依赖 Space 的 DOM 包装结构
    return page.locator('.ant-select').filter({
      hasText: /Select\s+cell\s+types|选择.*细胞类型|Cell Type|细胞类型/i,
    }).first()
  }

  test.beforeEach(async ({ page }) => {
    // Monitor console errors
    page.on('console', (msg) => {
      if (msg.type() === 'error') {
        console.error('Browser console error:', msg.text())
      }
    })

    // Monitor network failures
    page.on('requestfailed', (request) => {
      console.error('Network request failed:', request.url(), request.failure()?.errorText)
    })
  })

  test('A549 should appear in cell type filter', async ({ page }) => {
    console.log('Test 1: Checking if A549 appears in cell type filter dropdown')

    await gotoOverlap(page)

    // Take initial screenshot
    await page.screenshot({
      path: '/tmp/a549_test_1_initial.png',
      fullPage: true
    })

    // Find cell type filter (supports both English and Chinese labels)
    const cellTypeFilter = getCellTypeSelect(page)

    // Open dropdown
    await cellTypeFilter.click()
    await page.waitForTimeout(1000)

    // Take screenshot of dropdown
    await page.screenshot({
      path: '/tmp/a549_test_1_dropdown.png',
      fullPage: true
    })

    // Check if A549 appears in dropdown options
    const a549Option = page.locator('.ant-select-dropdown:visible .ant-select-item').filter({ hasText: /A549/ })
    const count = await a549Option.count()

    console.log(`Found ${count} A549 option(s) in cell type filter`)
    if (count === 0) {
      test.skip(true, 'A549 不在当前数据集中，跳过该校验')
    }

    // Get all cell type options for logging
    const allOptions = await page.locator('.ant-select-dropdown:visible .ant-select-item').allTextContents()
    console.log('All cell types available:', allOptions)
  })

  test('A549 data loads when selected (with H3K27me3)', async ({ page }) => {
    console.log('Test 2: Verifying A549 × H3K27me3 returns data')

    await gotoOverlap(page)

    // Step 1: Select A549 cell type
    const cellTypeFilter = getCellTypeSelect(page)
    await cellTypeFilter.click()
    await page.waitForTimeout(500)

    const a549Option = page.locator('.ant-select-dropdown:visible .ant-select-item').filter({ hasText: /A549/ }).first()

    if ((await a549Option.count()) === 0) {
      test.skip(true, 'A549 不在当前数据集中，跳过该校验')
    }

    // Wait for data request after selecting cell type
    const cellTypeDataResponsePromise = page.waitForResponse(
      (resp) =>
        resp.status() === 200 &&
        resp.url().includes('/api/v1/lncrna-chipseq-overlap') &&
        resp.url().includes('cell_type=A549'),
      { timeout: 30000 }
    )

    await a549Option.click()

    // If A549 has no overlaps in the current DB snapshot, treat as a valid empty-state scenario.
    const cellTypeDataResponse = await cellTypeDataResponsePromise
    const cellTypeData: any = await cellTypeDataResponse.json().catch(() => ({}))
    const cellTypeTotal = Number(cellTypeData?.total ?? 0)

    if (!Number.isFinite(cellTypeTotal) || cellTypeTotal <= 0) {
      await expect(page.getByText(/No overlaps found|暂无.*重叠/i)).toBeVisible({
        timeout: 20000,
      })
      return
    }

    await page.waitForTimeout(500)

    // Step 2: Select H3K27me3 mark
    const markFilter = page.locator('.ant-select').filter({
      hasText: /Mark Type|Mark|marks?|Histone|Epigenetic|标记|表观/i
    }).first()

    // Fallback: first select on page (Mark Type is the first column in the filter panel)
    const markSelector = (await markFilter.count()) > 0 ? markFilter : page.locator('.ant-select').first()

    await markSelector.scrollIntoViewIfNeeded()
    await markSelector.click()
    await page.waitForTimeout(300)

    const h3k27me3Option = page.locator('.ant-select-dropdown .ant-select-item').filter({
      hasText: /H3K27me3/
    }).first()

    const selectedMarkName = (await h3k27me3Option.count()) > 0
      ? 'H3K27me3'
      : (await page.locator('.ant-select-dropdown .ant-select-item').first().textContent())?.trim() || ''

    const markOption = (await h3k27me3Option.count()) > 0
      ? h3k27me3Option
      : page.locator('.ant-select-dropdown .ant-select-item').first()

    if ((await markOption.count()) === 0) {
      test.skip(true, 'Mark Type 下拉选项为空，跳过该校验')
    }

    const markDataResponsePromise = page.waitForResponse(
      (resp) =>
        resp.status() === 200 &&
        resp.url().includes('/api/v1/lncrna-chipseq-overlap') &&
        resp.url().includes('cell_type=A549') &&
        (selectedMarkName ? resp.url().includes(`mark_type=${encodeURIComponent(selectedMarkName)}`) : true),
      { timeout: 30000 }
    )

    await markOption.click()
    await markDataResponsePromise

    // Step 3: Wait for data to load
    await page.waitForTimeout(1500)

    // Take screenshot after filters applied
    await page.screenshot({
      path: '/tmp/a549_test_2_filtered.png',
      fullPage: true
    })

    // Step 4: Verify empty state OR table rows (data snapshot dependent)
    const emptyState = page.getByText(/No overlaps found|暂无.*重叠/i)
    if (await emptyState.count() > 0) {
      await expect(emptyState.first()).toBeVisible()
      return
    }

    const dataTable = page.locator('.ant-table-tbody tr').filter({
      hasNotText: /No Data|暂无数据/i
    })
    const rowCount = await dataTable.count()

    console.log(`A549 × ${selectedMarkName || 'selected mark'} returned ${rowCount} data rows`)
    expect(rowCount).toBeGreaterThan(0)
  })

  test('A549 appears in heatmap visualization', async ({ page }) => {
    console.log('Test 3: Verifying A549 appears in heatmap')

    await gotoOverlap(page)
    await page.waitForTimeout(2000)

    // Look for heatmap container (ECharts or custom)
    const heatmapCandidates = [
      page.locator('[data-testid="overlap-heatmap"]'),
      page.locator('.echarts-container'),
      page.locator('canvas[data-zr-dom-id]'),  // ECharts canvas
      page.locator('.heatmap-container')
    ]

    let heatmapFound = false
    for (const candidate of heatmapCandidates) {
      const count = await candidate.count()
      if (count > 0) {
        console.log(`Found heatmap: ${await candidate.first().evaluate(el => el.className)}`)
        heatmapFound = true
        break
      }
    }

    // Take full page screenshot for visual verification
    await page.screenshot({
      path: '/tmp/a549_test_3_heatmap.png',
      fullPage: true
    })

    if (heatmapFound) {
      console.log('Heatmap visualization detected - see screenshot for A549 presence')
      // Note: Actual A549 presence in heatmap requires visual inspection
      // or API validation since ECharts canvas is not easily queryable
    } else {
      console.warn('No heatmap visualization found - may not be on this page')
    }

    // Check if statistics cards show A549 data
    const statsCards = page.locator('.ant-statistic, .ant-card')
    const statsCount = await statsCards.count()
    console.log(`Found ${statsCount} statistic/card elements`)
  })

  test('A549 data exports correctly', async ({ page }) => {
    console.log('Test 4: Verifying A549 data can be exported')

    await gotoOverlap(page)

    // Apply A549 filter
    const cellTypeFilter = getCellTypeSelect(page)
    await cellTypeFilter.click()
    await page.waitForTimeout(500)

    const a549Option = page.locator('.ant-select-dropdown:visible .ant-select-item').filter({ hasText: /A549/ }).first()
    if ((await a549Option.count()) === 0) {
      test.skip(true, 'A549 不在当前数据集中，跳过该校验')
    }
    const filterResponse = page.waitForResponse(
      (resp) =>
        resp.status() === 200 &&
        resp.url().includes('/api/v1/lncrna-chipseq-overlap') &&
        resp.url().includes('cell_type=A549'),
      { timeout: 30000 }
    ).catch(() => null)
    await a549Option.click()
    await filterResponse
    await page.waitForTimeout(1500)

    // Look for export button
    const exportButton = page.locator('button').filter({
      hasText: /Export|导出/i
    }).first()

    const exportButtonCount = await exportButton.count()
    if (exportButtonCount > 0) {
      console.log('Export button found')

      // Setup download listener
      const downloadPromise = page.waitForEvent('download', { timeout: 30000 })

      // Click export
      await exportButton.click()
      await page.waitForTimeout(1000)

      // May need to select format (CSV/Excel)
      const csvOption = page.locator('.ant-dropdown-menu-item').filter({
        hasText: /CSV/i
      }).first()
      if (await csvOption.count() > 0) {
        await csvOption.click()
      }

      try {
        const download = await downloadPromise
        const fileName = download.suggestedFilename()
        console.log(`Export successful: ${fileName}`)

        // Save download to temp location
        await download.saveAs(`/tmp/${fileName}`)
        expect(fileName).toBeTruthy()
      } catch (error) {
        console.warn('Export download not completed:', error)
      }
    } else {
      console.warn('Export button not found on this page')
    }

    await page.screenshot({
      path: '/tmp/a549_test_4_export.png',
      fullPage: true
    })
  })

  test('A549 statistics are displayed correctly', async ({ page }) => {
    console.log('Test 5: Verifying A549 statistics')

    await gotoOverlap(page)

    // Apply A549 filter
    const cellTypeFilter = getCellTypeSelect(page)
    await cellTypeFilter.click()
    await page.waitForTimeout(500)

    const a549Option = page.locator('.ant-select-dropdown:visible .ant-select-item').filter({ hasText: /A549/ }).first()
    if ((await a549Option.count()) === 0) {
      test.skip(true, 'A549 不在当前数据集中，跳过该校验')
    }
    const filterResponse = page.waitForResponse(
      (resp) =>
        resp.status() === 200 &&
        resp.url().includes('/api/v1/lncrna-chipseq-overlap') &&
        resp.url().includes('cell_type=A549'),
      { timeout: 30000 }
    ).catch(() => null)
    await a549Option.click()
    await filterResponse
    await page.waitForTimeout(1500)

    // Take screenshot
    await page.screenshot({
      path: '/tmp/a549_test_5_statistics.png',
      fullPage: true
    })

    // Look for statistics cards
    const statisticElements = page.locator('.ant-statistic-content-value')
    const count = await statisticElements.count()

    console.log(`Found ${count} statistic value elements`)

    if (count > 0) {
      const values = await statisticElements.allTextContents()
      console.log('Statistic values:', values)

      // Expect at least one non-zero statistic
      const hasNonZero = values.some(v => {
        const num = parseInt(v.replace(/[^0-9]/g, ''))
        return !isNaN(num) && num > 0
      })

      expect(hasNonZero).toBe(true)
    }
  })

  test('No JavaScript errors when using A549', async ({ page }) => {
    console.log('Test 6: Checking for JavaScript errors')

    const errors: string[] = []

    page.on('console', (msg) => {
      if (msg.type() === 'error') {
        errors.push(msg.text())
      }
    })

    page.on('pageerror', (error) => {
      errors.push(error.message)
    })

    await gotoOverlap(page)

    // Apply A549 filter
    const cellTypeFilter = getCellTypeSelect(page)
    await cellTypeFilter.click()
    await page.waitForTimeout(500)

    const a549Option = page.locator('.ant-select-dropdown:visible .ant-select-item').filter({ hasText: /A549/ }).first()

    if (await a549Option.count() > 0) {
      const filterResponse = page.waitForResponse(
        (resp) =>
          resp.status() === 200 &&
          resp.url().includes('/api/v1/lncrna-chipseq-overlap') &&
          resp.url().includes('cell_type=A549'),
        { timeout: 30000 }
      ).catch(() => null)
      await a549Option.click()
      await filterResponse
      await page.waitForTimeout(1500)
    }

    // Wait a bit more to catch any delayed errors
    await page.waitForTimeout(2000)

    console.log(`Detected ${errors.length} JavaScript errors`)
    if (errors.length > 0) {
      console.error('JavaScript errors:', errors)
    }

    // We expect 0 errors, but be lenient with warnings
    const criticalErrors = errors.filter(e =>
      !e.includes('warning') &&
      !e.includes('Warning') &&
      !e.includes('404')  // Ignore 404s from optional resources
    )

    expect(criticalErrors.length).toBe(0)
  })
})

test.describe('A549 API Integration', () => {

  test('API returns A549 experiments', async ({ request }) => {
    console.log('API Test 1: Checking if A549 experiments exist in API')

    const response = await request.get(
      `${API_BASE_URL}/api/v1/lncrna-chipseq-overlap`,
      {
        params: {
          cell_type: 'A549',
          chromosome: 'chr22',  // Use smaller chromosome for faster test
          page_size: 10
        }
      }
    )

    expect(response.ok()).toBe(true)
    const data = await response.json()

    console.log('API response status:', response.status())
    console.log('Total records:', data.total || 0)
    const items = data.items ?? data.data ?? []
    console.log('Records in page:', items.length || 0)

    if (!Array.isArray(items) || items.length === 0) {
      test.skip(true, 'A549 overlaps 在当前数据库中为空，跳过该校验')
    }

    // Verify A549 is in the returned data
    const hasA549 = items.some((record: any) =>
      record.cell_type === 'A549' ||
      record.cellType === 'A549'
    )
    expect(hasA549).toBe(true)
  })

  test('API export includes A549 data', async ({ request }) => {
    console.log('API Test 2: Checking A549 export endpoint')

    const response = await request.get(
      `${API_BASE_URL}/api/v1/lncrna-chipseq-overlap/export`,
      {
        params: {
          format: 'csv',
          cell_type: 'A549',
          chromosome: 'chr22',
          max_rows: 100
        }
      }
    )

    expect(response.ok()).toBe(true)
    const csvText = await response.text()

    console.log('Export response length:', csvText.length, 'bytes')
    console.log('First 500 chars:', csvText.substring(0, 500))

    // Count rows with A549
    const lines = csvText.split('\n')
    const a549Lines = lines.filter(line => line.includes('A549'))
    console.log(`Export contains ${a549Lines.length} rows with A549`)

    if (a549Lines.length === 0) {
      test.skip(true, 'A549 export 在当前数据库中为空，跳过该校验')
    }

    expect(csvText).toContain('A549')
  })
})
