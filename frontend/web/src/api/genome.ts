/**
 * Genome Browser API client
 * Provides methods for fetching IGV.js configuration and genome data
 */
import { apiClient } from './client'

/**
 * Standard API response wrapper
 * All API responses follow this format: { success: boolean, data: T, message: string }
 */
export interface ApiResponse<T> {
  success: boolean
  data: T
  message: string
}

export interface IGVTrackConfig {
  name: string
  type: string
  format: string
  url: string
  /** Optional IGV.js service track to fetch by viewport */
  sourceType?: string
  indexURL?: string
  displayMode?: string
  color?: string
  /** Alternative color for negative strand features (used with colorByStrand) */
  altColor?: string
  height?: number
  visibilityWindow?: number

  // Label and display configuration
  /** Label fields to display for features (for bigBed/bigGenePred) */
  labelFields?: string
  /** Default label field to display */
  defaultLabelFields?: string
  /** Field name to use for feature name */
  nameField?: string
  /** Row height in EXPANDED display mode */
  expandedRowHeight?: number
  /** Row height in SQUISHED display mode */
  squishedRowHeight?: number

  // Track behavior options
  /** Track order (lower numbers appear first) */
  order?: number
  /** Whether the track can be removed by the user */
  removable?: boolean
  /** Whether features in this track are searchable */
  searchable?: boolean
  /** Description shown in track menu */
  description?: string
  /** Whether to use item RGB colors from the file (for bigBed 9+) */
  itemRgb?: boolean
  /** Color features by strand */
  colorByStrand?: string
  /** URL template for feature info links. Use $$ as placeholder for feature name */
  infoURL?: string

  // Interaction track specific options
  /** Arc type for interaction tracks: 'proportional' scales arc height by distance, 'nested' stacks arcs */
  arcType?: 'proportional' | 'nested'
  /** Arc orientation: 'UP' draws arcs above, 'DOWN' draws below, boolean for auto */
  arcOrientation?: 'UP' | 'DOWN' | boolean
  /** Alpha transparency for arcs (0-1 or string like "0.05") */
  alpha?: number | string
  /** Use logarithmic scale for arc heights */
  logScale?: boolean
  /** Show blocks at arc endpoints */
  showBlocks?: boolean
  /** Maximum value for scaling */
  max?: number
  /** Use score field for coloring/sizing */
  useScore?: boolean
}

export type IGVTrackConfigWithId = IGVTrackConfig & {
  id: string
}

export interface IGVConfig {
  // 内置基因组 ID (如 "hg19")，使用时 reference 为 null
  genome?: string | null
  // 自定义参考基因组配置，使用时 genome 为 null
  reference?: {
    id: string
    name: string
    fastaURL?: string | null
    indexURL?: string | null
    cytobandURL?: string | null
    twoBitURL?: string | null      // New: 2bit format URL (preferred for remote genomes)
    chromSizesURL?: string | null  // Optional: chromosome sizes file URL
  } | null
  locus: string
  tracks: IGVTrackConfig[]
}

export interface GenomeSearchResult {
  gene_id: number
  gene_name: string
  gene_ensembl_id: string
  chromosome: string
  gene_start: number
  gene_end: number
  strand: string
}

/** Autocomplete result item from /api/v1/igv/autocomplete */
export interface GeneAutocompleteItem {
  gene_name: string
  chromosome: string
  start: number
  end: number
  species_id: number
}

/** Autocomplete API response */
export interface GeneAutocompleteResponse {
  success: boolean
  data: GeneAutocompleteItem[]
}

/** ChIP-seq mark info for available marks API */
export interface ChIPSeqMarkInfo {
  mark_name: string
  display_name: string
  mark_category: string
  display_color: string
  description: string | null
  experiment_count: number
  peak_count: number
}

/** Response from /api/v1/igv/chipseq/marks/{speciesId} */
export interface ChIPSeqMarksResponse {
  species_id: number
  marks: ChIPSeqMarkInfo[]
}

