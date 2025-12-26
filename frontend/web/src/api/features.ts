/**
 * Features API Client
 *
 * Provides access to genomic feature data including RepeatMasker annotations
 * and feature tracks. This module enables querying repeat elements by gene,
 * region, or species, and managing IGV track configurations.
 *
 * Key features:
 * - Gene-specific RepeatMasker annotations with filtering
 * - Region-based repeat element queries
 * - Feature track management for IGV integration
 * - BED format export for external tools
 * - RepeatMasker class-specific track configurations
 *
 * **Data Volume**:
 * - Total RepeatMasker records: 5,481,341
 * - Supported repeat classes: SINE, LINE, LTR, DNA, Simple, Low_complexity, Other
 *
 * @module api/features
 * @see IGV Browser integration at /src/components/GenomeBrowser
 * @see Phase 6.1 IGV Feature Enhancement documentation
 */
import { apiClient } from './client'
import { API_BASE_URL } from '@/config/api'
import { openInNewTab } from '@/utils/safeWindow'
import type {
  RepeatMaskerResponse,
  RepeatMaskerFilters,
  RepeatStats,
  FeatureTrack,
  FeatureTrackStats,
  FeatureTrackListParams,
  RepeatRegionParams
} from '../types/features'

/**
 * API Response Wrapper
 * Standard wrapper for API responses with success flag and optional message
 */
interface ApiResponse<T> {
  success: boolean
  data: T
  message?: string
}

/**
 * Features API endpoints
 *
 * Provides methods for accessing genomic feature data including
 * RepeatMasker annotations and feature track configurations.
 */
