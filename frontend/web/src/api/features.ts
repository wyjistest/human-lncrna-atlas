/**
 * Features API Client
 * Handles RepeatMasker and other genomic feature data fetching
 */
import { apiClient } from './client'
import type {
  RepeatMaskerResponse,
  RepeatMaskerFilters,
  RepeatStats
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
  }
}

/**
 * Get RepeatMasker IGV track configuration
 * @param speciesId - Species ID
 */
export const getRepeatMaskerTrackConfig = (speciesId: number) =>
  apiClient.get<ApiResponse<{
    name: string
    type: string
    format: string
    url: string
    displayMode?: string
    color?: string
    height?: number
    visibilityWindow?: number
  }>>(`/api/v1/igv/config/repeatmasker/${speciesId}`)
