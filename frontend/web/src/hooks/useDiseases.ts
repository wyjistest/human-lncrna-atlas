import { useQuery } from '@tanstack/react-query'
import { diseasesApi } from '@/api/diseases'
import { queryKeys } from './queryKeys'

export const useDiseases = (params: Parameters<typeof diseasesApi.list>[0]) => {
  return useQuery({
    queryKey: queryKeys.diseases.list(params),
    queryFn: async ({ signal }) => {
      const { data } = await diseasesApi.list(params, signal)
      return data
    },
    meta: { skipGlobalErrorHandler: true },
  })
}

export const useDiseaseGenes = (
  traitId: number,
  params?: Parameters<typeof diseasesApi.getGenes>[1]
) => {
  return useQuery({
    queryKey: queryKeys.diseases.genes(traitId, params),
    queryFn: async ({ signal }) => {
      const { data } = await diseasesApi.getGenes(traitId, params, signal)
      return data
    },
    enabled: !!traitId,
    meta: { skipGlobalErrorHandler: true },
  })
}