export const featuresApi = {
  // =============================================================================
  // Gene-based RepeatMasker API
  // =============================================================================

  /**
   * Get RepeatMasker annotations for a specific gene
   *
   * Returns paginated repeat element annotations within the genomic region
   * of a specified gene. Supports filtering by repeat class, family,
   * and divergence range.
   *
   * **Performance**:
   * - Response time: 100-300ms (varies by gene size and filters)
   * - Response size: ~50-200 KB per page
   * - Backend cache: Redis 10 minutes
   *
   * @param geneId - Gene ID from the genes table
   * @param filters - Optional filters for repeat class, family, divergence, pagination
   * @param filters.repeat_class - Filter by repeat class (e.g., "SINE", "LINE", "LTR")
   * @param filters.repeat_family - Filter by repeat family (e.g., "Alu", "L1")
   * @param filters.min_divergence - Minimum divergence percentage (0-100)
   * @param filters.max_divergence - Maximum divergence percentage (0-100)
   * @param filters.page - Page number (default: 1)
   * @param filters.page_size - Items per page (default: 50, max: 500)
   * @returns AxiosResponse with RepeatMaskerResponse containing items and pagination
   *
   * @example
   * // Basic usage: Get all repeats for a gene
   * const { data } = useQuery({
   *   queryKey: ['gene-repeats', geneId],
   *   queryFn: () => featuresApi.getGeneRepeats(geneId),
   * })
   *
   * @example
   * // Filtered query: Get only SINE repeats
   * const { data } = useQuery({
   *   queryKey: ['gene-repeats', geneId, 'SINE'],
   *   queryFn: () => featuresApi.getGeneRepeats(geneId, {
   *     repeat_class: 'SINE',
   *     page_size: 100,
   *   }),
   * })
   *
   * @see RepeatMaskerResponse type for response structure
   * @see Gene Detail page RepeatMasker tab
   */
  getGeneRepeats: (geneId: number, filters?: RepeatMaskerFilters, signal?: AbortSignal) =>
    apiClient.get<RepeatMaskerResponse>(`/api/v1/features/genes/${geneId}/repeats`, {
      params: filters,
      signal
    }),

  /**
   * Get RepeatMasker statistics for a specific gene
   *
   * Returns aggregated statistics about repeat elements within a gene's
   * genomic region, including counts and coverage by repeat class.
   *
   * **Performance**:
   * - Response time: 50-150ms
   * - Response size: ~5 KB
   * - Backend cache: Redis 10 minutes
   *
   * @param geneId - Gene ID from the genes table
   * @returns AxiosResponse with RepeatStats containing class-level statistics
   *
   * @example
   * // Get repeat statistics for a gene
   * const { data } = useQuery({
   *   queryKey: ['gene-repeat-stats', geneId],
   *   queryFn: () => featuresApi.getGeneRepeatStats(geneId),
   *   staleTime: 10 * 60 * 1000,
   * })
   *
   * @see RepeatStats type for response structure
   */
  getGeneRepeatStats: (geneId: number, signal?: AbortSignal) =>
    apiClient.get<RepeatStats>(`/api/v1/features/genes/${geneId}/repeats/stats`, { signal }),

  /**
   * Export RepeatMasker data as BED format file
   *
   * Opens a new browser tab/window to download repeat annotations in BED format.
   * The BED file can be loaded into external genome browsers like UCSC or IGV.
   *
   * **File Format**: Standard BED6 with additional columns for repeat info
   * - Columns: chr, start, end, name, score, strand, class, family, divergence
   *
   * **Performance**:
   * - Response time: 500ms - 3s (varies by data volume)
   * - File size: 10KB - 5MB
   *
   * @param geneId - Gene ID from the genes table
   * @param filters - Optional filters (same as getGeneRepeats)
   * @param filters.repeat_class - Filter by repeat class
   * @param filters.repeat_family - Filter by repeat family
   * @param filters.min_divergence - Minimum divergence percentage
   * @param filters.max_divergence - Maximum divergence percentage
   *
   * @example
   * // Export all repeats for a gene
   * const handleExport = () => {
   *   featuresApi.exportRepeatsToBED(geneId)
   * }
   *
   * @example
   * // Export filtered repeats
   * const handleFilteredExport = () => {
   *   featuresApi.exportRepeatsToBED(geneId, {
   *     repeat_class: 'LINE',
   *     max_divergence: 20,
   *   })
   * }
   */
  exportRepeatsToBED: (geneId: number, filters?: RepeatMaskerFilters) => {
    const params = new URLSearchParams()

    if (filters?.repeat_class) params.append('repeat_class', filters.repeat_class)
    if (filters?.repeat_family) params.append('repeat_family', filters.repeat_family)
    if (filters?.min_divergence !== undefined) params.append('min_divergence', String(filters.min_divergence))
    if (filters?.max_divergence !== undefined) params.append('max_divergence', String(filters.max_divergence))

    const queryString = params.toString()
    const url = `${API_BASE_URL}/api/v1/features/genes/${geneId}/repeats/export${queryString ? `?${queryString}` : ''}`
    openInNewTab(url)
  },

  // =============================================================================
  // Feature Tracks API
  // =============================================================================

  /**
   * List all available feature tracks
   *
   * Returns a list of configured feature tracks for IGV integration.
   * Tracks can be filtered by category (e.g., "repeatmasker", "annotation")
   * and active status.
   *
   * **Performance**:
   * - Response time: 30-80ms
   * - Response size: ~10 KB
   * - Backend cache: Redis 30 minutes
   *
   * @param params - Optional filter parameters
   * @param params.category - Filter by track category
   * @param params.active - Filter by active status (true/false)
   * @returns AxiosResponse with array of FeatureTrack objects
   *
   * @example
   * // List all active tracks
   * const { data } = useQuery({
   *   queryKey: ['feature-tracks', { active: true }],
   *   queryFn: () => featuresApi.listTracks({ active: true }),
   *   staleTime: 30 * 60 * 1000,
   * })
   *
   * @example
   * // List RepeatMasker tracks only
   * const { data } = useQuery({
   *   queryKey: ['feature-tracks', 'repeatmasker'],
   *   queryFn: () => featuresApi.listTracks({ category: 'repeatmasker' }),
   * })
   *
   * @see FeatureTrack type for track structure
   * @see IGV configuration components
   */
  listTracks: (params?: FeatureTrackListParams, signal?: AbortSignal) =>
    apiClient.get<FeatureTrack[]>('/api/v1/features/tracks', { params, signal }),

  /**
   * Get details for a specific feature track
   *
   * Returns complete configuration for a single feature track,
   * including URL, format, display settings, and metadata.
   *
   * **Performance**:
   * - Response time: 20-50ms
   * - Response size: ~2 KB
   * - Backend cache: Redis 30 minutes
   *
   * @param trackId - Track ID from the feature_tracks table
   * @returns AxiosResponse with FeatureTrack object
   *
   * @example
   * // Get specific track details
   * const { data } = useQuery({
   *   queryKey: ['feature-track', trackId],
   *   queryFn: () => featuresApi.getTrack(trackId),
   *   enabled: !!trackId,
   * })
   *
   * @see FeatureTrack type for track structure
   */
  getTrack: (trackId: number, signal?: AbortSignal) =>
    apiClient.get<FeatureTrack>(`/api/v1/features/tracks/${trackId}`, { signal }),

  /**
   * Get statistics for all feature tracks
   *
   * Returns feature counts grouped by species for all tracks.
   * Useful for displaying track statistics in management interfaces.
   *
   * **Performance**:
   * - Response time: 100-300ms
   * - Response size: ~15 KB
   * - Backend cache: Redis 30 minutes
   *
   * @returns AxiosResponse with array of FeatureTrackStats objects
   *
   * @example
   * // Get statistics for all tracks
   * const { data } = useQuery({
   *   queryKey: ['feature-track-stats'],
   *   queryFn: () => featuresApi.getTrackStats(),
   *   staleTime: 30 * 60 * 1000,
   * })
   *
   * @see FeatureTrackStats type for statistics structure
   */
  getTrackStats: (signal?: AbortSignal) =>
    apiClient.get<FeatureTrackStats[]>('/api/v1/features/tracks/stats', { signal }),

  // =============================================================================
  // Region-based RepeatMasker API
  // =============================================================================

  /**
   * Get RepeatMasker annotations for a specific genomic region
   *
   * Returns repeat elements within a specified chromosome region.
   * Supports filtering by repeat class and family, with pagination.
   *
   * **Performance**:
   * - Response time: 100-500ms (varies by region size)
   * - Response size: ~20-100 KB per page
   * - Backend cache: Redis 5 minutes
   *
   * **Region Size Limits**:
   * - Maximum region size: 10 Mb
   * - Recommended region size: < 1 Mb for optimal performance
   *
   * @param speciesId - Species ID (1=Human, 2=Chimp, 3=Macaque, 4=Marmoset)
   * @param params - Region coordinates and optional filters
   * @param params.chr - Chromosome name (e.g., "chr1", "chrX")
   * @param params.start - Start position (1-based)
   * @param params.end - End position (1-based)
   * @param params.repeat_class - Filter by repeat class
   * @param params.repeat_family - Filter by repeat family
   * @param params.page - Page number (default: 1)
   * @param params.page_size - Items per page (default: 100)
   * @returns AxiosResponse with RepeatMaskerResponse
   *
   * @example
   * // Get repeats in a region
   * const { data } = useQuery({
   *   queryKey: ['region-repeats', speciesId, chr, start, end],
   *   queryFn: () => featuresApi.getRepeatsByRegion(speciesId, {
   *     chr: 'chr1',
   *     start: 1000000,
   *     end: 2000000,
   *   }),
   * })
   *
   * @example
   * // Get only Alu repeats in a region
   * const { data } = useQuery({
   *   queryKey: ['region-repeats', speciesId, 'Alu'],
   *   queryFn: () => featuresApi.getRepeatsByRegion(speciesId, {
   *     chr: 'chr1',
   *     start: 1000000,
   *     end: 2000000,
   *     repeat_class: 'SINE',
   *     repeat_family: 'Alu',
   *   }),
   * })
   *
   * @see RepeatMaskerResponse type for response structure
   * @see IGV Browser RepeatMasker track
   */
  getRepeatsByRegion: (speciesId: number, params: RepeatRegionParams, signal?: AbortSignal) =>
    apiClient.get<RepeatMaskerResponse>(`/api/v1/features/repeats/${speciesId}`, { params, signal }),

  /**
   * Get list of unique repeat classes for a species
   *
   * Returns all distinct repeat classes found in the RepeatMasker data
   * for a given species. Useful for populating filter dropdowns.
   *
   * **Performance**:
   * - Response time: 30-80ms
   * - Response size: ~1 KB
   * - Backend cache: Redis 1 hour
   *
   * @param speciesId - Species ID (1=Human, 2=Chimp, 3=Macaque, 4=Marmoset)
   * @returns AxiosResponse with array of repeat class names
   *
   * @example
   * // Get repeat classes for human
   * const { data } = useQuery({
   *   queryKey: ['repeat-classes', 1],
   *   queryFn: () => featuresApi.getRepeatClasses(1),
   *   staleTime: 60 * 60 * 1000, // 1 hour
   * })
   * // Returns: ["SINE", "LINE", "LTR", "DNA", "Simple_repeat", ...]
   *
   * @see RepeatMasker class filter in IGV controls
   */
  getRepeatClasses: (speciesId: number, signal?: AbortSignal) =>
    apiClient.get<string[]>(`/api/v1/features/repeats/${speciesId}/classes`, { signal }),

  /**
   * Get list of unique repeat families for a species
   *
   * Returns all distinct repeat families for a species, optionally
   * filtered by repeat class. Useful for cascading filter dropdowns.
   *
   * **Performance**:
   * - Response time: 30-100ms
   * - Response size: ~5 KB
   * - Backend cache: Redis 1 hour
   *
   * @param speciesId - Species ID (1=Human, 2=Chimp, 3=Macaque, 4=Marmoset)
   * @param repeatClass - Optional filter by repeat class
   * @returns AxiosResponse with array of repeat family names
   *
   * @example
   * // Get all families for human
   * const { data } = useQuery({
   *   queryKey: ['repeat-families', 1],
   *   queryFn: () => featuresApi.getRepeatFamilies(1),
   * })
   *
   * @example
   * // Get families for SINE class only
   * const { data } = useQuery({
   *   queryKey: ['repeat-families', 1, 'SINE'],
   *   queryFn: () => featuresApi.getRepeatFamilies(1, 'SINE'),
   * })
   * // Returns: ["Alu", "MIR", "tRNA-RTE", ...]
   *
   * @see RepeatMasker family filter in IGV controls
   */
  getRepeatFamilies: (speciesId: number, repeatClass?: string, signal?: AbortSignal) =>
    apiClient.get<string[]>(`/api/v1/features/repeats/${speciesId}/families`, {
      params: repeatClass ? { repeat_class: repeatClass } : undefined,
      signal
    }),
}

