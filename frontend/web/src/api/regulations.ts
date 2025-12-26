import { apiClient } from './client'
import type { components, RegulationFilterParams } from '@/types'

type RegulationListItem = components['schemas']['RegulationListItem']
type RegulationDetail = components['schemas']['RegulationDetail']
type PaginatedResponse<T> = components['schemas']['PaginatedResponse_RegulationListItem_'] & { items: T[] }

/**
 * lncRNA 选项接口（轻量级，仅用于下拉选择）
 *
 * Phase 5.2 Task 2 - 优化 Regulations 页面筛选器
 *
 * 包含调控数量统计，帮助用户选择调控关系多的 lncRNA
 *
 * @example
 * {
 *   gene_id: 1,
 *   gene_ensembl_id: "ENSG00000000003",
 *   gene_name: "TSPAN6",
 *   species_id: 1,
 *   species_name: "人类",
 *   regulation_count: 42
 * }
 */
export interface LncRNAOption {
  gene_id: number
  gene_ensembl_id: string
  gene_name: string | null
  species_id: number
  species_name: string
  regulation_count: number  // 该 lncRNA 的调控数量
}

/**
 * lncRNA 选项响应接口
 */
export interface LncRNAOptionsResponse {
  lncrnas: LncRNAOption[]
}

/**
 * 靶基因选项接口（轻量级，仅用于下拉选择）
 *
 * Phase 5.2 Task 2 - 优化 Regulations 页面筛选器
 *
 * 包含被调控次数统计，帮助用户选择热门靶基因
 *
 * @example
 * {
 *   gene_id: 2,
 *   gene_ensembl_id: "ENSG00000000005",
 *   gene_name: "TNMD",
 *   species_id: 1,
 *   species_name: "人类",
 *   lncrna_count: 15
 * }
 */
export interface TargetOption {
  gene_id: number
  gene_ensembl_id: string
  gene_name: string | null
  species_id: number
  species_name: string
  lncrna_count: number  // 被多少个 lncRNA 调控
}

/**
 * 靶基因选项响应接口
 */
