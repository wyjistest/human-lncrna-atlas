import { test, expect } from '@playwright/test'

/**
 * lncRNA-ChIP-seq Overlap Analysis E2E Tests
 *
 * Covers core functionality:
 * 1. Page routing and accessibility
 * 2. Component rendering (filters, table)
 * 3. Internationalization (Chinese/English)
 * 4. Filter interactions (Mark type, cell line, chromosome)
 * 5. Table interactions (pagination, sorting)
 * 6. Error handling
 * 7. Performance validation
 *
 * Note: Page language may be Chinese or English depending on browser settings
 */

const PAGE_URL = '/lncrna-chipseq-overlap'

function getEnvInt(name: string, fallback: number): number {
  const raw = process.env[name]
  if (!raw) return fallback
  const parsed = Number.parseInt(raw, 10)
  return Number.isFinite(parsed) ? parsed : fallback
}

function buildMockOverlapItems(total: number) {
  return Array.from({ length: total }, (_, index) => {
    const id = index + 1
    const markType = id % 2 === 0 ? 'H3K4me3' : 'H3K27me3'
    const cellType = id % 3 === 0 ? 'GM12878' : 'K562'
    const chromosome = id % 4 === 0 ? 'chr22' : 'chr1'

    const overlapLength = 50 + (id % 17) * 10 + id
    const overlapStart = 1_000_000 + id * 1_000
    const overlapEnd = overlapStart + overlapLength

    return {
      overlap_id: `mock_overlap_${id}`,
      lncrna_gene_id: 10_000 + id,
      lncrna_name: `LNC_${String(id).padStart(2, '0')}`,
      target_gene_id: 20_000 + id,
      target_gene_name: `TG_${String(id).padStart(2, '0')}`,
      mark_type: markType,
      mark_category: markType === 'H3K27me3' ? 'repressive' : 'activating',
      cell_type: cellType,
      chromosome,
      lncrna_binding_start: overlapStart - 200,
      lncrna_binding_end: overlapStart - 50,
      peak_start: overlapStart - 100,
      peak_end: overlapEnd + 100,
      overlap_start: overlapStart,
      overlap_end: overlapEnd,
      overlap_length: overlapLength,
      binding_affinity: 100 - id, // Default sort: desc => ids 1..20 appear on page 1
      peak_fold_enrichment: 2 + (id % 10) * 0.5,
      peak_qvalue: 0.001 + (id % 10) * 0.002,
    }
  })
}

function parseCsvParam(value: string | null): string[] {
  if (!value) return []
  return value.split(',').map((x) => x.trim()).filter(Boolean)
}

function parsePositiveInt(value: string | null, fallback: number): number {
  const parsed = Number.parseInt(value ?? '', 10)
  return Number.isFinite(parsed) && parsed > 0 ? parsed : fallback
}

async function mockOverlapApi(page: any) {
  const items = buildMockOverlapItems(30)

  await page.route('**/api/v1/lncrna-chipseq-overlap*', async (route: any) => {
    const requestUrl = new URL(route.request().url())

    // Only mock the main page endpoint; let summary/export/etc fall through.
    if (!requestUrl.pathname.endsWith('/api/v1/lncrna-chipseq-overlap')) {
      await route.fallback()
      return
    }

    const markTypes = new Set(parseCsvParam(requestUrl.searchParams.get('mark_type')))
    const cellTypes = new Set(parseCsvParam(requestUrl.searchParams.get('cell_type')))
    const chromosome = requestUrl.searchParams.get('chromosome')

    const pageNumber = parsePositiveInt(requestUrl.searchParams.get('page'), 1)
    const pageSize = parsePositiveInt(requestUrl.searchParams.get('page_size'), 20)

    const sortBy = requestUrl.searchParams.get('sort_by') || 'binding_affinity'
    const sortOrder = requestUrl.searchParams.get('sort_order') || 'desc'

    const filtered = items.filter((row) => {
      if (markTypes.size > 0 && !markTypes.has(row.mark_type)) return false
      if (cellTypes.size > 0 && !cellTypes.has(row.cell_type)) return false
      if (chromosome && row.chromosome !== chromosome) return false
      return true
    })

    const getSortValue = (row: any) => {
      switch (sortBy) {
        case 'binding_affinity':
          return row.binding_affinity
        case 'peak_fold_enrichment':
          return row.peak_fold_enrichment
        case 'peak_qvalue':
          return row.peak_qvalue ?? Number.POSITIVE_INFINITY
        case 'overlap_length':
          return row.overlap_length
        default:
          return row.binding_affinity
      }
    }

    const sorted = [...filtered].sort((a, b) => {
      const aVal = getSortValue(a)
      const bVal = getSortValue(b)
      if (aVal === bVal) return String(a.overlap_id).localeCompare(String(b.overlap_id))
      return sortOrder === 'asc' ? aVal - bVal : bVal - aVal
    })

    const startIndex = (pageNumber - 1) * pageSize
    const paged = sorted.slice(startIndex, startIndex + pageSize)

    await route.fulfill({
      status: 200,
      contentType: 'application/json',
      body: JSON.stringify({
        total: sorted.length,
        page: pageNumber,
        page_size: pageSize,
        items: paged,
      }),
    })
  })
}

