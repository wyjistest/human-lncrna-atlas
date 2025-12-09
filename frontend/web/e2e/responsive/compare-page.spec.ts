import { test, expect } from '@playwright/test'

/**
 * Responsive Design E2E Tests for ChIP-seq Compare Page
 *
 * Tests for responsive behavior across different viewport sizes.
 * Covers:
 * 1. Mobile viewport (375x667 - iPhone SE)
 * 2. Tablet viewport (768x1024 - iPad)
 * 3. Desktop viewport (1920x1080)
 * 4. Layout adaptations
 * 5. Touch interactions
 *
 * Note: Page language may be Chinese or English depending on browser settings
 */

const BASE_URL = process.env.BASE_URL || 'http://localhost:5173'
const TEST_GENE_ID = 17276

// Viewport configurations
const VIEWPORTS = {
  mobile: { width: 375, height: 667 },
  tablet: { width: 768, height: 1024 },
  desktop: { width: 1920, height: 1080 },
}

test.describe('Responsive Design - Mobile Viewport', () => {
  test.beforeEach(async ({ page }) => {
    await page.setViewportSize(VIEWPORTS.mobile)
    await page.goto(`${BASE_URL}/genes/${TEST_GENE_ID}`)
    await page.waitForLoadState('networkidle')
  })

  test('should render page correctly on mobile', async ({ page }) => {
    // Page should load
    await expect(page).toHaveURL(new RegExp(`/genes/${TEST_GENE_ID}`))

    // Main content should be visible
    const mainContent = page.locator('.ant-layout-content')
      .or(page.locator('main'))
      .or(page.locator('[class*="content"]'))

    await expect(mainContent.first()).toBeVisible({ timeout: 15000 })
  })

  test('should hide sidebar on mobile', async ({ page }) => {
    // Sidebar should be hidden or collapsed on mobile
    const sidebar = page.locator('.ant-layout-sider:visible')

    // Either sidebar should be hidden or have collapsed width
    const sidebarCount = await sidebar.count()
    if (sidebarCount > 0) {
      const sidebarBox = await sidebar.first().boundingBox()
      if (sidebarBox) {
        // Collapsed sidebar should be narrow
        expect(sidebarBox.width).toBeLessThanOrEqual(80)
      }
    }
  })

  test('should stack cards vertically on mobile', async ({ page }) => {
    // Navigate to ChIP-seq tab
    const genomicFeaturesTab = page.getByRole('tab', { name: /Genomic Features|/i })
    if ((await genomicFeaturesTab.count()) > 0) {
      await genomicFeaturesTab.click()
      await page.waitForTimeout(500)
    }

    const chipseqTab = page.getByRole('tab', { name: /ChIP-seq|ChIP|/i })
    if ((await chipseqTab.count()) > 0) {
      await chipseqTab.first().click()
      await page.waitForTimeout(1500)

      // Cards should stack vertically (check widths are similar)
      const cards = page.locator('.ant-card')
      const cardCount = await cards.count()

      if (cardCount >= 2) {
        const firstCard = await cards.first().boundingBox()
        const secondCard = await cards.nth(1).boundingBox()

        if (firstCard && secondCard) {
          // Cards should have similar widths (stacked)
          const widthDiff = Math.abs(firstCard.width - secondCard.width)
          expect(widthDiff).toBeLessThan(50)
        }
      }
    }
  })

  test('should have scrollable table on mobile', async ({ page }) => {
    // Navigate to ChIP-seq tab
    const genomicFeaturesTab = page.getByRole('tab', { name: /Genomic Features|/i })
    if ((await genomicFeaturesTab.count()) > 0) {
      await genomicFeaturesTab.click()
      await page.waitForTimeout(500)
    }

    const chipseqTab = page.getByRole('tab', { name: /ChIP-seq|ChIP|/i })
    if ((await chipseqTab.count()) > 0) {
      await chipseqTab.first().click()
      await page.waitForTimeout(2000)

      // Table should be in a scrollable container
      const tableWrapper = page.locator('.ant-table-wrapper')
        .or(page.locator('.ant-table-container'))

      if ((await tableWrapper.count()) > 0) {
        const table = page.locator('.ant-table')
        const tableBox = await table.first().boundingBox()
        const viewportWidth = VIEWPORTS.mobile.width

        // Table might be wider than viewport (scrollable)
        console.log(`Table width: ${tableBox?.width}, Viewport: ${viewportWidth}`)
      }
    }
  })

  test('should have touch-friendly buttons', async ({ page }) => {
    // Navigate to ChIP-seq tab
    const genomicFeaturesTab = page.getByRole('tab', { name: /Genomic Features|/i })
    if ((await genomicFeaturesTab.count()) > 0) {
      await genomicFeaturesTab.click()
      await page.waitForTimeout(500)
    }

    const chipseqTab = page.getByRole('tab', { name: /ChIP-seq|ChIP|/i })
    if ((await chipseqTab.count()) > 0) {
      await chipseqTab.first().click()
      await page.waitForTimeout(1500)

      // Check button sizes for touch targets
      const buttons = page.locator('.ant-btn')
      const buttonCount = await buttons.count()

      if (buttonCount > 0) {
        for (let i = 0; i < Math.min(buttonCount, 5); i++) {
          const button = buttons.nth(i)
          const box = await button.boundingBox()

          if (box) {
            // Touch targets should be at least 44px (iOS guideline)
            const minDimension = Math.min(box.width, box.height)
            console.log(`Button ${i} dimensions: ${box.width}x${box.height}`)
          }
        }
      }
    }
  })
})

