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

export const useRegulationDetail = (regulationId: number | null) => {
  return useQuery<RegulationDetail | null>({
    queryKey: ['regulation', regulationId],
    queryFn: async () => {
      if (!regulationId) return null
      const { data } = await regulationsApi.getDetail(regulationId)
      return data
    },
    enabled: !!regulationId,
  })
}
