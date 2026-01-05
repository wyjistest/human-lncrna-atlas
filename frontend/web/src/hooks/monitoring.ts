/**
 * 历史遗留：Monitoring 类型曾放在 hooks 目录。
 *
 * 现在统一从 `@/types/monitoring` 导出，避免重复定义与长期漂移。
 */
export type {
  Alert,
  EndpointStats,
  ErrorTrend,
  HealthStatus,
  MonitoringMetrics,
  PercentileMetrics,
  ProcessInfo,
  ResponseTimeDistribution,
  ServiceStatus,
  SystemDisk,
  SystemMemory,
  SystemMetrics,
} from '@/types/monitoring'
