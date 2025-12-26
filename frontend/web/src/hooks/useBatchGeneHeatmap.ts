/**
 * useBatchGeneHeatmap Hook
 * Custom hook for batch gene heatmap data fetching with React Query
 * Uses useQueries for parallel queries of multiple genes
 * Phase 2.10 - Batch Gene Heatmap Feature
 */

import { useQueries, QueryClient } from '@tanstack/react-query'
import { useMemo } from 'react'
import { chipseqApi, chipseqQueryKeys } from '@/api/chipseq'
import type { HeatmapMetricType, MarkType } from '@/types/chipseq'

interface GeneInfo {
  gene_id: number
  gene_name: string
  chromosome?: string
  start?: number
  end?: number
}

interface HeatmapMatrixData {
  gene_name: string
  gene_id: number
  chromosome?: string
  marks: string[]
  cell_types: string[]
  matrix: Array<Array<number | null>>
}

interface UseBatchGeneHeatmapOptions {
  /** Whether to enable queries */
  enabled?: boolean
  /** Cache time in ms */
  staleTime?: number
  /** Retry count */
  retry?: number
}

/**
 * Hook to fetch batch heatmap matrix data for multiple genes
 *
 * Uses TanStack Query's useQueries to fetch data for multiple genes in parallel.
 * Each gene query fetches the heatmap matrix for all marks and cell types.
 *
 * @param genes - Array of gene info objects
 * @param marks - Array of mark types to include
 * @param cellTypes - Array of cell type names
 * @param metric - Metric to visualize
 * @param flanking - Flanking region in bp
 * @param options - Query options
 *
 * @example
 * ```tsx
 * const { data, isLoading, errors } = useBatchGeneHeatmap(
 *   [{ gene_id: 123, gene_name: 'BRCA1' }],
 *   ['H3K27me3', 'H3K4me3'],
 *   ['H1', 'HepG2'],
 *   'median_fold_enrichment'
 * )
 * ```
 */
export function useBatchGeneHeatmap(
  genes: GeneInfo[],
  marks: MarkType[],
  cellTypes: string[],
  metric: HeatmapMetricType,
  flanking: number = 10000,
  options?: UseBatchGeneHeatmapOptions
) {
  const enabled = options?.enabled ?? true
  const staleTime = options?.staleTime ?? 30 * 60 * 1000 // 30 minutes
  const retry = options?.retry ?? 2

  // Create queries for each gene
  const queries = useMemo(
    () =>
      genes.map((gene) => ({
        queryKey: chipseqQueryKeys.heatmapMatrix(gene.gene_id, marks, cellTypes, metric),
        queryFn: async ({ signal }: { signal: AbortSignal }) => {
          const response = await chipseqApi.getHeatmapMatrix(
            gene.gene_id,
            marks,
            cellTypes,
            metric,
            flanking,
            signal
          )
          return response.data
        },
        staleTime,
        retry,
        enabled: enabled && genes.length > 0 && marks.length > 0 && cellTypes.length > 0,
      })),
    [genes, marks, cellTypes, metric, flanking, staleTime, retry, enabled]
  )

  // Execute all queries in parallel
  const results = useQueries({ queries })

  // Combine results
  const data = useMemo(() => {
    return results
      .map((result, index) => {
        if (!result.data || !genes[index]) return null

        // Map API response to HeatmapMatrixData format
        const apiData = result.data
        const gene = genes[index]

        return {
          gene_name: gene.gene_name,
          gene_id: gene.gene_id,
          chromosome: gene.chromosome,
          marks: apiData.marks || marks,
          cell_types: apiData.cell_types || cellTypes,
          matrix: apiData.matrix || [],
        } as HeatmapMatrixData
      })
      .filter((item): item is HeatmapMatrixData => item !== null)
  }, [results, genes, marks, cellTypes])

  // Determine overall loading state
  const isLoading = useMemo(() => results.some((r) => r.isPending), [results])

  // Determine overall error state
  const error = useMemo(() => {
    const errors = results.filter((r) => r.error).map((r) => r.error)
    return errors.length > 0 ? errors[0] : null
  }, [results])

  // Check if any queries succeeded
  const isSuccess = useMemo(() => results.some((r) => r.isSuccess), [results])

  // Get individual query status
  const queryStatus = useMemo(
    () =>
      results.map((result, index) => ({
        gene_id: genes[index]?.gene_id,
        gene_name: genes[index]?.gene_name,
        isPending: result.isPending,
        isSuccess: result.isSuccess,
        isError: result.isError,
        error: result.error,
      })),
    [results, genes]
  )

  return {
    /** Aggregated data for all genes */
    data,
    /** Loading state */
    isLoading,
    /** Any error that occurred */
    error,
    /** Whether at least one query succeeded */
    isSuccess,
    /** Status of individual gene queries */
    queryStatus,
    /** Raw results from each query */
    results,
  }
}

/**
 * Prefetch batch heatmap data using query client
 * Useful for preloading when user hovers over gene selections
 *
 * @example
 * ```tsx
 * const queryClient = useQueryClient()
 *
 * const handleGeneHover = (gene: GeneInfo) => {
 *   prefetchBatchGeneHeatmap(queryClient, [gene], marks, cellTypes, metric)
 * }
 * ```
 */
export async function prefetchBatchGeneHeatmap(
  queryClient: QueryClient,
  genes: GeneInfo[],
  marks: MarkType[],
  cellTypes: string[],
  metric: HeatmapMetricType,
  flanking: number = 10000
) {
  const promises = genes.map((gene) =>
    queryClient.prefetchQuery({
      queryKey: chipseqQueryKeys.heatmapMatrix(gene.gene_id, marks, cellTypes, metric),
      queryFn: async ({ signal }) => {
        const response = await chipseqApi.getHeatmapMatrix(
          gene.gene_id,
          marks,
          cellTypes,
          metric,
          flanking,
          signal
        )
        return response.data
      },
      staleTime: 30 * 60 * 1000,
    })
  )

  await Promise.all(promises)
}

/**
 * Hook to get combined loading and error states for batch queries
 *
 * @param results - Results from useBatchGeneHeatmap
 */
export function useBatchGeneHeatmapStatus(results: ReturnType<typeof useBatchGeneHeatmap>) {
  const { queryStatus } = results

  return useMemo(() => {
    const loadingGenes = queryStatus.filter((s) => s.isPending).map((s) => s.gene_name)
    const failedGenes = queryStatus.filter((s) => s.isError).map((s) => s.gene_name)
    const successGenes = queryStatus.filter((s) => s.isSuccess).map((s) => s.gene_name)

    return {
      loadingGenes,
      failedGenes,
      successGenes,
      loadingCount: loadingGenes.length,
      failedCount: failedGenes.length,
      successCount: successGenes.length,
      allComplete: queryStatus.every((s) => !s.isPending),
      anySuccess: successGenes.length > 0,
      anyError: failedGenes.length > 0,
    }
  }, [queryStatus])
}

export default useBatchGeneHeatmap
