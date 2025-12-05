/**
 * Conservation Types and Utilities
 * Phase 2.2.1 - Conservation Visualization MVP
 *
 * Uses Tol Bright color-blind safe palette for conservation tiers
 */

/**
 * Conservation category/tier based on species count
 */
export type ConservationCategory = 'high' | 'medium' | 'low' | 'unknown'

/**
 * Conservation data structure for a gene
 */
export interface ConservationData {
  /** Conservation label as 4-character binary string (e.g., "1100" = Human + Chimpanzee) */
  label: string
  /** Number of species where the gene is conserved (0-4) */
  count: number
  /** Parsed species presence */
  species: {
    human: boolean
    chimpanzee: boolean
    macaque: boolean
    marmoset: boolean
  }
  /** Calculated conservation category */
  category: ConservationCategory
}

/**
 * Tol Bright color palette - color-blind safe
 * https://personal.sron.nl/~pault/
 */
export const CONSERVATION_COLORS: Record<ConservationCategory, string> = {
  high: '#228833',     // Green - 4 species
  medium: '#CCBB44',   // Yellow - 2-3 species
  low: '#EE6677',      // Red - 1 species
  unknown: '#BBBBBB'   // Gray - 0 or unknown
} as const

/**
 * Species indices in conservation label string
 * Position 0: Human, Position 1: Chimpanzee, Position 2: Macaque, Position 3: Marmoset
 */
export const SPECIES_INDICES = {
  human: 0,
  chimpanzee: 1,
  macaque: 2,
  marmoset: 3
} as const

/**
 * Get conservation category from species count
 * @param count Number of species (0-4)
 * @returns Conservation category
 */
export function getConservationCategory(count: number): ConservationCategory {
  if (count >= 4) return 'high'
  if (count >= 2) return 'medium'
  if (count === 1) return 'low'
  return 'unknown'
}

/**
 * Parse conservation label string into structured data
 * @param label Conservation label (e.g., "1100", "1111", "0000")
 * @param count Optional pre-computed count, will be calculated from label if not provided
 * @returns Parsed conservation data
 */
export function parseConservationLabel(
  label?: string | null,
  count?: number
): ConservationData {
  // Default to "0000" if label is missing or invalid
  const normalizedLabel = (label && label.length === 4) ? label : '0000'

  // Parse species presence from label
  const species = {
    human: normalizedLabel[SPECIES_INDICES.human] === '1',
    chimpanzee: normalizedLabel[SPECIES_INDICES.chimpanzee] === '1',
    macaque: normalizedLabel[SPECIES_INDICES.macaque] === '1',
    marmoset: normalizedLabel[SPECIES_INDICES.marmoset] === '1'
  }

  // Calculate count from label if not provided
  const speciesCount = count ?? Object.values(species).filter(Boolean).length

  // Determine category
  const category = getConservationCategory(speciesCount)

  return {
    label: normalizedLabel,
    count: speciesCount,
    species,
    category
  }
}

/**
 * Get display text for conservation tier
 * @param category Conservation category
 * @param count Species count
 * @returns Formatted display string (e.g., "High (4/4)")
 */
export function getConservationDisplayText(
  category: ConservationCategory,
  count: number
): string {
  const categoryText = category.charAt(0).toUpperCase() + category.slice(1)
  if (category === 'unknown') {
    return categoryText
  }
  return `${categoryText} (${count}/4)`
}
