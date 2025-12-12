import { apiClient } from './client'
import type {
  components,
  BARange,
  DetailedStatsResponse,
  TopGene,
  TopDisease,
  ConservedRegulation,
  CacheStats,
  TopGenesParams,
  TopDiseasesParams,
  ConservedRegulationsParams,
} from '@/types'

type OverviewStats = components['schemas']['OverviewStats']

export const statsApi = {
  /**
   * Get overview statistics
   * @returns Overview stats including total counts
   */
  overview: () => apiClient.get<OverviewStats>('/api/v1/stats/overview'),

  /**
   * Get BA (binding affinity) range
   * Used for dynamically setting filter ranges
   */
  baRange: () => apiClient.get<BARange>('/api/v1/stats/ba-range'),

  /**
   * Get detailed statistics
   * Used for Stats page charts
   * @param params.buckets - Number of BA distribution buckets
   * @param params.top_limit - Number of top lncRNAs to return
   */
  detailed: (params?: { buckets?: number; top_limit?: number }) =>
    apiClient.get<DetailedStatsResponse>('/api/v1/stats/detailed', { params }),

  /**
   * Get top genes by regulation count
   * @param params.limit - Number of genes to return (default: 10)
   * @param params.gene_type - Filter by gene type (lncRNA/protein_coding)
   */
  topGenes: (params?: TopGenesParams) =>
    apiClient.get<TopGene[]>('/api/v1/stats/top-genes', { params }),

  /**
   * Get top diseases by gene association count
   * @param params.limit - Number of diseases to return (default: 10)
   */
  topDiseases: (params?: TopDiseasesParams) =>
    apiClient.get<TopDisease[]>('/api/v1/stats/top-diseases', { params }),

  /**
   * Get conserved regulations across species
   * @param params.min_species - Minimum species count (default: 2)
   * @param params.limit - Number of results (default: 100)
   */
  conservedRegulations: (params?: ConservedRegulationsParams) =>
    apiClient.get<ConservedRegulation[]>('/api/v1/stats/conserved-regulations', { params }),

  /**
   * Get cache status information
   * @returns Cache connection status and metrics
   */
  cacheStatus: () => apiClient.get<CacheStats>('/api/v1/stats/cache-status'),
}
