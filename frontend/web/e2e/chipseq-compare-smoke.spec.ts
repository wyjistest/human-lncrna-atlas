import { test, expect } from '@playwright/test'

const PAGE_URL = '/chipseq-compare'

test.describe('ChIP-seq Compare availability smoke', () => {
  test('renders unavailable state instead of mock charts', async ({ page }) => {
    const unexpectedApiCalls: string[] = []

    await page.route(/\/api\/v1\/(chipseq|features\/chipseq)\//, async (route) => {
      unexpectedApiCalls.push(route.request().url())
      await route.abort()
    })

    await page.goto(PAGE_URL)
    await page.waitForLoadState('domcontentloaded')

    await expect(page.getByTestId('chipseq-compare-page')).toBeVisible({ timeout: 15000 })
    await expect(page.getByTestId('chipseq-compare-unavailable')).toBeVisible({ timeout: 15000 })
    await expect(page.getByText('Global compare is not available yet')).toBeVisible({ timeout: 15000 })
    await expect(page.getByText('This page no longer shows mock data.')).toBeVisible({ timeout: 15000 })
    await expect(page.getByTestId('chipseq-compare-supported-paths')).toBeVisible({ timeout: 15000 })
    await expect(page.getByTestId('chipseq-compare-gene-search')).toBeVisible({ timeout: 15000 })
    await expect(page.getByTestId('chipseq-compare-genes-link')).toBeVisible({ timeout: 15000 })
    await expect(page.getByTestId('chipseq-compare-overlap-link')).toBeVisible({ timeout: 15000 })
    await expect(page.getByTestId('chipseq-compare-analysis-link')).toBeVisible({ timeout: 15000 })
    await expect(page.getByTestId('radar-compare-chart')).toHaveCount(0)
    expect(unexpectedApiCalls).toEqual([])
  })
})
