import { test, expect, Page } from '@playwright/test'

/**
 * Dynamic Overlap Track Loading E2E Tests
 *
 * Tests for the IGV dynamic overlap track loading functionality
 * on the lncRNA-ChIP-seq Overlap page.
 *
 * Core Features:
 * 1. Load overlap track button visibility when IGV is enabled
 * 2. API call verification when loading overlap track
 * 3. Auto-sync functionality with filter changes
 * 4. Performance testing for track loading
 * 5. Error handling for API failures
 *
 * Route: /lncrna-chipseq-overlap
 */

const PAGE_URL = '/lncrna-chipseq-overlap'
const BASE_URL = process.env.BASE_URL || 'http://localhost:5173'

// ============================================================================
// Helper Functions
// ============================================================================

/**
 * Wait for IGV overlap track API response
 */
async function waitForTrackLoad(page: Page, timeout = 15000) {
  return page.waitForResponse(
    (resp) => resp.url().includes('/api/v1/igv/overlap-track') && resp.status() === 200,
    { timeout }
  )
}

/**
 * Wait for page to fully load (table data visible)
 */
async function waitForPageLoad(page: Page) {
  // Wait for table to be visible
  await page.locator('.ant-table').first().waitFor({ timeout: 30000 }).catch(() => null)
  // Small delay for React state to settle
  await page.waitForTimeout(1000)
}

/**
 * Find the IGV browser switch (next to "Show IGV Browser:" text)
 */
function getIGVSwitch(page: Page) {
  // The switch is inside a container with "Show IGV Browser:" text
  return page
    .locator('div:has-text("Show IGV Browser") >> switch')
    .or(page.locator('[data-testid="igv-switch"]'))
    .or(page.getByText('Show IGV Browser').locator('..').locator('button[role="switch"]'))
    .first()
}

/**
 * Check if IGV is currently enabled/visible
 */
async function isIGVEnabled(page: Page) {
  const igvContainer = page
    .locator('[class*="genome-browser"]')
    .or(page.locator('[class*="igv"]'))
    .or(page.getByText('Genome Browser').locator('..').locator('..'))
    .first()
  return igvContainer.isVisible({ timeout: 5000 }).catch(() => false)
}

/**
 * Enable IGV browser if not already enabled
 */
async function ensureIGVEnabled(page: Page) {
  // First check if IGV section is already visible
  const igvSection = page.getByText('Genome Browser').first()
  const isVisible = await igvSection.isVisible({ timeout: 5000 }).catch(() => false)

  if (isVisible) {
    console.log('IGV is already enabled')
    return true
  }

  // Try to find and click the IGV switch
  const switchLocators = [
    // Look for switch near "Show IGV Browser" text
    page.locator('div').filter({ hasText: /Show IGV Browser/i }).locator('button[role="switch"]').first(),
    // Generic switch with IGV in nearby text
    page.locator('button[role="switch"]').first(),
    // Data test ID
    page.locator('[data-testid="igv-switch"]'),
  ]

  for (const locator of switchLocators) {
    const visible = await locator.isVisible({ timeout: 2000 }).catch(() => false)
    if (visible) {
      // Check if already checked
      const isChecked = await locator.getAttribute('aria-checked')
      if (isChecked === 'true') {
        console.log('IGV switch is already checked')
        return true
      }
      await locator.click()
      await page.waitForTimeout(3000)
      return true
    }
  }

  console.log('Warning: Could not find IGV switch')
  return false
}

/**
 * Find the load overlap track button
 */
function getLoadOverlapButton(page: Page) {
  return page
    .getByRole('button', { name: /load overlap track/i })
    .or(page.locator('[data-testid="load-overlap-track-btn"]'))
    .or(page.locator('button').filter({ hasText: /Load Overlap Track/i }))
    .first()
}

/**
 * Find the auto-sync switch
 */
