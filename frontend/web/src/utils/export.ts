/**
 * 导出工具函数
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
 * CSV 转义函数（防止 CSV 注入和公式注入）
 *
 * 安全措施：
 * 1. 以 =, +, -, @, \t, \r 开头的字符串前添加单引号防止公式注入
 * 2. 包含逗号、双引号、换行符的字符串用双引号包裹
 */
function escapeCSV(val: unknown): string {
  let str = String(val ?? '')

  // 防止 CSV 公式注入：Excel/Sheets 会将这些字符开头的内容解释为公式
  if (/^[=+\-@\t\r]/.test(str)) {
    str = "'" + str
  }

  // 处理需要引号包裹的特殊字符
  if (str.includes(',') || str.includes('"') || str.includes('\n') || str.includes('\r')) {
    return `"${str.replace(/"/g, '""')}"`
  }
  return str
}

/**
 * 分页获取所有数据
 */
async function fetchAllRegulations(
  filters: ExportFilterParams,
  total: number,
  onProgress?: (current: number, total: number) => void
): Promise<Regulation[]> {
  const PAGE_SIZE = EXPORT_LIMITS.FETCH_PAGE_SIZE
  const totalPages = Math.ceil(total / PAGE_SIZE)
  const allData: Regulation[] = []

  for (let page = 1; page <= totalPages; page++) {
    const { data } = await apiClient.get('/api/v1/regulations', {
      params: {
        ...filters,
        page,
        page_size: PAGE_SIZE
      }
    })

    allData.push(...data.items)
    onProgress?.(allData.length, total)

    // 避免过快请求
    if (page < totalPages) {
      await new Promise(resolve => setTimeout(resolve, 100))
    }
  }

  return allData
}

/**
 * 导出为 CSV
 */
function exportToCSV(data: Regulation[]): ExportResult {
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
 * 导出为 XLSX（动态导入）
 */
async function exportToXLSX(data: Regulation[]): Promise<ExportResult> {
  try {
    const XLSX = await import('xlsx')

    const worksheet = XLSX.utils.json_to_sheet(data.map(r => ({
      'ID': r.regulation_id,
      'lncRNA': r.lncrna_gene_name || '',
      'Target': r.target_gene_name || '',
      'Species': r.species_name,
      'Chr': r.target_chromosome || '',
      'Start': r.target_start,
      'End': r.target_end,
      'BA': r.binding_affinity,
      'Peaks': r.num_peaks
    })))

    const workbook = XLSX.utils.book_new()
    XLSX.utils.book_append_sheet(workbook, worksheet, 'Regulations')

    XLSX.writeFile(workbook, `regulations-${Date.now()}.xlsx`)

    return { success: true }
  } catch (error) {
    console.error('XLSX export failed:', error)
    return {
      success: false,
      error: 'EXPORT_FAILED',
      message: error instanceof Error ? error.message : '导出失败'
    }
  }
}

/**
 * 导出 Regulations（主函数）
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

  // 2. 获取数据
  try {
    const allData = await fetchAllRegulations(filters, total, onProgress)

    // 3. 生成文件
    if (format === 'csv') {
      return exportToCSV(allData)
    } else {
      return await exportToXLSX(allData)
    }
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
 * 导出选中行（无需分页获取，直接使用内存数据）
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

  if (format === 'csv') {
    return exportToCSV(data)
  } else {
    return await exportToXLSX(data)
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
