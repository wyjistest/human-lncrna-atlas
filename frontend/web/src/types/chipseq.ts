/**
 * ChIP-seq Type Definitions
 * Phase 2.2 - Universal ChIP-seq support for 15+ histone modification marks
 */

/**
 * Histone modification mark types
 * Represents all supported ChIP-seq marks
 */
export type MarkType =
  // Repressive marks
  | 'H3K27me3'   // Polycomb repressive mark
  | 'H3K9me3'    // Heterochromatin mark
  | 'H3K9me2'    // Heterochromatin mark (weaker)
  // Activating marks - promoter
  | 'H3K4me3'    // Active promoter mark
  | 'H3K4me2'    // Active promoter (weaker)
  // Activating marks - enhancer
  | 'H3K4me1'    // Enhancer mark
  | 'H3K27ac'    // Active enhancer mark
  | 'H3K9ac'     // Active chromatin
  | 'H3K36me3'   // Transcription elongation
  | 'H3K79me2'   // Transcription elongation
  // Other marks
  | 'H2AZ'       // Histone variant - regulatory regions
  | 'H2BK120ub'  // Ubiquitination mark
  | 'H4K20me1'   // Cell cycle regulation
  | 'H3K4ac'     // Active chromatin
  | 'H3K14ac'    // Active chromatin
  | 'H3K18ac'    // Active chromatin

/**
 * Mark category for grouping and styling
 */
export type MarkCategory = 'repressive' | 'activating' | 'enhancer' | 'elongation' | 'other'

/**
 * Configuration interface for each mark type
 */
export interface MarkConfig {
  /** Display name with functional description */
  displayName: string
  /** Short name for compact displays */
  shortName: string
  /** Color for visualization (hex) */
  color: string
  /** Secondary/lighter color for backgrounds */
  secondaryColor: string
  /** Mark category for grouping */
  category: MarkCategory
  /** Functional description */
  description: string
  /** Icon identifier (emoji or icon name) */
  icon: string
  /** Default filter values for this mark */
  defaultFilters: ChIPSeqFilters
  /** Whether this mark is commonly used */
  isCommon: boolean
  /** Sort priority (lower = higher priority) */
  sortOrder: number
}

/**
 * ChIP-seq peak data from backend API
 */
export interface ChIPSeqPeak {
  /** Unique peak identifier */
  peak_id: number
  /** Gene ID this peak is associated with */
  gene_id: number
  /** Mark type (e.g., H3K27me3) */
  mark_type: MarkType
  /** Chromosome */
  chromosome: string
  /** Peak start position */
  peak_start: number
  /** Peak end position */
  peak_end: number
  /** Peak width in bp */
  peak_width: number
  /** Peak summit position (absolute) */
  summit_position?: number | null
  /** Signal value at peak */
  signal_value: number | null
  /** P-value (-log10) */
  pvalue: number | null
  /** Q-value (-log10) */
  qvalue: number | null
  /** Fold enrichment over background */
  fold_enrichment: number | null
  /** Position relative to gene TSS */
  relative_position?: string
  /** Distance to TSS in bp */
  distance_to_tss?: number
  /** Strand of the gene */
  strand?: string
  /** Cell type / sample source */
  cell_type?: string
  /** Experiment ID reference */
  experiment_id?: string | number
}

/**
 * Filter parameters for ChIP-seq queries
 */
export interface ChIPSeqFilters {
  /** Filter by mark type */
  mark_type?: MarkType
  /** Minimum fold enrichment */
  min_fold_enrichment?: number
  /** Maximum fold enrichment */
  max_fold_enrichment?: number
  /** Maximum q-value (FDR) */
  max_qvalue?: number
  /** Maximum p-value */
  max_pvalue?: number
  /** Minimum signal value */
  min_signal?: number
  /** Position relative to gene (e.g., 'promoter', 'intron', 'upstream') */
  relative_position?: string
  /** Filter by cell type */
  cell_type?: string
  /** Flanking region in bp (default 10000) */
  flanking?: number
  /** Current page number */
  page?: number
  /** Items per page */
  page_size?: number
  /** Sort field */
  sort_by?: 'signal_value' | 'fold_enrichment' | 'qvalue' | 'pvalue' | 'peak_start'
  /** Sort direction */
  sort_order?: 'asc' | 'desc'
}

/**
 * Paginated response for ChIP-seq peaks
 */
