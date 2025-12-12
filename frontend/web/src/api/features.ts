/**
 * Features API Client
 * Handles RepeatMasker and other genomic feature data fetching
 */
import { apiClient } from './client'
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
 */
interface ApiResponse<T> {
  success: boolean
  data: T
  message?: string
}

export const featuresApi = {
  /**
   * Get RepeatMasker annotations for a gene
   * @param geneId - Gene ID
   * @param filters - Optional filters for repeat class, family, divergence, pagination
   */
  getGeneRepeats: (geneId: number, filters?: RepeatMaskerFilters) =>
    apiClient.get<RepeatMaskerResponse>(`/api/v1/features/genes/${geneId}/repeats`, {
      params: filters
    }),

  /**
   * Get RepeatMasker statistics for a gene
   * @param geneId - Gene ID
   */
  getGeneRepeatStats: (geneId: number) =>
    apiClient.get<RepeatStats>(`/api/v1/features/genes/${geneId}/repeats/stats`),

  /**
   * Export RepeatMasker data as BED format
   * Opens a new tab/window for download
   * @param geneId - Gene ID
   * @param filters - Optional filters
   */
  exportRepeatsToBED: (geneId: number, filters?: RepeatMaskerFilters) => {
    const API_BASE_URL = import.meta.env.VITE_API_BASE_URL || 'http://localhost:8000'
    const params = new URLSearchParams()

    if (filters?.repeat_class) params.append('repeat_class', filters.repeat_class)
    if (filters?.repeat_family) params.append('repeat_family', filters.repeat_family)
    if (filters?.min_divergence !== undefined) params.append('min_divergence', String(filters.min_divergence))
    if (filters?.max_divergence !== undefined) params.append('max_divergence', String(filters.max_divergence))

    const queryString = params.toString()
    const url = `${API_BASE_URL}/api/v1/features/genes/${geneId}/repeats/export${queryString ? `?${queryString}` : ''}`
    window.open(url, '_blank')
  },

  // =============================================================================
  // Feature Tracks API
  // =============================================================================

  /**
   * List all available feature tracks
   * @param params - Optional filters for category and active status
   */
  listTracks: (params?: FeatureTrackListParams) =>
    apiClient.get<FeatureTrack[]>('/api/v1/features/tracks', { params }),

  /**
   * Get details for a specific feature track
   * @param trackId - Track ID
   */
  getTrack: (trackId: number) =>
    apiClient.get<FeatureTrack>(`/api/v1/features/tracks/${trackId}`),

  /**
   * Get statistics for all feature tracks (feature counts by species)
   */
  getTrackStats: () =>
    apiClient.get<FeatureTrackStats[]>('/api/v1/features/tracks/stats'),

  // =============================================================================
  // Region-based RepeatMasker API
  // =============================================================================

  /**
   * Get RepeatMasker annotations for a specific genomic region
   * @param speciesId - Species ID
   * @param params - Region coordinates and optional filters
   */
  getRepeatsByRegion: (speciesId: number, params: RepeatRegionParams) =>
    apiClient.get<RepeatMaskerResponse>(`/api/v1/features/repeats/${speciesId}`, { params }),

  /**
   * Get list of unique repeat classes for a species
   * @param speciesId - Species ID
   */
  getRepeatClasses: (speciesId: number) =>
    apiClient.get<string[]>(`/api/v1/features/repeats/${speciesId}/classes`),

  /**
   * Get list of unique repeat families for a species
   * @param speciesId - Species ID
   * @param repeatClass - Optional filter by repeat class
   */
  getRepeatFamilies: (speciesId: number, repeatClass?: string) =>
    apiClient.get<string[]>(`/api/v1/features/repeats/${speciesId}/families`, {
      params: repeatClass ? { repeat_class: repeatClass } : undefined
    }),
}

/**
 * RepeatMasker display modes
 * - SQUISHED: Compact display (default)
 * - EXPANDED: Each repeat on its own row
 * - COLLAPSED: All repeats stacked
 */
export type RepeatMaskerDisplayMode = 'SQUISHED' | 'EXPANDED' | 'COLLAPSED'

/**
 * RepeatMasker track configuration response
 */
export interface RepeatMaskerTrackConfig {
  name: string
  type: string
  format: string
  url: string
  displayMode?: RepeatMaskerDisplayMode
  color?: string
  height?: number
  visibilityWindow?: number
  /** Color table for different repeat classes (UCSC Full mode) */
  colorTable?: Record<string, string>
  /** Whether to use itemRgb from the BED file */
  itemRgb?: boolean
}

/**
 * Get RepeatMasker IGV track configuration
 * @param speciesId - Species ID
 * @param displayMode - Display mode (SQUISHED, EXPANDED, COLLAPSED)
 */
export const getRepeatMaskerTrackConfig = (
  speciesId: number,
  displayMode?: RepeatMaskerDisplayMode
) =>
  apiClient.get<ApiResponse<RepeatMaskerTrackConfig>>(
    `/api/v1/igv/config/repeatmasker/${speciesId}`,
    {
      params: displayMode ? { display_mode: displayMode } : undefined
    }
  )

/**
 * RepeatMasker class track configuration (for grouped display)
 */
export interface RepeatMaskerClassTrack {
  id: string
  name: string
  type: string
  format: string
  url: string
  color: string
  height?: number
  visibilityWindow?: number
  displayMode?: string
}

/**
 * Response type for RepeatMasker class tracks API
 */
export interface RepeatMaskerClassTracksResponse {
  tracks: RepeatMaskerClassTrack[]
  species_id: number
  species_name: string
}

/**
 * Get RepeatMasker class-specific track configurations
 * Returns separate track configs for each repeat class (SINE, LINE, LTR, etc.)
 * @param speciesId - Species ID
 */
export const getRepeatMaskerClassTracks = (speciesId: number) =>
  apiClient.get<ApiResponse<RepeatMaskerClassTracksResponse>>(
    `/api/v1/igv/config/repeatmasker-classes/${speciesId}`
  )
