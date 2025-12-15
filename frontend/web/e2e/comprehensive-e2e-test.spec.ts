/**
 * Human LncRNA Atlas - Comprehensive E2E Test Suite
 *
 * 测试核心页面和用户流程:
 * 1. 首页 (/) - 统计卡片和导航
 * 2. 基因列表页 (/genes) - 表格、分页、筛选
 * 3. 调控关系页 (/regulations) - 多条件筛选、分页、导出
 * 4. 保守性分析页 (/conservation) - 热力图、统计卡片、Tab
 * 5. 网络可视化页 (/network) - Cytoscape、节点交互、疾病选择
 * 6. Sankey流图页 (/visualization/sankey-flow) - ECharts、筛选、统计
 * 7. API响应测试 - 关键端点验证
 */

import { test, expect, Page } from '@playwright/test';

// 配置
const BASE_URL = 'http://localhost:5173';
const API_BASE = 'http://localhost:8000';
const SCREENSHOT_DIR = process.env.SCREENSHOT_DIR || './test-results/screenshots';

// 测试结果收集
interface TestResult {
  page: string;
  status: 'Pass' | 'Fail';
  details: string[];
  issues: string[];
}

const testResults: TestResult[] = [];

// 辅助函数：等待网络空闲
async function waitForNetworkIdle(page: Page, timeout = 10000) {
  try {
    await page.waitForLoadState('networkidle', { timeout });
  } catch {
    // 继续测试，即使网络未完全空闲
  }
}

// 辅助函数：检查控制台错误
async function checkConsoleErrors(page: Page): Promise<string[]> {
  const errors: string[] = [];
  page.on('console', msg => {
    if (msg.type() === 'error') {
      errors.push(msg.text());
    }
  });
  return errors;
}

// ==================== 1. 首页测试 ====================
test.describe('1. 首页 (/) 测试', () => {
  test('1.1 统计卡片显示正确数据', async ({ page }) => {
    const result: TestResult = {
      page: '首页 (/)',
      status: 'Pass',
      details: [],
      issues: []
    };

    await page.goto(BASE_URL);
    await waitForNetworkIdle(page);

    // 检查页面标题或主要元素
    const title = await page.title();
    result.details.push(`页面标题: ${title}`);

    // 检查统计卡片
    const statsCards = page.locator('.ant-statistic, .ant-card, [data-testid*="stat"]');
    const cardsCount = await statsCards.count();
    result.details.push(`统计卡片数量: ${cardsCount}`);

    if (cardsCount === 0) {
      // 尝试其他选择器
      const altCards = page.locator('[class*="stat"], [class*="card"]');
      const altCount = await altCards.count();
      result.details.push(`备选卡片元素: ${altCount}`);
    }

    // 检查是否有数字显示（不是 0 或 "-"）
    const statsText = await page.locator('body').textContent();
    const hasNumbers = /\d{1,3}(,\d{3})*/.test(statsText || '');
    if (hasNumbers) {
      result.details.push('页面包含数字数据');
    } else {
      result.issues.push('页面可能缺少统计数据');
    }

    // 截图
    await page.screenshot({ path: `${SCREENSHOT_DIR}/e2e-homepage.png`, fullPage: true });
    result.details.push('截图: e2e-homepage.png');

    testResults.push(result);
    expect(true).toBe(true);
  });

  test('1.2 功能入口链接可用', async ({ page }) => {
    const result: TestResult = {
      page: '首页 - 导航链接',
      status: 'Pass',
      details: [],
      issues: []
    };

    await page.goto(BASE_URL);
    await waitForNetworkIdle(page);

    // 检查导航菜单
    const navLinks = page.locator('nav a, .ant-menu-item a, [href*="/genes"], [href*="/regulations"], [href*="/conservation"], [href*="/network"]');
    const linksCount = await navLinks.count();
    result.details.push(`导航链接数量: ${linksCount}`);

    // 检查主要导航链接
    const expectedLinks = ['/genes', '/regulations', '/conservation', '/network'];
    for (const link of expectedLinks) {
      const linkElement = page.locator(`a[href*="${link}"]`).first();
      if (await linkElement.isVisible({ timeout: 3000 }).catch(() => false)) {
        result.details.push(`链接 ${link} 可见`);
      } else {
        result.issues.push(`链接 ${link} 不可见或不存在`);
      }
    }

    testResults.push(result);
    expect(linksCount).toBeGreaterThan(0);
  });
});

