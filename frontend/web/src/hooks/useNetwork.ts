import { useQuery } from '@tanstack/react-query'
import { networkApi } from '@/api/network'

export const useNetwork = (geneId: number | null, params?: Parameters<typeof networkApi.getGeneNetwork>[1]) => {
  return useQuery({
    queryKey: ['network', geneId, params],
    queryFn: async () => {
      if (!geneId) return null
      const { data } = await networkApi.getGeneNetwork(geneId, params)
      return data
    },
    enabled: !!geneId,
  })
}
