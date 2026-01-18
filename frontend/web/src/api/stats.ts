/**
 * Stats API
 *
 * Provides access to platform statistics, analytics, and system metrics.
 * Used by dashboard pages, stats visualizations, and admin monitoring.
 *
 * Features:
 * - Overview statistics (totals, counts)
 * - Binding affinity distribution and ranges
 * - Top genes and diseases rankings
 * - Cross-species conservation analysis
 * - Cache status monitoring
 *
 * @module api/stats
 */
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
   * Get platform overview statistics
   *
   * Returns high-level counts for all major entities in the database.
   * Used by the home page dashboard and stats summary cards.
   *
   * **Performance**:
   * - Response time: 50-100ms (first call), 10-30ms (cached)
   * - Response size: ~500 bytes
   * - Backend cache: Redis 30 minutes
   *
   * **Data Includes**:
   * - Total genes count (by type: lncRNA, protein_coding)
   * - Total regulations count
   * - Total diseases/traits count
   * - Species breakdown
   *
   * @returns Overview statistics with entity counts
   *
   * @example
   * // Display dashboard stats
   * const { data } = useQuery({
   *   queryKey: ['stats-overview'],
   *   queryFn: () => statsApi.overview(),
   *   staleTime: 30 * 60 * 1000, // 30 minutes
   * })
   *
   * @example
   * // Use in stats cards
   * const { data: stats } = useQuery({
   *   queryKey: ['overview'],
   *   queryFn: () => statsApi.overview(),
   * })
   * // stats.data contains: { gene_count, regulation_count, ... }
   *
   * @see Home page dashboard cards
   * @see Stats page summary section
   */
  overview: (signal?: AbortSignal) => apiClient.get<OverviewStats>('/api/v1/stats/overview', { signal }),

  /**
   * Get binding affinity (BA) range statistics
   *
   * Returns the minimum and maximum binding affinity values across
   * all regulations. Used to dynamically configure filter sliders
   * and validate user input ranges.
   *
   * **Performance**:
   * - Response time: 30-80ms (first call), 10-20ms (cached)
   * - Response size: ~100 bytes
   * - Backend cache: Redis 60 minutes
   *
   * **Use Cases**:
   * - Set slider min/max bounds
   * - Validate filter inputs
   * - Display data range to users
   *
   * @returns BA range with min and max values
   *
   * @example
   * // Configure BA filter slider
   * const { data } = useQuery({
   *   queryKey: ['ba-range'],
   *   queryFn: () => statsApi.baRange(),
   *   staleTime: 60 * 60 * 1000, // 1 hour (rarely changes)
   * })
   * // data: { min: 0, max: 500 }
   *
   * @example
   * // Use with Ant Design Slider
   * <Slider
   *   min={baRange?.min ?? 0}
   *   max={baRange?.max ?? 500}
   *   value={[minBA, maxBA]}
   *   onChange={handleBAChange}
   * />
   *
   * @see Network page BA filter
   * @see Regulations table filter panel
   */
  baRange: (signal?: AbortSignal) => apiClient.get<BARange>('/api/v1/stats/ba-range', { signal }),

  /**
   * Get detailed statistics with distributions
   *
   * Returns comprehensive statistics including BA distribution
   * histograms and top lncRNA rankings. Used by the Stats page
   * for detailed charts and analysis.
   *
   * **Performance**:
   * - Response time: 100-300ms (first call), 50-100ms (cached)
   * - Response size: ~5-20 KB (depends on bucket count)
   * - Backend cache: Redis 30 minutes
   *
   * **Data Includes**:
   * - BA distribution histogram (configurable buckets)
   * - Top lncRNAs by regulation count
   * - Species distribution
   * - Gene type distribution
   *
   * @param params - Optional query parameters
   * @param params.buckets - Number of histogram buckets (default: 20)
   * @param params.top_limit - Number of top lncRNAs to return (default: 10)
   * @returns Detailed statistics with distribution data
   *
   * @example
   * // Basic usage with defaults
   * const { data } = useQuery({
   *   queryKey: ['stats-detailed'],
   *   queryFn: () => statsApi.detailed(),
   *   staleTime: 15 * 60 * 1000,
   * })
   *
   * @example
   * // Custom histogram resolution
   * const { data } = useQuery({
   *   queryKey: ['stats-detailed', { buckets: 50, top_limit: 20 }],
   *   queryFn: () => statsApi.detailed({
   *     buckets: 50,
   *     top_limit: 20
   *   }),
   * })
   *
   * @example
   * // Use for ECharts histogram
   * const chartData = data?.ba_distribution.map(bucket => ({
   *   name: bucket.range,
   *   value: bucket.count
   * }))
   *
   * @see Stats page charts section
   * @see BA distribution histogram component
   */
  detailed: (params?: { buckets?: number; top_limit?: number }, signal?: AbortSignal) =>
    apiClient.get<DetailedStatsResponse>('/api/v1/stats/detailed', { params, signal }),

  /**
   * Get top genes ranked by regulation count
   *
   * Returns genes with the most regulatory relationships,
   * indicating highly connected hub genes in the network.
   * Useful for identifying key regulatory nodes.
   *
   * **Performance**:
   * - Response time: 50-150ms (first call), 20-50ms (cached)
   * - Response size: ~2-10 KB (depends on limit)
   * - Backend cache: Redis 30 minutes
   * - Cache acceleration: ~24x faster with cache hit
   *
   * **Data Per Gene**:
   * - gene_id, core_id, gene_name
   * - gene_type (lncRNA/protein_coding)
   * - species_name
   * - regulation_count (total connections)
   *
   * @param params - Optional query parameters
   * @param params.limit - Number of genes to return (default: 10, max: 100)
   * @param params.gene_type - Filter by type ('lncRNA' or 'protein_coding')
   * @returns Array of top genes sorted by regulation count
   *
   * @example
   * // Get top 10 genes (default)
   * const { data } = useQuery({
   *   queryKey: ['top-genes'],
   *   queryFn: () => statsApi.topGenes(),
   *   staleTime: 15 * 60 * 1000,
   * })
   *
   * @example
   * // Get top 20 lncRNAs only
   * const { data } = useQuery({
   *   queryKey: ['top-genes', 'lncRNA', 20],
   *   queryFn: () => statsApi.topGenes({
   *     limit: 20,
   *     gene_type: 'lncRNA'
   *   }),
   * })
   *
   * @example
   * // Display in ranking table
   * <Table
   *   dataSource={topGenes}
   *   columns={[
   *     { title: 'Rank', render: (_, __, i) => i + 1 },
   *     { title: 'Gene', dataIndex: 'gene_name' },
   *     { title: 'Regulations', dataIndex: 'regulation_count' },
   *   ]}
   * />
   *
   * @see Stats page top genes section
   * @see Home page highlights
   */
  topGenes: (params?: TopGenesParams, signal?: AbortSignal) =>
    apiClient.get<TopGene[]>('/api/v1/stats/top-genes', { params, signal }),

  /**
   * Get top diseases ranked by gene association count
   *
   * Returns diseases/traits with the most associated genes,
   * highlighting conditions with broad regulatory involvement.
   * Useful for disease research prioritization.
   *
   * **Performance**:
   * - Response time: 50-150ms (first call), 20-50ms (cached)
   * - Response size: ~2-10 KB (depends on limit)
   * - Backend cache: Redis 30 minutes
   * - Cache acceleration: ~41x faster with cache hit
   *
   * **Data Per Disease**:
   * - trait_id, trait_name
   * - trait_category (disease classification)
   * - gene_count (total associated genes)
   * - lncrna_count (associated lncRNAs specifically)
   *
   * @param params - Optional query parameters
   * @param params.limit - Number of diseases to return (default: 10, max: 100)
   * @returns Array of top diseases sorted by gene count
   *
   * @example
   * // Get top 10 diseases (default)
   * const { data } = useQuery({
   *   queryKey: ['top-diseases'],
   *   queryFn: () => statsApi.topDiseases(),
   *   staleTime: 15 * 60 * 1000,
   * })
   *
   * @example
   * // Get top 50 diseases
   * const { data } = useQuery({
   *   queryKey: ['top-diseases', 50],
   *   queryFn: () => statsApi.topDiseases({ limit: 50 }),
   * })
   *
   * @example
   * // Display in bar chart
   * const chartData = topDiseases?.map(d => ({
   *   name: d.trait_name,
   *   genes: d.gene_count,
   *   lncRNAs: d.lncrna_count
   * }))
   *
   * @see Stats page top diseases section
   * @see Disease exploration page
   */
  topDiseases: (params?: TopDiseasesParams, signal?: AbortSignal) =>
    apiClient.get<TopDisease[]>('/api/v1/stats/top-diseases', { params, signal }),

  /**
   * Get conserved regulatory relationships across species
   *
   * Returns lncRNA-target gene pairs that are conserved across
   * multiple primate species. Essential for evolutionary analysis
   * and identifying functionally important regulations.
   *
   * **Performance**:
   * - Response time: 100-500ms (first call), 30-100ms (cached)
   * - Response size: ~10-100 KB (depends on limit)
   * - Backend cache: Redis 30 minutes
   *
   * **Conservation Levels**:
   * - 4 species: Highly conserved (across all primates)
   * - 3 species: Well conserved
   * - 2 species: Moderately conserved
   *
   * **Data Per Regulation**:
   * - lncrna_core_id, lncrna_name
   * - target_core_id, target_name
   * - species_count, species_list
   * - avg_binding_affinity
   *
   * @param params - Optional query parameters
   * @param params.min_species - Minimum species count (default: 2, max: 4)
   * @param params.limit - Number of results to return (default: 100)
   * @returns Array of conserved regulations with species details
   *
   * @example
   * // Get regulations conserved in at least 2 species
   * const { data } = useQuery({
   *   queryKey: ['conserved-regulations'],
   *   queryFn: () => statsApi.conservedRegulations(),
   *   staleTime: 15 * 60 * 1000,
   * })
   *
   * @example
   * // Get only highly conserved (all 4 species)
   * const { data } = useQuery({
   *   queryKey: ['conserved-regulations', { min_species: 4 }],
   *   queryFn: () => statsApi.conservedRegulations({
   *     min_species: 4,
   *     limit: 50
   *   }),
   * })
   *
   * @example
   * // Filter by conservation level
   * const highlyConserved = data?.filter(r => r.species_count === 4)
   * const humanChimpOnly = data?.filter(r =>
   *   r.species_list.includes('Human') &&
   *   r.species_list.includes('Chimp') &&
   *   r.species_count === 2
   * )
   *
   * @see Conservation page analysis
   * @see Stats page conservation section
   */
  conservedRegulations: (params?: ConservedRegulationsParams, signal?: AbortSignal) =>
    apiClient.get<ConservedRegulation[]>('/api/v1/stats/conserved-regulations', { params, signal }),

  /**
   * Get cache status and observability stats
   *
   * Returns cache health information (backend + connectivity) and lightweight
   * observability stats (hit/miss, namespaces/keys top). Used for monitoring
   * and debugging cache-related issues.
   *
   * **Performance**:
   * - Response time: 10-30ms (direct Redis query)
   * - Response size: ~1-5 KB (depends on tracked namespaces/keys)
   * - No caching (always live data)
   *
   * **Metrics Returned**:
   * - backend/enabled/hits/misses/hit_rate_pct
   * - namespaces: top namespaces + compute timing
   * - keys: top cache keys (bounded, best-effort)
   *
   * @returns Cache status with connection and usage metrics
   *
   * @example
   * // Monitor cache health
   * const { data } = useQuery({
   *   queryKey: ['cache-status'],
   *   queryFn: () => statsApi.cacheStatus(),
   *   refetchInterval: 30 * 1000, // Refresh every 30s
   * })
   *
   * @example
   * // Display cache status indicator
   * <Badge
   *   status={cacheStatus?.connected ? 'success' : 'error'}
   *   text={cacheStatus?.connected ? 'Connected' : 'Disconnected'}
   * />
   * <Statistic
   *   title="Memory Used"
   *   value={cacheStatus?.memory_used_mb}
   *   suffix="MB"
   * />
   *
   * @example
   * // Alert on cache issues
   * useEffect(() => {
   *   if (cacheStatus && !cacheStatus.connected) {
   *     notification.warning({
   *       message: 'Cache Offline',
   *       description: 'Redis cache is not available. Performance may be degraded.'
   *     })
   *   }
   * }, [cacheStatus])
   *
   * @see Admin monitoring dashboard
   * @see System health page
   */
  cacheStatus: (signal?: AbortSignal) => apiClient.get<CacheStats>('/api/v1/stats/cache-status', { signal }),
}
