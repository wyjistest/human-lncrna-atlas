import { test, expect } from '@playwright/test'

const PAGE_URL = '/chipseq-compare'

test.describe('ChIP-seq Compare availability smoke', () => {
  test('renders unavailable state instead of mock charts', async ({ page }) => {
    await page.goto(PAGE_URL)
    await page.waitForLoadState('domcontentloaded')

    await expect(page.getByTestId('chipseq-compare-page')).toBeVisible({ timeout: 15000 })
    await expect(page.getByTestId('chipseq-compare-unavailable')).toBeVisible({ timeout: 15000 })
    await expect(page.getByTestId('radar-compare-chart')).toHaveCount(0)
  })
})
