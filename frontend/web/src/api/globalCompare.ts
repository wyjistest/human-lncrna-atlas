/**
 * Global Compare API contract placeholder.
 *
 * The public /chipseq-compare page currently has no backend support. Keep the
 * client explicit about that fact so other callers do not silently depend on a
 * fake /api/v1/chipseq/* namespace.
 */

import type { AxiosResponse } from 'axios'
import type {
  GlobalCompareParams,
  GlobalCompareResponse,
  CellLineMatrixParams,
  CellLineMatrixResponse,
  SignalDistParams,
  SignalDistResponse,
} from '@/types/globalCompare'
import type { MarkType } from '@/types/chipseq'

export const GLOBAL_COMPARE_UNAVAILABLE_MESSAGE =
  'Global ChIP-seq compare endpoints are not available. Use /api/v1/features/chipseq/genes/{gene_id}/... endpoints instead.'

function rejectUnavailable<T>(): Promise<AxiosResponse<T>> {
  return Promise.reject(new Error(GLOBAL_COMPARE_UNAVAILABLE_MESSAGE))
}

/**
 * Global Compare API client object
 */
export const globalCompareApi = {
  isAvailable: false,
  availabilityReason: GLOBAL_COMPARE_UNAVAILABLE_MESSAGE,
  /**
   * Global compare is intentionally unavailable until a real backend contract exists.
   */
  getGlobalCompare: (_params?: GlobalCompareParams, _signal?: AbortSignal) =>
    rejectUnavailable<GlobalCompareResponse>(),

  /**
   * Global compare is intentionally unavailable until a real backend contract exists.
   */
  getCellLineMatrix: (_params: CellLineMatrixParams, _signal?: AbortSignal) =>
    rejectUnavailable<CellLineMatrixResponse>(),

  /**
   * Global compare is intentionally unavailable until a real backend contract exists.
   */
  getSignalDistribution: (_params?: SignalDistParams, _signal?: AbortSignal) =>
    rejectUnavailable<SignalDistResponse>(),
}

/**
 * Query key factory for React Query
 * Provides consistent query keys for caching and invalidation
 */
export const globalCompareQueryKeys = {
  /** Base key for all global compare queries */
  all: ['globalCompare'] as const,

  /** Global comparison data */
  compare: (
    marks?: MarkType[],
    cellTypes?: string[],
    options?: Pick<GlobalCompareParams, 'min_peaks' | 'include_position_distribution'>
  ) =>
    [
      ...globalCompareQueryKeys.all,
      'compare',
      marks && marks.length > 0 ? [...marks].sort().join(',') : 'all',
      cellTypes && cellTypes.length > 0 ? [...cellTypes].sort().join(',') : 'all',
      options?.min_peaks ?? null,
      options?.include_position_distribution ?? null,
    ] as const,

  /** Cell line matrix data */
  cellLineMatrix: (marks?: MarkType[], cellTypes?: string[], metric?: string) =>
    [
      ...globalCompareQueryKeys.all,
      'matrix',
      marks && marks.length > 0 ? [...marks].sort().join(',') : 'all',
      cellTypes && cellTypes.length > 0 ? [...cellTypes].sort().join(',') : 'all',
      metric || 'peak_count',
    ] as const,

  /** Signal distribution data */
  signalDistribution: (marks?: MarkType[], cellTypes?: string[], bins?: number) =>
    [
      ...globalCompareQueryKeys.all,
      'distribution',
      marks && marks.length > 0 ? [...marks].sort().join(',') : 'all',
      cellTypes && cellTypes.length > 0 ? [...cellTypes].sort().join(',') : 'all',
      bins ?? null,
    ] as const,
}
