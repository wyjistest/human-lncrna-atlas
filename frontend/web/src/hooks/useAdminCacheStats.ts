import { useQuery } from '@tanstack/react-query'
import { fetchCacheStats } from '@/api/admin'
import { queryKeys } from './queryKeys'

/**
 * Hook to fetch admin cache statistics.
 *
 * 功能:
 * - 默认每 10 秒刷新一次（无错误时）
 * - 遇到错误时停止轮询，避免 403/网络错误导致的 toast 刷屏
 * - 使用 skipGlobalErrorHandler 跳过全局错误提示，由页面内 ErrorState 展示
 */
export const useAdminCacheStats = () => {
  return useQuery({
    queryKey: queryKeys.admin.cacheStats(),
    queryFn: ({ signal }) => fetchCacheStats(signal),
    refetchInterval: (query) => (query.state.error ? false : 10000),
    staleTime: 5000,
    retry: 1,
    meta: {
      skipGlobalErrorHandler: true,
    },
  })
}

