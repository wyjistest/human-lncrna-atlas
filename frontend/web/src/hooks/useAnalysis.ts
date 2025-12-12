/**
 * Analysis Data Hooks
 *
 * React Query hooks for analysis data fetching
 */

import { useQuery } from '@tanstack/react-query'
import { analysisApi } from '@/api/analysis'

/**
 * Hook for analysis summary statistics
 */
export const useAnalysisSummary = () => {
  return useQuery({
    queryKey: ['analysis', 'summary'],
    queryFn: async () => {
      const { data } = await analysisApi.getSummary()
      return data
    },
    staleTime: 5 * 60 * 1000, // 5 minutes
  })
}

/**
 * Hook for high affinity data
 */
export const useHighAffinityData = (params?: {
  min_ba?: number
  species_id?: number
  limit?: number
  offset?: number
}) => {
  return useQuery({
    queryKey: ['analysis', 'high-affinity', params],
    queryFn: async () => {
      const { data } = await analysisApi.getHighAffinity(params)
      return data
    },
    staleTime: 5 * 60 * 1000,
  })
}

/**
 * Hook for conservation data
 */
export const useConservationData = (params?: {
  min_species_count?: number
  limit?: number
  offset?: number
}) => {
  return useQuery({
    queryKey: ['analysis', 'conservation', params],
    queryFn: async () => {
      const { data } = await analysisApi.getConservation(params)
      return data
    },
    staleTime: 5 * 60 * 1000,
  })
}

/**
 * Hook for epigenetic (ChIP-seq overlap) data
 */
export const useEpigeneticData = (params?: {
  mark_names?: string[]
  cell_types?: string[]
  min_ba?: number
  limit?: number
  offset?: number
}) => {
  return useQuery({
    queryKey: ['analysis', 'epigenetic', params],
    queryFn: async () => {
      const { data } = await analysisApi.getChipseqOverlaps(params)
      return data
    },
    staleTime: 5 * 60 * 1000,
  })
}

/**
 * Hook for disease network data
 */
export const useDiseaseData = (params?: {
  trait_name?: string
  min_ba?: number
  limit?: number
  offset?: number
}) => {
  return useQuery({
    queryKey: ['analysis', 'disease', params],
    queryFn: async () => {
      const { data } = await analysisApi.getDiseaseNetwork(params)
      return data
    },
    staleTime: 5 * 60 * 1000,
  })
}
