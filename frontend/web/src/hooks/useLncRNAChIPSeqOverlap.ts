/**
 * lncRNA-ChIP-seq Overlap Custom Hooks
 * Phase 3.0 - Task 1.4
 *
 * React Query hooks for fetching lncRNA-ChIP-seq overlap data.
 * Provides data fetching, caching, and state management for overlap analysis.
 */

import { useQuery, useQueryClient, type UseQueryOptions } from '@tanstack/react-query'
import { useCallback } from 'react'
import lncRNAChIPSeqOverlapApi, { overlapQueryKeys } from '@/api/lncRNAChIPSeqOverlapApi'
import type {
  OverlapFilters,
  OverlapResponse,
  OverlapSummary,
  OverlapHeatmapData,
  OverlapHeatmapXAxis,
  OverlapHeatmapYAxis,
  OverlapHeatmapMetric,
} from '@/types/lncRNAChIPSeqOverlap'

/**
 * Hook to fetch lncRNA-ChIP-seq overlaps with filtering and pagination
 *
 * @param filters - Query filters including pagination
 * @param options - Additional React Query options
 * @returns Query result with overlap data
 *
 * @example
 * ```tsx
 * const { data, isLoading, error } = useLncRNAChIPSeqOverlaps({
 *   mark_type: 'H3K27me3',
 *   cell_type: 'K562',
 *   page: 1,
 *   page_size: 20
 * })
 * ```
 */
export function useLncRNAChIPSeqOverlaps(
  filters: OverlapFilters,
  options?: Omit<UseQueryOptions<OverlapResponse, Error>, 'queryKey' | 'queryFn'>
) {
  return useQuery<OverlapResponse, Error>({
    queryKey: overlapQueryKeys.overlaps(filters),
    queryFn: async () => {
      const response = await lncRNAChIPSeqOverlapApi.getOverlaps(filters)
      return response.data
    },
    staleTime: 30 * 60 * 1000,  // 30 minutes cache
    gcTime: 60 * 60 * 1000,     // 1 hour in cache
    retry: 2,
    retryDelay: (attemptIndex) => Math.min(1000 * 2 ** attemptIndex, 30000),
    ...options
  })
}

/**
 * Hook to fetch summary statistics for overlap analysis (Phase 2)
 *
 * @param filters - Optional filters to scope the summary
 * @param options - Additional React Query options
 * @returns Query result with summary statistics
 *
 * @example
 * ```tsx
 * const { data: summary } = useLncRNAChIPSeqOverlapSummary({
 *   mark_type: 'H3K27me3'
 * }, {
 *   enabled: showSummary
 * })
 * ```
 */
export function useLncRNAChIPSeqOverlapSummary(
  filters?: Partial<OverlapFilters>,
  options?: Omit<UseQueryOptions<OverlapSummary, Error>, 'queryKey' | 'queryFn'>
) {
  return useQuery<OverlapSummary, Error>({
    queryKey: overlapQueryKeys.summary(filters),
    queryFn: async () => {
      const response = await lncRNAChIPSeqOverlapApi.getSummary(filters)
      return response.data
    },
    staleTime: 30 * 60 * 1000,
    gcTime: 60 * 60 * 1000,
    enabled: options?.enabled ?? false,  // Phase 2 feature - disabled by default
    ...options
  })
}

/**
 * Hook to prefetch overlap data for performance optimization
 * Useful for preloading data when user is likely to navigate to it
 *
 * @returns Prefetch function
 *
 * @example
 * ```tsx
 * const prefetchOverlaps = usePrefetchOverlaps()
 *
 * // On hover or before navigation
 * const handleMouseEnter = () => {
 *   prefetchOverlaps({
 *     mark_type: 'H3K4me3',
 *     page: 2,
 *     page_size: 20
 *   })
 * }
 * ```
 */
export function usePrefetchOverlaps() {
  const queryClient = useQueryClient()

  return useCallback(
    (filters: OverlapFilters) => {
      queryClient.prefetchQuery({
        queryKey: overlapQueryKeys.overlaps(filters),
        queryFn: async () => {
          const response = await lncRNAChIPSeqOverlapApi.getOverlaps(filters)
          return response.data
        },
        staleTime: 30 * 60 * 1000
      })
    },
    [queryClient]
  )
}

/**
 * Hook to invalidate overlap queries
 * Useful when data is updated and cache needs to be refreshed
 *
 * @returns Invalidation function
 *
 * @example
 * ```tsx
 * const invalidateOverlaps = useInvalidateOverlaps()
 *
 * // After data update
 * const handleDataUpdate = async () => {
 *   await updateData()
 *   invalidateOverlaps()  // Refresh all overlap queries
 * }
 * ```
 */
