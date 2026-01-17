/**
 * Export Utility Functions
 *
 * Provides utilities for exporting genomic data to various formats.
 * Phase 2.1: Added BED format export for RepeatMasker and other genomic features.
 */

import { saveAs } from 'file-saver'

/**
 * Feature interface for BED export
 */
interface BEDFeature {
  chromosome: string
  start: number
  end: number
  name?: string
  score?: number
  strand?: string
  thickStart?: number
  thickEnd?: number
  itemRgb?: string
  blockCount?: number
  blockSizes?: number[]
  blockStarts?: number[]
}

/**
 * Export options for BED files
 */
interface BEDExportOptions {
  /** Number of BED columns (3-12), default 6 */
  columns?: 3 | 4 | 5 | 6 | 9 | 12
  /** Track name for UCSC browser */
  trackName?: string
  /** Track description */
  description?: string
  /** Include header line */
  includeHeader?: boolean
  /** Default score if not provided (0-1000) */
  defaultScore?: number
  /** Default strand if not provided */
  defaultStrand?: string
}

/**
 * Sanitize string for BED format
 * BED format doesn't allow spaces or special characters in certain fields
 */
const sanitizeBEDField = (value: string | undefined | null): string => {
  if (!value) return '.'
  // Replace spaces and tabs with underscores
  return value.replace(/[\s\t]/g, '_')
}

/**
 * Validate chromosome format
 * Accepts chr1, chr2, chrX, chrY, chrM, chrMT formats
 */
const validateChromosome = (chr: string): string => {
  if (!chr) return 'chrUn'
  // Ensure chromosome starts with 'chr'
  if (!chr.toLowerCase().startsWith('chr')) {
    return `chr${chr}`
  }
  return chr
}

/**
 * Clamp score to valid BED range (0-1000)
 */
const clampScore = (score: number | undefined | null, defaultValue: number = 0): number => {
  if (score === undefined || score === null) return defaultValue
  return Math.max(0, Math.min(1000, Math.round(score)))
}

/**
 * Export features to BED format
 *
 * BED format specification:
 * - Column 1: chromosome (required)
 * - Column 2: chromStart (required, 0-based)
 * - Column 3: chromEnd (required)
 * - Column 4: name (optional)
 * - Column 5: score (optional, 0-1000)
 * - Column 6: strand (optional, +, -, or .)
 *
 * @param features - Array of features to export
 * @param filename - Output filename (without extension)
 * @param options - Export options
 */
export const exportToBED = (
  features: BEDFeature[],
  filename: string,
  options: BEDExportOptions = {}
): void => {
  const {
    columns = 6,
    trackName,
    description,
    includeHeader = true,
    defaultScore = 0,
    defaultStrand = '.'
  } = options

  const lines: string[] = []

  // Add track header line if specified
  if (includeHeader && (trackName || description)) {
    const headerParts = ['track']
    if (trackName) headerParts.push(`name="${sanitizeBEDField(trackName)}"`)
    if (description) headerParts.push(`description="${description}"`)
    lines.push(headerParts.join(' '))
  }

  // Convert features to BED lines
  for (const feature of features) {
    const chr = validateChromosome(feature.chromosome)
    // BED format uses 0-based start coordinates
    const start = Math.max(0, feature.start - 1) // Convert from 1-based to 0-based
    const end = feature.end
    const name = sanitizeBEDField(feature.name) || 'feature'
    const score = clampScore(feature.score, defaultScore)
    const strand = feature.strand || defaultStrand

    let line: string

    switch (columns) {
      case 3:
        line = [chr, start, end].join('\t')
        break
      case 4:
        line = [chr, start, end, name].join('\t')
        break
      case 5:
        line = [chr, start, end, name, score].join('\t')
        break
      case 6:
      default:
        line = [chr, start, end, name, score, strand].join('\t')
        break
      case 9:
        line = [
          chr,
          start,
          end,
          name,
          score,
          strand,
          feature.thickStart ?? start,
          feature.thickEnd ?? end,
          feature.itemRgb || '0'
        ].join('\t')
        break
      case 12:
        line = [
          chr,
          start,
          end,
          name,
          score,
          strand,
          feature.thickStart ?? start,
          feature.thickEnd ?? end,
          feature.itemRgb || '0',
          feature.blockCount ?? 1,
          feature.blockSizes?.join(',') ?? (end - start).toString(),
          feature.blockStarts?.join(',') ?? '0'
        ].join('\t')
        break
    }

    lines.push(line)
  }

  // Join lines and create blob
  const bedContent = lines.join('\n')
  const blob = new Blob([bedContent], { type: 'text/plain;charset=utf-8' })

  // Download file
  saveAs(blob, `${filename}.bed`)
}

/**
 * Export RepeatMasker features to BED format
 * Specialized function for RepeatMasker data
 */
export const exportRepeatMaskerToBED = (
  features: Array<{
    chromosome: string
    start: number
    end: number
    repeat_name: string
    repeat_class: string
    repeat_family: string
    divergence: number
    strand?: string
  }>,
  filename: string = 'repeatmasker_export'
): void => {
  // Convert RepeatMasker features to BED format
  // Use repeat_name as name, divergence*10 as score (normalized to 0-1000)
  const bedFeatures: BEDFeature[] = features.map(f => ({
    chromosome: f.chromosome,
    start: f.start,
    end: f.end,
    // Combine repeat info into name field
    name: `${f.repeat_name}|${f.repeat_class}|${f.repeat_family}`,
    // Convert divergence (0-50%) to score (0-500, inverted so lower divergence = higher score)
    score: Math.round((50 - f.divergence) * 20),
    strand: f.strand || '.'
  }))

  exportToBED(bedFeatures, filename, {
    columns: 6,
    trackName: 'RepeatMasker',
    description: 'RepeatMasker repeat elements export',
    includeHeader: true
  })
}

/**
 * Generate timestamp string for filenames
 */
export const generateExportTimestamp = (): string => {
  return new Date().toISOString().slice(0, 19).replace(/[:-]/g, '').replace('T', '_')
}

/**
 * Create filename with timestamp
 */
export const createTimestampedFilename = (prefix: string): string => {
  return `${prefix}_${generateExportTimestamp()}`
}
