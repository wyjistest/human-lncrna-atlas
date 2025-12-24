/**
 * Conservation API Module
 *
 * Provides API access for cross-species lncRNA conservation analysis.
 * This module enables querying conservation patterns across 4 primate species:
 * Human (1), Chimpanzee (2), Macaque (3), and Marmoset (4).
 *
 * Key features:
 * - Overview statistics for conservation distribution
 * - Heatmap matrix data for species pairwise comparison
 * - Paginated list of conserved regulatory relationships
 * - Venn diagram data for species overlap visualization
 * - CSV export for downstream analysis
 *
 * @module api/conservation
 * @see Conservation page component at /src/pages/Conservation
 * @see Phase 5.0 Conservation API documentation
 */

import { apiClient } from './client'
import type {
  ConservationQueryParams
} from '@/types/conservationPage'
import type {
  ConservationSummaryResponse,
  ConservationMatrixResponse,
  ConservedRegulationListResponse,
  ConservationVennResponse,
} from '@/types/conservationApi'

/**
 * Conservation API endpoints
 *
 * All endpoints use Redis caching on the backend with 5-minute TTL.
 * Frontend React Query should use matching staleTime for optimal caching.
 */
export const conservationApi = {
  /**
   * Get conservation overview statistics
   *
   * Returns aggregated statistics about conserved lncRNA regulations across species.
   * Provides distribution of regulations by conservation level (2, 3, or 4 species)
   * and top species combinations.
   *
   * **Performance**:
   * - Response time: 50-100ms (first), 20-50ms (cached)
   * - Response size: ~2 KB
   * - Backend cache: Redis 5 minutes
   *
   * @param speciesIds - Optional species IDs to filter (1-4). If empty, returns data for all species.
   * @returns Promise with conservation overview including:
   *   - distribution: Array of {conservation_count, regulation_count, lncrna_count}
   *   - top_combinations: Array of top species combinations with counts
   *
   * @example
   * // Get overview for all 4 species
   * const { data } = useQuery({
   *   queryKey: ['conservation-overview'],
   *   queryFn: () => conservationApi.getOverview(),
   *   staleTime: 5 * 60 * 1000,
   * })
   *
   * @example
   * // Get overview for Human and Chimpanzee only
   * const { data } = useQuery({
   *   queryKey: ['conservation-overview', [1, 2]],
   *   queryFn: () => conservationApi.getOverview([1, 2]),
   * })
   *
   * @see ConservationOverview type for response structure
   */
  getOverview: async (speciesIds?: number[]): Promise<ConservationSummaryResponse> => {
    const params: Record<string, string> = {}
    if (speciesIds && speciesIds.length > 0) {
      params.species_ids = speciesIds.join(',')
    }
    const response = await apiClient.get<ConservationSummaryResponse>(
      '/api/v1/conservation/overview',
      { params }
    )
    return response.data
  },

  /**
   * Get conservation matrix data for heatmap visualization
   *
   * Returns a symmetric matrix showing shared lncRNA counts between species pairs.
   * Used to render the conservation heatmap on the Conservation page.
   * Diagonal values represent total lncRNAs in each species.
   *
   * **Performance**:
   * - Response time: 100-200ms (first), 50-100ms (cached)
   * - Response size: ~5 KB
   * - Backend cache: Redis 5 minutes
   *
   * @param speciesIds - Species IDs to include in matrix (minimum 2 required)
   * @returns Promise with matrix data including:
   *   - species: Array of species IDs
   *   - species_names: Array of species display names
   *   - matrix: 2D array of shared lncRNA counts (symmetric)
   *   - max_value: Maximum value in matrix (for color scaling)
   *   - min_value: Minimum value in matrix
   *
   * @example
   * // Get matrix for all 4 species
   * const { data } = useQuery({
   *   queryKey: ['conservation-matrix', [1, 2, 3, 4]],
   *   queryFn: () => conservationApi.getMatrix([1, 2, 3, 4]),
   *   staleTime: 5 * 60 * 1000,
   * })
   *
   * @example
   * // Get matrix for 2 species comparison
   * const { data } = useQuery({
   *   queryKey: ['conservation-matrix', selectedSpecies],
   *   queryFn: () => conservationApi.getMatrix(selectedSpecies),
   *   enabled: selectedSpecies.length >= 2,
   * })
   *
   * @see ConservationMatrix component for rendering
   */
  getMatrix: async (speciesIds: number[]): Promise<ConservationMatrixResponse> => {
    const response = await apiClient.get<ConservationMatrixResponse>(
      '/api/v1/conservation/matrix',
      { params: { species_ids: speciesIds.join(',') } }
    )
    return response.data
  },

  /**
   * Get paginated list of conserved regulations
   *
   * Returns detailed information about lncRNA-gene regulatory relationships
   * that are conserved across multiple species. Supports filtering by species,
   * conservation level, binding affinity, and gene names.
   *
   * **Performance**:
   * - Response time: 150-400ms (varies by filters)
   * - Response size: ~20-50 KB per page
   * - Backend cache: Redis 2 minutes
   *
   * **Data Volume**:
   * - 4 species conserved: ~12,345 regulations
   * - 3 species conserved: ~34,567 regulations
   * - 2 species conserved: ~109,877 regulations
   *
   * @param params - Query parameters
   * @param params.species_ids - Filter by species IDs (array)
   * @param params.page - Page number (default: 1)
   * @param params.page_size - Items per page (default: 20, max: 100)
   * @param params.min_conservation - Minimum number of species (2-4)
   * @param params.min_ba - Minimum binding affinity threshold
   * @param params.lncrna_gene_name - Filter by lncRNA name (partial match)
   * @param params.target_gene_name - Filter by target gene name (partial match)
   * @returns Promise with paginated response including:
   *   - items: Array of ConservedRegulation objects
   *   - total: Total number of matching records
   *   - page: Current page number
   *   - page_size: Items per page
   *   - pages: Total number of pages
   *
   * @example
   * // Basic paginated query
   * const { data } = useQuery({
   *   queryKey: ['conservation-regulations', { page: 1, page_size: 20 }],
   *   queryFn: () => conservationApi.getConservedRegulations({
   *     page: 1,
   *     page_size: 20,
   *   }),
   * })
   *
   * @example
   * // Filtered query with all parameters
   * const { data } = useQuery({
   *   queryKey: ['conservation-regulations', filters],
   *   queryFn: () => conservationApi.getConservedRegulations({
   *     species_ids: [1, 2, 3, 4],
   *     page: 1,
   *     page_size: 20,
   *     min_conservation: 3,
   *     min_ba: 50,
   *     lncrna_gene_name: 'MALAT1',
   *   }),
   * })
   *
   * @see ConservedRegulation type for item structure
   * @see Conservation page table component
   */
  getConservedRegulations: async (
    params: ConservationQueryParams
  ): Promise<ConservedRegulationListResponse> => {
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

    const response = await apiClient.get<ConservedRegulationListResponse>(
      '/api/v1/conservation/regulations',
      { params: apiParams }
    )
    return response.data
  },

  /**
   * Get Venn diagram data for species overlap visualization
   *
   * Returns intersection counts for species combinations, suitable for
   * rendering 2-4 species Venn diagrams. Each combination is represented
   * with its member species and count.
   *
   * **Performance**:
   * - Response time: 50-150ms
   * - Response size: ~3 KB
   * - Backend cache: Redis 5 minutes
   *
   * @param speciesIds - Species IDs to analyze (2-4 species)
   * @returns Promise with Venn diagram data including:
   *   - sets: Array of individual species data
   *   - intersections: Array of overlap counts for each combination
   *
   * @example
   * // Get Venn data for 3 species
   * const { data } = useQuery({
   *   queryKey: ['conservation-venn', [1, 2, 3]],
   *   queryFn: () => conservationApi.getVennData([1, 2, 3]),
   *   staleTime: 5 * 60 * 1000,
   * })
   *
   * @see VennDiagramData type for response structure
   */
  getVennData: async (
    dataType: 'lncrna' | 'regulation' = 'lncrna'
  ): Promise<ConservationVennResponse> => {
    const response = await apiClient.get<ConservationVennResponse>(
      '/api/v1/conservation/venn',
      { params: { data_type: dataType } }
    )
    return response.data
  },

  /**
   * Export conserved regulations as CSV file
   *
   * Exports filtered conserved regulations data as a downloadable CSV file.
   * Supports the same filters as getConservedRegulations but without pagination,
   * returning all matching records.
   *
   * **Performance**:
   * - Response time: 500ms - 5s (depends on data volume)
   * - Response size: Varies (50KB - 10MB)
   * - No backend cache (fresh data each request)
   *
   * **Rate Limiting**:
   * - Max 10 exports per minute per IP
   * - Large exports may timeout after 30 seconds
   *
   * @param params - Query parameters (without pagination)
   * @param params.species_ids - Filter by species IDs
   * @param params.min_conservation - Minimum conservation level
   * @param params.min_ba - Minimum binding affinity
   * @param params.lncrna_gene_name - Filter by lncRNA name
   * @param params.target_gene_name - Filter by target gene name
   * @returns Promise with Blob containing CSV data
   *
   * @example
   * // Export filtered regulations
   * const handleExport = async () => {
   *   try {
   *     const blob = await conservationApi.exportRegulations({
   *       species_ids: [1, 2, 3, 4],
   *       min_conservation: 3,
   *     })
   *
   *     // Create download link
   *     const url = URL.createObjectURL(blob)
   *     const a = document.createElement('a')
   *     a.href = url
   *     a.download = `conservation_${new Date().toISOString()}.csv`
   *     a.click()
   *     URL.revokeObjectURL(url)
   *   } catch (error) {
   *     message.error('Export failed')
   *   }
   * }
   *
   * @see Conservation page export button implementation
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
