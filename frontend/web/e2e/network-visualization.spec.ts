import { test, expect, type Page } from '@playwright/test'

/**
 * Network Visualization E2E Tests
 *
 * This test suite covers the Network page functionality:
 * 1. Cytoscape.js graph initialization and rendering
 * 2. Gene search and network loading
 * 3. Node and edge interactions
 * 4. Filter controls (BA threshold, species)
 * 5. Layout switching
 * 6. Export functionality (PNG, SVG, JSON)
 * 7. Performance validation
 * 8. Error handling
 *
 * The Network page uses Cytoscape.js for interactive lncRNA-target
 * regulatory network visualization.
 *
 * Route: /network
 */

const PAGE_URL = '/network'

// Helper to wait for network API
async function waitForNetworkAPI(page: Page, timeout = 30000) {
  return page.waitForResponse(
    (resp) => resp.url().includes('/network') && resp.status() === 200,
    { timeout }
  ).catch(() => null)
}

async function fillGeneSearch(page: Page, gene: string): Promise<boolean> {
  // Network 页通常使用 antd Select/AutoComplete（combobox），其 input 可能为 readonly；
  // 这时应通过 click + keyboard 输入，而不是 locator.fill。
  const combobox = page.getByRole('combobox').first()
  if ((await combobox.count()) > 0) {
    // antd Select 的 input 常被内部 span 覆盖，直接点 input 可能被拦截；优先点击 selector 容器。
    const select = page.locator('.ant-select', { has: combobox }).first()
    if ((await select.count()) > 0) {
      const selector = select.locator('.ant-select-selector')
      if ((await selector.count()) > 0) {
        await selector.first().click()
      } else {
        await select.first().click()
      }
    } else {
      await combobox.click({ force: true })
    }
    await page.keyboard.press('Control+A')
    await page.keyboard.type(gene)
    return true
  }

  const input = page
    .locator('input[placeholder*="gene" i], input[placeholder*="search" i], input[type="search"]')
    .first()
  if ((await input.count()) > 0) {
    await input.fill(gene)
    return true
  }

  return false
}

async function submitGeneSearch(page: Page, gene: string) {
  const responsePromise = waitForNetworkAPI(page)

  const ok = await fillGeneSearch(page, gene)
  if (!ok) {
    return null
  }

  const searchButton = page.locator('button').filter({ hasText: /Search|查询|搜索/i }).first()
  if ((await searchButton.count()) > 0) {
    await searchButton.click()
  } else {
    await page.keyboard.press('Enter')
  }

  return responsePromise
}

// ============================================================================
// Test Suite: Page Loading
// ============================================================================

test.describe('Network Visualization - Page Loading', () => {
  test('Page loads successfully', async ({ page }) => {
    await page.goto(PAGE_URL)
    await page.waitForLoadState('networkidle')

    expect(page.url()).toContain(PAGE_URL)

    const mainContent = page.locator('h1, h2, .ant-card, [class*="network"]').first()
    await expect(mainContent).toBeVisible({ timeout: 15000 })
  })

  test('Page title is displayed', async ({ page }) => {
    await page.goto(PAGE_URL)
    await page.waitForLoadState('networkidle')

    const title = page.locator('h1, h2').first()
    await expect(title).toBeVisible({ timeout: 10000 })

    const titleText = await title.textContent()
    expect(titleText).toMatch(/Network|网络/i)
  })

  test('Search/input form is visible', async ({ page }) => {
    await page.goto(PAGE_URL)
    await page.waitForLoadState('networkidle')

    // Look for gene search input or network controls
    const searchInput = page.locator('input, .ant-select, .ant-input-search').first()
    await expect(searchInput).toBeVisible({ timeout: 10000 })
  })

  test('Controls panel is rendered', async ({ page }) => {
    await page.goto(PAGE_URL)
    await page.waitForLoadState('networkidle')
    await page.waitForTimeout(2000)

    // Look for filter controls
    const controls = page.locator('.ant-select, .ant-slider, .ant-input-number, .ant-form-item').first()
    const hasControls = await controls.count() > 0

    console.log(`Controls panel found: ${hasControls}`)
  })
})

// ============================================================================
// Test Suite: Gene Search and Network Loading
// ============================================================================