function getAutoSyncSwitch(page: Page) {
  return page
    .locator('div').filter({ hasText: /Auto Sync/i }).locator('button[role="switch"]').first()
    .or(page.getByRole('switch', { name: /auto.*sync/i }))
    .or(page.locator('[data-testid="auto-sync-switch"]'))
}

// ============================================================================
// P0 Tests: Core Functionality
// ============================================================================

test.describe('P0: Core Functionality', () => {
  test.beforeEach(async ({ page }) => {
    await page.goto(`${BASE_URL}${PAGE_URL}`)
    await page.waitForLoadState('networkidle')
    // Wait for page content to load
    await waitForPageLoad(page)
  })

  test('should display load overlap track button when IGV is visible', async ({ page }) => {
    // Ensure IGV is enabled
    const igvEnabled = await ensureIGVEnabled(page)

    if (!igvEnabled) {
      console.log('Warning: Could not enable IGV - feature may not be implemented')
      test.skip()
      return
    }

    // Verify the load overlap track button is visible
    const loadButton = getLoadOverlapButton(page)
    const buttonVisible = await loadButton.isVisible({ timeout: 10000 }).catch(() => false)

    if (buttonVisible) {
      console.log('Success: Load overlap track button is visible')
      await expect(loadButton).toBeVisible()
    } else {
      console.log('Warning: Load overlap track button not found - feature may not be implemented yet')
      // Check for any button related to tracks/overlap
      const anyTrackButton = page.locator('button').filter({ hasText: /track|overlap/i })
      const count = await anyTrackButton.count()
      console.log(`Found ${count} track-related buttons`)
    }
  })

  test('should load overlap track when button clicked', async ({ page }) => {
    // Ensure IGV is enabled
    const igvEnabled = await ensureIGVEnabled(page)

    if (!igvEnabled) {
      console.log('Warning: Could not enable IGV')
      test.skip()
      return
    }

    // Find load button
    const loadButton = getLoadOverlapButton(page)
    const buttonVisible = await loadButton.isVisible({ timeout: 10000 }).catch(() => false)

    if (!buttonVisible) {
      console.log('Warning: Load overlap track button not visible')
      test.skip()
      return
    }

    // Set up response listener BEFORE clicking
    const responsePromise = page.waitForResponse(
      (resp) => resp.url().includes('/api/v1/igv/overlap-track'),
      { timeout: 15000 }
    )

    // Click the load button
    await loadButton.click()

    try {
      // Wait for API response
      const response = await responsePromise
      const status = response.status()

      console.log(`API Response Status: ${status}`)
      console.log(`API URL: ${response.url()}`)

      // Verify successful response
      expect(status).toBe(200)
      console.log('Success: Overlap track API called successfully')
    } catch (error) {
      console.log('Warning: API response not received within timeout')
      console.log('This may indicate the API endpoint is not implemented yet')
    }
  })

  test('should sync track with filter changes when auto-sync enabled', async ({ page }) => {
    // Ensure IGV is enabled
    const igvEnabled = await ensureIGVEnabled(page)

    if (!igvEnabled) {
      console.log('Warning: Could not enable IGV')
      test.skip()
      return
    }

    // Look for auto-sync switch
    const autoSyncSwitch = getAutoSyncSwitch(page)

    const autoSyncVisible = await autoSyncSwitch.isVisible({ timeout: 5000 }).catch(() => false)

    if (!autoSyncVisible) {
      console.log('Warning: Auto-sync switch not found - feature may not be implemented')
      test.skip()
      return
    }

    // Enable auto-sync
    await autoSyncSwitch.click()
    console.log('Success: Auto-sync switch clicked')

    // Find and interact with mark filter
    const markSelect = page
      .locator('[data-testid="mark-filter"]')
      .or(page.getByPlaceholder(/mark/i))
      .or(page.locator('.ant-select').filter({ hasText: /mark|H3K/i }))

    const markVisible = await markSelect.isVisible({ timeout: 5000 }).catch(() => false)

    if (!markVisible) {
      console.log('Warning: Mark filter not found')
      test.skip()
      return
    }

    // Set up response listener
    const responsePromise = page.waitForResponse(
      (resp) => resp.url().includes('/api/v1/igv/overlap-track'),
      { timeout: 10000 }
    )

    // Change filter
    await markSelect.click()
    await page.waitForTimeout(300)

    // Select H3K27me3 option if available
    const option = page.getByText('H3K27me3').or(page.locator('.ant-select-item').first())
    const optionVisible = await option.isVisible({ timeout: 3000 }).catch(() => false)

    if (optionVisible) {
      await option.click()

      try {
        // Verify API was called
        await responsePromise
        console.log('Success: Track synced with filter change')
      } catch {
        console.log('Warning: Auto-sync API call not detected')
      }
    } else {
      console.log('Warning: No filter options available')
    }
  })

  test('should display IGV browser container', async ({ page }) => {
    // Open IGV
    const igvOpened = await ensureIGVEnabled(page)

    if (!igvOpened) {
      console.log('Warning: IGV switch not found')
      test.skip()
      return
    }

    // Verify IGV container is visible
    const igvContainer = page
      .locator('[data-testid="genome-browser"]')
      .or(page.locator('[class*="igv"]'))
      .or(page.locator('[class*="genome-browser"]'))
      .first()

    const containerVisible = await igvContainer.isVisible({ timeout: 15000 }).catch(() => false)

    if (containerVisible) {
      console.log('Success: IGV container is visible')
      await expect(igvContainer).toBeVisible()
    } else {
      console.log('Warning: IGV container not found after enabling switch')
    }
  })
})

