/**
 * Network API
 *
 * Provides access to network visualization data including gene networks,
 * cross-species comparisons, and disease-related network analysis.
 *
 * Features:
 * - Gene-centric network visualization
 * - Cross-species regulatory network comparison
 * - Disease-trait network exploration
 * - Available combination discovery for disease networks
 *
 * @module api/network
 */
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
  /**
   * Get gene-centric regulatory network for visualization
   *
   * Returns a network graph centered on a specific gene, showing its
   * regulatory relationships with other genes. Used by the Network
   * page to visualize lncRNA-protein coding gene interactions.
   *
   * **Performance**:
   * - Response time: 100-500ms (depends on network size)
   * - Response size: ~10-500 KB (varies by depth and filters)
   * - Backend cache: Redis 15 minutes
   *
   * @param geneId - The gene ID to center the network on
   * @param params - Optional query parameters
   * @param params.species_id - Filter by species (1=Human, 2=Chimp, 3=Macaque, 4=Marmoset)
   * @param params.min_ba - Minimum binding affinity threshold (default: 0)
   * @param params.max_distance - Maximum genomic distance in bp
   * @param params.depth - Network expansion depth (default: 1)
   * @returns Network data with nodes (genes) and edges (regulations)
   *
   * @example
   * // Basic usage: Get network for gene ID 1
   * const { data } = useQuery({
   *   queryKey: ['gene-network', geneId],
   *   queryFn: () => networkApi.getGeneNetwork(geneId),
   *   staleTime: 10 * 60 * 1000,
   * })
   *
   * @example
   * // With filters: Human species, min BA of 100
   * const { data } = useQuery({
   *   queryKey: ['gene-network', geneId, { species_id: 1, min_ba: 100 }],
   *   queryFn: () => networkApi.getGeneNetwork(geneId, {
   *     species_id: 1,
   *     min_ba: 100,
   *     depth: 2
   *   }),
   * })
   *
   * @see NetworkPage component for visualization implementation
   * @see GeneDetail page for gene-specific network view
   */
  getGeneNetwork: (geneId: number, params?: {
    species_id?: number
    min_ba?: number
    max_distance?: number
    depth?: number
  }, signal?: AbortSignal) =>
    apiClient.get<APINetworkData>(`/api/v1/network/gene/${geneId}`, { params, signal }),

  /**
   * Compare regulatory networks across species for a lncRNA
   *
   * Phase 7.0 - Cross-species network comparison feature
   *
   * Retrieves regulatory targets for a lncRNA across all 4 primate species,
   * identifying conserved and species-specific regulatory relationships.
   * Essential for evolutionary analysis of lncRNA function.
   *
   * **Performance**:
   * - Response time: 200-800ms (first call), 50-150ms (cached)
   * - Response size: ~20-100 KB (depends on target count)
   * - Backend cache: Redis 30 minutes
   * - Cache acceleration: ~67x faster with cache hit
   *
   * **Data Structure**:
   * - Returns species_networks keyed by species_id (1-4)
   * - Each network contains target genes with binding affinity
   * - Includes conserved_targets (genes regulated in multiple species)
   *
   * @param lncrnaGeneId - The lncRNA gene ID to compare across species
   * @param params - Optional comparison parameters
   * @param params.min_ba - Minimum binding affinity threshold
   * @param params.max_targets_per_species - Limit targets per species (default: 100)
   * @returns Cross-species comparison data with conserved target analysis
   *
   * @example
   * // Basic usage: Compare lncRNA across all species
   * const { data } = useQuery({
   *   queryKey: ['species-comparison', lncrnaGeneId],
   *   queryFn: () => networkApi.compareSpecies(lncrnaGeneId),
   *   staleTime: 15 * 60 * 1000,
   * })
   *
   * @example
   * // With filters: Only high-affinity interactions
   * const { data } = useQuery({
   *   queryKey: ['species-comparison', lncrnaGeneId, minBA],
   *   queryFn: () => networkApi.compareSpecies(lncrnaGeneId, {
   *     min_ba: 150,
   *     max_targets_per_species: 50
   *   }),
   * })
   *
   * @see Network page Cross-Species Comparison drawer
   * @see OrthologBrowser component for related functionality
   */
  compareSpecies: (lncrnaGeneId: number, params?: CompareParams, signal?: AbortSignal) =>
    apiClient.get<SpeciesNetworkComparison>('/api/v1/network/compare', {
      params: { lncrna_gene_id: lncrnaGeneId, ...params },
      signal
    }),

  /**
   * Get available disease-ontology-species combinations
   *
   * Returns all valid combinations of trait_id, ontology_id, and species_id
   * that have associated network data. Used to populate filter dropdowns
   * on the Disease Network page.
   *
   * **Performance**:
   * - Response time: 50-150ms (first call), 10-30ms (cached)
   * - Response size: ~5-20 KB
   * - Backend cache: Redis 30 minutes
   *
   * @param speciesId - Optional species filter (1=Human, 2=Chimp, 3=Macaque, 4=Marmoset)
   * @returns List of available trait-ontology-species combinations
   *
   * @example
   * // Get all available combinations
   * const { data } = useQuery({
   *   queryKey: ['available-combinations'],
   *   queryFn: () => networkApi.getAvailableCombinations(),
   *   staleTime: 30 * 60 * 1000,
   * })
   *
   * @example
   * // Filter by species
   * const { data } = useQuery({
   *   queryKey: ['available-combinations', speciesId],
   *   queryFn: () => networkApi.getAvailableCombinations(speciesId),
   *   enabled: !!speciesId,
   * })
   *
   * @see Network page disease filter implementation
   */
  getAvailableCombinations: (speciesId?: number, signal?: AbortSignal) =>
    apiClient.get<AvailableCombinationsResponse>('/api/v1/network/available-combinations', {
      params: speciesId ? { species_id: speciesId } : undefined,
      signal
    }),

  /**
   * Get disease-centric regulatory network
   *
   * Retrieves a network graph showing lncRNA-gene relationships
   * associated with a specific disease/trait. Enables exploration
   * of disease-related regulatory mechanisms.
   *
   * **Performance**:
   * - Response time: 200-1000ms (varies by network complexity)
   * - Response size: ~50-500 KB
   * - Backend cache: Redis 15 minutes
   *
   * **Network Structure**:
   * - Nodes: lncRNA and protein-coding genes
   * - Edges: Regulatory relationships with binding affinity
   * - Stats: Node counts, edge counts, trait/ontology info
   *
   * @param params - Disease network query parameters
   * @param params.trait_id - Disease/trait ID (required)
   * @param params.ontology_id - Ontology ID (required)
   * @param params.species_id - Filter by species (optional)
   * @param params.min_ba - Minimum binding affinity threshold
   * @param params.max_nodes - Maximum number of nodes to return
   * @param params.max_edges - Maximum number of edges to return
   * @returns Network data optimized for disease visualization
   *
   * @example
   * // Basic usage: Get disease network
   * const { data } = useQuery({
   *   queryKey: ['disease-network', traitId, ontologyId],
   *   queryFn: () => networkApi.getDiseaseNetwork({
   *     trait_id: traitId,
   *     ontology_id: ontologyId
   *   }),
   *   enabled: !!traitId && !!ontologyId,
   * })
   *
   * @example
   * // With all parameters
   * const { data } = useQuery({
   *   queryKey: ['disease-network', params],
   *   queryFn: () => networkApi.getDiseaseNetwork({
   *     trait_id: 123,
   *     ontology_id: 456,
   *     species_id: 1,
   *     min_ba: 100,
   *     max_nodes: 200,
   *     max_edges: 500
   *   }),
   * })
   *
   * @see Network page disease network tab
   * @see Sankey Flow visualization for alternative disease view
   */
  getDiseaseNetwork: (params: DiseaseNetworkParams, signal?: AbortSignal) =>
    apiClient.get<NetworkData>('/api/v1/network/disease', { params, signal }),

  /**
   * Get detailed gene information for network context
   *
   * Retrieves comprehensive gene details including conservation info,
   * connection statistics, and genomic location. Used by the network
   * visualization to display gene tooltips and detail panels.
   *
   * **Performance**:
   * - Response time: 50-100ms
   * - Response size: ~1-2 KB
   * - Backend cache: Redis 30 minutes
   *
   * **Data Includes**:
   * - Basic info: name, ensembl_id, type, species
   * - Location: chromosome, start, end, strand
   * - Conservation: core_id, conservation_label, species count
   * - Connections: source/target counts, total BA
   *
   * @param geneId - Gene ID to fetch details for
   * @returns Detailed gene information for network context
   *
   * @example
   * // Fetch gene detail on node click
   * const { data, isLoading } = useQuery({
   *   queryKey: ['gene-detail-network', geneId],
   *   queryFn: () => networkApi.getGeneDetail(geneId),
   *   enabled: !!geneId,
   * })
   *
   * @example
   * // Use in network node tooltip
   * const handleNodeClick = async (nodeId: number) => {
   *   const { data } = await networkApi.getGeneDetail(nodeId)
   *   setSelectedGene(data)
   * }
   *
   * @see Network page node detail panel
   * @see GeneDetail page for full gene information
   */
  getGeneDetail: (geneId: number, signal?: AbortSignal) =>
    apiClient.get<GeneDetail>(`/api/v1/network/gene/${geneId}/detail`, { signal }),
}