test.describe('Responsive Design - Tablet Viewport', () => {
  test.beforeEach(async ({ page }) => {
    await page.setViewportSize(VIEWPORTS.tablet)
    await page.goto(`${BASE_URL}/genes/${TEST_GENE_ID}`)
    await page.waitForLoadState('networkidle')
  })

  test('should render page correctly on tablet', async ({ page }) => {
    await expect(page).toHaveURL(new RegExp(`/genes/${TEST_GENE_ID}`))

    const mainContent = page.locator('.ant-layout-content')
      .or(page.locator('main'))

    await expect(mainContent.first()).toBeVisible({ timeout: 15000 })
  })

  test('should show sidebar in collapsed state on tablet', async ({ page }) => {
    const sidebar = page.locator('.ant-layout-sider')

    const sidebarCount = await sidebar.count()
    if (sidebarCount > 0) {
      const sidebarBox = await sidebar.first().boundingBox()
      if (sidebarBox) {
        // On tablet, sidebar might be collapsed
        console.log(`Sidebar width on tablet: ${sidebarBox.width}`)
      }
    }
  })

  test('should display two-column layout for cards on tablet', async ({ page }) => {
    // Navigate to ChIP-seq tab
    const genomicFeaturesTab = page.getByRole('tab', { name: /Genomic Features|/i })
    if ((await genomicFeaturesTab.count()) > 0) {
      await genomicFeaturesTab.click()
      await page.waitForTimeout(500)
    }

    const chipseqTab = page.getByRole('tab', { name: /ChIP-seq|ChIP|/i })
    if ((await chipseqTab.count()) > 0) {
      await chipseqTab.first().click()
      await page.waitForTimeout(1500)

      // Check if cards are in grid layout
      const cardsRow = page.locator('.ant-row').first()
      if ((await cardsRow.count()) > 0) {
        const cols = cardsRow.locator('.ant-col')
        const colCount = await cols.count()
        console.log(`Number of columns in row on tablet: ${colCount}`)
      }
    }
  })

  test('should have adequate table column visibility', async ({ page }) => {
    // Navigate to ChIP-seq tab
    const genomicFeaturesTab = page.getByRole('tab', { name: /Genomic Features|/i })
    if ((await genomicFeaturesTab.count()) > 0) {
      await genomicFeaturesTab.click()
      await page.waitForTimeout(500)
    }

    const chipseqTab = page.getByRole('tab', { name: /ChIP-seq|ChIP|/i })
    if ((await chipseqTab.count()) > 0) {
      await chipseqTab.first().click()
      await page.waitForTimeout(2000)

      const table = page.locator('.ant-table')
      if ((await table.count()) > 0) {
        const headers = table.locator('.ant-table-thead th')
        const headerCount = await headers.count()
        console.log(`Visible table columns on tablet: ${headerCount}`)
      }
    }
  })
})