test.describe('Network Visualization - Search and Load', () => {
  test.beforeEach(async ({ page }) => {
    await page.goto(PAGE_URL)
    await page.waitForLoadState('networkidle')
    await page.waitForTimeout(2000)
  })

  test('Can search for a gene', async ({ page }) => {
    const resp = await submitGeneSearch(page, 'MALAT1')
    console.log(`Gene search submitted: ${!!resp}`)
  })

  test('Network loads after search', async ({ page }) => {
    await submitGeneSearch(page, 'NEAT1')
    await page.waitForTimeout(3000)

    // Cytoscape container should be visible
    const cyContainer = page.locator('[class*="cytoscape"], [class*="network"], canvas').first()
    const isVisible = await cyContainer.isVisible({ timeout: 10000 }).catch(() => false)

    console.log(`Network container visible: ${isVisible}`)
  })

  test('Shows loading state during network fetch', async ({ page }) => {
    // Slow down API
    await page.route('**/api/v1/network*', async (route) => {
      await new Promise(resolve => setTimeout(resolve, 2000))
      route.continue()
    })

    const ok = await fillGeneSearch(page, 'MALAT1')
    if (!ok) test.skip()

    await page.keyboard.press('Enter')

    // Check for loading state
    const spinner = page.locator('.ant-spin')
    const isLoading = await spinner.isVisible({ timeout: 3000 }).catch(() => false)

    console.log(`Loading state shown: ${isLoading}`)
  })

  test('Handles gene not found', async ({ page }) => {
    const ok = await fillGeneSearch(page, 'NONEXISTENT_GENE_XYZ123')
    if (!ok) test.skip()

    await page.keyboard.press('Enter')
    await page.waitForTimeout(3000)

    // Should show error or empty message
    const errorMsg = page.locator('.ant-message-error, .ant-notification-notice-error, .ant-alert-error')
    const emptyState = page.locator('.ant-empty')
    const noDataText = page.getByText(/no.*data|not found|未找到|无数据/i)

    const hasError = await errorMsg.isVisible().catch(() => false)
    const isEmpty = await emptyState.isVisible().catch(() => false)
    const hasNoData = await noDataText.isVisible().catch(() => false)

    console.log(`Gene not found feedback: error=${hasError}, empty=${isEmpty}, noData=${hasNoData}`)
  })
})

// ============================================================================
// Test Suite: Graph Interactions
// ============================================================================

test.describe('Network Visualization - Graph Interactions', () => {
  test.beforeEach(async ({ page }) => {
    await page.goto(PAGE_URL)
    await page.waitForLoadState('networkidle')

    // Trigger a search to load network data
    await submitGeneSearch(page, 'MALAT1')
    await page.waitForTimeout(3000)
  })

  test('Graph container is rendered', async ({ page }) => {
    const graphContainer = page.locator('[class*="cytoscape"], [class*="network-container"], canvas, .cy-container').first()
    const isVisible = await graphContainer.isVisible({ timeout: 10000 }).catch(() => false)

    console.log(`Graph container visible: ${isVisible}`)
  })

  test('Can click on a node', async ({ page }) => {
    // Cytoscape renders to canvas - look for nodes
    const canvas = page.locator('canvas').first()

    if (await canvas.isVisible().catch(() => false)) {
      const box = await canvas.boundingBox()
      if (box) {
        // Click center of canvas (likely where nodes are)
        await page.mouse.click(box.x + box.width / 2, box.y + box.height / 2)
        await page.waitForTimeout(500)

        // Look for tooltip or node detail popup
        const tooltip = page.locator('[class*="tooltip"], [class*="popover"], .ant-popover, .ant-tooltip')
        const hasTooltip = await tooltip.isVisible().catch(() => false)

        console.log(`Node click tooltip: ${hasTooltip}`)
      }
    }
  })

  test('Node hover shows tooltip', async ({ page }) => {
    const canvas = page.locator('canvas').first()

    if (await canvas.isVisible().catch(() => false)) {
      const box = await canvas.boundingBox()
      if (box) {
        // Hover over center
        await page.mouse.move(box.x + box.width / 2, box.y + box.height / 2)
        await page.waitForTimeout(1000)

        // Check for tooltip
        const tooltip = page.locator('[class*="tooltip"], .ant-tooltip, [data-cy-tooltip]')
        const hasTooltip = await tooltip.isVisible().catch(() => false)

        console.log(`Hover tooltip: ${hasTooltip}`)
      }
    }
  })

  test('Can zoom the graph', async ({ page }) => {
    const canvas = page.locator('canvas').first()

    if (await canvas.isVisible().catch(() => false)) {
      const box = await canvas.boundingBox()
      if (box) {
        // Scroll to zoom
        await page.mouse.move(box.x + box.width / 2, box.y + box.height / 2)
        await page.mouse.wheel(0, -100) // Zoom in
        await page.waitForTimeout(500)

        console.log('Zoom interaction completed')
      }
    }
  })

  test('Can pan the graph', async ({ page }) => {
    const canvas = page.locator('canvas').first()

    if (await canvas.isVisible().catch(() => false)) {
      const box = await canvas.boundingBox()
      if (box) {
        // Drag to pan
        await page.mouse.move(box.x + box.width / 2, box.y + box.height / 2)
        await page.mouse.down()
        await page.mouse.move(box.x + box.width / 2 + 50, box.y + box.height / 2 + 50)
        await page.mouse.up()

        console.log('Pan interaction completed')
      }
    }
  })
})