// =============================================================================
// RepeatMasker Display Types and Configuration
// =============================================================================

/**
 * RepeatMasker display modes for IGV visualization
 *
 * Controls how repeat elements are rendered in the IGV browser:
 * - SQUISHED: Compact display with overlapping repeats (default, best for overview)
 * - EXPANDED: Each repeat on its own row (best for detailed analysis)
 * - COLLAPSED: All repeats stacked in single row (most compact)
 */
export type RepeatMaskerDisplayMode = 'SQUISHED' | 'EXPANDED' | 'COLLAPSED'

/**
 * RepeatMasker track configuration for IGV
 *
 * Contains all settings needed to add a RepeatMasker track to IGV.js.
 * The configuration follows IGV.js track format specification.
 */
export interface RepeatMaskerTrackConfig {
  /** Track display name */
  name: string
  /** Track type (usually "annotation" or "bed") */
  type: string
  /** Data format (usually "bed" or "bigBed") */
  format: string
  /** URL to the track data file */
  url: string
  /** Display mode controlling visual density */
  displayMode?: RepeatMaskerDisplayMode
  /** Default track color (hex format) */
  color?: string
  /** Track height in pixels */
  height?: number
  /** Maximum zoom level for data display (in bp) */
  visibilityWindow?: number
  /** Color mapping for different repeat classes (UCSC Full mode) */
  colorTable?: Record<string, string>
  /** Whether to use RGB colors from the BED file itemRgb column */
  itemRgb?: boolean
}