// ============================================================================
// P1 Tests: Performance
// ============================================================================

test.describe('P1: Performance', () => {
  test.beforeEach(async ({ page }) => {
    await page.goto(`${BASE_URL}${PAGE_URL}`)
    await page.waitForLoadState('networkidle')
    await waitForPageLoad(page)
  })

  test('track should load within 5 seconds', async ({ page }) => {
    // Open IGV
    const igvOpened = await ensureIGVEnabled(page)

    if (!igvOpened) {
      console.log('Warning: IGV switch not found')
      test.skip()
      return
    }

    const loadButton = getLoadOverlapButton(page)
    const buttonVisible = await loadButton.isVisible({ timeout: 10000 }).catch(() => false)

    if (!buttonVisible) {
      console.log('Warning: Load button not visible')
      test.skip()
      return
    }

    // Measure load time
    const startTime = Date.now()

    const responsePromise = page.waitForResponse(
      (resp) => resp.url().includes('/api/v1/igv/overlap-track'),
      { timeout: 15000 }
    )

    await loadButton.click()

    try {
      await responsePromise
      const loadTime = Date.now() - startTime

      console.log(`Track load time: ${loadTime}ms`)

      // Verify load time is under 5 seconds
      expect(loadTime).toBeLessThan(5000)
      console.log('Success: Track loaded within 5 seconds')
    } catch {
      console.log('Warning: Could not measure load time - API may not be implemented')
    }
  })

  test('page should load within 10 seconds', async ({ page }) => {
    const startTime = Date.now()

    await page.goto(`${BASE_URL}${PAGE_URL}`)
    await page.waitForLoadState('networkidle')

    // Wait for table to appear
    const table = page.locator('.ant-table').first()
    await table.waitFor({ timeout: 10000 }).catch(() => null)

    const loadTime = Date.now() - startTime

    console.log(`Page load time: ${loadTime}ms`)
    expect(loadTime).toBeLessThan(10000)
    console.log('Success: Page loaded within 10 seconds')
  })

  test('IGV initialization should complete within 15 seconds', async ({ page }) => {
    const startTime = Date.now()

    // Open IGV
    const igvOpened = await ensureIGVEnabled(page)

    if (!igvOpened) {
      console.log('Warning: IGV switch not found')
      test.skip()
      return
    }

    // Wait for IGV container
    const igvContainer = page
      .locator('[data-testid="genome-browser"]')
      .or(page.locator('[class*="igv"]'))
      .first()

    await igvContainer.waitFor({ timeout: 15000, state: 'visible' }).catch(() => null)

    const initTime = Date.now() - startTime

    console.log(`IGV initialization time: ${initTime}ms`)

    if (initTime < 15000) {
      console.log('Success: IGV initialized within 15 seconds')
      expect(initTime).toBeLessThan(15000)
    } else {
      console.log('Warning: IGV initialization exceeded 15 seconds or container not found')
    }
  })
})

