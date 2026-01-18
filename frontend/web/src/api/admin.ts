/**
 * Admin API Client
 * Endpoints for admin and monitoring functionality
 */
import { apiClient } from './client'
import type { CacheStatsDetails, MonitoringMetrics } from '@/types/monitoring'
import type { MaterializedViewsRefreshRequest, MaterializedViewsRefreshResponse, MaterializedViewsStatusResponse } from '@/types/admin'

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

  /**
   * Reset cache stats counters (does not clear cached values)
   * POST /api/v1/admin/cache/reset-stats
   */
  resetCacheStats: () =>
    apiClient.post<{ status: string; message?: string }>('/api/v1/admin/cache/reset-stats'),

  /**
   * Fetch cache statistics
   * GET /api/v1/admin/cache/stats
   */
  cacheStats: (signal?: AbortSignal) =>
    apiClient.get<CacheStatsDetails>('/api/v1/admin/cache/stats', { signal }),

  /**
   * Invalidate cache by namespace
   * POST /api/v1/admin/cache/invalidate/{namespace}
   */
  invalidateCacheNamespace: (namespace: string) =>
    apiClient.post<{ status: string; namespace?: string; deleted?: number; message?: string }>(
      `/api/v1/admin/cache/invalidate/${encodeURIComponent(namespace)}`,
    ),

  /**
   * Clear all cache entries (dangerous)
   * POST /api/v1/admin/cache/clear
   */
  clearCache: () =>
    apiClient.post<{ status: string; deleted?: number; message?: string }>('/api/v1/admin/cache/clear'),

  /**
   * Fetch materialized views status
   * GET /api/v1/admin/materialized-views/status
   */
  materializedViewsStatus: (signal?: AbortSignal) =>
    apiClient.get<MaterializedViewsStatusResponse>('/api/v1/admin/materialized-views/status', { signal }),

  /**
   * Refresh materialized views
   * POST /api/v1/admin/materialized-views/refresh
   */
  refreshMaterializedViews: (body: MaterializedViewsRefreshRequest) =>
    apiClient.post<MaterializedViewsRefreshResponse>('/api/v1/admin/materialized-views/refresh', body),
}

/**
 * Convenience function for fetching monitoring metrics
 */
export const fetchMonitoringMetrics = async (signal?: AbortSignal): Promise<MonitoringMetrics> => {
  const { data } = await adminApi.metrics(signal)
  return data
}

export const fetchCacheStats = async (signal?: AbortSignal): Promise<CacheStatsDetails> => {
  const { data } = await adminApi.cacheStats(signal)
  return data
}

export const fetchMaterializedViewsStatus = async (signal?: AbortSignal): Promise<MaterializedViewsStatusResponse> => {
  const { data } = await adminApi.materializedViewsStatus(signal)
  return data
}