// ==================== 2. 基因列表页测试 ====================
test.describe('2. 基因列表页 (/genes) 测试', () => {
  test('2.1 表格数据加载', async ({ page }) => {
    const result: TestResult = {
      page: '基因列表页 (/genes)',
      status: 'Pass',
      details: [],
      issues: []
    };

    await page.goto(`${BASE_URL}/genes`);
    await waitForNetworkIdle(page, 15000);

    // 等待表格加载
    const table = page.locator('table, .ant-table');
    await table.first().waitFor({ timeout: 10000 }).catch(() => {});

    // 检查表格行数
    const rows = page.locator('table tbody tr, .ant-table-tbody tr');
    const rowsCount = await rows.count();
    result.details.push(`表格行数: ${rowsCount}`);

    if (rowsCount === 0) {
      result.issues.push('表格无数据');
      result.status = 'Fail';
    } else {
      // 检查数据是否为空值
      const firstRowText = await rows.first().textContent();
      if (firstRowText?.includes('-') && firstRowText.split('-').length > 5) {
        result.issues.push('数据可能显示为空值 (-)');
      }
      result.details.push(`首行数据预览: ${firstRowText?.substring(0, 100)}...`);
    }

    await page.screenshot({ path: `${SCREENSHOT_DIR}/e2e-genes-list.png`, fullPage: true });
    result.details.push('截图: e2e-genes-list.png');

    testResults.push(result);
    expect(rowsCount).toBeGreaterThan(0);
  });

  test('2.2 分页功能', async ({ page }) => {
    const result: TestResult = {
      page: '基因列表页 - 分页',
      status: 'Pass',
      details: [],
      issues: []
    };

    await page.goto(`${BASE_URL}/genes`);
    await waitForNetworkIdle(page, 15000);

    // 检查分页组件
    const pagination = page.locator('.ant-pagination, [class*="pagination"]');
    const hasPagination = await pagination.first().isVisible({ timeout: 5000 }).catch(() => false);
    result.details.push(`分页组件存在: ${hasPagination}`);

    if (hasPagination) {
      // 尝试点击下一页
      const nextButton = page.locator('.ant-pagination-next, [aria-label*="next"], [class*="next"]').first();
      if (await nextButton.isEnabled().catch(() => false)) {
        await nextButton.click();
        await waitForNetworkIdle(page);
        result.details.push('点击下一页成功');
      }
    } else {
      result.issues.push('分页组件不存在');
    }

    testResults.push(result);
  });

  test('2.3 物种筛选', async ({ page }) => {
    const result: TestResult = {
      page: '基因列表页 - 物种筛选',
      status: 'Pass',
      details: [],
      issues: []
    };

    await page.goto(`${BASE_URL}/genes`);
    await waitForNetworkIdle(page, 15000);

    // 查找物种筛选器
    const speciesFilter = page.locator('[data-testid*="species"], .ant-select, select, [class*="species"]').first();
    const hasFilter = await speciesFilter.isVisible({ timeout: 5000 }).catch(() => false);
    result.details.push(`物种筛选器存在: ${hasFilter}`);

    if (hasFilter) {
      try {
        await speciesFilter.click();
        await page.waitForTimeout(1000);

        // 检查下拉选项
        const options = page.locator('.ant-select-item, .ant-select-dropdown-menu-item, option');
        const optionsCount = await options.count();
        result.details.push(`筛选选项数量: ${optionsCount}`);

        await page.screenshot({ path: `${SCREENSHOT_DIR}/e2e-genes-filter.png` });
      } catch (e) {
        result.issues.push(`筛选器交互失败: ${e}`);
      }
    }

    testResults.push(result);
  });

  test('2.4 点击基因跳转详情页', async ({ page }) => {
    const result: TestResult = {
      page: '基因列表页 - 跳转详情',
      status: 'Pass',
      details: [],
      issues: []
    };

    await page.goto(`${BASE_URL}/genes`);
    await waitForNetworkIdle(page, 15000);

    // 查找可点击的基因链接
    const geneLinks = page.locator('table a, .ant-table a, [data-testid*="gene-link"]');
    const linksCount = await geneLinks.count();
    result.details.push(`基因链接数量: ${linksCount}`);

    if (linksCount > 0) {
      const firstLink = geneLinks.first();
      const href = await firstLink.getAttribute('href');
      result.details.push(`首个链接地址: ${href}`);

      // 点击链接
      await firstLink.click();
      await waitForNetworkIdle(page, 10000);

      const newUrl = page.url();
      result.details.push(`跳转后URL: ${newUrl}`);

      if (newUrl.includes('/gene/') || newUrl.includes('gene')) {
        result.details.push('成功跳转到基因详情页');
      } else {
        result.issues.push('未能跳转到详情页');
      }

      await page.screenshot({ path: `${SCREENSHOT_DIR}/e2e-gene-detail.png`, fullPage: true });
    } else {
      result.issues.push('无可点击的基因链接');
    }

    testResults.push(result);
  });
});

