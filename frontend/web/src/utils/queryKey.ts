/**
 * QueryKey 归一化工具
 *
 * TanStack Query 会对 queryKey 做确定性哈希（对象 key 顺序不影响；数组顺序会影响）。
 * 本工具用于把“语义等价”的参数归一化成同一个结构，减少重复缓存与额外请求。
 */

type PlainObject = Record<string, unknown>

function isPlainObject(value: unknown): value is PlainObject {
  if (value === null || typeof value !== 'object') return false
  const proto = Object.getPrototypeOf(value)
  return proto === Object.prototype || proto === null
}

function isSortablePrimitiveArray(values: unknown[]): values is Array<string | number | boolean> {
  return values.every((v) => typeof v === 'string' || typeof v === 'number' || typeof v === 'boolean')
}

function dedupeAndSortPrimitiveArray(values: Array<string | number | boolean>): Array<string | number | boolean> {
  const unique = Array.from(new Set(values))

  if (unique.every((v) => typeof v === 'string')) {
    return (unique as string[]).sort((a, b) => a.localeCompare(b))
  }
  if (unique.every((v) => typeof v === 'number')) {
    return (unique as number[]).sort((a, b) => a - b)
  }
  if (unique.every((v) => typeof v === 'boolean')) {
    return (unique as boolean[]).sort((a, b) => Number(a) - Number(b))
  }
  return unique
}

function normalizeQueryKeyValue(value: unknown): unknown {
  if (value === undefined) return undefined

  // 常见不可 JSON 序列化对象做安全降级（仅用于 queryKey）
  if (value instanceof Date) {
    return value.toISOString()
  }
  if (typeof URLSearchParams !== 'undefined' && value instanceof URLSearchParams) {
    return value.toString()
  }

  if (Array.isArray(value)) {
    const normalizedArray = value
      .map(normalizeQueryKeyValue)
      .filter((v) => v !== undefined)

    if (isSortablePrimitiveArray(normalizedArray)) {
      return dedupeAndSortPrimitiveArray(normalizedArray)
    }

    return normalizedArray
  }

  if (isPlainObject(value)) {
    return normalizeQueryKeyObject(value)
  }

  return value
}

/**
 * 归一化 queryKey 中的参数对象：
 * - 去掉值为 `undefined` 的字段（与 axios params 行为保持一致）
 * - 数组：去掉 `undefined`，对纯基本类型数组做去重+排序（降低“顺序不敏感”过滤器导致的缓存碎片）
 * - 递归处理嵌套对象/数组
 * - 若对象归一化后为空，则返回 `undefined`
 */
export function normalizeQueryKeyObject(obj: unknown): PlainObject | undefined {
  if (!isPlainObject(obj)) return undefined

  const out: PlainObject = {}
  for (const [key, raw] of Object.entries(obj)) {
    const normalized = normalizeQueryKeyValue(raw)
    if (normalized === undefined) continue
    out[key] = normalized
  }

  return Object.keys(out).length > 0 ? out : undefined
}

/**
 * 归一化“逗号分隔列表”字符串（用于 queryKey）：
 * - split(',') + trim + 去空 + 去重 + 排序
 */
export function normalizeCommaSeparatedList(value: string | undefined): string | undefined {
  if (!value) return undefined
  const items = value
    .split(',')
    .map((s) => s.trim())
    .filter((s) => s.length > 0)

  if (items.length === 0) return undefined

  const uniqueSorted = Array.from(new Set(items)).sort((a, b) => a.localeCompare(b))
  return uniqueSorted.join(',')
}
