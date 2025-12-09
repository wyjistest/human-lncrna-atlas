/**
 * BoxPlotChart Component
 * Phase 2.5 - ECharts box plot for signal distribution comparison
 *
 * Displays box plots showing the distribution of signal values
 * for each mark type, enabling comparison of variability and spread.
 *
 * Features:
 * - Box plot with min, Q1, median, Q3, max
 * - Outlier display
 * - Color-coded by mark type
 * - Interactive tooltips with statistics
 * - i18n support
 */

import { useMemo } from 'react'
import ReactECharts from 'echarts-for-react'
import { Empty } from 'antd'
import { useTranslation } from 'react-i18next'
import echarts from '@/utils/echarts'
import type { ECOption } from '@/utils/echarts'
import { getChartToolbox } from '@/utils/chart-export'
import { getMarkColor, getMarkConfig } from '@/config/markConfigs'
import type { BoxPlotData } from '@/types/globalCompare'

interface BoxPlotChartProps {
  /** Box plot data for each mark */
  data: BoxPlotData[]
  /** Loading state */
  loading?: boolean
  /** Chart height */
  height?: number
  /** Y-axis label */
  yAxisLabel?: string
  /** Show outliers */
  showOutliers?: boolean
}

/**
 * Format value for tooltip display
 */
function formatValue(value: number): string {
  if (value >= 1000000) return `${(value / 1000000).toFixed(2)}M`
  if (value >= 1000) return `${(value / 1000).toFixed(2)}K`
  return value.toFixed(2)
}

/**
 * BoxPlotChart Component
 *
 * Renders a box plot chart showing signal distribution for multiple marks.
 *
 * @example
 * ```tsx
 * <BoxPlotChart
 *   data={boxPlotData}
 *   yAxisLabel="Signal Value"
 *   height={400}
 * />
 * ```
 */
export function BoxPlotChart({
  data,
  loading = false,
  height = 400,
  yAxisLabel,
  showOutliers = true,
}: BoxPlotChartProps) {
  const { t } = useTranslation('globalCompare')

  // Sort data by median value descending
  const sortedData = useMemo(() => {
    return [...data].sort((a, b) => b.median - a.median)
  }, [data])

  // ECharts option configuration
  const option: ECOption = useMemo(() => {
    if (!sortedData || sortedData.length === 0) {
      return {}
    }

    // Prepare boxplot data: [min, Q1, median, Q3, max]
    const boxplotData = sortedData.map((item) => ({
      value: [item.min, item.q1, item.median, item.q3, item.max],
      itemStyle: {
        color: getMarkColor(item.mark_type),
        borderColor: getMarkColor(item.mark_type),
      },
    }))

    // Prepare outlier data if available
    const outlierData: Array<[number, number]> = []
    if (showOutliers) {
      sortedData.forEach((item, idx) => {
        if (item.outliers && item.outliers.length > 0) {
          item.outliers.forEach((outlier) => {
            outlierData.push([idx, outlier])
          })
        }
      })
    }

    // X-axis labels
    const xAxisLabels = sortedData.map((item) => {
      const config = getMarkConfig(item.mark_type)
      return config?.shortName || item.mark_type
    })

    return {
      title: {
        text: t('charts.boxplot.title', 'Signal Distribution by Mark'),
        left: 'center',
        top: 10,
        textStyle: {
          fontSize: 16,
          fontWeight: 'bold',
        },
      },
      toolbox: getChartToolbox(
        t('charts.boxplot.title', 'Signal Distribution'),
        t('export.saveImage', 'Save as Image')
      ),
      tooltip: {
        trigger: 'item',
        formatter: (params: any) => {
          if (params.componentType === 'series' && params.seriesType === 'boxplot') {
            const [min, q1, median, q3, max] = params.data.value
            const markIndex = params.dataIndex
            const markData = sortedData[markIndex]
            const markConfig = getMarkConfig(markData.mark_type)
            const markName = markConfig?.displayName || markData.mark_type

            return [
              `<strong>${markName}</strong>`,
              `${t('charts.boxplot.max', 'Max')}: ${formatValue(max)}`,
              `${t('charts.boxplot.q3', 'Q3 (75%)')}: ${formatValue(q3)}`,
              `${t('charts.boxplot.median', 'Median')}: ${formatValue(median)}`,
              `${t('charts.boxplot.q1', 'Q1 (25%)')}: ${formatValue(q1)}`,
              `${t('charts.boxplot.min', 'Min')}: ${formatValue(min)}`,
              `${t('charts.boxplot.sampleSize', 'Sample Size')}: ${markData.n.toLocaleString()}`,
            ].join('<br/>')
          }
          // Outlier tooltip
          if (params.componentType === 'series' && params.seriesType === 'scatter') {
            return `${t('charts.boxplot.outlier', 'Outlier')}: ${formatValue(params.data[1])}`
          }
          return ''
        },
      },
      grid: {
        left: '12%',
        right: '8%',
        bottom: '18%',
        top: '18%',
      },
      xAxis: {
        type: 'category',
        data: xAxisLabels,
        axisLabel: {
          rotate: 45,
          fontSize: 11,
          interval: 0,
        },
        splitArea: {
          show: false,
        },
      },
      yAxis: {
        type: 'value',
        name: yAxisLabel || t('charts.boxplot.yAxis', 'Signal Value'),
        nameLocation: 'middle',
        nameGap: 50,
        splitArea: {
          show: true,
          areaStyle: {
            color: ['#fff', '#fafafa'],
          },
        },
        axisLabel: {
          formatter: (value: number) => formatValue(value),
        },
      },
      series: [
        {
          name: t('charts.boxplot.seriesName', 'Signal Distribution'),
          type: 'boxplot',
          data: boxplotData,
          itemStyle: {
            borderWidth: 2,
          },
          emphasis: {
            itemStyle: {
              shadowBlur: 10,
              shadowOffsetX: 0,
              shadowColor: 'rgba(0, 0, 0, 0.3)',
            },
          },
        },
        // Outliers scatter series
        ...(showOutliers && outlierData.length > 0
          ? [
              {
                name: t('charts.boxplot.outliers', 'Outliers'),
                type: 'scatter' as const,
                data: outlierData,
                itemStyle: {
                  color: '#ff4d4f',
                },
                symbolSize: 6,
              },
            ]
          : []),
      ],
    }
  }, [sortedData, showOutliers, yAxisLabel, t])

  // Handle empty state
  if (!data || data.length === 0) {
    return (
      <Empty
        image={Empty.PRESENTED_IMAGE_SIMPLE}
        description={t('charts.noData', 'No data available for box plot')}
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
      data-testid="boxplot-chart"
    />
  )
}

export default BoxPlotChart
