/**
 * OverlapCellTypeChart Component
 * Phase 3.0 Phase 2 - Donut pie chart for cell type distribution
 *
 * Displays a donut pie chart showing the distribution of overlaps
 * across different cell types.
 *
 * Features:
 * - ECharts donut pie chart (radius: ['40%', '70%'])
 * - Color coding by cell type using getCellTypeColor()
 * - Percentage labels
 * - Legend on right side
 * - i18n support
 */

import { useMemo } from 'react'
import ReactECharts from 'echarts-for-react'
import { Empty } from 'antd'
import { useTranslation } from 'react-i18next'
import echarts from '@/utils/echarts'
import type { ECOption } from '@/utils/echarts'
import { getChartToolbox } from '@/utils/chart-export'
import { getCellTypeColor, getCellTypeLabel } from '@/config/cellTypeConfigs'

interface CellTypeDistData {
  cell_type: string
  count: number
}

interface OverlapCellTypeChartProps {
  /** Cell type distribution data from summary */
  data: CellTypeDistData[]
  /** Loading state */
  loading?: boolean
  /** Chart height */
  height?: number
}

/**
 * OverlapCellTypeChart Component
 *
 * Donut pie chart showing overlap counts by cell type.
 * Uses cell type-specific colors from getCellTypeColor() for visual consistency.
 *
 * @example
 * ```tsx
 * <OverlapCellTypeChart
 *   data={summary.by_cell_type}
 *   loading={isLoading}
 * />
 * ```
 */
export function OverlapCellTypeChart({
  data,
  loading = false,
  height = 350,
}: OverlapCellTypeChartProps) {
  const { t, i18n } = useTranslation('overlap')

  // Sort data by count descending for better visualization
  const sortedData = useMemo(() => {
    return [...data].sort((a, b) => b.count - a.count)
  }, [data])

  // Calculate total for percentage
  const total = useMemo(() => {
    return sortedData.reduce((sum, item) => sum + item.count, 0)
  }, [sortedData])

  const option: ECOption = useMemo(() => {
    if (!sortedData || sortedData.length === 0) {
      return {}
    }

    return {
      title: {
        text: t('charts.cellTypeDistribution', 'Overlap Distribution by Cell Type'),
        left: 'center',
        top: 10,
        textStyle: {
          fontSize: 14,
          fontWeight: 'bold',
        },
      },
      toolbox: getChartToolbox(
        t('charts.cellTypeDistribution', 'Cell Type Distribution'),
        t('export.saveImage', 'Save as Image')
      ),
      tooltip: {
        trigger: 'item',
        formatter: (params: any) => {
          const cellType = params.name
          const displayName = getCellTypeLabel(cellType, i18n.language)
          const percentage = ((params.value / total) * 100).toFixed(1)
          return [
            `<strong>${displayName}</strong>`,
            `${t('charts.overlapCount', 'Overlaps')}: ${params.value.toLocaleString()}`,
            `${t('charts.percentage', 'Percentage')}: ${percentage}%`,
          ].join('<br/>')
        },
      },
      legend: {
        orient: 'vertical',
        right: 'right',
        top: 'middle',
        formatter: (name: string) => {
          const item = sortedData.find((d) => d.cell_type === name)
          const displayName = getCellTypeLabel(name, i18n.language)
          if (item) {
            const percentage = ((item.count / total) * 100).toFixed(1)
            return `${displayName} (${percentage}%)`
          }
          return displayName
        },
      },
      series: [
        {
          type: 'pie',
          radius: ['40%', '70%'],
          center: ['40%', '55%'],
          avoidLabelOverlap: true,
          data: sortedData.map((d) => ({
            name: d.cell_type,
            value: d.count,
            itemStyle: {
              color: getCellTypeColor(d.cell_type),
            },
          })),
          emphasis: {
            itemStyle: {
              shadowBlur: 10,
              shadowOffsetX: 0,
              shadowColor: 'rgba(0, 0, 0, 0.5)',
            },
            label: {
              show: true,
              fontWeight: 'bold',
            },
          },
          label: {
            show: true,
            formatter: (params: any) => {
              const percentage = ((params.value / total) * 100).toFixed(1)
              if (parseFloat(percentage) < 5) {
                return '' // Hide labels for small slices
              }
              return `${getCellTypeLabel(params.name, i18n.language)}\n${params.value.toLocaleString()} (${percentage}%)`
            },
            fontSize: 11,
          },
          labelLine: {
            show: true,
            length: 15,
            length2: 10,
          },
        },
      ],
    }
  }, [sortedData, total, t, i18n.language])

  // Handle empty state
  if (!data || data.length === 0) {
    return (
      <Empty
        image={Empty.PRESENTED_IMAGE_SIMPLE}
        description={t('charts.noCellTypeData', 'No cell type distribution data available')}
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
      data-testid="overlap-cell-type-chart"
    />
  )
}

export default OverlapCellTypeChart
