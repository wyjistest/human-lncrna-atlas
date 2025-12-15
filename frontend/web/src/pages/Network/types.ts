import type { Core } from 'cytoscape'
import type { NetworkData } from '@/types/network'

/**
 * Species ID to translation key mapping
 */
export const SPECIES_KEYS: Record<number, string> = {
  1: 'human',
  2: 'chimpanzee',
  3: 'macaque',
  4: 'marmoset'
}

/**
 * Species ID to English name mapping (used for file names, immutable)
 */
export const SPECIES_EN_NAMES: Record<number, string> = {
  1: 'Human',
  2: 'Chimpanzee',
  3: 'Macaque',
  4: 'Marmoset'
}

/**
 * NetworkCard component props
 */
export interface NetworkCardProps {
  speciesId: number
  speciesName: string
  data: NetworkData | null
  loading: boolean
  error: Error | null
  onRefReady?: (cyRef: React.RefObject<Core>, isReady: boolean) => void
  lncrnaCoreId?: number  // For cross-species comparison
  lncrnaGeneId?: number  // For cross-species comparison
}

/**
 * Network card reference data for batch export
 */
export interface NetworkCardRef {
  cyRef: React.RefObject<Core>
  data: NetworkData | null
  speciesName: string
  isReady: boolean
}
