import { useQuery, useQueryClient } from '@tanstack/react-query'
import { useCallback } from 'react'
import { regulationsApi } from '@/api/regulations'
import type { components } from '@/types'

type RegulationDetail = components['schemas']['RegulationDetail']

export const useRegulations = (params: Parameters<typeof regulationsApi.list>[0]) => {
  return useQuery({
    queryKey: ['regulations', params],
    queryFn: async () => {
      const { data } = await regulationsApi.list(params)
      return data
    },
  })
}

/**
 * 预加载调控关系列表数据的 Hook
 * 用于在用户浏览当前页时，提前加载相邻页数据到缓存
 */
export const usePrefetchRegulations = () => {
  const queryClient = useQueryClient()

  return useCallback((params: Parameters<typeof regulationsApi.list>[0]) => {
    queryClient.prefetchQuery({
      queryKey: ['regulations', params],
      queryFn: async () => {
        const { data } = await regulationsApi.list(params)
        return data
      },
    })
  }, [queryClient])
}

/**
 * 获取调控关系详情的 Hook
 * @param regulationId - 调控关系 ID
 * @param options - 可选配置
 * @param options.enabled - 是否启用查询（默认 true），可用于控制弹窗关闭时停止请求
 */
export const useRegulationDetail = (
  regulationId: number | null,
  options?: { enabled?: boolean }
) => {
  // 默认 enabled 为 true，但需要同时满足 regulationId 存在和外部 enabled 条件
  const isEnabled = !!regulationId && (options?.enabled ?? true)

  return useQuery<RegulationDetail | null>({
    queryKey: ['regulation', regulationId],
    queryFn: async () => {
      if (!regulationId) return null
      const { data } = await regulationsApi.getDetail(regulationId)
      return data
    },
    enabled: isEnabled,
  })
}
