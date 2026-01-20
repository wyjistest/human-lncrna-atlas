/**
 * lncRNA-ChIP-seq Overlap API Client
 * Phase 3.0 - Task 1.3
 *
 * API functions for querying lncRNA binding site overlaps with ChIP-seq peaks.
 * Backend endpoints will be implemented in parallel by backend agent.
 *
 * Backend Endpoints:
 * - GET /api/v1/lncrna-chipseq-overlap - Paginated overlap query
 * - GET /api/v1/lncrna-chipseq-overlap/statistics - Statistics summary (canonical endpoint)
 * - GET /api/v1/lncrna-chipseq-overlap/summary - Alias for /statistics (backward compatibility)
 */

import { apiClient } from './client'
import { API_BASE_URL } from '@/config/api'
import { openInNewTab } from '@/utils/safeWindow'
import { normalizeCommaSeparatedList, normalizeQueryKeyObject } from '@/utils/queryKey'
import type {
  OverlapFilters,
  OverlapCursorResponse,
  OverlapResponse,
  OverlapSummary,
  OverlapHeatmapData,
  OverlapHeatmapParams,
} from '@/types/lncRNAChIPSeqOverlap'

const DEFAULT_MAX_QVALUE = 0.05
const DEFAULT_PAGE = 1
const DEFAULT_PAGE_SIZE = 20
const DEFAULT_SORT_BY: NonNullable<OverlapFilters['sort_by']> = 'binding_affinity'
const DEFAULT_SORT_ORDER: NonNullable<OverlapFilters['sort_order']> = 'desc'

function normalizeOverlapsFiltersForKey(filters: OverlapFilters) {
  // /lncrna-chipseq-overlap 是分页端点：page/page_size 必须进入 key
  return normalizeQueryKeyObject({
    ...filters,
    mark_type: normalizeCommaSeparatedList(filters.mark_type),
    cell_type: normalizeCommaSeparatedList(filters.cell_type),
    page: filters.page ?? DEFAULT_PAGE,
    page_size: filters.page_size ?? DEFAULT_PAGE_SIZE,
    sort_by: filters.sort_by ?? DEFAULT_SORT_BY,
    sort_order: filters.sort_order ?? DEFAULT_SORT_ORDER,
    max_qvalue: filters.max_qvalue ?? DEFAULT_MAX_QVALUE,
  })
}

function normalizeOverlapsCursorFiltersForKey(filters: OverlapFilters) {
  // /lncrna-chipseq-overlap/cursor 是 cursor(keyset)端点：不接受 page，但 page_size 必须进入 key
  return normalizeQueryKeyObject({
    lncrna_gene_id: filters.lncrna_gene_id,
    target_gene_id: filters.target_gene_id,
    mark_type: normalizeCommaSeparatedList(filters.mark_type),
    cell_type: normalizeCommaSeparatedList(filters.cell_type),
    chromosome: filters.chromosome,
    min_overlap_length: filters.min_overlap_length,
    min_binding_affinity: filters.min_binding_affinity,
    min_peak_strength: filters.min_peak_strength,
    max_qvalue: filters.max_qvalue ?? DEFAULT_MAX_QVALUE,
    page_size: filters.page_size ?? DEFAULT_PAGE_SIZE,
    sort_by: filters.sort_by ?? DEFAULT_SORT_BY,
    sort_order: filters.sort_order ?? DEFAULT_SORT_ORDER,
  })
}

function buildSummaryParams(filters?: Partial<OverlapFilters>) {
  if (!filters) return undefined

  // /summary(/statistics) 端点不接受分页/排序参数；仅保留服务端支持的字段，避免缓存碎片与无效 query params。
  return normalizeQueryKeyObject({
    lncrna_gene_id: filters.lncrna_gene_id,
    target_gene_id: filters.target_gene_id,
    mark_type: normalizeCommaSeparatedList(filters.mark_type),
    cell_type: normalizeCommaSeparatedList(filters.cell_type),
    chromosome: filters.chromosome,
    min_binding_affinity: filters.min_binding_affinity,
    max_qvalue: filters.max_qvalue ?? DEFAULT_MAX_QVALUE,
  })
}

/**
 * lncRNA-ChIP-seq Overlap API namespace
 */