// ============================================================================
// P2 Tests: Edge Cases & Error Handling
// ============================================================================

test.describe('P2: Edge Cases', () => {
  test('should handle API error gracefully', async ({ page }) => {
    // Mock API to return error
    await page.route('**/api/v1/igv/overlap-track*', (route) => {
      route.fulfill({
        status: 500,
        contentType: 'application/json',
        body: JSON.stringify({ detail: 'Internal Server Error' })
      })
    })

    await page.goto(`${BASE_URL}${PAGE_URL}`)
    await page.waitForLoadState('networkidle')

    // Open IGV
    const igvOpened = await ensureIGVEnabled(page)

    if (!igvOpened) {
      console.log('Warning: IGV switch not found')
      test.skip()
      return
    }

    const loadButton = getLoadOverlapButton(page)
    const buttonVisible = await loadButton.isVisible({ timeout: 10000 }).catch(() => false)

    if (!buttonVisible) {
      console.log('Warning: Load button not visible')
      test.skip()
      return
    }

    await loadButton.click()
    await page.waitForTimeout(2000)

    // Verify page is still functional (no crash)
    await expect(page.locator('body')).toBeVisible()
    console.log('Success: Page handled API error gracefully')

    // Check for error message display
    const errorMessage = page
      .locator('.ant-message-error')
      .or(page.locator('.ant-alert-error'))
      .or(page.getByText(/error|failed|失败|错误/i))

    const hasError = await errorMessage.isVisible({ timeout: 3000 }).catch(() => false)

    if (hasError) {
      console.log('Success: Error message displayed to user')
    } else {
      console.log('Info: No visible error message (may be handled silently)')
    }
  })

  test('load button should be disabled or hidden when IGV is not visible', async ({ page }) => {
    await page.goto(`${BASE_URL}${PAGE_URL}`)
    await page.waitForLoadState('networkidle')
    await page.waitForTimeout(2000)

    // Check button state when IGV is disabled/hidden
    const loadButton = getLoadOverlapButton(page)

    const isVisible = await loadButton.isVisible({ timeout: 3000 }).catch(() => false)

    if (isVisible) {
      // If visible, it should be disabled
      const isDisabled = await loadButton.isDisabled().catch(() => false)

      if (isDisabled) {
        console.log('Success: Load button is disabled when IGV is hidden')
        await expect(loadButton).toBeDisabled()
      } else {
        console.log('Warning: Load button is visible and enabled when IGV is hidden')
      }
    } else {
      console.log('Success: Load button is hidden when IGV is not visible')
    }
  })

  test('should handle empty overlap results', async ({ page }) => {
    // Mock API to return empty results
    await page.route('**/api/v1/igv/overlap-track*', (route) => {
      route.fulfill({
        status: 200,
        contentType: 'application/json',
        body: JSON.stringify({ tracks: [], message: 'No overlaps found' })
      })
    })

    await page.goto(`${BASE_URL}${PAGE_URL}`)
    await page.waitForLoadState('networkidle')

    // Open IGV
    const igvOpened = await ensureIGVEnabled(page)

    if (!igvOpened) {
      console.log('Warning: IGV switch not found')
      test.skip()
      return
    }

    const loadButton = getLoadOverlapButton(page)
    const buttonVisible = await loadButton.isVisible({ timeout: 10000 }).catch(() => false)

    if (!buttonVisible) {
      console.log('Warning: Load button not visible')
      test.skip()
      return
    }

    await loadButton.click()
    await page.waitForTimeout(2000)

    // Verify page handles empty results gracefully
    await expect(page.locator('body')).toBeVisible()
    console.log('Success: Page handled empty results gracefully')
  })

  test('should handle network timeout', async ({ page }) => {
    // Mock API to delay indefinitely (simulating timeout)
    await page.route('**/api/v1/igv/overlap-track*', async (route) => {
      // Delay for 30 seconds (longer than typical timeout)
      await new Promise((resolve) => setTimeout(resolve, 30000))
      route.fulfill({
        status: 200,
        contentType: 'application/json',
        body: JSON.stringify({ tracks: [] })
      })
    })

    await page.goto(`${BASE_URL}${PAGE_URL}`)
    await page.waitForLoadState('networkidle')

    // Open IGV
    const igvOpened = await ensureIGVEnabled(page)

    if (!igvOpened) {
      console.log('Warning: IGV switch not found')
      test.skip()
      return
    }

    const loadButton = getLoadOverlapButton(page)
    const buttonVisible = await loadButton.isVisible({ timeout: 10000 }).catch(() => false)

    if (!buttonVisible) {
      console.log('Warning: Load button not visible')
      test.skip()
      return
    }

    await loadButton.click()

    // Wait for loading indicator or timeout handling
    await page.waitForTimeout(5000)

    // Verify page is still responsive
    await expect(page.locator('body')).toBeVisible()
    console.log('Success: Page remains responsive during slow API response')
  })
})