export interface ChIPSeqResponse {
  /** Total number of peaks matching filters */
  total: number
  /** Current page items */
  items: ChIPSeqPeak[]
  /** Current page number */
  page: number
  /** Items per page */
  page_size: number
}

/**
 * Raw backend response for gene ChIP-seq data
 * This is the actual structure returned by /api/v1/features/chipseq/genes/{gene_id}
 */
export interface GeneChIPSeqRawResponse {
  gene_id: number
  gene_name: string
  chromosome: string
  gene_start: number
  gene_end: number
  strand: string
  region_start: number
  region_end: number
  /** Peaks grouped by mark type */
  marks: Record<string, GenePeakAssociation[]>
  total_peaks: number
  marks_present: string[]
}

/**
 * Peak association data from backend
 */
export interface GenePeakAssociation {
  peak_id: number
  chromosome: string
  peak_start: number
  peak_end: number
  summit_position: number | null
  overlap_type: string
  distance_to_tss: number
  overlap_bp: number
  fold_enrichment: number | null
  qvalue: number | null
  mark_type: MarkType
  mark_category: string
  experiment_id: number
}

/**
 * Peak width percentile statistics
 */
export interface PeakWidthPercentiles {
  /** 25th percentile */
  p25: number
  /** 50th percentile (median) */
  p50: number
  /** 75th percentile */
  p75: number
}

/**
 * Summary statistics for ChIP-seq data
 */
export interface ChIPSeqSummary {
  /** Mark type */
  mark_type: MarkType
  /** Total number of peaks */
  total_peaks: number
  /** Average signal value */
  avg_signal: number
  /** Maximum signal value */
  max_signal: number
  /** Average fold enrichment */
  avg_fold_enrichment: number
  /** Peaks in promoter region */
  promoter_peaks: number
  /** Peaks in gene body */
  gene_body_peaks: number
  /** Peaks in upstream region */
  upstream_peaks: number
  /** Peaks in downstream region */
  downstream_peaks: number
  /** Distribution by relative position */
  position_distribution: Record<string, number>
  /** Signal distribution histogram */
  signal_distribution?: Array<{ range: string; count: number }>
  /** Whether this gene has bivalent domain (H3K4me3 + H3K27me3) */
  has_bivalent_domain?: boolean
  /** Median fold enrichment */
  median_fold_enrichment?: number
  /** Standard deviation of fold enrichment */
  std_fold_enrichment?: number
  /** Total coverage in base pairs */
  total_coverage_bp?: number
  /** Peak width distribution percentiles */
  peak_width_percentiles?: PeakWidthPercentiles
}

/**
 * Mark comparison data
 */
export interface MarkComparisonData {
  /** Mark type */
  mark_type: MarkType
  /** Summary statistics */
  summary: ChIPSeqSummary
  /** Top peaks (limited) */
  top_peaks: ChIPSeqPeak[]
}

/**
 * Overlap region between two marks
 */
export interface OverlapRegion {
  /** First mark type */
  mark1: MarkType
  /** Second mark type */
  mark2: MarkType
  /** Number of overlapping regions */
  region_count: number
  /** Total base pairs in overlap */
  total_bp: number
}

/**
 * Overlapping region with domain classification
 */
export interface OverlappingRegionDetail {
  /** Chromosome */
  chromosome: string
  /** Start position */
  start: number
  /** End position */
  end: number
  /** Marks present in this region */
  marks: MarkType[]
  /** Domain type classification */
  domain_type: 'bivalent' | 'active' | 'repressed'
}

/**
 * Raw mark data from backend compare API
 */
export interface RawCompareMarkData {
  mark_type: MarkType
  mark_category: string
  display_color: string
  peaks: Array<{
    peak_id: number
    chromosome: string
    peak_start: number
    peak_end: number
    summit_position: number | null
    fold_enrichment: number | null
    qvalue: number | null
    mark_type: MarkType
  }>
  peak_count: number
  avg_fold_enrichment: number | null
  median_fold_enrichment: number | null
  std_fold_enrichment: number | null
  total_coverage_bp: number | null
  peak_width_percentiles: PeakWidthPercentiles | null
}

/**
 * Raw response from compare API
 */
