import { useQuery } from '@tanstack/react-query'
import { fetchMonitoringMetrics } from '@/api/admin'
import { queryKeys } from './queryKeys'

/**
 * Hook to fetch and auto-refresh monitoring metrics
 * Automatically refreshes every 5 seconds
 */
export const useMonitoringMetrics = () => {
  return useQuery({
    queryKey: queryKeys.admin.metrics(),
    queryFn: fetchMonitoringMetrics,
    refetchInterval: 5000, // Auto-refresh every 5 seconds
    staleTime: 3000, // Consider data stale after 3 seconds
  })
}
