/**
 * GlobalBarChart Component
 * Phase 2.5 - ECharts bar chart for global mark comparison
 *
 * Displays a multi-series bar chart comparing peak counts, gene counts,
 * and other metrics across different marks.
 *
 * Features:
 * - Multi-series grouped/stacked bars
 * - Color-coded by mark type
 * - Metric toggle (peak count, gene count, coverage)
 * - Interactive tooltips with full statistics
 * - i18n support
 */

import { useMemo, useState } from 'react'
import ReactECharts from 'echarts-for-react'
import { Empty, Space, Typography, Segmented } from 'antd'
import { useTranslation } from 'react-i18next'
import echarts from '@/utils/echarts'
import type { ECOption } from '@/utils/echarts'
import { getChartToolbox } from '@/utils/chart-export'
import { getMarkColor, getMarkConfig } from '@/config/markConfigs'
import type { GlobalMarkSummary } from '@/types/globalCompare'
import type { TooltipFormatterParams, BarParams } from '@/types/echarts'

const { Text } = Typography

type BarMetric = 'total_peaks' | 'gene_count' | 'total_coverage_bp' | 'cell_type_count'

interface GlobalBarChartProps {
  /** Mark summary data for comparison */
  data: GlobalMarkSummary[]
  /** Loading state */
  loading?: boolean
  /** Chart height */
  height?: number
  /** Initial metric to display */
  initialMetric?: BarMetric
  /** Show metric selector */
  showMetricSelector?: boolean
  /** Sort by value */
  sortByValue?: boolean
}

/**
 * Format large numbers for display
 */
function formatNumber(value: number): string {
  if (value >= 1000000000) return `${(value / 1000000000).toFixed(1)}G`
  if (value >= 1000000) return `${(value / 1000000).toFixed(1)}M`
  if (value >= 1000) return `${(value / 1000).toFixed(1)}K`
  return value.toFixed(0)
}

/**
 * Format value based on metric type
 */
function formatMetricValue(value: number, metric: BarMetric): string {
  switch (metric) {
    case 'total_coverage_bp':
      if (value >= 1000000000) return `${(value / 1000000000).toFixed(2)} Gb`
      if (value >= 1000000) return `${(value / 1000000).toFixed(2)} Mb`
      if (value >= 1000) return `${(value / 1000).toFixed(1)} Kb`
      return `${value} bp`
    default:
      return formatNumber(value)
  }
}

/**
 * GlobalBarChart Component
 *
 * Renders a bar chart comparing marks across various metrics.
 *
 * @example
 * ```tsx
 * <GlobalBarChart
 *   data={markSummaries}
 *   initialMetric="total_peaks"
 *   height={400}
 * />
 * ```
 */
