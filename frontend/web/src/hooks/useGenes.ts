/**
 * Gene-related React Query Hooks
 *
 * This module provides hooks for fetching and managing gene data,
 * including gene lists, details, regulations, diseases, and orthologs.
 *
 * **API Endpoints Used**:
 * - GET /api/v1/genes - Paginated gene list
 * - GET /api/v1/genes/:id - Gene detail
 * - GET /api/v1/genes/:id/orthologs - Ortholog genes
 * - GET /api/v1/regulations - Gene regulations (via regulationsApi)
 * - GET /api/v1/diseases/gene/:id - Gene disease associations
 *
 * @module hooks/useGenes
 */

import { useQuery, useQueryClient } from '@tanstack/react-query'
import { useCallback } from 'react'
import { genesApi } from '@/api/genes'
import { regulationsApi } from '@/api/regulations'
import { diseasesApi } from '@/api/diseases'
import { queryKeys } from './queryKeys'

/**
 * Hook to fetch paginated gene list with filtering options
 *
 * Retrieves genes from the database with support for pagination, species filtering,
 * gene type filtering, and search functionality. Used primarily on the Genes list page.
 *
 * **Use Cases**:
 * - Gene list page with pagination
 * - Filtering genes by species or type
 * - Searching genes by name or Ensembl ID
 *
 * **Performance**:
 * - Response time: 100-300ms (depends on filters)
 * - Uses React Query's built-in caching
 *
 * **Return Values**:
 * - data: Paginated response with items array and pagination metadata
 * - isLoading: True during initial load
 * - isError: True if request failed
 * - error: Error object if request failed
 *
 * @param params - Query parameters for gene list
 * @param params.page - Page number (1-indexed)
 * @param params.page_size - Number of items per page
 * @param params.gene_type - Filter by gene type (lncRNA/protein_coding)
 * @param params.species_id - Filter by species ID (1=Human, 2=Chimp, 3=Macaque, 4=Marmoset)
 * @param params.search - Search by gene name or Ensembl ID
 * @returns React Query result with paginated gene list
 *
 * @example
 * ```tsx
 * // Basic usage with pagination
 * const { data, isLoading, error } = useGenes({ page: 1, page_size: 20 })
 *
 * if (isLoading) return <Spin />
 * if (error) return <ErrorState error={error} />
 *
 * return (
 *   <Table
 *     dataSource={data?.items}
 *     pagination={{
 *       total: data?.total,
 *       current: data?.page,
 *       pageSize: data?.page_size,
 *     }}
 *   />
 * )
 * ```
 *
 * @example
 * ```tsx
 * // With filters
 * const { data } = useGenes({
 *   page: 1,
 *   page_size: 20,
 *   species_id: 1,
 *   gene_type: 'lncRNA',
 *   search: 'HOTAIR',
 * })
 * ```
 */
export const useGenes = (
  params: Parameters<typeof genesApi.list>[0],
  options?: { enabled?: boolean }
) => {
  return useQuery({
    queryKey: queryKeys.genes.list(params),
    queryFn: async ({ signal }) => {
      const { data } = await genesApi.list(params, signal)
      return data
    },
    enabled: options?.enabled ?? true,
    meta: { skipGlobalErrorHandler: true },
  })
}

/**
 * Hook to prefetch gene list data for adjacent pages
 *
 * Enables prefetching gene data to improve perceived performance when users
 * navigate between pages. Call this when user is browsing the current page
 * to preload adjacent pages into the cache.
 *
 * **Use Cases**:
 * - Prefetch next/previous page when user is viewing current page
 * - Improve page navigation speed for large datasets
 *
 * **Performance**:
 * - Prefetches in background without blocking UI
 * - Data cached according to React Query settings
 *
 * @returns Callback function to trigger prefetch
 *
 * @example
 * ```tsx
 * const prefetchGenes = usePrefetchGenes()
 *
 * // Prefetch next page when user is on current page
 * useEffect(() => {
 *   prefetchGenes({ page: currentPage + 1, page_size: 20 })
 * }, [currentPage])
 *
 * // Or prefetch on hover
 * <button onMouseEnter={() => prefetchGenes({ page: 2 })}>
 *   Page 2
 * </button>
 * ```
 */
