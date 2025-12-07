/**
 * Error Rate Trend Chart
 * Displays error rate trend over the last 10 minutes as a line chart
 */

import { useMemo } from 'react'
import ReactECharts from 'echarts-for-react'
import { Empty } from 'antd'
import echarts from '@/utils/echarts'
import type { ECOption } from '@/utils/echarts'
import type { ErrorTrend } from '@/types/monitoring'

interface ErrorTrendChartProps {
  data?: ErrorTrend
}

export function ErrorTrendChart({ data }: ErrorTrendChartProps) {
  const option: ECOption = useMemo(() => {
    if (!data || !data.timestamps.length) {
      return {} as ECOption
    }

    return {
      tooltip: {
        trigger: 'axis',
        formatter: (params: unknown) => {
          const p = (params as { name: string; value: number }[])[0]
          const percentage = (p.value * 100).toFixed(3)
          return `${p.name}<br/>Error Rate: ${percentage}%`
        }
      },

      grid: {
        left: '12%',
        right: '10%',
        bottom: '15%',
        top: '10%'
      },

      xAxis: {
        type: 'category',
        data: data.timestamps,
        axisLabel: {
          fontSize: 11
        },
        name: 'Time',
        nameLocation: 'middle',
        nameGap: 30,
        boundaryGap: false
      },

      yAxis: {
        type: 'value',
        name: 'Error Rate (%)',
        nameLocation: 'middle',
        nameGap: 45,
        axisLabel: {
          formatter: (value: number) => `${(value * 100).toFixed(2)}%`
        },
        min: 0
      },

      series: [
        {
          type: 'line',
          data: data.error_rates,
          smooth: true,
          symbol: 'circle',
          symbolSize: 6,
          lineStyle: {
            color: '#f5222d',
            width: 2
          },
          itemStyle: {
            color: '#f5222d'
          },
          areaStyle: {
            color: new echarts.graphic.LinearGradient(0, 0, 0, 1, [
              { offset: 0, color: 'rgba(245, 34, 45, 0.4)' },
              { offset: 1, color: 'rgba(245, 34, 45, 0.05)' }
            ])
          }
        }
      ]
    }
  }, [data])

  if (!data || !data.timestamps.length) {
    return (
      <div style={{ height: 300, display: 'flex', alignItems: 'center', justifyContent: 'center' }}>
        <Empty description="No error trend data available" />
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
