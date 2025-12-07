import { useQuery } from '@tanstack/react-query'
import { statsApi } from '@/api/stats'

export const useStats = () => {
  return useQuery({
    queryKey: ['stats', 'overview'],
    queryFn: async () => {
      const { data } = await statsApi.overview()
      return data
    },
  })
}