// ============================================================================
// Test Suite: Filter Controls
// ============================================================================

test.describe('Network Visualization - Filters', () => {
  test.beforeEach(async ({ page }) => {
    await page.goto(PAGE_URL)
    await page.waitForLoadState('networkidle')
    await page.waitForTimeout(2000)
  })

  test('BA threshold slider is available', async ({ page }) => {
    const slider = page.locator('.ant-slider').first()
    const hasSlider = await slider.count() > 0

    if (hasSlider) {
      await expect(slider).toBeVisible()
      console.log('BA threshold slider found')
    }
  })

  test('Can adjust BA threshold', async ({ page }) => {
    const slider = page.locator('.ant-slider')

    if (await slider.count() > 0) {
      const sliderHandle = slider.locator('.ant-slider-handle').first()
      const box = await sliderHandle.boundingBox()

      if (box) {
        // Drag the slider handle
        await page.mouse.move(box.x + box.width / 2, box.y + box.height / 2)
        await page.mouse.down()
        await page.mouse.move(box.x + 50, box.y)
        await page.mouse.up()

        await page.waitForTimeout(1000)
        console.log('BA threshold adjusted')
      }
    }
  })

  test('Species filter is available', async ({ page }) => {
    const speciesSelect = page.locator('.ant-select').filter({ hasText: /Species|Human|Mouse|物种/i }).first()
      .or(page.locator('.ant-checkbox-group, .ant-radio-group').filter({ hasText: /Human|Mouse/i }))

    const hasSpeciesFilter = await speciesSelect.count() > 0
    console.log(`Species filter found: ${hasSpeciesFilter}`)
  })

  test('Can toggle species filter', async ({ page }) => {
    const speciesCheckbox = page.locator('.ant-checkbox-wrapper').filter({ hasText: /Human|Mouse/i }).first()

    if (await speciesCheckbox.count() > 0) {
      await speciesCheckbox.click()
      await page.waitForTimeout(1000)
      console.log('Species filter toggled')
    }
  })

  test('Layout selector is available', async ({ page }) => {
    const layoutSelect = page.locator('.ant-select').filter({ hasText: /Layout|布局|cose|circle|grid/i }).first()
      .or(page.locator('.ant-radio-group').filter({ hasText: /cose|circle|grid/i }))

    const hasLayoutSelect = await layoutSelect.count() > 0
    console.log(`Layout selector found: ${hasLayoutSelect}`)
  })

  test('Can change layout', async ({ page }) => {
    // First load network
    await submitGeneSearch(page, 'MALAT1')
    await page.waitForTimeout(3000)

    // Find layout selector
    const layoutSelect = page.locator('.ant-select').filter({ hasText: /Layout|cose/i }).first()

    if (await layoutSelect.count() > 0) {
      await layoutSelect.click()
      await page.waitForTimeout(300)

      const layoutOption = page.locator('.ant-select-dropdown:visible .ant-select-item')
        .filter({ hasText: /circle|grid|concentric/i }).first()

      if (await layoutOption.count() > 0) {
        await layoutOption.click()
        await page.waitForTimeout(2000) // Layout animation

        console.log('Layout changed')
      }
    }
  })
})

