/**
 * lncRNA-ChIP-seq Overlap Analysis Types
 * Phase 3.0 - Task 1.3
 *
 * Type definitions for lncRNA binding sites overlapping with ChIP-seq peaks.
 * This allows analysis of epigenetic regulation at lncRNA binding locations.
 */

import type { MarkType } from './chipseq'

/**
 * Filter parameters for overlap query
 */
export interface OverlapFilters {
  /** lncRNA gene ID to filter by */
  lncrna_gene_id?: number
  /** Target gene ID to filter by */
  target_gene_id?: number
  /** Mark type(s) - comma-separated for multiple (e.g., "H3K27me3,H3K4me3") */
  mark_type?: string
  /** Cell type(s) - comma-separated for multiple (e.g., "K562,GM12878") */
  cell_type?: string
  /** Chromosome filter */
  chromosome?: string
  /** Minimum overlap length in base pairs */
  min_overlap_length?: number
  /** Minimum binding affinity score */
  min_binding_affinity?: number
  /** Minimum peak signal/fold enrichment */
  min_peak_strength?: number
  /** Maximum Q-value (FDR) threshold */
  max_qvalue?: number
  /** Page number for pagination */
  page?: number
  /** Items per page */
  page_size?: number
  /** Sort field */
  sort_by?: 'overlap_length' | 'binding_affinity' | 'peak_fold_enrichment' | 'peak_qvalue'
  /** Sort direction */
  sort_order?: 'asc' | 'desc'
}

/**
 * Single overlap result between lncRNA binding site and ChIP-seq peak
 */
export interface OverlapResult {
  /** Unique identifier for this overlap */
  overlap_id: string

  // lncRNA information
  /** lncRNA gene ID */
  lncrna_gene_id: number
  /** lncRNA gene name/symbol */
  lncrna_name: string | null

  // Target gene information
  /** Target gene ID */
  target_gene_id: number
  /** Target gene name/symbol */
  target_gene_name: string | null

  // ChIP-seq mark information
  /** Histone modification mark type */
  mark_type: MarkType
  /** Mark category (repressive, activating, etc.) */
  mark_category: 'repressive' | 'activating' | 'bivalent_component' | 'enhancer' | 'elongation' | 'other'
  /** Cell type/line where this was observed */
  cell_type: string

  // Genomic coordinates
  /** Chromosome */
  chromosome: string
  /** lncRNA binding site start */
  lncrna_binding_start: number
  /** lncRNA binding site end */
  lncrna_binding_end: number
  /** ChIP-seq peak start */
  peak_start: number
  /** ChIP-seq peak end */
  peak_end: number
  /** Overlap region start */
  overlap_start: number
  /** Overlap region end */
  overlap_end: number
  /** Overlap length in base pairs */
  overlap_length: number

  // Functional scores
  /** lncRNA-target binding affinity score */
  binding_affinity: number
  /** ChIP-seq peak fold enrichment */
  peak_fold_enrichment: number
  /** ChIP-seq peak Q-value (FDR) */
  peak_qvalue: number | null
}

/**
 * Paginated response for overlap queries
 */
export interface OverlapResponse {
  /** Total number of overlaps matching filters */
  total: number
  /** Current page number */
  page: number
  /** Items per page */
  page_size: number
  /** Array of overlap results for current page */
  items: OverlapResult[]
}

/**
 * Cursor (keyset) pagination response for overlap queries
 */
export interface OverlapCursorResponse {
  /** Total number of overlaps matching filters */
  total: number
  /** Items per page */
  page_size: number
  /** Array of overlap results for current page */
  items: OverlapResult[]
  /** Opaque cursor token for fetching the next page */
  next_cursor: string | null
  /** True if there are more results after this page */
  has_more: boolean
  /** True if default chromosome filter (chr22) was applied */
  default_filter_applied: boolean
  /** The chromosome filter actually used in the query */
  effective_chromosome: string | null
  /** True if the optimized materialized view was used */
  using_materialized_view: boolean
}

/**
 * Summary statistics for overlap analysis (Phase 2)
 */