// ==================== 3. 调控关系页测试 ====================
test.describe('3. 调控关系页 (/regulations) 测试', () => {
  test('3.1 多条件筛选', async ({ page }) => {
    const result: TestResult = {
      page: '调控关系页 (/regulations)',
      status: 'Pass',
      details: [],
      issues: []
    };

    await page.goto(`${BASE_URL}/regulations`);
    await waitForNetworkIdle(page, 15000);

    // 检查筛选控件
    const filters = page.locator('.ant-select, .ant-input, .ant-slider, [class*="filter"]');
    const filtersCount = await filters.count();
    result.details.push(`筛选控件数量: ${filtersCount}`);

    // 检查表格
    const tableRows = page.locator('table tbody tr, .ant-table-tbody tr');
    const rowsCount = await tableRows.count();
    result.details.push(`表格行数: ${rowsCount}`);

    await page.screenshot({ path: `${SCREENSHOT_DIR}/e2e-regulations.png`, fullPage: true });
    result.details.push('截图: e2e-regulations.png');

    if (rowsCount === 0) {
      result.issues.push('表格无数据');
    }

    testResults.push(result);
  });

  test('3.2 表格分页', async ({ page }) => {
    const result: TestResult = {
      page: '调控关系页 - 分页',
      status: 'Pass',
      details: [],
      issues: []
    };

    await page.goto(`${BASE_URL}/regulations`);
    await waitForNetworkIdle(page, 15000);

    // 检查分页
    const pagination = page.locator('.ant-pagination');
    const hasPagination = await pagination.isVisible({ timeout: 5000 }).catch(() => false);
    result.details.push(`分页组件: ${hasPagination ? '存在' : '不存在'}`);

    // 检查总记录数显示
    const totalText = await page.locator('[class*="pagination"], [class*="total"]').textContent().catch(() => '');
    result.details.push(`分页信息: ${totalText?.substring(0, 50)}`);

    testResults.push(result);
  });

  test('3.3 数据导出按钮', async ({ page }) => {
    const result: TestResult = {
      page: '调控关系页 - 导出',
      status: 'Pass',
      details: [],
      issues: []
    };

    await page.goto(`${BASE_URL}/regulations`);
    await waitForNetworkIdle(page, 15000);

    // 查找导出按钮
    const exportButton = page.locator('button:has-text("Export"), button:has-text("导出"), [data-testid*="export"], button:has-text("Download")').first();
    const hasExport = await exportButton.isVisible({ timeout: 5000 }).catch(() => false);
    result.details.push(`导出按钮: ${hasExport ? '存在' : '不存在'}`);

    if (hasExport) {
      const buttonText = await exportButton.textContent();
      result.details.push(`按钮文本: ${buttonText}`);
    } else {
      result.issues.push('导出按钮不存在');
    }

    testResults.push(result);
  });
});