export const usePrefetchGenes = () => {
  const queryClient = useQueryClient()

  return useCallback((params: Parameters<typeof genesApi.list>[0]) => {
    queryClient.prefetchQuery({
      queryKey: queryKeys.genes.list(params),
      queryFn: async ({ signal }) => {
        const { data } = await genesApi.list(params, signal)
        return data
      },
    })
  }, [queryClient])
}

/**
 * Hook to fetch detailed information for a single gene
 *
 * Retrieves comprehensive gene data including genomic location, annotations,
 * and related information. Used on the Gene Detail page to display all
 * available gene information.
 *
 * **Use Cases**:
 * - Gene detail page (/genes/:id)
 * - Gene info tooltip/modal in other components
 * - Pre-loading gene data for navigation
 *
 * **Return Values**:
 * - data: Complete gene details (GeneDetail type)
 * - isLoading: True during initial load
 * - isError: True if gene not found or request failed
 * - error: Error object with details
 *
 * **Query Behavior**:
 * - Enabled only when geneId is truthy (> 0)
 * - Uses React Query caching
 *
 * @param geneId - The gene ID to fetch details for
 * @returns React Query result with gene details
 *
 * @example
 * ```tsx
 * // On Gene Detail page
 * const { id } = useParams<{ id: string }>()
 * const geneId = parseInt(id || '0')
 * const { data: gene, isLoading, error } = useGeneDetail(geneId)
 *
 * if (isLoading) return <PageSkeleton />
 * if (error) return <ErrorState error={error} />
 *
 * return (
 *   <div>
 *     <h1>{gene.gene_name}</h1>
 *     <p>Location: {gene.chromosome}:{gene.start_position}-{gene.end_position}</p>
 *   </div>
 * )
 * ```
 */
export const useGeneDetail = (geneId: number) => {
  return useQuery({
    queryKey: queryKeys.genes.detail(geneId),
    queryFn: async ({ signal }) => {
      const { data } = await genesApi.detail(geneId, signal)
      return data
    },
    enabled: !!geneId,
    meta: { skipGlobalErrorHandler: true },
  })
}

/**
 * 获取基因的调控关系列表
 */
export const useGeneRegulations = (geneId: number, params?: { page?: number; page_size?: number }) => {
  const paginationParams = {
    page: params?.page || 1,
    page_size: params?.page_size || 20,
  }

  return useQuery({
    queryKey: queryKeys.genes.regulations(geneId, paginationParams),
    queryFn: async ({ signal }) => {
      const { data } = await regulationsApi.list({
        lncrna_gene_id: geneId,
        ...paginationParams,
      }, signal)
      return data
    },
    enabled: !!geneId,
  })
}

/**
 * 获取基因的疾病关联列表
 */
export const useGeneDiseases = (geneId: number) => {
  return useQuery({
    queryKey: queryKeys.genes.diseases(geneId),
    queryFn: async ({ signal }) => {
      const { data } = await diseasesApi.getGeneAssociations(geneId, signal)
      return data
    },
    enabled: !!geneId,
  })
}

/**
 * 获取基因的直系同源基因列表
 *
 * Phase 6.2 - Ortholog Browser feature
 *
 * 用途: OrthologBrowser 组件，显示跨物种直系同源基因
 *
 * @param geneId - 基因 ID
 * @returns 直系同源基因列表
 */
export const useGeneOrthologs = (geneId: number) => {
  return useQuery({
    queryKey: queryKeys.genes.orthologs(geneId),
    queryFn: async ({ signal }) => {
      const { data } = await genesApi.getOrthologs(geneId, signal)
      return data
    },
    enabled: geneId > 0,
    staleTime: 5 * 60 * 1000, // 5 minutes cache
  })
}
