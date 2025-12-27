/**
 * Analysis Data Hooks
 *
 * React Query hooks for analysis data fetching
 */

import { useQuery } from '@tanstack/react-query'
import { analysisApi } from '@/api/analysis'
import { queryKeys } from './queryKeys'

/**
 * Hook for analysis summary statistics
 */
export const useAnalysisSummary = () => {
  return useQuery({
    queryKey: queryKeys.analysis.summary(),
    queryFn: async ({ signal }) => {
      const { data } = await analysisApi.getSummary(signal)
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
}) => {
  return useQuery({
    queryKey: queryKeys.analysis.highAffinity(params),
    queryFn: async ({ signal }) => {
      const { data } = await analysisApi.getHighAffinity(params, signal)
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
}) => {
  return useQuery({
    queryKey: queryKeys.analysis.conservation(params),
    queryFn: async ({ signal }) => {
      const { data } = await analysisApi.getConservation(params, signal)
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
  min_ba?: number
  limit?: number
}) => {
  return useQuery({
    queryKey: queryKeys.analysis.epigenetic(params),
    queryFn: async ({ signal }) => {
      const { data } = await analysisApi.getChipseqOverlaps(params, signal)
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
  limit?: number
}) => {
  return useQuery({
    queryKey: queryKeys.analysis.disease(params),
    queryFn: async ({ signal }) => {
      const { data } = await analysisApi.getDiseaseNetwork(params, signal)
      return data
    },
    staleTime: 5 * 60 * 1000,
  })
}