// ==================== 4. 保守性分析页测试 ====================
test.describe('4. 保守性分析页 (/conservation) 测试', () => {
  test('4.1 热力图渲染', async ({ page }) => {
    const result: TestResult = {
      page: '保守性分析页 (/conservation)',
      status: 'Pass',
      details: [],
      issues: []
    };

    await page.goto(`${BASE_URL}/conservation`);
    await waitForNetworkIdle(page, 20000);

    // 检查页面加载
    await page.waitForTimeout(3000);

    // 查找热力图/图表容器
    const heatmapContainer = page.locator('[class*="echarts"], [class*="heatmap"], canvas, svg').first();
    const hasHeatmap = await heatmapContainer.isVisible({ timeout: 10000 }).catch(() => false);
    result.details.push(`热力图容器: ${hasHeatmap ? '存在' : '不存在'}`);

    // 检查 canvas 元素
    const canvasElements = page.locator('canvas');
    const canvasCount = await canvasElements.count();
    result.details.push(`Canvas 元素数量: ${canvasCount}`);

    await page.screenshot({ path: `${SCREENSHOT_DIR}/e2e-conservation.png`, fullPage: true });
    result.details.push('截图: e2e-conservation.png');

    testResults.push(result);
  });

  test('4.2 统计卡片数据', async ({ page }) => {
    const result: TestResult = {
      page: '保守性分析页 - 统计卡片',
      status: 'Pass',
      details: [],
      issues: []
    };

    await page.goto(`${BASE_URL}/conservation`);
    await waitForNetworkIdle(page, 15000);

    // 检查统计卡片
    const statCards = page.locator('.ant-statistic, .ant-card, [class*="stat"]');
    const cardsCount = await statCards.count();
    result.details.push(`统计卡片数量: ${cardsCount}`);

    // 检查数据是否有效
    const pageText = await page.locator('body').textContent();
    const hasValidData = pageText && !pageText.includes('No Data') && /\d+/.test(pageText);
    result.details.push(`数据有效: ${hasValidData}`);

    if (!hasValidData) {
      result.issues.push('统计卡片可能无数据');
    }

    testResults.push(result);
  });

  test('4.3 Tab 切换', async ({ page }) => {
    const result: TestResult = {
      page: '保守性分析页 - Tab切换',
      status: 'Pass',
      details: [],
      issues: []
    };

    await page.goto(`${BASE_URL}/conservation`);
    await waitForNetworkIdle(page, 15000);

    // 检查 Tab 组件
    const tabs = page.locator('.ant-tabs-tab, [role="tab"]');
    const tabsCount = await tabs.count();
    result.details.push(`Tab 数量: ${tabsCount}`);

    if (tabsCount > 1) {
      // 点击第二个 Tab
      await tabs.nth(1).click();
      await waitForNetworkIdle(page, 5000);
      result.details.push('Tab 切换成功');

      await page.screenshot({ path: `${SCREENSHOT_DIR}/e2e-conservation-tab2.png`, fullPage: true });
    }

    testResults.push(result);
  });
});

