/**
 * Query Key Factory
 * 集中管理所有 TanStack Query 的 query keys
 * 便于缓存管理和一致性的缓存失效
 */

// 基础 query keys
export const queryKeys = {
  // Genes
  genes: {
    all: ['genes'] as const,
    lists: () => [...queryKeys.genes.all, 'list'] as const,
    list: (params: Record<string, unknown>) => [...queryKeys.genes.lists(), params] as const,
    details: () => [...queryKeys.genes.all, 'detail'] as const,
    detail: (id: number) => [...queryKeys.genes.details(), id] as const,
    regulations: (geneId: number, params?: Record<string, unknown>) =>
      [...queryKeys.genes.detail(geneId), 'regulations', params] as const,
  },

  // Regulations
  regulations: {
    all: ['regulations'] as const,
    lists: () => [...queryKeys.regulations.all, 'list'] as const,
    list: (params: Record<string, unknown>) => [...queryKeys.regulations.lists(), params] as const,
    details: () => [...queryKeys.regulations.all, 'detail'] as const,
    detail: (id: number) => [...queryKeys.regulations.details(), id] as const,
  },

  // Diseases (Traits)
  diseases: {
    all: ['diseases'] as const,
    lists: () => [...queryKeys.diseases.all, 'list'] as const,
    list: (params: Record<string, unknown>) => [...queryKeys.diseases.lists(), params] as const,
    details: () => [...queryKeys.diseases.all, 'detail'] as const,
    detail: (id: number) => [...queryKeys.diseases.details(), id] as const,
    genes: (traitId: number, params?: Record<string, unknown>) =>
      [...queryKeys.diseases.detail(traitId), 'genes', params] as const,
  },

  // Stats
  stats: {
    all: ['stats'] as const,
    overview: () => [...queryKeys.stats.all, 'overview'] as const,
    detailed: (params?: Record<string, unknown>) => [...queryKeys.stats.all, 'detailed', params] as const,
    baRange: () => [...queryKeys.stats.all, 'ba-range'] as const,
    topGenes: (params?: Record<string, unknown>) => [...queryKeys.stats.all, 'top-genes', params] as const,
    topDiseases: (params?: Record<string, unknown>) => [...queryKeys.stats.all, 'top-diseases', params] as const,
  },

  // Network
  network: {
    all: ['network'] as const,
    gene: (geneId: number, params?: Record<string, unknown>) =>
      [...queryKeys.network.all, 'gene', geneId, params] as const,
    geneDetail: (geneId: number) => [...queryKeys.network.all, 'gene-detail', geneId] as const,
  },

  // Species (for filters)
  species: {
    all: ['species'] as const,
    list: () => [...queryKeys.species.all, 'list'] as const,
  },
} as const

// 类型导出，方便在其他地方使用
export type QueryKeys = typeof queryKeys
