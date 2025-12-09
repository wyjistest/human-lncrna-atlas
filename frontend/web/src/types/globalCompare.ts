/**
 * Global Compare Type Definitions
 * Phase 2.5 - Types for multi-marks comparison across the entire database
 *
 * These types support global-level comparison (not gene-specific):
 * - Cross-mark comparison statistics
 * - Cell line x Mark matrix data
 * - Signal distribution data
 */

import type { MarkType, MarkCategory } from './chipseq'

/**
 * Summary statistics for a single mark in global comparison
 */
export interface GlobalMarkSummary {
  /** Mark type identifier */
  mark_type: MarkType
  /** Mark category */
  category: MarkCategory
  /** Total number of peaks across all genes */
  total_peaks: number
  /** Number of genes with this mark */
  gene_count: number
  /** Number of cell types with this mark */
  cell_type_count: number
  /** Average signal value across all peaks */
  avg_signal: number
  /** Maximum signal value */
  max_signal: number
  /** Average fold enrichment */
  avg_fold_enrichment: number
  /** Median fold enrichment */
  median_fold_enrichment: number
  /** Total genomic coverage in base pairs */
  total_coverage_bp: number
  /** Average peak width */
  avg_peak_width: number
  /** Position distribution percentages */
  position_distribution: Record<string, number>
}

/**
 * Parameters for global compare API
 */
export interface GlobalCompareParams {
  /** Filter by mark types (optional, all marks if not specified) */
  marks?: MarkType[]
  /** Filter by cell types (optional) */
  cell_types?: string[]
  /** Minimum peak count threshold */
  min_peaks?: number
  /** Include position distribution data */
  include_position_distribution?: boolean
}

/**
 * Response from global compare API
 */
export interface GlobalCompareResponse {
  /** List of mark summaries */
  marks: GlobalMarkSummary[]
  /** Total number of marks in response */
  total_marks: number
  /** Filters applied */
  filters_applied: {
    marks?: MarkType[]
    cell_types?: string[]
    min_peaks?: number
  }
  /** Query timestamp */
  timestamp: string
}

/**
 * Cell type entry in cell line matrix
 */
export interface CellLineMatrixEntry {
  /** Cell type identifier */
  cell_type: string
  /** Mark type */
  mark_type: MarkType
  /** Value for the selected metric */
  value: number | null
  /** Peak count */
  peak_count: number
  /** Gene count */
  gene_count: number
  /** Average signal */
  avg_signal: number | null
  /** Total coverage */
  total_coverage_bp: number
}

/**
 * Parameters for cell line matrix API
 */
export interface CellLineMatrixParams {
  /** Mark types to include (X-axis) */
  marks?: MarkType[]
  /** Cell types to include (Y-axis) */
  cell_types?: string[]
  /** Metric to use for matrix values */
  metric: CellLineMatrixMetric
}

/**
 * Metric types for cell line matrix
 */
export type CellLineMatrixMetric =
  | 'peak_count'
  | 'gene_count'
  | 'avg_signal'
  | 'total_coverage_bp'
  | 'avg_fold_enrichment'

/**
 * Response from cell line matrix API
 */
export interface CellLineMatrixResponse {
  /** X-axis labels (mark types) */
  x_labels: MarkType[]
  /** Y-axis labels (cell types) */
  y_labels: string[]
  /** Selected metric */
  metric: CellLineMatrixMetric
  /** Matrix data: [x_index, y_index, value] */
  data: CellLineMatrixEntry[]
  /** 2D matrix for easy access: matrix[y][x] */
  matrix: Array<Array<number | null>>
  /** Total combinations */
  total_combinations: number
  /** Valid combinations (non-null values) */
  valid_combinations: number
}

/**
 * Signal distribution data point
 */
export interface SignalDistributionPoint {
  /** Mark type */
  mark_type: MarkType
  /** Signal value bins */
  bins: number[]
  /** Counts per bin */
  counts: number[]
  /** Statistics */
  stats: {
    min: number
    max: number
    mean: number
    median: number
    std: number
    q1: number
    q3: number
  }
}

/**
 * Parameters for signal distribution API
 */
export interface SignalDistParams {
  /** Mark types to include */
  marks?: MarkType[]
  /** Cell types filter */
  cell_types?: string[]
  /** Number of bins for histogram */
  bins?: number
}

/**
 * Response from signal distribution API
 */
export interface SignalDistResponse {
  /** Distribution data for each mark */
  distributions: SignalDistributionPoint[]
  /** Filters applied */
  filters_applied: {
    marks?: MarkType[]
    cell_types?: string[]
  }
}

/**
 * Radar chart dimension configuration
 */
export interface RadarDimension {
  /** Dimension name */
  name: string
  /** Maximum value for this dimension */
  max: number
  /** Minimum value (default 0) */
  min?: number
}

/**
 * Radar chart data point
 */
export interface RadarDataPoint {
  /** Mark type */
  mark_type: MarkType
  /** Values for each dimension */
  values: number[]
  /** Display name */
  name: string
  /** Color for this series */
  color: string
}

/**
 * Box plot data for a single mark
 */
export interface BoxPlotData {
  /** Mark type */
  mark_type: MarkType
  /** Min value */
  min: number
  /** Q1 (25th percentile) */
  q1: number
  /** Median (50th percentile) */
  median: number
  /** Q3 (75th percentile) */
  q3: number
  /** Max value */
  max: number
  /** Outliers */
  outliers?: number[]
  /** Sample size */
  n: number
}

/**
 * View mode for GlobalCompareSection
 */
export type GlobalCompareViewMode = 'radar' | 'bar' | 'boxplot' | 'matrix'

/**
 * Filter state for GlobalCompareSection
 */
export interface GlobalCompareFilters {
  /** Selected marks */
  selectedMarks: MarkType[]
  /** Selected cell types */
  selectedCellTypes: string[]
  /** Matrix metric */
  matrixMetric: CellLineMatrixMetric
}
