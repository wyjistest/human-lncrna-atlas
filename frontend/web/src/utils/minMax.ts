export type MinMaxRange = {
  min: number
  max: number
}

export type MinMaxOptions = {
  /**
   * 当 values 中没有任何有限数值时返回的默认范围
   */
  defaultMin: number
  defaultMax: number
  /**
   * 额外纳入计算的基线值（用于保证视觉映射包含 0/1 等基准）
   */
  include?: Iterable<number>
}

/**
 * 计算 min/max（安全遍历版）
 *
 * 目的：
 * - 避免 `Math.min(...arr)` / `Math.max(...arr)` 在大数组下的参数长度上限与性能问题
 * - 统一处理 null/undefined/NaN/Infinity 等非有限值
 */
export function getMinMax(
  values: Iterable<number | null | undefined>,
  options: MinMaxOptions
): MinMaxRange {
  let min = Number.POSITIVE_INFINITY
  let max = Number.NEGATIVE_INFINITY

  const update = (v: number) => {
    if (!Number.isFinite(v)) return
    if (v < min) min = v
    if (v > max) max = v
  }

  for (const v of values) {
    if (typeof v !== 'number') continue
    update(v)
  }

  if (options.include) {
    for (const v of options.include) update(v)
  }

  if (!Number.isFinite(min) || !Number.isFinite(max)) {
    return { min: options.defaultMin, max: options.defaultMax }
  }

  return { min, max }
}

/**
 * 计算最大值（安全遍历版）
 */
export function getMax(values: Iterable<number | null | undefined>, defaultValue: number): number {
  let max = Number.NEGATIVE_INFINITY
  for (const v of values) {
    if (typeof v !== 'number' || !Number.isFinite(v)) continue
    if (v > max) max = v
  }
  return Number.isFinite(max) ? max : defaultValue
}

