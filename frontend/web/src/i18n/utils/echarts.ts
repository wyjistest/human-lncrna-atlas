/**
 * ECharts 按需导入配置（基于 ECharts 6）
 *
 * 仅导入需要的组件，减少 bundle 大小
 * 当前导入：PieChart, BarChart, LineChart, GaugeChart, BoxplotChart, HeatmapChart
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
} from 'echarts/charts'

// 组件
import {
  TitleComponent,
  TooltipComponent,
  LegendComponent,
  GridComponent,
  ToolboxComponent,
  VisualMapComponent,
} from 'echarts/components'

// 渲染器
import { CanvasRenderer } from 'echarts/renderers'

// 类型定义
import type {
  PieSeriesOption,
  BarSeriesOption,
  LineSeriesOption,
  GaugeSeriesOption,
  BoxplotSeriesOption,
  HeatmapSeriesOption,
} from 'echarts/charts'

import type {
  TitleComponentOption,
  TooltipComponentOption,
  LegendComponentOption,
  GridComponentOption,
  ToolboxComponentOption,
  VisualMapComponentOption,
} from 'echarts/components'

// 组合选项类型
export type ECOption = echarts.ComposeOption<
  | PieSeriesOption
  | BarSeriesOption
  | LineSeriesOption
  | GaugeSeriesOption
  | BoxplotSeriesOption
  | HeatmapSeriesOption
  | TitleComponentOption
  | TooltipComponentOption
  | LegendComponentOption
  | GridComponentOption
  | ToolboxComponentOption
  | VisualMapComponentOption
>

// 注册组件
echarts.use([
  PieChart,
  BarChart,
  LineChart,
  GaugeChart,
  BoxplotChart,
  HeatmapChart,
  TitleComponent,
  TooltipComponent,
  LegendComponent,
  GridComponent,
  ToolboxComponent,
  VisualMapComponent,
  CanvasRenderer,
])

export default echarts
