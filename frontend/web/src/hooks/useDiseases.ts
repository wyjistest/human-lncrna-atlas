import { useQuery } from '@tanstack/react-query'
import { diseasesApi } from '@/api/diseases'
import { queryKeys } from './queryKeys'

export const useDiseases = (params: Parameters<typeof diseasesApi.list>[0]) => {
  return useQuery({
    queryKey: queryKeys.diseases.list(params as Record<string, unknown>),
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
    queryKey: queryKeys.diseases.genes(traitId, params as Record<string, unknown>),
    queryFn: async () => {
      const { data } = await diseasesApi.getGenes(traitId, params)
      return data
    },
    enabled: !!traitId,
  })
}
