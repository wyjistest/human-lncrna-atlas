import { test, expect } from '@playwright/test'

/**
 * Smoke: Admin Materialized Views page should render with mocked
 * /api/v1/admin/materialized-views/status.
 *
 * This test is intentionally fully mocked to keep CI fast and independent of
 * backend/DB state.
 */

const PAGE_URL = '/admin/materialized-views'

function buildMockMaterializedViewsStatusResponse() {
  return {
    status: 'success',
    supported: true,
    database_backend: 'postgresql',
    checked_at: '2026-03-19T04:00:00Z',
    refresh_lock_available: true,
    views: [
      {
        name: 'mv_lncrna_chipseq_overlaps',
        exists: true,
        populated: true,
        rows_estimate: 1234,
        total_size: '16 kB',
        total_size_bytes: 16384,
        heap_size: '8 kB',
        heap_size_bytes: 8192,
        index_size: '8 kB',
        index_size_bytes: 8192,
        last_analyze_at: '2026-03-19T03:55:00Z',
        last_autoanalyze_at: '2026-03-19T03:57:00Z',
        last_stats_at: '2026-03-19T03:57:00Z',
        last_stats_source: 'autoanalyze',
        stats_age_seconds: 180,
        health_status: 'healthy',
        severity: 'info',
        recommended_action: null,
        affects_features: ['Overlap compare'],
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

    await page.goto(PAGE_URL)
    await page.waitForLoadState('domcontentloaded')

    await expect(page.getByTestId('admin-materialized-views-page')).toBeVisible({ timeout: 15000 })

    const lock = page.getByTestId('admin-materialized-views-refresh-lock')
    await expect(lock).toBeVisible({ timeout: 15000 })
    await expect(lock).toContainText('available')

    const backend = page.getByTestId('admin-materialized-views-backend')
    await expect(backend).toContainText('postgresql')

    await expect(page.getByTestId('admin-materialized-views-refresh-status')).toBeVisible({ timeout: 15000 })
    await expect(page.getByTestId('admin-materialized-views-refresh-views')).toBeVisible({ timeout: 15000 })
    await expect(page.getByTestId('admin-materialized-views-runtime')).toContainText('postgresql-supported')

    const status = page.getByTestId('admin-materialized-views-status')
    await expect(status).toBeVisible({ timeout: 15000 })
    await expect(status).toContainText('mv_lncrna_chipseq_overlaps')
    await expect(status).toContainText('16 kB')
    await expect(status).toContainText('Heap: 8 kB')
    await expect(status).toContainText('Source: autoanalyze')
    await expect(status).toContainText('healthy')
    await expect(status).toContainText('No action needed.')
  })
})
