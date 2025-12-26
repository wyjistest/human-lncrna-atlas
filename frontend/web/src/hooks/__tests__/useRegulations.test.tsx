/**
 * useRegulations Hook Tests
 *
 * Tests for regulation-related React Query hooks including:
 * - useRegulations: Paginated regulation list fetching with filters
 * - usePrefetchRegulations: Prefetching regulation list data
 * - useRegulationDetail: Single regulation detail fetching
 *
 * @module hooks/__tests__/useRegulations
 */
import { renderHook, waitFor } from '@testing-library/react'
import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest'
import type { ReactNode } from 'react'

import {
  useRegulations,
  usePrefetchRegulations,
  useRegulationDetail,
} from '../useRegulations'

// Mock API module
vi.mock('@/api/regulations', () => ({
  regulationsApi: {
    list: vi.fn(),
    getDetail: vi.fn(),
  },
}))

// Import mocked module for type access
import { regulationsApi } from '@/api/regulations'

// Type the mocked functions
const mockRegulationsApiList = vi.mocked(regulationsApi.list)
const mockRegulationsApiGetDetail = vi.mocked(regulationsApi.getDetail)

/**
 * Creates a wrapper component with QueryClientProvider for testing hooks
 * @returns Wrapper component and queryClient instance
 */
const createWrapper = () => {
  const queryClient = new QueryClient({
    defaultOptions: {
      queries: {
        retry: false, // Disable retries for faster tests
        gcTime: 0, // Garbage collect immediately
      },
    },
  })

  const wrapper = ({ children }: { children: ReactNode }) => (
    <QueryClientProvider client={queryClient}>{children}</QueryClientProvider>
  )

  return { wrapper, queryClient }
}

// Mock data fixtures
const mockRegulationListResponse = {
  data: {
    items: [
      {
        regulation_id: 1,
        lncrna_gene_id: 100,
        lncrna_gene_name: 'LNCRNA1',
        lncrna_ensembl_id: 'ENSG00000100',
        target_gene_id: 200,
        target_gene_name: 'TARGET1',
        target_ensembl_id: 'ENSG00000200',
        species_id: 1,
        species_name: 'Human',
        binding_affinity: 185.5,
        chromosome: 'chr1',
        distance: 50000,
      },
      {
        regulation_id: 2,
        lncrna_gene_id: 100,
        lncrna_gene_name: 'LNCRNA1',
        lncrna_ensembl_id: 'ENSG00000100',
        target_gene_id: 201,
        target_gene_name: 'TARGET2',
        target_ensembl_id: 'ENSG00000201',
        species_id: 1,
        species_name: 'Human',
        binding_affinity: 120.3,
        chromosome: 'chr1',
        distance: 75000,
      },
    ],
    total: 2,
    page: 1,
    page_size: 20,
  },
}

const mockRegulationDetailResponse = {
  data: {
    regulation_id: 1,
    lncrna_gene_id: 100,
    lncrna_gene_name: 'LNCRNA1',
    lncrna_ensembl_id: 'ENSG00000100',
    target_gene_id: 200,
    target_gene_name: 'TARGET1',
    target_ensembl_id: 'ENSG00000200',
    species_id: 1,
    species_name: 'Human',
    binding_affinity: 185.5,
    chromosome: 'chr1',
    distance: 50000,
    lncrna_sequence: 'ATCGATCGATCG',
    target_promoter_sequence: 'GCTAGCTAGCTA',
    triplex_forming_oligo: 'TCTCTCTCT',
    triplex_target_site: 'AGAGAGAGA',
  },
}

