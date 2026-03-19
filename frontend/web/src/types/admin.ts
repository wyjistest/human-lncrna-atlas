/**
 * Admin API Types
 * Used by admin-only operational endpoints
 */

export interface MaterializedViewStatusItem {
  name: string
  exists: boolean
  populated: boolean | null
  rows_estimate: number | null
  total_size: string | null
  total_size_bytes: number | null
  heap_size: string | null
  heap_size_bytes: number | null
  index_size: string | null
  index_size_bytes: number | null
  last_analyze_at: string | null
  last_autoanalyze_at: string | null
  last_stats_at: string | null
  last_stats_source: 'analyze' | 'autoanalyze' | 'none'
  stats_age_seconds: number | null
}

export interface MaterializedViewsStatusResponse {
  status: string
  supported: boolean
  database_backend: string
  checked_at: string
  refresh_lock_available: boolean | null
  views: MaterializedViewStatusItem[]
}

export interface MaterializedViewsRefreshRequest {
  views?: string[] | null
  concurrently: boolean
  analyze: boolean
  timeout_seconds?: number | null
}

export interface MaterializedViewRefreshResultItem {
  name: string
  ok?: boolean
  skipped?: boolean
  reason?: string
  concurrently?: boolean
  analyze?: boolean
  note?: string | null
  error?: string
  duration_seconds?: number
}

export interface MaterializedViewsRefreshResponse {
  status: string
  concurrently_requested: boolean
  timeout_seconds: number
  analyze: boolean
  views: MaterializedViewRefreshResultItem[]
  total_duration_seconds: number
  mv_availability_cache_reset?: boolean
}
