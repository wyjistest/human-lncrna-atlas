/**
 * Admin API Client
 * Endpoints for admin and monitoring functionality
 */
import { apiClient } from './client'
import type { MonitoringMetrics } from '@/types/monitoring'

export const adminApi = {
  /**
   * Fetch monitoring metrics
   * GET /api/v1/admin/metrics
   */
  metrics: (signal?: AbortSignal) =>
    apiClient.get<MonitoringMetrics>('/api/v1/admin/metrics', { signal }),

  /**
   * Reset in-memory monitoring stats (does not affect Prometheus /metrics)
   * POST /api/v1/admin/metrics/reset-stats
   */
  resetMetrics: () =>
    apiClient.post<{ status: string; message?: string }>('/api/v1/admin/metrics/reset-stats'),
}

/**
 * Convenience function for fetching monitoring metrics
 */
export const fetchMonitoringMetrics = async (signal?: AbortSignal): Promise<MonitoringMetrics> => {
  const { data } = await adminApi.metrics(signal)
  return data
}
