/**
 * Genes API
 * Provides access to gene data, including list, detail, and lightweight options
 *
 * Phase 5.2: Added getOptions() method for lightweight gene selection
 */
import { apiClient } from './client'
import type { components } from '@/types'

type GeneListItem = components['schemas']['GeneListItem']
type GeneDetail = components['schemas']['GeneDetail']
type PaginatedResponse<T> = components['schemas']['PaginatedResponse_GeneListItem_'] & { items: T[] }

/**
 * Gene option interface (lightweight, for dropdown selection)
 * Used by gene selectors and autocomplete components
 *
 * @example
 * {
 *   gene_id: 1,
 *   gene_ensembl_id: "ENSG00000000003",
 *   gene_name: "TSPAN6",
 *   species_id: 1,
 *   species_name: "人类"
 * }
 */
export interface GeneOption {
  gene_id: number
  gene_ensembl_id: string
  gene_name: string | null
  species_id: number
  species_name: string
}

/**
 * Gene options response interface
 */
export interface GeneOptionsResponse {
  genes: GeneOption[]
}

export const genesApi = {
  /**
   * Get paginated gene list with full details
   *
   * Used by: Genes list page (/genes)
   *
   * @param params - Query parameters
   * @param params.page - Page number (default: 1)
   * @param params.page_size - Items per page (default: 100)
   * @param params.gene_type - Filter by type (lncRNA/protein_coding)
   * @param params.species_id - Filter by species ID (1-4)
   * @param params.search - Search by gene name or ID
   * @returns Paginated gene list with full details
   */
  list: (params: {
    page?: number
    page_size?: number
    gene_type?: string
    species_id?: number
    search?: string
  }) => apiClient.get<PaginatedResponse<GeneListItem>>('/api/v1/genes', { params }),

  /**
   * Get detailed information for a single gene
   *
   * Used by: Gene detail page (/genes/:id)
   *
   * @param geneId - Gene ID
   * @returns Complete gene information including orthologs, regulations, diseases
   */
  detail: (geneId: number) => apiClient.get<GeneDetail>(`/api/v1/genes/${geneId}`),

  /**
   * Get lightweight gene options for dropdown selection
   *
   * Phase 5.2 - Optimized API following Phase 5.1 Diseases API pattern
   *
   * Returns only essential fields (id, name, species) without pagination.
   * Designed for dropdown selectors and autocomplete components.
   *
   * **Performance**:
   * - Response time: 200-350ms (first call), 150-250ms (cached)
   * - Response size: ~2MB (all genes), ~600KB (filtered by species)
   * - Backend cache: Redis 30 minutes
   * - Frontend cache: React Query 10 minutes (recommended)
   *
   * **Data Volume**:
   * - All genes: 17,248 records
   * - Human only: 5,484 records
   * - lncRNA only: 6,554 records
   * - Protein-coding only: 10,694 records
   *
   * @param params - Optional filters
   * @param params.species_id - Filter by species (1=Human, 2=Chimp, 3=Macaque, 4=Marmoset)
   * @param params.gene_type - Filter by gene type (lncRNA/protein_coding)
   * @returns Promise with genes array (no pagination, all results returned)
   *
   * @example
   * // Basic usage: All genes (use with caution, 2MB response)
   * const { data } = useQuery({
   *   queryKey: ['gene-options'],
   *   queryFn: () => genesApi.getOptions(),
   *   staleTime: 10 * 60 * 1000, // 10 minutes cache
   * })
   *
   * @example
   * // Recommended: Filter by species to reduce data size
   * const { data } = useQuery({
   *   queryKey: ['gene-options', speciesId],
   *   queryFn: () => genesApi.getOptions({ species_id: speciesId }),
   *   staleTime: 10 * 60 * 1000,
   *   enabled: !!speciesId, // Only load when species selected
   * })
   *
   * @example
   * // Filter by gene type
   * const { data } = useQuery({
   *   queryKey: ['gene-options', 'lncRNA'],
   *   queryFn: () => genesApi.getOptions({ gene_type: 'lncRNA' }),
   *   staleTime: 10 * 60 * 1000,
   * })
   *
   * @example
   * // Combine filters
   * const { data } = useQuery({
   *   queryKey: ['gene-options', speciesId, geneType],
   *   queryFn: () => genesApi.getOptions({ species_id: speciesId, gene_type: geneType }),
   *   staleTime: 10 * 60 * 1000,
   * })
   *
   * @see GENES_API_INTEGRATION_PLAN.md for complete integration guide
   * @see Phase 5.1 Diseases API (diseases.ts) for similar pattern
   */
  getOptions: async (params?: {
    species_id?: number
    gene_type?: string
  }): Promise<GeneOptionsResponse> => {
    const response = await apiClient.get<GeneOptionsResponse>(
      '/api/v1/genes/options',
      { params }
    )
    return response.data
  }
}
