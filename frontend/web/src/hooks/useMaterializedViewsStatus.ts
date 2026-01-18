import { useQuery } from '@tanstack/react-query'
import { fetchMaterializedViewsStatus } from '@/api/admin'
import { queryKeys } from './queryKeys'

/**
 * Hook to fetch materialized views status.
 *
 * 说明：
 * - 默认每 30 秒刷新一次（无错误时）
 * - 遇到错误时停止轮询，避免 403/网络错误导致的 toast 刷屏
 * - 使用 skipGlobalErrorHandler 跳过全局错误提示，由页面内 ErrorState 展示
 */
export const useMaterializedViewsStatus = () => {
  return useQuery({
    queryKey: queryKeys.admin.materializedViewsStatus(),
    queryFn: ({ signal }) => fetchMaterializedViewsStatus(signal),
    refetchInterval: (query) => (query.state.error ? false : 30000),
    staleTime: 10000,
    retry: 1,
    meta: {
      skipGlobalErrorHandler: true,
    },
  })
}

