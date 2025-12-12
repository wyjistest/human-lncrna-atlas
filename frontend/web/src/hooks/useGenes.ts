import { useQuery, useQueryClient } from '@tanstack/react-query'
import { useCallback } from 'react'
import { genesApi } from '@/api/genes'
import { regulationsApi } from '@/api/regulations'
import { diseasesApi } from '@/api/diseases'

export const useGenes = (params: Parameters<typeof genesApi.list>[0]) => {
  return useQuery({
    queryKey: ['genes', params],
    queryFn: async () => {
      const { data } = await genesApi.list(params)
      return data
    },
  })
}

/**
 * 预加载基因列表数据的 Hook
 * 用于在用户浏览当前页时，提前加载相邻页数据到缓存
 */
export const usePrefetchGenes = () => {
  const queryClient = useQueryClient()

  return useCallback((params: Parameters<typeof genesApi.list>[0]) => {
    queryClient.prefetchQuery({
      queryKey: ['genes', params],
      queryFn: async () => {
        const { data } = await genesApi.list(params)
        return data
      },
    })
  }, [queryClient])
}

export const useGeneDetail = (geneId: number) => {
  return useQuery({
    queryKey: ['gene', geneId],
    queryFn: async () => {
      const { data } = await genesApi.detail(geneId)
      return data
    },
    enabled: !!geneId,
  })
}

/**
 * 获取基因的调控关系列表
 */
export const useGeneRegulations = (geneId: number, params?: { page?: number; page_size?: number }) => {
  return useQuery({
    queryKey: ['gene', geneId, 'regulations', params],
    queryFn: async () => {
      const { data } = await regulationsApi.list({
        lncrna_gene_id: geneId,
        page: params?.page || 1,
        page_size: params?.page_size || 20,
      })
      return data
    },
    enabled: !!geneId,
  })
}

/**
 * 获取基因的疾病关联列表
 */
export const useGeneDiseases = (geneId: number) => {
  return useQuery({
    queryKey: ['gene', geneId, 'diseases'],
    queryFn: async () => {
      const { data } = await diseasesApi.getGeneAssociations(geneId)
      return data
    },
    enabled: !!geneId,
  })
}

/**
 * 获取基因的直系同源基因列表
 *
 * Phase 6.2 - Ortholog Browser feature
 *
 * 用途: OrthologBrowser 组件，显示跨物种直系同源基因
 *
 * @param geneId - 基因 ID
 * @returns 直系同源基因列表
 */
export const useGeneOrthologs = (geneId: number) => {
  return useQuery({
    queryKey: ['gene', geneId, 'orthologs'],
    queryFn: async () => {
      const { data } = await genesApi.getOrthologs(geneId)
      return data
    },
    enabled: geneId > 0,
    staleTime: 5 * 60 * 1000, // 5 minutes cache
  })
}
