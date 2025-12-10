import { apiClient } from './client'
import type { components } from '@/types'

type TraitGeneAssociationDetail = components['schemas']['TraitGeneAssociationDetail']
type PaginatedTraitAssociationResponse = components['schemas']['PaginatedResponse_TraitGeneAssociationDetail_']
type PaginatedGeneResponse = components['schemas']['PaginatedResponse_TraitGeneAssociationDetail_']

/**
 * 疾病选项接口（轻量级，仅用于下拉选择）
 */
export interface DiseaseOption {
  trait_id: number
  trait_name: string
}

/**
 * 疾病选项响应接口
 */
export interface DiseaseOptionsResponse {
  traits: DiseaseOption[]
}

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

  /**
   * 获取疾病选项列表（轻量级 API）
   * 仅返回 trait_id 和 trait_name，用于下拉选择
   * 后端已去重
   */
  getOptions: async (): Promise<DiseaseOptionsResponse> => {
    const response = await apiClient.get<DiseaseOptionsResponse>('/api/v1/diseases/options')
    return response.data
  },
}
