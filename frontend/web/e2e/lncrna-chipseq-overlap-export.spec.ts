import { test, expect, type Page } from '@playwright/test'

const PAGE_URL = '/lncrna-chipseq-overlap'
const DOWNLOAD_TIMEOUT = 30000

// Helper: Apply chr22 filter
async function applyChr22Filter(page: Page): Promise<void> {
  // 通过标签定位 Chromosome Select（避免 placeholder 在选择后变化导致 locator 失效）
  const chrLabel = page.getByText(/^(Chromosome|染色体)[:：]$/i).first()
  const chrField = chrLabel.locator('..').locator('..')
  const chrSelect = chrField.locator('.ant-select').first()

  if (!(await chrSelect.count())) return

  // Select: showSearch=true，直接输入过滤
  await chrSelect.click()
  const dropdown = page.locator('.ant-select-dropdown:visible')
  await dropdown.waitFor({ state: 'visible', timeout: 5000 })

  await page.keyboard.type('chr22')
  await page.keyboard.press('Enter')

  await expect(chrSelect).toContainText(/chr22/i, { timeout: 10000 })
}

// Helper: Check if export button is visible
async function checkExportButtonVisible(page: Page): Promise<boolean> {
  const exportButton = page.locator('button').filter({ hasText: /导出|Export/ }).first()
  return await exportButton.count() > 0
}

// Helper: Click export and select format
async function clickExportFormat(page: Page, format: 'CSV' | 'BED'): Promise<void> {
  const exportGroup = page.locator('.ant-dropdown-button').filter({ hasText: /导出|Export/i }).first()
  const exportButtons = exportGroup.locator('button')

  if (format === 'BED') {
    // BED: click main button
    await exportButtons.first().click()
  } else {
    // CSV: click dropdown arrow, wait for menu, click CSV item
    await exportButtons.last().click()
    await page.waitForSelector('.ant-dropdown-menu:visible', { state: 'visible', timeout: 5000 })
    await page.locator('.ant-dropdown-menu:visible .ant-dropdown-menu-item').filter({ hasText: /CSV/i }).first().click()
  }
}

test.describe('lncRNA-ChIP-seq Overlap Export', () => {

  test.beforeEach(async ({ page }) => {
    await page.goto(PAGE_URL)
    await page.waitForLoadState('domcontentloaded')

    // 页面可能包含持续请求（例如 IGV 资源加载），避免 networkidle 卡死
    const exportBtn = page.locator('button').filter({ hasText: /导出|Export/i }).first()
    await exportBtn.waitFor({ state: 'visible', timeout: 20000 }).catch(() => {})
    await page.waitForTimeout(1000)
  })

  test('should display export button on page', async ({ page }) => {
    const buttonVisible = await checkExportButtonVisible(page)
    expect(buttonVisible).toBe(true)
  })

  test('should export overlaps as CSV', async ({ page }) => {
    await applyChr22Filter(page)

    // 捕获 window.open 调用（导出通过新标签页触发下载）
    let exportUrl = ''
    await page.exposeFunction('captureWindowOpen', (url: string) => {
      exportUrl = url
    })
    await page.evaluate(() => {
      window.open = function(url?: string | URL) {
        if (url) {
          ;(window as any).captureWindowOpen(url.toString())
        }
        return null
      }
    })

    await clickExportFormat(page, 'CSV')
    await expect.poll(() => exportUrl, { timeout: DOWNLOAD_TIMEOUT }).toContain('/api/v1/lncrna-chipseq-overlap/export')

    expect(exportUrl).toContain('format=csv')
    expect(exportUrl).toContain('chromosome=chr22')

    console.log('CSV export URL verified:', exportUrl)
  })

  test('should export overlaps as BED', async ({ page }) => {
    await applyChr22Filter(page)

    // 捕获 window.open 调用（导出通过新标签页触发下载）
    let exportUrl = ''
    await page.exposeFunction('captureWindowOpen', (url: string) => {
      exportUrl = url
    })
    await page.evaluate(() => {
      window.open = function(url?: string | URL) {
        if (url) {
          ;(window as any).captureWindowOpen(url.toString())
        }
        return null
      }
    })

    await clickExportFormat(page, 'BED')
    await expect.poll(() => exportUrl, { timeout: DOWNLOAD_TIMEOUT }).toContain('/api/v1/lncrna-chipseq-overlap/export')

    expect(exportUrl).toContain('format=bed')
    expect(exportUrl).toContain('chromosome=chr22')

    console.log('BED export URL verified:', exportUrl)
  })
})
