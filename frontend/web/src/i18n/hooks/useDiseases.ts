import { useQuery } from '@tanstack/react-query'
import { diseasesApi } from '@/api/diseases'

export const useDiseases = (params: Parameters<typeof diseasesApi.list>[0]) => {
  return useQuery({
    queryKey: ['diseases', params],
    queryFn: async () => {
      const { data } = await diseasesApi.list(params)
      return data
    },
  })
}

export const useDiseaseGenes = (
  traitId: number,
  params?: Parameters<typeof diseasesApi.getGenes>[1]
) => {
  return useQuery({
    queryKey: ['disease', traitId, 'genes', params],
    queryFn: async () => {
      const { data } = await diseasesApi.getGenes(traitId, params)
      return data
    },
    enabled: !!traitId,
  })
}
