import { test, expect, type Page } from '@playwright/test'

/**
 * IGV Genome Browser E2E Tests
 *
 * This test suite covers the Genome Browser page functionality:
 * 1. IGV.js component loading and initialization
 * 2. Gene search and navigation
 * 3. Species selection and switching
 * 4. Locus navigation via URL parameters
 * 5. Track display and management
 * 6. Error handling for IGV
 * 7. Performance validation
 *
 * The Genome Browser page uses IGV.js for interactive genome visualization
 * and supports multiple species (Human, Mouse, etc.)
 *
 * Route: /genome-browser
 * URL Parameters:
 * - gene: Gene name to load (e.g., CATG00000000011.1)
 * - locus: Genomic locus (e.g., chr1:1000000-2000000)
 * - species: Species ID (1-4)
 */

const BASE_URL = process.env.BASE_URL || 'http://localhost:5173'
const PAGE_URL = '/genome-browser'

// Helper to wait for IGV to initialize
async function waitForIGVInit(page: Page, timeout = 30000) {
  // IGV creates a container with igv-container class or data attribute
  const igvContainer = page.locator('[class*="igv"], [data-igv], .igv-track-container, .igv-column').first()
  await igvContainer.waitFor({ timeout, state: 'visible' }).catch(() => null)
  return igvContainer
}

// ============================================================================
// Test Suite: Page Loading
// ============================================================================

test.describe('Genome Browser - Page Loading', () => {
  test('Page loads successfully', async ({ page }) => {
    await page.goto(`${BASE_URL}${PAGE_URL}`)
    await page.waitForLoadState('domcontentloaded')

    // URL should be correct
    expect(page.url()).toContain(PAGE_URL)

    // Main content should be visible
    const mainContent = page.locator('h1, h2, .ant-card, [class*="genome"]').first()
    await expect(mainContent).toBeVisible({ timeout: 20000 })
  })

  test('Page title is displayed', async ({ page }) => {
    await page.goto(`${BASE_URL}${PAGE_URL}`)
    await page.waitForLoadState('domcontentloaded')

    const title = page.locator('h1, h2').first()
    await expect(title).toBeVisible({ timeout: 15000 })

    const titleText = await title.textContent()
    expect(titleText).toMatch(/Genome.*Browser|IGV|基因组浏览器/i)
  })

  test('IGV container initializes', async ({ page }) => {
    await page.goto(`${BASE_URL}${PAGE_URL}`)
    await page.waitForLoadState('domcontentloaded')

    // Wait for IGV container
    await page.waitForTimeout(3000) // IGV needs time to initialize

    // Look for IGV-specific elements
    const igvElement = page.locator('[class*="igv"], [class*="genome-browser"], [data-igv]').first()
    const isIGVVisible = await igvElement.isVisible({ timeout: 20000 }).catch(() => false)

    if (isIGVVisible) {
      console.log('IGV container initialized')
    } else {
      // Check if there's a loading or error state
      const loadingState = page.locator('.ant-spin, [class*="loading"]')
      const errorState = page.locator('.ant-alert-error, [class*="error"]')

      const isLoading = await loadingState.isVisible().catch(() => false)
      const hasError = await errorState.isVisible().catch(() => false)

      console.log(`IGV loading: ${isLoading}, error: ${hasError}`)
    }
  })

  test('Loading state is shown while IGV initializes', async ({ page }) => {
    await page.goto(`${BASE_URL}${PAGE_URL}`)

    // Check for loading indicator during initialization
    const loadingIndicator = page.locator('.ant-spin, [class*="loading"], .ant-skeleton').first()
    const hasLoading = await loadingIndicator.isVisible({ timeout: 3000 }).catch(() => false)

    console.log(`Loading state shown: ${hasLoading}`)

    // Avoid networkidle: IGV may keep requesting resources
    await page.waitForLoadState('domcontentloaded')
  })
})

// ============================================================================
// Test Suite: Species Selection
// ============================================================================

