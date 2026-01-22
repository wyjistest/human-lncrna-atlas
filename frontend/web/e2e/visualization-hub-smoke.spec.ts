import { test, expect } from '@playwright/test'

/**
 * Smoke: Visualization Hub page should render (no backend/DB required).
 *
 * This test is intentionally independent of any API calls so it can run in the
 * same fully-static (vite preview) environment as other e2e-smoke specs.
 */

const PAGE_URL = '/visualization'

test.describe('Visualization Hub - smoke', () => {
  test('renders hub cards', async ({ page }) => {
    await page.goto(PAGE_URL)
    await page.waitForLoadState('domcontentloaded')

    await expect(page.getByTestId('visualization-page')).toBeVisible({ timeout: 15000 })
    const cardCount = await page.getByTestId('visualization-card').count()
    expect(cardCount).toBeGreaterThanOrEqual(5)
  })
})
