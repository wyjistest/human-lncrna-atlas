/**
 * Response Time Distribution Chart
 * Displays response time distribution as a bar chart with color gradient
 */

import { useMemo } from 'react'
import ReactECharts from 'echarts-for-react'
import { Empty } from 'antd'
import echarts from '@/utils/echarts'
import type { ECOption } from '@/utils/echarts'
import type { ResponseTimeDistribution } from '@/types/monitoring'
import { escapeHtml } from '@/utils/escapeHtml'

interface ResponseTimeChartProps {
  data?: ResponseTimeDistribution
}

/**
 * Color gradient from green (fast) to red (slow)
 * Maps to buckets: 0-50ms, 50-100ms, 100-200ms, 200-500ms, 500ms+
 */
const BUCKET_COLORS = [
  '#52c41a', // Green - 0-50ms (fast)
  '#13c2c2', // Cyan - 50-100ms
  '#faad14', // Yellow - 100-200ms
  '#fa8c16', // Orange - 200-500ms
  '#f5222d'  // Red - 500ms+ (slow)
]

export function ResponseTimeChart({ data }: ResponseTimeChartProps) {
  const option: ECOption = useMemo(() => {
    if (!data || !data.buckets.length) {
      return {} as ECOption
    }

    return {
      tooltip: {
        trigger: 'axis',
        axisPointer: {
          type: 'shadow'
        },
        formatter: (params: unknown) => {
          const p = (params as { name: string; value: number }[])[0]
          return `${escapeHtml(p.name)}<br/>Requests: ${p.value.toLocaleString()}`
        }
      },

      grid: {
        left: '10%',
        right: '10%',
        bottom: '15%',
        top: '10%'
      },

      xAxis: {
        type: 'category',
        data: data.buckets,
        axisLabel: {
          fontSize: 11
        },
        name: 'Response Time',
        nameLocation: 'middle',
        nameGap: 30
      },

      yAxis: {
        type: 'value',
        name: 'Requests',
        nameLocation: 'middle',
        nameGap: 50,
        axisLabel: {
          formatter: (value: number) => {
            if (value >= 1000000) return `${(value / 1000000).toFixed(1)}M`
            if (value >= 1000) return `${(value / 1000).toFixed(1)}K`
            return value.toString()
          }
        }
      },

      series: [
        {
          type: 'bar',
          data: data.counts.map((count, index) => ({
            value: count,
            itemStyle: {
              color: new echarts.graphic.LinearGradient(0, 0, 0, 1, [
                { offset: 0, color: BUCKET_COLORS[index] || BUCKET_COLORS[4] },
                { offset: 1, color: adjustColorBrightness(BUCKET_COLORS[index] || BUCKET_COLORS[4], -20) }
              ])
            }
          })),
          barWidth: '60%'
        }
      ]
    }
  }, [data])

  if (!data || !data.buckets.length) {
    return (
      <div style={{ height: 300, display: 'flex', alignItems: 'center', justifyContent: 'center' }}>
        <Empty description="No response time data available" />
      </div>
    )
  }

  return (
    <ReactECharts
      echarts={echarts}
      option={option}
      style={{ height: 300 }}
      notMerge={true}
      lazyUpdate={true}
    />
  )
}

/**
 * Adjust hex color brightness
 */
function adjustColorBrightness(hex: string, percent: number): string {
  const num = parseInt(hex.replace('#', ''), 16)
  const amt = Math.round(2.55 * percent)
  const R = Math.max(0, Math.min(255, (num >> 16) + amt))
  const G = Math.max(0, Math.min(255, ((num >> 8) & 0x00ff) + amt))
  const B = Math.max(0, Math.min(255, (num & 0x0000ff) + amt))
  return `#${(0x1000000 + R * 0x10000 + G * 0x100 + B).toString(16).slice(1)}`
}