/**
 * Get RepeatMasker IGV track configuration
 *
 * Returns configuration object for adding a RepeatMasker track to IGV.js.
 * The track displays all repeat classes with UCSC-style coloring.
 *
 * **Performance**:
 * - Response time: 20-50ms
 * - Response size: ~3 KB
 * - Backend cache: Redis 1 hour
 *
 * @param speciesId - Species ID (1=Human, 2=Chimp, 3=Macaque, 4=Marmoset)
 * @param displayMode - Optional display mode (SQUISHED, EXPANDED, COLLAPSED)
 * @returns AxiosResponse with track configuration wrapped in ApiResponse
 *
 * @example
 * // Get default track config
 * const { data } = useQuery({
 *   queryKey: ['repeatmasker-track-config', speciesId],
 *   queryFn: () => getRepeatMaskerTrackConfig(speciesId),
 * })
 *
 * // Add to IGV browser
 * igvBrowser.loadTrack(data.data)
 *
 * @example
 * // Get expanded view config
 * const { data } = await getRepeatMaskerTrackConfig(1, 'EXPANDED')
 *
 * @see IGV.js track configuration documentation
 */
export const getRepeatMaskerTrackConfig = (
  speciesId: number,
  displayMode?: RepeatMaskerDisplayMode,
  signal?: AbortSignal
) =>
  apiClient.get<ApiResponse<RepeatMaskerTrackConfig>>(
    `/api/v1/igv/config/repeatmasker/${speciesId}`,
    {
      params: displayMode ? { display_mode: displayMode } : undefined,
      signal
    }
  )