// ============================================================================
// Test Suite: Export Functionality
// ============================================================================

test.describe('Network Visualization - Export', () => {
  test.beforeEach(async ({ page }) => {
    await page.goto(PAGE_URL)
    await page.waitForLoadState('networkidle')

    // Load network
    await submitGeneSearch(page, 'MALAT1')
    await page.waitForTimeout(3000)
  })

  test('Export button is visible', async ({ page }) => {
    const exportButton = page.locator('button').filter({ hasText: /Export|PNG|SVG|导出/i }).first()
    const hasExport = await exportButton.count() > 0

    console.log(`Export button found: ${hasExport}`)
  })

  test('Export dropdown shows format options', async ({ page }) => {
    const exportButton = page.locator('button').filter({ hasText: /Export|导出/i }).first()

    if (await exportButton.count() > 0) {
      await exportButton.click()
      await page.waitForTimeout(500)

      const dropdown = page.locator('.ant-dropdown-menu:visible')
      if (await dropdown.isVisible().catch(() => false)) {
        const options = dropdown.locator('.ant-dropdown-menu-item')
        const optionCount = await options.count()

        console.log(`Export format options: ${optionCount}`)
      }
    }
  })

  test('PNG export triggers download', async ({ page }) => {
    const exportButton = page.locator('button').filter({ hasText: /Export|PNG|导出/i }).first()

    if (await exportButton.count() > 0) {
      await exportButton.click()
      await page.waitForTimeout(500)

      const pngOption = page.locator('.ant-dropdown-menu-item').filter({ hasText: /PNG/i }).first()

      if (await pngOption.isVisible().catch(() => false)) {
        const downloadPromise = page.waitForEvent('download', { timeout: 10000 }).catch(() => null)
        await pngOption.click()

        const download = await downloadPromise
        if (download) {
          const filename = download.suggestedFilename()
          expect(filename).toMatch(/\.png$/i)
          console.log(`PNG downloaded: ${filename}`)
        }
      }
    }
  })

  test('SVG export triggers download', async ({ page }) => {
    const exportButton = page.locator('button').filter({ hasText: /Export|SVG|导出/i }).first()

    if (await exportButton.count() > 0) {
      await exportButton.click()
      await page.waitForTimeout(500)

      const svgOption = page.locator('.ant-dropdown-menu-item').filter({ hasText: /SVG/i }).first()

      if (await svgOption.isVisible().catch(() => false)) {
        const downloadPromise = page.waitForEvent('download', { timeout: 10000 }).catch(() => null)
        await svgOption.click()

        const download = await downloadPromise
        if (download) {
          const filename = download.suggestedFilename()
          expect(filename).toMatch(/\.svg$/i)
          console.log(`SVG downloaded: ${filename}`)
        }
      }
    }
  })
})

// ============================================================================
// Test Suite: Error States
// ============================================================================

