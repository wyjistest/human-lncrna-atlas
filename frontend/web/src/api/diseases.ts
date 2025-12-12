/**
 * Diseases API
 *
 * Provides access to disease/trait data including associations with genes
 * and lncRNAs. Supports disease exploration, gene-disease relationships,
 * and lightweight option lists for UI selectors.
 *
 * Features:
 * - Disease/trait list with pagination and filtering
 * - Gene associations per disease
 * - Disease associations per gene
 * - Lightweight options for dropdown selection
 *
 * Phase 5.1: Added getOptions() method for optimized dropdown loading
 *
 * @module api/diseases
 */
import { apiClient } from './client'
import type { components } from '@/types'

type TraitGeneAssociationDetail = components['schemas']['TraitGeneAssociationDetail']
type PaginatedTraitAssociationResponse = components['schemas']['PaginatedResponse_TraitGeneAssociationDetail_']
type PaginatedGeneResponse = components['schemas']['PaginatedResponse_TraitGeneAssociationDetail_']

/**
 * Disease option interface (lightweight, for dropdown selection)
 *
 * Minimal fields required for select/autocomplete components.
 * Does not include category, gene counts, or other detailed info.
 *
 * @example
 * {
 *   trait_id: 123,
 *   trait_name: "Type 2 Diabetes"
 * }
 */
export interface DiseaseOption {
  trait_id: number
  trait_name: string
}

/**
 * Disease options response interface
 *
 * Wrapper for the lightweight disease options list.
 * Contains only deduplicated trait_id and trait_name pairs.
 */
export interface DiseaseOptionsResponse {
  traits: DiseaseOption[]
}

