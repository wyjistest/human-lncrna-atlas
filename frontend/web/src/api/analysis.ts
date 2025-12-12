/**
 * Analysis API Client
 *
 * Wraps the export APIs from Phase 6.0-A for frontend consumption
 */

import { apiClient } from './client'

export interface AnalysisSummary {
  high_affinity: {
    total_regulations: number
    unique_lncrnas: number
    unique_targets: number
    avg_ba: number
    max_ba: number
  }
  conservation: {
    four_species: number
    three_species: number
    two_species: number
    total_conserved: number
  }
  epigenetic: {
    total_overlaps: number
    bivalent_domains: number
    active_marks: number
    repressive_marks: number
  }
  disease: {
    total_diseases: number
    total_lncrnas: number
    total_genes: number
    avg_connections: number
  }
}

export interface HighAffinityRecord {
  lncrna_gene_id: number
  lncrna_name: string
  target_gene_id: number
  target_name: string
  binding_affinity: number
  species_id: number
  species_name: string
  chr: string
  start_in_genome: number
  end_in_genome: number
}

export interface ConservationRecord {
  core_id: number
  lncrna_names: string
  species_count: number
  total_regulations: number
  avg_binding_affinity: number
  conserved_targets: number
}

export interface ChIPSeqOverlapRecord {
  regulation_id: number
  lncrna_name: string
  target_name: string
  binding_affinity: number
  mark_name: string
  peak_score: number
  peak_chr: string
  peak_start: number
  peak_end: number
  cell_type: string
}

export interface DiseaseNetworkNode {
  id: string
  type: 'disease' | 'gene' | 'lncrna'
  name: string
}

export interface DiseaseNetworkEdge {
  source: string
  target: string
  type: 'disease-gene' | 'regulation'
  weight: number
}

export interface DiseaseNetworkResponse {
  nodes: DiseaseNetworkNode[]
  edges: DiseaseNetworkEdge[]
  query_params: {
    trait_name: string | null
    limit: number
    format: string
  }
}

export interface PaginatedResponse<T> {
  data: T[]
  total: number
  page: number
  page_size: number
}

export const analysisApi = {
  /**
   * Get summary statistics for all analysis modules
   */
  getSummary: () =>
    apiClient.get<AnalysisSummary>('/api/v1/analysis/summary'),

  /**
   * Get high affinity regulatory relationships
   */
  getHighAffinity: (params?: {
    min_ba?: number
    species_id?: number
    limit?: number
    offset?: number
  }) =>
    apiClient.get<PaginatedResponse<HighAffinityRecord>>('/api/v1/export/high-affinity', { params }),

  /**
   * Get conservation data across species
   */
  getConservation: (params?: {
    min_species_count?: number
    limit?: number
    offset?: number
  }) =>
    apiClient.get<PaginatedResponse<ConservationRecord>>('/api/v1/export/conservation', { params }),

  /**
   * Get ChIP-seq overlaps for epigenetic analysis
   */
  getChipseqOverlaps: (params?: {
    mark_names?: string[]
    cell_types?: string[]
    min_ba?: number
    limit?: number
    offset?: number
  }) =>
    apiClient.get<PaginatedResponse<ChIPSeqOverlapRecord>>('/api/v1/export/chipseq-overlaps', { params }),

  /**
   * Get disease network data
   */
  getDiseaseNetwork: (params?: {
    trait_name?: string
    min_ba?: number
    limit?: number
    offset?: number
  }) =>
    apiClient.get<DiseaseNetworkResponse>('/api/v1/export/disease-network', { params }),
}
