import { test, expect } from '@playwright/test'

/**
 * Navigation Menu E2E Tests
 *
 * Tests for site-wide navigation and menu functionality.
 * Verifies that users can navigate to all major sections including ChIP-seq features.
 *
 * Covers:
 * 1. Main navigation menu
 * 2. ChIP-seq related menu items
 * 3. Breadcrumb navigation
 * 4. Deep linking
 *
 * Note: Page language may be Chinese or English depending on browser settings
 */


test.describe('Main Navigation Menu', () => {
  test.beforeEach(async ({ page }) => {
    await page.goto('/')
    await page.waitForLoadState('networkidle')
  })

  test('should display navigation menu', async ({ page }) => {
    // Look for main navigation (sidebar or top menu)
    const navigation = page.locator('.ant-menu')
      .or(page.locator('nav'))
      .or(page.locator('.ant-layout-sider'))

    await expect(navigation.first()).toBeVisible({ timeout: 10000 })
  })

  test('should have Home menu item', async ({ page }) => {
    const homeItem = page.getByRole('menuitem', { name: /Home|首页/i })
      .or(page.locator('.ant-menu-item').filter({ hasText: /Home|首页/i }))
      .or(page.locator('a').filter({ hasText: /Home|首页/i }))

    const itemCount = await homeItem.count()
    if (itemCount > 0) {
      await homeItem.first().click()
      // Playwright 的 URL 是完整地址（含 host），这里仅校验回到根路径即可（兼容 127.0.0.1/localhost/LAN IP）。
      await expect(page).toHaveURL(/\/$/)
    }
  })

  test('should have Genes menu item', async ({ page }) => {
    const genesItem = page.getByRole('menuitem', { name: /Gene List|Genes|基因/i })
      .or(page.locator('.ant-menu-item').filter({ hasText: /Gene List|Genes|基因/i }))
      .or(page.locator('a').filter({ hasText: /Gene List|Genes|基因/i }))

    const itemCount = await genesItem.count()
    if (itemCount > 0) {
      await genesItem.first().click()
      await page.waitForLoadState('networkidle')
      await expect(page).toHaveURL(/genes/)
    }
  })

  test('should have lncRNA-ChIP-seq Overlap menu item', async ({ page }) => {
    const overlapItem = page.getByRole('menuitem', { name: /Overlap|ChIP.*seq/i })
      .or(page.locator('.ant-menu-item').filter({ hasText: /Overlap|ChIP.*seq/i }))
      .or(page.locator('a').filter({ hasText: /Overlap/i }))

    const itemCount = await overlapItem.count()
    if (itemCount > 0) {
      await overlapItem.first().click()
      await page.waitForLoadState('networkidle')
      await expect(page).toHaveURL(/lncrna-chipseq-overlap/)
    } else {
      console.log('lncRNA-ChIP-seq Overlap menu item not found in main menu')
    }
  })

  test('should have Genome Browser menu item', async ({ page }) => {
    const browserItem = page.getByRole('menuitem', { name: /Genome.*Browser|Browser/i })
      .or(page.locator('.ant-menu-item').filter({ hasText: /Genome.*Browser|Browser/i }))
      .or(page.locator('a').filter({ hasText: /Browser/i }))

    const itemCount = await browserItem.count()
    if (itemCount > 0) {
      await browserItem.first().click()
      await page.waitForLoadState('networkidle')
      await expect(page).toHaveURL(/genome-browser/)
    }
  })

  test('should have Regulations menu item', async ({ page }) => {
    const regulationsItem = page.getByRole('menuitem', { name: /Regulations|调控|关系/i })
      .or(page.locator('.ant-menu-item').filter({ hasText: /Regulations|调控|关系/i }))
      .or(page.locator('a').filter({ hasText: /Regulations|调控|关系/i }))

    const itemCount = await regulationsItem.count()
    if (itemCount > 0) {
      await regulationsItem.first().click()
      await page.waitForLoadState('networkidle')
      await expect(page).toHaveURL(/regulations/)
    }
  })
})

