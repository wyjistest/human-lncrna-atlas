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
  /** Number of response time samples collected for percentiles (windowed); <10 means percentiles may be null */
  samples: number
  /** Endpoint response time percentiles (ms); null/undefined when samples are insufficient */
  percentiles?: PercentileMetrics | null
  /** Average DB time per request (ms); best-effort */
  db_avg_ms?: number | null
  /** Average DB queries per request; best-effort */
  db_query_avg?: number | null
  /** Number of per-request DB time samples collected for db_percentiles (windowed); <10 means db_percentiles may be null */
  db_samples?: number
  /** Per-request DB time percentiles (ms); null/undefined when samples are insufficient */
  db_percentiles?: PercentileMetrics | null
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
 * Cache statistics summary (hit rate, requests)
 */
export interface CacheStatsSummary {
  /** Cache backend type e.g., "redis" | "memory" */
  backend: string
  /** Whether cache is enabled */
  enabled: boolean
  /** Total cache hits */
  hits: number
  /** Total cache misses */
  misses: number
  /** Total cache requests */
  total_requests: number
  /** Cache hit rate percentage (0-100) */
  hit_rate_pct: number
}

export interface CacheNamespaceBreakdownItem {
  /** Cache namespace name */
  namespace: string
  /** Total requests for this namespace */
  requests: number
  /** Cache hits */
  hits: number
  /** Cache misses */
  misses: number
  /** Cache hit rate percentage (0-100) */
  hit_rate_pct: number
  /** Number of backend compute operations */
  compute_count: number
  /** Average backend compute time in ms */
  compute_avg_ms: number
  /** Max backend compute time in ms */
  compute_max_ms: number
}

export interface CacheKeyBreakdownItem {
  /** Cache key (may include hash) */
  key: string
  /** Best-effort parsed namespace */
  namespace?: string | null
  /** Total requests for this key */
  requests: number
  /** Cache hits */
  hits: number
  /** Cache misses */
  misses: number
  /** Cache hit rate percentage (0-100) */
  hit_rate_pct: number
  /** Number of backend compute operations */
  compute_count: number
  /** Average backend compute time in ms */
  compute_avg_ms: number
  /** Max backend compute time in ms */
  compute_max_ms: number
}

export interface CacheRouteBreakdownItem {
  /** Route template (best-effort) */
  route: string
  /** Number of backend compute operations */
  compute_count: number
  /** Average backend compute time in ms */
  compute_avg_ms: number
  /** Max backend compute time in ms */
  compute_max_ms: number
}

export interface CacheNamespacesBreakdown {
  /** Number of tracked namespaces */
  tracked: number
  /** Top N limit */
  limit: number
  /** Top namespaces */
  top: CacheNamespaceBreakdownItem[]
}

export interface CacheKeysBreakdown {
  /** Number of tracked keys */
  tracked: number
  /** Top N limit */
  limit: number
  /** Top keys */
  top: CacheKeyBreakdownItem[]
}

export interface CacheRoutesBreakdown {
  /** Number of tracked routes */
  tracked: number
  /** Top N limit */
  limit: number
  /** Top routes */
  top: CacheRouteBreakdownItem[]
}

export interface CacheBreakdown {
  /** Breakdown by cache namespace */
  namespaces: CacheNamespacesBreakdown
  /** Breakdown by cache key */
  keys: CacheKeysBreakdown
  /** Breakdown by route (cache-miss compute attribution; best-effort) */
  routes?: CacheRoutesBreakdown
}

export interface CacheGetLatencyPercentiles {
  /** Hit samples collected (rolling window) */
  hits_samples: number
  /** Miss samples collected (rolling window) */
  misses_samples: number
  /** Max samples retained per category */
  max_samples: number
  /** Hit latency percentiles (ms); null/undefined when samples are insufficient */
  hits?: PercentileMetrics | null
  /** Miss latency percentiles (ms); null/undefined when samples are insufficient */
  misses?: PercentileMetrics | null
}

/**
 * Slow query summary item (aggregated by SQL fingerprint)
 */
export interface SlowQuerySummary {
  fingerprint: string
  statement: string
  count: number
  total_time_ms: number
  avg_ms: number
  max_ms: number
  last_seen: string
  route?: string | null
}

/**
 * Database performance metrics (best-effort, in-memory windowed stats)
 */
export interface DatabaseMetrics {
  total_queries: number
  total_time_ms: number
  query_samples: number
  avg_ms: number
  percentiles?: PercentileMetrics | null

  request_samples: number
  request_total_ms: number
  request_avg_ms: number
  request_percentiles?: PercentileMetrics | null

  slow_query_threshold_ms: number
  slow_queries: SlowQuerySummary[]
}

export interface CacheStatsDetails extends CacheStatsSummary {
  /** Human-readable hit rate e.g., "70.0%" */
  hit_rate: string
  /** Server-side allowlist of cache namespaces (for admin UI dropdowns) */
  allowed_namespaces?: string[]
  /** Namespace-level breakdown */
  namespaces: CacheNamespacesBreakdown
  /** Key-level breakdown */
  keys: CacheKeysBreakdown
  /** Redis backend details (when connected) */
  redis?: {
    host: string
    connected: boolean
  }
  /** In-memory backend details (when redis is unavailable) */
  memory?: {
    size: number
    max_size: number
    evictions: number
  }
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
  /** Cache stats summary (hit rate, requests) */
  cache_stats?: CacheStatsSummary
  /** Cache breakdown (namespaces / hot keys) */
  cache_breakdown?: CacheBreakdown
  /** Cache get() latency percentiles (hits/misses) */
  cache_get_latency?: CacheGetLatencyPercentiles | null

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
  /** Database performance metrics */
  database?: DatabaseMetrics | null
}
