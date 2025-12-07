import { apiClient } from './client'
import type { components, BARange, DetailedStatsResponse } from '@/types'

type OverviewStats = components['schemas']['OverviewStats']

export const statsApi = {
  overview: () => apiClient.get<OverviewStats>('/api/v1/stats/overview'),

  /**
   * 获取 BA 范围
   * 用于动态设置筛选器范围
   */
  baRange: () => apiClient.get<BARange>('/api/v1/stats/ba-range'),

  /**
   * 获取详细统计信息
   * 用于 Stats 页面图表展示
   */
  detailed: (params?: { buckets?: number; top_limit?: number }) =>
    apiClient.get<DetailedStatsResponse>('/api/v1/stats/detailed', { params }),
}
