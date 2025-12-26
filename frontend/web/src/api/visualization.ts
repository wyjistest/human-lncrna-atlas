/**
 * Visualization API Client
 *
 * Provides APIs for advanced visualization components including Sankey flow
 * diagrams that display lncRNA regulatory network relationships. This module
 * enables querying complex three-layer network data (lncRNA -> Gene -> Disease).
 *
 * Key features:
 * - Sankey flow diagram data for regulatory network visualization
 * - Multi-layer network structure (lncRNA, Gene, Disease)
 * - Species and disease filtering
 * - Binding affinity threshold filtering
 * - Network statistics and node counting
 *
 * **Data Volume**:
 * - Total regulations: 804,630
 * - Diseases with associations: 273
 * - Average nodes per query: 50-200
 *
 * @module api/visualization
 * @see Sankey Flow page at /src/pages/Visualization/SankeyFlow
 * @see Phase 5.3 Sankey Flow documentation
 */

import { apiClient } from './client'

// =============================================================================
// Type Definitions
// =============================================================================

/**
 * Sankey node representing an entity in the regulatory network
 *
 * Nodes are organized into three layers:
 * - Layer 0: lncRNA (long non-coding RNA)
 * - Layer 1: Gene (target gene)
 * - Layer 2: Disease (associated disease/trait)
 *
 * @example
 * {
 *   id: "lncrna_1234",
 *   name: "MALAT1",
 *   layer: 0
 * }
 */
export interface SankeyNode {
  /**
   * Unique identifier for the node
   * Format: "{type}_{id}" (e.g., "lncrna_1234", "gene_5678", "disease_91")
   */
  id: string
  /** Display name shown in the visualization */
  name: string
  /**
   * Layer in the Sankey diagram
   * - 0: lncRNA (source layer, left side)
   * - 1: Gene (middle layer)
   * - 2: Disease (target layer, right side)
   */
  layer: number
}

/**
 * Sankey link representing flow/connection between nodes
 *
 * Links connect nodes across layers to show regulatory relationships:
 * - lncRNA -> Gene: Represents regulatory relationship with binding affinity
 * - Gene -> Disease: Represents disease association with -log10(p-value)
 *
 * @example
 * {
 *   source: "lncrna_1234",
 *   target: "gene_5678",
 *   value: 85.5,
 *   flow_count: 3
 * }
 */
export interface SankeyLink {
  /** Source node ID (must exist in nodes array) */
  source: string
  /** Target node ID (must exist in nodes array) */
  target: string
  /**
   * Flow value representing connection strength
   * - For lncRNA->Gene: Binding Affinity (BA) value (0-200+)
   * - For Gene->Disease: -log10(p-value) scaled value
   */
  value: number
  /** Number of individual connections this aggregated flow represents */
  flow_count: number
}

/**
 * Response structure for Sankey data API
 *
 * Contains all data needed to render a Sankey flow diagram including
 * nodes, links, query parameters, and network statistics.
 */
export interface SankeyResponse {
  /** All nodes in the network (lncRNA, Gene, Disease entities) */
  nodes: SankeyNode[]
  /** All links/flows between nodes */
  links: SankeyLink[]
  /** Query parameters echoed back for reference */
  query_params: {
    /** Species filter applied (null if not filtered) */
    species_id: number | null
    /** Minimum BA threshold applied (null if not filtered) */
    min_ba: number | null
    /** Disease name filter applied (null if not filtered) */
    trait_name: string | null
    /** Node limit applied */
    limit: number
  }
  /** Aggregated statistics about the returned data */
  statistics: {
    /** Total number of nodes across all layers */
    total_nodes: number
    /** Total number of links/connections */
    total_links: number
    /** Number of lncRNA nodes (layer 0) */
    lncrna_count: number
    /** Number of gene nodes (layer 1) */
    gene_count: number
    /** Number of disease nodes (layer 2) */
    disease_count: number
  }
}

/**
 * Query parameters for Sankey data API
 */
export interface SankeyQueryParams {
  /**
   * Filter by species
   * - 1: Human
   * - 2: Chimpanzee
   * - 3: Macaque
   * - 4: Marmoset
   */
  species_id?: number
  /** Minimum binding affinity threshold (0-200+) */
  min_ba?: number
  /** Filter by disease/trait name (partial match, case-insensitive) */
  trait_name?: string
  /** Maximum number of nodes to return (default: 100, max: 500) */
  limit?: number
}

/**
 * Backend response structure for Sankey data API
 * This matches the actual structure returned by the backend
 * (differs from frontend SankeyResponse for transformation)
 */
interface BackendSankeyResponse {
  success: boolean
  data: {
    nodes: SankeyNode[]
    links: SankeyLink[]
  }
  stats: {
    total_lncrnas: number
    total_genes: number
    total_diseases: number
  }
  query_params: {
    species_id: number | null
    min_ba: number | null
    trait_name: string | null
    limit: number
  }
}

// =============================================================================
// API Endpoints
// =============================================================================

/**
 * Visualization API endpoints
 *
 * Provides methods for fetching advanced visualization data
 * including Sankey flow diagrams and network statistics.
 */