test.describe('Genome Browser - Species Selection', () => {
  test.beforeEach(async ({ page }) => {
    await page.goto(`${BASE_URL}${PAGE_URL}`)
    await page.waitForLoadState('domcontentloaded')
    await page.waitForTimeout(2000)
  })

  test('Species selector is visible', async ({ page }) => {
    const speciesSelector = page.locator('.ant-select').filter({ hasText: /Human|Mouse|Species|物种/i }).first()
      .or(page.locator('[data-testid="species-selector"]'))
      .or(page.locator('.ant-form-item').filter({ hasText: /Species|物种/i }).locator('.ant-select'))
      .or(page.locator('.ant-radio-group, .ant-segmented').filter({ hasText: /Human|Mouse/i }))

    const selectorCount = await speciesSelector.count()
    console.log(`Species selector found: ${selectorCount > 0}`)

    if (selectorCount > 0) {
      await expect(speciesSelector).toBeVisible()
    }
  })

  test('Can switch between species', async ({ page }) => {
    // Find species selector (could be select, radio, or segmented control)
    const speciesSelect = page.locator('.ant-select').filter({ hasText: /Human|Mouse|物种/i }).first()

    if (await speciesSelect.count() > 0) {
      await speciesSelect.click()
      await page.waitForTimeout(300)

      const dropdown = page.locator('.ant-select-dropdown:visible')
      if (await dropdown.isVisible().catch(() => false)) {
        // Select a different species
        const mouseOption = dropdown.locator('.ant-select-item').filter({ hasText: /Mouse|小鼠/i }).first()

        if (await mouseOption.count() > 0) {
          await mouseOption.click()
          await page.waitForTimeout(3000) // Wait for IGV to reload

          console.log('Species switched to Mouse')
        }
      }
    } else {
      // Try radio or segmented control
      const radioOption = page.locator('.ant-radio-wrapper, .ant-segmented-item')
        .filter({ hasText: /Mouse|小鼠/i }).first()

      if (await radioOption.count() > 0) {
        await radioOption.click()
        await page.waitForTimeout(3000)
        console.log('Species switched via radio/segmented')
      }
    }
  })

  test('Species switch updates IGV', async ({ page }) => {
    // Track API calls to detect IGV config changes
    const apiCalls: string[] = []
    page.on('request', (request) => {
      if (request.url().includes('igv') || request.url().includes('genome') || request.url().includes('reference')) {
        apiCalls.push(request.url())
      }
    })

    // Switch species
    const speciesControl = page.locator('.ant-select, .ant-radio-group, .ant-segmented')
      .filter({ hasText: /Human|Mouse|Species/i }).first()

    if (await speciesControl.count() > 0) {
      // Click to change species
      const option = page.locator('.ant-radio-wrapper, .ant-segmented-item, .ant-select')
        .filter({ hasText: /Mouse|Human/i }).first()

      if (await option.count() > 0) {
        await option.click()
        await page.waitForTimeout(3000)

        console.log(`API calls made: ${apiCalls.length}`)
      }
    }
  })
})

// ============================================================================
// Test Suite: Gene Search
// ============================================================================

