/**
 * ChIP-seq Mark Configurations
 * Phase 2.2 - Complete configuration for 15+ histone modification marks
 *
 * This file contains all mark-specific configurations including:
 * - Display properties (colors, icons, names)
 * - Default filter values
 * - Categorization for UI grouping
 */

import type { MarkType, MarkConfig, MarkCategory } from '@/types/chipseq'

/**
 * Complete mark configurations for all supported ChIP-seq marks
 */
export const MARK_CONFIGS: Record<MarkType, MarkConfig> = {
  // ============================================
  // REPRESSIVE MARKS
  // ============================================
  H3K27me3: {
    displayName: 'H3K27me3 (Repressive)',
    shortName: 'K27me3',
    color: '#9B59B6',
    secondaryColor: '#E8DAEF',
    category: 'repressive',
    description: 'Polycomb repressive mark - silences developmental genes',
    icon: 'stop',
    isCommon: true,
    sortOrder: 1,
    defaultFilters: {
      min_fold_enrichment: 5,
      max_qvalue: 0.01,
      flanking: 10000,
    },
  },

  H3K9me3: {
    displayName: 'H3K9me3 (Heterochromatin)',
    shortName: 'K9me3',
    color: '#8E44AD',
    secondaryColor: '#D7BDE2',
    category: 'repressive',
    description: 'Constitutive heterochromatin mark - silences repetitive elements',
    icon: 'lock',
    isCommon: true,
    sortOrder: 2,
    defaultFilters: {
      min_fold_enrichment: 4,
      max_qvalue: 0.01,
      flanking: 10000,
    },
  },

  H3K9me2: {
    displayName: 'H3K9me2 (Silencing)',
    shortName: 'K9me2',
    color: '#7D3C98',
    secondaryColor: '#D2B4DE',
    category: 'repressive',
    description: 'Facultative heterochromatin - weaker silencing mark',
    icon: 'lock',
    isCommon: false,
    sortOrder: 3,
    defaultFilters: {
      min_fold_enrichment: 3,
      max_qvalue: 0.05,
      flanking: 10000,
    },
  },

  // ============================================
  // ACTIVATING MARKS - PROMOTER
  // ============================================
  H3K4me3: {
    displayName: 'H3K4me3 (Active Promoter)',
    shortName: 'K4me3',
    color: '#27AE60',
    secondaryColor: '#D5F5E3',
    category: 'activating',
    description: 'Active promoter mark - marks transcription start sites',
    icon: 'check-circle',
    isCommon: true,
    sortOrder: 4,
    defaultFilters: {
      min_fold_enrichment: 5,
      max_qvalue: 0.01,
      flanking: 5000,
    },
  },

  H3K4me2: {
    displayName: 'H3K4me2 (Promoter)',
    shortName: 'K4me2',
    color: '#2ECC71',
    secondaryColor: '#ABEBC6',
    category: 'activating',
    description: 'Promoter-associated mark - weaker than H3K4me3',
    icon: 'check',
    isCommon: false,
    sortOrder: 5,
    defaultFilters: {
      min_fold_enrichment: 3,
      max_qvalue: 0.05,
      flanking: 5000,
    },
  },

  // ============================================
  // ACTIVATING MARKS - ENHANCER
  // ============================================
  H3K4me1: {
    displayName: 'H3K4me1 (Enhancer)',
    shortName: 'K4me1',
    color: '#F39C12',
    secondaryColor: '#FCF3CF',
    category: 'enhancer',
    description: 'Enhancer mark - marks poised and active enhancers',
    icon: 'star',
    isCommon: true,
    sortOrder: 6,
    defaultFilters: {
      min_fold_enrichment: 3,
      max_qvalue: 0.05,
      flanking: 50000,
    },
  },

  H3K27ac: {
    displayName: 'H3K27ac (Active Enhancer)',
    shortName: 'K27ac',
    color: '#E67E22',
    secondaryColor: '#FAD7A0',
    category: 'enhancer',
    description: 'Active enhancer mark - distinguishes active from poised enhancers',
    icon: 'star',
    isCommon: true,
    sortOrder: 7,
    defaultFilters: {
      min_fold_enrichment: 4,
      max_qvalue: 0.01,
      flanking: 50000,
    },
  },

  H3K9ac: {
    displayName: 'H3K9ac (Active Chromatin)',
    shortName: 'K9ac',
    color: '#D35400',
    secondaryColor: '#F6DDCC',
    category: 'activating',
    description: 'Active chromatin mark - associated with transcription activation',
    icon: 'bulb',
    isCommon: false,
    sortOrder: 8,
    defaultFilters: {
      min_fold_enrichment: 3,
      max_qvalue: 0.05,
      flanking: 10000,
    },
  },

  // ============================================
  // ELONGATION MARKS
  // ============================================
  H3K36me3: {
    displayName: 'H3K36me3 (Elongation)',
    shortName: 'K36me3',
    color: '#3498DB',
    secondaryColor: '#D4E6F1',
    category: 'elongation',
    description: 'Transcription elongation mark - marks gene bodies of active genes',
    icon: 'arrow-right',
    isCommon: true,
    sortOrder: 9,
    defaultFilters: {
      min_fold_enrichment: 3,
      max_qvalue: 0.05,
      flanking: 10000,
    },
  },

  H3K79me2: {
    displayName: 'H3K79me2 (Elongation)',
    shortName: 'K79me2',
    color: '#2980B9',
    secondaryColor: '#AED6F1',
    category: 'elongation',
    description: 'Transcription elongation - DOT1L mediated',
    icon: 'arrow-right',
    isCommon: false,
    sortOrder: 10,
    defaultFilters: {
      min_fold_enrichment: 3,
      max_qvalue: 0.05,
      flanking: 10000,
    },
  },

  // ============================================
  // OTHER MARKS
  // ============================================
  H2AZ: {
    displayName: 'H2A.Z (Regulatory)',
    shortName: 'H2AZ',
    color: '#16A085',
    secondaryColor: '#D1F2EB',
    category: 'other',
    description: 'Histone variant - marks regulatory regions and poised promoters',
    icon: 'setting',
    isCommon: false,
    sortOrder: 11,
    defaultFilters: {
      min_fold_enrichment: 3,
      max_qvalue: 0.05,
      flanking: 10000,
    },
  },

  H2BK120ub: {
    displayName: 'H2BK120ub (Ubiquitination)',
    shortName: 'K120ub',
    color: '#1ABC9C',
    secondaryColor: '#A3E4D7',
    category: 'other',
    description: 'Ubiquitination mark - associated with transcription elongation',
    icon: 'tag',
    isCommon: false,
    sortOrder: 12,
    defaultFilters: {
      min_fold_enrichment: 2,
      max_qvalue: 0.05,
      flanking: 10000,
    },
  },

  H4K20me1: {
    displayName: 'H4K20me1 (Cell Cycle)',
    shortName: 'H4K20me1',
    color: '#34495E',
    secondaryColor: '#D5D8DC',
    category: 'other',
    description: 'Cell cycle regulation - associated with replication and transcription',
    icon: 'sync',
    isCommon: false,
    sortOrder: 13,
    defaultFilters: {
      min_fold_enrichment: 2,
      max_qvalue: 0.05,
      flanking: 10000,
    },
  },

  H3K4ac: {
    displayName: 'H3K4ac (Active)',
    shortName: 'K4ac',
    color: '#52C41A',
    secondaryColor: '#D9F7BE',
    category: 'activating',
    description: 'Active chromatin acetylation mark',
    icon: 'bulb',
    isCommon: false,
    sortOrder: 14,
    defaultFilters: {
      min_fold_enrichment: 3,
      max_qvalue: 0.05,
      flanking: 10000,
    },
  },

  H3K14ac: {
    displayName: 'H3K14ac (Active)',
    shortName: 'K14ac',
    color: '#73D13D',
    secondaryColor: '#B7EB8F',
    category: 'activating',
    description: 'Active chromatin acetylation - transcription activation',
    icon: 'bulb',
    isCommon: false,
    sortOrder: 15,
    defaultFilters: {
      min_fold_enrichment: 3,
      max_qvalue: 0.05,
      flanking: 10000,
    },
  },

  H3K18ac: {
    displayName: 'H3K18ac (Active)',
    shortName: 'K18ac',
    color: '#95DE64',
    secondaryColor: '#D9F7BE',
    category: 'activating',
    description: 'Active chromatin acetylation - associated with active transcription',
    icon: 'bulb',
    isCommon: false,
    sortOrder: 16,
    defaultFilters: {
      min_fold_enrichment: 3,
      max_qvalue: 0.05,
      flanking: 10000,
    },
  },
}

