/**
 * Monitoring API Types
 * Used by admin monitoring endpoints
 */

/**
 * System health status
 */
export type HealthStatus = 'healthy' | 'degraded' | 'down'

/**
 * Service status for database and cache
 */
export type ServiceStatus = 'ok' | 'error' | 'not_configured'

/**
 * Response time distribution data (Phase 2)
 */
export interface ResponseTimeDistribution {
  /** Bucket labels e.g., ["0-50ms", "50-100ms", ...] */
  buckets: string[]
  /** Request counts per bucket */
  counts: number[]
}

/**
 * Error rate trend data over time (Phase 2)
 */
export interface ErrorTrend {
  /** Timestamps e.g., ["12:00", "12:01", ...] */
  timestamps: string[]
  /** Error rates (0-1) at each timestamp */
  error_rates: number[]
}

/**
 * Endpoint statistics (Phase 2)
 */
export interface EndpointStats {
  /** API endpoint path */
  path: string
  /** Total request count */
  requests: number
  /** Average response time in milliseconds */
  avg_ms: number
  /** Total error count */
  errors: number
  /** Error rate (0-1) */
  error_rate: number
}

/**
 * System memory metrics (Phase 3)
 */
export interface SystemMemory {
  /** Used memory in MB */
  used_mb: number
  /** Total memory in MB */
  total_mb: number
  /** Memory usage percentage (0-100) */
  percent: number
}

/**
 * System disk metrics (Phase 3)
 */
export interface SystemDisk {
  /** Used disk space in GB */
  used_gb: number
  /** Total disk space in GB */
  total_gb: number
  /** Disk usage percentage (0-100) */
  percent: number
}

/**
 * Process info metrics (Phase 3)
 */
export interface ProcessInfo {
  /** Process CPU usage percentage */
  cpu_percent: number
  /** Process memory usage in MB */
  memory_mb: number
}

/**
 * System metrics (Phase 3)
 */
export interface SystemMetrics {
  /** CPU usage percentage (0-100) */
  cpu_percent: number
  /** Memory metrics */
  memory: SystemMemory
  /** Disk metrics */
  disk: SystemDisk
  /** Process-specific metrics */
  process: ProcessInfo
}

/**
 * Alert notification (Phase 3)
 */
export interface Alert {
  /** Alert severity level */
  type: 'warning' | 'critical'
  /** Metric name that triggered the alert */
  metric: string
  /** Current metric value */
  value: number
  /** Threshold that was exceeded */
  threshold: number
  /** Human-readable alert message */
  message: string
}

/**
 * Response time percentiles (Phase 3)
 */
export interface PercentileMetrics {
  /** 50th percentile response time in ms */
  p50_ms: number
  /** 95th percentile response time in ms */
  p95_ms: number
  /** 99th percentile response time in ms */
  p99_ms: number
}

/**
 * Monitoring metrics returned by GET /api/v1/admin/metrics
 */
export interface MonitoringMetrics {
  // Phase 1 fields
  request: {
    /** Total number of requests */
    total: number
    /** Requests in the last minute */
    last_minute: number
  }
  errors: {
    /** Total number of errors */
    total: number
    /** Error rate (0-1) */
    rate: number
  }
  response_time: {
    /** Average response time in milliseconds */
    avg_ms: number
  }
  health: {
    /** Overall system health status */
    status: HealthStatus
    /** Database connection status */
    database: 'ok' | 'error'
    /** Cache status */
    cache: ServiceStatus
    /** System uptime in seconds */
    uptime_seconds: number
  }

  // Phase 2 fields
  /** Response time distribution histogram data */
  response_time_distribution?: ResponseTimeDistribution
  /** Error rate trend over last 10 minutes */
  error_trend?: ErrorTrend
  /** Per-endpoint statistics */
  endpoints?: EndpointStats[]

  // Phase 3 fields
  /** System resource metrics */
  system?: SystemMetrics
  /** Active alerts */
  alerts?: Alert[]
  /** Response time percentiles */
  percentiles?: PercentileMetrics | null
}