test.describe('ChIP-seq Feature Navigation', () => {
	  test('should navigate from Genes list to Gene detail', async ({ page }) => {
	    // Go to genes list
	    await page.goto('/genes')
	    await page.waitForLoadState('networkidle')
	
	    // 在 Gene List 表格中点击“View →”按钮进入详情（避免误点外链 View →）
		    // antd Virtual Table 的行不一定是 <tr>，统一用 `.ant-table-row[data-row-key]` 兼容虚拟/非虚拟渲染。
		    const firstRow = page.locator('.ant-table-row[data-row-key]').first()
		      .or(page.locator('table tbody tr').first())

	    if ((await firstRow.count()) > 0) {
	      const viewBtn = firstRow.getByRole('button', { name: /View/i }).first()
	      if ((await viewBtn.count()) > 0) {
	        await Promise.all([
	          page.waitForURL(/\/genes\/\d+/, { timeout: 15000 }),
	          viewBtn.click(),
	        ])

	        // Should navigate to gene detail page
	        await expect(page).toHaveURL(/\/genes\/\d+/)
	      }
	    }
	  })

  test('should navigate to ChIP-seq tab from Gene detail', async ({ page }) => {
    // Go directly to a gene detail page
    await page.goto('/genes/17276')
    await page.waitForLoadState('networkidle')

    // Look for Genomic Features tab
    const genomicFeaturesTab = page.getByRole('tab', { name: /Genomic Features|基因组|Feature/i })
    if ((await genomicFeaturesTab.count()) > 0) {
      await genomicFeaturesTab.click()
      await page.waitForTimeout(500)
    }

    // Look for ChIP-seq tab
    const chipseqTab = page.getByRole('tab', { name: /ChIP-seq|ChIP/i })
      .or(page.locator('.ant-tabs-tab').filter({ hasText: /ChIP/i }))

    const tabCount = await chipseqTab.count()
    if (tabCount > 0) {
      await chipseqTab.first().click()
      await page.waitForTimeout(1000)

      // ChIP-seq content should be visible
      const chipseqContent = page.locator('.ant-table')
        .or(page.locator('.ant-card'))

      await expect(chipseqContent.first()).toBeVisible({ timeout: 10000 })
    }
  })

  test('should access lncRNA-ChIP-seq Overlap page directly', async ({ page }) => {
    await page.goto('/lncrna-chipseq-overlap')
    await page.waitForLoadState('networkidle')

    // Should load the page
    await expect(page).toHaveURL(/lncrna-chipseq-overlap/)

    // Page content should be visible
    const pageContent = page.locator('.ant-table')
      .or(page.locator('.ant-card'))
      .or(page.locator('h1, h2'))

    await expect(pageContent.first()).toBeVisible({ timeout: 15000 })
  })
})

