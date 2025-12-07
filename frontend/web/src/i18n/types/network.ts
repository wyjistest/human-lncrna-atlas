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
