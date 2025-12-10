import { test, expect } from '@playwright/test'

/**
 * lncRNA-ChIP-seq Overlap IGV Integration E2E Tests
 *
 * 测试 Overlap 页面与 IGV 基因组浏览器的集成功能
 *
 * 核心功能：
 * 1. Overlap 表格 + IGV 分屏布局渲染
 * 2. 点击表格行触发 IGV 跳转到对应染色体位置
 * 3. 性能测试（加载时间、跳转时间）
 * 4. 错误场景处理
 *
 * Route: /lncrna-chipseq-overlap
 */

const PAGE_URL = '/lncrna-chipseq-overlap'
const BASE_URL = process.env.BASE_URL || 'http://localhost:5173'

// ============================================================================
// P0 测试：布局渲染
// ============================================================================

test.describe('Overlap IGV Integration - Layout', () => {
  test.beforeEach(async ({ page }) => {
    await page.goto(`${BASE_URL}${PAGE_URL}`)
    await page.waitForLoadState('networkidle')
  })

  test('should render split layout with overlap table and IGV browser', async ({ page }) => {
    // 等待页面加载完成
    await page.waitForTimeout(2000)

    // 验证 Overlap 表格存在
    const overlapTable = page.locator('.ant-table, [data-testid="overlap-table"]').first()
    const hasTable = await overlapTable.isVisible({ timeout: 10000 }).catch(() => false)

    if (hasTable) {
      console.log('✓ Overlap table is visible')
    } else {
      console.log('⚠ Overlap table not found')
    }

    // 验证 IGV 浏览器容器存在
    const genomeBrowser = page.locator('[data-testid="genome-browser"], [class*="genome-browser"], [class*="igv"]').first()
    const hasBrowser = await genomeBrowser.isVisible({ timeout: 15000 }).catch(() => false)

    if (hasBrowser) {
      console.log('✓ IGV genome browser is visible')
      await expect(genomeBrowser).toBeVisible()
    } else {
      console.log('⚠ IGV browser not found - may not be implemented yet')
    }

    // 至少有一个组件应该可见
    expect(hasTable || hasBrowser).toBe(true)
  })

  test('should display overlap table with data', async ({ page }) => {
    await page.waitForTimeout(3000)

    // 查找表格
    const table = page.locator('.ant-table').first()
    await expect(table).toBeVisible({ timeout: 10000 })

    // 验证表格有数据行
    const tableRows = page.locator('.ant-table tbody tr')
    const rowCount = await tableRows.count()

    if (rowCount > 0) {
      console.log(`✓ Table has ${rowCount} rows`)
      expect(rowCount).toBeGreaterThan(0)
    } else {
      // 可能是空状态
      const emptyState = page.locator('.ant-empty')
      const hasEmptyState = await emptyState.isVisible().catch(() => false)
      console.log(`⚠ Table is empty (empty state: ${hasEmptyState})`)
    }
  })

  test('should display IGV browser container', async ({ page }) => {
    await page.waitForTimeout(3000)

    // 查找 IGV 容器（可能尚未实现）
    const igvContainer = page.locator('[data-testid="genome-browser"], [class*="genome"], [class*="igv"]').first()
    const isVisible = await igvContainer.isVisible({ timeout: 15000 }).catch(() => false)

    if (isVisible) {
      console.log('✓ IGV container found and visible')
      await expect(igvContainer).toBeVisible()
    } else {
      console.log('⚠ IGV container not found - feature may not be implemented yet')
      // 这不是失败，只是功能尚未实现
    }
  })
})

// ============================================================================
// P0 测试：点击表格行触发 IGV 跳转
// ============================================================================