export interface RawChIPSeqCompareResponse {
  gene_id: number
  gene_name: string
  chromosome: string
  region_start: number
  region_end: number
  marks: RawCompareMarkData[]
  all_overlaps: Array<{
    chromosome: string
    start: number
    end: number
    marks: MarkType[]
  }>
  overlap_statistics: Record<string, number>
  overlapping_regions: OverlappingRegionDetail[]
  bivalent_regions: Array<{
    chromosome: string
    start: number
    end: number
  }>
}

/**
 * Response for mark comparison API
 */
export interface ChIPSeqCompareResponse {
  /** Gene ID */
  gene_id: number
  /** Gene name (optional) */
  gene_name?: string
  /** Comparison data for each mark */
  marks: MarkComparisonData[]
  /** Overlap statistics between marks */
  overlap_stats?: Record<string, number>
  /** Overlap regions between mark pairs */
  overlap_regions?: OverlapRegion[]
  /** Detailed overlapping regions with domain classification */
  overlapping_regions?: OverlappingRegionDetail[]
  /** Whether bivalent domain is detected (H3K4me3 + H3K27me3) */
  has_bivalent_domain?: boolean
}

/**
 * Available marks for a species
 */
export interface AvailableMarksResponse {
  /** Species ID */
  species_id: number
  /** List of available marks */
  marks: Array<{
    mark_type: MarkType
    display_name: string
    peak_count: number
    gene_count: number
  }>
}

/**
 * View modes for multi-mark display
 */
export type CompareViewMode = 'merged' | 'parallel' | 'stats'

/**
 * Position relative to gene
 */
export const RELATIVE_POSITIONS = [
  { value: 'promoter', label: 'Promoter' },
  { value: 'upstream', label: 'Upstream' },
  { value: 'downstream', label: 'Downstream' },
  { value: 'exon', label: 'Exon' },
  { value: 'intron', label: 'Intron' },
  { value: 'gene_body', label: 'Gene Body' },
] as const

/**
 * Sort options for peaks table
 */
export const SORT_OPTIONS = [
  { value: 'signal_value', label: 'Signal Value' },
  { value: 'fold_enrichment', label: 'Fold Enrichment' },
  { value: 'qvalue', label: 'Q-Value' },
  { value: 'pvalue', label: 'P-Value' },
  { value: 'peak_start', label: 'Position' },
] as const

/**
 * Default filter values
 */
export const DEFAULT_CHIPSEQ_FILTERS: ChIPSeqFilters = {
  page: 1,
  page_size: 20,
  flanking: 10000,
  sort_by: 'fold_enrichment',
  sort_order: 'desc',
}

// ============================================
// CELL LINE COMPARISON TYPES (Phase 2.6)
// ============================================

/**
 * Entry for a single cell line in cell line comparison
 */
export interface CellLineComparisonEntry {
  /** Cell type identifier (e.g., 'K562', 'GM12878') */
  cell_type: string
  /** Optional cell line name */
  cell_line?: string
  /** Peaks for this cell line */
  peaks: ChIPSeqPeak[]
  /** Total number of peaks */
  total_peaks: number
  /** Average signal value */
  avg_signal?: number
  /** Median fold enrichment */
  median_fold_enrichment?: number
  /** Standard deviation of fold enrichment */
  std_fold_enrichment?: number
  /** Total coverage in base pairs */
  total_coverage_bp: number
  /** Peak width percentile distribution */
  peak_width_percentiles?: PeakWidthPercentiles
}

/**
 * Overlap region between two cell lines for the same mark
 */
export interface CellLineOverlapRegion {
  /** Chromosome */
  chromosome: string
  /** Start position */
  start: number
  /** End position */
  end: number
  /** Length of overlap region */
  length: number
  /** First cell type */
  cell_type_1: string
  /** Second cell type */
  cell_type_2: string
  /** Peak ID from first cell type */
  peak_id_1: number
  /** Peak ID from second cell type */
  peak_id_2: number
}

/**
 * Response from cell line comparison API
 */
export interface CellLineComparisonResponse {
  /** Gene ID */
  gene_id: number
  /** Gene name */
  gene_name: string
  /** Chromosome */
  chromosome: string
  /** Region start position */
  region_start: number
  /** Region end position */
  region_end: number
  /** Mark type being compared */
  mark_type: string
  /** Data for each cell line */
  cell_lines: CellLineComparisonEntry[]
  /** Overlap regions between cell lines */
  overlap_regions?: CellLineOverlapRegion[]
  /** Total number of cell lines in comparison */
  total_cell_lines: number
  /** Number of peaks common across all cell lines */
  common_peaks: number
}
