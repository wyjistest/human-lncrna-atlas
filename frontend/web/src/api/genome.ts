/**
 * Genome Browser API client
 * Provides methods for fetching IGV.js configuration and genome data
 */
import { apiClient } from './client'

export interface IGVTrackConfig {
  name: string
  type: string
  format: string
  url: string
  indexURL?: string
  displayMode?: string
  color?: string
  height?: number
  visibilityWindow?: number
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

export const genomeApi = {
  /**
   * Get IGV configuration for a specific species
   * @param speciesId - Species ID (1: Human, 2: Chimpanzee, 3: Macaque, 4: Marmoset)
   */
  getIGVConfig: (speciesId: number) =>
    apiClient.get<IGVConfig>(`/api/v1/igv/config/${speciesId}`),

  /**
   * Get IGV configuration for a specific gene
   * Auto-locates to the gene position and loads only its regulations
   * @param geneName - Gene name (e.g., CATG00000000011.1)
   * @param padding - Padding around gene (default 50kb)
   */
  getIGVConfigForGene: (geneName: string, padding?: number) =>
    apiClient.get<IGVConfig>(`/api/v1/igv/config/gene/${encodeURIComponent(geneName)}`, {
      params: padding !== undefined ? { padding } : undefined
    }),

  /**
   * Search for a gene by name
   * @param speciesId - Species ID
   * @param query - Gene name or Ensembl ID to search
   */
  searchGene: (speciesId: number, query: string) =>
    apiClient.get<GenomeSearchResult[]>('/api/v1/igv/search', {
      params: { species_id: speciesId, query }
    }),
}
