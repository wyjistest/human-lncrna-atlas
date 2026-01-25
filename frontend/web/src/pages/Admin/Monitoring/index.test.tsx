import { screen } from '@testing-library/react'
import { vi } from 'vitest'

import { renderWithProviders } from '@/test/testUtils'
import Monitoring from './index'

vi.mock('@/hooks/useMonitoringMetrics', () => ({
  useMonitoringMetrics: () => ({
    data: {
      request: { total: 1, last_minute: 0 },
      errors: { total: 0, rate: 0 },
      response_time: { avg_ms: 10 },
      health: { status: 'healthy', database: 'ok', cache: 'ok', uptime_seconds: 60 },
      cache_stats: {
        backend: 'memory',
        enabled: true,
        hits: 1,
        misses: 0,
        total_requests: 1,
        hit_rate_pct: 100,
      },
      cache_breakdown: {
        namespaces: {
          tracked: 1,
          limit: 10,
          top: [
            {
              namespace: 'stats:overview',
              requests: 1,
              hits: 1,
              misses: 0,
              hit_rate_pct: 100,
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
              namespace: 'stats:overview',
              requests: 1,
              hits: 1,
              misses: 0,
              hit_rate_pct: 100,
              compute_count: 0,
              compute_avg_ms: 0,
              compute_max_ms: 0,
            },
          ],
        },
        routes: {
          tracked: 1,
          limit: 10,
          top: [
            {
              route: '/api/v1/test',
              compute_count: 1,
              compute_avg_ms: 12.3,
              compute_max_ms: 20.0,
            },
          ],
        },
      },
      cache_get_latency: {
        hits_samples: 12,
        misses_samples: 11,
        max_samples: 1000,
        hits: { p50_ms: 0.5, p95_ms: 1.2, p99_ms: 2.0 },
        misses: { p50_ms: 0.8, p95_ms: 2.5, p99_ms: 4.1 },
      },
      response_time_distribution: { buckets: [], counts: [] },
      error_trend: { timestamps: [], error_rates: [] },
      endpoints: [
        {
          path: '/api/v1/test',
          requests: 1,
          avg_ms: 10,
          percentiles: { p50_ms: 8, p95_ms: 20, p99_ms: 30 },
          errors: 0,
          error_rate: 0,
        },
      ],
      system: {
        cpu_percent: 0,
        memory: { used_mb: 0, total_mb: 0, percent: 0 },
        disk: { used_gb: 0, total_gb: 0, percent: 0 },
        process: { cpu_percent: 0, memory_mb: 0 },
      },
      alerts: [],
      percentiles: null,
      database: {
        total_queries: 0,
        total_time_ms: 0,
        query_samples: 0,
        avg_ms: 0,
        percentiles: null,
        request_samples: 0,
        request_total_ms: 0,
        request_avg_ms: 0,
        request_percentiles: null,
        slow_query_threshold_ms: 200,
        slow_queries: [],
      },
    },
    isLoading: false,
    error: null,
    refetch: vi.fn(),
    isFetching: false,
  }),
}))

describe('Admin Monitoring page', () => {
  it('renders cache breakdown section', () => {
    renderWithProviders(<Monitoring />)

    expect(screen.getByTestId('admin-monitoring-page')).toBeInTheDocument()
    expect(screen.getByTestId('admin-monitoring-response-percentiles')).toBeInTheDocument()
    expect(screen.getByTestId('admin-monitoring-endpoint-statistics')).toBeInTheDocument()
    expect(screen.getByTestId('admin-monitoring-top-endpoints-p95')).toBeInTheDocument()
    expect(screen.getByTestId('admin-monitoring-top-endpoints-p99')).toBeInTheDocument()
    expect(screen.getByTestId('admin-monitoring-top-db-endpoints-p95')).toBeInTheDocument()
    expect(screen.getByTestId('admin-monitoring-top-db-endpoints-p99')).toBeInTheDocument()
    expect(screen.getByTestId('admin-monitoring-database')).toBeInTheDocument()
    expect(screen.getByTestId('admin-monitoring-cache-get-latency')).toBeInTheDocument()

    expect(screen.getByText('Reset Cache Stats')).toBeInTheDocument()
    expect(screen.getByTestId('admin-monitoring-download-metrics')).toBeInTheDocument()
    expect(screen.getByText('Cache Get Latency')).toBeInTheDocument()
    expect(screen.getByText('Cache Namespaces')).toBeInTheDocument()
    expect(screen.getByText('Cache Hot Keys')).toBeInTheDocument()
    expect(screen.getByText('Cache Routes (Compute Top)')).toBeInTheDocument()
    expect(screen.getAllByText('Compute Count').length).toBeGreaterThan(0)
    expect(screen.getAllByText('P95 (ms)').length).toBeGreaterThan(0)
    expect(screen.getAllByText('P99 (ms)').length).toBeGreaterThan(0)
    expect(screen.getByText('Database Performance')).toBeInTheDocument()
  }, 10_000)
})