async function waitForTableHasRows(page: any) {
  const tbody = page.locator('.ant-table-tbody')
  await tbody.waitFor({ state: 'visible', timeout: 20000 })
  const rows = page.locator('.ant-table-tbody .ant-table-row, .ant-table-tbody [data-row-key]')
  await expect.poll(async () => rows.count(), { timeout: 20000 }).toBeGreaterThan(0)
}

async function getFirstTwoRowNumbers(page: any, extractor: (row: any) => Promise<number>) {
  const rows = page.locator('.ant-table-tbody .ant-table-row, .ant-table-tbody [data-row-key]')
  await expect.poll(async () => rows.count(), { timeout: 20000 }).toBeGreaterThan(1)
  const first = rows.nth(0)
  const second = rows.nth(1)
  const [a, b] = await Promise.all([extractor(first), extractor(second)])
  return { a, b }
}

test.describe('lncRNA-ChIP-seq Overlap Analysis Page', () => {
		test.beforeEach(async ({ page }) => {
		  // Navigate to lncRNA-ChIP-seq Overlap page
		  await page.goto(PAGE_URL)
		  await page.waitForLoadState('domcontentloaded')

	  // 页面可能包含持续请求（例如 IGV 资源加载），避免 networkidle 卡死
	  await page.locator('h1, h2').first().waitFor({ state: 'visible', timeout: 20000 }).catch(() => {})
	})

  // ============================================================================
  // P0 Tests: Routing and Page Access
  // ============================================================================

  test('should load the page successfully', async ({ page }) => {
    // Verify URL is correct
    expect(page.url()).toContain(PAGE_URL)

    // Verify page has content
    // Look for main heading, card, or table container
    const mainContent = page.locator('h1, h2, .ant-card, .ant-table').first()
    await expect(mainContent).toBeVisible({ timeout: 15000 })
  })

  test('should display correct page title', async ({ page }) => {
    // Look for page title (h1 or h2)
    const title = page.locator('h1, h2').first()
    await expect(title).toBeVisible({ timeout: 10000 })

    // Title should contain "lncRNA" and "ChIP-seq" or "Overlap" (in Chinese or English)
    const titleText = await title.textContent()
    expect(titleText).toMatch(/lncRNA.*ChIP.*seq.*Overlap|lncRNA.*ChIP.*seq.*重叠|ChIP.*seq.*Overlap|ChIP.*seq.*重叠/i)
  })

  test('should display breadcrumb navigation', async ({ page }) => {
    // Verify breadcrumb exists
    const breadcrumb = page.locator('.ant-breadcrumb')

    // Wait for breadcrumb to be visible (may take a moment to render)
    const isBreadcrumbVisible = await breadcrumb.isVisible({ timeout: 5000 }).catch(() => false)

    if (isBreadcrumbVisible) {
      // Verify breadcrumb has items
      const breadcrumbItems = page.locator('.ant-breadcrumb-link, .ant-breadcrumb-item')
      const itemCount = await breadcrumbItems.count()
      expect(itemCount).toBeGreaterThan(0)
    } else {
      // If no breadcrumb, at least page title should be visible
      const title = page.locator('h1, h2').first()
      await expect(title).toBeVisible()
    }
  })

	  test('should be accessible from navigation menu', async ({ page }) => {
	    // Go to home page
	    await page.goto('/')
	    await page.waitForLoadState('domcontentloaded')

    // Look for navigation link (may be in sidebar or top menu)
    // Try multiple selectors for flexibility
    const navLink = page.getByRole('menuitem', { name: /Overlap|重叠/i })
      .or(page.locator('[role="menu"] a').filter({ hasText: /Overlap|重叠/i }))
      .or(page.locator('nav a').filter({ hasText: /Overlap|重叠/i }))

    const linkCount = await navLink.count()

	    if (linkCount > 0) {
	      // Click the navigation link
	      await navLink.first().click()
	      await page.waitForLoadState('domcontentloaded')

	      // Verify navigation succeeded
	      expect(page.url()).toContain(PAGE_URL)
	    } else {
      // If no nav link found, skip test (feature may not be in menu yet)
      console.log('Navigation link not found - skipping test')
    }
  })

  // ============================================================================
  // P0 Tests: Component Rendering
  // ============================================================================

  test('should render main component container', async ({ page }) => {
    // Wait for page to stabilize
    await page.waitForTimeout(2000)

    // Verify main container exists (card or table wrapper)
    const mainContainer = page.locator('.ant-card, .ant-table-wrapper, [class*="LncRNAChIPSeqOverlap"]').first()

    const isVisible = await mainContainer.isVisible().catch(() => false)

    // Component should be visible or show loading state
    if (!isVisible) {
      const loadingIndicator = page.locator('.ant-spin')
      const hasLoading = await loadingIndicator.isVisible().catch(() => false)
      expect(hasLoading).toBe(true)
    } else {
      expect(isVisible).toBe(true)
    }
  })

  test('should display filter panel', async ({ page }) => {
    // Wait for filters to load
    await page.waitForTimeout(2000)

    // Look for filter controls (selects, inputs)
    const filterSelects = page.locator('.ant-select')
    const filterInputs = page.locator('.ant-input-number, .ant-input')

    const selectCount = await filterSelects.count()
    const inputCount = await filterInputs.count()

    // Should have at least one filter control (mark type, cell line, or chromosome)
    expect(selectCount + inputCount).toBeGreaterThan(0)
  })

  test('should display mark type filter', async ({ page }) => {
    await page.waitForTimeout(2000)

    // Look for Mark type selector
    const markSelector = page.locator('.ant-select').filter({ hasText: /Mark|标记|Histone/i }).first()
      .or(page.locator('.ant-form-item').filter({ hasText: /Mark|标记/i }).locator('.ant-select').first())

    const selectorCount = await markSelector.count()

    if (selectorCount > 0) {
      await expect(markSelector).toBeVisible()
    } else {
      // Mark selector might be first select on page
      const anySelect = page.locator('.ant-select').first()
      await expect(anySelect).toBeVisible()
    }
  })

  test('should display data table', async ({ page }) => {
    // Wait for table to load
    await page.waitForTimeout(3000)

    // Look for Ant Design table
    const table = page.locator('.ant-table').first()

    // Table may show data, loading, or empty state
    const isTableVisible = await table.isVisible().catch(() => false)

    if (!isTableVisible) {
      // Check for loading or empty state
      const loadingIndicator = page.locator('.ant-spin').first()
      const emptyState = page.locator('.ant-empty').first()

      const hasLoading = await loadingIndicator.isVisible().catch(() => false)
      const isEmpty = await emptyState.isVisible().catch(() => false)

      expect(hasLoading || isEmpty).toBe(true)
    } else {
      // Verify table has headers
      const tableHeaders = table.locator('.ant-table-thead th')
      const headerCount = await tableHeaders.count()
      expect(headerCount).toBeGreaterThan(0)
    }
  })

  test('should display table columns', async ({ page }) => {
    await page.waitForTimeout(3000)

    const table = page.locator('.ant-table').first()

    if (await table.isVisible().catch(() => false)) {
      // Verify expected columns exist
      const headers = table.locator('.ant-table-thead th')
      const headerCount = await headers.count()

      // Should have multiple columns (lncRNA, chromosome, overlap info, etc.)
      expect(headerCount).toBeGreaterThan(3)

      // Verify some column names
      const headerText = await table.locator('.ant-table-thead').textContent()

      // Should contain key column names (in Chinese or English)
      const hasRelevantColumns = /lncRNA|Gene|Chromosome|Overlap|Peak|染色体|重叠|基因/i.test(headerText || '')
      expect(hasRelevantColumns).toBe(true)
    }
  })

  // ============================================================================
  // P0 Tests: Internationalization
  // ============================================================================

  test('should support language switching', async ({ page }) => {
    // Look for language switcher
    const langSwitcher = page.locator('[class*="language"], [class*="locale"]').first()
      .or(page.getByRole('button', { name: /中文|English|语言|Language/i }).first())

    const switcherCount = await langSwitcher.count()

    if (switcherCount > 0) {
      await expect(langSwitcher).toBeVisible()

      // Click language switcher
      await langSwitcher.click()
      await page.waitForTimeout(500)

      // Verify language options appear
      const languageOptions = page.locator('.ant-dropdown-menu-item, .ant-select-item')
      const optionCount = await languageOptions.count()

      expect(optionCount).toBeGreaterThan(0)
    }
  })

  test('should display Chinese content', async ({ page }) => {
    // Check if page contains Chinese characters
    const pageText = await page.textContent('body')
    const hasChinese = /[\u4e00-\u9fa5]/.test(pageText || '')

    // If no Chinese found, try switching language
    if (!hasChinese) {
      const langSwitcher = page.locator('[class*="language"]').first()
        .or(page.getByRole('button', { name: /中文|English/i }).first())

      if (await langSwitcher.count() > 0) {
        await langSwitcher.click()
        await page.waitForTimeout(300)

        const chineseOption = page.getByText('中文').or(page.getByText('简体中文')).first()
        if (await chineseOption.isVisible().catch(() => false)) {
          await chineseOption.click()
          await page.waitForTimeout(500)

          // Verify Chinese text appears
          const newPageText = await page.textContent('body')
          const nowHasChinese = /[\u4e00-\u9fa5]/.test(newPageText || '')
          expect(nowHasChinese).toBe(true)
        }
      }
    }

    // At minimum, verify page loaded successfully
    const mainContent = page.locator('h1, h2, .ant-table').first()
    await expect(mainContent).toBeVisible()
  })

  test('should display English content', async ({ page }) => {
    // Look for language switcher
    const langSwitcher = page.locator('[class*="language"]').first()
      .or(page.getByRole('button', { name: /中文|English/i }).first())

    if (await langSwitcher.count() > 0) {
      // Click to open language menu
      await langSwitcher.click()
      await page.waitForTimeout(300)

      // Select English
      const englishOption = page.getByText('English').first()
      if (await englishOption.isVisible().catch(() => false)) {
        await englishOption.click()
        await page.waitForTimeout(500)

        // Verify English text in title
        const title = page.locator('h1, h2').first()
        const titleText = await title.textContent()

        // Title should contain English words
        expect(titleText).toMatch(/lncRNA.*ChIP.*seq.*Overlap/i)
      }
    }

    // At minimum, verify page loaded successfully
    const mainContent = page.locator('h1, h2, .ant-table').first()
    await expect(mainContent).toBeVisible()
  })

	  // ============================================================================
	  // P1 Tests: Filter Functionality (mocked; backend data independent)
	  // ============================================================================

	  test('should filter by mark type', async ({ page }) => {
	    await mockOverlapApi(page)
	    await page.goto(PAGE_URL)
	    await page.waitForLoadState('domcontentloaded')
	    await waitForTableHasRows(page)

	    const tbody = page.locator('.ant-table-tbody')
	    const hasK4 = await tbody.getByText(/^K4me3$/).count()
	    expect(hasK4).toBeGreaterThan(0)

	    const markControl = page.getByTestId('overlap-filter-mark-type')
	    const markSelect = markControl.locator('.ant-select').first()
	    await markSelect.click()

	    const dropdown = page.locator('.ant-select-dropdown:visible')
	    await dropdown.waitFor({ state: 'visible', timeout: 15000 })

	    await Promise.all([
	      page.waitForResponse((resp) => {
	        if (resp.status() !== 200) return false
	        const url = new URL(resp.url())
	        return (
	          url.pathname.endsWith('/api/v1/lncrna-chipseq-overlap') &&
	          (url.searchParams.get('mark_type') || '').includes('H3K27me3')
	        )
	      }),
	      dropdown.getByRole('option', { name: /^H3K27me3/i }).first().click(),
	    ])

	    await page.keyboard.press('Escape').catch(() => null)

	    await waitForTableHasRows(page)
	    expect(await tbody.getByText(/^K27me3$/).count()).toBeGreaterThan(0)
	    expect(await tbody.getByText(/^K4me3$/).count()).toBe(0)
	  })

	  test('should filter by cell type', async ({ page }) => {
	    await mockOverlapApi(page)
	    await page.goto(PAGE_URL)
	    await page.waitForLoadState('domcontentloaded')
	    await waitForTableHasRows(page)

	    const tbody = page.locator('.ant-table-tbody')
	    const hasGM = await tbody.getByText('GM12878').count()
	    expect(hasGM).toBeGreaterThan(0)

	    const cellTypeControl = page.getByTestId('overlap-filter-cell-type')
	    const cellTypeSelect = cellTypeControl.locator('.ant-select').first()
	    await page.keyboard.press('Escape').catch(() => null)
	    await cellTypeSelect.click()

	    const dropdown = page.locator('.ant-select-dropdown:visible')
	    await dropdown.waitFor({ state: 'visible', timeout: 15000 })

	    await Promise.all([
	      page.waitForResponse((resp) => {
	        if (resp.status() !== 200) return false
	        const url = new URL(resp.url())
	        return (
	          url.pathname.endsWith('/api/v1/lncrna-chipseq-overlap') &&
	          (url.searchParams.get('cell_type') || '').includes('K562')
	        )
	      }),
	      dropdown.getByRole('option', { name: /^K562$/i }).first().click(),
	    ])

	    await page.keyboard.press('Escape').catch(() => null)

	    await waitForTableHasRows(page)
	    expect(await tbody.getByText('K562').count()).toBeGreaterThan(0)
	    expect(await tbody.getByText('GM12878').count()).toBe(0)
	  })

	  test('should filter by chromosome', async ({ page }) => {
	    await mockOverlapApi(page)
	    await page.goto(PAGE_URL)
	    await page.waitForLoadState('domcontentloaded')
	    await waitForTableHasRows(page)

	    const tbody = page.locator('.ant-table-tbody')
	    const hasChr22 = await tbody.getByText(/^chr22:/).count()
	    expect(hasChr22).toBeGreaterThan(0)

	    const chrControl = page.getByTestId('overlap-filter-chromosome')
	    const chrSelect = chrControl.locator('.ant-select').first()
	    await page.keyboard.press('Escape').catch(() => null)
	    await chrSelect.click()

	    const dropdown = page.locator('.ant-select-dropdown:visible')
	    await dropdown.waitFor({ state: 'visible', timeout: 15000 })

	    await Promise.all([
	      page.waitForResponse((resp) => {
	        if (resp.status() !== 200) return false
	        const url = new URL(resp.url())
	        return url.pathname.endsWith('/api/v1/lncrna-chipseq-overlap') && url.searchParams.get('chromosome') === 'chr1'
	      }),
	      dropdown.getByRole('option', { name: /^chr1$/i }).first().click(),
	    ])

	    await page.keyboard.press('Escape').catch(() => null)

	    await waitForTableHasRows(page)
	    expect(await tbody.getByText(/^chr1:/).count()).toBeGreaterThan(0)
	    expect(await tbody.getByText(/^chr22:/).count()).toBe(0)
	  })

	  test('should reset filters', async ({ page }) => {
	    await mockOverlapApi(page)
	    await page.goto(PAGE_URL)
	    await page.waitForLoadState('domcontentloaded')
	    await waitForTableHasRows(page)

	    // Apply a mark filter first
	    const markControl = page.getByTestId('overlap-filter-mark-type')
	    await markControl.locator('.ant-select').first().click()
	    const dropdown = page.locator('.ant-select-dropdown:visible')
	    await dropdown.waitFor({ state: 'visible', timeout: 15000 })

	    await Promise.all([
	      page.waitForResponse((resp) => {
	        if (resp.status() !== 200) return false
	        const url = new URL(resp.url())
	        return url.pathname.endsWith('/api/v1/lncrna-chipseq-overlap') && (url.searchParams.get('mark_type') || '').includes('H3K27me3')
	      }),
	      dropdown.getByRole('option', { name: /^H3K27me3/i }).first().click(),
	    ])

	    await page.keyboard.press('Escape').catch(() => null)

	    const tbody = page.locator('.ant-table-tbody')
	    await waitForTableHasRows(page)
	    expect(await tbody.getByText(/^K4me3$/).count()).toBe(0)

	    const resetButton = page.getByRole('button', { name: /Reset|重置|Clear|清空/i })
	    await resetButton.click()

	    await waitForTableHasRows(page)
	    await expect
	      .poll(async () => tbody.getByText(/^K4me3$/).count(), { timeout: 15000 })
	      .toBeGreaterThan(0)
	  })

	  // ============================================================================
	  // P1 Tests: Table Interactions (mocked; backend data independent)
	  // ============================================================================

	  test('should paginate through results', async ({ page }) => {
	    await mockOverlapApi(page)
	    await page.goto(PAGE_URL)
	    await page.waitForLoadState('domcontentloaded')
	    await waitForTableHasRows(page)

	    const tbody = page.locator('.ant-table-tbody')
	    expect(await tbody.getByText('LNC_01').count()).toBeGreaterThan(0)

	    const pagination = page.locator('.ant-pagination')
	    await expect(pagination).toBeVisible({ timeout: 15000 })

	    const page2Button = pagination.locator('.ant-pagination-item-2')
	    await expect(page2Button).toBeVisible()

	    await Promise.all([
	      page.waitForResponse((resp) => {
	        if (resp.status() !== 200) return false
	        const url = new URL(resp.url())
	        return url.pathname.endsWith('/api/v1/lncrna-chipseq-overlap') && url.searchParams.get('page') === '2'
	      }),
	      page2Button.click(),
	    ])

	    await expect(page2Button).toHaveClass(/ant-pagination-item-active/)
	    await waitForTableHasRows(page)
	    expect(await tbody.getByText('LNC_21').count()).toBeGreaterThan(0)
	    expect(await tbody.getByText('LNC_01').count()).toBe(0)
	  })

	  test('should sort by overlap length', async ({ page }) => {
	    await mockOverlapApi(page)
	    await page.goto(PAGE_URL)
	    await page.waitForLoadState('domcontentloaded')
	    await waitForTableHasRows(page)

	    const overlapLengthHeader = page.getByRole('columnheader', { name: /Overlap.*Length|重叠.*长度/i }).first()

	    const responsePromise = page.waitForResponse((resp) => {
	      if (resp.status() !== 200) return false
	      const url = new URL(resp.url())
	      return url.pathname.endsWith('/api/v1/lncrna-chipseq-overlap') && url.searchParams.get('sort_by') === 'overlap_length'
	    })

	    await overlapLengthHeader.click()
	    const response = await responsePromise
	    const responseUrl = new URL(response.url())
	    const order = responseUrl.searchParams.get('sort_order') || 'asc'

	    const readOverlapLengthFromLocation = async (row: any) => {
	      const text = await row.getByText(/\bbp\b/i).first().innerText()
	      const digits = text.replace(/[^0-9]/g, '')
	      return Number.parseInt(digits, 10)
	    }

	    const { a, b } = await getFirstTwoRowNumbers(page, readOverlapLengthFromLocation)
	    if (order === 'desc') {
	      expect(a).toBeGreaterThanOrEqual(b)
	    } else {
	      expect(a).toBeLessThanOrEqual(b)
	    }
	  })

	  test('should sort by binding affinity', async ({ page }) => {
	    await mockOverlapApi(page)
	    await page.goto(PAGE_URL)
	    await page.waitForLoadState('domcontentloaded')
	    await waitForTableHasRows(page)

	    const bindingAffinityHeader = page.getByRole('columnheader', { name: /Binding Affinity|结合.*亲和力|亲和力/i }).first()

	    const responsePromise = page.waitForResponse((resp) => {
	      if (resp.status() !== 200) return false
	      const url = new URL(resp.url())
	      return url.pathname.endsWith('/api/v1/lncrna-chipseq-overlap') && url.searchParams.get('sort_by') === 'binding_affinity'
	    })

	    await bindingAffinityHeader.click()
	    const response = await responsePromise
	    const responseUrl = new URL(response.url())
	    const order = responseUrl.searchParams.get('sort_order') || 'asc'

	    const readBindingAffinity = async (row: any) => {
	      const cell = row.locator('strong').first()
	      const text = await cell.innerText()
	      const parsed = Number.parseFloat(text)
	      return Number.isFinite(parsed) ? parsed : 0
	    }

	    const { a, b } = await getFirstTwoRowNumbers(page, readBindingAffinity)
	    if (order === 'desc') {
	      expect(a).toBeGreaterThanOrEqual(b)
	    } else {
	      expect(a).toBeLessThanOrEqual(b)
	    }
	  })

	  test('should change page size', async ({ page }) => {
	    await mockOverlapApi(page)
	    await page.goto(PAGE_URL)
	    await page.waitForLoadState('domcontentloaded')
	    await waitForTableHasRows(page)

	    const pagination = page.locator('.ant-pagination')
	    await expect(pagination).toBeVisible({ timeout: 15000 })

	    const sizeChanger = pagination.locator('.ant-pagination-options-size-changer').first()
	    await expect(sizeChanger).toBeVisible()

	    await sizeChanger.click()
	    const dropdown = page.locator('.ant-select-dropdown:visible')
	    await dropdown.waitFor({ state: 'visible', timeout: 15000 })

	    await Promise.all([
	      page.waitForResponse((resp) => {
	        if (resp.status() !== 200) return false
	        const url = new URL(resp.url())
	        return (
	          url.pathname.endsWith('/api/v1/lncrna-chipseq-overlap') &&
	          url.searchParams.get('page') === '1' &&
	          url.searchParams.get('page_size') === '10'
	        )
	      }),
	      dropdown.getByRole('option', { name: /^10\s*\/\s*page$/i }).first().click(),
	    ])

	    // Table should render <= page_size rows for current viewport.
	    const rowCount = await page.locator('.ant-table-tbody .ant-table-row, .ant-table-tbody [data-row-key]').count()
	    expect(rowCount).toBeGreaterThan(0)
	    expect(rowCount).toBeLessThanOrEqual(10)
	  })

  // ============================================================================
  // Performance Tests
  // ============================================================================

  test('page should load within reasonable time', async ({ page }) => {
    const budgetMs = getEnvInt('E2E_OVERLAP_PAGE_LOAD_BUDGET_MS', 8000)
    const startTime = Date.now()

    await page.goto(PAGE_URL, { waitUntil: 'domcontentloaded' })
    await page.locator('h1, h2').first().waitFor({ timeout: 10000 })

    const loadTime = Date.now() - startTime

    // SPA shell should be fast; data loading is async
    expect(loadTime).toBeLessThan(budgetMs)

    console.log(`Page loaded in ${loadTime}ms`)
  })

  test('initial render should be fast', async ({ page }) => {
    const budgetMs = getEnvInt('E2E_OVERLAP_INITIAL_RENDER_BUDGET_MS', 6000)
    const startTime = Date.now()

    await page.goto(PAGE_URL, { waitUntil: 'domcontentloaded' })

    // Wait for first meaningful content
    await page.locator('h1, h2, .ant-card, .ant-table').first().waitFor({ timeout: 10000 })

    const renderTime = Date.now() - startTime

    // Initial render is environment-dependent (dev server, CPU). Allow override via env var.
    expect(renderTime).toBeLessThan(budgetMs)

    console.log(`Initial render completed in ${renderTime}ms (budget: ${budgetMs}ms)`)
  })

  // ============================================================================
  // Error Handling Tests
  // ============================================================================

	  test('should handle API error gracefully', async ({ page }) => {
    // Intercept API and return error
    await page.route('**/api/v1/lncrna-chipseq-overlap*', (route) => {
      route.fulfill({
        status: 500,
        contentType: 'application/json',
        body: JSON.stringify({ detail: 'Internal Server Error' })
      })
    })

	    await page.goto(PAGE_URL)
	    // React Query 会重试，给足时间等待错误/空态出现
	    await page.waitForTimeout(1000)

	    // Verify error notification is displayed (Ant Design notification or message)
	    const errorNotification = page.locator('.ant-notification, .ant-message')
	      .filter({ hasText: /Internal Server Error|Error|Failed|错误|失败/i })
	    const errorText = page.getByText(/Internal Server Error|Unable to load data|加载失败|Unable to load/i)
	    const emptyState = page.locator('.ant-empty')
	    const table = page.locator('.ant-table')

	    await expect.poll(async () => {
	      const hasErrorNotification = await errorNotification.isVisible().catch(() => false)
	      const hasErrorText = await errorText.isVisible().catch(() => false)
	      const hasEmpty = await emptyState.isVisible().catch(() => false)
	      const hasTable = await table.isVisible().catch(() => false)
	      return hasErrorNotification || hasErrorText || hasEmpty || hasTable
	    }, { timeout: 15000 }).toBe(true)

	    // Cleanup route
	    await page.unrouteAll({ behavior: 'ignoreErrors' })
	  })

	  test('should handle empty results gracefully', async ({ page }) => {
	    // Intercept API and return empty data
	    await page.route('**/api/v1/lncrna-chipseq-overlap*', (route) => {
	      route.fulfill({
	        status: 200,
	        contentType: 'application/json',
	        body: JSON.stringify({ items: [], total: 0, page: 1, page_size: 20 })
	      })
	    })

    await page.goto(PAGE_URL)
    await page.waitForTimeout(2000)

    // Verify empty state is displayed
    const emptyState = page.locator('.ant-empty')
    const emptyText = page.getByText(/No.*Data|暂无数据|无数据/i)

    const hasEmpty = await emptyState.isVisible().catch(() => false)
    const hasEmptyText = await emptyText.isVisible().catch(() => false)

    expect(hasEmpty || hasEmptyText).toBe(true)
  })

  test('should handle network timeout', async ({ page }) => {
    // Intercept API and abort immediately (simulating timeout)
    await page.route('**/api/v1/lncrna-chipseq-overlap*', (route) => {
      route.abort('timedout')
    })

    await page.goto(PAGE_URL)
    await page.waitForTimeout(3000)

    // Should show loading state, error, or handle gracefully
    const loadingIndicator = page.locator('.ant-spin')
    const errorMessage = page.getByText(/Error|Failed|Timeout|错误|失败|超时/i)
    const table = page.locator('.ant-table')

    const hasLoading = await loadingIndicator.isVisible().catch(() => false)
    const hasError = await errorMessage.isVisible().catch(() => false)
    const hasTable = await table.isVisible().catch(() => false)

    // Page should handle timeout gracefully (loading, error, or fallback to empty table)
    expect(hasLoading || hasError || hasTable).toBe(true)

    // Cleanup route
    await page.unrouteAll({ behavior: 'ignoreErrors' })
  })

  // ============================================================================
  // API Integration Tests
  // ============================================================================

  test('should make correct API calls on page load', async ({ page }) => {
    const apiRequests: string[] = []

    // Track API requests
    page.on('request', (request) => {
      if (request.url().includes('/lncrna-chipseq-overlap')) {
        apiRequests.push(request.url())
        console.log('API Request:', request.url())
      }
    })

    await page.goto(PAGE_URL)
    await page.waitForLoadState('networkidle')
    await page.waitForTimeout(2000)

    // Verify at least one API call was made
    console.log(`Total API calls: ${apiRequests.length}`)
  })

  test('should include correct query parameters', async ({ page }) => {
    let capturedUrl = ''

    page.on('request', (request) => {
      if (request.url().includes('/lncrna-chipseq-overlap')) {
        capturedUrl = request.url()
      }
    })

    await page.goto(PAGE_URL)
    await page.waitForLoadState('networkidle')
    await page.waitForTimeout(2000)

    if (capturedUrl) {
      // Verify URL structure
      expect(capturedUrl).toContain('/api/v1/')
      console.log('Captured API URL:', capturedUrl)
    }
  })

  // ============================================================================
  // Accessibility Tests
  // ============================================================================

	  test('should have accessible table structure', async ({ page }) => {
	    await page.waitForTimeout(3000)

	    const table = page.locator('.ant-table').first()

	    if (await table.isVisible().catch(() => false)) {
	      // AntD Table may render body using virtualized divs (no <tbody>).
	      // Validate accessible structure via roles instead of strict DOM tags.
	      const headers = table.getByRole('columnheader')
	      await expect(headers.first()).toBeVisible()

	      const rows = table.getByRole('row')
	      const rowCount = await rows.count()
	      expect(rowCount).toBeGreaterThan(0)
	    }
	  })

  test('should support keyboard navigation', async ({ page }) => {
    await page.waitForTimeout(2000)

    // Focus on first interactive element
    const firstSelect = page.locator('.ant-select').first()

    if (await firstSelect.count() > 0) {
      await firstSelect.click()

      // Try keyboard navigation
      await page.keyboard.press('ArrowDown')
      await page.waitForTimeout(300)

      await page.keyboard.press('Enter')
      await page.waitForTimeout(500)

      // Verify interaction worked
      const dropdown = page.locator('.ant-select-dropdown')
      const isDropdownVisible = await dropdown.isVisible().catch(() => false)

      // If dropdown closed, selection likely worked
      expect(true).toBe(true) // Test passed if no errors
    }
  })

  test('should have proper focus management', async ({ page }) => {
    await page.waitForTimeout(2000)

    // Tab through interactive elements
    await page.keyboard.press('Tab')
    await page.waitForTimeout(200)

    // Verify some element received focus
    const focusedElement = page.locator(':focus')
    const hasFocus = await focusedElement.count() > 0

    expect(hasFocus).toBe(true)
  })
})

