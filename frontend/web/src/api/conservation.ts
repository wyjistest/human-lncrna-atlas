/**
 * Conservation API Module
 * API calls for cross-species conservation analysis
 */

import { apiClient } from './client'
import type {
  ConservationOverview,
  ConservationMatrixData,
  ConservedRegulationsResponse,
  ConservationQueryParams,
  VennDiagramData
} from '@/types/conservationPage'

/**
 * Conservation API endpoints
 */
export const conservationApi = {
  /**
   * Get conservation overview statistics
   * @param speciesIds Optional species IDs to filter
   */
  getOverview: async (speciesIds?: number[]): Promise<ConservationOverview> => {
    const params: Record<string, string> = {}
    if (speciesIds && speciesIds.length > 0) {
      params.species_ids = speciesIds.join(',')
    }
    const response = await apiClient.get<ConservationOverview>(
      '/api/v1/conservation/overview',
      { params }
    )
    return response.data
  },

  /**
   * Get conservation matrix data for heatmap visualization
   * @param speciesIds Species IDs to include in matrix
   */
  getMatrix: async (speciesIds: number[]): Promise<ConservationMatrixData> => {
    const response = await apiClient.get<ConservationMatrixData>(
      '/api/v1/conservation/matrix',
      { params: { species_ids: speciesIds.join(',') } }
    )
    return response.data
  },

  /**
   * Get paginated list of conserved regulations
   * @param params Query parameters
   */
  getConservedRegulations: async (
    params: ConservationQueryParams
  ): Promise<ConservedRegulationsResponse> => {
    const apiParams: Record<string, string | number> = {
      page: params.page || 1,
      page_size: params.page_size || 20
    }

    if (params.species_ids && params.species_ids.length > 0) {
      apiParams.species_ids = params.species_ids.join(',')
    }
    if (params.min_conservation) {
      apiParams.min_conservation = params.min_conservation
    }
    if (params.min_ba) {
      apiParams.min_ba = params.min_ba
    }
    if (params.lncrna_gene_name) {
      apiParams.lncrna_gene_name = params.lncrna_gene_name
    }
    if (params.target_gene_name) {
      apiParams.target_gene_name = params.target_gene_name
    }

    const response = await apiClient.get<ConservedRegulationsResponse>(
      '/api/v1/conservation/regulations',
      { params: apiParams }
    )
    return response.data
  },

  /**
   * Get Venn diagram data for species overlap visualization
   * @param speciesIds Species IDs to analyze
   */
  getVennData: async (speciesIds: number[]): Promise<VennDiagramData> => {
    const response = await apiClient.get<VennDiagramData>(
      '/api/v1/conservation/venn',
      { params: { species_ids: speciesIds.join(',') } }
    )
    return response.data
  },

  /**
   * Export conserved regulations as CSV
   * @param params Query parameters (without pagination)
   */
  exportRegulations: async (params: Omit<ConservationQueryParams, 'page' | 'page_size'>): Promise<Blob> => {
    const apiParams: Record<string, string | number> = {}

    if (params.species_ids && params.species_ids.length > 0) {
      apiParams.species_ids = params.species_ids.join(',')
    }
    if (params.min_conservation) {
      apiParams.min_conservation = params.min_conservation
    }
    if (params.min_ba) {
      apiParams.min_ba = params.min_ba
    }
    if (params.lncrna_gene_name) {
      apiParams.lncrna_gene_name = params.lncrna_gene_name
    }
    if (params.target_gene_name) {
      apiParams.target_gene_name = params.target_gene_name
    }

    const response = await apiClient.get('/api/v1/conservation/regulations/export', {
      params: apiParams,
      responseType: 'blob'
    })
    return response.data
  }
}

export default conservationApi
