/**
 * Global Compare API Client
 * Phase 2.5 - API functions for global multi-marks comparison
 *
 * Backend Endpoints (to be implemented):
 * - GET /api/v1/chipseq/global-compare - Get global comparison data
 * - GET /api/v1/chipseq/cell-line-matrix - Get cell line x mark matrix
 * - GET /api/v1/chipseq/signal-distribution - Get signal distribution data
 */

import { apiClient } from './client'
import type {
  GlobalCompareParams,
  GlobalCompareResponse,
  CellLineMatrixParams,
  CellLineMatrixResponse,
  SignalDistParams,
  SignalDistResponse,
} from '@/types/globalCompare'
import type { MarkType } from '@/types/chipseq'

/**
 * Global Compare API client object
 */
export const globalCompareApi = {
  /**
   * Get global comparison data across all marks
   * @param params - Query parameters including marks filter
   */
  getGlobalCompare: (params?: GlobalCompareParams, signal?: AbortSignal) =>
    apiClient.get<GlobalCompareResponse>('/api/v1/chipseq/global-compare', {
      params: {
        marks: params?.marks?.join(','),
        cell_types: params?.cell_types?.join(','),
        min_peaks: params?.min_peaks,
        include_position_distribution: params?.include_position_distribution,
      },
      signal,
    }),

  /**
   * Get cell line x mark matrix data
   * @param params - Query parameters including marks and cell types
   */
  getCellLineMatrix: (params: CellLineMatrixParams, signal?: AbortSignal) =>
    apiClient.get<CellLineMatrixResponse>('/api/v1/chipseq/cell-line-matrix', {
      params: {
        marks: params.marks?.join(','),
        cell_types: params.cell_types?.join(','),
        metric: params.metric,
      },
      signal,
    }),

  /**
   * Get signal distribution data for marks
   * @param params - Query parameters including marks filter
   */
  getSignalDistribution: (params?: SignalDistParams, signal?: AbortSignal) =>
    apiClient.get<SignalDistResponse>('/api/v1/chipseq/signal-distribution', {
      params: {
        marks: params?.marks?.join(','),
        cell_types: params?.cell_types?.join(','),
        bins: params?.bins,
      },
      signal,
    }),
}

/**
 * Query key factory for React Query
 * Provides consistent query keys for caching and invalidation
 */
export const globalCompareQueryKeys = {
  /** Base key for all global compare queries */
  all: ['globalCompare'] as const,

  /** Global comparison data */
  compare: (marks?: MarkType[], cellTypes?: string[]) =>
    [
      ...globalCompareQueryKeys.all,
      'compare',
      marks?.sort().join(',') || 'all',
      cellTypes?.sort().join(',') || 'all',
    ] as const,

  /** Cell line matrix data */
  cellLineMatrix: (marks?: MarkType[], cellTypes?: string[], metric?: string) =>
    [
      ...globalCompareQueryKeys.all,
      'matrix',
      marks?.sort().join(',') || 'all',
      cellTypes?.sort().join(',') || 'all',
      metric || 'peak_count',
    ] as const,

  /** Signal distribution data */
  signalDistribution: (marks?: MarkType[], cellTypes?: string[]) =>
    [
      ...globalCompareQueryKeys.all,
      'distribution',
      marks?.sort().join(',') || 'all',
      cellTypes?.sort().join(',') || 'all',
    ] as const,
}
