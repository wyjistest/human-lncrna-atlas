import { test, expect } from '@playwright/test'

const PAGE_URL = '/chipseq-compare'

test.describe('ChIP-seq Compare - mocked smoke', () => {
  test('renders global compare section and default radar chart', async ({ page }) => {
    await page.goto(PAGE_URL)
    await page.waitForLoadState('domcontentloaded')

    await expect(page.getByTestId('chipseq-compare-page')).toBeVisible({ timeout: 15000 })
    await expect(page.getByTestId('radar-compare-chart')).toBeVisible({ timeout: 15000 })
  })
})

