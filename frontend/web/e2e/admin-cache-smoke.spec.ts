import { test, expect } from '@playwright/test'

/**
 * Smoke: Admin Cache Management page should render with mocked /api/v1/admin/cache/stats.
 *
 * This test is intentionally fully mocked to keep CI fast and independent of
 * backend/DB state.
 */

const PAGE_URL = '/admin/cache'
const BASE_URL = process.env.BASE_URL || 'http://localhost:5173'

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

    await page.goto(`${BASE_URL}${PAGE_URL}`)
    await page.waitForLoadState('domcontentloaded')

    await expect(page.getByRole('heading', { name: 'Cache Management' })).toBeVisible({ timeout: 15000 })
    await expect(page.getByText('Invalidate Namespace')).toBeVisible({ timeout: 15000 })
    await expect(page.getByText('Clear Cache')).toBeVisible({ timeout: 15000 })
    await expect(page.getByText('Cache Namespaces')).toBeVisible({ timeout: 15000 })
    await expect(page.getByText('Cache Hot Keys')).toBeVisible({ timeout: 15000 })
    await expect(page.getByText('Compute Count')).toBeVisible({ timeout: 15000 })
  })
})

