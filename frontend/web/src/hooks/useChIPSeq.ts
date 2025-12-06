/**
 * ChIP-seq Custom Hooks
 * Phase 2.2 - React Query hooks for ChIP-seq data fetching
 *
 * Provides:
 * - useChIPSeqPeaks: Fetch paginated peak data
 * - useChIPSeqSummary: Fetch summary statistics
 * - useChIPSeqMarks: Fetch available marks
 * - useChIPSeqCompare: Fetch multi-mark comparison data
 */

import { useQuery, useQueryClient } from '@tanstack/react-query'
import { useCallback, useMemo } from 'react'
import { chipseqApi, chipseqQueryKeys } from '@/api/chipseq'
import { getMarkConfig } from '@/config/markConfigs'
import type {
  MarkType,
  ChIPSeqFilters,
  ChIPSeqResponse,
  ChIPSeqSummary,
  ChIPSeqCompareResponse,
  AvailableMarksResponse,
} from '@/types/chipseq'

/**
 * Hook to fetch ChIP-seq peaks for a gene
 *
 * @param geneId - Gene ID
 * @param filters - Filter and pagination options
 * @param options - Additional query options
 *
 * @example
 * ```tsx
 * const { data, isLoading } = useChIPSeqPeaks(123, {
 *   mark_type: 'H3K27me3',
 *   page: 1,
 *   page_size: 20
 * })
 * ```
 */
export function useChIPSeqPeaks(
  geneId: number,
  filters: ChIPSeqFilters,
  options?: {
    enabled?: boolean
    staleTime?: number
  }
) {
  return useQuery({
    queryKey: chipseqQueryKeys.peaks(geneId, filters),
    queryFn: async (): Promise<ChIPSeqResponse> => {
      const response = await chipseqApi.getGenePeaks(geneId, filters)
      return response.data
    },
    staleTime: options?.staleTime ?? 30 * 60 * 1000, // 30 minutes default
    enabled: (options?.enabled ?? true) && geneId > 0 && !!filters.mark_type,
  })
}

/**
 * Hook to fetch ChIP-seq summary statistics for a gene and mark type
 *
 * @param geneId - Gene ID
 * @param markType - Histone modification mark type
 * @param options - Additional query options
 *
 * @example
 * ```tsx
 * const { data: summary } = useChIPSeqSummary(123, 'H3K27me3')
 * ```
 */
export function useChIPSeqSummary(
  geneId: number,
  markType: MarkType | undefined,
  options?: {
    enabled?: boolean
    staleTime?: number
  }
) {
  return useQuery({
    queryKey: chipseqQueryKeys.summary(geneId, markType!),
    queryFn: async (): Promise<ChIPSeqSummary> => {
      const response = await chipseqApi.getGeneSummary(geneId, markType!)
      return response.data
    },
    staleTime: options?.staleTime ?? 30 * 60 * 1000,
    enabled: (options?.enabled ?? true) && geneId > 0 && !!markType,
  })
}

/**
 * Hook to fetch available ChIP-seq marks for a species
 *
 * @param speciesId - Species ID (default: 1 for Human)
 * @param options - Additional query options
 *
 * @example
 * ```tsx
 * const { data: marks } = useChIPSeqMarks(1)
 * ```
 */
export function useChIPSeqMarks(
  speciesId: number = 1,
  options?: {
    enabled?: boolean
    staleTime?: number
  }
) {
  return useQuery({
    queryKey: chipseqQueryKeys.availableMarks(speciesId),
    queryFn: async (): Promise<AvailableMarksResponse> => {
      const response = await chipseqApi.getAvailableMarks(speciesId)
      return response.data
    },
    staleTime: options?.staleTime ?? 60 * 60 * 1000, // 1 hour default (rarely changes)
    enabled: options?.enabled ?? true,
  })
}

/**
 * Hook to fetch multi-mark comparison data for a gene
 *
 * @param geneId - Gene ID
 * @param marks - Array of mark types to compare
 * @param flanking - Flanking region in bp
 * @param options - Additional query options
 *
 * @example
 * ```tsx
 * const { data } = useChIPSeqCompare(123, ['H3K27me3', 'H3K4me3'])
 * ```
 */