export const genomeApi = {
  /**
   * Get IGV configuration for a specific species
   * @param speciesId - Species ID (1: Human, 2: Chimpanzee, 3: Macaque, 4: Marmoset)
   * @returns API response with IGVConfig wrapped in { success, data, message }
   */
  getIGVConfig: (speciesId: number, signal?: AbortSignal) =>
    apiClient.get<ApiResponse<IGVConfig>>(`/api/v1/igv/config/${speciesId}`, { signal }),

  /**
   * Get IGV configuration for a specific gene
   * Auto-locates to the gene position and loads only its regulations
   * @param geneName - Gene name (e.g., CATG00000000011.1)
   * @param padding - Padding around gene (default 50kb)
   * @returns API response with IGVConfig wrapped in { success, data, message }
   */
  getIGVConfigForGene: (geneName: string, padding?: number, signal?: AbortSignal) =>
    apiClient.get<ApiResponse<IGVConfig>>(`/api/v1/igv/config/gene/${encodeURIComponent(geneName)}`, {
      params: padding !== undefined ? { padding } : undefined,
      signal
    }),

  /**
   * Search for a gene by name
   * @param speciesId - Species ID
   * @param query - Gene name or Ensembl ID to search
   */
  searchGene: (speciesId: number, query: string, signal?: AbortSignal) =>
    apiClient.get<GenomeSearchResult[]>('/api/v1/igv/search', {
      params: { species_id: speciesId, query },
      signal
    }),

  /**
   * Autocomplete gene search
   * Returns matching genes for autocomplete suggestions
   * @param query - Partial gene name to search (e.g., "hla-")
   * @param speciesId - Species ID (1: Human, 2: Chimpanzee, 3: Macaque, 4: Marmoset)
   * @param limit - Maximum number of results (default 10)
   */
  autocompleteGene: (query: string, speciesId: number, limit: number = 10, signal?: AbortSignal) =>
    apiClient.get<GeneAutocompleteResponse>('/api/v1/igv/autocomplete', {
      params: { q: query, species_id: speciesId, limit },
      signal
    }),

  /**
   * Get available ChIP-seq marks for a species
   * @param speciesId - Species ID (1: Human, 2: Chimpanzee, 3: Macaque, 4: Marmoset)
   * @returns API response with available marks and their metadata
   */
  getChIPSeqMarks: (speciesId: number, signal?: AbortSignal) =>
    apiClient.get<ApiResponse<ChIPSeqMarksResponse>>(`/api/v1/igv/chipseq/marks/${speciesId}`, { signal }),

  /**
   * Get IGV configuration with ChIP-seq tracks included
   * @param speciesId - Species ID
   * @param markTypes - Array of mark types to include (e.g., ['H3K27me3', 'H3K4me3'])
   * @returns API response with IGVConfig including ChIP-seq tracks
   */
  getIGVConfigWithChIPSeq: (speciesId: number, markTypes: string[], signal?: AbortSignal) =>
    apiClient.get<ApiResponse<IGVConfig>>(`/api/v1/igv/config/chipseq/${speciesId}`, {
      params: { mark_types: markTypes.join(',') },
      signal
    }),

  /**
   * Get UCSC multiz-derived conservation track configs (phastCons/phyloP)
   *
   * Notes:
   * - Currently only supports Human/hg19 (species_id=1) to match the project's assembly.
   * - Tracks are remote BigWig URLs served by UCSC (requires CORS + HTTP Range).
   */
  getUCSCMultizTracks: (speciesId: number, signal?: AbortSignal) =>
    apiClient.get<ApiResponse<{
      tracks: IGVTrackConfigWithId[]
      species_id: number
      species_name: string
      genome_assembly?: string
    }>>(`/api/v1/igv/config/ucsc-multiz/${speciesId}`, { signal }),
}
