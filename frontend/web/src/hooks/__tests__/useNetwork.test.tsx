/**
 * useNetwork Hook Tests
 *
 * Tests for network visualization React Query hook:
 * - useNetwork: Gene-centric network data fetching for Cytoscape visualization
 *
 * @module hooks/__tests__/useNetwork
 */
import { renderHook, waitFor } from '@testing-library/react'
import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest'
import type { ReactNode } from 'react'

import { useNetwork } from '../useNetwork'

// Mock API module
vi.mock('@/api/network', () => ({
  networkApi: {
    getGeneNetwork: vi.fn(),
  },
}))

// Import mocked module for type access
import { networkApi } from '@/api/network'

// Type the mocked function
const mockGetGeneNetwork = vi.mocked(networkApi.getGeneNetwork)

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
const mockNetworkResponse = {
  data: {
    nodes: [
      {
        id: 1,
        gene_name: 'LNCRNA1',
        gene_type: 'lncRNA',
        species_id: 1,
        species_name: 'Human',
        degree: 5,
        is_center: true,
      },
      {
        id: 2,
        gene_name: 'TARGET1',
        gene_type: 'protein_coding',
        species_id: 1,
        species_name: 'Human',
        degree: 3,
        is_center: false,
      },
      {
        id: 3,
        gene_name: 'TARGET2',
        gene_type: 'protein_coding',
        species_id: 1,
        species_name: 'Human',
        degree: 2,
        is_center: false,
      },
    ],
    edges: [
      {
        source: 1,
        target: 2,
        binding_affinity: 185.5,
        distance: 50000,
        regulation_id: 101,
      },
      {
        source: 1,
        target: 3,
        binding_affinity: 120.3,
        distance: 75000,
        regulation_id: 102,
      },
    ],
    stats: {
      total_nodes: 3,
      total_edges: 2,
      lncrna_count: 1,
      target_count: 2,
      avg_binding_affinity: 152.9,
    },
  },
}

const mockNetworkResponseWithFilters = {
  data: {
    nodes: [
      {
        id: 1,
        gene_name: 'LNCRNA1',
        gene_type: 'lncRNA',
        species_id: 1,
        species_name: 'Human',
        degree: 1,
        is_center: true,
      },
      {
        id: 2,
        gene_name: 'TARGET1',
        gene_type: 'protein_coding',
        species_id: 1,
        species_name: 'Human',
        degree: 1,
        is_center: false,
      },
    ],
    edges: [
      {
        source: 1,
        target: 2,
        binding_affinity: 185.5,
        distance: 50000,
        regulation_id: 101,
      },
    ],
    stats: {
      total_nodes: 2,
      total_edges: 1,
      lncrna_count: 1,
      target_count: 1,
      avg_binding_affinity: 185.5,
    },
  },
}

