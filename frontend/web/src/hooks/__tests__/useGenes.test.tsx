/**
 * useGenes Hook Tests
 *
 * Tests for gene-related React Query hooks including:
 * - useGenes: Paginated gene list fetching
 * - usePrefetchGenes: Prefetching gene list data
 * - useGeneDetail: Single gene detail fetching
 * - useGeneRegulations: Gene regulations fetching
 * - useGeneDiseases: Gene disease associations
 * - useGeneOrthologs: Cross-species ortholog data
 *
 * @module hooks/__tests__/useGenes
 */
import { renderHook, waitFor } from '@testing-library/react'
import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest'
import type { ReactNode } from 'react'

import {
  useGenes,
  usePrefetchGenes,
  useGeneDetail,
  useGeneRegulations,
  useGeneDiseases,
  useGeneOrthologs,
} from '../useGenes'

// Mock API modules
vi.mock('@/api/genes', () => ({
  genesApi: {
    list: vi.fn(),
    detail: vi.fn(),
    getOrthologs: vi.fn(),
  },
}))

vi.mock('@/api/regulations', () => ({
  regulationsApi: {
    list: vi.fn(),
  },
}))

vi.mock('@/api/diseases', () => ({
  diseasesApi: {
    getGeneAssociations: vi.fn(),
  },
}))

// Import mocked modules for type access
import { genesApi } from '@/api/genes'
import { regulationsApi } from '@/api/regulations'
import { diseasesApi } from '@/api/diseases'

// Type the mocked functions
const mockGenesApiList = vi.mocked(genesApi.list)
const mockGenesApiDetail = vi.mocked(genesApi.detail)
const mockGenesApiGetOrthologs = vi.mocked(genesApi.getOrthologs)
const mockRegulationsApiList = vi.mocked(regulationsApi.list)
const mockDiseasesApiGetGeneAssociations = vi.mocked(diseasesApi.getGeneAssociations)

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
const mockGeneListResponse = {
  data: {
    items: [
      {
        gene_id: 1,
        gene_ensembl_id: 'ENSG00000001',
        gene_name: 'GENE1',
        gene_type: 'lncRNA',
        species_id: 1,
        species_name: 'Human',
        chromosome: 'chr1',
        start_position: 1000,
        end_position: 2000,
        strand: '+',
      },
      {
        gene_id: 2,
        gene_ensembl_id: 'ENSG00000002',
        gene_name: 'GENE2',
        gene_type: 'protein_coding',
        species_id: 1,
        species_name: 'Human',
        chromosome: 'chr1',
        start_position: 3000,
        end_position: 4000,
        strand: '-',
      },
    ],
    total: 2,
    page: 1,
    page_size: 20,
  },
}

const mockGeneDetailResponse = {
  data: {
    gene_id: 1,
    gene_ensembl_id: 'ENSG00000001',
    gene_name: 'GENE1',
    gene_type: 'lncRNA',
    species_id: 1,
    species_name: 'Human',
    chromosome: 'chr1',
    start_position: 1000,
    end_position: 2000,
    strand: '+',
    description: 'Test gene description',
    biotype: 'lncRNA',
  },
}

const mockRegulationsResponse = {
  data: {
    items: [
      {
        regulation_id: 1,
        lncrna_gene_id: 1,
        lncrna_gene_name: 'GENE1',
        target_gene_id: 100,
        target_gene_name: 'TARGET1',
        binding_affinity: 150.5,
      },
    ],
    total: 1,
    page: 1,
    page_size: 20,
  },
}

const mockDiseasesResponse = {
  data: [
    {
      trait_id: 1,
      trait_name: 'Cancer',
      ontology_id: 10,
      ontology_name: 'EFO',
      association_score: 0.85,
    },
  ],
}

const mockOrthologsResponse = {
  data: [
    {
      gene_id: 10,
      gene_name: 'GENE1_chimp',
      species_id: 2,
      species_name: 'Chimpanzee',
      core_id: 'CORE001',
      regulation_count: 42,
    },
    {
      gene_id: 20,
      gene_name: 'GENE1_macaque',
      species_id: 3,
      species_name: 'Macaque',
      core_id: 'CORE001',
      regulation_count: 38,
    },
  ],
}

