/**
 * CellLineMatrixChart Component
 * Phase 2.5 - ECharts heatmap for cell line x mark matrix
 *
 * Displays a heatmap showing the relationship between cell types and marks.
 * X-axis: Mark types, Y-axis: Cell types, Color intensity: Selected metric
 *
 * Features:
 * - Heatmap visualization with configurable metrics
 * - Interactive cell clicking
 * - Color scale based on metric type
 * - Detailed tooltips
 * - i18n support
 */

import { useMemo, useRef, useEffect } from 'react'
import ReactECharts from 'echarts-for-react'
import type { EChartsInstance } from 'echarts-for-react'
import { Empty, Space, Typography, Segmented, Spin } from 'antd'
import { useTranslation } from 'react-i18next'
import echarts from '@/utils/echarts'
import type { ECOption } from '@/utils/echarts'
import { getChartToolbox } from '@/utils/chart-export'
import { getMarkConfig } from '@/config/markConfigs'
import { getCellTypeLabel } from '@/config/cellTypeConfigs'
import type { CellLineMatrixResponse, CellLineMatrixMetric } from '@/types/globalCompare'
import type { MarkType } from '@/types/chipseq'
import type { HeatmapParams, VisualMapFormatter } from '@/types/echarts'

const { Text } = Typography

interface CellLineMatrixChartProps {
  /** Matrix data from API */
  data: CellLineMatrixResponse | undefined
  /** Current metric being displayed */
  metric: CellLineMatrixMetric
  /** Callback when metric changes */
  onMetricChange?: (metric: CellLineMatrixMetric) => void
  /** Callback when a cell is clicked */
  onCellClick?: (cellType: string, markType: MarkType) => void
  /** Loading state */
  loading?: boolean
  /** Chart height (auto-calculated if not specified) */
  height?: number
  /** Show metric selector */
  showMetricSelector?: boolean
}

/**
 * Format metric value for display
 */
function formatMetricValue(value: number | null, metric: CellLineMatrixMetric): string {
  if (value === null || value === undefined) return 'N/A'

  switch (metric) {
    case 'peak_count':
    case 'gene_count':
      if (value >= 1000000) return `${(value / 1000000).toFixed(1)}M`
      if (value >= 1000) return `${(value / 1000).toFixed(1)}K`
      return value.toLocaleString()
    case 'avg_signal':
    case 'avg_fold_enrichment':
      return value.toFixed(2)
    case 'total_coverage_bp':
      if (value >= 1000000000) return `${(value / 1000000000).toFixed(2)} Gb`
      if (value >= 1000000) return `${(value / 1000000).toFixed(2)} Mb`
      if (value >= 1000) return `${(value / 1000).toFixed(1)} Kb`
      return `${value} bp`
    default:
      return value.toString()
  }
}

/**
 * Get color range based on metric type
 */
function getColorRange(metric: CellLineMatrixMetric): string[] {
  const schemes: Record<CellLineMatrixMetric, string[]> = {
    peak_count: ['#f6ffed', '#52c41a', '#135200'],
    gene_count: ['#fff0f6', '#eb2f96', '#9e1068'],
    avg_signal: ['#fff7e6', '#fa8c16', '#ad4e00'],
    total_coverage_bp: ['#f0f5ff', '#1890ff', '#003a8c'],
    avg_fold_enrichment: ['#f9f0ff', '#722ed1', '#391085'],
  }
  return schemes[metric] || schemes.peak_count
}

/**
 * CellLineMatrixChart Component
 *
 * Renders a heatmap matrix showing cell type x mark relationships.
 *
 * @example
 * ```tsx
 * <CellLineMatrixChart
 *   data={matrixData}
 *   metric="peak_count"
 *   onMetricChange={(m) => setMetric(m)}
 *   onCellClick={(cell, mark) => console.log(cell, mark)}
 * />
 * ```
 */