export const lncRNAChIPSeqOverlapApi = {
  /**
   * Get lncRNA-ChIP-seq overlaps with filtering and pagination
   *
   * @param filters - Query filters
   * @returns Paginated overlap results
   *
   * @example
   * ```ts
   * const response = await lncRNAChIPSeqOverlapApi.getOverlaps({
   *   mark_type: 'H3K27me3',
   *   cell_type: 'K562',
   *   min_overlap_length: 100,
   *   page: 1,
   *   page_size: 20
   * })
   * ```
   */
		  getOverlaps: (filters: OverlapFilters, signal?: AbortSignal) =>
		    apiClient.get<OverlapResponse>('/api/v1/lncrna-chipseq-overlap', {
	      params: {
	        lncrna_gene_id: filters.lncrna_gene_id,
	        target_gene_id: filters.target_gene_id,
	        mark_type: normalizeCommaSeparatedList(filters.mark_type),
	        cell_type: normalizeCommaSeparatedList(filters.cell_type),
	        chromosome: filters.chromosome,
	        min_overlap_length: filters.min_overlap_length,
	        min_binding_affinity: filters.min_binding_affinity,
	        min_peak_strength: filters.min_peak_strength,
	        max_qvalue: filters.max_qvalue ?? DEFAULT_MAX_QVALUE,
	        page: filters.page ?? DEFAULT_PAGE,
	        page_size: filters.page_size ?? DEFAULT_PAGE_SIZE,
	        sort_by: filters.sort_by ?? DEFAULT_SORT_BY,
	        sort_order: filters.sort_order ?? DEFAULT_SORT_ORDER,
	      },
		      signal
		    }),

	  /**
	   * Get lncRNA-ChIP-seq overlaps with cursor(keyset) pagination
	   *
	   * @param filters - Query filters (same as getOverlaps, but ignores page)
	   * @param cursor - Opaque cursor token from previous response
	   * @returns Cursor-paginated overlap results
	   */
	  getOverlapsCursor: (filters: OverlapFilters, cursor?: string | null, signal?: AbortSignal) =>
	    apiClient.get<OverlapCursorResponse>('/api/v1/lncrna-chipseq-overlap/cursor', {
	      params: {
	        lncrna_gene_id: filters.lncrna_gene_id,
	        target_gene_id: filters.target_gene_id,
	        mark_type: normalizeCommaSeparatedList(filters.mark_type),
	        cell_type: normalizeCommaSeparatedList(filters.cell_type),
	        chromosome: filters.chromosome,
	        min_overlap_length: filters.min_overlap_length,
	        min_binding_affinity: filters.min_binding_affinity,
	        min_peak_strength: filters.min_peak_strength,
	        max_qvalue: filters.max_qvalue ?? DEFAULT_MAX_QVALUE,
	        cursor: cursor ?? undefined,
	        page_size: filters.page_size ?? DEFAULT_PAGE_SIZE,
	        sort_by: filters.sort_by ?? DEFAULT_SORT_BY,
	        sort_order: filters.sort_order ?? DEFAULT_SORT_ORDER,
	      },
	      signal,
	    }),

  /**
   * Get summary statistics for overlap analysis
   *
   * Note: This calls /summary endpoint (alias for /statistics).
   * The canonical endpoint is /statistics, but /summary is kept for backward compatibility.
   *
   * @param filters - Optional filters to scope the summary
   * @returns Summary statistics
   *
   * @example
   * ```ts
   * const response = await lncRNAChIPSeqOverlapApi.getSummary({
   *   mark_type: 'H3K27me3'
   * })
   * ```
   */
	  getSummary: (filters?: Partial<OverlapFilters>, signal?: AbortSignal) =>
	    apiClient.get<OverlapSummary>('/api/v1/lncrna-chipseq-overlap/summary', {
	      params: buildSummaryParams(filters),
	      signal
	    }),

  /**
   * Export overlaps in specified format (BED or CSV)
   * Opens a new tab/window for direct download
   *
   * @param filters - Query filters
   * @param format - Export format ('bed' or 'csv')
   */
  exportOverlaps: (filters: OverlapFilters, format: 'bed' | 'csv') => {
    const params = new URLSearchParams()

    // Apply all filters
    if (filters.lncrna_gene_id) params.append('lncrna_gene_id', String(filters.lncrna_gene_id))
    if (filters.target_gene_id) params.append('target_gene_id', String(filters.target_gene_id))
    if (filters.mark_type) params.append('mark_type', filters.mark_type)
    if (filters.cell_type) params.append('cell_type', filters.cell_type)
    if (filters.chromosome) params.append('chromosome', filters.chromosome)
    if (filters.min_overlap_length !== undefined) {
      params.append('min_overlap_length', String(filters.min_overlap_length))
    }
    if (filters.min_binding_affinity !== undefined) {
      params.append('min_binding_affinity', String(filters.min_binding_affinity))
    }
    if (filters.min_peak_strength !== undefined) {
      params.append('min_peak_strength', String(filters.min_peak_strength))
    }
    if (filters.max_qvalue !== undefined) {
      params.append('max_qvalue', String(filters.max_qvalue))
    }

    params.append('format', format)

    const url = `${API_BASE_URL}/api/v1/lncrna-chipseq-overlap/export?${params.toString()}`
    openInNewTab(url)
  },

  /**
   * Export overlaps to BED format (Phase 2)
   * @deprecated Use exportOverlaps() instead
   */
  exportToBED: (filters: OverlapFilters, signal?: AbortSignal) =>
    apiClient.get<string>('/api/v1/lncrna-chipseq-overlap/export', {
      params: {
        ...filters,
        format: 'bed'
      },
      responseType: 'blob',
      signal
    }),

  /**
   * Export overlaps to CSV format (Phase 2)
   * @deprecated Use exportOverlaps() instead
   */
  exportToCSV: (filters: OverlapFilters, signal?: AbortSignal) =>
    apiClient.get<string>('/api/v1/lncrna-chipseq-overlap/export', {
      params: {
        ...filters,
        format: 'csv'
      },
      responseType: 'blob',
      signal
    }),

  /**
   * Get heatmap matrix data for overlap visualization (Phase 3.0 Phase 2)
   *
   * @param params - Heatmap parameters including axis dimensions and metric
   * @returns Heatmap data with labels and values
   *
   * @example
   * ```ts
   * const response = await lncRNAChIPSeqOverlapApi.getHeatmap({
   *   x_axis: 'mark_type',
   *   y_axis: 'lncrna',
   *   metric: 'count',
   *   top_n: 50
   * })
   * ```
   */
  getHeatmap: (params: OverlapHeatmapParams, signal?: AbortSignal) =>
    apiClient.get<OverlapHeatmapData>('/api/v1/lncrna-chipseq-overlap/heatmap', {
      params: {
        x_axis: params.x_axis,
        y_axis: params.y_axis,
        metric: params.metric,
        top_n: params.top_n,
        chromosome: params.chromosome,
        min_binding_affinity: params.min_binding_affinity,
        max_qvalue: params.max_qvalue,
      },
      signal
    }),
}