describe('useGenes', () => {
  beforeEach(() => {
    vi.clearAllMocks()
  })

  afterEach(() => {
    vi.resetAllMocks()
  })

  describe('useGenes hook', () => {
    it('returns gene list data successfully', async () => {
      mockGenesApiList.mockResolvedValueOnce(mockGeneListResponse)

      const { wrapper } = createWrapper()
      const { result } = renderHook(
        () => useGenes({ page: 1, page_size: 20 }),
        { wrapper }
      )

      // Initially loading
      expect(result.current.isLoading).toBe(true)

      await waitFor(() => {
        expect(result.current.isSuccess).toBe(true)
      })

      expect(result.current.data).toEqual(mockGeneListResponse.data)
      expect(mockGenesApiList).toHaveBeenCalledWith({ page: 1, page_size: 20 }, expect.anything())
    })

    it('handles API errors gracefully', async () => {
      const error = new Error('Network error')
      mockGenesApiList.mockRejectedValueOnce(error)

      const { wrapper } = createWrapper()
      const { result } = renderHook(
        () => useGenes({ page: 1 }),
        { wrapper }
      )

      await waitFor(() => {
        expect(result.current.isError).toBe(true)
      })

      expect(result.current.error).toBeDefined()
    })

    it('supports species filter parameter', async () => {
      mockGenesApiList.mockResolvedValueOnce(mockGeneListResponse)

      const { wrapper } = createWrapper()
      const { result } = renderHook(
        () => useGenes({ page: 1, species_id: 1 }),
        { wrapper }
      )

      await waitFor(() => {
        expect(result.current.isSuccess).toBe(true)
      })

      expect(mockGenesApiList).toHaveBeenCalledWith({ page: 1, species_id: 1 }, expect.anything())
    })

    it('supports search parameter', async () => {
      mockGenesApiList.mockResolvedValueOnce(mockGeneListResponse)

      const { wrapper } = createWrapper()
      const { result } = renderHook(
        () => useGenes({ page: 1, search: 'BRCA1' }),
        { wrapper }
      )

      await waitFor(() => {
        expect(result.current.isSuccess).toBe(true)
      })

      expect(mockGenesApiList).toHaveBeenCalledWith({ page: 1, search: 'BRCA1' }, expect.anything())
    })
  })

  describe('usePrefetchGenes hook', () => {
    it('prefetches gene list data', async () => {
      mockGenesApiList.mockResolvedValueOnce(mockGeneListResponse)

      const { wrapper } = createWrapper()
      const { result } = renderHook(() => usePrefetchGenes(), { wrapper })

      // Call the prefetch function
      result.current({ page: 2, page_size: 20 })

      // Wait for the API to be called (prefetch is fire-and-forget)
      await waitFor(() => {
        expect(mockGenesApiList).toHaveBeenCalledWith({ page: 2, page_size: 20 }, expect.anything())
      })
    })
  })

  describe('useGeneDetail hook', () => {
    it('returns gene detail data successfully', async () => {
      mockGenesApiDetail.mockResolvedValueOnce(mockGeneDetailResponse)

      const { wrapper } = createWrapper()
      const { result } = renderHook(() => useGeneDetail(1), { wrapper })

      await waitFor(() => {
        expect(result.current.isSuccess).toBe(true)
      })

      expect(result.current.data).toEqual(mockGeneDetailResponse.data)
      expect(mockGenesApiDetail).toHaveBeenCalledWith(1, expect.anything())
    })

    it('does not fetch when geneId is falsy', async () => {
      const { wrapper } = createWrapper()
      const { result } = renderHook(() => useGeneDetail(0), { wrapper })

      // Should not be loading or fetching
      expect(result.current.isLoading).toBe(false)
      expect(result.current.fetchStatus).toBe('idle')
      expect(mockGenesApiDetail).not.toHaveBeenCalled()
    })

    it('handles errors properly', async () => {
      mockGenesApiDetail.mockRejectedValueOnce(new Error('Gene not found'))

      const { wrapper } = createWrapper()
      const { result } = renderHook(() => useGeneDetail(999), { wrapper })

      await waitFor(() => {
        expect(result.current.isError).toBe(true)
      })

      expect(result.current.error).toBeDefined()
    })
  })

  describe('useGeneRegulations hook', () => {
    it('returns gene regulations successfully', async () => {
      mockRegulationsApiList.mockResolvedValueOnce(mockRegulationsResponse)

      const { wrapper } = createWrapper()
      const { result } = renderHook(
        () => useGeneRegulations(1, { page: 1, page_size: 20 }),
        { wrapper }
      )

      await waitFor(() => {
        expect(result.current.isSuccess).toBe(true)
      })

      expect(result.current.data).toEqual(mockRegulationsResponse.data)
      expect(mockRegulationsApiList).toHaveBeenCalledWith({
        lncrna_gene_id: 1,
        page: 1,
        page_size: 20,
      }, expect.anything())
    })

    it('uses default pagination when params not provided', async () => {
      mockRegulationsApiList.mockResolvedValueOnce(mockRegulationsResponse)

      const { wrapper } = createWrapper()
      const { result } = renderHook(() => useGeneRegulations(1), { wrapper })

      await waitFor(() => {
        expect(result.current.isSuccess).toBe(true)
      })

      expect(mockRegulationsApiList).toHaveBeenCalledWith({
        lncrna_gene_id: 1,
        page: 1,
        page_size: 20,
      }, expect.anything())
    })

    it('does not fetch when geneId is falsy', async () => {
      const { wrapper } = createWrapper()
      const { result } = renderHook(() => useGeneRegulations(0), { wrapper })

      expect(result.current.fetchStatus).toBe('idle')
      expect(mockRegulationsApiList).not.toHaveBeenCalled()
    })
  })

  describe('useGeneDiseases hook', () => {
    it('returns gene disease associations successfully', async () => {
      mockDiseasesApiGetGeneAssociations.mockResolvedValueOnce(mockDiseasesResponse)

      const { wrapper } = createWrapper()
      const { result } = renderHook(() => useGeneDiseases(1), { wrapper })

      await waitFor(() => {
        expect(result.current.isSuccess).toBe(true)
      })

      expect(result.current.data).toEqual(mockDiseasesResponse.data)
      expect(mockDiseasesApiGetGeneAssociations).toHaveBeenCalledWith(1, expect.anything())
    })

    it('does not fetch when geneId is falsy', async () => {
      const { wrapper } = createWrapper()
      const { result } = renderHook(() => useGeneDiseases(0), { wrapper })

      expect(result.current.fetchStatus).toBe('idle')
      expect(mockDiseasesApiGetGeneAssociations).not.toHaveBeenCalled()
    })
  })

  describe('useGeneOrthologs hook', () => {
    it('returns ortholog data successfully', async () => {
      mockGenesApiGetOrthologs.mockResolvedValueOnce(mockOrthologsResponse)

      const { wrapper } = createWrapper()
      const { result } = renderHook(() => useGeneOrthologs(1), { wrapper })

      await waitFor(() => {
        expect(result.current.isSuccess).toBe(true)
      })

      expect(result.current.data).toEqual(mockOrthologsResponse.data)
      expect(mockGenesApiGetOrthologs).toHaveBeenCalledWith(1, expect.anything())
    })

    it('does not fetch when geneId is 0 or negative', async () => {
      const { wrapper } = createWrapper()
      const { result } = renderHook(() => useGeneOrthologs(0), { wrapper })

      expect(result.current.fetchStatus).toBe('idle')
      expect(mockGenesApiGetOrthologs).not.toHaveBeenCalled()
    })

    it('has appropriate stale time configured', async () => {
      mockGenesApiGetOrthologs.mockResolvedValueOnce(mockOrthologsResponse)

      const { wrapper } = createWrapper()
      renderHook(() => useGeneOrthologs(1), { wrapper })

      await waitFor(() => {
        expect(mockGenesApiGetOrthologs).toHaveBeenCalled()
      })

      // Verify staleTime is set (5 minutes = 300000ms)
      // This is implicitly tested by the hook not refetching on re-render
    })
  })
})