export function GlobalBarChart({
  data,
  loading = false,
  height = 400,
  initialMetric = 'total_peaks',
  showMetricSelector = true,
  sortByValue = true,
}: GlobalBarChartProps) {
  const { t } = useTranslation('globalCompare')
  const [metric, setMetric] = useState<BarMetric>(initialMetric)

  // Metric options for selector
  const metricOptions = useMemo(
    () => [
      { value: 'total_peaks' as BarMetric, label: t('charts.bar.totalPeaks', 'Total Peaks') },
      { value: 'gene_count' as BarMetric, label: t('charts.bar.geneCount', 'Gene Count') },
      { value: 'cell_type_count' as BarMetric, label: t('charts.bar.cellTypes', 'Cell Types') },
      { value: 'total_coverage_bp' as BarMetric, label: t('charts.bar.coverage', 'Coverage') },
    ],
    [t]
  )

  // Sort data by selected metric
  const sortedData = useMemo(() => {
    if (!data) return []
    const sorted = [...data]
    if (sortByValue) {
      sorted.sort((a, b) => b[metric] - a[metric])
    }
    return sorted
  }, [data, metric, sortByValue])

  // Get Y-axis label and unit
  const yAxisConfig = useMemo(() => {
    switch (metric) {
      case 'total_peaks':
        return {
          name: t('charts.bar.totalPeaks', 'Total Peaks'),
          formatter: (value: number) => formatNumber(value),
        }
      case 'gene_count':
        return {
          name: t('charts.bar.geneCount', 'Gene Count'),
          formatter: (value: number) => formatNumber(value),
        }
      case 'cell_type_count':
        return {
          name: t('charts.bar.cellTypes', 'Cell Types'),
          formatter: (value: number) => value.toString(),
        }
      case 'total_coverage_bp':
        return {
          name: t('charts.bar.coverage', 'Genomic Coverage'),
          formatter: (value: number) => {
            if (value >= 1000000000) return `${(value / 1000000000).toFixed(0)}G`
            if (value >= 1000000) return `${(value / 1000000).toFixed(0)}M`
            if (value >= 1000) return `${(value / 1000).toFixed(0)}K`
            return value.toString()
          },
        }
      default:
        return {
          name: 'Value',
          formatter: (value: number) => formatNumber(value),
        }
    }
  }, [metric, t])

  // ECharts option configuration
  const option: ECOption = useMemo(() => {
    if (!sortedData || sortedData.length === 0) {
      return {}
    }

    return {
      title: {
        text: t('charts.bar.title', 'Mark Comparison'),
        left: 'center',
        top: 10,
        textStyle: {
          fontSize: 16,
          fontWeight: 'bold',
        },
      },
      toolbox: getChartToolbox(
        `mark-comparison-${metric}`,
        t('export.saveImage', 'Save as Image')
      ),
      tooltip: {
        trigger: 'axis',
        axisPointer: { type: 'shadow' },
        formatter: (params: unknown) => {
          const arr = params as TooltipFormatterParams[]
          const p = arr[0]
          const markIndex = p.dataIndex
          const markData = sortedData[markIndex]
          const markConfig = getMarkConfig(markData.mark_type)

          const lines = [
            `<strong>${markConfig?.displayName || markData.mark_type}</strong>`,
            '',
            `${t('charts.bar.totalPeaks', 'Peaks')}: ${markData.total_peaks.toLocaleString()}`,
            `${t('charts.bar.geneCount', 'Genes')}: ${markData.gene_count.toLocaleString()}`,
            `${t('charts.bar.cellTypes', 'Cell Types')}: ${markData.cell_type_count}`,
            `${t('charts.bar.coverage', 'Coverage')}: ${formatMetricValue(markData.total_coverage_bp, 'total_coverage_bp')}`,
            '',
            `${t('charts.bar.avgSignal', 'Avg Signal')}: ${markData.avg_signal.toFixed(2)}`,
            `${t('charts.bar.avgEnrichment', 'Avg Enrichment')}: ${markData.avg_fold_enrichment.toFixed(2)}x`,
          ]

          return lines.join('<br/>')
        },
      },
      grid: {
        left: '12%',
        right: '8%',
        bottom: '20%',
        top: '18%',
      },
      xAxis: {
        type: 'category',
        data: sortedData.map((d) => {
          const config = getMarkConfig(d.mark_type)
          return config?.shortName || d.mark_type
        }),
        axisLabel: {
          rotate: 45,
          fontSize: 11,
          interval: 0,
        },
      },
      yAxis: {
        type: 'value',
        name: yAxisConfig.name,
        nameLocation: 'middle',
        nameGap: 50,
        axisLabel: {
          formatter: yAxisConfig.formatter,
        },
      },
      series: [
        {
          type: 'bar',
          data: sortedData.map((d) => ({
            value: d[metric],
            itemStyle: {
              color: new echarts.graphic.LinearGradient(0, 0, 0, 1, [
                { offset: 0, color: getMarkColor(d.mark_type) },
                { offset: 1, color: `${getMarkColor(d.mark_type)}88` },
              ]),
            },
          })),
          barMaxWidth: 50,
          label: {
            show: sortedData.length <= 15,
            position: 'top',
            formatter: (params: unknown) => {
              const p = params as BarParams
              return formatMetricValue(p.value as number, metric)
            },
            fontSize: 10,
            color: '#666',
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
  }, [sortedData, metric, yAxisConfig, t])

  // Handle empty state
  if (!data || data.length === 0) {
    return (
      <Empty
        image={Empty.PRESENTED_IMAGE_SIMPLE}
        description={t('charts.noData', 'No data available')}
        style={{ padding: 48 }}
      />
    )
  }

  return (
    <Space orientation="vertical" size="middle" style={{ width: '100%' }}>
      {/* Metric Selector */}
      {showMetricSelector && (
        <Space>
          <Text type="secondary">{t('charts.bar.metricLabel', 'Compare by')}:</Text>
          <Segmented
            options={metricOptions}
            value={metric}
            onChange={(value) => setMetric(value as BarMetric)}
            size="small"
          />
        </Space>
      )}

      {/* Bar Chart */}
      <ReactECharts
        echarts={echarts}
        option={option}
        style={{ height }}
        notMerge
        lazyUpdate
        showLoading={loading}
        data-testid="global-bar-chart"
      />
    </Space>
  )
}

export default GlobalBarChart
