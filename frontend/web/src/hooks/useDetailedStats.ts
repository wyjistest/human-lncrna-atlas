/**
 * 详细统计数据 Hook
 *
 * 用于 Stats 页面图表展示
 * API: GET /api/v1/stats/detailed
 * 状态：✅ 后端已实现
 */

import { useQuery } from '@tanstack/react-query'
import { statsApi } from '@/api/stats'
import { queryKeys } from './queryKeys'

interface UseDetailedStatsOptions {
  buckets?: number
  topLimit?: number
}

export function useDetailedStats(options: UseDetailedStatsOptions = {}) {
  const { buckets = 10, topLimit = 10 } = options

  return useQuery({
    queryKey: queryKeys.stats.detailed({ buckets, topLimit }),
    queryFn: async ({ signal }) => {
      const { data } = await statsApi.detailed({ buckets, top_limit: topLimit }, signal)
      return data
    },
    staleTime: 10 * 60 * 1000  // 10分钟缓存
  })
}

/**
 * BA 范围 Hook
 * 用于动态设置筛选器范围
 */
export function useBARange() {
  return useQuery({
    queryKey: queryKeys.stats.baRange(),
    queryFn: async ({ signal }) => {
      const { data } = await statsApi.baRange(signal)
      return data
    },
    staleTime: 30 * 60 * 1000  // 30分钟缓存（BA范围不常变化）
  })
}