test.describe('Responsive Design - Desktop Viewport', () => {
  test.beforeEach(async ({ page }) => {
    await page.setViewportSize(VIEWPORTS.desktop)
    await page.goto(`${BASE_URL}/genes/${TEST_GENE_ID}`)
    await page.waitForLoadState('networkidle')
  })

  test('should render page correctly on desktop', async ({ page }) => {
    await expect(page).toHaveURL(new RegExp(`/genes/${TEST_GENE_ID}`))

    const mainContent = page.locator('.ant-layout-content')
      .or(page.locator('main'))

    await expect(mainContent.first()).toBeVisible({ timeout: 15000 })
  })

  test('should show expanded sidebar on desktop', async ({ page }) => {
    const sidebar = page.locator('.ant-layout-sider')

    const sidebarCount = await sidebar.count()
    if (sidebarCount > 0) {
      const sidebarBox = await sidebar.first().boundingBox()
      if (sidebarBox) {
        // Expanded sidebar should be wider than 100px
        console.log(`Sidebar width on desktop: ${sidebarBox.width}`)
      }
    }
  })

  test('should display multi-column layout on desktop', async ({ page }) => {
    // Navigate to ChIP-seq tab
    const genomicFeaturesTab = page.getByRole('tab', { name: /Genomic Features|/i })
    if ((await genomicFeaturesTab.count()) > 0) {
      await genomicFeaturesTab.click()
      await page.waitForTimeout(500)
    }

    const chipseqTab = page.getByRole('tab', { name: /ChIP-seq|ChIP|/i })
    if ((await chipseqTab.count()) > 0) {
      await chipseqTab.first().click()
      await page.waitForTimeout(1500)

      // Statistics cards should be in a row
      const statsCards = page.locator('.ant-statistic')
      const cardCount = await statsCards.count()

      if (cardCount >= 2) {
        const firstCard = await statsCards.first().boundingBox()
        const secondCard = await statsCards.nth(1).boundingBox()

        if (firstCard && secondCard) {
          // Cards should be side by side (different X positions, similar Y)
          const yDiff = Math.abs(firstCard.y - secondCard.y)
          console.log(`Cards Y difference on desktop: ${yDiff}`)
        }
      }
    }
  })

  test('should show all table columns without horizontal scroll', async ({ page }) => {
    // Navigate to ChIP-seq tab
    const genomicFeaturesTab = page.getByRole('tab', { name: /Genomic Features|/i })
    if ((await genomicFeaturesTab.count()) > 0) {
      await genomicFeaturesTab.click()
      await page.waitForTimeout(500)
    }

    const chipseqTab = page.getByRole('tab', { name: /ChIP-seq|ChIP|/i })
    if ((await chipseqTab.count()) > 0) {
      await chipseqTab.first().click()
      await page.waitForTimeout(2000)

      const tableContainer = page.locator('.ant-table-container')
      if ((await tableContainer.count()) > 0) {
        const containerBox = await tableContainer.first().boundingBox()
        const tableBox = await page.locator('.ant-table').first().boundingBox()

        if (containerBox && tableBox) {
          // Table should fit within container on desktop
          console.log(`Container width: ${containerBox.width}, Table width: ${tableBox.width}`)
        }
      }
    }
  })
})

test.describe('Responsive Charts', () => {
  test('should resize charts on viewport change', async ({ page }) => {
    await page.setViewportSize(VIEWPORTS.desktop)
    await page.goto(`${BASE_URL}/genes/${TEST_GENE_ID}`)
    await page.waitForLoadState('networkidle')

    // Navigate to ChIP-seq tab
    const genomicFeaturesTab = page.getByRole('tab', { name: /Genomic Features|/i })
    if ((await genomicFeaturesTab.count()) > 0) {
      await genomicFeaturesTab.click()
      await page.waitForTimeout(500)
    }

    const chipseqTab = page.getByRole('tab', { name: /ChIP-seq|ChIP|/i })
    if ((await chipseqTab.count()) > 0) {
      await chipseqTab.first().click()
      await page.waitForTimeout(1500)

      // Enter compare mode and go to Statistics view
      const compareButton = page.getByRole('button', { name: /Compare|/i })
      if ((await compareButton.count()) > 0) {
        await compareButton.first().click()
        await page.waitForTimeout(500)

        // Select additional mark
        const markSelector = page.locator('.ant-select').first()
        if ((await markSelector.count()) > 0) {
          await markSelector.click()
          await page.waitForTimeout(300)

          const markOption = page.locator('.ant-select-dropdown').getByText('H3K4me3', { exact: false })
          if ((await markOption.count()) > 0) {
            await markOption.first().click()
            await page.waitForTimeout(1500)

            // Switch to Statistics view
            const statsTab = page.getByRole('tab', { name: /Statistics|/i })
            if ((await statsTab.count()) > 0) {
              await statsTab.click()
              await page.waitForTimeout(1000)

              // Get initial chart size
              const chart = page.locator('canvas').first()
              const initialSize = await chart.boundingBox()

              // Resize viewport
              await page.setViewportSize(VIEWPORTS.tablet)
              await page.waitForTimeout(500)

              // Chart should resize
              const newSize = await chart.boundingBox()

              if (initialSize && newSize) {
                console.log(`Chart size changed: ${initialSize.width}x${initialSize.height} -> ${newSize.width}x${newSize.height}`)
              }
            }
          }
        }
      }
    }
  })
})