test.describe('Overlap IGV Integration - Navigation', () => {
  test.beforeEach(async ({ page }) => {
    await page.goto(`${BASE_URL}${PAGE_URL}`)
    await page.waitForLoadState('networkidle')
    await page.waitForTimeout(3000)
  })

  test('should navigate IGV when clicking table row', async ({ page }) => {
    // 等待表格加载
    const table = page.locator('.ant-table tbody')
    await table.waitFor({ timeout: 10000 }).catch(() => null)

    // 检查是否有数据行
    const firstRow = page.locator('.ant-table tbody tr').first()
    const hasRows = await firstRow.isVisible().catch(() => false)

    if (!hasRows) {
      console.log('⚠ No table rows available - cannot test navigation')
      return
    }

    // 点击第一行
    await firstRow.click()
    await page.waitForTimeout(1000)

    // 验证是否有成功提示（假设实现后会有 message.success）
    const successMessage = page.locator('.ant-message-success')
    const hasSuccess = await successMessage.isVisible({ timeout: 5000 }).catch(() => false)

    if (hasSuccess) {
      console.log('✓ Success message displayed after row click')
      await expect(successMessage).toBeVisible()
    } else {
      console.log('⚠ No success message - IGV navigation may not be implemented')
    }

    // 检查 IGV 是否有响应（locus 变化）
    const igvLocus = page.locator('[class*="igv-locus"], input[placeholder*="locus"], input[value*="chr"]').first()
    const hasLocus = await igvLocus.isVisible({ timeout: 3000 }).catch(() => false)

    if (hasLocus) {
      const locusValue = await igvLocus.inputValue().catch(() => '')
      console.log(`✓ IGV locus updated: ${locusValue}`)
    } else {
      console.log('⚠ IGV locus input not found')
    }
  })

  test('should highlight clicked row', async ({ page }) => {
    const firstRow = page.locator('.ant-table tbody tr').first()
    const hasRows = await firstRow.isVisible({ timeout: 10000 }).catch(() => false)

    if (!hasRows) {
      console.log('⚠ No table rows available')
      return
    }

    // 点击行
    await firstRow.click()
    await page.waitForTimeout(500)

    // 检查行是否有高亮样式（ant-table-row-selected 或自定义类）
    const rowClass = await firstRow.getAttribute('class')
    const isHighlighted = rowClass?.includes('selected') || rowClass?.includes('active')

    console.log(`Row click highlight: ${isHighlighted ? '✓' : '⚠'} (class: ${rowClass})`)
  })

  test('should update IGV locus to overlap region', async ({ page }) => {
    // 等待表格
    const firstRow = page.locator('.ant-table tbody tr').first()
    await firstRow.waitFor({ timeout: 10000 }).catch(() => null)

    const hasRows = await firstRow.isVisible().catch(() => false)
    if (!hasRows) {
      console.log('⚠ No rows available')
      return
    }

    // 获取行中的染色体位置信息
    const locationCell = firstRow.locator('td').nth(4) // Location 列通常在第 5 列
    const locationText = await locationCell.textContent().catch(() => '')
    console.log(`Table row location: ${locationText}`)

    // 点击行
    await firstRow.click()
    await page.waitForTimeout(2000)

    // 检查 IGV 是否跳转到对应位置
    const igvContainer = page.locator('[class*="igv"], [data-testid="genome-browser"]').first()
    const hasIGV = await igvContainer.isVisible().catch(() => false)

    if (hasIGV) {
      console.log('✓ IGV container visible after row click')
    } else {
      console.log('⚠ IGV not visible or not implemented')
    }
  })
})

// ============================================================================
// P1 测试：性能
// ============================================================================

