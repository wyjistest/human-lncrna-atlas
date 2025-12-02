import { apiClient } from './client'
import type { components } from '@/types'

type TraitDetail = components['schemas']['TraitDetail']
type TraitGeneAssociationDetail = components['schemas']['TraitGeneAssociationDetail']
type PaginatedTraitAssociationResponse = components['schemas']['PaginatedResponse_TraitGeneAssociationDetail_']
type PaginatedGeneResponse = components['schemas']['PaginatedResponse_TraitGeneAssociationDetail_']

export const diseasesApi = {
  /** 获取疾病/性状列表 - 返回带关联信息的列表 */
  list: (params: {
    page?: number
    page_size?: number
    trait_category?: string
    search?: string
  }) => apiClient.get<PaginatedTraitAssociationResponse>('/api/v1/diseases', { params }),

  getGenes: (traitId: number, params?: {
    page?: number
    page_size?: number
    ontology_id?: number
  }) => apiClient.get<PaginatedGeneResponse>(`/api/v1/diseases/${traitId}/genes`, { params }),

  /** 获取基因的疾病关联列表 */
  getGeneAssociations: (geneId: number) =>
    apiClient.get<TraitGeneAssociationDetail[]>(`/api/v1/diseases/gene/${geneId}/associations`),
}
