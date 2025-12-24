/**
 * Conservation API Response Types (Backend Contract)
 *
 * These types mirror the FastAPI responses from:
 * - `GET /api/v1/conservation/overview`
 * - `GET /api/v1/conservation/matrix`
 * - `GET /api/v1/conservation/regulations`
 * - `GET /api/v1/conservation/venn`
 *
 * UI-friendly transformed types live in `src/types/conservationPage.ts`.
 */

import type { ConservedRegulation } from './conservationPage'

export interface ConservationDistributionResponse {
  conservation_count: number
  lncrna_count: number
  regulation_count: number
  percentage: number
}

export interface SpeciesCombinationStatsResponse {
  combination_label: string
  species_names: string[]
  species_count: number
  lncrna_count: number
  regulation_count: number
}

export interface ConservationSummaryResponse {
  total_lncrnas: number
  total_regulations: number
  distribution: ConservationDistributionResponse[]
  top_combinations: SpeciesCombinationStatsResponse[]
  fully_conserved_count: number
  primate_specific_count: number
}

export interface ConservationMatrixSpeciesInfo {
  id: number
  name: string
}

export interface ConservationMatrixResponse {
  species: ConservationMatrixSpeciesInfo[]
  lncrna_matrix: number[][]
  regulation_matrix: number[][]
  jaccard_matrix: number[][]
  diagonal_totals: Record<string, number>
}

export interface ConservedRegulationListResponse {
  items: ConservedRegulation[]
  total: number
  page: number
  page_size: number
  total_pages: number
  min_species: number
}

export interface ConservationVennResponse {
  sets: string[]
  data: Record<string, number>
  data_type: 'lncrna' | 'regulation'
  total_patterns: number
  total_items: number
}

