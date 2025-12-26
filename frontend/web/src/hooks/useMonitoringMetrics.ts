import { useQuery } from '@tanstack/react-query'
import { fetchMonitoringMetrics } from '@/api/admin'
import { queryKeys } from './queryKeys'

/**
 * Hook to fetch and auto-refresh monitoring metrics
 *
 * 功能:
 * - 正常情况下每 5 秒自动刷新
 * - 遇到错误时停止轮询，避免 403/网络错误导致的 toast 刷屏
 * - 使用 skipGlobalErrorHandler 跳过全局错误提示，由页面内 ErrorState 展示
 */
export const useMonitoringMetrics = () => {
  return useQuery({
    queryKey: queryKeys.admin.metrics(),
    queryFn: ({ signal }) => fetchMonitoringMetrics(signal),
    // 仅在无错误时每 5 秒刷新，有错误时停止轮询
    refetchInterval: (query) => (query.state.error ? false : 5000),
    staleTime: 3000, // Consider data stale after 3 seconds
    retry: 1, // 只重试一次，避免 403 时多次重试
    meta: {
      // 跳过全局错误 toast，由页面内 ErrorState 展示错误信息
      skipGlobalErrorHandler: true,
    },
  })
}
