import { apiClient } from './client'
import type { components } from '@/types'
import type {
  NetworkData,
  SpeciesNetworkComparison,
  CompareParams,
  AvailableCombinationsResponse,
  DiseaseNetworkParams,
  GeneDetail
} from '@/types/network'

type APINetworkData = components['schemas']['NetworkData']

export const networkApi = {
  // Existing method
  getGeneNetwork: (geneId: number, params?: {
    species_id?: number
    min_ba?: number
    max_distance?: number
    depth?: number
  }) => apiClient.get<APINetworkData>(`/api/v1/network/gene/${geneId}`, { params }),

  // NEW: Cross-species comparison
  compareSpecies: (lncrnaGeneId: number, params?: CompareParams) =>
    apiClient.get<SpeciesNetworkComparison>('/api/v1/network/compare', {
      params: { lncrna_gene_id: lncrnaGeneId, ...params }
    }),

  // NEW: Get available disease-ontology combinations
  getAvailableCombinations: (speciesId?: number) =>
    apiClient.get<AvailableCombinationsResponse>('/api/v1/network/available-combinations', {
      params: speciesId ? { species_id: speciesId } : undefined
    }),

  // NEW: Get disease network
  getDiseaseNetwork: (params: DiseaseNetworkParams) =>
    apiClient.get<NetworkData>('/api/v1/network/disease', { params }),

  // NEW: Get gene detail
  getGeneDetail: (geneId: number) =>
    apiClient.get<GeneDetail>(`/api/v1/network/gene/${geneId}/detail`),
}
