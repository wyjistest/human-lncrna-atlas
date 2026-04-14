import { useQuery } from '@tanstack/react-query'

import { apiClient } from '@/api/client'

export type RootStatus = {
  version?: string
  db_mode?: string
  db_name?: string
}

export const useRootStatus = () => {
  return useQuery({
    queryKey: ['root-status'],
    queryFn: async ({ signal }) => {
      const { data } = await apiClient.get<RootStatus>('/', { signal })
      return data
    },
    staleTime: 60 * 1000,
  })
}
