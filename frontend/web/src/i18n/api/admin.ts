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
  metrics: () => apiClient.get<MonitoringMetrics>('/api/v1/admin/metrics'),
}

/**
 * Convenience function for fetching monitoring metrics
 */
export const fetchMonitoringMetrics = async (): Promise<MonitoringMetrics> => {
  const { data } = await adminApi.metrics()
  return data
}