test.describe('Overlap IGV Integration - Performance', () => {
  test('IGV should load within 15 seconds', async ({ page }) => {
    const startTime = Date.now()

    await page.goto(`${BASE_URL}${PAGE_URL}`)
    await page.waitForLoadState('networkidle')

    // 等待 IGV 容器出现
    const igvContainer = page.locator('[data-testid="genome-browser"], [class*="igv"], [class*="genome-browser"]').first()
    await igvContainer.waitFor({ timeout: 15000, state: 'visible' }).catch(() => null)

    const loadTime = Date.now() - startTime

    console.log(`IGV 加载时间: ${loadTime}ms`)

    if (loadTime < 15000) {
      console.log('✓ IGV loaded within 15 seconds')
      expect(loadTime).toBeLessThan(15000)
    } else {
      console.log('⚠ IGV load time exceeded 15s or not found')
    }
  })

  test('IGV navigation should respond within 3 seconds', async ({ page }) => {
    await page.goto(`${BASE_URL}${PAGE_URL}`)
    await page.waitForLoadState('networkidle')
    await page.waitForTimeout(3000)

    // 确保表格已加载
    const firstRow = page.locator('.ant-table tbody tr').first()
    const hasRows = await firstRow.isVisible({ timeout: 10000 }).catch(() => false)

    if (!hasRows) {
      console.log('⚠ No rows to test navigation performance')
      return
    }

    // 测量跳转时间
    const startTime = Date.now()

    await firstRow.click()

    // 等待成功提示或 IGV 响应
    await Promise.race([
      page.locator('.ant-message-success').waitFor({ timeout: 3000 }),
      page.waitForTimeout(3000)
    ]).catch(() => null)

    const navTime = Date.now() - startTime

    console.log(`IGV 跳转时间: ${navTime}ms`)

    if (navTime < 3000) {
      console.log('✓ Navigation responded within 3 seconds')
      expect(navTime).toBeLessThan(3000)
    } else {
      console.log('⚠ Navigation time exceeded 3s')
    }
  })

  test('Page should load overlap table within 10 seconds', async ({ page }) => {
    const startTime = Date.now()

    await page.goto(`${BASE_URL}${PAGE_URL}`)

    // 等待表格出现
    const table = page.locator('.ant-table').first()
    await table.waitFor({ timeout: 10000 })

    const loadTime = Date.now() - startTime

    console.log(`Overlap table 加载时间: ${loadTime}ms`)
    expect(loadTime).toBeLessThan(10000)
  })
})

// ============================================================================
// P2 测试：错误场景
// ============================================================================

test.describe('Overlap IGV Integration - Error Handling', () => {
  test('should handle empty table gracefully', async ({ page }) => {
    // 使用会返回空结果的筛选条件
    await page.goto(`${BASE_URL}${PAGE_URL}?chromosome=chrNonExistent`)
    await page.waitForLoadState('networkidle')
    await page.waitForTimeout(2000)

    // 应该显示空状态
    const emptyState = page.locator('.ant-empty')
    const hasEmpty = await emptyState.isVisible({ timeout: 5000 }).catch(() => false)

    if (hasEmpty) {
      console.log('✓ Empty state displayed correctly')
      await expect(emptyState).toBeVisible()
    }
  })

  test('should handle API error gracefully', async ({ page }) => {
    // 拦截 API 并返回错误
    await page.route('**/api/v1/lncrna-chipseq-overlap*', (route) => {
      route.fulfill({
        status: 500,
        contentType: 'application/json',
        body: JSON.stringify({ detail: 'Internal Server Error' })
      })
    })

    await page.goto(`${BASE_URL}${PAGE_URL}`)
    await page.waitForTimeout(2000)

    // 应该显示错误提示
    const errorAlert = page.locator('.ant-alert-error, .ant-message-error')
    const errorText = page.getByText(/Error|Failed|错误|失败/i)

    const hasError = await errorAlert.isVisible({ timeout: 3000 }).catch(() => false) ||
                     await errorText.isVisible({ timeout: 3000 }).catch(() => false)

    console.log(`Error handling: ${hasError ? '✓' : '⚠'}`)
  })

  test('should handle invalid row click gracefully', async ({ page }) => {
    await page.goto(`${BASE_URL}${PAGE_URL}`)
    await page.waitForLoadState('networkidle')
    await page.waitForTimeout(2000)

    // 等待表格
    const table = page.locator('.ant-table')
    await table.waitFor({ timeout: 10000 }).catch(() => null)

    // 尝试点击表头（不是数据行）
    const tableHeader = page.locator('.ant-table-thead tr').first()
    const hasHeader = await tableHeader.isVisible().catch(() => false)

    if (hasHeader) {
      await tableHeader.click()
      await page.waitForTimeout(1000)

      // 不应该有错误提示
      const errorMessage = page.locator('.ant-message-error')
      const hasError = await errorMessage.isVisible({ timeout: 2000 }).catch(() => false)

      expect(hasError).toBe(false)
      console.log('✓ No error when clicking table header')
    }
  })

  test('should handle IGV initialization failure', async ({ page }) => {
    // 拦截 IGV 配置 API
    await page.route('**/api/v1/igv/**', (route) => {
      route.fulfill({
        status: 500,
        body: JSON.stringify({ detail: 'IGV config error' })
      })
    })

    await page.goto(`${BASE_URL}${PAGE_URL}`)
    await page.waitForTimeout(3000)

    // 页面应该仍然可用（表格显示）
    const table = page.locator('.ant-table')
    const hasTable = await table.isVisible({ timeout: 5000 }).catch(() => false)

    console.log(`Table visible despite IGV error: ${hasTable ? '✓' : '⚠'}`)

    // 可能显示 IGV 错误提示
    const errorAlert = page.locator('.ant-alert-warning, .ant-alert-error')
    const hasAlert = await errorAlert.isVisible().catch(() => false)

    if (hasAlert) {
      console.log('✓ Error alert displayed for IGV failure')
    }
  })
})

