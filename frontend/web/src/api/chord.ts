/**
 * Chord Diagram API Client
 *
 * Provides APIs for querying lncRNA-Gene chord diagram data showing
 * regulatory relationships as circular network connections.
 *
 * @module api/chord
 */

import { apiClient } from './client'

// =============================================================================
// Type Definitions
// =============================================================================

/**
 * Chord diagram node representing lncRNA or Gene
 *
 * @example
 * {
 *   id: "lncrna_1234",
 *   name: "MALAT1",
 *   category: "lncrna",
 *   value: 85.5
 * }
 */
export interface ChordNode {
  /** Unique identifier (e.g., "lncrna_1234", "gene_5678") */
  id: string
  /** Display name */
  name: string
  /** Node category: "lncrna" or "gene" */
  category: 'lncrna' | 'gene'
  /** Node value (aggregate binding affinity or degree) */
  value: number
}

/**
 * Chord diagram link representing lncRNA-Gene connection
 *
 * @example
 * {
 *   source: "lncrna_1234",
 *   target: "gene_5678",
 *   value: 85.5
 * }
 */
export interface ChordLink {
  /** Source node ID (lncRNA) */
  source: string
  /** Target node ID (Gene) */
  target: string
  /** Connection strength (binding affinity) */
  value: number
}

/**
 * Chord diagram adjacency matrix (optional, for true chord layout)
 * matrix[i][j] = value from node i to node j
 */
export type ChordMatrix = number[][]

/**
 * Chord diagram statistics
 */
export interface ChordStatistics {
  /** Total number of nodes */
  total_nodes: number
  /** Number of lncRNA nodes */
  lncrna_count: number
  /** Number of gene nodes */
  gene_count: number
  /** Total number of connections */
  total_links: number
}

/**
 * Query parameters for Chord diagram API
 */
export interface ChordQueryParams {
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
  /** Maximum number of nodes to return (default: 50, max: 200) */
  limit?: number
}

/**
 * Response structure for Chord diagram API
 */
export interface ChordResponse {
  /** All nodes in the network */
  nodes: ChordNode[]
  /** All links between nodes */
  links: ChordLink[]
  /** Adjacency matrix (optional) */
  matrix?: ChordMatrix
  /** Query parameters echoed back */
  query_params: {
    species_id: number | null
    min_ba: number | null
    limit: number
  }
  /** Network statistics */
  statistics: ChordStatistics
}

// =============================================================================
// API Endpoints
// =============================================================================

/**
 * Chord Diagram API endpoints
 */
export const chordApi = {
  /**
   * Get Chord diagram data showing lncRNA-Gene regulatory network
   *
   * Returns a circular network structure suitable for rendering as a Chord
   * diagram or circular graph. Shows how lncRNAs connect to genes with
   * binding affinity as connection weight.
   *
   * **Network Structure**:
   * ```
   * lncRNA (Blue) ←→ Gene (Green)
   *     |                |
   *  BA value         Degree
   * ```
   *
   * **Performance**:
   * - Response time: 300ms - 1.5s
   * - Response size: ~20-100 KB
   * - Recommended limit: 50-100 nodes for optimal visualization
   *
   * @param params - Query parameters for filtering
   * @returns Promise with Chord diagram data
   *
   * @example
   * // Basic usage
   * const { data } = useQuery({
   *   queryKey: ['chord-data'],
   *   queryFn: () => chordApi.getChordData(),
   * })
   *
   * @example
   * // Filtered by species and minimum BA
   * const { data } = useQuery({
   *   queryKey: ['chord-data', { species_id: 1, min_ba: 100 }],
   *   queryFn: () => chordApi.getChordData({
   *     species_id: 1,
   *     min_ba: 100,
   *     limit: 80,
   *   }),
   * })
   */
  getChordData: async (params?: ChordQueryParams): Promise<ChordResponse> => {
    const response = await apiClient.get('/api/v1/visualization/chord-data', { params })

    // Transform backend response to frontend format
    const raw = response.data as any

    return {
      nodes: raw.data?.nodes || [],
      links: raw.data?.links || [],
      matrix: raw.data?.matrix,
      query_params: raw.query_params || {
        species_id: null,
        min_ba: null,
        limit: 50,
      },
      statistics: {
        total_nodes: raw.data?.nodes?.length || 0,
        lncrna_count: raw.stats?.lncrna_count || 0,
        gene_count: raw.stats?.gene_count || 0,
        total_links: raw.data?.links?.length || 0,
      },
    }
  },
}

export default chordApi