export function useChIPSeqCompare(
  geneId: number,
  marks: MarkType[],
  flanking?: number,
  options?: {
    enabled?: boolean
    staleTime?: number
  }
) {
  return useQuery({
    queryKey: chipseqQueryKeys.compare(geneId, marks),
    queryFn: async (): Promise<ChIPSeqCompareResponse> => {
      const response = await chipseqApi.compareMarks(geneId, marks, flanking)
      return response.data
    },
    staleTime: options?.staleTime ?? 30 * 60 * 1000,
    enabled: (options?.enabled ?? true) && geneId > 0 && marks.length > 0,
  })
}

/**
 * Hook to prefetch ChIP-seq peaks data
 * Useful for preloading data when user hovers over a mark selector
 *
 * @example
 * ```tsx
 * const prefetch = usePrefetchChIPSeqPeaks()
 * // On hover
 * prefetch(123, { mark_type: 'H3K4me3' })
 * ```
 */
export function usePrefetchChIPSeqPeaks() {
  const queryClient = useQueryClient()

  return useCallback(
    (geneId: number, filters: ChIPSeqFilters) => {
      queryClient.prefetchQuery({
        queryKey: chipseqQueryKeys.peaks(geneId, filters),
        queryFn: async () => {
          const response = await chipseqApi.getGenePeaks(geneId, filters)
          return response.data
        },
        staleTime: 30 * 60 * 1000,
      })
    },
    [queryClient]
  )
}

/**
 * Hook to invalidate ChIP-seq cache
 * Useful after data mutations
 *
 * @example
 * ```tsx
 * const invalidate = useInvalidateChIPSeqCache()
 * // After mutation
 * invalidate.gene(123)
 * ```
 */
export function useInvalidateChIPSeqCache() {
  const queryClient = useQueryClient()

  return useMemo(
    () => ({
      /** Invalidate all ChIP-seq queries */
      all: () => queryClient.invalidateQueries({ queryKey: chipseqQueryKeys.all }),

      /** Invalidate queries for a specific gene */
      gene: (geneId: number) =>
        queryClient.invalidateQueries({ queryKey: chipseqQueryKeys.gene(geneId) }),

      /** Invalidate available marks cache */
      marks: (speciesId: number) =>
        queryClient.invalidateQueries({ queryKey: chipseqQueryKeys.availableMarks(speciesId) }),
    }),
    [queryClient]
  )
}

/**
 * Utility hook to get mark configuration with localized names
 * Combines static config with dynamic translation
 *
 * @param markType - Mark type
 * @param t - Translation function (optional)
 *
 * @example
 * ```tsx
 * const config = useMarkConfig('H3K27me3')
 * ```
 */
export function useMarkConfig(markType: MarkType | undefined) {
  return useMemo(() => {
    if (!markType) return null
    return getMarkConfig(markType)
  }, [markType])
}

/**
 * Combined hook for common ChIP-seq data needs
 * Fetches both peaks and summary in parallel
 *
 * @param geneId - Gene ID
 * @param markType - Mark type
 * @param filters - Additional filters
 *
 * @example
 * ```tsx
 * const { peaks, summary, isLoading } = useChIPSeqData(123, 'H3K27me3')
 * ```
 */
export function useChIPSeqData(
  geneId: number,
  markType: MarkType | undefined,
  filters?: Omit<ChIPSeqFilters, 'mark_type'>
) {
  const fullFilters: ChIPSeqFilters = {
    ...filters,
    mark_type: markType,
    page: filters?.page ?? 1,
    page_size: filters?.page_size ?? 20,
  }

  const peaksQuery = useChIPSeqPeaks(geneId, fullFilters, {
    enabled: !!markType,
  })

  const summaryQuery = useChIPSeqSummary(geneId, markType, {
    enabled: !!markType,
  })

  return {
    peaks: peaksQuery.data,
    summary: summaryQuery.data,
    isLoading: peaksQuery.isLoading || summaryQuery.isLoading,
    isError: peaksQuery.isError || summaryQuery.isError,
    error: peaksQuery.error || summaryQuery.error,
    refetch: () => {
      peaksQuery.refetch()
      summaryQuery.refetch()
    },
  }
}
