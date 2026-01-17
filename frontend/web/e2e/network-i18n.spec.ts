import { test, expect, type Page } from '@playwright/test'

/**
 * Network 页面国际化 E2E 测试
 *
 * 测试场景：
 * 1. 页面标题和描述切换
 * 2. Select placeholder 切换
 * 3. 按钮文本切换
 * 4. 过滤器文本切换
 * 5. 物种名称切换
 * 6. 布局选择器选项切换
 */

// 辅助函数：通过 localStorage 切换语言（更可靠）
async function switchLanguageViaStorage(page: Page, language: 'zh-CN' | 'en') {
  // 直接设置 localStorage
  await page.evaluate((lang) => {
    localStorage.setItem('i18n_lang', lang)
  }, language)

  // 刷新页面以应用语言变更
  await page.reload()
  await page.waitForLoadState('networkidle')
}

// 辅助函数：通过 UI 切换语言（用于专门测试语言切换UI的场景）
async function switchLanguageViaUI(page: Page, language: 'zh-CN' | 'en') {
  const targetLang = language === 'zh-CN' ? '简体中文' : 'English'

  // 找到语言选择器
  const languageSelector = page.locator('.ant-layout-header .ant-select').first()
  const currentLangText = await languageSelector.locator('.ant-select-content-value').textContent()

  // 如果已经是目标语言，跳过
  if (currentLangText?.includes(targetLang)) {
    return
  }

  // 点击语言选择器
  await languageSelector.click()

  // 等待下拉菜单出现
  await page.waitForSelector('.ant-select-dropdown:visible')

  // 点击目标语言
  await page.getByText(targetLang, { exact: false }).click()

  // 等待语言切换生效
  await page.waitForTimeout(1000)
}

test.describe('Network 页面国际化测试', () => {
  test.beforeEach(async ({ page }) => {
    // 访问 Network 页面
    await page.goto('/network')

    // 等待页面加载完成
    await page.waitForLoadState('networkidle')

    // 确保切换到中文（通过 localStorage，更可靠）
    await switchLanguageViaStorage(page, 'zh-CN')
  })

  test('Test 1: 页面标题和描述切换', async ({ page }) => {
    // 检查中文标题
    await expect(page.getByRole('heading', { name: '网络可视化', level: 1 })).toBeVisible()

    // 检查中文描述
    await expect(page.getByText('根据疾病-Ontology组合构建lncRNA调控网络（支持多物种对比，最多4个）')).toBeVisible()

    // 切换到英文（通过 localStorage）
    await switchLanguageViaStorage(page, 'en')

    // 检查英文标题
    await expect(page.getByRole('heading', { name: 'Network Visualization', level: 1 })).toBeVisible()

    // 检查英文描述
    await expect(page.getByText('Build lncRNA regulatory networks based on Disease-Ontology combinations (supports multi-species comparison, up to 4)')).toBeVisible()

    // 切回中文
    await switchLanguageViaStorage(page, 'zh-CN')

    // 验证中文标题再次显示
    await expect(page.getByRole('heading', { name: '网络可视化', level: 1 })).toBeVisible()
  })

  test('Test 2: Select placeholder 切换', async ({ page }) => {
    // 注意：默认情况下物种选择器已选中"人类"
    // 检查其他未选中的选择器的 placeholder
    await expect(page.getByText('选择疾病')).toBeVisible()
    await expect(page.getByText('选择Ontology')).toBeVisible()

    // 检查物种选择器中的选中项文本
    await expect(page.locator('.ant-select-selection-item').filter({ hasText: '人类' })).toBeVisible()

    // 切换到英文
    await switchLanguageViaStorage(page, 'en')

    // 检查英文 placeholder
    await expect(page.getByText('Select disease')).toBeVisible()
    await expect(page.getByText('Select Ontology')).toBeVisible()

    // 也检查物种选择器中的选中项文本是否切换为 Human
    await expect(page.locator('.ant-select-selection-item').filter({ hasText: 'Human' })).toBeVisible()
  })

  test('Test 3: 按钮文本切换', async ({ page }) => {
    // 检查中文按钮
    await expect(page.getByRole('button', { name: '查询网络' })).toBeVisible()

    // 切换到英文
    await switchLanguageViaStorage(page, 'en')

    // 检查英文按钮
    await expect(page.getByRole('button', { name: 'Query Network' })).toBeVisible()

    // 切回中文
    await switchLanguageViaStorage(page, 'zh-CN')

    // 验证中文按钮再次显示
    await expect(page.getByRole('button', { name: '查询网络' })).toBeVisible()
  })

  test('Test 4: 物种选中项文本切换', async ({ page }) => {
    // 验证默认选中的物种名称会随语言切换而改变
    // 检查中文选中项
    await expect(page.locator('.ant-select-selection-item').filter({ hasText: '人类' })).toBeVisible()

    // 切换到英文
    await switchLanguageViaStorage(page, 'en')

    // 检查英文选中项
    await expect(page.locator('.ant-select-selection-item').filter({ hasText: 'Human' })).toBeVisible()

    // 切回中文
    await switchLanguageViaStorage(page, 'zh-CN')

    // 再次检查中文选中项
    await expect(page.locator('.ant-select-selection-item').filter({ hasText: '人类' })).toBeVisible()
  })

  test('Test 5: 标签文本切换', async ({ page }) => {
    // 检查中文标签
    await expect(page.getByText('物种:', { exact: false })).toBeVisible()
    await expect(page.getByText('疾病:', { exact: false })).toBeVisible()
    await expect(page.getByText('Ontology:', { exact: false })).toBeVisible()

    // 切换到英文
    await switchLanguageViaStorage(page, 'en')

    // 检查英文标签
    await expect(page.getByText('Species:', { exact: false })).toBeVisible()
    await expect(page.getByText('Disease:', { exact: false })).toBeVisible()
    await expect(page.getByText('Ontology:', { exact: false })).toBeVisible()
  })

  test('Test 6: 持久化测试 - 刷新页面保持语言', async ({ page }) => {
    // 切换到英文
    await switchLanguageViaStorage(page, 'en')

    // 验证英文标题
    await expect(page.getByRole('heading', { name: 'Network Visualization', level: 1 })).toBeVisible()

    // 刷新页面
    await page.reload()
    await page.waitForLoadState('networkidle')

    // 验证语言仍然是英文
    await expect(page.getByRole('heading', { name: 'Network Visualization', level: 1 })).toBeVisible()

    // 切回中文
    await switchLanguageViaStorage(page, 'zh-CN')

    // 刷新页面
    await page.reload()
    await page.waitForLoadState('networkidle')

    // 验证语言是中文
    await expect(page.getByRole('heading', { name: '网络可视化', level: 1 })).toBeVisible()
  })
})
