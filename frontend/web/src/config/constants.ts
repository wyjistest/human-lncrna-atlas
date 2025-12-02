/**
 * 全局配置常量
 *
 * BA 范围说明：
 * - 实际数据范围：50.0 - 755.99（来自 /api/v1/stats/ba-range）
 * - 前端使用 useBARange hook 动态获取，此处为静态回退值
 */

// ============ BA（Binding Affinity）配置 ============
export const BA_CONFIG = {
  /** 最小值（实际数据 min: 50.0） */
  MIN: 50,

  /** 最大值（实际数据 max: 755.99） */
  MAX: 756,

  /** 滑块步长 */
  STEP: 1,

  /** 默认筛选范围（不设置表示不限制） */
  DEFAULT_MIN: undefined,
  DEFAULT_MAX: undefined,

  /** 直方图区间数量 */
  HISTOGRAM_BUCKETS: 10
} as const

// ============ 导出限制 ============
export const EXPORT_LIMITS = {
  /** 数据量超过此值时显示警告 */
  WARN: 1000,

  /** 前端导出上限 */
  MAX_FRONTEND: 10000,

  /** 分页获取时每页大小 */
  FETCH_PAGE_SIZE: 200
} as const

// ============ 批量操作限制 ============
export const BATCH_LIMITS = {
  /** 批量导出选中行上限（与 EXPORT_LIMITS.MAX_FRONTEND 对齐） */
  MAX_EXPORT: EXPORT_LIMITS.MAX_FRONTEND,

  /** 批量可视化上限（防止浏览器卡顿） */
  MAX_VISUALIZATION: 100
} as const

// ============ 物种选项 ============
export const SPECIES_OPTIONS = [
  { label: '人类', value: 1 },
  { label: '黑猩猩', value: 2 },
  { label: '猕猴', value: 3 },
  { label: '狨猴', value: 4 }
] as const

// ============ 染色体选项 ============
export const CHROMOSOME_OPTIONS = [
  'chr1', 'chr2', 'chr3', 'chr4', 'chr5', 'chr6', 'chr7', 'chr8', 'chr9', 'chr10',
  'chr11', 'chr12', 'chr13', 'chr14', 'chr15', 'chr16', 'chr17', 'chr18', 'chr19',
  'chr20', 'chr21', 'chr22', 'chrX', 'chrY'
].map(chr => ({ label: chr, value: chr }))

// ============ 工具函数：生成 BA 区间 ============

/**
 * 动态生成 BA 分布区间（用于直方图）
 */
export function generateBABuckets(
  min: number = BA_CONFIG.MIN,
  max: number = BA_CONFIG.MAX,
  numBuckets: number = BA_CONFIG.HISTOGRAM_BUCKETS
) {
  const step = (max - min) / numBuckets

  return Array.from({ length: numBuckets }, (_, i) => ({
    min: min + i * step,
    max: min + (i + 1) * step,
    label: `${(min + i * step).toFixed(0)}-${(min + (i + 1) * step).toFixed(0)}`
  }))
}
