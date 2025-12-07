/**
 * OverlapMarkDistChart Component
 * Phase 3.0 Phase 2 - Bar chart for mark type distribution
 *
 * Displays a bar chart showing the distribution of overlaps
 * across different histone modification mark types.
 *
 * Features:
 * - ECharts bar chart visualization
 * - X-axis: Mark types
 * - Y-axis: Overlap count
 * - Color coding by mark type using MARK_CONFIGS
 * - Tooltip with count and average strength
 * - i18n support
 */

import { useMemo } from 'react'
import ReactECharts from 'echarts-for-react'
import { Empty } from 'antd'
import { useTranslation } from 'react-i18next'
import echarts from '@/utils/echarts'
import type { ECOption } from '@/utils/echarts'
import { getChartToolbox } from '@/utils/chart-export'
import { getMarkColor, MARK_CONFIGS } from '@/config/markConfigs'
import type { MarkType } from '@/types/chipseq'

interface MarkDistData {
  mark_type: string
  count: number
  avg_strength: number
}

interface OverlapMarkDistChartProps {
  /** Mark type distribution data from summary */
  data: MarkDistData[]
  /** Loading state */
  loading?: boolean
  /** Chart height */
  height?: number
}

/**
 * OverlapMarkDistChart Component
 *
 * Bar chart showing overlap counts by mark type.
 * Uses mark-specific colors from MARK_CONFIGS for visual consistency.
 *
 * @example
 * ```tsx
 * <OverlapMarkDistChart
 *   data={summary.by_mark_type}
 *   loading={isLoading}
 * />
 * ```
 */
export function OverlapMarkDistChart({
  data,
  loading = false,
  height = 350,
}: OverlapMarkDistChartProps) {
  const { t } = useTranslation('overlap')

  // Sort data by count descending for better visualization
  const sortedData = useMemo(() => {
    return [...data].sort((a, b) => b.count - a.count)
  }, [data])

  const option: ECOption = useMemo(() => {
    if (!sortedData || sortedData.length === 0) {
      return {}
    }

    return {
      title: {
        text: t('charts.markDistribution', 'Overlap Distribution by Mark Type'),
        left: 'center',
        top: 10,
        textStyle: {
          fontSize: 14,
          fontWeight: 'bold',
        },
      },
      toolbox: getChartToolbox(
        t('charts.markDistribution', 'Mark Distribution'),
        t('export.saveImage', 'Save as Image')
      ),
      tooltip: {
        trigger: 'axis',
        axisPointer: { type: 'shadow' },
        formatter: (params: any) => {
          const p = params[0]
          const markType = p.name as MarkType
          const config = MARK_CONFIGS[markType]
          const displayName = config?.displayName || markType
          const dataItem = sortedData.find((d) => d.mark_type === markType)

          const lines = [
            `<strong>${displayName}</strong>`,
            `${t('charts.overlapCount', 'Overlaps')}: ${p.value.toLocaleString()}`,
          ]

          if (dataItem?.avg_strength) {
            lines.push(
              `${t('charts.avgStrength', 'Avg Strength')}: ${dataItem.avg_strength.toFixed(2)}`
            )
          }

          return lines.join('<br/>')
        },
      },
      grid: {
        left: '12%',
        right: '8%',
        bottom: '20%',
        top: '15%',
      },
      xAxis: {
        type: 'category',
        data: sortedData.map((d) => d.mark_type),
        axisLabel: {
          rotate: 45,
          fontSize: 11,
          formatter: (value: string) => {
            const config = MARK_CONFIGS[value as MarkType]
            return config?.shortName || value
          },
        },
      },
      yAxis: {
        type: 'value',
        name: t('charts.overlapCount', 'Overlap Count'),
        nameLocation: 'middle',
        nameGap: 45,
        axisLabel: {
          formatter: (value: number) => {
            if (value >= 1000000) return `${(value / 1000000).toFixed(1)}M`
            if (value >= 1000) return `${(value / 1000).toFixed(1)}K`
            return value.toString()
          },
        },
      },
      series: [
        {
          type: 'bar',
          data: sortedData.map((d) => ({
            value: d.count,
            itemStyle: {
              color: new echarts.graphic.LinearGradient(0, 0, 0, 1, [
                { offset: 0, color: getMarkColor(d.mark_type as MarkType) },
                { offset: 1, color: `${getMarkColor(d.mark_type as MarkType)}88` },
              ]),
            },
          })),
          barMaxWidth: 50,
          label: {
            show: sortedData.length <= 10,
            position: 'top',
            formatter: (params: any) => {
              if (params.value >= 1000) {
                return `${(params.value / 1000).toFixed(1)}K`
              }
              return params.value.toLocaleString()
            },
            fontSize: 10,
          },
          emphasis: {
            itemStyle: {
              shadowBlur: 10,
              shadowOffsetX: 0,
              shadowColor: 'rgba(0, 0, 0, 0.3)',
            },
          },
        },
      ],
    }
  }, [sortedData, t])

  // Handle empty state
  if (!data || data.length === 0) {
    return (
      <Empty
        image={Empty.PRESENTED_IMAGE_SIMPLE}
        description={t('charts.noMarkData', 'No mark distribution data available')}
        style={{ padding: 48 }}
      />
    )
  }

  return (
    <ReactECharts
      echarts={echarts}
      option={option}
      style={{ height }}
      notMerge
      lazyUpdate
      showLoading={loading}
      data-testid="overlap-mark-dist-chart"
    />
  )
}

export default OverlapMarkDistChart