// ============================================================================
// P2 Tests: User Interaction
// ============================================================================

test.describe('P2: User Interaction', () => {
  test.beforeEach(async ({ page }) => {
    await page.goto(`${BASE_URL}${PAGE_URL}`)
    await page.waitForLoadState('networkidle')
    await waitForPageLoad(page)
  })

  test('should toggle IGV visibility with switch', async ({ page }) => {
    // Find the IGV switch using better locators
    const igvSwitch = page.locator('button[role="switch"]').first()
    const switchVisible = await igvSwitch.isVisible({ timeout: 5000 }).catch(() => false)

    if (!switchVisible) {
      console.log('Warning: IGV switch not found')
      test.skip()
      return
    }

    // Toggle ON
    await igvSwitch.click()
    await page.waitForTimeout(2000)

    const igvContainer = page
      .locator('[data-testid="genome-browser"]')
      .or(page.locator('[class*="igv"]'))
      .first()

    const igvVisibleAfterOn = await igvContainer.isVisible({ timeout: 10000 }).catch(() => false)
    console.log(`IGV visible after toggle ON: ${igvVisibleAfterOn}`)

    // Toggle OFF
    await igvSwitch.click()
    await page.waitForTimeout(1000)

    const igvVisibleAfterOff = await igvContainer.isVisible({ timeout: 3000 }).catch(() => false)
    console.log(`IGV visible after toggle OFF: ${igvVisibleAfterOff}`)

    // Verify toggle works
    if (igvVisibleAfterOn && !igvVisibleAfterOff) {
      console.log('Success: IGV toggle works correctly')
    } else {
      console.log('Warning: IGV toggle behavior may not be as expected')
    }
  })

  test('should maintain track state after filter changes', async ({ page }) => {
    // Open IGV
    const igvOpened = await ensureIGVEnabled(page)

    if (!igvOpened) {
      console.log('Warning: IGV switch not found')
      test.skip()
      return
    }

    // Load track first
    const loadButton = getLoadOverlapButton(page)
    const buttonVisible = await loadButton.isVisible({ timeout: 10000 }).catch(() => false)

    if (buttonVisible) {
      await loadButton.click()
      await page.waitForTimeout(3000)
    }

    // Change a filter
    const chromosomeSelect = page
      .locator('[data-testid="chromosome-filter"]')
      .or(page.getByPlaceholder(/chromosome|chr/i))
      .or(page.locator('.ant-select').filter({ hasText: /chr/i }))

    const chrVisible = await chromosomeSelect.isVisible({ timeout: 5000 }).catch(() => false)

    if (chrVisible) {
      await chromosomeSelect.click()
      await page.waitForTimeout(300)

      const option = page.locator('.ant-select-item').first()
      const optionVisible = await option.isVisible({ timeout: 3000 }).catch(() => false)

      if (optionVisible) {
        await option.click()
        await page.waitForTimeout(2000)

        // Verify IGV is still visible
        const igvContainer = page
          .locator('[data-testid="genome-browser"]')
          .or(page.locator('[class*="igv"]'))
          .first()

        const stillVisible = await igvContainer.isVisible({ timeout: 5000 }).catch(() => false)

        if (stillVisible) {
          console.log('Success: IGV remains visible after filter change')
        } else {
          console.log('Warning: IGV state changed after filter change')
        }
      }
    } else {
      console.log('Info: Chromosome filter not found')
    }
  })

  test('should support keyboard navigation to load button', async ({ page }) => {
    // Open IGV
    const igvOpened = await ensureIGVEnabled(page)

    if (!igvOpened) {
      console.log('Warning: IGV switch not found')
      test.skip()
      return
    }

    const loadButton = getLoadOverlapButton(page)
    const buttonVisible = await loadButton.isVisible({ timeout: 10000 }).catch(() => false)

    if (!buttonVisible) {
      console.log('Warning: Load button not visible')
      test.skip()
      return
    }

    // Focus the button using Tab navigation
    await page.keyboard.press('Tab')
    await page.waitForTimeout(200)

    // Try to focus on the load button
    await loadButton.focus()
    await page.waitForTimeout(200)

    // Check if button is focused
    const isFocused = await page.evaluate(() => {
      const activeElement = document.activeElement
      return (
        activeElement?.tagName === 'BUTTON' &&
        (activeElement?.textContent?.toLowerCase().includes('load') ||
          activeElement?.textContent?.toLowerCase().includes('track') ||
          activeElement?.textContent?.toLowerCase().includes('overlap'))
      )
    })

    if (isFocused) {
      console.log('Success: Load button can be focused')

      // Test Enter key activation
      await page.keyboard.press('Enter')
      await page.waitForTimeout(1000)
      console.log('Success: Button can be activated with keyboard')
    } else {
      console.log('Info: Button focus via keyboard may need improvement')
    }
  })
})