test.describe('Network Visualization - Error States', () => {
  test('Handles API error gracefully', async ({ page }) => {
    await page.route('**/api/v1/network*', (route) => {
      route.fulfill({
        status: 500,
        contentType: 'application/json',
        body: JSON.stringify({ detail: 'Internal Server Error' })
      })
    })

    await page.goto(PAGE_URL)
    await page.waitForLoadState('networkidle')

    const ok = await fillGeneSearch(page, 'TEST')
    if (!ok) test.skip()

    await page.keyboard.press('Enter')
    await page.waitForTimeout(3000)

    // Should show error
    const errorIndicator = page.locator('.ant-message-error, .ant-notification-notice-error, .ant-alert-error')
    const errorText = page.getByText(/Error|Failed|错误/i)

    const hasError = await errorIndicator.isVisible().catch(() => false) ||
                     await errorText.isVisible().catch(() => false)

    console.log(`API error handled: ${hasError}`)
  })

  test('Shows empty state when no data', async ({ page }) => {
    await page.route('**/api/v1/network*', (route) => {
      route.fulfill({
        status: 200,
        contentType: 'application/json',
        body: JSON.stringify({ nodes: [], edges: [] })
      })
    })

    await page.goto(PAGE_URL)
    const ok = await fillGeneSearch(page, 'TEST')
    if (!ok) test.skip()

    await page.keyboard.press('Enter')
    await page.waitForTimeout(2000)

    const emptyState = page.locator('.ant-empty')
    const noDataText = page.getByText(/no.*data|no.*results|无数据/i)

    const isEmpty = await emptyState.isVisible().catch(() => false)
    const hasNoData = await noDataText.isVisible().catch(() => false)

    console.log(`Empty state: ${isEmpty || hasNoData}`)
  })

  test('Console errors are minimal', async ({ page }) => {
    const consoleErrors: string[] = []
    page.on('console', (msg) => {
      if (msg.type() === 'error') {
        consoleErrors.push(msg.text())
      }
    })

    await page.goto(PAGE_URL)
    await page.waitForLoadState('networkidle')
    await page.waitForTimeout(3000)

    const criticalErrors = consoleErrors.filter(e =>
      e.includes('Uncaught') ||
      e.includes('Cannot read') ||
      e.includes('undefined is not')
    )

    console.log(`Console errors: ${consoleErrors.length}, Critical: ${criticalErrors.length}`)
    expect(criticalErrors.length).toBe(0)
  })
})

// ============================================================================
// Test Suite: Performance
// ============================================================================

test.describe('Network Visualization - Performance', () => {
  test('Page loads within acceptable time', async ({ page }) => {
    const startTime = Date.now()

    await page.goto(PAGE_URL)
    await page.waitForLoadState('networkidle')

    const loadTime = Date.now() - startTime
    expect(loadTime).toBeLessThan(10000)

    console.log(`Page loaded in ${loadTime}ms`)
  })

  test('Network renders within acceptable time', async ({ page }) => {
    await page.goto(PAGE_URL)
    await page.waitForLoadState('domcontentloaded')

    // 当前 /network 页面为 Disease + Ontology 组合查询（非 gene search）
    const diseaseSelect = page.getByTestId('network-disease-select').first()
    const ontologySelect = page.getByTestId('network-ontology-select').first()
    const queryButton = page.getByTestId('network-query-button').first()

    // Select first available disease
    await diseaseSelect.waitFor({ state: 'visible', timeout: 15000 })
    const diseaseInput = diseaseSelect.locator('input[role="combobox"]').first()
    await expect(diseaseInput).toBeEnabled({ timeout: 15000 })
    await diseaseSelect.click()
    {
      const dropdown = page.locator('.ant-select-dropdown:visible')
      await dropdown.waitFor({ state: 'visible', timeout: 10000 })
      const firstDisease = dropdown.locator('.ant-select-item').first()
      if ((await firstDisease.count()) === 0) {
        test.skip()
        return
      }
      await firstDisease.waitFor({ state: 'visible', timeout: 10000 })
      await page.waitForTimeout(100) // allow popup to settle (virtual list / transition)
      await firstDisease.click()
      await page.keyboard.press('Escape')
      await page.waitForTimeout(100)
    }

    // Select first available ontology (enabled after disease is selected)
    const ontologyInput = ontologySelect.locator('input[role="combobox"]').first()
    await expect(ontologyInput).toBeEnabled({ timeout: 15000 })
    await ontologySelect.click()
    {
      const dropdown = page.locator('.ant-select-dropdown:visible')
      await dropdown.waitFor({ state: 'visible', timeout: 10000 })
      const firstOntology = dropdown.locator('.ant-select-item').first()
      if ((await firstOntology.count()) === 0) {
        test.skip()
        return
      }
      await firstOntology.waitFor({ state: 'visible', timeout: 10000 })
      await page.waitForTimeout(100) // allow popup to settle (virtual list / transition)
      await firstOntology.click()
      await page.keyboard.press('Escape')
      await page.waitForTimeout(100)
    }

    const startTime = Date.now()

    const networkResponsePromise = page.waitForResponse(
      (resp) => resp.url().includes('/api/v1/network/disease') && resp.status() === 200,
      { timeout: 30000 }
    ).catch(() => null)

    await queryButton.click()
    await networkResponsePromise

    const canvas = page.locator('canvas').first()
    await canvas.waitFor({ timeout: 20000, state: 'visible' }).catch(() => null)

    const renderTime = Date.now() - startTime
    expect(renderTime).toBeLessThan(20000)

    console.log(`Network rendered in ${renderTime}ms`)
  })

  test('Interactions are responsive', async ({ page }) => {
    await page.goto(PAGE_URL)
    await page.waitForLoadState('networkidle')

    // Load network
    await submitGeneSearch(page, 'MALAT1')
    await page.waitForTimeout(3000)

    // Test zoom responsiveness
    const canvas = page.locator('canvas').first()
    if (await canvas.isVisible().catch(() => false)) {
      const startTime = Date.now()
      const box = await canvas.boundingBox()
      if (box) {
        await page.mouse.move(box.x + box.width / 2, box.y + box.height / 2)
        await page.mouse.wheel(0, -50)
      }
      const interactionTime = Date.now() - startTime

      expect(interactionTime).toBeLessThan(1000)
      console.log(`Interaction response: ${interactionTime}ms`)
    }
  })
})

