import { test, expect, Download } from '@playwright/test'
import * as fs from 'fs'
import * as path from 'path'
import { fileURLToPath } from 'url'
import { dirname } from 'path'

const __filename = fileURLToPath(import.meta.url)
const __dirname = dirname(__filename)

const BASE_URL = 'http://localhost:5175'
const PAGE_URL = '/lncrna-chipseq-overlap'
const DOWNLOAD_TIMEOUT = 30000
const DOWNLOAD_DIR = path.join(__dirname, '../test-downloads')

// Helper: Apply chr22 filter
async function applyChr22Filter(page: any): Promise<void> {
  const chrSelector = page.locator('.ant-select').filter({ hasText: /Chromosome|染色体/i }).first()
  if (await chrSelector.count() > 0) {
    await chrSelector.click()
    await page.waitForTimeout(300)
    const chr22Option = page.locator('.ant-select-dropdown .ant-select-item').filter({ hasText: 'chr22' }).first()
    if (await chr22Option.count() > 0) {
      await chr22Option.click()
      await page.waitForTimeout(500)
    }
  }
}

// Helper: Check if export button is visible
async function checkExportButtonVisible(page: any): Promise<boolean> {
  const exportButton = page.locator('button').filter({ hasText: /导出|Export/ }).first()
  return await exportButton.count() > 0
}

// Helper: Click export and select format
// Note: Export uses window.open(), which we'll verify by checking the window.open call
async function clickExportFormat(page: any, format: 'CSV' | 'BED'): Promise<{ url: string }> {
  // Monitor window.open calls
  let exportUrl = ''
  await page.exposeFunction('captureWindowOpen', (url: string) => {
    console.log('window.open called with:', url)
    exportUrl = url
  })

  // Override window.open to capture the URL
  await page.evaluate(() => {
    const originalOpen = window.open
    window.open = function(url?: string | URL, target?: string, features?: string) {
      if (url) {
        (window as any).captureWindowOpen(url.toString())
      }
      return null
    }
  })

  if (format === 'BED') {
    // BED: click main button
    await page.locator('.ant-dropdown-button button').first().click()
  } else {
    // CSV: click dropdown arrow, wait for menu, click CSV item
    await page.locator('.ant-dropdown-button button').last().click()
    await page.waitForSelector('.ant-dropdown-menu', { state: 'visible', timeout: 5000 })
    await page.locator('.ant-dropdown-menu-item').filter({ hasText: /CSV/ }).first().click()
  }

  // Wait for window.open to be called
  await page.waitForTimeout(1000)

  return { url: exportUrl }
}

test.describe('lncRNA-ChIP-seq Overlap Export', () => {

  test.beforeEach(async ({ page }) => {
    // Setup download directory
    if (!fs.existsSync(DOWNLOAD_DIR)) {
      fs.mkdirSync(DOWNLOAD_DIR, { recursive: true })
    }

    await page.goto(`${BASE_URL}${PAGE_URL}`)
    await page.waitForLoadState('networkidle')
    await page.waitForTimeout(3000)
  })

  test('should display export button on page', async ({ page }) => {
    const buttonVisible = await checkExportButtonVisible(page)
    expect(buttonVisible).toBe(true)
  })

  test('should export overlaps as CSV', async ({ page }) => {
    await applyChr22Filter(page)

    const { url } = await clickExportFormat(page, 'CSV')

    // Verify URL is correct
    expect(url).toContain('/api/v1/lncrna-chipseq-overlap/export')
    expect(url).toContain('format=csv')
    expect(url).toContain('chromosome=chr22')

    // Verify URL format is valid
    expect(url).toMatch(/^https?:\/\//)

    console.log('CSV export URL verified:', url)
  })

  test('should export overlaps as BED', async ({ page }) => {
    await applyChr22Filter(page)

    const { url } = await clickExportFormat(page, 'BED')

    // Verify URL is correct
    expect(url).toContain('/api/v1/lncrna-chipseq-overlap/export')
    expect(url).toContain('format=bed')
    expect(url).toContain('chromosome=chr22')

    // Verify URL format is valid
    expect(url).toMatch(/^https?:\/\//)

    console.log('BED export URL verified:', url)
  })
})