export function useInvalidateOverlaps() {
  const queryClient = useQueryClient()

  return useCallback(() => {
    queryClient.invalidateQueries({
      queryKey: overlapQueryKeys.all
    })
  }, [queryClient])
}

/**
 * Combined hook for fetching both overlaps and summary in parallel
 * Useful for dashboard views that need both datasets
 *
 * @param filters - Query filters
 * @param enableSummary - Whether to fetch summary statistics
 * @returns Combined query results
 *
 * @example
 * ```tsx
 * const { overlaps, summary, isLoading } = useLncRNAChIPSeqOverlapData({
 *   mark_type: 'H3K27me3',
 *   page: 1,
 *   page_size: 20
 * }, true)
 * ```
 */
export function useLncRNAChIPSeqOverlapData(
  filters: OverlapFilters,
  enableSummary: boolean = false
) {
  const overlapsQuery = useLncRNAChIPSeqOverlaps(filters)

  const summaryQuery = useLncRNAChIPSeqOverlapSummary(
    filters,
    { enabled: enableSummary }
  )

  return {
    overlaps: overlapsQuery.data,
    summary: summaryQuery.data,
    isLoading: overlapsQuery.isLoading || (enableSummary && summaryQuery.isLoading),
    isError: overlapsQuery.isError || summaryQuery.isError,
    error: overlapsQuery.error || summaryQuery.error,
    refetch: () => {
      overlapsQuery.refetch()
      if (enableSummary) {
        summaryQuery.refetch()
      }
    },
  }
}

/**
 * Hook to fetch heatmap data for overlap visualization (Phase 3.0 Phase 2)
 *
 * @param xAxis - X-axis dimension (mark_type or cell_type)
 * @param yAxis - Y-axis dimension (lncrna or target_gene)
 * @param metric - Metric to display (count, avg_binding_affinity, total_overlap_length)
 * @param topN - Number of top items to include (default: 50)
 * @param filters - Optional additional filters
 * @param options - Additional React Query options
 * @returns Query result with heatmap data
 *
 * @example
 * ```tsx
 * const { data, isLoading } = useOverlapHeatmap(
 *   'mark_type',
 *   'lncrna',
 *   'count',
 *   50,
 *   { chromosome: 'chr1' }
 * )
 * ```
 */
export function useOverlapHeatmap(
  xAxis: OverlapHeatmapXAxis,
  yAxis: OverlapHeatmapYAxis,
  metric: OverlapHeatmapMetric,
  topN: number = 50,
  filters?: Partial<OverlapFilters>,
  options?: Omit<UseQueryOptions<OverlapHeatmapData, Error>, 'queryKey' | 'queryFn'>
) {
  const params = {
    x_axis: xAxis,
    y_axis: yAxis,
    metric,
    top_n: topN,
    chromosome: filters?.chromosome,
    min_binding_affinity: filters?.min_binding_affinity,
    max_qvalue: filters?.max_qvalue,
  }

  return useQuery<OverlapHeatmapData, Error>({
    queryKey: overlapQueryKeys.heatmap(params),
    queryFn: async () => {
      const response = await lncRNAChIPSeqOverlapApi.getHeatmap(params)
      return response.data
    },
    staleTime: 30 * 60 * 1000,  // 30 minutes cache
    gcTime: 60 * 60 * 1000,     // 1 hour in cache
    retry: 2,
    retryDelay: (attemptIndex) => Math.min(1000 * 2 ** attemptIndex, 30000),
    ...options
  })
}

/**
 * Hook to export overlap data
 * Handles file download for BED and CSV formats (Phase 2)
 *
 * @param filters - Query filters for export
 * @param format - Export format ('bed' or 'csv')
 * @returns Export function with loading state
 */
export function useExportOverlaps(
  filters: OverlapFilters,
  format: 'bed' | 'csv' = 'bed'
) {
  const [isExporting, setIsExporting] = React.useState(false)

  const exportData = useCallback(async () => {
    setIsExporting(true)
    try {
      const response = format === 'bed'
        ? await lncRNAChIPSeqOverlapApi.exportToBED(filters)
        : await lncRNAChIPSeqOverlapApi.exportToCSV(filters)

      // Create download link
      const blob = new Blob([response.data], {
        type: format === 'bed' ? 'text/plain' : 'text/csv'
      })
      const url = window.URL.createObjectURL(blob)
      const link = document.createElement('a')
      link.href = url
      link.download = `lncrna_chipseq_overlap_${Date.now()}.${format}`
      document.body.appendChild(link)
      link.click()
      document.body.removeChild(link)
      window.URL.revokeObjectURL(url)
    } catch (error) {
      console.error('Export failed:', error)
      throw error
    } finally {
      setIsExporting(false)
    }
  }, [filters, format])

  return {
    exportData,
    isExporting
  }
}

// React import for useState
import React from 'react'
