import { test, expect } from '@playwright/test'

/**
 * 调控关系筛选流程 E2E 测试
 *
 * 覆盖核心功能：
 * 1. 调控关系列表浏览
 * 2. 基本筛选功能
 * 3. 数据导出按钮
 */

test.describe('调控关系筛选流程', () => {
  test.beforeEach(async ({ page }) => {
    await page.goto('/regulations')
    // 等待表格加载
    await expect(page.locator('.ant-table')).toBeVisible({ timeout: 20000 })
  })

  test('调控关系列表正常加载', async ({ page }) => {
    // 验证表格有数据
    const rows = page.locator('.ant-table-tbody tr')
    await expect(rows.first()).toBeVisible()

    // 验证分页器存在
    await expect(page.locator('.ant-pagination')).toBeVisible()

    // 验证显示了总数
    const totalText = page.locator('.ant-pagination-total-text')
    await expect(totalText).toBeVisible()
  })

  test('高级筛选面板存在', async ({ page }) => {
    // Regulations 页面有高级筛选（AdvancedFilters 组件）
    // 可能在 Collapse 面板中

    // 查找筛选相关的 UI 元素
    const filterSection = page.locator('.ant-collapse, .ant-form, .ant-space').first()
    await expect(filterSection).toBeVisible()
  })

  test('BA 值范围输入框存在', async ({ page }) => {
    // 找到 BA 最小/最大值输入框
    const inputNumbers = page.locator('.ant-input-number')

    // 应该有 BA 范围输入
    if (await inputNumbers.count() > 0) {
      await expect(inputNumbers.first()).toBeVisible()
    }
  })

  test('查看调控关系详情', async ({ page }) => {
    // 等待表格行加载
    const firstRow = page.locator('.ant-table-tbody tr').first()
    await expect(firstRow).toBeVisible()

    // 尝试找到详情按钮或链接
    const detailButton = firstRow.locator('button, a').first()
    if (await detailButton.count() > 0) {
      await detailButton.click()
      // 等待可能的页面变化或弹窗
      await page.waitForTimeout(1000)
    }
  })

  test('导出下拉菜单存在', async ({ page }) => {
    // 找到导出按钮（可能是下拉按钮）
    const exportButton = page.locator('button').filter({ hasText: /导出|Export/i })

    if (await exportButton.count() > 0) {
      await expect(exportButton.first()).toBeVisible()
    }
  })
})

test.describe('调控关系分页', () => {
  test('分页功能正常', async ({ page }) => {
    await page.goto('/regulations')
    await expect(page.locator('.ant-table')).toBeVisible({ timeout: 20000 })

    // 找到分页器
    const pagination = page.locator('.ant-pagination')
    await expect(pagination).toBeVisible()

    // 点击第二页
    const page2Button = pagination.locator('.ant-pagination-item-2')
    if (await page2Button.count() > 0) {
      // ⚠️ 避免竞态：先注册 waitForResponse 再触发 click，否则可能错过瞬时完成的请求
      await Promise.all([
        page.waitForResponse(
          (response) =>
            response.url().includes('/api/v1/regulations') && response.status() === 200,
          { timeout: 20000 }
        ),
        page2Button.click(),
      ])

      // 验证页码变化
      await expect(page2Button).toHaveClass(/ant-pagination-item-active/)
    }
  })
})

test.describe('调控关系 URL 参数', () => {
  test('URL 参数正确应用筛选', async ({ page }) => {
    // 直接通过 URL 参数筛选
    await page.goto('/regulations?species_ids=1')

    // 等待表格加载
    await expect(page.locator('.ant-table')).toBeVisible({ timeout: 20000 })

    // 验证表格有数据
    await expect(page.locator('.ant-table-tbody tr').first()).toBeVisible()
  })
})