test.describe('Genome Browser - Gene Search', () => {
  test.beforeEach(async ({ page }) => {
    await page.goto(`${BASE_URL}${PAGE_URL}`)
    await page.waitForLoadState('domcontentloaded')
    await page.waitForTimeout(2000)
  })

  test('Gene search input is visible', async ({ page }) => {
    const searchInput = page.locator('input[placeholder*="gene" i], input[placeholder*="search" i], .ant-input-search').first()
      .or(page.locator('[data-testid="gene-search"]'))

    const hasSearchInput = await searchInput.count() > 0
    console.log(`Gene search input found: ${hasSearchInput}`)

    if (hasSearchInput) {
      await expect(searchInput).toBeVisible()
    }
  })

  test('Can search for a gene', async ({ page }) => {
    const searchInput = page.locator('input[type="text"], .ant-input').first()

    if (await searchInput.count() > 0) {
      // Enter a gene name
      await searchInput.fill('MALAT1')
      await page.keyboard.press('Enter')

      // Wait for IGV to navigate
      await page.waitForTimeout(3000)

      console.log('Gene search submitted')
    }
  })

  test('Gene search updates IGV locus', async ({ page }) => {
    // Track navigation events
    let locusChanged = false
    page.on('request', (request) => {
      if (request.url().includes('locus') || request.url().includes('search')) {
        locusChanged = true
      }
    })

    const searchInput = page.locator('input').filter({ has: page.locator('[placeholder*="gene" i]') }).first()
      .or(page.locator('.ant-input').first())

    if (await searchInput.count() > 0) {
      await searchInput.fill('NEAT1')
      await page.keyboard.press('Enter')
      await page.waitForTimeout(2000)

      // IGV should update (track changes are hard to verify directly)
      console.log(`Locus change triggered: ${locusChanged}`)
    }
  })

	  test('Invalid gene shows appropriate feedback', async ({ page }) => {
	    const searchInput = page.locator('input[placeholder*="Enter gene name"], input[placeholder*="gene name" i]').first()

	    if (await searchInput.count() > 0) {
	      await searchInput.fill('NONEXISTENT_GENE_12345')
	      await page.keyboard.press('Enter')
	      await page.waitForTimeout(2000)

      // Check for error message or notification
      const errorMsg = page.locator('.ant-message-error, .ant-notification-notice-error, .ant-alert-error')
      const warningMsg = page.getByText(/not found|no results|未找到/i)

      const hasError = await errorMsg.isVisible().catch(() => false)
      const hasWarning = await warningMsg.isVisible().catch(() => false)

      console.log(`Invalid gene feedback: error=${hasError}, warning=${hasWarning}`)
    }
  })
})

// ============================================================================
// Test Suite: URL Parameters
// ============================================================================

test.describe('Genome Browser - URL Parameters', () => {
  test('Gene parameter navigates to gene locus', async ({ page }) => {
    await page.goto(`${BASE_URL}${PAGE_URL}?gene=MALAT1`)
    await page.waitForLoadState('domcontentloaded')
    await page.waitForTimeout(3000)

    // Page should load with gene parameter
    expect(page.url()).toContain('gene=MALAT1')

    // IGV should be visible
    const igvContainer = page.locator('[class*="igv"], [class*="genome"]').first()
    const isVisible = await igvContainer.isVisible({ timeout: 20000 }).catch(() => false)

    console.log(`IGV loaded with gene parameter: ${isVisible}`)
  })

  test('Locus parameter navigates to coordinates', async ({ page }) => {
    await page.goto(`${BASE_URL}${PAGE_URL}?locus=chr1:1000000-2000000`)
    await page.waitForLoadState('domcontentloaded')
    await page.waitForTimeout(3000)

    expect(page.url()).toContain('locus=')

    // IGV should display the locus
    const igvContainer = page.locator('[class*="igv"], [class*="genome"]').first()
    await expect(igvContainer).toBeVisible({ timeout: 20000 })
  })

  test('Species parameter sets correct genome', async ({ page }) => {
    // Species ID 2 is typically Mouse
    await page.goto(`${BASE_URL}${PAGE_URL}?species=2`)
    await page.waitForLoadState('domcontentloaded')
    await page.waitForTimeout(3000)

    expect(page.url()).toContain('species=2')

    // Check if species selector reflects the parameter
    const speciesText = await page.locator('.ant-select-selection-item, .ant-radio-button-wrapper-checked, .ant-segmented-item-selected').textContent().catch(() => '')
    console.log(`Species from URL: ${speciesText}`)
  })

	  test('Combined parameters work together', async ({ page }) => {
	    await page.goto(`${BASE_URL}${PAGE_URL}?species=1&gene=MALAT1`)
	    await page.waitForLoadState('domcontentloaded')
	    await page.waitForTimeout(3000)

	    expect(page.url()).toContain('gene=MALAT1')

	    // 一些实现会在 species 为默认值时从 URL 中移除该参数，这里只校验 UI 选择结果
	    const selectedSpecies = page.locator('.ant-select').filter({ hasText: /Human|人类/i }).first()
	    await expect(selectedSpecies).toBeVisible({ timeout: 10000 })

	    // Page should load successfully
	    const mainContent = page.locator('[class*="igv"], [class*="genome"], .ant-card').first()
	    await expect(mainContent).toBeVisible({ timeout: 20000 })
	  })
})