describe('useRegulations', () => {
  beforeEach(() => {
    vi.clearAllMocks()
  })

  afterEach(() => {
    vi.resetAllMocks()
  })

  describe('useRegulations hook', () => {
    it('returns regulation list data successfully', async () => {
      mockRegulationsApiList.mockResolvedValueOnce(mockRegulationListResponse)

      const { wrapper } = createWrapper()
      const { result } = renderHook(
        () => useRegulations({ page: 1, page_size: 20 }),
        { wrapper }
      )

      // Initially loading
      expect(result.current.isLoading).toBe(true)

      await waitFor(() => {
        expect(result.current.isSuccess).toBe(true)
      })

      expect(result.current.data).toEqual(mockRegulationListResponse.data)
      expect(mockRegulationsApiList).toHaveBeenCalledWith({ page: 1, page_size: 20 }, expect.anything())
    })

    it('handles API errors gracefully', async () => {
      const error = new Error('Network error')
      mockRegulationsApiList.mockRejectedValueOnce(error)

      const { wrapper } = createWrapper()
      const { result } = renderHook(
        () => useRegulations({ page: 1 }),
        { wrapper }
      )

      await waitFor(() => {
        expect(result.current.isError).toBe(true)
      })

      expect(result.current.error).toBeDefined()
    })

    it('supports species_id filter parameter', async () => {
      mockRegulationsApiList.mockResolvedValueOnce(mockRegulationListResponse)

      const { wrapper } = createWrapper()
      const { result } = renderHook(
        () => useRegulations({ page: 1, species_id: 1 }),
        { wrapper }
      )

      await waitFor(() => {
        expect(result.current.isSuccess).toBe(true)
      })

      expect(mockRegulationsApiList).toHaveBeenCalledWith({ page: 1, species_id: 1 }, expect.anything())
    })

    it('supports chromosome filter parameter', async () => {
      mockRegulationsApiList.mockResolvedValueOnce(mockRegulationListResponse)

      const { wrapper } = createWrapper()
      const { result } = renderHook(
        () => useRegulations({ page: 1, chromosome: 'chr1' }),
        { wrapper }
      )

      await waitFor(() => {
        expect(result.current.isSuccess).toBe(true)
      })

      expect(mockRegulationsApiList).toHaveBeenCalledWith({ page: 1, chromosome: 'chr1' }, expect.anything())
    })

    it('supports binding affinity range filters', async () => {
      mockRegulationsApiList.mockResolvedValueOnce(mockRegulationListResponse)

      const { wrapper } = createWrapper()
      const { result } = renderHook(
        () => useRegulations({ page: 1, min_ba: 100, max_ba: 200 }),
        { wrapper }
      )

      await waitFor(() => {
        expect(result.current.isSuccess).toBe(true)
      })

      expect(mockRegulationsApiList).toHaveBeenCalledWith({
        page: 1,
        min_ba: 100,
        max_ba: 200,
      }, expect.anything())
    })

    it('supports lncrna_gene_name search parameter', async () => {
      mockRegulationsApiList.mockResolvedValueOnce(mockRegulationListResponse)

      const { wrapper } = createWrapper()
      const { result } = renderHook(
        () => useRegulations({ page: 1, lncrna_gene_name: 'HOTAIR' }),
        { wrapper }
      )

      await waitFor(() => {
        expect(result.current.isSuccess).toBe(true)
      })

      expect(mockRegulationsApiList).toHaveBeenCalledWith({
        page: 1,
        lncrna_gene_name: 'HOTAIR',
      }, expect.anything())
    })

    it('supports target_gene_name search parameter', async () => {
      mockRegulationsApiList.mockResolvedValueOnce(mockRegulationListResponse)

      const { wrapper } = createWrapper()
      const { result } = renderHook(
        () => useRegulations({ page: 1, target_gene_name: 'TP53' }),
        { wrapper }
      )

      await waitFor(() => {
        expect(result.current.isSuccess).toBe(true)
      })

      expect(mockRegulationsApiList).toHaveBeenCalledWith({
        page: 1,
        target_gene_name: 'TP53',
      }, expect.anything())
    })

    it('supports multiple species filter with species_ids', async () => {
      mockRegulationsApiList.mockResolvedValueOnce(mockRegulationListResponse)

      const { wrapper } = createWrapper()
      const { result } = renderHook(
        () => useRegulations({ page: 1, species_ids: '1,2' }),
        { wrapper }
      )

      await waitFor(() => {
        expect(result.current.isSuccess).toBe(true)
      })

      expect(mockRegulationsApiList).toHaveBeenCalledWith({
        page: 1,
        species_ids: '1,2',
      }, expect.anything())
    })

    it('updates query key when params change', async () => {
      mockRegulationsApiList.mockResolvedValue(mockRegulationListResponse)

      const { wrapper } = createWrapper()
      const { result, rerender } = renderHook(
        ({ page }) => useRegulations({ page }),
        { wrapper, initialProps: { page: 1 } }
      )

      await waitFor(() => {
        expect(result.current.isSuccess).toBe(true)
      })

      expect(mockRegulationsApiList).toHaveBeenCalledWith({ page: 1 }, expect.anything())

      // Change page
      rerender({ page: 2 })

      await waitFor(() => {
        expect(mockRegulationsApiList).toHaveBeenCalledWith({ page: 2 }, expect.anything())
      })
    })
  })

  describe('usePrefetchRegulations hook', () => {
    it('prefetches regulation list data', async () => {
      mockRegulationsApiList.mockResolvedValueOnce(mockRegulationListResponse)

      const { wrapper } = createWrapper()
      const { result } = renderHook(() => usePrefetchRegulations(), { wrapper })

      // Call the prefetch function
      result.current({ page: 2, page_size: 20 })

      // Wait for the API to be called (prefetch is fire-and-forget)
      await waitFor(() => {
        expect(mockRegulationsApiList).toHaveBeenCalledWith({ page: 2, page_size: 20 }, expect.anything())
      })
    })

    it('prefetches with filter parameters', async () => {
      mockRegulationsApiList.mockResolvedValueOnce(mockRegulationListResponse)

      const { wrapper } = createWrapper()
      const { result } = renderHook(() => usePrefetchRegulations(), { wrapper })

      const params = { page: 1, species_id: 1, min_ba: 100 }
      result.current(params)

      // Wait for the API to be called with filter params
      await waitFor(() => {
        expect(mockRegulationsApiList).toHaveBeenCalledWith(params, expect.anything())
      })
    })
  })

  describe('useRegulationDetail hook', () => {
    it('returns regulation detail data successfully', async () => {
      mockRegulationsApiGetDetail.mockResolvedValueOnce(mockRegulationDetailResponse)

      const { wrapper } = createWrapper()
      const { result } = renderHook(() => useRegulationDetail(1), { wrapper })

      await waitFor(() => {
        expect(result.current.isSuccess).toBe(true)
      })

      expect(result.current.data).toEqual(mockRegulationDetailResponse.data)
      expect(mockRegulationsApiGetDetail).toHaveBeenCalledWith(1, expect.anything())
    })

    it('does not fetch when regulationId is null', async () => {
      const { wrapper } = createWrapper()
      const { result } = renderHook(() => useRegulationDetail(null), { wrapper })

      // Should not be loading or fetching
      expect(result.current.isLoading).toBe(false)
      expect(result.current.fetchStatus).toBe('idle')
      expect(mockRegulationsApiGetDetail).not.toHaveBeenCalled()
    })

    it('respects enabled option', async () => {
      mockRegulationsApiGetDetail.mockResolvedValueOnce(mockRegulationDetailResponse)

      const { wrapper } = createWrapper()
      const { result, rerender } = renderHook(
        ({ regulationId, enabled }) => useRegulationDetail(regulationId, { enabled }),
        { wrapper, initialProps: { regulationId: 1 as number | null, enabled: false } }
      )

      // Should not fetch when disabled
      expect(result.current.fetchStatus).toBe('idle')
      expect(mockRegulationsApiGetDetail).not.toHaveBeenCalled()

      // Enable the query
      rerender({ regulationId: 1, enabled: true })

      await waitFor(() => {
        expect(result.current.isSuccess).toBe(true)
      })

      expect(mockRegulationsApiGetDetail).toHaveBeenCalledWith(1, expect.anything())
    })

    it('handles errors properly', async () => {
      mockRegulationsApiGetDetail.mockRejectedValueOnce(new Error('Regulation not found'))

      const { wrapper } = createWrapper()
      const { result } = renderHook(() => useRegulationDetail(999), { wrapper })

      await waitFor(() => {
        expect(result.current.isError).toBe(true)
      })

      expect(result.current.error).toBeDefined()
    })

    it('returns null data when regulationId is null but hook is called', async () => {
      const { wrapper } = createWrapper()
      const { result } = renderHook(() => useRegulationDetail(null), { wrapper })

      // Data should be undefined (not fetched)
      expect(result.current.data).toBeUndefined()
    })
  })
})