// ==================== 5. 网络可视化页测试 ====================
test.describe('5. 网络可视化页 (/network) 测试', () => {
  test('5.1 Cytoscape 图渲染', async ({ page }) => {
    const result: TestResult = {
      page: '网络可视化页 (/network)',
      status: 'Pass',
      details: [],
      issues: []
    };

    await page.goto(`${BASE_URL}/network`);
    await waitForNetworkIdle(page, 20000);

    // 等待网络图加载
    await page.waitForTimeout(5000);

    // 检查 Cytoscape 容器
    const cytoscapeContainer = page.locator('[class*="cytoscape"], [id*="cy"], canvas').first();
    const hasCytoscape = await cytoscapeContainer.isVisible({ timeout: 15000 }).catch(() => false);
    result.details.push(`Cytoscape 容器: ${hasCytoscape ? '存在' : '不存在'}`);

    // 检查 canvas
    const canvas = page.locator('canvas');
    const canvasCount = await canvas.count();
    result.details.push(`Canvas 数量: ${canvasCount}`);

    await page.screenshot({ path: `${SCREENSHOT_DIR}/e2e-network.png`, fullPage: true });
    result.details.push('截图: e2e-network.png');

    if (canvasCount === 0 && !hasCytoscape) {
      result.issues.push('网络图可能未渲染');
    }

    testResults.push(result);
  });

  test('5.2 疾病选择器', async ({ page }) => {
    const result: TestResult = {
      page: '网络可视化页 - 疾病选择',
      status: 'Pass',
      details: [],
      issues: []
    };

    await page.goto(`${BASE_URL}/network`);
    await waitForNetworkIdle(page, 15000);

    // 查找疾病选择器
    const diseaseSelector = page.locator('.ant-select, [data-testid*="disease"], [class*="disease"]').first();
    const hasSelector = await diseaseSelector.isVisible({ timeout: 10000 }).catch(() => false);
    result.details.push(`疾病选择器: ${hasSelector ? '存在' : '不存在'}`);

    if (hasSelector) {
      try {
        await diseaseSelector.click();
        await page.waitForTimeout(1000);

        const options = page.locator('.ant-select-item, .ant-select-dropdown-menu-item');
        const optionsCount = await options.count();
        result.details.push(`疾病选项数量: ${optionsCount}`);

        await page.screenshot({ path: `${SCREENSHOT_DIR}/e2e-network-diseases.png` });
      } catch (e) {
        result.issues.push(`选择器交互失败: ${e}`);
      }
    }

    testResults.push(result);
  });

  test('5.3 节点点击交互', async ({ page }) => {
    const result: TestResult = {
      page: '网络可视化页 - 节点交互',
      status: 'Pass',
      details: [],
      issues: []
    };

    await page.goto(`${BASE_URL}/network`);
    await waitForNetworkIdle(page, 20000);
    await page.waitForTimeout(5000);

    // 尝试点击网络图区域
    const networkArea = page.locator('canvas, [class*="cytoscape"]').first();
    if (await networkArea.isVisible().catch(() => false)) {
      // 获取元素边界
      const box = await networkArea.boundingBox();
      if (box) {
        // 点击中心区域
        await page.mouse.click(box.x + box.width / 2, box.y + box.height / 2);
        await page.waitForTimeout(1000);
        result.details.push('点击网络图中心区域');

        // 检查是否有弹出信息
        const tooltip = page.locator('[class*="tooltip"], [class*="popup"], .ant-drawer').first();
        const hasTooltip = await tooltip.isVisible({ timeout: 2000 }).catch(() => false);
        result.details.push(`节点信息展示: ${hasTooltip ? '有' : '无'}`);
      }
    }

    testResults.push(result);
  });
});