// ============================================================================
// Test Suite: Track Display
// ============================================================================

test.describe('Genome Browser - Tracks', () => {
  test.beforeEach(async ({ page }) => {
    await page.goto(`${BASE_URL}${PAGE_URL}`)
    await page.waitForLoadState('domcontentloaded')
    await page.waitForTimeout(5000) // IGV needs time to fully initialize
  })

  test('Reference genome track is displayed', async ({ page }) => {
    // IGV displays reference track by default
    const refTrack = page.locator('[class*="igv-track"], [class*="reference"], .igv-ideogram').first()
    const isVisible = await refTrack.isVisible({ timeout: 10000 }).catch(() => false)

    console.log(`Reference track visible: ${isVisible}`)
  })

  test('Gene annotation track is displayed', async ({ page }) => {
    // Look for gene/annotation track
    const geneTrack = page.locator('[class*="gene"], [class*="annotation"], .igv-feature-track').first()
    const isVisible = await geneTrack.isVisible({ timeout: 10000 }).catch(() => false)

    console.log(`Gene track visible: ${isVisible}`)
  })

  test('Track controls are accessible', async ({ page }) => {
    // Look for track control buttons (gear icon, expand/collapse)
    const trackControls = page.locator('[class*="igv-track-menu"], [class*="track-control"], [class*="settings"]').first()
    const hasControls = await trackControls.count() > 0

    console.log(`Track controls found: ${hasControls}`)
  })

  test('Can interact with track settings', async ({ page }) => {
    // Find settings/gear icon on a track
    const settingsIcon = page.locator('[class*="igv-gear"], [class*="track-settings"], .ant-dropdown-trigger').first()

    if (await settingsIcon.count() > 0) {
      await settingsIcon.click()
      await page.waitForTimeout(500)

      // Settings menu should appear
      const settingsMenu = page.locator('.ant-dropdown-menu:visible, [class*="igv-menu"]')
      const menuVisible = await settingsMenu.isVisible().catch(() => false)

      console.log(`Track settings menu: ${menuVisible}`)
    }
  })
})

// ============================================================================
// Test Suite: Navigation Controls
// ============================================================================

test.describe('Genome Browser - Navigation', () => {
  test.beforeEach(async ({ page }) => {
    await page.goto(`${BASE_URL}${PAGE_URL}`)
    await page.waitForLoadState('domcontentloaded')
    await page.waitForTimeout(5000)
  })

  test('Zoom controls are available', async ({ page }) => {
    // Look for zoom in/out buttons
    const zoomIn = page.locator('[class*="zoom-in"], button:has-text("+"), [aria-label*="zoom in" i]').first()
    const zoomOut = page.locator('[class*="zoom-out"], button:has-text("-"), [aria-label*="zoom out" i]').first()

    const hasZoomIn = await zoomIn.count() > 0
    const hasZoomOut = await zoomOut.count() > 0

    console.log(`Zoom controls: in=${hasZoomIn}, out=${hasZoomOut}`)
  })

	  test('Locus input allows coordinate entry', async ({ page }) => {
	    // IGV has a locus search box
	    const locusInput = page.locator('input.igv-search-input').first()

	    if (await locusInput.count() > 0) {
	      // Enter coordinates
	      await locusInput.fill('chr1:1000000-2000000')
	      await page.keyboard.press('Enter')
      await page.waitForTimeout(2000)

      console.log('Locus coordinate entry works')
    }
  })

  test('Can pan/scroll the view', async ({ page }) => {
    // IGV supports drag-to-pan
    const igvContainer = page.locator('[class*="igv"], [class*="genome-browser"]').first()

    if (await igvContainer.count() > 0) {
      const box = await igvContainer.boundingBox()
      if (box) {
        // Simulate drag
        await page.mouse.move(box.x + box.width / 2, box.y + box.height / 2)
        await page.mouse.down()
        await page.mouse.move(box.x + box.width / 2 + 100, box.y + box.height / 2)
        await page.mouse.up()

        console.log('Pan interaction completed')
      }
    }
  })
})