export function CellLineMatrixChart({
  data,
  metric,
  onMetricChange,
  onCellClick,
  loading = false,
  height,
  showMetricSelector = true,
}: CellLineMatrixChartProps) {
  const { t, i18n } = useTranslation('globalCompare')
  const chartRef = useRef<ReactECharts>(null)

  // Metric options for selector
  const metricOptions = useMemo(
    () => [
      { value: 'peak_count' as CellLineMatrixMetric, label: t('charts.matrix.peakCount', 'Peak Count') },
      { value: 'gene_count' as CellLineMatrixMetric, label: t('charts.matrix.geneCount', 'Gene Count') },
      { value: 'avg_signal' as CellLineMatrixMetric, label: t('charts.matrix.avgSignal', 'Avg Signal') },
      {
        value: 'avg_fold_enrichment' as CellLineMatrixMetric,
        label: t('charts.matrix.foldEnrichment', 'Fold Enrichment'),
      },
      {
        value: 'total_coverage_bp' as CellLineMatrixMetric,
        label: t('charts.matrix.coverage', 'Coverage'),
      },
    ],
    [t]
  )

  // Transform matrix data for heatmap
  const { heatmapData, valueRange, xLabels, yLabels } = useMemo(() => {
    if (!data) {
      return {
        heatmapData: [],
        valueRange: { min: 0, max: 1 },
        xLabels: [],
        yLabels: [],
      }
    }

    // Create labels with proper display names
    const xLabels = data.x_labels.map((mark) => {
      const config = getMarkConfig(mark as MarkType)
      return config?.shortName || mark
    })

    const yLabels = data.y_labels.map((cellType) => getCellTypeLabel(cellType, i18n.language))

    // Create heatmap data points: [x, y, value]
    const points: Array<[number, number, number | null]> = []

    // Use matrix data directly
    data.matrix.forEach((row, yIdx) => {
      row.forEach((value, xIdx) => {
        points.push([xIdx, yIdx, value])
      })
    })

    // Calculate value range
    const validValues = points.map((d) => d[2]).filter((v): v is number => v !== null)
    const min = validValues.length > 0 ? Math.min(...validValues, 0) : 0
    const max = validValues.length > 0 ? Math.max(...validValues, 1) : 1

    return {
      heatmapData: points,
      valueRange: { min, max },
      xLabels,
      yLabels,
    }
  }, [data, i18n.language])

  // Calculate dynamic height based on rows
  const chartHeight = height || Math.max(350, 150 + (yLabels.length || 5) * 40)

  // ECharts option configuration
  const option: ECOption = useMemo(() => {
    if (!data || heatmapData.length === 0) {
      return {}
    }

    return {
      title: {
        text: t('charts.matrix.title', 'Cell Type x Mark Matrix'),
        left: 'center',
        top: 10,
        textStyle: {
          fontSize: 16,
          fontWeight: 'bold',
        },
      },
      toolbox: getChartToolbox(
        `cell-line-matrix-${metric}`,
        t('export.saveImage', 'Save as Image')
      ),
      tooltip: {
        position: 'top',
        formatter: (params: unknown) => {
          const p = params as HeatmapParams
          const dataArr = Array.isArray(p.data) ? p.data : p.data.value
          const [xIdx, yIdx, value] = dataArr
          const markType = data.x_labels[xIdx]
          const cellType = data.y_labels[yIdx]

          const markConfig = getMarkConfig(markType as MarkType)
          const markDisplayName = markConfig?.displayName || markType
          const cellDisplayName = getCellTypeLabel(cellType, i18n.language)

          // Find detailed data if available
          const detailData = data.data.find(
            (d) => d.mark_type === markType && d.cell_type === cellType
          )

          const lines = [
            `<strong>${cellDisplayName}</strong>`,
            `${t('charts.matrix.mark', 'Mark')}: ${markDisplayName}`,
            '',
            `<strong>${metricOptions.find((m) => m.value === metric)?.label}</strong>: ${formatMetricValue(value, metric)}`,
          ]

          if (detailData) {
            if (metric !== 'peak_count') {
              lines.push(`${t('charts.matrix.peakCount', 'Peaks')}: ${detailData.peak_count.toLocaleString()}`)
            }
            if (metric !== 'gene_count') {
              lines.push(`${t('charts.matrix.geneCount', 'Genes')}: ${detailData.gene_count.toLocaleString()}`)
            }
          }

          return lines.join('<br/>')
        },
      },
      grid: {
        left: '18%',
        right: '12%',
        bottom: '22%',
        top: '15%',
      },
      xAxis: {
        type: 'category',
        data: xLabels,
        splitArea: { show: true },
        axisLabel: {
          rotate: 45,
          fontSize: 11,
          interval: 0,
        },
      },
      yAxis: {
        type: 'category',
        data: yLabels,
        splitArea: { show: true },
        axisLabel: {
          fontSize: 11,
          width: 100,
          overflow: 'truncate',
          ellipsis: '...',
        },
      },
      visualMap: {
        min: valueRange.min,
        max: valueRange.max,
        calculable: true,
        orient: 'horizontal',
        left: 'center',
        bottom: '5%',
        itemWidth: 15,
        itemHeight: 120,
        inRange: {
          color: getColorRange(metric),
        },
        formatter: ((value: number) => formatMetricValue(value, metric)) as VisualMapFormatter,
      },
      series: [
        {
          name: metricOptions.find((m) => m.value === metric)?.label || metric,
          type: 'heatmap',
          data: heatmapData,
          label: {
            show: xLabels.length <= 10 && yLabels.length <= 10,
            formatter: (params: unknown) => {
              const p = params as HeatmapParams
              const dataArr = Array.isArray(p.data) ? p.data : p.data.value
              const value = dataArr[2]
              if (value === null || value === undefined) return '-'
              if (metric === 'peak_count' || metric === 'gene_count') {
                if (value >= 1000) return `${(value / 1000).toFixed(0)}k`
                return value.toString()
              }
              if (metric === 'total_coverage_bp') {
                if (value >= 1000000) return `${(value / 1000000).toFixed(1)}M`
                if (value >= 1000) return `${(value / 1000).toFixed(0)}k`
                return value.toString()
              }
              return value.toFixed(1)
            },
            fontSize: 9,
            color: '#333',
          },
          emphasis: {
            itemStyle: {
              shadowBlur: 10,
              shadowColor: 'rgba(0, 0, 0, 0.5)',
            },
          },
          itemStyle: {
            borderColor: '#fff',
            borderWidth: 2,
            borderRadius: 4,
          },
        },
      ],
    }
  }, [data, heatmapData, valueRange, xLabels, yLabels, metric, metricOptions, t, i18n.language])

  // Handle chart click events
  useEffect(() => {
    if (!chartRef.current || !onCellClick || !data) return

    const chartInstance = chartRef.current.getEchartsInstance() as EChartsInstance

    const handleClick = (params: unknown) => {
      const p = params as HeatmapParams
      if (p.componentType === 'series' && p.seriesType === 'heatmap') {
        const dataArr = Array.isArray(p.data) ? p.data : p.data.value
        const [xIdx, yIdx] = dataArr
        onCellClick(data.y_labels[yIdx], data.x_labels[xIdx] as MarkType)
      }
    }

    chartInstance.on('click', handleClick)

    return () => {
      chartInstance.off('click', handleClick)
    }
  }, [onCellClick, data])

  // Handle empty state
  if (!loading && (!data || data.valid_combinations === 0)) {
    return (
      <Empty
        description={t('charts.matrix.noData', 'No matrix data available')}
        style={{ padding: 48 }}
      />
    )
  }

  return (
    <Space orientation="vertical" size="middle" style={{ width: '100%' }}>
      {/* Metric Selector */}
      {showMetricSelector && onMetricChange && (
        <Space>
          <Text type="secondary">{t('charts.matrix.metricLabel', 'Display Metric')}:</Text>
          <Segmented
            options={metricOptions}
            value={metric}
            onChange={(value) => onMetricChange(value as CellLineMatrixMetric)}
            size="small"
          />
        </Space>
      )}

      {/* Heatmap Chart */}
      {loading ? (
        <div
          style={{
            height: chartHeight,
            display: 'flex',
            alignItems: 'center',
            justifyContent: 'center',
          }}
        >
          <Spin size="large" />
        </div>
      ) : (
        <ReactECharts
          ref={chartRef}
          echarts={echarts}
          option={option}
          style={{ height: chartHeight }}
          notMerge
          lazyUpdate
          data-testid="cell-line-matrix-chart"
        />
      )}
    </Space>
  )
}

export default CellLineMatrixChart
