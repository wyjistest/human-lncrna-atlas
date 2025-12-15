/**
 * ECharts 回调函数类型定义
 *
 * 为 ECharts 的 formatter、click handler 等回调提供类型支持，
 * 减少代码中的 `as any` 类型断言。
 */

import type { EChartsOption } from 'echarts'

/**
 * ECharts 通用参数基础类型
 */
export interface EChartsBaseParams {
  componentType: string
  componentSubType?: string
  componentIndex: number
  seriesType?: string
  seriesIndex?: number
  seriesId?: string
  seriesName?: string
  name: string
  dataIndex: number
  data: unknown
  dataType?: string
  value: number | number[] | string | null
  color?: string
  dimensionNames?: string[]
  encode?: Record<string, number[]>
  $vars?: string[]
}

/**
 * Tooltip formatter 参数类型
 */
export interface TooltipFormatterParams extends EChartsBaseParams {
  marker?: string
  axisValue?: string | number
  axisValueLabel?: string
  percent?: number
}

/**
 * 热力图 (Heatmap) 数据项类型
 */
export interface HeatmapDataItem {
  value: [number, number, number | null]
  itemStyle?: {
    color?: string
    borderColor?: string
  }
}

/**
 * 热力图 tooltip/click 参数
 */
export interface HeatmapParams extends Omit<EChartsBaseParams, 'value'> {
  value: [number, number, number | null]
  data: HeatmapDataItem | [number, number, number | null]
}

/**
 * 柱状图/条形图参数
 */
export interface BarParams extends EChartsBaseParams {
  value: number
}

/**
 * 饼图参数
 */
export interface PieParams extends EChartsBaseParams {
  value: number
  percent: number
}

/**
 * Sankey 图参数
 */
export interface SankeyParams extends EChartsBaseParams {
  dataType: 'node' | 'edge'
  data: {
    name?: string
    value?: number
    source?: string
    target?: string
  }
}

/**
 * Chord 图参数
 */
export interface ChordParams extends EChartsBaseParams {
  dataType: 'node' | 'edge'
  data: {
    id?: string
    name?: string
    value?: number
    source?: string | number
    target?: string | number
  }
}

/**
 * 雷达图参数
 */
export interface RadarParams extends EChartsBaseParams {
  value: number[]
}

/**
 * 箱线图参数
 */
export interface BoxplotParams extends EChartsBaseParams {
  value: [number, number, number, number, number] // [min, Q1, median, Q3, max]
}

/**
 * Axis label formatter 参数类型
 */
export interface AxisLabelFormatterParams {
  value: string | number
  index: number
}

/**
 * Visual Map formatter 参数
 */
export type VisualMapFormatterParams = number | [number, number]

/**
 * ECharts click 事件参数
 */
export type EChartsClickParams =
  | HeatmapParams
  | BarParams
  | PieParams
  | SankeyParams
  | ChordParams
  | RadarParams
  | BoxplotParams
  | EChartsBaseParams

/**
 * 类型守卫：检查是否为热力图参数
 */
export function isHeatmapParams(params: EChartsClickParams): params is HeatmapParams {
  return Array.isArray(params.value) && params.value.length === 3
}

/**
 * 类型守卫：检查是否为 Sankey/Chord 节点
 */
export function isNodeParams(
  params: SankeyParams | ChordParams
): params is (SankeyParams | ChordParams) & { dataType: 'node' } {
  return params.dataType === 'node'
}

/**
 * 类型守卫：检查是否为 Sankey/Chord 边
 */
export function isEdgeParams(
  params: SankeyParams | ChordParams
): params is (SankeyParams | ChordParams) & { dataType: 'edge' } {
  return params.dataType === 'edge'
}

/**
 * ECharts 实例方法类型 (用于 ref)
 */
export interface EChartsInstance {
  getEchartsInstance: () => {
    setOption: (option: EChartsOption, notMerge?: boolean) => void
    resize: () => void
    dispatchAction: (payload: Record<string, unknown>) => void
    on: (eventName: string, handler: (params: EChartsClickParams) => void) => void
    off: (eventName: string, handler?: (params: EChartsClickParams) => void) => void
    getDataURL: (opts?: { type?: string; pixelRatio?: number; backgroundColor?: string }) => string
    clear: () => void
    dispose: () => void
  }
}
