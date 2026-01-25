import { test, expect } from '@playwright/test'

/**
 * Smoke: Admin Cache Management page should render with mocked /api/v1/admin/cache/stats.
 *
 * This test is intentionally fully mocked to keep CI fast and independent of
 * backend/DB state.
 */

const PAGE_URL = '/admin/cache'

function buildMockCacheStatsResponse() {
  return {
    backend: 'memory',
    enabled: true,
    hits: 10,
    misses: 2,
    total_requests: 12,
    hit_rate_pct: 83.33,
    hit_rate: '83.33%',
    allowed_namespaces: ['stats', 'genes', 'export'],
    namespaces: {
      tracked: 2,
      limit: 10,
      top: [
        {
          namespace: 'stats',
          requests: 12,
          hits: 10,
          misses: 2,
          hit_rate_pct: 83.33,
          compute_count: 0,
          compute_avg_ms: 0,
          compute_max_ms: 0,
        },
      ],
    },
    keys: {
      tracked: 1,
      limit: 10,
      top: [
        {
          key: 'lncrna:stats:overview',
          namespace: 'stats',
          requests: 12,
          hits: 10,
          misses: 2,
          hit_rate_pct: 83.33,
          compute_count: 0,
          compute_avg_ms: 0,
          compute_max_ms: 0,
        },
      ],
    },
    memory: {
      size: 123,
      max_size: 1000,
      evictions: 0,
    },
  }
}

test.describe('Admin Cache - mocked smoke', () => {
  test('renders cache management page with mocked stats', async ({ page }) => {
    await page.route('**/api/v1/admin/cache/stats*', async (route) => {
      await route.fulfill({
        status: 200,
        contentType: 'application/json',
        body: JSON.stringify(buildMockCacheStatsResponse()),
      })
    })

    await page.goto(PAGE_URL)
    await page.waitForLoadState('domcontentloaded')

    await expect(page.getByTestId('admin-cache-page')).toBeVisible({ timeout: 15000 })
    await expect(page.getByTestId('admin-cache-refresh')).toBeVisible({ timeout: 15000 })
    await expect(page.getByTestId('admin-cache-reset-stats')).toBeVisible({ timeout: 15000 })
    await expect(page.getByTestId('admin-cache-invalidate-namespace')).toBeVisible({ timeout: 15000 })
    await expect(page.getByTestId('admin-cache-clear-cache')).toBeVisible({ timeout: 15000 })

    const backendCard = page.getByTestId('admin-cache-stat-backend')
    await expect(backendCard).toBeVisible({ timeout: 15000 })
    await expect(backendCard).toContainText('memory')

    const hitRateCard = page.getByTestId('admin-cache-stat-hit-rate')
    await expect(hitRateCard).toBeVisible({ timeout: 15000 })
    await expect(hitRateCard).toContainText('83.3%')

    const totalRequestsCard = page.getByTestId('admin-cache-stat-total-requests')
    await expect(totalRequestsCard).toBeVisible({ timeout: 15000 })
    await expect(totalRequestsCard).toContainText('12')

    const namespaces = page.getByTestId('admin-cache-namespaces')
    await expect(namespaces).toBeVisible({ timeout: 15000 })
    await expect(namespaces.getByText('stats')).toBeVisible({ timeout: 15000 })

    const hotKeys = page.getByTestId('admin-cache-hot-keys')
    await expect(hotKeys).toBeVisible({ timeout: 15000 })
    await expect(hotKeys.getByText('lncrna:stats:overview')).toBeVisible({ timeout: 15000 })
  })
})