describe('useNetwork', () => {
  beforeEach(() => {
    vi.clearAllMocks()
  })

  afterEach(() => {
    vi.resetAllMocks()
  })

  describe('useNetwork hook', () => {
    it('returns network data successfully', async () => {
      mockGetGeneNetwork.mockResolvedValueOnce(mockNetworkResponse)

      const { wrapper } = createWrapper()
      const { result } = renderHook(() => useNetwork(1), { wrapper })

      // Initially loading
      expect(result.current.isLoading).toBe(true)

      await waitFor(() => {
        expect(result.current.isSuccess).toBe(true)
      })

      expect(result.current.data).toEqual(mockNetworkResponse.data)
      expect(mockGetGeneNetwork).toHaveBeenCalledWith(1, undefined)
    })

    it('does not fetch when geneId is null', async () => {
      const { wrapper } = createWrapper()
      const { result } = renderHook(() => useNetwork(null), { wrapper })

      // Should not be loading or fetching
      expect(result.current.isLoading).toBe(false)
      expect(result.current.fetchStatus).toBe('idle')
      expect(mockGetGeneNetwork).not.toHaveBeenCalled()
    })

    it('handles API errors gracefully', async () => {
      const error = new Error('Network error')
      mockGetGeneNetwork.mockRejectedValueOnce(error)

      const { wrapper } = createWrapper()
      const { result } = renderHook(() => useNetwork(1), { wrapper })

      await waitFor(() => {
        expect(result.current.isError).toBe(true)
      })

      expect(result.current.error).toBeDefined()
    })

    it('supports species_id filter parameter', async () => {
      mockGetGeneNetwork.mockResolvedValueOnce(mockNetworkResponseWithFilters)

      const { wrapper } = createWrapper()
      const { result } = renderHook(
        () => useNetwork(1, { species_id: 1 }),
        { wrapper }
      )

      await waitFor(() => {
        expect(result.current.isSuccess).toBe(true)
      })

      expect(mockGetGeneNetwork).toHaveBeenCalledWith(1, { species_id: 1 })
    })

    it('supports min_ba filter parameter', async () => {
      mockGetGeneNetwork.mockResolvedValueOnce(mockNetworkResponseWithFilters)

      const { wrapper } = createWrapper()
      const { result } = renderHook(
        () => useNetwork(1, { min_ba: 150 }),
        { wrapper }
      )

      await waitFor(() => {
        expect(result.current.isSuccess).toBe(true)
      })

      expect(mockGetGeneNetwork).toHaveBeenCalledWith(1, { min_ba: 150 })
    })

    it('supports max_distance filter parameter', async () => {
      mockGetGeneNetwork.mockResolvedValueOnce(mockNetworkResponseWithFilters)

      const { wrapper } = createWrapper()
      const { result } = renderHook(
        () => useNetwork(1, { max_distance: 100000 }),
        { wrapper }
      )

      await waitFor(() => {
        expect(result.current.isSuccess).toBe(true)
      })

      expect(mockGetGeneNetwork).toHaveBeenCalledWith(1, { max_distance: 100000 })
    })

    it('supports depth parameter', async () => {
      mockGetGeneNetwork.mockResolvedValueOnce(mockNetworkResponse)

      const { wrapper } = createWrapper()
      const { result } = renderHook(
        () => useNetwork(1, { depth: 2 }),
        { wrapper }
      )

      await waitFor(() => {
        expect(result.current.isSuccess).toBe(true)
      })

      expect(mockGetGeneNetwork).toHaveBeenCalledWith(1, { depth: 2 })
    })

    it('supports multiple filter parameters combined', async () => {
      mockGetGeneNetwork.mockResolvedValueOnce(mockNetworkResponseWithFilters)

      const params = {
        species_id: 1,
        min_ba: 100,
        max_distance: 50000,
        depth: 1,
      }

      const { wrapper } = createWrapper()
      const { result } = renderHook(
        () => useNetwork(1, params),
        { wrapper }
      )

      await waitFor(() => {
        expect(result.current.isSuccess).toBe(true)
      })

      expect(mockGetGeneNetwork).toHaveBeenCalledWith(1, params)
    })

    it('returns null when geneId is null and query runs', async () => {
      const { wrapper } = createWrapper()
      const { result } = renderHook(() => useNetwork(null), { wrapper })

      // Data should be undefined because query is disabled
      expect(result.current.data).toBeUndefined()
    })

    it('updates query key when geneId changes', async () => {
      mockGetGeneNetwork.mockResolvedValue(mockNetworkResponse)

      const { wrapper } = createWrapper()
      const { result, rerender } = renderHook(
        ({ geneId }) => useNetwork(geneId),
        { wrapper, initialProps: { geneId: 1 as number | null } }
      )

      await waitFor(() => {
        expect(result.current.isSuccess).toBe(true)
      })

      expect(mockGetGeneNetwork).toHaveBeenCalledWith(1, undefined)

      // Change geneId
      rerender({ geneId: 2 })

      await waitFor(() => {
        expect(mockGetGeneNetwork).toHaveBeenCalledWith(2, undefined)
      })
    })

    it('updates query key when params change', async () => {
      mockGetGeneNetwork.mockResolvedValue(mockNetworkResponse)

      const { wrapper } = createWrapper()
      const { result, rerender } = renderHook(
        ({ geneId, params }) => useNetwork(geneId, params),
        { wrapper, initialProps: { geneId: 1 as number | null, params: { min_ba: 100 } } }
      )

      await waitFor(() => {
        expect(result.current.isSuccess).toBe(true)
      })

      expect(mockGetGeneNetwork).toHaveBeenCalledWith(1, { min_ba: 100 })

      // Change params
      rerender({ geneId: 1, params: { min_ba: 200 } })

      await waitFor(() => {
        expect(mockGetGeneNetwork).toHaveBeenCalledWith(1, { min_ba: 200 })
      })
    })

    it('stops fetching when geneId becomes null', async () => {
      mockGetGeneNetwork.mockResolvedValue(mockNetworkResponse)

      const { wrapper } = createWrapper()
      const { result, rerender } = renderHook(
        ({ geneId }) => useNetwork(geneId),
        { wrapper, initialProps: { geneId: 1 as number | null } }
      )

      await waitFor(() => {
        expect(result.current.isSuccess).toBe(true)
      })

      // Clear the mock call history
      vi.clearAllMocks()

      // Set geneId to null
      rerender({ geneId: null })

      // Should not make new API calls
      expect(mockGetGeneNetwork).not.toHaveBeenCalled()
    })
  })

  describe('network data structure', () => {
    it('returns proper node structure', async () => {
      mockGetGeneNetwork.mockResolvedValueOnce(mockNetworkResponse)

      const { wrapper } = createWrapper()
      const { result } = renderHook(() => useNetwork(1), { wrapper })

      await waitFor(() => {
        expect(result.current.isSuccess).toBe(true)
      })

      const nodes = result.current.data?.nodes
      expect(nodes).toHaveLength(3)

      // Verify center node
      const centerNode = nodes?.find((n) => n.is_center)
      expect(centerNode).toBeDefined()
      expect(centerNode?.gene_type).toBe('lncRNA')

      // Verify target nodes
      const targetNodes = nodes?.filter((n) => !n.is_center)
      expect(targetNodes).toHaveLength(2)
      targetNodes?.forEach((node) => {
        expect(node.gene_type).toBe('protein_coding')
      })
    })

    it('returns proper edge structure', async () => {
      mockGetGeneNetwork.mockResolvedValueOnce(mockNetworkResponse)

      const { wrapper } = createWrapper()
      const { result } = renderHook(() => useNetwork(1), { wrapper })

      await waitFor(() => {
        expect(result.current.isSuccess).toBe(true)
      })

      const edges = result.current.data?.edges
      expect(edges).toHaveLength(2)

      edges?.forEach((edge) => {
        expect(edge.source).toBeDefined()
        expect(edge.target).toBeDefined()
        expect(edge.binding_affinity).toBeGreaterThan(0)
        expect(edge.regulation_id).toBeDefined()
      })
    })

    it('returns proper stats structure', async () => {
      mockGetGeneNetwork.mockResolvedValueOnce(mockNetworkResponse)

      const { wrapper } = createWrapper()
      const { result } = renderHook(() => useNetwork(1), { wrapper })

      await waitFor(() => {
        expect(result.current.isSuccess).toBe(true)
      })

      const stats = result.current.data?.stats
      expect(stats).toBeDefined()
      expect(stats?.total_nodes).toBe(3)
      expect(stats?.total_edges).toBe(2)
      expect(stats?.lncrna_count).toBe(1)
      expect(stats?.target_count).toBe(2)
      expect(stats?.avg_binding_affinity).toBeCloseTo(152.9, 1)
    })
  })
})
