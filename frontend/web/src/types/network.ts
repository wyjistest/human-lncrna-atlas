/**
 * 网络可视化相关类型定义
 */

export interface GeneDetail {
  gene_id: number
  gene_name: string
  gene_ensembl_id: string
  gene_type: 'lncRNA' | 'protein_coding'
  species_id: number
  species_name: string
  chromosome: string | null
  gene_start: number | null
  gene_end: number | null
  strand: string | null
  core_id: number
  conservation_label: string  // 保守性标签，如 "1000" 表示只在人类中存在
  conservation_count: number  // 保守物种数量
  connections: {
    as_source: number
    as_target: number
    total: number
    total_ba: number
  }
}

export interface NetworkNode {
  id: string
  label: string
  type: 'lncRNA' | 'protein_coding'
  gene_id: number
  core_id: number
}

export interface NetworkEdge {
  source: string
  target: string
  binding_affinity: number
  regulation_id: number
}

export interface NetworkData {
  nodes: NetworkNode[]
  edges: NetworkEdge[]
  stats: {
    total_nodes: number
    total_edges: number
    lncrna_count: number
    protein_coding_count: number
    trait_name?: string
    ontology_name?: string
  }
}

/**
 * Cross-species comparison types
 */
export interface CompareParams {
  min_ba?: number
  max_targets_per_species?: number
}

export interface SpeciesTargetGene {
  target_gene_id: number
  target_name: string | null
  target_core_id: number
  binding_affinity: number | null
}

export interface SpeciesNetworkData {
  lncrna_gene_id: number
  species_id: number
  target_count: number
  total_target_count: number
  truncated: boolean
  targets: SpeciesTargetGene[]
}

export interface SpeciesNetworkComparison {
  lncrna_core_id: number
  species_networks: Record<number, SpeciesNetworkData>
  conserved_target_count: number
  conserved_targets: number[]
}

export interface AvailableCombination {
  trait_id: number
  ontology_id: number
  species_id: number
}

export interface AvailableCombinationsResponse {
  combinations: AvailableCombination[]
}

export interface DiseaseNetworkParams {
  trait_id: number
  ontology_id: number
  species_id?: number
  min_ba?: number
  max_nodes?: number
  max_edges?: number
}