/**
 * Category configurations for grouping marks in UI
 */
export const CATEGORY_CONFIGS: Record<MarkCategory, {
  displayName: string
  color: string
  description: string
  icon: string
}> = {
  repressive: {
    displayName: 'Repressive Marks',
    color: '#9B59B6',
    description: 'Marks associated with gene silencing and heterochromatin',
    icon: 'stop',
  },
  activating: {
    displayName: 'Activating Marks',
    color: '#27AE60',
    description: 'Marks associated with active promoters and transcription',
    icon: 'check-circle',
  },
  enhancer: {
    displayName: 'Enhancer Marks',
    color: '#F39C12',
    description: 'Marks associated with enhancer elements',
    icon: 'star',
  },
  elongation: {
    displayName: 'Elongation Marks',
    color: '#3498DB',
    description: 'Marks associated with transcription elongation',
    icon: 'arrow-right',
  },
  other: {
    displayName: 'Other Marks',
    color: '#95A5A6',
    description: 'Other histone modifications and variants',
    icon: 'tag',
  },
}

/**
 * Get mark configuration by mark type
 */
export function getMarkConfig(markType: MarkType): MarkConfig {
  return MARK_CONFIGS[markType]
}

/**
 * Get category configuration by category type
 */
export function getCategoryConfig(category: MarkCategory) {
  return CATEGORY_CONFIGS[category]
}

