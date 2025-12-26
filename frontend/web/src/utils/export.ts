/**
 * 导出工具函数
 *
 * Phase 9.3 更新：迁移到后端 openpyxl 导出
 * - xlsx npm 库存在已知漏洞 (high severity)
 * - 现在所有导出都通过后端 API 完成
 * - 后端使用 openpyxl write_only 模式，降低内存峰值（非真 O(1)，完整文件需在内存中生成）
 *
 * 导出限制：
 * - < 1000 条：直接导出
 * - 1000-10000 条：显示警告后导出
 * - > 10000 条：拒绝，提示缩小筛选范围
 */

import { saveAs } from 'file-saver'
import { apiClient } from '@/api/client'
import type { Regulation, ExportResult } from '@/types'
import { EXPORT_LIMITS } from '@/config/constants'
import { escapeCSV } from '@/utils/csv'

/**
 * 导出筛选参数（后端支持的格式）
 */
interface ExportFilterParams {
  min_ba?: number
  max_ba?: number
  species_ids?: string  // 逗号分隔
  chromosomes?: string  // 逗号分隔
  lncrna_gene_name?: string
  target_gene_name?: string
}

/**
 * 从后端下载导出文件
 *
 * @param filters - 筛选参数
 * @param format - 导出格式 (csv/excel)
 * @param total - 预期总数（用于限制检查）
 */
async function downloadFromBackend(
  filters: ExportFilterParams,
  format: 'csv' | 'xlsx',
  total: number,
): Promise<ExportResult> {
  try {
    // 构建请求参数
    const params = new URLSearchParams()

    // 映射格式：前端用 xlsx，后端用 excel
    params.append('format', format === 'xlsx' ? 'excel' : 'csv')
    params.append('limit', String(Math.min(total, EXPORT_LIMITS.MAX_FRONTEND)))

    if (filters.min_ba !== undefined) {
      params.append('min_ba', String(filters.min_ba))
    }
    if (filters.max_ba !== undefined) {
      params.append('max_ba', String(filters.max_ba))
    }
    if (filters.species_ids) {
      params.append('species_ids', filters.species_ids)
    }
    if (filters.chromosomes) {
      params.append('chromosomes', filters.chromosomes)
    }
    if (filters.lncrna_gene_name) {
      params.append('lncrna_gene_name', filters.lncrna_gene_name)
    }
    if (filters.target_gene_name) {
      params.append('target_gene_name', filters.target_gene_name)
    }

    // 使用 blob 响应类型下载文件
    const response = await apiClient.get('/api/v1/export/regulations', {
      params,
      responseType: 'blob',
    })

    // 从 Content-Disposition 获取文件名，或使用默认名
    const contentDisposition = response.headers['content-disposition']
    let filename = `regulations-${Date.now()}.${format === 'xlsx' ? 'xlsx' : 'csv'}`

    if (contentDisposition) {
      const match = contentDisposition.match(/filename=([^;]+)/)
      if (match) {
        filename = match[1].replace(/['"]/g, '')
      }
    }

    // 触发浏览器下载
    saveAs(response.data, filename)

    return { success: true }
  } catch (error) {
    console.error('Export failed:', error)
    return {
      success: false,
      error: 'EXPORT_FAILED',
      message: error instanceof Error ? error.message : '导出失败'
    }
  }
}

/**
 * 本地生成 CSV（仅用于小量选中行导出）
 */
function exportToCSVLocal(data: Regulation[]): ExportResult {
  try {
    const headers = ['ID', 'lncRNA', 'Target', 'Species', 'Chr', 'Start', 'End', 'BA', 'Peaks']

    const rows = data.map(r => [
      escapeCSV(r.regulation_id),
      escapeCSV(r.lncrna_gene_name),
      escapeCSV(r.target_gene_name),
      escapeCSV(r.species_name),
      escapeCSV(r.target_chromosome),
      escapeCSV(r.target_start),
      escapeCSV(r.target_end),
      escapeCSV(r.binding_affinity),
      escapeCSV(r.num_peaks)
    ].join(','))

    const csv = [headers.join(','), ...rows].join('\n')
    const blob = new Blob(['\uFEFF' + csv], { type: 'text/csv;charset=utf-8;' })

    saveAs(blob, `regulations-${Date.now()}.csv`)

    return { success: true }
  } catch (error) {
    console.error('CSV export failed:', error)
    return {
      success: false,
      error: 'EXPORT_FAILED',
      message: error instanceof Error ? error.message : '导出失败'
    }
  }
}

/**
 * 导出 Regulations（主函数）
 *
 * Phase 9.3: 全部迁移到后端导出
 */
export async function exportRegulations(
  filters: ExportFilterParams,
  format: 'csv' | 'xlsx',
  total: number,
  onProgress?: (current: number, total: number) => void
): Promise<ExportResult> {
  // 1. 数据量检查
  if (total === 0) {
    return {
      success: false,
      error: 'NO_DATA',
      message: '没有可导出的数据'
    }
  }

  if (total > EXPORT_LIMITS.MAX_FRONTEND) {
    return {
      success: false,
      error: 'DATA_TOO_LARGE',
      total,
      limit: EXPORT_LIMITS.MAX_FRONTEND,
      message: `数据量过大（${total} 条），超过导出限制（${EXPORT_LIMITS.MAX_FRONTEND} 条）`
    }
  }

  // 2. 通知开始（后端流式处理，无法提供精确进度）
  onProgress?.(0, total)

  // 3. 调用后端 API 下载
  const result = await downloadFromBackend(filters, format, total)

  // 4. 通知完成
  if (result.success) {
    onProgress?.(total, total)
  }

  return result
}

/**
 * 导出选中行
 *
 * 对于小量选中行：
 * - CSV: 本地生成（快速，无需网络请求）
 * - XLSX: 调用后端 API（安全，避免 xlsx 漏洞）
 */
export async function exportSelectedRegulations(
  data: Regulation[],
  format: 'csv' | 'xlsx'
): Promise<ExportResult> {
  if (data.length === 0) {
    return {
      success: false,
      error: 'NO_DATA',
      message: '没有选中的数据'
    }
  }

  // 校验上限
  if (data.length > EXPORT_LIMITS.MAX_FRONTEND) {
    return {
      success: false,
      error: 'DATA_TOO_LARGE',
      total: data.length,
      limit: EXPORT_LIMITS.MAX_FRONTEND,
      message: `选中数据过多（${data.length} 条），超过导出限制（${EXPORT_LIMITS.MAX_FRONTEND} 条）`
    }
  }

  // CSV: 本地生成（小量数据，快速响应）
  if (format === 'csv') {
    return exportToCSVLocal(data)
  }

  // XLSX: 选中行导出不支持 XLSX 格式
  // 原因：后端 API 基于筛选条件查询，无法接收 regulation_id 列表
  // 解决方案：明确告知用户，建议使用 CSV 格式
  return {
    success: false,
    error: 'FORMAT_NOT_SUPPORTED',
    message: '选中行导出暂不支持 Excel 格式，请使用 CSV 格式导出',
    suggestedFormat: 'csv'
  }
}

/**
 * 检查是否需要显示大数据量警告
 */
export function shouldShowExportWarning(total: number): boolean {
  return total > EXPORT_LIMITS.WARN && total <= EXPORT_LIMITS.MAX_FRONTEND
}

/**
 * 检查是否超过导出限制
 */
export function isExportLimitExceeded(total: number): boolean {
  return total > EXPORT_LIMITS.MAX_FRONTEND
}
