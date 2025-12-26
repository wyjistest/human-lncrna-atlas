import { useQuery } from '@tanstack/react-query'
import { statsApi } from '@/api/stats'
import { queryKeys } from './queryKeys'

export const useStats = () => {
  return useQuery({
    queryKey: queryKeys.stats.overview(),
    queryFn: async ({ signal }) => {
      const { data } = await statsApi.overview(signal)
      return data
    },
  })
}
