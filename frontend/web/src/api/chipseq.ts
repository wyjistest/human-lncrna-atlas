/**
 * ChIP-seq API Client
 * Phase 2.2 - API functions for ChIP-seq data retrieval
 *
 * Backend Endpoints:
 * - GET /features/chipseq/marks?species_id=1 - Get available marks
 * - GET /features/chipseq/genes/{gene_id}?mark_type=H3K27me3&flanking=10000 - Get gene peaks
 * - GET /features/chipseq/genes/{gene_id}/summary?mark_type=H3K27me3 - Get statistics
 * - GET /features/chipseq/genes/{gene_id}/compare?marks=H3K27me3,H3K4me3 - Compare marks
 */

import { apiClient } from './client'
import { API_BASE_URL } from '@/config/api'
import type {
  MarkType,
  ChIPSeqFilters,
  ChIPSeqSummary,
  RawChIPSeqCompareResponse,
  AvailableMarksResponse,
  GeneChIPSeqRawResponse,
  CellLineComparisonResponse,
  HeatmapMatrixResponse,
  HeatmapMetricType,
  ChIPSeqExperiment,
  ChIPSeqExperimentListResponse,
  ChIPSeqExperimentFilters,
  ChIPSeqGlobalStats,
} from '@/types/chipseq'

/**
 * ChIP-seq API client object
 */
export const chipseqApi = {
  /**
   * Get available ChIP-seq marks for a species
   * @param speciesId - Species ID (default: 1 for Human)
   */
  getAvailableMarks: (speciesId: number = 1) =>
    apiClient.get<AvailableMarksResponse>('/api/v1/features/chipseq/marks', {
      params: { species_id: speciesId },
    }),

  /**
   * Get ChIP-seq peaks for a gene (raw backend response)
   * @param geneId - Gene ID
   * @param filters - Query filters including mark_type, pagination, and filtering options
   */
  getGenePeaks: (geneId: number, filters?: ChIPSeqFilters) =>
    apiClient.get<GeneChIPSeqRawResponse>(`/api/v1/features/chipseq/genes/${geneId}`, {
      params: {
        mark_type: filters?.mark_type,
        min_fold_enrichment: filters?.min_fold_enrichment,
        max_fold_enrichment: filters?.max_fold_enrichment,
        max_qvalue: filters?.max_qvalue,
        max_pvalue: filters?.max_pvalue,
        min_signal: filters?.min_signal,
        relative_position: filters?.relative_position,
        cell_type: filters?.cell_type,
        flanking: filters?.flanking,
        page: filters?.page,
        page_size: filters?.page_size,
        sort_by: filters?.sort_by,
        sort_order: filters?.sort_order,
      },
    }),

  /**
   * Get ChIP-seq summary statistics for a gene and mark type
   * @param geneId - Gene ID
   * @param markType - Histone modification mark type
   */
  getGeneSummary: (geneId: number, markType: MarkType) =>
    apiClient.get<ChIPSeqSummary>(`/api/v1/features/chipseq/genes/${geneId}/summary`, {
      params: { mark_type: markType },
    }),

  /**
   * Compare multiple ChIP-seq marks for a gene
   * @param geneId - Gene ID
   * @param marks - Array of mark types to compare
   * @param flanking - Flanking region in bp (optional)
   */
  compareMarks: (geneId: number, marks: MarkType[], flanking?: number) =>
    apiClient.get<RawChIPSeqCompareResponse>(`/api/v1/features/chipseq/genes/${geneId}/compare`, {
      params: {
        marks: marks.join(','),
        flanking,
      },
    }),

  /**
   * Export ChIP-seq peaks as BED format
   * Opens a new tab/window for download
   * @param geneId - Gene ID
   * @param filters - Optional filters
   */
  exportPeaksToBED: (geneId: number, filters?: ChIPSeqFilters) => {
    const params = new URLSearchParams()

    if (filters?.mark_type) params.append('mark_type', filters.mark_type)
    if (filters?.min_fold_enrichment !== undefined) {
      params.append('min_fold_enrichment', String(filters.min_fold_enrichment))
    }
    if (filters?.max_qvalue !== undefined) {
      params.append('max_qvalue', String(filters.max_qvalue))
    }
    if (filters?.relative_position) {
      params.append('relative_position', filters.relative_position)
    }
    if (filters?.flanking !== undefined) {
      params.append('flanking', String(filters.flanking))
    }

    const queryString = params.toString()
    const url = `${API_BASE_URL}/api/v1/features/chipseq/genes/${geneId}/export${
      queryString ? `?${queryString}` : ''
    }`
    window.open(url, '_blank')
  },

  /**
   * Export multi-mark comparison as CSV
   * @param geneId - Gene ID
   * @param marks - Array of mark types
   */
  exportComparisonToCSV: (geneId: number, marks: MarkType[]) => {
    const params = new URLSearchParams()
    params.append('marks', marks.join(','))
    params.append('format', 'csv')

    const url = `${API_BASE_URL}/api/v1/features/chipseq/genes/${geneId}/compare/export?${params.toString()}`
    window.open(url, '_blank')
  },

  /**
   * Compare same mark across multiple cell lines
   * @param geneId - Gene ID
   * @param markType - Single mark type to compare
   * @param cellTypes - Array of cell types to compare
   * @param flanking - Flanking region in bp (optional)
   */
  compareCellLines: (
    geneId: number,
    markType: MarkType,
    cellTypes: string[],
    flanking?: number
  ) =>
    apiClient.get<CellLineComparisonResponse>(
      `/api/v1/features/chipseq/genes/${geneId}/compare-cell-lines`,
      {
        params: {
          mark_type: markType,
          cell_types: cellTypes.join(','),
          flanking,
        },
      }
    ),

  /**
   * Get heatmap matrix data for multiple marks and cell types
   * Returns a 2D matrix: rows = cell types, columns = marks
   * @param geneId - Gene ID
   * @param marks - Array of mark types (X-axis)
   * @param cellTypes - Array of cell types (Y-axis)
   * @param metric - Metric to use for matrix values
   * @param flanking - Flanking region in bp (optional)
   */
  getHeatmapMatrix: (
    geneId: number,
    marks: MarkType[],
    cellTypes: string[],
    metric: HeatmapMetricType,
    flanking?: number
  ) =>
    apiClient.get<HeatmapMatrixResponse>(
      `/api/v1/features/chipseq/genes/${geneId}/heatmap-matrix`,
      {
        params: {
          marks: marks.join(','),
          cell_types: cellTypes.join(','),
          metric,
          flanking,
        },
      }
    ),

  // =============================================================================
  // Experiments API
  // =============================================================================

  /**
   * List ChIP-seq experiments with filtering options
   * Supports filtering by species, mark type, cell type, and data source
   * @param filters - Optional filter parameters
   */
  listExperiments: (filters?: ChIPSeqExperimentFilters) =>
    apiClient.get<ChIPSeqExperimentListResponse>('/api/v1/features/chipseq/experiments', {
      params: filters,
    }),

  /**
   * Get details for a specific ChIP-seq experiment
   * @param experimentId - Experiment ID
   */
  getExperiment: (experimentId: number) =>
    apiClient.get<ChIPSeqExperiment>(`/api/v1/features/chipseq/experiments/${experimentId}`),

  // =============================================================================
  // Global Statistics API
  // =============================================================================

  /**
   * Get global ChIP-seq statistics
   * Returns overall counts and per-mark statistics
   * Uses materialized view for fast response
   */
  getGlobalStats: () =>
    apiClient.get<ChIPSeqGlobalStats>('/api/v1/features/chipseq/stats'),
}