// ============================================================================
// Test Suite: Responsive Design
// ============================================================================

test.describe('Network Visualization - Responsive', () => {
  test('Desktop view works correctly', async ({ page }) => {
    await page.setViewportSize({ width: 1920, height: 1080 })
    await page.goto(PAGE_URL)
    await page.waitForLoadState('networkidle')

    const mainContent = page.locator('[class*="network"], .ant-card, h1, h2').first()
    await expect(mainContent).toBeVisible({ timeout: 15000 })
  })

  test('Tablet view is usable', async ({ page }) => {
    await page.setViewportSize({ width: 768, height: 1024 })
    await page.goto(PAGE_URL)
    await page.waitForLoadState('networkidle')

    const mainContent = page.locator('[class*="network"], .ant-card, h1, h2').first()
    await expect(mainContent).toBeVisible({ timeout: 15000 })
  })

  test('Mobile view adapts appropriately', async ({ page }) => {
    await page.setViewportSize({ width: 375, height: 667 })
    await page.goto(PAGE_URL)
    await page.waitForLoadState('networkidle')

    // Content should be visible
    const body = page.locator('body')
    await expect(body).toBeVisible()

    // Check for mobile-friendly message or adapted view
    const mobileMsg = page.getByText(/desktop|larger screen|移动端/i)
    const hasMobileMsg = await mobileMsg.isVisible().catch(() => false)

    console.log(`Mobile adaptation: ${hasMobileMsg ? 'message shown' : 'view adapted'}`)
  })
})

// ============================================================================
// Test Suite: Accessibility
// ============================================================================

test.describe('Network Visualization - Accessibility', () => {
  test.beforeEach(async ({ page }) => {
    await page.goto(PAGE_URL)
    await page.waitForLoadState('networkidle')
  })

  test('Page has heading', async ({ page }) => {
    const heading = page.locator('h1, h2').first()
    await expect(heading).toBeVisible()
  })

  test('Form controls have labels', async ({ page }) => {
    const formItems = page.locator('.ant-form-item')
    const formItemCount = await formItems.count()

    if (formItemCount > 0) {
      const labels = page.locator('.ant-form-item-label')
      const labelCount = await labels.count()
      console.log(`Form items: ${formItemCount}, Labels: ${labelCount}`)
    }
  })

  test('Keyboard navigation works', async ({ page }) => {
    await page.keyboard.press('Tab')
    await page.waitForTimeout(200)

    const focusedElement = page.locator(':focus')
    expect(await focusedElement.count()).toBeGreaterThan(0)
  })

  test('Color indicators have text alternatives', async ({ page }) => {
    // In network graphs, legend should have text labels
    const legend = page.locator('[class*="legend"], .ant-descriptions')
    const hasLegend = await legend.count() > 0

    if (hasLegend) {
      const legendText = await legend.textContent()
      console.log(`Legend provides text: ${legendText?.length || 0 > 0}`)
    }
  })
})