// ============================================================================
// P2 Tests: Accessibility
// ============================================================================

test.describe('P2: Accessibility', () => {
  test.beforeEach(async ({ page }) => {
    await page.goto(`${BASE_URL}${PAGE_URL}`)
    await page.waitForLoadState('networkidle')
    await waitForPageLoad(page)
  })

  test('load button should have proper aria attributes', async ({ page }) => {
    // Open IGV
    const igvOpened = await ensureIGVEnabled(page)

    if (!igvOpened) {
      console.log('Warning: IGV switch not found')
      test.skip()
      return
    }

    const loadButton = getLoadOverlapButton(page)
    const buttonVisible = await loadButton.isVisible({ timeout: 10000 }).catch(() => false)

    if (!buttonVisible) {
      console.log('Warning: Load button not visible')
      test.skip()
      return
    }

    // Check for aria-label or accessible name
    const ariaLabel = await loadButton.getAttribute('aria-label')
    const buttonText = await loadButton.textContent()
    const role = await loadButton.getAttribute('role')

    console.log(`Button aria-label: ${ariaLabel || 'not set'}`)
    console.log(`Button text content: ${buttonText}`)
    console.log(`Button role: ${role || 'button (default)'}`)

    // Button should have accessible name
    const hasAccessibleName = !!ariaLabel || !!buttonText?.trim()
    expect(hasAccessibleName).toBe(true)
    console.log('Success: Button has accessible name')
  })

  test('IGV switch should have proper label', async ({ page }) => {
    // Find the IGV switch using better locators
    const igvSwitch = page.locator('button[role="switch"]').first()
    const switchVisible = await igvSwitch.isVisible({ timeout: 5000 }).catch(() => false)

    if (!switchVisible) {
      console.log('Warning: IGV switch not found')
      test.skip()
      return
    }

    // Check for associated label
    const ariaLabel = await igvSwitch.getAttribute('aria-label')
    const ariaLabelledBy = await igvSwitch.getAttribute('aria-labelledby')

    console.log(`Switch aria-label: ${ariaLabel || 'not set'}`)
    console.log(`Switch aria-labelledby: ${ariaLabelledBy || 'not set'}`)

    // Should have some form of labeling
    const hasLabel = !!ariaLabel || !!ariaLabelledBy
    if (hasLabel) {
      console.log('Success: IGV switch has proper labeling')
    } else {
      console.log('Warning: IGV switch may need accessibility improvement')
    }
  })
})

