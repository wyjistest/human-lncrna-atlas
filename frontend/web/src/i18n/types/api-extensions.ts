/**
 * 类型扩展文件
 *
 * 用途：扩展 OpenAPI 自动生成的类型，避免直接修改 api.ts
 * 规范：所有新增类型放这里，统一从 @/types 导出
 *
 * 注意：NetworkNode, NetworkEdge, NetworkData, GeneDetail 已在 network.ts 中定义
 */

import type { components } from './api'

// ============ 复用 OpenAPI 类型（别名） ============
export type Gene = components['schemas']['GeneListItem']
export type Regulation = components['schemas']['RegulationListItem']
export type RegulationDetail = components['schemas']['RegulationDetail']
export type Trait = components['schemas']['TraitDetail']
export type OverviewStats = components['schemas']['OverviewStats']

// Base type alias for GeneDetail (required for interface extension)
type GeneDetailBase = components['schemas']['GeneDetail']

/**
 * 扩展的 GeneDetail 类型 (用于基因详情页面)
 * 基于 OpenAPI 的 GeneDetail，添加后端新增的 conservation 字段
 *
 * Phase 2.2: Conservation feature
 */
export interface GeneDetailExtended extends GeneDetailBase {
  /** Conservation label string, e.g., "1111" or "1000" (H-C-M-M format) */
  conservation_label?: string
  /** Number of species where the gene is conserved (1-4) */
  conservation_count?: number
}

// 分页响应类型
export type PaginatedResponse<T> = {
  items: T[]
  total: number
  page: number
  page_size: number
  total_pages: number
}

// ============ 新增类型（后端已实现） ============

/**
 * BA 范围
 * API: GET /api/v1/stats/ba-range
 * 状态：✅ 后端已实现
 */
export interface BARange {
  min_ba: number
  max_ba: number
  avg_ba: number
  total_count: number
}

/**
 * BA 分布桶
 */
export interface BADistribution {
  range_start: number
  range_end: number
  count: number
}

/**
 * 详细统计信息（用于 Stats 页面图表）
 * API: GET /api/v1/stats/detailed
 * 状态：✅ 后端已实现
 */
export interface DetailedStatsResponse {
  species_distribution: Array<{
    species_id: number
    species_name: string
    count: number
  }>

  ba_distribution: BADistribution[]

  top_lncrnas: Array<{
    gene_id: number
    gene_name: string
    gene_ensembl_id: string
    species_name: string
    regulation_count: number
  }>

  ba_range: BARange
}

/**
 * Regulations 筛选参数
 * 状态：✅ 后端已全部实现
 *
 * 注意：多值参数统一使用逗号分隔字符串格式
 */
export interface RegulationFilterParams {
  // 分页
  page?: number
  page_size?: number

  // BA 范围筛选
  min_ba?: number
  max_ba?: number

  // 物种筛选（逗号分隔，如 "1,2,3"）
  species_ids?: string

  // 染色体筛选（逗号分隔，如 "chr1,chr2"）
  chromosomes?: string

  // 基因 ID 筛选
  lncrna_gene_id?: number
  target_gene_id?: number

  // 基因名模糊搜索
  lncrna_gene_name?: string
  target_gene_name?: string
}

/**
 * 导出参数
 */
export interface ExportParams extends RegulationFilterParams {
  format: 'csv' | 'xlsx'
  limit?: number
}

/**
 * 导出结果
 */
export type ExportResult =
  | { success: true }
  | {
      success: false
      error: 'DATA_TOO_LARGE' | 'EXPORT_FAILED' | 'NO_DATA'
      total?: number
      limit?: number
      message?: string
    }
