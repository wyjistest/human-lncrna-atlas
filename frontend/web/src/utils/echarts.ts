/**
 * ECharts 按需导入配置（基于 ECharts 6）
 *
 * 仅导入需要的组件，减少 bundle 大小
 * 当前导入：PieChart, BarChart, LineChart, GaugeChart, BoxplotChart, HeatmapChart, RadarChart
 */

import * as echarts from 'echarts/core'

// 图表类型
import {
  PieChart,
  BarChart,
  LineChart,
  GaugeChart,
  BoxplotChart,
  HeatmapChart,
  RadarChart,
  ScatterChart,
  SankeyChart,
  GraphChart,
} from 'echarts/charts'

// 组件
import {
  TitleComponent,
  TooltipComponent,
  LegendComponent,
  GridComponent,
  ToolboxComponent,
  VisualMapComponent,
  RadarComponent,
} from 'echarts/components'

// ECharts v6: grid.containLabel 已废弃但仍被历史配置使用；注册 LegacyGridContainLabel 可避免控制台警告
// 参考：https://echarts.apache.org/en/option.html#grid.containLabel
import { LegacyGridContainLabel } from 'echarts/features'

// 渲染器
import { CanvasRenderer, SVGRenderer } from 'echarts/renderers'

// 类型定义
import type {
  PieSeriesOption,
  BarSeriesOption,
  LineSeriesOption,
  GaugeSeriesOption,
  BoxplotSeriesOption,
  HeatmapSeriesOption,
  RadarSeriesOption,
  ScatterSeriesOption,
  SankeySeriesOption,
  GraphSeriesOption,
} from 'echarts/charts'

import type {
  TitleComponentOption,
  TooltipComponentOption,
  LegendComponentOption,
  GridComponentOption,
  ToolboxComponentOption,
  VisualMapComponentOption,
  RadarComponentOption,
} from 'echarts/components'

// 组合选项类型
export type ECOption = echarts.ComposeOption<
  | PieSeriesOption
  | BarSeriesOption
  | LineSeriesOption
  | GaugeSeriesOption
  | BoxplotSeriesOption
  | HeatmapSeriesOption
  | RadarSeriesOption
  | ScatterSeriesOption
  | SankeySeriesOption
  | GraphSeriesOption
  | TitleComponentOption
  | TooltipComponentOption
  | LegendComponentOption
  | GridComponentOption
  | ToolboxComponentOption
  | VisualMapComponentOption
  | RadarComponentOption
>

// 注册组件
echarts.use([
  PieChart,
  BarChart,
  LineChart,
  GaugeChart,
  BoxplotChart,
  HeatmapChart,
  RadarChart,
  ScatterChart,
  SankeyChart,
  GraphChart,
  TitleComponent,
  TooltipComponent,
  LegendComponent,
  GridComponent,
  ToolboxComponent,
  VisualMapComponent,
  RadarComponent,
  LegacyGridContainLabel,
  CanvasRenderer,
  SVGRenderer,
])

export default echarts
