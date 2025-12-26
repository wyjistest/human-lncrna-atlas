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
}

/**
 * Convenience function for fetching monitoring metrics
 */
export const fetchMonitoringMetrics = async (signal?: AbortSignal): Promise<MonitoringMetrics> => {
  const { data } = await adminApi.metrics(signal)
  return data
}