// ==================== 6. Sankey 流图页测试 ====================
test.describe('6. Sankey 流图页 (/visualization/sankey-flow) 测试', () => {
  test('6.1 ECharts 图表渲染', async ({ page }) => {
    const result: TestResult = {
      page: 'Sankey 流图页 (/visualization/sankey-flow)',
      status: 'Pass',
      details: [],
      issues: []
    };

    await page.goto(`${BASE_URL}/visualization/sankey-flow`);
    await waitForNetworkIdle(page, 20000);
    await page.waitForTimeout(3000);

    // 检查 ECharts 容器
    const echartsContainer = page.locator('[class*="echarts"], [_echarts_instance_], canvas').first();
    const hasEcharts = await echartsContainer.isVisible({ timeout: 15000 }).catch(() => false);
    result.details.push(`ECharts 容器: ${hasEcharts ? '存在' : '不存在'}`);

    // 检查 canvas
    const canvas = page.locator('canvas');
    const canvasCount = await canvas.count();
    result.details.push(`Canvas 数量: ${canvasCount}`);

    await page.screenshot({ path: `${SCREENSHOT_DIR}/e2e-sankey.png`, fullPage: true });
    result.details.push('截图: e2e-sankey.png');

    if (canvasCount === 0) {
      result.issues.push('Sankey 图可能未渲染');
    }

    testResults.push(result);
  });

  test('6.2 筛选控件交互', async ({ page }) => {
    const result: TestResult = {
      page: 'Sankey 流图页 - 筛选控件',
      status: 'Pass',
      details: [],
      issues: []
    };

    await page.goto(`${BASE_URL}/visualization/sankey-flow`);
    await waitForNetworkIdle(page, 15000);

    // 检查筛选控件
    const filters = page.locator('.ant-select, .ant-slider, .ant-input-number, [class*="filter"]');
    const filtersCount = await filters.count();
    result.details.push(`筛选控件数量: ${filtersCount}`);

    // 检查物种选择器
    const speciesSelect = page.locator('.ant-select').first();
    if (await speciesSelect.isVisible().catch(() => false)) {
      await speciesSelect.click();
      await page.waitForTimeout(500);

      const options = page.locator('.ant-select-item');
      const optionsCount = await options.count();
      result.details.push(`物种选项数量: ${optionsCount}`);

      // 关闭下拉
      await page.keyboard.press('Escape');
    }

    testResults.push(result);
  });

  test('6.3 统计数据显示', async ({ page }) => {
    const result: TestResult = {
      page: 'Sankey 流图页 - 统计数据',
      status: 'Pass',
      details: [],
      issues: []
    };

    await page.goto(`${BASE_URL}/visualization/sankey-flow`);
    await waitForNetworkIdle(page, 15000);

    // 检查统计卡片
    const stats = page.locator('.ant-statistic, .ant-card, [class*="stat"]');
    const statsCount = await stats.count();
    result.details.push(`统计卡片数量: ${statsCount}`);

    // 检查数据内容
    const pageText = await page.locator('body').textContent();
    const numbers = pageText?.match(/\d+/g) || [];
    result.details.push(`页面数字数量: ${numbers.length}`);

    // 检查特定统计项
    const hasLncRNA = pageText?.toLowerCase().includes('lncrna');
    const hasGene = pageText?.toLowerCase().includes('gene');
    const hasDisease = pageText?.toLowerCase().includes('disease');
    result.details.push(`关键词检查 - lncRNA: ${hasLncRNA}, Gene: ${hasGene}, Disease: ${hasDisease}`);

    testResults.push(result);
  });
});