/**
 * Get all marks of a specific category
 */
export function getMarksByCategory(category: MarkCategory): MarkType[] {
  return (Object.entries(MARK_CONFIGS) as [MarkType, MarkConfig][])
    .filter(([_, config]) => config.category === category)
    .sort((a, b) => a[1].sortOrder - b[1].sortOrder)
    .map(([type]) => type)
}

/**
 * Get commonly used marks (for quick selection)
 */
export function getCommonMarks(): MarkType[] {
  return (Object.entries(MARK_CONFIGS) as [MarkType, MarkConfig][])
    .filter(([_, config]) => config.isCommon)
    .sort((a, b) => a[1].sortOrder - b[1].sortOrder)
    .map(([type]) => type)
}

/**
 * Get all mark types sorted by category and priority
 */
export function getAllMarkTypes(): MarkType[] {
  return (Object.entries(MARK_CONFIGS) as [MarkType, MarkConfig][])
    .sort((a, b) => a[1].sortOrder - b[1].sortOrder)
    .map(([type]) => type)
}

/**
 * Get marks grouped by category (for select dropdown)
 */
export function getMarksGroupedByCategory(): Array<{
  category: MarkCategory
  categoryName: string
  marks: Array<{ value: MarkType; label: string; color: string }>
}> {
  const categories: MarkCategory[] = ['repressive', 'activating', 'enhancer', 'elongation', 'other']

  return categories.map((category) => ({
    category,
    categoryName: CATEGORY_CONFIGS[category].displayName,
    marks: getMarksByCategory(category).map((markType) => ({
      value: markType,
      label: MARK_CONFIGS[markType].displayName,
      color: MARK_CONFIGS[markType].color,
    })),
  }))
}

/**
 * Get color for a mark type
 */
export function getMarkColor(markType: MarkType): string {
  return MARK_CONFIGS[markType]?.color || '#95A5A6'
}

/**
 * Get secondary color for a mark type (for backgrounds)
 */
export function getMarkSecondaryColor(markType: MarkType): string {
  return MARK_CONFIGS[markType]?.secondaryColor || '#D5D8DC'
}

/**
 * Check if a mark is a repressive mark
 */
export function isRepressiveMark(markType: MarkType): boolean {
  return MARK_CONFIGS[markType]?.category === 'repressive'
}

/**
 * Check if a mark is an activating/enhancer mark
 */
export function isActivatingMark(markType: MarkType): boolean {
  const category = MARK_CONFIGS[markType]?.category
  return category === 'activating' || category === 'enhancer'
}