/**
 * Query key factory for React Query
 * Provides consistent query keys for caching and invalidation
 */
export const overlapQueryKeys = {
  /** Base key for all overlap queries */
  all: ['lncrna-chipseq-overlap'] as const,

  /** Overlap data queries */
  overlaps: (filters: OverlapFilters) => {
    const normalized = normalizeOverlapsFiltersForKey(filters)
    return normalized
      ? ([...overlapQueryKeys.all, 'overlaps', normalized] as const)
      : ([...overlapQueryKeys.all, 'overlaps'] as const)
  },

  /** Overlap data queries (cursor keyset pagination) */
  overlapsCursor: (filters: OverlapFilters) => {
    const normalized = normalizeOverlapsCursorFiltersForKey(filters)
    return normalized
      ? ([...overlapQueryKeys.all, 'overlapsCursor', normalized] as const)
      : ([...overlapQueryKeys.all, 'overlapsCursor'] as const)
  },

  /** Summary statistics */
  summary: (filters?: Partial<OverlapFilters>) => {
    const normalized = buildSummaryParams(filters)
    return normalized
      ? ([...overlapQueryKeys.all, 'summary', normalized] as const)
      : ([...overlapQueryKeys.all, 'summary'] as const)
  },

  /** Heatmap data (Phase 3.0 Phase 2) */
  heatmap: (params: OverlapHeatmapParams) => {
    const normalized = normalizeQueryKeyObject(params)
    return normalized
      ? ([...overlapQueryKeys.all, 'heatmap', normalized] as const)
      : ([...overlapQueryKeys.all, 'heatmap'] as const)
  },
}

export default lncRNAChIPSeqOverlapApi