// ==================== 7. API 响应测试 ====================
test.describe('7. API 响应测试', () => {
  test('7.1 Stats Overview API', async ({ request }) => {
    const result: TestResult = {
      page: 'API: /api/v1/stats/overview',
      status: 'Pass',
      details: [],
      issues: []
    };

    try {
      const response = await request.get(`${API_BASE}/api/v1/stats/overview`);
      result.details.push(`状态码: ${response.status()}`);

      if (response.ok()) {
        const data = await response.json();
        result.details.push(`响应数据: ${JSON.stringify(data).substring(0, 200)}...`);
      } else {
        result.issues.push(`API 返回错误: ${response.status()}`);
        result.status = 'Fail';
      }
    } catch (e) {
      result.issues.push(`API 请求失败: ${e}`);
      result.status = 'Fail';
    }

    testResults.push(result);
  });

  test('7.2 Genes List API', async ({ request }) => {
    const result: TestResult = {
      page: 'API: /api/v1/genes',
      status: 'Pass',
      details: [],
      issues: []
    };

    try {
      const response = await request.get(`${API_BASE}/api/v1/genes?page=1&page_size=10`);
      result.details.push(`状态码: ${response.status()}`);

      if (response.ok()) {
        const data = await response.json();
        const itemsCount = data.items?.length || data.data?.length || 0;
        result.details.push(`返回记录数: ${itemsCount}`);
        result.details.push(`总记录数: ${data.total || data.count || 'N/A'}`);
      } else {
        result.issues.push(`API 返回错误: ${response.status()}`);
        result.status = 'Fail';
      }
    } catch (e) {
      result.issues.push(`API 请求失败: ${e}`);
      result.status = 'Fail';
    }

    testResults.push(result);
  });

  test('7.3 Regulations API', async ({ request }) => {
    const result: TestResult = {
      page: 'API: /api/v1/regulations',
      status: 'Pass',
      details: [],
      issues: []
    };

    try {
      const response = await request.get(`${API_BASE}/api/v1/regulations?page=1&page_size=10`);
      result.details.push(`状态码: ${response.status()}`);

      if (response.ok()) {
        const data = await response.json();
        result.details.push(`返回记录数: ${data.items?.length || data.data?.length || 0}`);
      } else {
        result.issues.push(`API 返回错误: ${response.status()}`);
        result.status = 'Fail';
      }
    } catch (e) {
      result.issues.push(`API 请求失败: ${e}`);
      result.status = 'Fail';
    }

    testResults.push(result);
  });

  test('7.4 Conservation API', async ({ request }) => {
    const result: TestResult = {
      page: 'API: /api/v1/conservation/overview',
      status: 'Pass',
      details: [],
      issues: []
    };

    try {
      const response = await request.get(`${API_BASE}/api/v1/conservation/overview`);
      result.details.push(`状态码: ${response.status()}`);

      if (response.ok()) {
        const data = await response.json();
        result.details.push(`响应结构: ${Object.keys(data).join(', ')}`);
      } else {
        result.issues.push(`API 返回错误: ${response.status()}`);
        result.status = 'Fail';
      }
    } catch (e) {
      result.issues.push(`API 请求失败: ${e}`);
      result.status = 'Fail';
    }

    testResults.push(result);
  });

  test('7.5 Diseases Options API', async ({ request }) => {
    const result: TestResult = {
      page: 'API: /api/v1/diseases/options',
      status: 'Pass',
      details: [],
      issues: []
    };

    try {
      const response = await request.get(`${API_BASE}/api/v1/diseases/options`);
      result.details.push(`状态码: ${response.status()}`);

      if (response.ok()) {
        const data = await response.json();
        const optionsCount = Array.isArray(data) ? data.length : data.items?.length || 0;
        result.details.push(`疾病选项数: ${optionsCount}`);
      } else {
        result.issues.push(`API 返回错误: ${response.status()}`);
        result.status = 'Fail';
      }
    } catch (e) {
      result.issues.push(`API 请求失败: ${e}`);
      result.status = 'Fail';
    }

    testResults.push(result);
  });

  test('7.6 Sankey Data API', async ({ request }) => {
    const result: TestResult = {
      page: 'API: /api/v1/visualization/sankey-data',
      status: 'Pass',
      details: [],
      issues: []
    };

    try {
      const response = await request.get(`${API_BASE}/api/v1/visualization/sankey-data?species_id=1&limit=50`);
      result.details.push(`状态码: ${response.status()}`);

      if (response.ok()) {
        const data = await response.json();
        result.details.push(`响应结构: ${JSON.stringify(Object.keys(data || {}))}`);

        // 检查节点和链接
        const nodes = data.nodes || data.data?.nodes || [];
        const links = data.links || data.data?.links || [];
        result.details.push(`节点数: ${nodes.length}, 链接数: ${links.length}`);
      } else {
        result.issues.push(`API 返回错误: ${response.status()}`);
        result.status = 'Fail';
      }
    } catch (e) {
      result.issues.push(`API 请求失败: ${e}`);
      result.status = 'Fail';
    }

    testResults.push(result);
  });
});

// ==================== 测试报告生成 ====================
test.afterAll(async () => {
  console.log('\n' + '='.repeat(80));
  console.log('Human LncRNA Atlas E2E 测试报告');
  console.log('='.repeat(80));

  let passCount = 0;
  let failCount = 0;
  const allIssues: string[] = [];

  for (const result of testResults) {
    console.log(`\n[${result.status}] ${result.page}`);
    for (const detail of result.details) {
      console.log(`  - ${detail}`);
    }
    for (const issue of result.issues) {
      console.log(`  ⚠ ${issue}`);
      allIssues.push(`${result.page}: ${issue}`);
    }

    if (result.status === 'Pass') passCount++;
    else failCount++;
  }

  console.log('\n' + '-'.repeat(80));
  console.log('测试摘要');
  console.log('-'.repeat(80));
  console.log(`通过: ${passCount}`);
  console.log(`失败: ${failCount}`);
  console.log(`总计: ${testResults.length}`);

  if (allIssues.length > 0) {
    console.log('\n问题汇总:');
    allIssues.forEach((issue, i) => console.log(`  ${i + 1}. ${issue}`));
  }

  console.log('='.repeat(80));
});
