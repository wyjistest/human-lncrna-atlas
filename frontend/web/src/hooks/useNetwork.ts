import { useQuery } from '@tanstack/react-query'
import { networkApi } from '@/api/network'
import { queryKeys } from './queryKeys'

export const useNetwork = (geneId: number | null, params?: Parameters<typeof networkApi.getGeneNetwork>[1]) => {
  return useQuery({
    queryKey: queryKeys.network.gene(geneId, params as Record<string, unknown>),
    queryFn: async () => {
      if (!geneId) return null
      const { data } = await networkApi.getGeneNetwork(geneId, params)
      return data
    },
    enabled: !!geneId,
  })
}
