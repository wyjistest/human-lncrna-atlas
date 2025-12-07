import { apiClient } from './client'
import type { components, RegulationFilterParams } from '@/types'

type RegulationListItem = components['schemas']['RegulationListItem']
type RegulationDetail = components['schemas']['RegulationDetail']
type PaginatedResponse<T> = components['schemas']['PaginatedResponse_RegulationListItem_'] & { items: T[] }

export const regulationsApi = {
  /**
   * 获取调控关系列表（支持多种筛选条件）
   *
   * 筛选参数：
   * - species_id / species_ids: 物种筛选（单个或逗号分隔的多个）
   * - chromosome / chromosomes: 染色体筛选（单个或逗号分隔的多个）
   * - min_ba / max_ba: BA 范围筛选
   * - lncrna_gene_name / target_gene_name: 基因名模糊搜索
   */
  list: (params: RegulationFilterParams) =>
    apiClient.get<PaginatedResponse<RegulationListItem>>('/api/v1/regulations', { params }),

  /**
   * 获取调控关系详情（包含序列数据）
   */
  getDetail: (regulationId: number) =>
    apiClient.get<RegulationDetail>(`/api/v1/regulations/${regulationId}`),
}