/**
 * RepeatMasker class-specific track configuration
 *
 * Configuration for a single repeat class track (e.g., SINE-only track).
 * Used when displaying repeat classes as separate colored tracks.
 */
export interface RepeatMaskerClassTrack {
  /** Unique track identifier */
  id: string
  /** Track display name (e.g., "SINE Repeats") */
  name: string
  /** Track type (usually "annotation") */
  type: string
  /** Data format (usually "bed") */
  format: string
  /** URL to the class-specific track data */
  url: string
  /** Track color in hex format (e.g., "#FF0000") */
  color: string
  /** Track height in pixels */
  height?: number
  /** Maximum zoom level for data display */
  visibilityWindow?: number
  /** Display mode */
  displayMode?: string
}

/**
 * Response type for RepeatMasker class tracks API
 *
 * Contains multiple track configurations, one per repeat class,
 * allowing users to toggle individual classes on/off.
 */
export interface RepeatMaskerClassTracksResponse {
  /** Array of class-specific track configurations */
  tracks: RepeatMaskerClassTrack[]
  /** Species ID these tracks are for */
  species_id: number
  /** Species display name */
  species_name: string
}

/**
 * Get RepeatMasker class-specific track configurations
 *
 * Returns separate track configs for each repeat class (SINE, LINE, LTR, etc.),
 * enabling individual control over which classes are displayed.
 * Each track has a distinct color following UCSC conventions.
 *
 * **Performance**:
 * - Response time: 30-80ms
 * - Response size: ~8 KB
 * - Backend cache: Redis 1 hour
 *
 * **Track Colors** (UCSC convention):
 * - SINE: #FF0000 (Red)
 * - LINE: #00FF00 (Green)
 * - LTR: #0000FF (Blue)
 * - DNA: #FFA500 (Orange)
 * - Simple: #FF00FF (Magenta)
 * - Low_complexity: #00FFFF (Cyan)
 * - Other: #808080 (Gray)
 *
 * @param speciesId - Species ID (1=Human, 2=Chimp, 3=Macaque, 4=Marmoset)
 * @returns AxiosResponse with class tracks wrapped in ApiResponse
 *
 * @example
 * // Get class-specific tracks
 * const { data } = useQuery({
 *   queryKey: ['repeatmasker-class-tracks', speciesId],
 *   queryFn: () => getRepeatMaskerClassTracks(speciesId),
 * })
 *
 * // Add selected class tracks to IGV
 * const selectedClasses = ['SINE', 'LINE']
 * data.data.tracks
 *   .filter(track => selectedClasses.includes(track.id))
 *   .forEach(track => igvBrowser.loadTrack(track))
 *
 * @see RepeatMasker track controls in IGV toolbar
 * @see Phase 6.1 IGV enhancement documentation
 */
export const getRepeatMaskerClassTracks = (speciesId: number, signal?: AbortSignal) =>
  apiClient.get<ApiResponse<RepeatMaskerClassTracksResponse>>(
    `/api/v1/igv/config/repeatmasker-classes/${speciesId}`,
    { signal }
  )
