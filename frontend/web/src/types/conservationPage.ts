/**
 * Conservation Page Types
 * Cross-species conservation analysis page type definitions
 */

/**
 * Species definition
 */
export interface Species {
  id: number
  name: string
  shortName: string
}

/**
 * Available species for conservation analysis
 */
export const CONSERVATION_SPECIES: Species[] = [
  { id: 1, name: 'Human', shortName: 'H' },
  { id: 2, name: 'Chimpanzee', shortName: 'C' },
  { id: 3, name: 'Macaque', shortName: 'M' },
  { id: 4, name: 'Marmoset', shortName: 'Ma' }
]

/**
 * Conservation overview statistics
 */
export interface ConservationOverview {
  /** Total number of conserved regulations */
  total_conserved: number
  /** Regulations conserved in all 4 species */
  four_species: number
  /** Regulations conserved in 3 species */
  three_species: number
  /** Regulations conserved in 2 species */
  two_species: number
  /** Statistics by species combination */
  by_combination: ConservationCombinationStats[]
}

/**
 * Statistics for a specific species combination
 */
export interface ConservationCombinationStats {
  /** Species IDs in this combination */
  species_ids: number[]
  /** Species names */
  species_names: string[]
  /** Number of shared regulations */
  regulation_count: number
  /** Conservation label (e.g., "1100") */
  conservation_label: string
}

/**
 * Conservation matrix data for heatmap
 */
export interface ConservationMatrixData {
  /** Species IDs */
  species: number[]
  /** Species names */
  species_names: string[]
  /** Matrix values (symmetric matrix) */
  matrix: number[][]
  /** Maximum value in matrix */
  max_value: number
  /** Minimum value in matrix */
  min_value: number
}

/**
 * Conserved regulation record
 */
export interface ConservedRegulation {
  /** Core ID (shared across species) */
  core_id: number
  /** LncRNA gene name */
  lncrna_gene_name: string | null
  /** LncRNA Ensembl ID */
  lncrna_ensembl_id: string | null
  /** Target gene name */
  target_gene_name: string | null
  /** Target Ensembl ID */
  target_ensembl_id: string | null
  /** Conservation label (e.g., "1100") */
  conservation_label: string
  /** Number of species with this regulation */
  species_count: number
  /** List of species IDs with this regulation */
  species_ids: number[]
  /** Average binding affinity across species */
  avg_binding_affinity: number | null
  /** Binding affinities per species */
  species_binding_affinities: SpeciesBindingAffinity[]
}

/**
 * Binding affinity for a specific species
 */
export interface SpeciesBindingAffinity {
  species_id: number
  species_name: string
  binding_affinity: number
}

/**
 * Conservation query parameters
 */
export interface ConservationQueryParams {
  /** Species IDs to include */
  species_ids: number[]
  /** Minimum conservation level (2-4 species) */
  min_conservation?: number
  /** Minimum binding affinity */
  min_ba?: number
  /** LncRNA gene name filter */
  lncrna_gene_name?: string
  /** Target gene name filter */
  target_gene_name?: string
  /** Page number */
  page?: number
  /** Page size */
  page_size?: number
}

/**
 * Paginated conserved regulations response
 */
export interface ConservedRegulationsResponse {
  items: ConservedRegulation[]
  total: number
  page: number
  page_size: number
  pages: number
}

/**
 * Venn diagram data for species overlap visualization
 */
export interface VennDiagramData {
  /** Single species counts */
  single: { [species_id: number]: number }
  /** Pairwise overlap counts */
  pairs: { [key: string]: number }
  /** Triple overlap counts */
  triples: { [key: string]: number }
  /** All four species overlap */
  all_four: number
}

/**
 * Conservation filter state for the page
 */
export interface ConservationFilterState {
  selectedSpecies: number[]
  minConservation: number
  minBA: number
  lncrnaName: string
  targetName: string
}