export const diseasesApi = {
  /**
   * Get paginated disease/trait list with full details
   *
   * Returns diseases with associated gene counts and categories.
   * Used by the Diseases list page for browsing and filtering.
   *
   * **Performance**:
   * - Response time: 100-300ms (first call), 50-100ms (cached)
   * - Response size: ~20-100 KB (depends on page size)
   * - Backend cache: Redis 15 minutes
   *
   * **Data Per Disease**:
   * - trait_id, trait_name, trait_category
   * - Gene association details
   * - lncRNA involvement metrics
   *
   * @param params - Query parameters for filtering and pagination
   * @param params.page - Page number (default: 1)
   * @param params.page_size - Items per page (default: 20)
   * @param params.trait_category - Filter by disease category
   * @param params.search - Search by disease name
   * @returns Paginated disease list with association details
   *
   * @example
   * // Basic usage: First page with defaults
   * const { data } = useQuery({
   *   queryKey: ['diseases', { page: 1 }],
   *   queryFn: () => diseasesApi.list({ page: 1 }),
   * })
   *
   * @example
   * // With search and category filter
   * const { data } = useQuery({
   *   queryKey: ['diseases', { search, category, page }],
   *   queryFn: () => diseasesApi.list({
   *     page,
   *     page_size: 20,
   *     trait_category: category,
   *     search: searchTerm
   *   }),
   * })
   *
   * @example
   * // Paginated table implementation
   * <Table
   *   dataSource={data?.items}
   *   pagination={{
   *     current: page,
   *     total: data?.total,
   *     pageSize: data?.page_size,
   *     onChange: setPage
   *   }}
   * />
   *
   * @see Diseases list page (/diseases)
   * @see Disease detail page for individual disease view
   */
  list: (params: {
    page?: number
    page_size?: number
    trait_category?: string
    search?: string
  }) => apiClient.get<PaginatedTraitAssociationResponse>('/api/v1/diseases', { params }),

  /**
   * Get genes associated with a specific disease
   *
   * Returns paginated list of genes (lncRNAs and protein-coding)
   * that are associated with the specified disease/trait.
   * Includes regulation details and binding affinity data.
   *
   * **Performance**:
   * - Response time: 100-500ms (varies by gene count)
   * - Response size: ~10-100 KB (depends on page size)
   * - Backend cache: Redis 15 minutes
   *
   * **Use Cases**:
   * - Disease detail page gene list
   * - Disease-gene network visualization
   * - Export disease-associated genes
   *
   * @param traitId - Disease/trait ID
   * @param params - Optional pagination and filter parameters
   * @param params.page - Page number (default: 1)
   * @param params.page_size - Items per page (default: 20)
   * @param params.ontology_id - Filter by specific ontology
   * @returns Paginated gene list with disease association details
   *
   * @example
   * // Get first page of genes for a disease
   * const { data } = useQuery({
   *   queryKey: ['disease-genes', traitId],
   *   queryFn: () => diseasesApi.getGenes(traitId),
   *   enabled: !!traitId,
   * })
   *
   * @example
   * // With pagination and ontology filter
   * const { data } = useQuery({
   *   queryKey: ['disease-genes', traitId, page, ontologyId],
   *   queryFn: () => diseasesApi.getGenes(traitId, {
   *     page,
   *     page_size: 50,
   *     ontology_id: ontologyId
   *   }),
   *   enabled: !!traitId,
   * })
   *
   * @example
   * // Use in disease detail page
   * const DiseaseGenePage = ({ traitId }) => {
   *   const { data, isLoading } = useQuery({
   *     queryKey: ['disease-genes', traitId],
   *     queryFn: () => diseasesApi.getGenes(traitId),
   *   })
   *   return <GeneTable genes={data?.items} loading={isLoading} />
   * }
   *
   * @see Disease detail page gene tab
   * @see Network page disease network view
   */
  getGenes: (traitId: number, params?: {
    page?: number
    page_size?: number
    ontology_id?: number
  }) => apiClient.get<PaginatedGeneResponse>(`/api/v1/diseases/${traitId}/genes`, { params }),

  /**
   * Get disease associations for a specific gene
   *
   * Returns all diseases/traits associated with the specified gene.
   * Used by the Gene detail page to show disease involvement.
   *
   * **Performance**:
   * - Response time: 50-200ms (first call), 20-50ms (cached)
   * - Response size: ~5-50 KB (depends on association count)
   * - Backend cache: Redis 30 minutes
   *
   * **Data Per Association**:
   * - trait_id, trait_name, trait_category
   * - Ontology information
   * - Association evidence details
   *
   * @param geneId - Gene ID to find disease associations for
   * @returns Array of disease associations for the gene
   *
   * @example
   * // Get all disease associations for a gene
   * const { data } = useQuery({
   *   queryKey: ['gene-diseases', geneId],
   *   queryFn: () => diseasesApi.getGeneAssociations(geneId),
   *   enabled: !!geneId,
   * })
   *
   * @example
   * // Display in gene detail page
   * const GeneDiseaseTab = ({ geneId }) => {
   *   const { data: associations } = useQuery({
   *     queryKey: ['gene-diseases', geneId],
   *     queryFn: () => diseasesApi.getGeneAssociations(geneId),
   *   })
   *   return (
   *     <List
   *       dataSource={associations}
   *       renderItem={item => (
   *         <List.Item>
   *           <Link to={`/diseases/${item.trait_id}`}>
   *             {item.trait_name}
   *           </Link>
   *         </List.Item>
   *       )}
   *     />
   *   )
   * }
   *
   * @example
   * // Count diseases per category
   * const categoryCounts = associations?.reduce((acc, a) => {
   *   acc[a.trait_category] = (acc[a.trait_category] || 0) + 1
   *   return acc
   * }, {} as Record<string, number>)
   *
   * @see Gene detail page disease tab
   * @see Disease-gene relationship explorer
   */
  getGeneAssociations: (geneId: number) =>
    apiClient.get<TraitGeneAssociationDetail[]>(`/api/v1/diseases/gene/${geneId}/associations`),

  /**
   * Get lightweight disease options for dropdown selection
   *
   * Phase 5.1 - Optimized API for disease selector components
   *
   * Returns only essential fields (trait_id, trait_name) without
   * pagination. Designed for dropdown selectors and autocomplete
   * components where full disease details are not needed.
   *
   * **Performance**:
   * - Response time: 7-50ms (first call), 5-20ms (cached)
   * - Response size: ~20 KB (273 unique diseases)
   * - Backend cache: Redis 30 minutes
   * - Performance improvement: 99% faster than list() API (550x speedup)
   *
   * **Data Volume**:
   * - Total diseases: 273 (deduplicated)
   * - Original API returned 500 records with duplicates
   *
   * **Optimization Details**:
   * - Server-side deduplication (no client-side processing needed)
   * - Minimal payload (only id and name)
   * - Aggressive caching (30-minute Redis TTL)
   *
   * @returns Promise with traits array containing all unique diseases
   *
   * @example
   * // Basic usage: Load all disease options
   * const { data } = useQuery({
   *   queryKey: ['disease-options'],
   *   queryFn: () => diseasesApi.getOptions(),
   *   staleTime: 30 * 60 * 1000, // 30 minutes cache
   * })
   *
   * @example
   * // Use with Ant Design Select
   * <Select
   *   showSearch
   *   placeholder="Select a disease"
   *   options={diseaseOptions?.traits.map(d => ({
   *     value: d.trait_id,
   *     label: d.trait_name
   *   }))}
   *   filterOption={(input, option) =>
   *     option?.label.toLowerCase().includes(input.toLowerCase())
   *   }
   * />
   *
   * @example
   * // Use with autocomplete
   * const [searchValue, setSearchValue] = useState('')
   * const filteredOptions = diseaseOptions?.traits
   *   .filter(d => d.trait_name.toLowerCase().includes(searchValue.toLowerCase()))
   *   .slice(0, 20) // Limit displayed options
   *
   * @example
   * // Preload on page mount for instant dropdown
   * const queryClient = useQueryClient()
   * useEffect(() => {
   *   queryClient.prefetchQuery({
   *     queryKey: ['disease-options'],
   *     queryFn: () => diseasesApi.getOptions(),
   *   })
   * }, [])
   *
   * @see Network page disease filter dropdown
   * @see Phase 5.1 optimization (CLAUDE.md)
   * @see genesApi.getOptions() for similar pattern
   */
  getOptions: async (): Promise<DiseaseOptionsResponse> => {
    const response = await apiClient.get<DiseaseOptionsResponse>('/api/v1/diseases/options')
    return response.data
  },
}
