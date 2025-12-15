/**
 * Clustering API Client
 *
 * Provides APIs for hierarchical clustering analysis and clustered heatmap generation.
 *
 * @module api/clustering
 */

import { apiClient } from './client'
import type { DendrogramData } from '@/components/visualization/DendrogramSVG'

// =============================================================================
// Type Definitions
// =============================================================================

/**
 * Clustering parameters
 */
export interface ClusteringParams {
  /** Data type to cluster: "genes", "samples", "lncrnas" */
  data_type: 'genes' | 'samples' | 'lncrnas'
  /** IDs of entities to cluster */
  entity_ids?: string[]
  /** Species filter (optional) */
  species_id?: number
  /** Clustering method: "ward", "average", "complete", "single" */
  method?: 'ward' | 'average' | 'complete' | 'single'
  /** Distance metric: "euclidean", "correlation", "manhattan" */
  metric?: 'euclidean' | 'correlation' | 'manhattan'
  /** Whether to cluster rows */
  cluster_rows?: boolean
  /** Whether to cluster columns */
  cluster_cols?: boolean
}

/**
 * Clustered heatmap response
 */
export interface ClusteredHeatmapResponse {
  /** Heatmap data matrix (clustered order) */
  data: number[][]
  /** Row labels (in clustered order) */
  row_labels: string[]
  /** Column labels (in clustered order) */
  col_labels: string[]
  /** Row dendrogram data (optional) */
  row_dendrogram?: DendrogramData
  /** Column dendrogram data (optional) */
  col_dendrogram?: DendrogramData
  /** Metadata about the clustering */
  metadata: {
    method: string
    metric: string
    n_rows: number
    n_cols: number
  }
}

// =============================================================================
// API Endpoints
// =============================================================================

/**
 * Clustering API endpoints
 */
export const clusteringApi = {
  /**
   * Get clustered heatmap with hierarchical clustering
   *
   * Performs hierarchical clustering on rows and/or columns and returns
   * a heatmap with data in clustered order along with dendrogram data.
   *
   * **Clustering Methods**:
   * - `ward`: Minimizes variance within clusters (default, recommended)
   * - `average`: Uses average distance between clusters (UPGMA)
   * - `complete`: Uses maximum distance (furthest neighbor)
   * - `single`: Uses minimum distance (nearest neighbor)
   *
   * **Distance Metrics**:
   * - `euclidean`: Straight-line distance (default)
   * - `correlation`: 1 - Pearson correlation
   * - `manhattan`: Sum of absolute differences
   *
   * **Performance**:
   * - Response time: 500ms - 5s (depends on matrix size)
   * - Recommended max: 100 rows × 100 columns
   *
   * @param params - Clustering parameters
   * @returns Promise with clustered heatmap data
   *
   * @example
   * // Cluster genes by expression across samples
   * const { data } = useQuery({
   *   queryKey: ['clustered-heatmap', { data_type: 'genes' }],
   *   queryFn: () => clusteringApi.getClusteredHeatmap({
   *     data_type: 'genes',
   *     entity_ids: ['GENE1', 'GENE2', 'GENE3'],
   *     method: 'ward',
   *     metric: 'euclidean',
   *     cluster_rows: true,
   *     cluster_cols: true,
   *   }),
   * })
   *
   * @example
   * // Cluster lncRNAs by correlation
   * const { data } = await clusteringApi.getClusteredHeatmap({
   *   data_type: 'lncrnas',
   *   species_id: 1,
   *   method: 'average',
   *   metric: 'correlation',
   *   cluster_rows: true,
   *   cluster_cols: false,
   * })
   */
  getClusteredHeatmap: async (params: ClusteringParams): Promise<ClusteredHeatmapResponse> => {
    const response = await apiClient.post('/api/v1/clustering/heatmap-clustered', params)

    // Transform backend response to frontend format
    const raw = response.data as any

    return {
      data: raw.data?.matrix || [],
      row_labels: raw.data?.row_labels || [],
      col_labels: raw.data?.col_labels || [],
      row_dendrogram: raw.data?.row_dendrogram
        ? {
            icoord: raw.data.row_dendrogram.icoord,
            dcoord: raw.data.row_dendrogram.dcoord,
            leaves: raw.data.row_dendrogram.leaves,
          }
        : undefined,
      col_dendrogram: raw.data?.col_dendrogram
        ? {
            icoord: raw.data.col_dendrogram.icoord,
            dcoord: raw.data.col_dendrogram.dcoord,
            leaves: raw.data.col_dendrogram.leaves,
          }
        : undefined,
      metadata: {
        method: raw.metadata?.method || params.method || 'ward',
        metric: raw.metadata?.metric || params.metric || 'euclidean',
        n_rows: raw.data?.row_labels?.length || 0,
        n_cols: raw.data?.col_labels?.length || 0,
      },
    }
  },
}

export default clusteringApi