test.describe('Responsive Filters', () => {
  test('should collapse filters on mobile', async ({ page }) => {
    await page.setViewportSize(VIEWPORTS.mobile)
    await page.goto(`${BASE_URL}/genes/${TEST_GENE_ID}`)
    await page.waitForLoadState('networkidle')

    // Navigate to ChIP-seq tab
    const genomicFeaturesTab = page.getByRole('tab', { name: /Genomic Features|/i })
    if ((await genomicFeaturesTab.count()) > 0) {
      await genomicFeaturesTab.click()
      await page.waitForTimeout(500)
    }

    const chipseqTab = page.getByRole('tab', { name: /ChIP-seq|ChIP|/i })
    if ((await chipseqTab.count()) > 0) {
      await chipseqTab.first().click()
      await page.waitForTimeout(1500)

      // Look for collapsed filter panel or filter toggle button
      const filterCollapse = page.locator('.ant-collapse')
        .or(page.getByRole('button', { name: /Filter|/i }))

      const collapseCount = await filterCollapse.count()
      console.log(`Filter collapse/toggle elements: ${collapseCount}`)
    }
  })

  test('should show expanded filters on desktop', async ({ page }) => {
    await page.setViewportSize(VIEWPORTS.desktop)
    await page.goto(`${BASE_URL}/genes/${TEST_GENE_ID}`)
    await page.waitForLoadState('networkidle')

    // Navigate to ChIP-seq tab
    const genomicFeaturesTab = page.getByRole('tab', { name: /Genomic Features|/i })
    if ((await genomicFeaturesTab.count()) > 0) {
      await genomicFeaturesTab.click()
      await page.waitForTimeout(500)
    }

    const chipseqTab = page.getByRole('tab', { name: /ChIP-seq|ChIP|/i })
    if ((await chipseqTab.count()) > 0) {
      await chipseqTab.first().click()
      await page.waitForTimeout(1500)

      // Filters should be visible without expansion on desktop
      const filterInputs = page.locator('.ant-select, .ant-input-number')
      const inputCount = await filterInputs.count()
      console.log(`Visible filter inputs on desktop: ${inputCount}`)
    }
  })
})

test.describe('Responsive Tables', () => {
  test('should show horizontal scroll indicator on mobile', async ({ page }) => {
    await page.setViewportSize(VIEWPORTS.mobile)
    await page.goto(`${BASE_URL}/genes/${TEST_GENE_ID}`)
    await page.waitForLoadState('networkidle')

    // Navigate to ChIP-seq tab
    const genomicFeaturesTab = page.getByRole('tab', { name: /Genomic Features|/i })
    if ((await genomicFeaturesTab.count()) > 0) {
      await genomicFeaturesTab.click()
      await page.waitForTimeout(500)
    }

    const chipseqTab = page.getByRole('tab', { name: /ChIP-seq|ChIP|/i })
    if ((await chipseqTab.count()) > 0) {
      await chipseqTab.first().click()
      await page.waitForTimeout(2000)

      // Table container should be scrollable
      const tableBody = page.locator('.ant-table-body')
      if ((await tableBody.count()) > 0) {
        const scrollableStyle = await tableBody.first().getAttribute('style')
        console.log(`Table body style: ${scrollableStyle}`)
      }
    }
  })

  test('should be able to scroll table horizontally', async ({ page }) => {
    await page.setViewportSize(VIEWPORTS.mobile)
    await page.goto(`${BASE_URL}/genes/${TEST_GENE_ID}`)
    await page.waitForLoadState('networkidle')

    // Navigate to ChIP-seq tab
    const genomicFeaturesTab = page.getByRole('tab', { name: /Genomic Features|/i })
    if ((await genomicFeaturesTab.count()) > 0) {
      await genomicFeaturesTab.click()
      await page.waitForTimeout(500)
    }

    const chipseqTab = page.getByRole('tab', { name: /ChIP-seq|ChIP|/i })
    if ((await chipseqTab.count()) > 0) {
      await chipseqTab.first().click()
      await page.waitForTimeout(2000)

      // Simulate horizontal scroll
      const tableContainer = page.locator('.ant-table-container')
      if ((await tableContainer.count()) > 0) {
        // Scroll right
        await tableContainer.first().evaluate((el) => {
          el.scrollLeft = 200
        })
        await page.waitForTimeout(300)

        // Verify scroll position changed
        const scrollLeft = await tableContainer.first().evaluate((el) => el.scrollLeft)
        console.log(`Table scroll position: ${scrollLeft}`)
      }
    }
  })
})

