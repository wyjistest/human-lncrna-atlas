/**
 * Cell Type Configuration
 * Centralized configuration for all supported cell types/lines
 *
 * This file contains all cell type configurations including:
 * - Display properties (colors, labels)
 * - Category classification (cancer, normal, stem)
 * - Bilingual support (English and Chinese)
 */

export type CellTypeCategory = 'cancer' | 'normal' | 'stem'

export interface CellTypeConfig {
  value: string
  label: string
  labelZh: string
  color: string
  category: CellTypeCategory
  description?: string
  descriptionZh?: string
}

/**
 * Complete cell type configurations for all supported cell lines
 */
export const CELL_TYPE_CONFIGS: Record<string, CellTypeConfig> = {
  'K562': {
    value: 'K562',
    label: 'K562 (Leukemia)',
    labelZh: 'K562 (白血病细胞)',
    color: '#E74C3C',
    category: 'cancer',
    description: 'Chronic myelogenous leukemia cell line',
    descriptionZh: '慢性髓系白血病细胞系'
  },
  'GM12878': {
    value: 'GM12878',
    label: 'GM12878 (B-lymphocyte)',
    labelZh: 'GM12878 (B淋巴细胞)',
    color: '#3498DB',
    category: 'normal',
    description: 'Lymphoblastoid cell line',
    descriptionZh: '淋巴母细胞系'
  },
  'HepG2': {
    value: 'HepG2',
    label: 'HepG2 (Hepatocellular carcinoma)',
    labelZh: 'HepG2 (肝癌细胞)',
    color: '#27AE60',
    category: 'cancer',
    description: 'Hepatocellular carcinoma cell line',
    descriptionZh: '肝细胞癌细胞系'
  },
  'H1-hESC': {
    value: 'H1-hESC',
    label: 'H1-hESC (Embryonic stem cell)',
    labelZh: 'H1-hESC (人胚胎干细胞)',
    color: '#9B59B6',
    category: 'stem',
    description: 'Human embryonic stem cell line',
    descriptionZh: '人胚胎干细胞系'
  },
  'MCF-7': {
    value: 'MCF-7',
    label: 'MCF-7 (Breast cancer)',
    labelZh: 'MCF-7 (乳腺癌细胞)',
    color: '#FF69B4',
    category: 'cancer',
    description: 'Breast adenocarcinoma cell line',
    descriptionZh: '乳腺腺癌细胞系'
  },
  'HMEC': {
    value: 'HMEC',
    label: 'HMEC (Mammary epithelial)',
    labelZh: 'HMEC (乳腺上皮细胞)',
    color: '#DEB887',
    category: 'normal',
    description: 'Human mammary epithelial cells',
    descriptionZh: '人类乳腺上皮细胞'
  },
  'A549': {
    value: 'A549',
    label: 'A549 (Lung cancer)',
    labelZh: 'A549 (肺癌细胞)',
    color: '#17A2B8',
    category: 'cancer',
    description: 'Lung adenocarcinoma cell line',
    descriptionZh: '肺腺癌细胞系'
  }
}

/**
 * Category configurations for grouping cell types in UI
 */
export const CELL_CATEGORY_CONFIGS: Record<CellTypeCategory, {
  displayName: string
  displayNameZh: string
  color: string
  description: string
}> = {
  cancer: {
    displayName: 'Cancer Cell Lines',
    displayNameZh: '癌症细胞系',
    color: '#E74C3C',
    description: 'Cell lines derived from cancer tissues'
  },
  normal: {
    displayName: 'Normal Cell Lines',
    displayNameZh: '正常细胞系',
    color: '#3498DB',
    description: 'Cell lines derived from normal tissues'
  },
  stem: {
    displayName: 'Stem Cell Lines',
    displayNameZh: '干细胞系',
    color: '#9B59B6',
    description: 'Embryonic and induced pluripotent stem cell lines'
  }
}

/**
 * Get cell type options for Select component
 * @param locale - Current locale ('en' or 'zh-CN')
 * @returns Array of options for Select component
 */
export function getCellTypeOptions(locale: string = 'en'): Array<{ value: string; label: string }> {
  return Object.values(CELL_TYPE_CONFIGS).map(config => ({
    value: config.value,
    label: locale === 'zh-CN' ? config.labelZh : config.label
  }))
}

/**
 * Get cell type configuration by cell type value
 * @param cellType - Cell type value (e.g., 'K562', 'GM12878')
 * @returns Cell type configuration or undefined
 */
export function getCellTypeConfig(cellType: string): CellTypeConfig | undefined {
  return CELL_TYPE_CONFIGS[cellType]
}

/**
 * Get color by cell type
 * @param cellType - Cell type value
 * @returns Color hex code or default gray
 */
export function getCellTypeColor(cellType: string): string {
  return CELL_TYPE_CONFIGS[cellType]?.color || '#999999'
}

/**
 * Get cell type label for display
 * @param cellType - Cell type value
 * @param locale - Current locale
 * @returns Localized label or the original value
 */
export function getCellTypeLabel(cellType: string, locale: string = 'en'): string {
  const config = CELL_TYPE_CONFIGS[cellType]
  if (!config) return cellType
  return locale === 'zh-CN' ? config.labelZh : config.label
}

/**
 * Get all cell types of a specific category
 * @param category - Category type
 * @returns Array of cell type values
 */
export function getCellTypesByCategory(category: CellTypeCategory): string[] {
  return Object.entries(CELL_TYPE_CONFIGS)
    .filter(([_, config]) => config.category === category)
    .map(([key]) => key)
}

/**
 * Get all supported cell type values
 * @returns Array of cell type values
 */
export function getAllCellTypes(): string[] {
  return Object.keys(CELL_TYPE_CONFIGS)
}