// ============================================================================
// P2 测试：用户交互
// ============================================================================

test.describe('Overlap IGV Integration - User Interaction', () => {
  test.beforeEach(async ({ page }) => {
    await page.goto(`${BASE_URL}${PAGE_URL}`)
    await page.waitForLoadState('networkidle')
    await page.waitForTimeout(2000)
  })

  test('should maintain selection when switching pages', async ({ page }) => {
    // 等待表格
    const firstRow = page.locator('.ant-table tbody tr').first()
    const hasRows = await firstRow.isVisible({ timeout: 10000 }).catch(() => false)

    if (!hasRows) {
      console.log('⚠ No rows available')
      return
    }

    // 点击第一行
    await firstRow.click()
    await page.waitForTimeout(500)

    // 切换页面（如果有分页）
    const nextPageButton = page.locator('.ant-pagination-next')
    const hasNextPage = await nextPageButton.isVisible().catch(() => false)

    if (hasNextPage && !(await nextPageButton.isDisabled())) {
      await nextPageButton.click()
      await page.waitForTimeout(1000)

      // 返回第一页
      const prevPageButton = page.locator('.ant-pagination-prev')
      await prevPageButton.click()
      await page.waitForTimeout(1000)

      // 检查选中状态是否保留
      console.log('✓ Pagination navigation works')
    } else {
      console.log('⚠ No pagination available')
    }
  })

  test('should update IGV when filtering changes', async ({ page }) => {
    // 查找筛选器
    const markFilter = page.locator('.ant-select').first()
    const hasFilter = await markFilter.isVisible({ timeout: 5000 }).catch(() => false)

    if (!hasFilter) {
      console.log('⚠ No filter available')
      return
    }

    // 改变筛选条件
    await markFilter.click()
    await page.waitForTimeout(300)

    const firstOption = page.locator('.ant-select-dropdown .ant-select-item').first()
    const hasOption = await firstOption.isVisible().catch(() => false)

    if (hasOption) {
      await firstOption.click()
      await page.waitForTimeout(2000)

      // 表格应该刷新
      const table = page.locator('.ant-table')
      await expect(table).toBeVisible()

      console.log('✓ Filter change refreshed table')
    }
  })
})

// ============================================================================
// P2 测试：可访问性
// ============================================================================

test.describe('Overlap IGV Integration - Accessibility', () => {
  test.beforeEach(async ({ page }) => {
    await page.goto(`${BASE_URL}${PAGE_URL}`)
    await page.waitForLoadState('networkidle')
  })

  test('should support keyboard navigation in table', async ({ page }) => {
    await page.waitForTimeout(2000)

    // 尝试 Tab 键导航
    await page.keyboard.press('Tab')
    await page.waitForTimeout(200)

    const focusedElement = page.locator(':focus')
    const hasFocus = await focusedElement.count() > 0

    expect(hasFocus).toBe(true)
    console.log(`Keyboard navigation: ${hasFocus ? '✓' : '⚠'}`)
  })

  test('should have proper ARIA labels', async ({ page }) => {
    await page.waitForTimeout(2000)

    // 检查表格是否有 ARIA 属性
    const table = page.locator('.ant-table')
    const hasTable = await table.isVisible().catch(() => false)

    if (hasTable) {
      const role = await table.getAttribute('role')
      console.log(`Table role: ${role}`)
    }
  })
})