export const visualizationApi = {
  /**
   * Get Sankey flow diagram data showing lncRNA -> Gene -> Disease connections
   *
   * Returns a three-layer network structure suitable for rendering as a Sankey
   * flow diagram. The data shows how lncRNAs regulate genes which are associated
   * with diseases, with flow width representing connection strength.
   *
   * **Network Structure**:
   * ```
   * lncRNA (Layer 0) --> Gene (Layer 1) --> Disease (Layer 2)
   *     |                    |                   |
   *   Blue               Green               Red
   *     |                    |                   |
   *  BA value          -log10(pval)         Count
   * ```
   *
   * **Performance**:
   * - Response time: 500ms - 2s (varies by filters and limit)
   * - Response size: ~50-200 KB
   * - Backend cache: Redis 10 minutes
   *
   * **Data Aggregation**:
   * - Multiple lncRNA-gene pairs are aggregated by average BA
   * - Gene-disease links use -log10(p-value) for weight
   * - Flow count indicates number of underlying connections
   *
   * @param params - Query parameters for filtering and limiting results
   * @param params.species_id - Filter by species (1=Human, 2=Chimp, 3=Macaque, 4=Marmoset)
   * @param params.min_ba - Minimum binding affinity threshold (default: 100)
   * @param params.trait_name - Filter by disease/trait name (partial match)
   * @param params.limit - Maximum nodes to return (default: 100, max: 500)
   * @returns Promise with Sankey diagram data including nodes, links, and statistics
   *
   * @example
   * // Basic usage: Get default Sankey data
   * const { data } = useQuery({
   *   queryKey: ['sankey-data'],
   *   queryFn: () => visualizationApi.getSankeyData(),
   *   staleTime: 10 * 60 * 1000,
   * })
   *
   * @example
   * // Filtered by species and minimum BA
   * const { data } = useQuery({
   *   queryKey: ['sankey-data', { species_id: 1, min_ba: 100 }],
   *   queryFn: () => visualizationApi.getSankeyData({
   *     species_id: 1, // Human only
   *     min_ba: 100,   // High affinity only
   *     limit: 200,
   *   }),
   * })
   *
   * @example
   * // Filtered by disease
   * const { data } = useQuery({
   *   queryKey: ['sankey-data', { trait_name: 'diabetes' }],
   *   queryFn: () => visualizationApi.getSankeyData({
   *     trait_name: 'diabetes',
   *     limit: 150,
   *   }),
   * })
   *
   * @example
   * // Using with ECharts Sankey
   * const { data } = await visualizationApi.getSankeyData({ limit: 100 })
   *
   * const option = {
   *   series: [{
   *     type: 'sankey',
   *     data: data.nodes.map(n => ({ name: n.id, label: n.name })),
   *     links: data.links.map(l => ({
   *       source: l.source,
   *       target: l.target,
   *       value: l.value,
   *     })),
   *   }],
   * }
   *
   * @see SankeyFlow page component at /src/pages/Visualization/SankeyFlow
   * @see ECharts Sankey documentation
   * @see Phase 5.3 Visualization documentation
   */
  getSankeyData: async (params?: SankeyQueryParams, signal?: AbortSignal): Promise<SankeyResponse> => {
    const response = await apiClient.get<BackendSankeyResponse>(
      '/api/v1/visualization/sankey-data',
      { params, signal }
    )

    // Backend returns: { success, data: { nodes, links }, stats, query_params }
    // Transform to expected frontend format for consistency
    const raw = response.data

    return {
      nodes: raw.data?.nodes || [],
      links: raw.data?.links || [],
      query_params: raw.query_params || {
        species_id: null,
        min_ba: null,
        trait_name: null,
        limit: 100
      },
      statistics: {
        total_nodes: (raw.data?.nodes?.length || 0),
        total_links: (raw.data?.links?.length || 0),
        lncrna_count: raw.stats?.total_lncrnas || 0,
        gene_count: raw.stats?.total_genes || 0,
        disease_count: raw.stats?.total_diseases || 0,
      }
    }
  },
}

// =============================================================================
// Utility Types for Visualization Components
// =============================================================================

/**
 * Color scheme for Sankey node layers
 *
 * Default colors follow the project's visualization guidelines:
 * - lncRNA: Blue (#4096ff) - Primary regulatory elements
 * - Gene: Green (#52c41a) - Target genes
 * - Disease: Red (#ff4d4f) - Disease outcomes
 */
export const SANKEY_LAYER_COLORS = {
  lncrna: '#4096ff',
  gene: '#52c41a',
  disease: '#ff4d4f',
} as const

/**
 * Get color for a Sankey node based on its layer
 *
 * @param layer - Node layer (0, 1, or 2)
 * @returns Hex color code for the layer
 *
 * @example
 * const color = getSankeyNodeColor(0) // Returns '#4096ff' (blue for lncRNA)
 */
export function getSankeyNodeColor(layer: number): string {
  switch (layer) {
    case 0:
      return SANKEY_LAYER_COLORS.lncrna
    case 1:
      return SANKEY_LAYER_COLORS.gene
    case 2:
      return SANKEY_LAYER_COLORS.disease
    default:
      return '#808080' // Gray fallback
  }
}

/**
 * Get layer name for display purposes
 *
 * @param layer - Node layer (0, 1, or 2)
 * @returns Human-readable layer name
 *
 * @example
 * const name = getSankeyLayerName(0) // Returns 'LncRNA'
 */
export function getSankeyLayerName(layer: number): string {
  switch (layer) {
    case 0:
      return 'LncRNA'
    case 1:
      return 'Gene'
    case 2:
      return 'Disease'
    default:
      return 'Unknown'
  }
}

export default visualizationApi
