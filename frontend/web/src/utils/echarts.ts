/**
 * ECharts 按需导入配置（基于 ECharts 6）
 *
 * 仅导入需要的组件，减少 bundle 大小
 * 当前导入：PieChart, BarChart（约 280KB gzip）
 */

import * as echarts from 'echarts/core'

// 图表类型
import { PieChart, BarChart } from 'echarts/charts'

// 组件
import {
  TitleComponent,
  TooltipComponent,
  LegendComponent,
  GridComponent,
  ToolboxComponent
} from 'echarts/components'

// 渲染器
import { CanvasRenderer } from 'echarts/renderers'

// 类型定义
import type {
  PieSeriesOption,
  BarSeriesOption
} from 'echarts/charts'

import type {
  TitleComponentOption,
  TooltipComponentOption,
  LegendComponentOption,
  GridComponentOption,
  ToolboxComponentOption
} from 'echarts/components'

// 组合选项类型
export type ECOption = echarts.ComposeOption<
  | PieSeriesOption
  | BarSeriesOption
  | TitleComponentOption
  | TooltipComponentOption
  | LegendComponentOption
  | GridComponentOption
  | ToolboxComponentOption
>

// 注册组件
echarts.use([
  PieChart,
  BarChart,
  TitleComponent,
  TooltipComponent,
  LegendComponent,
  GridComponent,
  ToolboxComponent,
  CanvasRenderer
])

export default echarts