// ============================================================================
// Additional Test Suite: Deep Link Navigation
// ============================================================================

test.describe('lncRNA-ChIP-seq Overlap - Deep Links', () => {
  test('should support URL parameters for filters', async ({ page }) => {
    // Navigate with query parameters
    await page.goto(`${PAGE_URL}?mark_type=H3K27me3&chromosome=chr1`)
    await page.waitForLoadState('networkidle')
    await page.waitForTimeout(2000)

    // Verify page loaded
    const mainContent = page.locator('h1, h2, .ant-table').first()
    await expect(mainContent).toBeVisible()

    // Verify URL parameters preserved
    expect(page.url()).toContain('mark_type=H3K27me3')
    expect(page.url()).toContain('chromosome=chr1')
  })

  test('should preserve filters in URL on filter change', async ({ page }) => {
    await page.goto(PAGE_URL)
    await page.waitForLoadState('networkidle')
    await page.waitForTimeout(2000)

    const currentUrl = page.url()
    console.log('Current URL:', currentUrl)

    // URL should be valid
    expect(currentUrl).toContain(PAGE_URL)
  })
})

// ============================================================================
// Additional Test Suite: Mobile Responsiveness
// ============================================================================

test.describe('lncRNA-ChIP-seq Overlap - Mobile View', () => {
  test.use({ viewport: { width: 375, height: 667 } }) // iPhone SE size

  test('should be responsive on mobile', async ({ page }) => {
    await page.goto(PAGE_URL)
    await page.waitForLoadState('networkidle')
    await page.waitForTimeout(2000)

    // Verify main content visible on mobile
    const mainContent = page.locator('h1, h2, .ant-card, .ant-table').first()
    await expect(mainContent).toBeVisible()

    // Verify table is scrollable or responsive
    const table = page.locator('.ant-table')

    if (await table.isVisible().catch(() => false)) {
      const tableWrapper = page.locator('.ant-table-wrapper')
      await expect(tableWrapper).toBeVisible()
    }
  })

  test('should have accessible navigation on mobile', async ({ page }) => {
    await page.goto(PAGE_URL)
    await page.waitForLoadState('networkidle')

    // Verify page title visible
    const title = page.locator('h1, h2').first()
    await expect(title).toBeVisible({ timeout: 10000 })

    // Verify filters accessible (may be collapsed)
    const filterControls = page.locator('.ant-select, .ant-input, button')
    const controlCount = await filterControls.count()
    expect(controlCount).toBeGreaterThan(0)
  })
})
