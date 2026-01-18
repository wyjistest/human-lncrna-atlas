/**
 * Stats API Types
 *
 * Type definitions for statistics API endpoints
 * API: /api/v1/stats/*
 */

/**
 * Top gene by regulation count
 * API: GET /api/v1/stats/top-genes
 */
export interface TopGene {
  gene_id: number
  core_id: number
  gene_name: string | null
  gene_type: string
  species_name: string
  regulation_count: number
}

/**
 * Top disease by gene association count
 * API: GET /api/v1/stats/top-diseases
 */
export interface TopDisease {
  trait_id: number
  trait_name: string
  trait_category: string | null
  gene_count: number
  lncrna_count: number
}

/**
 * Conserved regulation across species
 * API: GET /api/v1/stats/conserved-regulations
 */
export interface ConservedRegulation {
  lncrna_core_id: number
  lncrna_name: string | null
  target_core_id: number
  target_name: string | null
  species_count: number
  species_list: string[]
  avg_binding_affinity: number | null
}

/**
 * Cache status information
 * API: GET /api/v1/stats/cache-status
 */
export interface CacheStats {
  backend: 'redis' | 'memory'
  enabled: boolean
  hits: number
  misses: number
  total_requests: number
  hit_rate: string
  hit_rate_pct: number
  namespaces: {
    tracked: number
    top: Array<{
      namespace: string
      requests: number
      hits: number
      misses: number
      hit_rate_pct: number
      compute_count: number
      compute_avg_ms: number
      compute_max_ms: number
    }>
    limit: number
  }
  keys?: {
    tracked: number
    top: Array<{
      key: string
      namespace?: string | null
      requests: number
      hits: number
      misses: number
      hit_rate_pct: number
    }>
    limit: number
  }
  redis?: {
    host: string
    connected: boolean
  }
  memory?: {
    size: number
    max_size: number
    evictions: number
  }
}

/**
 * Parameters for top genes query
 */
export interface TopGenesParams {
  /** Number of genes to return (default: 10) */
  limit?: number
  /** Filter by gene type (lncRNA/protein_coding) */
  gene_type?: string
}

/**
 * Parameters for top diseases query
 */
export interface TopDiseasesParams {
  /** Number of diseases to return (default: 10) */
  limit?: number
}

/**
 * Parameters for conserved regulations query
 */
export interface ConservedRegulationsParams {
  /** Minimum species count (default: 2) */
  min_species?: number
  /** Number of results (default: 100) */
  limit?: number
}