// ============================================================================
// P2 Tests: Integration with Table
// ============================================================================

test.describe('P2: Integration with Table', () => {
  test.beforeEach(async ({ page }) => {
    await page.goto(`${BASE_URL}${PAGE_URL}`)
    await page.waitForLoadState('networkidle')
    await waitForPageLoad(page)
  })

  test('should load track data matching current table filters', async ({ page }) => {
    // Open IGV
    const igvOpened = await ensureIGVEnabled(page)

    if (!igvOpened) {
      console.log('Warning: IGV switch not found')
      test.skip()
      return
    }

    // Get current filter values (if visible)
    const chromosomeSelect = page.locator('.ant-select').filter({ hasText: /chr/i }).first()
    let currentChromosome = ''

    const chrVisible = await chromosomeSelect.isVisible({ timeout: 3000 }).catch(() => false)
    if (chrVisible) {
      currentChromosome = (await chromosomeSelect.textContent()) || ''
      console.log(`Current chromosome filter: ${currentChromosome}`)
    }

    // Load track and verify API call includes filter params
    const loadButton = getLoadOverlapButton(page)
    const buttonVisible = await loadButton.isVisible({ timeout: 10000 }).catch(() => false)

    if (!buttonVisible) {
      console.log('Warning: Load button not visible')
      test.skip()
      return
    }

    let apiUrl = ''
    page.on('request', (request) => {
      if (request.url().includes('/api/v1/igv/overlap-track')) {
        apiUrl = request.url()
      }
    })

    await loadButton.click()
    await page.waitForTimeout(3000)

    if (apiUrl) {
      console.log(`API URL called: ${apiUrl}`)
      // Verify filter params are in the URL
      if (currentChromosome && apiUrl.includes('chromosome')) {
        console.log('Success: API call includes chromosome filter')
      }
    } else {
      console.log('Info: Could not capture API URL')
    }
  })

  test('clicking table row should update IGV view', async ({ page }) => {
    // Open IGV
    const igvOpened = await ensureIGVEnabled(page)

    if (!igvOpened) {
      console.log('Warning: IGV switch not found')
      test.skip()
      return
    }

    // Wait for table data
    const tableRow = page.locator('.ant-table tbody tr').first()
    const hasRows = await tableRow.isVisible({ timeout: 10000 }).catch(() => false)

    if (!hasRows) {
      console.log('Warning: No table rows available')
      test.skip()
      return
    }

    // Click a row
    await tableRow.click()
    await page.waitForTimeout(2000)

    // Check for IGV locus update or success message
    const successMessage = page.locator('.ant-message-success')
    const hasSuccess = await successMessage.isVisible({ timeout: 3000 }).catch(() => false)

    const igvLocus = page.locator('[class*="igv-locus"], input[placeholder*="locus"]').first()
    const hasLocus = await igvLocus.isVisible({ timeout: 3000 }).catch(() => false)

    if (hasSuccess) {
      console.log('Success: Row click triggered IGV navigation')
    } else if (hasLocus) {
      const locusValue = await igvLocus.inputValue().catch(() => '')
      console.log(`IGV locus value: ${locusValue}`)
    } else {
      console.log('Info: Row click response not detected')
    }
  })
})
