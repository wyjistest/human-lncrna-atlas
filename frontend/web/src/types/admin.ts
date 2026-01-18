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
}

export interface MaterializedViewsStatusResponse {
  status: string
  refresh_lock_available: boolean
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