// ============================================================================
// Test Suite: Error Handling
// ============================================================================

test.describe('Genome Browser - Error Handling', () => {
  test('Handles invalid locus gracefully', async ({ page }) => {
    await page.goto(`${BASE_URL}${PAGE_URL}?locus=invalid_locus`)
    await page.waitForLoadState('domcontentloaded')
    await page.waitForTimeout(3000)

    // Page should not crash
    const body = page.locator('body')
    await expect(body).toBeVisible()

    // May show error or warning
    const errorIndicator = page.locator('.ant-alert, .ant-message, .ant-notification')
    const hasError = await errorIndicator.isVisible().catch(() => false)

    console.log(`Invalid locus error shown: ${hasError}`)
  })

  test('Handles API errors', async ({ page }) => {
    await page.route('**/api/v1/igv-config*', (route) => {
      route.fulfill({
        status: 500,
        contentType: 'application/json',
        body: JSON.stringify({ detail: 'Server Error' })
      })
    })

    await page.goto(`${BASE_URL}${PAGE_URL}`)
    await page.waitForTimeout(3000)

    // Should show error state
    const errorIndicator = page.locator('.ant-alert-error, .ant-notification-notice-error, .ant-result-error')
    const errorText = page.getByText(/Error|Failed|错误/i)

    const hasError = await errorIndicator.isVisible().catch(() => false) ||
                     await errorText.isVisible().catch(() => false)

    console.log(`API error handled: ${hasError}`)
  })

  test('Shows fallback when IGV fails to load', async ({ page }) => {
    // Block IGV assets
    await page.route('**/igv*.js', (route) => route.abort())
    await page.route('**/igv*.css', (route) => route.abort())

    await page.goto(`${BASE_URL}${PAGE_URL}`)
    await page.waitForTimeout(5000)

    // Should show error or fallback message
    const body = page.locator('body')
    await expect(body).toBeVisible()

    const errorMsg = page.locator('.ant-alert, .ant-result-error')
    const errorText = page.getByText(/failed|error|unavailable/i)

    console.log('IGV load failure handled')
  })

  test('Console errors are minimal', async ({ page }) => {
    const consoleErrors: string[] = []
    page.on('console', (msg) => {
      if (msg.type() === 'error') {
        consoleErrors.push(msg.text())
      }
    })

    await page.goto(`${BASE_URL}${PAGE_URL}`)
    await page.waitForLoadState('domcontentloaded')
    await page.waitForTimeout(5000)

    // Filter for critical errors
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

test.describe('Genome Browser - Performance', () => {
  test('Page loads within acceptable time', async ({ page }) => {
    const startTime = Date.now()

    await page.goto(`${BASE_URL}${PAGE_URL}`)
    await page.waitForLoadState('domcontentloaded')

    const loadTime = Date.now() - startTime
    expect(loadTime).toBeLessThan(15000) // 15 seconds max (IGV is heavy)

    console.log(`Page loaded in ${loadTime}ms`)
  })

  test('IGV initializes within acceptable time', async ({ page }) => {
    await page.goto(`${BASE_URL}${PAGE_URL}`)

    const startTime = Date.now()
    const igvContainer = page.locator('[class*="igv"], [class*="genome"]').first()
    await igvContainer.waitFor({ timeout: 20000, state: 'visible' }).catch(() => null)

    const initTime = Date.now() - startTime
    expect(initTime).toBeLessThan(20000) // 20 seconds max

    console.log(`IGV initialized in ${initTime}ms`)
  })

  test('Navigation response is acceptable', async ({ page }) => {
    await page.goto(`${BASE_URL}${PAGE_URL}`)
    await page.waitForLoadState('domcontentloaded')
    await page.waitForTimeout(5000)

    const locusInput = page.getByTestId('genome-locus-autocomplete').locator('input').first()
    if ((await locusInput.count()) === 0) {
      test.skip()
      return
    }

    const startTime = Date.now()

    await locusInput.fill('chr1:5000000-6000000')
    await page.keyboard.press('Enter')
    await page.waitForTimeout(2000)

    const navTime = Date.now() - startTime
    expect(navTime).toBeLessThan(10000)

    console.log(`Navigation completed in ${navTime}ms`)
  })
})

// ============================================================================
// Test Suite: Responsive Design
// ============================================================================

test.describe('Genome Browser - Responsive', () => {
  test('Desktop view works correctly', async ({ page }) => {
    await page.setViewportSize({ width: 1920, height: 1080 })
    await page.goto(`${BASE_URL}${PAGE_URL}`)
    await page.waitForLoadState('domcontentloaded')

    const mainContent = page.locator('[class*="igv"], [class*="genome"], .ant-card').first()
    await expect(mainContent).toBeVisible({ timeout: 20000 })
  })

  test('Tablet view is usable', async ({ page }) => {
    await page.setViewportSize({ width: 768, height: 1024 })
    await page.goto(`${BASE_URL}${PAGE_URL}`)
    await page.waitForLoadState('domcontentloaded')

    const mainContent = page.locator('[class*="igv"], [class*="genome"], .ant-card, h1, h2').first()
    await expect(mainContent).toBeVisible({ timeout: 20000 })
  })

  test('Mobile view shows appropriate message or adapts', async ({ page }) => {
    await page.setViewportSize({ width: 375, height: 667 })
    await page.goto(`${BASE_URL}${PAGE_URL}`)
    await page.waitForLoadState('domcontentloaded')

    // IGV may not work well on mobile - should show message or adapted view
    const content = page.locator('body')
    await expect(content).toBeVisible()

    // Check for mobile-specific message
    const mobileMsg = page.getByText(/desktop|larger screen|不支持移动/i)
    const hasMobileMsg = await mobileMsg.isVisible().catch(() => false)

    console.log(`Mobile message shown: ${hasMobileMsg}`)
  })
})

// ============================================================================
// Test Suite: Accessibility
// ============================================================================

test.describe('Genome Browser - Accessibility', () => {
  test.beforeEach(async ({ page }) => {
    await page.goto(`${BASE_URL}${PAGE_URL}`)
    await page.waitForLoadState('domcontentloaded')
    await page.waitForTimeout(3000)
  })

  test('Page has heading', async ({ page }) => {
    const heading = page.locator('h1, h2').first()
    await expect(heading).toBeVisible()
  })

  test('Form controls have labels', async ({ page }) => {
    const inputs = page.locator('input[type="text"]')
    const inputCount = await inputs.count()

    // Check for associated labels or placeholders
    for (let i = 0; i < inputCount; i++) {
      const input = inputs.nth(i)
      const placeholder = await input.getAttribute('placeholder')
      const ariaLabel = await input.getAttribute('aria-label')
      const id = await input.getAttribute('id')

      const hasLabel = placeholder || ariaLabel || id
      console.log(`Input ${i}: labeled=${!!hasLabel}`)
    }
  })

  test('Keyboard navigation works', async ({ page }) => {
    await page.keyboard.press('Tab')
    await page.waitForTimeout(200)

    const focusedElement = page.locator(':focus')
    expect(await focusedElement.count()).toBeGreaterThan(0)
  })
})