export interface TargetOptionsResponse {
  targets: TargetOption[]
}

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
  list: (params: RegulationFilterParams, signal?: AbortSignal) =>
    apiClient.get<PaginatedResponse<RegulationListItem>>('/api/v1/regulations', { params, signal }),

  /**
   * 获取调控关系详情（包含序列数据）
   */
  getDetail: (regulationId: number, signal?: AbortSignal) =>
    apiClient.get<RegulationDetail>(`/api/v1/regulations/${regulationId}`, { signal }),

  /**
   * 获取 lncRNA 选项列表（轻量级 API）
   *
   * Phase 5.2 Task 2 - 新增方法
   *
   * 用途: Regulations 页面的 lncRNA 筛选下拉框，替代现有的文本输入 + 模糊搜索
   *
   * 性能:
   * - 响应时间: 50-200ms (首次), < 10ms (缓存)
   * - 响应大小: 预计 500KB-1MB（取决于数据量）
   * - 后端缓存: Redis 30 分钟
   * - 前端缓存: 推荐 React Query 10 分钟
   *
   * 数据特征:
   * - 仅返回有调控关系的 lncRNA（regulation_count > 0）
   * - 按调控数量降序排序，帮助用户快速找到热门 lncRNA
   * - 自动去重，每个 lncRNA 只出现一次
   *
   * @param params - 查询参数
   * @param params.species_id - 可选：按物种过滤（1=Human, 2=Chimp, 3=Macaque, 4=Marmoset）
   * @returns Promise with lncrnas array
   *
   * @example
   * // 基础用法：获取所有 lncRNA
   * const { data } = useQuery({
   *   queryKey: ['lncrna-options'],
   *   queryFn: () => regulationsApi.getLncRNAOptions(),
   *   staleTime: 10 * 60 * 1000, // 10 分钟缓存
   * })
   *
   * @example
   * // 推荐：按物种过滤（减少数据传输）
   * const { data } = useQuery({
   *   queryKey: ['lncrna-options', speciesId],
   *   queryFn: () => regulationsApi.getLncRNAOptions({ species_id: speciesId }),
   *   staleTime: 10 * 60 * 1000,
   *   enabled: !!speciesId, // 只在物种选中时加载
   * })
   *
   * @example
   * // 渲染选择器（带调控数量提示）
   * <Select
   *   showSearch
   *   virtual // 支持大数据量
   *   loading={isLoading}
   *   options={data?.lncrnas.map(lnc => ({
   *     value: lnc.gene_id,
   *     label: `${lnc.gene_name || lnc.gene_ensembl_id} (${lnc.regulation_count} targets)`,
   *     searchValue: `${lnc.gene_name} ${lnc.gene_ensembl_id}`
   *   }))}
   * />
   *
   * @see REGULATIONS_API_INTEGRATION_PLAN.md for complete integration guide
   * @see Phase 5.1 Diseases API (diseases.ts) for similar pattern
   * @see Phase 5.2 Genes API (genes.ts) for similar pattern
   */
  getLncRNAOptions: async (params?: {
    species_id?: number
  }, signal?: AbortSignal): Promise<LncRNAOptionsResponse> => {
    const response = await apiClient.get<LncRNAOptionsResponse>(
      '/api/v1/regulations/lncrna-options',
      { params, signal }
    )
    return response.data
  },

  /**
   * 获取靶基因选项列表（轻量级 API）
   *
   * Phase 5.2 Task 2 - 新增方法
   *
   * 用途: Regulations 页面的靶基因筛选下拉框，替代现有的文本输入 + 模糊搜索
   *
   * 性能:
   * - 响应时间: 50-200ms (首次), < 10ms (缓存)
   * - 响应大小: 预计 1-2MB（靶基因数量通常更多）
   * - 后端缓存: Redis 30 分钟
   * - 前端缓存: 推荐 React Query 10 分钟
   *
   * 数据特征:
   * - 仅返回被调控的靶基因（lncrna_count > 0）
   * - 按被调控次数降序排序，帮助用户快速找到热门靶基因
   * - 自动去重，每个靶基因只出现一次
   *
   * @param params - 查询参数
   * @param params.species_id - 可选：按物种过滤（1=Human, 2=Chimp, 3=Macaque, 4=Marmoset）
   * @returns Promise with targets array
   *
   * @example
   * // 基础用法：获取所有靶基因
   * const { data } = useQuery({
   *   queryKey: ['target-options'],
   *   queryFn: () => regulationsApi.getTargetOptions(),
   *   staleTime: 10 * 60 * 1000, // 10 分钟缓存
   * })
   *
   * @example
   * // 推荐：按物种过滤（减少数据传输）
   * const { data } = useQuery({
   *   queryKey: ['target-options', speciesId],
   *   queryFn: () => regulationsApi.getTargetOptions({ species_id: speciesId }),
   *   staleTime: 10 * 60 * 1000,
   *   enabled: !!speciesId, // 只在物种选中时加载
   * })
   *
   * @example
   * // 渲染选择器（带被调控次数提示）
   * <Select
   *   showSearch
   *   virtual // 支持大数据量
   *   loading={isLoading}
   *   options={data?.targets.map(target => ({
   *     value: target.gene_id,
   *     label: `${target.gene_name || target.gene_ensembl_id} (${target.lncrna_count} lncRNAs)`,
   *     searchValue: `${target.gene_name} ${target.gene_ensembl_id}`
   *   }))}
   * />
   *
   * @see REGULATIONS_API_INTEGRATION_PLAN.md for complete integration guide
   * @see Phase 5.1 Diseases API (diseases.ts) for similar pattern
   * @see Phase 5.2 Genes API (genes.ts) for similar pattern
   */
  getTargetOptions: async (params?: {
    species_id?: number
  }, signal?: AbortSignal): Promise<TargetOptionsResponse> => {
    const response = await apiClient.get<TargetOptionsResponse>(
      '/api/v1/regulations/target-options',
      { params, signal }
    )
    return response.data
  }
}
