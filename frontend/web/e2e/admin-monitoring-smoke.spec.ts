import { test, expect } from '@playwright/test'

/**
 * Smoke: Admin Monitoring page should render with mocked /api/v1/admin/metrics.
 *
 * This test is intentionally fully mocked to keep CI fast and independent of
 * backend/DB state.
 */

const PAGE_URL = '/admin/monitoring'

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
    endpoints: [
      {
        path: '/api/v1/demo/fast',
        requests: 12,
        avg_ms: 80.2,
        samples: 12,
        percentiles: { p50_ms: 60, p95_ms: 120, p99_ms: 180 },
        db_avg_ms: 10.5,
        db_query_avg: 1.25,
        db_samples: 12,
        db_percentiles: { p50_ms: 8, p95_ms: 20, p99_ms: 35 },
        errors: 0,
        error_rate: 0,
      },
      {
        path: '/api/v1/demo/slow',
        requests: 8,
        avg_ms: 450.0,
        samples: 8,
        percentiles: null,
        db_avg_ms: 380.0,
        db_query_avg: 3.0,
        db_samples: 8,
        db_percentiles: null,
        errors: 1,
        error_rate: 0.125,
      },
    ],
    system: {
      cpu_percent: 0,
      memory: { used_mb: 0, total_mb: 0, percent: 0 },
      disk: { used_gb: 0, total_gb: 0, percent: 0 },
      process: { cpu_percent: 0, memory_mb: 0 },
    },
    alerts: [],
    percentiles: { p50_ms: 100, p95_ms: 300, p99_ms: 800 },
    database: {
      total_queries: 48,
      total_time_ms: 2500,
      query_samples: 12,
      avg_ms: 52.08,
      percentiles: { p50_ms: 20, p95_ms: 150, p99_ms: 300 },
      request_samples: 12,
      request_total_ms: 1200,
      request_avg_ms: 100.0,
      request_percentiles: { p50_ms: 60, p95_ms: 220, p99_ms: 380 },
      slow_query_threshold_ms: 200,
      slow_queries: [
        {
          fingerprint: 'deadbeefcafe',
          statement: 'SELECT pg_sleep(0.25)',
          count: 12,
          total_time_ms: 3000,
          avg_ms: 250,
          max_ms: 300,
          last_seen: '2026-01-19T00:00:00',
          route: '/api/v1/demo/slow',
        },
      ],
    },
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

    await page.goto(PAGE_URL)
    await page.waitForLoadState('domcontentloaded')

    await expect(page.getByRole('heading', { name: 'System Monitoring' })).toBeVisible({ timeout: 15000 })

    await expect(page.getByTestId('admin-monitoring-page')).toBeVisible({ timeout: 15000 })

    const cacheLatencyCard = page.getByTestId('admin-monitoring-cache-get-latency')
    await expect(cacheLatencyCard).toBeVisible({ timeout: 15000 })
    await expect(cacheLatencyCard.getByText('hits: 12 / misses: 12')).toBeVisible({ timeout: 15000 })
    await expect(cacheLatencyCard.getByText('P50')).toHaveCount(2)
    await expect(cacheLatencyCard.getByText('P95')).toHaveCount(2)
    await expect(cacheLatencyCard.getByText('P99')).toHaveCount(2)

    const dbCard = page.getByTestId('admin-monitoring-database')
    await expect(dbCard).toBeVisible({ timeout: 15000 })
    await expect(dbCard.getByText('Database Performance')).toBeVisible({ timeout: 15000 })
    await expect(page.getByTestId('admin-monitoring-database-slow-queries')).toBeVisible({ timeout: 15000 })
    await expect(page.getByText('deadbeefcafe')).toBeVisible({ timeout: 15000 })

    const topP95 = page.getByTestId('admin-monitoring-top-endpoints-p95')
    await expect(topP95).toBeVisible({ timeout: 15000 })
    await expect(topP95.getByText('/api/v1/demo/fast')).toBeVisible({ timeout: 15000 })

    const topDbP95 = page.getByTestId('admin-monitoring-top-db-endpoints-p95')
    await expect(topDbP95).toBeVisible({ timeout: 15000 })
    await expect(topDbP95.getByText('/api/v1/demo/fast')).toBeVisible({ timeout: 15000 })

    const topDbP99 = page.getByTestId('admin-monitoring-top-db-endpoints-p99')
    await expect(topDbP99).toBeVisible({ timeout: 15000 })

    const downloadBtn = page.getByTestId('admin-monitoring-download-metrics')
    await expect(downloadBtn).toBeVisible({ timeout: 15000 })
  })
})
