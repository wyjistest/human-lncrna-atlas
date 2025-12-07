/**
 * lncRNA-ChIP-seq Overlap API Client
 * Phase 3.0 - Task 1.3
 *
 * API functions for querying lncRNA binding site overlaps with ChIP-seq peaks.
 * Backend endpoints will be implemented in parallel by backend agent.
 *
 * Backend Endpoints:
 * - GET /api/v1/lncrna-chipseq-overlap - Paginated overlap query
 * - GET /api/v1/lncrna-chipseq-overlap/summary - Statistics summary (Phase 2)
 */

import { apiClient } from './client'
import type {
  OverlapFilters,
  OverlapResponse,
  OverlapSummary,
  OverlapHeatmapData,
  OverlapHeatmapParams,
} from '@/types/lncRNAChIPSeqOverlap'

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
  getOverlaps: (filters: OverlapFilters) =>
    apiClient.get<OverlapResponse>('/api/v1/lncrna-chipseq-overlap', {
      params: {
        lncrna_gene_id: filters.lncrna_gene_id,
        target_gene_id: filters.target_gene_id,
        mark_type: filters.mark_type,
        cell_type: filters.cell_type,
        chromosome: filters.chromosome,
        min_overlap_length: filters.min_overlap_length,
        min_binding_affinity: filters.min_binding_affinity,
        min_peak_strength: filters.min_peak_strength,
        max_qvalue: filters.max_qvalue,
        page: filters.page ?? 1,
        page_size: filters.page_size ?? 20,
        sort_by: filters.sort_by,
        sort_order: filters.sort_order,
      }
    }),

  /**
   * Get summary statistics for overlap analysis (Phase 2)
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
  getSummary: (filters?: Partial<OverlapFilters>) =>
    apiClient.get<OverlapSummary>('/api/v1/lncrna-chipseq-overlap/summary', {
      params: filters
    }),

  /**
   * Export overlaps to BED format (Phase 2)
   *
   * @param filters - Query filters
   * @returns BED file content as text
   */
  exportToBED: (filters: OverlapFilters) =>
    apiClient.get<string>('/api/v1/lncrna-chipseq-overlap/export', {
      params: {
        ...filters,
        format: 'bed'
      },
      responseType: 'blob'
    }),

  /**
   * Export overlaps to CSV format (Phase 2)
   *
   * @param filters - Query filters
   * @returns CSV file content as text
   */
  exportToCSV: (filters: OverlapFilters) =>
    apiClient.get<string>('/api/v1/lncrna-chipseq-overlap/export', {
      params: {
        ...filters,
        format: 'csv'
      },
      responseType: 'blob'
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
  getHeatmap: (params: OverlapHeatmapParams) =>
    apiClient.get<OverlapHeatmapData>('/api/v1/lncrna-chipseq-overlap/heatmap', {
      params: {
        x_axis: params.x_axis,
        y_axis: params.y_axis,
        metric: params.metric,
        top_n: params.top_n,
        chromosome: params.chromosome,
        min_binding_affinity: params.min_binding_affinity,
        max_qvalue: params.max_qvalue,
      }
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
  overlaps: (filters: OverlapFilters) =>
    [...overlapQueryKeys.all, 'overlaps', filters] as const,

  /** Summary statistics */
  summary: (filters?: Partial<OverlapFilters>) =>
    [...overlapQueryKeys.all, 'summary', filters] as const,

  /** Heatmap data (Phase 3.0 Phase 2) */
  heatmap: (params: OverlapHeatmapParams) =>
    [...overlapQueryKeys.all, 'heatmap', params] as const,
}

export default lncRNAChIPSeqOverlapApi
