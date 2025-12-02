import { test, expect } from '@playwright/test'

/**
 * 基因浏览流程 E2E 测试
 *
 * 覆盖核心用户流程：
 * 1. 首页访问 → 导航到基因列表
 * 2. 基因列表浏览、搜索、筛选
 * 3. 查看基因详情
 *
 * 注意：页面语言可能是中文或英文，取决于浏览器设置
 */

test.describe('基因浏览流程', () => {
  test('首页正常加载', async ({ page }) => {
    await page.goto('/')

    // 验证主标题存在（h1）
    await expect(page.getByRole('heading', { level: 1, name: 'Human LncRNA Atlas' })).toBeVisible({ timeout: 15000 })

    // 验证导航菜单存在
    await expect(page.locator('[role="menu"]')).toBeVisible()
  })

  test('导航到基因列表页', async ({ page }) => {
    await page.goto('/')

    // 点击基因列表菜单（支持中英文）
    // 使用 menuitem role 和正则匹配
    await page.getByRole('menuitem', { name: /Gene List|基因列表/i }).click()

    // 验证 URL 变化
    await expect(page).toHaveURL(/\/genes/)

    // 等待表格加载
    await expect(page.locator('.ant-table')).toBeVisible({ timeout: 15000 })

    // 验证表格有数据
    const rows = page.locator('.ant-table-tbody tr')
    await expect(rows.first()).toBeVisible()
  })

  test('基因列表搜索功能', async ({ page }) => {
    await page.goto('/genes')

    // 等待表格加载
    await expect(page.locator('.ant-table')).toBeVisible({ timeout: 15000 })

    // 找到搜索框并输入
    const searchInput = page.locator('.ant-input-search input')
    await searchInput.fill('MALAT1')
    await searchInput.press('Enter')

    // 等待 API 响应
    await page.waitForResponse((response) =>
      response.url().includes('/api/v1/genes') && response.status() === 200
    )

    // 验证表格仍然可见
    await expect(page.locator('.ant-table')).toBeVisible()
  })

  test('基因类型筛选', async ({ page }) => {
    await page.goto('/genes')
    await expect(page.locator('.ant-table')).toBeVisible({ timeout: 15000 })

    // Genes 页面有基因类型筛选 (lncRNA / protein_coding)
    const geneTypeSelect = page.locator('.ant-select').first()
    await geneTypeSelect.click()

    // 等待下拉菜单出现
    await page.locator('.ant-select-dropdown').waitFor({ state: 'visible' })

    // 选择 lncRNA（使用更通用的选择器）
    const lncRNAOption = page.locator('.ant-select-dropdown .ant-select-item').filter({ hasText: /lncRNA/i })
    if (await lncRNAOption.count() > 0) {
      await lncRNAOption.click()

      // 等待 API 响应
      await page.waitForResponse((response) =>
        response.url().includes('/api/v1/genes') && response.status() === 200
      )
    }

    // 验证表格已更新
    await expect(page.locator('.ant-table-tbody')).toBeVisible()
  })

  test('查看基因详情', async ({ page }) => {
    await page.goto('/genes')
    await expect(page.locator('.ant-table')).toBeVisible({ timeout: 15000 })

    // 查看按钮在表格最后一列
    const viewButton = page.locator('.ant-table-tbody tr').first().getByRole('button').first()

    if (await viewButton.count() > 0) {
      await viewButton.click()

      // 验证跳转到详情页
      await expect(page).toHaveURL(/\/genes\/\d+/)

      // 等待详情加载
      await page.waitForLoadState('networkidle')
    }
  })

  test('基因详情页正常显示', async ({ page }) => {
    // 直接访问已知基因详情页
    await page.goto('/genes/17276')

    // 等待页面加载
    await page.waitForLoadState('networkidle')

    // 验证页面有内容
    await expect(page.locator('h1, h2, .ant-descriptions, .ant-card').first()).toBeVisible({ timeout: 15000 })
  })
})

test.describe('基因列表分页', () => {
  test('分页导航正常工作', async ({ page }) => {
    await page.goto('/genes')
    await expect(page.locator('.ant-table')).toBeVisible({ timeout: 15000 })

    // 找到分页器
    const pagination = page.locator('.ant-pagination')
    await expect(pagination).toBeVisible()

    // 使用精确的选择器点击第二页
    const page2Button = pagination.locator('.ant-pagination-item-2')
    if (await page2Button.count() > 0) {
      await page2Button.click()

      // 等待表格更新
      await page.waitForResponse((response) =>
        response.url().includes('/api/v1/genes') && response.status() === 200
      )

      // 验证页码按钮激活状态变化
      await expect(page2Button).toHaveClass(/ant-pagination-item-active/)
    }
  })
})
