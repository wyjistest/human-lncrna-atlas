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
  GeneChIPSeqRawResponse,
  ChIPSeqPeak,
  RawChIPSeqCompareResponse,
  MarkComparisonData,
  CellLineComparisonResponse,
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
      const rawData: GeneChIPSeqRawResponse = response.data

      // Get peaks for the selected mark type
      const markType = filters.mark_type
      const allPeaks = markType && rawData.marks[markType] ? rawData.marks[markType] : []

      // Transform GenePeakAssociation to ChIPSeqPeak format
      const transformedPeaks: ChIPSeqPeak[] = allPeaks.map((peak) => ({
        peak_id: peak.peak_id,
        gene_id: rawData.gene_id,
        mark_type: peak.mark_type,
        chromosome: peak.chromosome,
        peak_start: peak.peak_start,
        peak_end: peak.peak_end,
        peak_width: peak.peak_end - peak.peak_start,
        summit_position: peak.summit_position,
        fold_enrichment: peak.fold_enrichment,
        log2_fold_enrichment: peak.fold_enrichment ? Math.log2(peak.fold_enrichment) : null,
        signal_value: null,
        pvalue: null,
        qvalue: peak.qvalue,
        neg_log10_qvalue: peak.qvalue ? -Math.log10(peak.qvalue) : null,
        overlap_type: peak.overlap_type as 'promoter' | 'gene_body' | 'upstream' | 'downstream',
        distance_to_tss: peak.distance_to_tss,
        overlap_bp: peak.overlap_bp,
        mark_category: peak.mark_category as 'repressive' | 'activating' | 'enhancer' | 'elongation' | 'other',
        experiment_id: peak.experiment_id,
      }))

      // Client-side pagination
      const page = filters.page ?? 1
      const pageSize = filters.page_size ?? 20
      const startIndex = (page - 1) * pageSize
      const endIndex = startIndex + pageSize
      const paginatedPeaks = transformedPeaks.slice(startIndex, endIndex)

      return {
        total: transformedPeaks.length,
        items: paginatedPeaks,
        page,
        page_size: pageSize,
      }
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
      const rawData: RawChIPSeqCompareResponse = response.data

      // Transform raw backend response to frontend expected format
      const transformedMarks: MarkComparisonData[] = rawData.marks.map((m) => ({
        mark_type: m.mark_type,
        summary: {
          mark_type: m.mark_type,
          total_peaks: m.peak_count,
          avg_signal: 0, // Not provided by backend
          max_signal: 0, // Not provided by backend
          avg_fold_enrichment: m.avg_fold_enrichment ?? 0,
          promoter_peaks: 0, // Not provided by backend
          gene_body_peaks: 0, // Not provided by backend
          upstream_peaks: 0, // Not provided by backend
          downstream_peaks: 0, // Not provided by backend
          position_distribution: {},
          median_fold_enrichment: m.median_fold_enrichment ?? undefined,
          std_fold_enrichment: m.std_fold_enrichment ?? undefined,
          total_coverage_bp: m.total_coverage_bp ?? undefined,
          peak_width_percentiles: m.peak_width_percentiles ?? undefined,
        },
        top_peaks: (m.peaks || []).map((peak) => ({
          peak_id: peak.peak_id,
          gene_id: rawData.gene_id,
          mark_type: peak.mark_type,
          chromosome: peak.chromosome,
          peak_start: peak.peak_start,
          peak_end: peak.peak_end,
          peak_width: peak.peak_end - peak.peak_start,
          summit_position: peak.summit_position ?? undefined,
          signal_value: 0, // Not provided by backend
          pvalue: 0, // Not provided by backend
          qvalue: peak.qvalue ?? 0,
          fold_enrichment: peak.fold_enrichment ?? 0,
        })),
      }))

      return {
        gene_id: rawData.gene_id,
        gene_name: rawData.gene_name,
        marks: transformedMarks,
        overlap_stats: rawData.overlap_statistics,
        overlapping_regions: rawData.overlapping_regions,
        has_bivalent_domain: rawData.bivalent_regions && rawData.bivalent_regions.length > 0,
      }
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
        queryFn: async (): Promise<ChIPSeqResponse> => {
          const response = await chipseqApi.getGenePeaks(geneId, filters)
          const rawData: GeneChIPSeqRawResponse = response.data

          // Get peaks for the selected mark type
          const markType = filters.mark_type
          const allPeaks = markType && rawData.marks[markType] ? rawData.marks[markType] : []

          // Transform GenePeakAssociation to ChIPSeqPeak format
          const transformedPeaks: ChIPSeqPeak[] = allPeaks.map((peak) => ({
            peak_id: peak.peak_id,
            gene_id: rawData.gene_id,
            mark_type: peak.mark_type,
            chromosome: peak.chromosome,
            peak_start: peak.peak_start,
            peak_end: peak.peak_end,
            peak_width: peak.peak_end - peak.peak_start,
            summit_position: peak.summit_position,
            fold_enrichment: peak.fold_enrichment,
            log2_fold_enrichment: peak.fold_enrichment ? Math.log2(peak.fold_enrichment) : null,
            signal_value: null,
            pvalue: null,
            qvalue: peak.qvalue,
            neg_log10_qvalue: peak.qvalue ? -Math.log10(peak.qvalue) : null,
            overlap_type: peak.overlap_type as 'promoter' | 'gene_body' | 'upstream' | 'downstream',
            distance_to_tss: peak.distance_to_tss,
            overlap_bp: peak.overlap_bp,
            mark_category: peak.mark_category as 'repressive' | 'activating' | 'enhancer' | 'elongation' | 'other',
            experiment_id: peak.experiment_id,
          }))

          // Client-side pagination
          const page = filters.page ?? 1
          const pageSize = filters.page_size ?? 20
          const startIndex = (page - 1) * pageSize
          const endIndex = startIndex + pageSize
          const paginatedPeaks = transformedPeaks.slice(startIndex, endIndex)

          return {
            total: transformedPeaks.length,
            items: paginatedPeaks,
            page,
            page_size: pageSize,
          }
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

/**
 * Hook to fetch cell line comparison data
 * Compares the same mark across multiple cell lines
 *
 * @param geneId - Gene ID
 * @param markType - Mark type to compare
 * @param cellTypes - Array of cell types to compare
 * @param flanking - Flanking region in bp
 * @param options - Additional query options
 *
 * @example
 * ```tsx
 * const { data, isLoading } = useChIPSeqCellLineCompare(
 *   123,
 *   'H3K27me3',
 *   ['K562', 'GM12878', 'HepG2']
 * )
 * ```
 */
export function useChIPSeqCellLineCompare(
  geneId: number,
  markType: MarkType | undefined,
  cellTypes: string[],
  flanking: number = 10000,
  options?: { enabled?: boolean }
) {
  return useQuery({
    queryKey: chipseqQueryKeys.compareCellLines(geneId, markType || 'H3K27me3', cellTypes),
    queryFn: async (): Promise<CellLineComparisonResponse> => {
      if (!markType) throw new Error('Mark type is required')
      const response = await chipseqApi.compareCellLines(geneId, markType, cellTypes, flanking)
      return response.data
    },
    enabled: !!markType && cellTypes.length >= 2 && (options?.enabled ?? true),
    staleTime: 30 * 60 * 1000, // 30 minutes
  })
}
