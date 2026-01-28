/**
 * 图表导出工具
 * 使用 ECharts 内置 getDataURL 导出 PNG
 */

import type { EChartsInstance } from 'echarts-for-react'
import echarts from './echarts'
import type { ECOption } from './echarts'

export interface ChartExportOptions {
  pixelRatio?: number
  backgroundColor?: string
}

/**
 * 导出图表为 PNG
 */
export function exportChartToPNG(
  chartInstance: EChartsInstance | null | undefined,
  filename: string,
  options: ChartExportOptions = {}
): boolean {
  if (!chartInstance) {
    console.warn('[ChartExport] No chart instance provided')
    return false
  }

  const { pixelRatio = 2, backgroundColor = '#fff' } = options

  try {
    const url = chartInstance.getDataURL({
      type: 'png',
      pixelRatio,
      backgroundColor
    })

    const link = document.createElement('a')
    link.href = url
    link.download = `${filename}-${Date.now()}.png`
    link.click()

    return true
  } catch (error) {
    console.error('[ChartExport] Failed to export chart:', error)
    return false
  }
}

/**
 * 导出图表为 SVG（使用离屏 SVG renderer 渲染）
 */
export function exportChartToSVG(
  chartInstance: EChartsInstance | null | undefined,
  filename: string,
  options: ChartExportOptions = {}
): boolean {
  if (!chartInstance) {
    console.warn('[ChartExport] No chart instance provided')
    return false
  }

  const { backgroundColor = '#fff' } = options

  const width = typeof chartInstance.getWidth === 'function' ? chartInstance.getWidth() : 800
  const height = typeof chartInstance.getHeight === 'function' ? chartInstance.getHeight() : 600

  const container = document.createElement('div')
  container.style.position = 'fixed'
  container.style.left = '-9999px'
  container.style.top = '-9999px'
  container.style.width = `${width}px`
  container.style.height = `${height}px`
  document.body.appendChild(container)

  let svgChart: ReturnType<typeof echarts.init> | null = null

  try {
    svgChart = echarts.init(container, undefined, { renderer: 'svg', width, height })
    const option = (chartInstance.getOption?.() ?? {}) as ECOption
    svgChart.setOption(option, { notMerge: true, lazyUpdate: false })

    const url = svgChart.getDataURL({
      type: 'svg',
      backgroundColor,
    })

    const link = document.createElement('a')
    link.href = url
    link.download = `${filename}-${Date.now()}.svg`
    link.click()

    return true
  } catch (error) {
    console.error('[ChartExport] Failed to export chart:', error)
    return false
  } finally {
    try {
      svgChart?.dispose()
    } catch {
      // ignore cleanup errors
    }
    if (container.parentNode) {
      container.parentNode.removeChild(container)
    }
  }
}

/**
 * 生成 ECharts toolbox 配置（内置保存图片按钮）
 * @param filename - 导出文件名
 * @param saveImageTitle - "保存为图片" 按钮的提示文本（需要调用方传入翻译后的字符串）
 */
export function getChartToolbox(filename: string, saveImageTitle: string = 'Save as image') {
  return {
    show: true,
    right: 20,
    top: 10,
    feature: {
      saveAsImage: {
        type: 'png' as const,  // 使用 as const 确保类型为字面量 'png'
        name: filename,
        pixelRatio: 2,
        title: saveImageTitle,
        backgroundColor: '#fff'
      }
    }
  }
}