export interface OverlapSummary {
  /** Total number of overlaps */
  total_overlaps: number
  /** Number of unique lncRNAs involved */
  unique_lncrnas: number
  /** Number of unique target genes involved */
  unique_target_genes: number
  /** Number of unique mark types */
  unique_marks: number
  /** Number of unique cell types */
  unique_cell_types: number

  // Aggregate statistics
  /** Average overlap length */
  avg_overlap_length: number
  /** Average binding affinity */
  avg_binding_affinity: number
  /** Average peak strength */
  avg_peak_strength: number

  // Breakdowns
  /** Statistics by mark type */
  by_mark_type: Array<{
    mark_type: string
    count: number
    avg_strength: number
  }>
  /** Statistics by cell type */
  by_cell_type: Array<{
    cell_type: string
    count: number
  }>

  /** True if default chromosome filter (chr22) was applied for performance optimization */
  default_filter_applied?: boolean
  /** The chromosome filter actually used in the query */
  effective_chromosome?: string | null
}

export interface OverlapCrossSpeciesComparisonResponse {
  lncrna_core_id: number
  target_core_id: number | null
  species_names: Record<string, string>
  species_stats: Record<
    number,
    {
      species_id: number
      species_name: string
      lncrna_gene_id: number | null
      target_gene_id: number | null
      statistics: OverlapSummary
    }
  >
}

/**
 * Mark category mapping (aligned with ChIP-seq schema)
 */
export type MarkCategory = 'repressive' | 'activating' | 'bivalent_component' | 'enhancer' | 'elongation' | 'other' | 'open_chromatin'

/**
 * Cell type options (common ENCODE cell lines)
 */
export const CELL_TYPE_OPTIONS = [
  'K562',      // Chronic myelogenous leukemia
  'GM12878',   // Lymphoblastoid
  'HepG2',     // Hepatocellular carcinoma
  'H1-hESC',   // Human embryonic stem cells
  'HeLa-S3',   // Cervical cancer
  'A549',      // Lung carcinoma
  'MCF-7',     // Breast cancer
  'HMEC',      // Human mammary epithelial cells
] as const

/**
 * Chromosome options
 */
export const CHROMOSOME_OPTIONS = [
  'chr1', 'chr2', 'chr3', 'chr4', 'chr5', 'chr6',
  'chr7', 'chr8', 'chr9', 'chr10', 'chr11', 'chr12',
  'chr13', 'chr14', 'chr15', 'chr16', 'chr17', 'chr18',
  'chr19', 'chr20', 'chr21', 'chr22', 'chrX', 'chrY', 'chrM'
] as const

export type CellType = typeof CELL_TYPE_OPTIONS[number]
export type Chromosome = typeof CHROMOSOME_OPTIONS[number]

/**
 * Heatmap data structure for overlap visualization (Phase 3.0 Phase 2)
 */
export interface OverlapHeatmapData {
  /** X-axis labels (mark types or cell types) */
  x_labels: string[]
  /** Y-axis labels (lncRNAs or target genes) */
  y_labels: string[]
  /** Heatmap data points */
  data: Array<{ x: string; y: string; value: number }>
  /** Current metric being displayed */
  metric: OverlapHeatmapMetric
  /** Total possible combinations */
  total_combinations: number
  /** Combinations with valid data */
  valid_combinations: number
}

/**
 * Heatmap metric options
 */
export type OverlapHeatmapMetric = 'count' | 'avg_binding_affinity' | 'total_overlap_length'

/**
 * X-axis options for heatmap
 */
export type OverlapHeatmapXAxis = 'mark_type' | 'cell_type'

/**
 * Y-axis options for heatmap
 */
export type OverlapHeatmapYAxis = 'lncrna' | 'target_gene'

/**
 * Heatmap request parameters
 */
export interface OverlapHeatmapParams {
  /** X-axis dimension */
  x_axis: OverlapHeatmapXAxis
  /** Y-axis dimension */
  y_axis: OverlapHeatmapYAxis
  /** Metric to display */
  metric: OverlapHeatmapMetric
  /** Top N items to include */
  top_n?: number
  /** Chromosome filter */
  chromosome?: string
  /** Minimum binding affinity filter */
  min_binding_affinity?: number
  /** Maximum Q-value filter */
  max_qvalue?: number
}
