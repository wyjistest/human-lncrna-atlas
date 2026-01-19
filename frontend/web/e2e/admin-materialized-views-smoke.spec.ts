import { test, expect } from '@playwright/test'

/**
 * Smoke: Admin Materialized Views page should render with mocked
 * /api/v1/admin/materialized-views/status.
 *
 * This test is intentionally fully mocked to keep CI fast and independent of
 * backend/DB state.
 */

const PAGE_URL = '/admin/materialized-views'
const BASE_URL = process.env.BASE_URL || 'http://localhost:5173'

function buildMockMaterializedViewsStatusResponse() {
  return {
    status: 'success',
    refresh_lock_available: true,
    views: [
      {
        name: 'mv_lncrna_chipseq_overlaps',
        exists: true,
        populated: true,
        rows_estimate: 1234,
        total_size: '16 kB',
      },
    ],
  }
}

test.describe('Admin Materialized Views - mocked smoke', () => {
  test('renders materialized views status table with mocked data', async ({ page }) => {
    await page.route('**/api/v1/admin/materialized-views/status*', async (route) => {
      await route.fulfill({
        status: 200,
        contentType: 'application/json',
        body: JSON.stringify(buildMockMaterializedViewsStatusResponse()),
      })
    })

    await page.goto(`${BASE_URL}${PAGE_URL}`)
    await page.waitForLoadState('domcontentloaded')

    await expect(page.getByTestId('admin-materialized-views-page')).toBeVisible({ timeout: 15000 })

    const lock = page.getByTestId('admin-materialized-views-refresh-lock')
    await expect(lock).toBeVisible({ timeout: 15000 })
    await expect(lock).toContainText('available')

    await expect(page.getByTestId('admin-materialized-views-refresh-status')).toBeVisible({ timeout: 15000 })
    await expect(page.getByTestId('admin-materialized-views-refresh-views')).toBeVisible({ timeout: 15000 })

    const status = page.getByTestId('admin-materialized-views-status')
    await expect(status).toBeVisible({ timeout: 15000 })
    await expect(status).toContainText('mv_lncrna_chipseq_overlaps')
    await expect(status).toContainText('16 kB')
  })
})
