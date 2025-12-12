/**
 * Visualization API Client
 *
 * APIs for advanced visualization components like Sankey flow diagrams
 */

import { apiClient } from './client'

/**
 * Sankey node representing lncRNA, Gene, or Disease
 */
export interface SankeyNode {
  /** Unique identifier for the node */
  id: string
  /** Display name */
  name: string
  /** Layer in the Sankey diagram (0=lncRNA, 1=Gene, 2=Disease) */
  layer: number
}

/**
 * Sankey link representing flow from source to target
 */
export interface SankeyLink {
  /** Source node ID */
  source: string
  /** Target node ID */
  target: string
  /** Flow value (e.g., binding affinity or connection strength) */
  value: number
  /** Number of connections this flow represents */
  flow_count: number
}

/**
 * Response structure for Sankey data API
 */
export interface SankeyResponse {
  /** All nodes in the network */
  nodes: SankeyNode[]
  /** All links between nodes */
  links: SankeyLink[]
  /** Query parameters echoed back */
  query_params: {
    species_id: number | null
    min_ba: number | null
    trait_name: string | null
    limit: number
  }
  /** Statistics about the data */
  statistics: {
    total_nodes: number
    total_links: number
    lncrna_count: number
    gene_count: number
    disease_count: number
  }
}

/**
 * Visualization API endpoints
 */
export const visualizationApi = {
  /**
   * Get Sankey flow diagram data showing lncRNA → Gene → Disease connections
   *
   * @param params - Query parameters
   * @param params.species_id - Filter by species (1=Human, 2=Chimp, 3=Macaque, 4=Marmoset)
   * @param params.min_ba - Minimum binding affinity threshold
   * @param params.trait_name - Filter by disease/trait name (partial match)
   * @param params.limit - Maximum number of nodes to return (default: 100)
   * @returns Sankey diagram data with nodes and links
   */
  getSankeyData: async (params?: {
    species_id?: number
    min_ba?: number
    trait_name?: string
    limit?: number
  }): Promise<SankeyResponse> => {
    const response = await apiClient.get('/api/v1/visualization/sankey-data', { params })
    // Backend returns: { success, data: { nodes, links }, stats, query_params }
    // Transform to expected frontend format
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