/**
 * Query key factory for React Query
 * Provides consistent query keys for caching and invalidation
 */
export const chipseqQueryKeys = {
  /** Base key for all ChIP-seq queries */
  all: ['chipseq'] as const,

  /** Available marks for a species */
  availableMarks: (speciesId: number) =>
    [...chipseqQueryKeys.all, 'marks', speciesId] as const,

  /** Gene-level queries */
  gene: (geneId: number) =>
    [...chipseqQueryKeys.all, 'gene', geneId] as const,

  /** Peaks for a gene with filters */
  peaks: (geneId: number, filters: ChIPSeqFilters) =>
    [...chipseqQueryKeys.gene(geneId), 'peaks', filters] as const,

  /** Summary for a gene and mark type */
  summary: (geneId: number, markType: MarkType) =>
    [...chipseqQueryKeys.gene(geneId), 'summary', markType] as const,

  /** Comparison data for multiple marks */
  compare: (geneId: number, marks: MarkType[]) =>
    [...chipseqQueryKeys.gene(geneId), 'compare', marks.sort().join(',')] as const,

  /** Cell line comparison data for a single mark across multiple cell types */
  compareCellLines: (geneId: number, markType: MarkType, cellTypes: string[]) =>
    [...chipseqQueryKeys.gene(geneId), 'compare-cell-lines', markType, cellTypes.sort().join(',')] as const,

  /** Heatmap matrix data for multiple marks and cell types */
  heatmapMatrix: (geneId: number, marks: MarkType[], cellTypes: string[], metric: HeatmapMetricType) =>
    [...chipseqQueryKeys.gene(geneId), 'heatmap-matrix', marks.sort().join(','), cellTypes.sort().join(','), metric] as const,

  /** All experiments */
  experiments: () => [...chipseqQueryKeys.all, 'experiments'] as const,

  /** Experiments with filters */
  experimentsList: (filters: ChIPSeqExperimentFilters) =>
    [...chipseqQueryKeys.experiments(), 'list', filters] as const,

  /** Single experiment by ID */
  experiment: (experimentId: number) =>
    [...chipseqQueryKeys.experiments(), experimentId] as const,

  /** Global statistics */
  globalStats: () => [...chipseqQueryKeys.all, 'global-stats'] as const,
}
