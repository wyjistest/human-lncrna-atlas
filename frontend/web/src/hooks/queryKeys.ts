/**
 * Query Key Factory
 * 集中管理所有 TanStack Query 的 query keys
 * 便于缓存管理和一致性的缓存失效
 */

import { normalizeQueryKeyObject } from '@/utils/queryKey'

// 基础 query keys
export const queryKeys = {
  // Genes
  genes: {
    all: ['genes'] as const,
    lists: () => [...queryKeys.genes.all, 'list'] as const,
    list: (params?: unknown) => {
      const normalized = normalizeQueryKeyObject(params)
      return normalized ? ([...queryKeys.genes.lists(), normalized] as const) : queryKeys.genes.lists()
    },
    details: () => [...queryKeys.genes.all, 'detail'] as const,
    detail: (id: number) => [...queryKeys.genes.details(), id] as const,
    regulations: (geneId: number, params?: unknown) => {
      const normalized = normalizeQueryKeyObject(params)
      return normalized
        ? ([...queryKeys.genes.detail(geneId), 'regulations', normalized] as const)
        : ([...queryKeys.genes.detail(geneId), 'regulations'] as const)
    },
    diseases: (geneId: number) => [...queryKeys.genes.detail(geneId), 'diseases'] as const,
    orthologs: (geneId: number) => [...queryKeys.genes.detail(geneId), 'orthologs'] as const,
  },

  // Regulations
  regulations: {
    all: ['regulations'] as const,
    lists: () => [...queryKeys.regulations.all, 'list'] as const,
    list: (params?: unknown) => {
      const normalized = normalizeQueryKeyObject(params)
      return normalized ? ([...queryKeys.regulations.lists(), normalized] as const) : queryKeys.regulations.lists()
    },
    details: () => [...queryKeys.regulations.all, 'detail'] as const,
    detail: (id: number) => [...queryKeys.regulations.details(), id] as const,
  },

  // Diseases (Traits)
  diseases: {
    all: ['diseases'] as const,
    lists: () => [...queryKeys.diseases.all, 'list'] as const,
    list: (params?: unknown) => {
      const normalized = normalizeQueryKeyObject(params)
      return normalized ? ([...queryKeys.diseases.lists(), normalized] as const) : queryKeys.diseases.lists()
    },
    details: () => [...queryKeys.diseases.all, 'detail'] as const,
    detail: (id: number) => [...queryKeys.diseases.details(), id] as const,
    genes: (traitId: number, params?: unknown) => {
      const normalized = normalizeQueryKeyObject(params)
      return normalized
        ? ([...queryKeys.diseases.detail(traitId), 'genes', normalized] as const)
        : ([...queryKeys.diseases.detail(traitId), 'genes'] as const)
    },
  },

  // Stats
  stats: {
    all: ['stats'] as const,
    overview: () => [...queryKeys.stats.all, 'overview'] as const,
    detailed: (params?: unknown) => {
      const normalized = normalizeQueryKeyObject(params)
      return normalized
        ? ([...queryKeys.stats.all, 'detailed', normalized] as const)
        : ([...queryKeys.stats.all, 'detailed'] as const)
    },
    baRange: () => [...queryKeys.stats.all, 'ba-range'] as const,
    topGenes: (params?: unknown) => {
      const normalized = normalizeQueryKeyObject(params)
      return normalized
        ? ([...queryKeys.stats.all, 'top-genes', normalized] as const)
        : ([...queryKeys.stats.all, 'top-genes'] as const)
    },
    topDiseases: (params?: unknown) => {
      const normalized = normalizeQueryKeyObject(params)
      return normalized
        ? ([...queryKeys.stats.all, 'top-diseases', normalized] as const)
        : ([...queryKeys.stats.all, 'top-diseases'] as const)
    },
  },

  // Network
  network: {
    all: ['network'] as const,
    gene: (geneId: number | null, params?: unknown) => {
      const normalized = normalizeQueryKeyObject(params)
      return normalized
        ? ([...queryKeys.network.all, 'gene', geneId, normalized] as const)
        : ([...queryKeys.network.all, 'gene', geneId] as const)
    },
    geneDetail: (geneId: number) => [...queryKeys.network.all, 'gene-detail', geneId] as const,
  },

  // Species (for filters)
  species: {
    all: ['species'] as const,
    list: () => [...queryKeys.species.all, 'list'] as const,
  },

  // Admin / Monitoring
  admin: {
    all: ['admin'] as const,
    metrics: () => [...queryKeys.admin.all, 'metrics'] as const,
  },

  // Analysis
  analysis: {
    all: ['analysis'] as const,
    summary: () => [...queryKeys.analysis.all, 'summary'] as const,
    highAffinity: (params?: unknown) => {
      const normalized = normalizeQueryKeyObject(params)
      return normalized
        ? ([...queryKeys.analysis.all, 'high-affinity', normalized] as const)
        : ([...queryKeys.analysis.all, 'high-affinity'] as const)
    },
    conservation: (params?: unknown) => {
      const normalized = normalizeQueryKeyObject(params)
      return normalized
        ? ([...queryKeys.analysis.all, 'conservation', normalized] as const)
        : ([...queryKeys.analysis.all, 'conservation'] as const)
    },
    epigenetic: (params?: unknown) => {
      const normalized = normalizeQueryKeyObject(params)
      return normalized
        ? ([...queryKeys.analysis.all, 'epigenetic', normalized] as const)
        : ([...queryKeys.analysis.all, 'epigenetic'] as const)
    },
    disease: (params?: unknown) => {
      const normalized = normalizeQueryKeyObject(params)
      return normalized
        ? ([...queryKeys.analysis.all, 'disease', normalized] as const)
        : ([...queryKeys.analysis.all, 'disease'] as const)
    },
  },
} as const

// 类型导出，方便在其他地方使用
export type QueryKeys = typeof queryKeys
