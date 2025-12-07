/**
 * System Gauge Component
 * Displays CPU/Memory usage as a gauge chart with color segments
 */

import { useMemo } from 'react'
import ReactECharts from 'echarts-for-react'
import echarts from '@/utils/echarts'
import type { ECOption } from '@/utils/echarts'

interface SystemGaugeProps {
  /** Current value (0-100) */
  value: number
  /** Gauge title */
  title: string
  /** Optional subtitle (e.g., "2.1 / 8.0 GB") */
  subtitle?: string
}

/**
 * Color thresholds for gauge segments:
 * - 0-60%: Green (healthy)
 * - 60-85%: Yellow (warning)
 * - 85-100%: Red (critical)
 */
const GAUGE_COLORS: [number, string][] = [
  [0.6, '#52c41a'],  // Green
  [0.85, '#faad14'], // Yellow
  [1, '#f5222d']     // Red
]

export function SystemGauge({ value, title, subtitle }: SystemGaugeProps) {
  const option: ECOption = useMemo(() => {
    return {
      series: [
        {
          type: 'gauge',
          startAngle: 200,
          endAngle: -20,
          min: 0,
          max: 100,
          splitNumber: 10,
          progress: {
            show: true,
            width: 18
          },
          pointer: {
            show: false
          },
          axisLine: {
            lineStyle: {
              width: 18,
              color: GAUGE_COLORS
            }
          },
          axisTick: {
            show: false
          },
          splitLine: {
            show: false
          },
          axisLabel: {
            show: false
          },
          anchor: {
            show: false
          },
          title: {
            show: true,
            offsetCenter: [0, '70%'],
            fontSize: 12,
            color: '#8c8c8c'
          },
          detail: {
            valueAnimation: true,
            fontSize: 24,
            fontWeight: 'bold',
            formatter: '{value}%',
            color: 'inherit',
            offsetCenter: [0, '0%']
          },
          data: [
            {
              value: Math.round(value * 10) / 10,
              name: subtitle || title
            }
          ]
        }
      ]
    }
  }, [value, title, subtitle])

  return (
    <ReactECharts
      echarts={echarts}
      option={option}
      style={{ height: 200 }}
      notMerge={true}
      lazyUpdate={true}
    />
  )
}