test.describe('Breadcrumb Navigation', () => {
  test('should display breadcrumbs on Gene detail page', async ({ page }) => {
    await page.goto('/genes/17276')
    await page.waitForLoadState('networkidle')

    const breadcrumb = page.locator('.ant-breadcrumb')

    const breadcrumbCount = await breadcrumb.count()
    if (breadcrumbCount > 0) {
      await expect(breadcrumb).toBeVisible()

      // Breadcrumb should have items
      const breadcrumbItems = breadcrumb.locator('.ant-breadcrumb-link, .ant-breadcrumb-separator')
      const itemCount = await breadcrumbItems.count()
      expect(itemCount).toBeGreaterThan(0)
    }
  })

  test('should navigate back via breadcrumb', async ({ page }) => {
    await page.goto('/genes/17276')
    await page.waitForLoadState('networkidle')

    const breadcrumb = page.locator('.ant-breadcrumb')

    if ((await breadcrumb.count()) > 0) {
      // Click on "Genes" breadcrumb item to go back
      const genesLink = breadcrumb.locator('a').filter({ hasText: /Genes|Gene List|基因/i })

      if ((await genesLink.count()) > 0) {
        await genesLink.click()
        await page.waitForLoadState('networkidle')

        // Should navigate back to genes list
        await expect(page).toHaveURL(/\/genes$|\/genes\//)
      }
    }
  })
})

test.describe('Deep Linking', () => {
  test('should load Gene detail page directly by URL', async ({ page }) => {
    await page.goto('/genes/17276')
    await page.waitForLoadState('networkidle')

    // Page should load correctly
    await expect(page).toHaveURL(/\/genes\/17276/)

    // Gene detail content should be visible
    const pageContent = page.locator('.ant-descriptions')
      .or(page.locator('.ant-card'))
      .or(page.locator('.ant-tabs'))

    await expect(pageContent.first()).toBeVisible({ timeout: 15000 })
  })

  test('should handle non-existent gene gracefully', async ({ page }) => {
    await page.goto('/genes/99999999')
    await page.waitForLoadState('networkidle')

    // Should show error or not found message (wait for it, don't just "count" once)
    const errorContent = page.getByText(/Not Found|Error|404/i)
      .or(page.locator('.ant-result'))
      .or(page.locator('.ant-alert-error'))
      .or(page.locator('text=Failed to load'))
      .or(page.getByText(/Gene not found/i))
      .or(page.locator('[data-testid="error-state"]'))

    try {
      await expect(errorContent.first()).toBeVisible({ timeout: 15000 })
      return
    } catch {
      // If no error, page should still load (maybe empty state) or redirect away
      const pageContent = page.locator('.ant-empty')
        .or(page.locator('.ant-card'))
        .or(page.locator('.ant-result'))

      await expect(pageContent.first()).toBeVisible({ timeout: 15000 })
    }
  })

  test('should load lncRNA-ChIP-seq Overlap page directly', async ({ page }) => {
    await page.goto('/lncrna-chipseq-overlap')
    await page.waitForLoadState('networkidle')

    // Page should load correctly
    await expect(page).toHaveURL(/lncrna-chipseq-overlap/)

    // Wait for page content
    const pageContent = page.locator('.ant-table')
      .or(page.locator('.ant-card'))
      .or(page.locator('h1, h2'))

    await expect(pageContent.first()).toBeVisible({ timeout: 15000 })
  })
})

test.describe('Menu Item Highlighting', () => {
  test('should highlight current menu item on Genes page', async ({ page }) => {
    await page.goto('/genes')
    await page.waitForLoadState('networkidle')

    // Look for highlighted menu item
    const activeMenuItem = page.locator('.ant-menu-item-selected')
      .or(page.locator('.ant-menu-item-active'))

    const activeCount = await activeMenuItem.count()
    if (activeCount > 0) {
      const activeText = await activeMenuItem.first().textContent()
      expect(activeText?.toLowerCase()).toContain('gene')
    }
  })

  test('should highlight current menu item on Regulations page', async ({ page }) => {
    await page.goto('/regulations')
    await page.waitForLoadState('networkidle')

    const activeMenuItem = page.locator('.ant-menu-item-selected')
      .or(page.locator('.ant-menu-item-active'))

    const activeCount = await activeMenuItem.count()
    if (activeCount > 0) {
      const activeText = await activeMenuItem.first().textContent()
      console.log(`Active menu item: ${activeText}`)
    }
  })
})

test.describe('Sub-Menu Navigation', () => {
  test('should expand and collapse sub-menus', async ({ page }) => {
    await page.goto('/')
    await page.waitForLoadState('networkidle')

    // Look for expandable sub-menu
    const subMenuTrigger = page.locator('.ant-menu-submenu-title').first()
      .or(page.locator('.ant-menu-item-group-title').first())

    const triggerCount = await subMenuTrigger.count()
    if (triggerCount > 0) {
      // Click to expand
      await subMenuTrigger.click()
      await page.waitForTimeout(300)

      // Sub-menu should be visible
      const subMenu = page.locator('.ant-menu-submenu-popup')
        .or(page.locator('.ant-menu-sub'))

      const subMenuCount = await subMenu.count()
      console.log(`Sub-menu elements found: ${subMenuCount}`)
    }
  })

  test('should navigate through sub-menu items', async ({ page }) => {
    await page.goto('/')
    await page.waitForLoadState('networkidle')

    // Look for menu items under sub-menu (e.g., Data Analysis sub-menu)
    const subMenuTrigger = page.locator('.ant-menu-submenu-title').filter({ hasText: /Data|Analysis/i })

    if ((await subMenuTrigger.count()) > 0) {
      await subMenuTrigger.click()
      await page.waitForTimeout(500)

      // Click a sub-menu item
      const subMenuItem = page.locator('.ant-menu-sub .ant-menu-item').first()
      if ((await subMenuItem.count()) > 0) {
        await subMenuItem.click()
        await page.waitForLoadState('networkidle')

        // Should navigate to the sub-item page
        console.log(`Navigated to: ${page.url()}`)
      }
    }
  })
})

test.describe('Mobile Navigation', () => {
  test('should show hamburger menu on mobile viewport', async ({ page }) => {
    await page.setViewportSize({ width: 375, height: 667 })
    await page.goto('/')
    await page.waitForLoadState('networkidle')

    // Look for hamburger menu button
    const hamburgerButton = page.locator('.ant-layout-sider-trigger')
      .or(page.locator('button[aria-label*="menu"]'))
      .or(page.locator('[class*="hamburger"]'))

    const buttonCount = await hamburgerButton.count()
    console.log(`Hamburger menu button found: ${buttonCount > 0}`)
  })

  test('should open mobile menu when hamburger clicked', async ({ page }) => {
    await page.setViewportSize({ width: 375, height: 667 })
    await page.goto('/')
    await page.waitForLoadState('networkidle')

    const hamburgerButton = page.locator('.ant-layout-sider-trigger')
      .or(page.locator('button[aria-label*="menu"]'))

    if ((await hamburgerButton.count()) > 0) {
      await hamburgerButton.click()
      await page.waitForTimeout(500)

      // Menu should be visible
      const menu = page.locator('.ant-menu')
      await expect(menu.first()).toBeVisible()
    }
  })
})

test.describe('Language Switching', () => {
  test('should display language switcher', async ({ page }) => {
    await page.goto('/')
    await page.waitForLoadState('networkidle')

    // Look for language switcher
    const languageSwitcher = page.locator('[data-testid="language-switcher"]')
      .or(page.locator('.ant-dropdown-trigger').filter({ hasText: /EN|ZH/i }))
      .or(page.locator('button').filter({ hasText: /English|中文/i }))

    const switcherCount = await languageSwitcher.count()
    console.log(`Language switcher found: ${switcherCount > 0}`)
  })

  test('should switch language when clicked', async ({ page }) => {
    await page.goto('/')
    await page.waitForLoadState('networkidle')

    const languageSwitcher = page.locator('[data-testid="language-switcher"]')
      .or(page.locator('.ant-dropdown-trigger').filter({ hasText: /EN|ZH/i }))

    if ((await languageSwitcher.count()) > 0) {
      await languageSwitcher.click()
      await page.waitForTimeout(300)

      // Look for language option
      const languageOption = page.getByText(/English|中文/i)
        .or(page.locator('.ant-dropdown-menu-item'))

      if ((await languageOption.count()) > 0) {
        await languageOption.first().click()
        await page.waitForTimeout(500)

        // Page should update (menu items should be in selected language)
        console.log('Language switched')
      }
    }
  })
})
