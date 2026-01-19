import { test, expect } from '@playwright/test'

/**
 * Smoke: Admin Monitoring page should render with mocked /api/v1/admin/metrics.
 *
 * This test is intentionally fully mocked to keep CI fast and independent of
 * backend/DB state.
 */

const PAGE_URL = '/admin/monitoring'
const BASE_URL = process.env.BASE_URL || 'http://localhost:5173'

function buildMockMetricsResponse() {
  return {
    request: { total: 42, last_minute: 3 },
    errors: { total: 1, rate: 0.0238 },
    response_time: { avg_ms: 123.4 },
    health: { status: 'healthy', database: 'ok', cache: 'ok', uptime_seconds: 3600 },
    cache_stats: {
      backend: 'memory',
      enabled: true,
      hits: 10,
      misses: 2,
      total_requests: 12,
      hit_rate_pct: 83.33,
    },
    cache_breakdown: {
      namespaces: { tracked: 0, limit: 10, top: [] },
      keys: { tracked: 0, limit: 10, top: [] },
    },
    cache_get_latency: {
      hits_samples: 12,
      misses_samples: 12,
      max_samples: 1000,
      hits: { p50_ms: 0.5, p95_ms: 1.2, p99_ms: 2.0 },
      misses: { p50_ms: 0.8, p95_ms: 2.5, p99_ms: 4.1 },
    },
    response_time_distribution: { buckets: [], counts: [] },
    error_trend: { timestamps: [], error_rates: [] },
    endpoints: [],
    system: {
      cpu_percent: 0,
      memory: { used_mb: 0, total_mb: 0, percent: 0 },
      disk: { used_gb: 0, total_gb: 0, percent: 0 },
      process: { cpu_percent: 0, memory_mb: 0 },
    },
    alerts: [],
    percentiles: { p50_ms: 100, p95_ms: 300, p99_ms: 800 },
  }
}

test.describe('Admin Monitoring - mocked smoke', () => {
  test('renders monitoring cards and cache latency percentiles', async ({ page }) => {
    await page.route('**/api/v1/admin/metrics*', async (route) => {
      await route.fulfill({
        status: 200,
        contentType: 'application/json',
        body: JSON.stringify(buildMockMetricsResponse()),
      })
    })

    await page.goto(`${BASE_URL}${PAGE_URL}`)
    await page.waitForLoadState('domcontentloaded')

    await expect(page.getByRole('heading', { name: 'System Monitoring' })).toBeVisible({ timeout: 15000 })

    await expect(page.getByTestId('admin-monitoring-page')).toBeVisible({ timeout: 15000 })

    const cacheLatencyCard = page.getByTestId('admin-monitoring-cache-get-latency')
    await expect(cacheLatencyCard).toBeVisible({ timeout: 15000 })
    await expect(cacheLatencyCard.getByText('hits: 12 / misses: 12')).toBeVisible({ timeout: 15000 })
    await expect(cacheLatencyCard.getByText('P50')).toHaveCount(2)
    await expect(cacheLatencyCard.getByText('P95')).toHaveCount(2)
    await expect(cacheLatencyCard.getByText('P99')).toHaveCount(2)
  })
})
