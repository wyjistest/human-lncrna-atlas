/**
 * Genomic Features Type Definitions
 * Phase 2.1 - RepeatMasker and other genomic feature types
 */

/**
 * Base interface for all genomic features
 */
export interface GenomicFeature {
  feature_id: number
  chromosome: string
  feature_start: number
  feature_end: number
  feature_name?: string
  strand?: string
  score?: number
  attributes: Record<string, unknown>
}

/**
 * RepeatMasker Feature
 * Represents a repeat element annotation from RepeatMasker
 */
export interface RepeatMaskerFeature {
  feature_id: number
  chromosome: string
  start: number
  end: number
  repeat_name: string
  repeat_class: string   // LINE, SINE, LTR, DNA, Simple_repeat, Low_complexity, etc.
  repeat_family: string  // L1, Alu, MIR, etc.
  divergence: number     // 0-50, percentage divergence from consensus
  strand?: string        // '+', '-', or '.'
}

/**
 * RepeatMasker Query Parameters
 */
export interface RepeatMaskerFilters {
  repeat_class?: string
  repeat_family?: string
  min_divergence?: number
  max_divergence?: number
  page?: number
  page_size?: number
}

/**
 * RepeatMasker Paginated Response
 */
export interface RepeatMaskerResponse {
  total: number
  items: RepeatMaskerFeature[]
  page: number
  page_size: number
}

/**
 * RepeatMasker Statistics
 */
export interface RepeatStats {
  total_count: number
  class_distribution: Record<string, number>  // e.g., {'LINE': 123, 'SINE': 456}
  family_distribution: Record<string, number> // e.g., {'L1': 100, 'Alu': 200}
  avg_divergence: number
}

/**
 * Feature Track Configuration (for future extension)
 */
export interface FeatureTrack {
  track_id: number
  track_name: string
  track_category: 'repeat' | 'epigenetic' | 'conservation'
  display_name: string
  display_color: string
  is_active: boolean
}

/**
 * Repeat Class Options for filtering
 */
export const REPEAT_CLASSES: Array<{ value: string; label: string }> = [
  { value: 'LINE', label: 'LINE' },
  { value: 'SINE', label: 'SINE' },
  { value: 'LTR', label: 'LTR' },
  { value: 'DNA', label: 'DNA' },
  { value: 'Simple_repeat', label: 'Simple Repeat' },
  { value: 'Low_complexity', label: 'Low Complexity' },
  { value: 'Satellite', label: 'Satellite' },
  { value: 'RNA', label: 'RNA' },
  { value: 'RC', label: 'Rolling Circle' },
  { value: 'Unknown', label: 'Unknown' },
]

/**
 * Color mapping for repeat classes (for visualization)
 */
export const REPEAT_CLASS_COLORS: Record<string, string> = {
  LINE: '#E74C3C',        // Red
  SINE: '#3498DB',        // Blue
  LTR: '#2ECC71',         // Green
  DNA: '#9B59B6',         // Purple
  Simple_repeat: '#F39C12', // Orange
  Low_complexity: '#1ABC9C', // Teal
  Satellite: '#E91E63',   // Pink
  RNA: '#00BCD4',         // Cyan
  RC: '#795548',          // Brown
  Unknown: '#95A5A6',     // Gray
}