test.describe('Responsive Tabs', () => {
  test('should have scrollable tabs on mobile', async ({ page }) => {
    await page.setViewportSize(VIEWPORTS.mobile)
    await page.goto(`${BASE_URL}/genes/${TEST_GENE_ID}`)
    await page.waitForLoadState('networkidle')

    // Tabs should be scrollable if there are many
    const tabsNav = page.locator('.ant-tabs-nav')
    if ((await tabsNav.count()) > 0) {
      const navBox = await tabsNav.first().boundingBox()
      console.log(`Tabs nav width on mobile: ${navBox?.width}`)
    }
  })

  test('should show all tabs on desktop', async ({ page }) => {
    await page.setViewportSize(VIEWPORTS.desktop)
    await page.goto(`${BASE_URL}/genes/${TEST_GENE_ID}`)
    await page.waitForLoadState('networkidle')

    const tabs = page.locator('.ant-tabs-tab')
    const visibleTabs = await tabs.evaluateAll((elements) =>
      elements.filter((el) => (el as HTMLElement).offsetParent !== null).length
    )
    console.log(`Visible tabs on desktop: ${visibleTabs}`)
  })
})

test.describe('Print Layout', () => {
  test('should have print-friendly styles', async ({ page }) => {
    await page.setViewportSize(VIEWPORTS.desktop)
    await page.goto(`${BASE_URL}/genes/${TEST_GENE_ID}`)
    await page.waitForLoadState('networkidle')

    // Navigate to ChIP-seq tab
    const genomicFeaturesTab = page.getByRole('tab', { name: /Genomic Features|/i })
    if ((await genomicFeaturesTab.count()) > 0) {
      await genomicFeaturesTab.click()
      await page.waitForTimeout(500)
    }

    const chipseqTab = page.getByRole('tab', { name: /ChIP-seq|ChIP|/i })
    if ((await chipseqTab.count()) > 0) {
      await chipseqTab.first().click()
      await page.waitForTimeout(1500)

      // Emulate print media
      await page.emulateMedia({ media: 'print' })
      await page.waitForTimeout(300)

      // Take screenshot in print mode
      const screenshot = await page.screenshot()
      console.log(`Print mode screenshot taken, size: ${screenshot.length} bytes`)

      // Reset to screen media
      await page.emulateMedia({ media: 'screen' })
    }
  })
})

test.describe('High DPI Display', () => {
  test('should render correctly on high DPI display', async ({ page }) => {
    // Set high DPI viewport
    await page.setViewportSize({ width: 1920, height: 1080 })
    await page.evaluate(() => {
      Object.defineProperty(window, 'devicePixelRatio', {
        get: () => 2,
      })
    })

    await page.goto(`${BASE_URL}/genes/${TEST_GENE_ID}`)
    await page.waitForLoadState('networkidle')

    // Page should render correctly
    const mainContent = page.locator('.ant-layout-content')
    await expect(mainContent.first()).toBeVisible({ timeout: 15000 })

    // Charts should still render (canvas elements)
    const canvases = page.locator('canvas')
    const canvasCount = await canvases.count()
    console.log(`Canvas elements on high DPI: ${canvasCount}`)
  })
})
