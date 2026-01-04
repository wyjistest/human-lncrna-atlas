/**
 * OverlapHeatmapMatrix Component
 * Phase 3.0 Phase 2 - Multi-dimensional heatmap for overlap analysis
 *
 * Visualizes lncRNA-ChIP-seq overlap data as a matrix heatmap where:
 * - X-axis: Mark types or Cell types (configurable)
 * - Y-axis: lncRNAs or Target genes (configurable)
 * - Color intensity: Selected metric value
 *
 * Features:
 * - Interactive metric switching (count, avg_binding_affinity, total_overlap_length)
 * - Axis dimension switching
 * - Detailed tooltips with full statistics
 * - Responsive height based on number of items
 * - VisualMap color gradient
 * - i18n support
 */

import { useMemo, useState, useRef, useEffect } from 'react'
import { escapeHtml } from '@/utils/escapeHtml'
import ReactECharts from 'echarts-for-react'
import type { EChartsInstance } from 'echarts-for-react'
import {
  Card,
  Row,
  Col,
  Statistic,
  Space,
  Segmented,
  Empty,
  Typography,
  Select,
  InputNumber,
  Spin,
} from 'antd'
import { useTranslation } from 'react-i18next'
import echarts from '@/utils/echarts'
import type { ECOption } from '@/utils/echarts'
import { getChartToolbox } from '@/utils/chart-export'
import { getMinMax } from '@/utils/minMax'
import { MARK_CONFIGS } from '@/config/markConfigs'
import { getCellTypeLabel } from '@/config/cellTypeConfigs'
import { useOverlapHeatmap } from '@/hooks/useLncRNAChIPSeqOverlap'
import type {
  OverlapHeatmapMetric,
  OverlapHeatmapXAxis,
  OverlapHeatmapYAxis,
  OverlapFilters,
} from '@/types/lncRNAChIPSeqOverlap'
import type { MarkType } from '@/types/chipseq'
import type { HeatmapParams, VisualMapFormatter } from '@/types/echarts'

const { Text } = Typography

interface OverlapHeatmapMatrixProps {
  /** Initial X-axis dimension */
  initialXAxis?: OverlapHeatmapXAxis
  /** Initial Y-axis dimension */
  initialYAxis?: OverlapHeatmapYAxis
  /** Initial metric to display */
  initialMetric?: OverlapHeatmapMetric
  /** Initial top N items */
  initialTopN?: number
  /** Optional filters to apply */
  filters?: Partial<OverlapFilters>
  /** Callback when a cell is clicked */
  onCellClick?: (params: { x: string; y: string; value: number }) => void
  /** Show controls */
  showControls?: boolean
}

/**
 * Format metric value for display based on metric type
 */
function formatMetricValue(value: number | null, metric: OverlapHeatmapMetric): string {
  if (value === null || value === undefined) return 'N/A'

  switch (metric) {
    case 'count':
      return value.toLocaleString()
    case 'avg_binding_affinity':
      return value.toFixed(2)
    case 'total_overlap_length':
      if (value >= 1000000) return `${(value / 1000000).toFixed(2)} Mb`
      if (value >= 1000) return `${(value / 1000).toFixed(1)} kb`
      return `${value} bp`
    default:
      return value.toString()
  }
}

/**
 * Get color range based on metric type
 */
function getColorRange(metric: OverlapHeatmapMetric): string[] {
  const schemes: Record<OverlapHeatmapMetric, string[]> = {
    count: ['#f6ffed', '#52c41a', '#135200'],
    avg_binding_affinity: ['#fff0f6', '#eb2f96', '#9e1068'],
    total_overlap_length: ['#f0f5ff', '#1890ff', '#003a8c'],
  }
  return schemes[metric] || schemes.count
}

/**
 * Get metric display label
 */
function getMetricLabel(
  metric: OverlapHeatmapMetric,
  t: (key: string, fallback: string) => string
): string {
  const labels: Record<OverlapHeatmapMetric, string> = {
    count: t('charts.heatmap.metricCount', 'Overlap Count'),
    avg_binding_affinity: t('charts.heatmap.metricBindingAffinity', 'Avg Binding Affinity'),
    total_overlap_length: t('charts.heatmap.metricOverlapLength', 'Total Overlap Length'),
  }
  return labels[metric] || metric
}

/**
 * Get axis display label
 */
function getAxisLabel(
  axis: OverlapHeatmapXAxis | OverlapHeatmapYAxis,
  t: (key: string, fallback: string) => string
): string {
  const labels: Record<string, string> = {
    mark_type: t('charts.heatmap.axisMarkType', 'Mark Type'),
    cell_type: t('charts.heatmap.axisCellType', 'Cell Type'),
    lncrna: t('charts.heatmap.axisLncrna', 'lncRNA'),
    target_gene: t('charts.heatmap.axisTargetGene', 'Target Gene'),
  }
  return labels[axis] || axis
}

/**
 * Get label for axis value
 */
function getValueLabel(
  value: string,
  axisType: OverlapHeatmapXAxis | OverlapHeatmapYAxis,
  language: string
): string {
  if (axisType === 'mark_type') {
    const config = MARK_CONFIGS[value as MarkType]
    return config?.shortName || value
  }
  if (axisType === 'cell_type') {
    return getCellTypeLabel(value, language)
  }
  return value
}

/**
 * OverlapHeatmapMatrix Component
 *
 * Renders a heatmap matrix visualization showing overlap metrics
 * across configurable dimensions.
 *
 * @example
 * ```tsx
 * <OverlapHeatmapMatrix
 *   initialXAxis="mark_type"
 *   initialYAxis="lncrna"
 *   initialMetric="count"
 *   filters={{ chromosome: 'chr1' }}
 * />
 * ```
 */
export function OverlapHeatmapMatrix({
  initialXAxis = 'mark_type',
  initialYAxis = 'lncrna',
  initialMetric = 'count',
  initialTopN = 50,
  filters,
  onCellClick,
  showControls = true,
}: OverlapHeatmapMatrixProps) {
  const { t, i18n } = useTranslation('overlap')
  const chartRef = useRef<ReactECharts>(null)

  // State for configuration
  const [xAxis, setXAxis] = useState<OverlapHeatmapXAxis>(initialXAxis)
  const [yAxis, setYAxis] = useState<OverlapHeatmapYAxis>(initialYAxis)
  const [metric, setMetric] = useState<OverlapHeatmapMetric>(initialMetric)
  const [topN, setTopN] = useState<number>(initialTopN)

  // Fetch heatmap data
  const {
    data: heatmapData,
    isLoading,
    error,
  } = useOverlapHeatmap(xAxis, yAxis, metric, topN, filters, {
    enabled: true,
  })

  // Metric options for segmented control
  const metricOptions = useMemo(
    () => [
      {
        value: 'count' as OverlapHeatmapMetric,
        label: t('charts.heatmap.metricCount', 'Count'),
      },
      {
        value: 'avg_binding_affinity' as OverlapHeatmapMetric,
        label: t('charts.heatmap.metricBindingAffinity', 'Binding Affinity'),
      },
      {
        value: 'total_overlap_length' as OverlapHeatmapMetric,
        label: t('charts.heatmap.metricOverlapLength', 'Overlap Length'),
      },
    ],
    [t]
  )

  // Axis options
  const xAxisOptions = [
    { value: 'mark_type', label: t('charts.heatmap.axisMarkType', 'Mark Type') },
    { value: 'cell_type', label: t('charts.heatmap.axisCellType', 'Cell Type') },
  ]

  const yAxisOptions = [
    { value: 'lncrna', label: t('charts.heatmap.axisLncrna', 'lncRNA') },
    { value: 'target_gene', label: t('charts.heatmap.axisTargetGene', 'Target Gene') },
  ]

  // Transform data to ECharts heatmap format: [x, y, value]
  const { heatmapPoints, valueRange } = useMemo(() => {
    if (!heatmapData) {
      return { heatmapPoints: [], valueRange: { min: 0, max: 1 } }
    }

    const points: Array<[number, number, number | null]> = []

    // Create lookup maps for indices
    const xIndexMap = new Map(heatmapData.x_labels.map((label, idx) => [label, idx]))
    const yIndexMap = new Map(heatmapData.y_labels.map((label, idx) => [label, idx]))

    // Convert data points
    for (const point of heatmapData.data) {
      const xIdx = xIndexMap.get(point.x)
      const yIdx = yIndexMap.get(point.y)
      if (xIdx !== undefined && yIdx !== undefined) {
        points.push([xIdx, yIdx, point.value])
      }
    }

    // Calculate value range（安全遍历：避免 Math.min/max(...arr) 大数组问题）
    const validValues = points.map((d) => d[2]).filter((v): v is number => v !== null)
    const { min, max } = getMinMax(validValues, { defaultMin: 0, defaultMax: 1, include: [0, 1] })

    return {
      heatmapPoints: points,
      valueRange: { min, max },
    }
  }, [heatmapData])

  // Generate labels
  const xLabels = useMemo(
    () =>
      heatmapData?.x_labels.map((label) => getValueLabel(label, xAxis, i18n.language)) || [],
    [heatmapData?.x_labels, xAxis, i18n.language]
  )

  const yLabels = useMemo(
    () =>
      heatmapData?.y_labels.map((label) => getValueLabel(label, yAxis, i18n.language)) || [],
    [heatmapData?.y_labels, yAxis, i18n.language]
  )

  // ECharts option configuration
  const option: ECOption = useMemo(() => {
    if (!heatmapData || heatmapPoints.length === 0) {
      return {}
    }

    return {
      title: {
        text: t('charts.heatmap.title', 'lncRNA-ChIP-seq Overlap Matrix'),
        left: 'center',
        top: 10,
        textStyle: { fontSize: 14, fontWeight: 'bold' },
      },
      toolbox: getChartToolbox(
        `overlap-heatmap-${xAxis}-${yAxis}`,
        t('export.saveImage', 'Save as Image')
      ),
      tooltip: {
        position: 'top',
        formatter: (params: unknown) => {
          const p = params as HeatmapParams
          const dataArr = Array.isArray(p.data) ? p.data : p.data.value
          const [xIdx, yIdx, value] = dataArr
          const xLabel = heatmapData.x_labels[xIdx]
          const yLabel = heatmapData.y_labels[yIdx]

          const xDisplayLabel = getValueLabel(xLabel, xAxis, i18n.language)
          const yDisplayLabel = getValueLabel(yLabel, yAxis, i18n.language)

          const lines = [
            `<strong>${getAxisLabel(yAxis, t)}</strong>: ${escapeHtml(yDisplayLabel)}`,
            `<strong>${getAxisLabel(xAxis, t)}</strong>: ${escapeHtml(xDisplayLabel)}`,
            `<br/><strong>${getMetricLabel(metric, t)}</strong>: ${formatMetricValue(value, metric)}`,
          ]

          return lines.join('<br/>')
        },
      },
      grid: {
        left: '18%',
        right: '12%',
        bottom: '25%',
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
          fontSize: 10,
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
          name: getMetricLabel(metric, t),
          type: 'heatmap',
          data: heatmapPoints,
          label: {
            show:
              heatmapData.x_labels.length <= 8 && heatmapData.y_labels.length <= 15,
            formatter: (params: unknown) => {
              const p = params as HeatmapParams
              const dataArr = Array.isArray(p.data) ? p.data : p.data.value
              const value = dataArr[2]
              if (value === null || value === undefined) return '-'
              if (metric === 'count') {
                if (value >= 1000) return `${(value / 1000).toFixed(0)}k`
                return value.toString()
              }
              if (metric === 'total_overlap_length') {
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
  }, [heatmapData, heatmapPoints, valueRange, xLabels, yLabels, xAxis, yAxis, metric, t, i18n.language])

  // Handle chart click events
  useEffect(() => {
    if (!chartRef.current || !onCellClick || !heatmapData) return

    const chartInstance = chartRef.current.getEchartsInstance() as EChartsInstance

    const handleClick = (params: unknown) => {
      const p = params as HeatmapParams
      if (p.componentType === 'series' && p.seriesType === 'heatmap') {
        const dataArr = Array.isArray(p.data) ? p.data : p.data.value
        const [xIdx, yIdx, value] = dataArr
        onCellClick({
          x: heatmapData.x_labels[xIdx],
          y: heatmapData.y_labels[yIdx],
          value: value ?? 0,
        })
      }
    }

    chartInstance.on('click', handleClick)

    return () => {
      chartInstance.off('click', handleClick)
    }
  }, [onCellClick, heatmapData])

  // Handle error state
  if (error) {
    return (
      <Empty
        description={t('charts.heatmap.error', 'Failed to load heatmap data')}
      />
    )
  }

  // Handle empty state
  if (!isLoading && (!heatmapData || heatmapData.valid_combinations === 0)) {
    return (
      <Empty
        description={t('charts.heatmap.noData', 'No heatmap data available')}
      />
    )
  }

  // Calculate dynamic chart height based on number of rows
  const chartHeight = Math.max(350, 200 + (heatmapData?.y_labels.length || 10) * 35)

  return (
    <Space
      direction="vertical"
      size="middle"
      style={{ width: '100%' }}
      data-testid="overlap-heatmap-matrix"
    >
      {/* Controls */}
      {showControls && (
        <Card size="small">
          <Row gutter={[16, 16]} align="middle">
            <Col xs={24} sm={12} md={6}>
              <Space orientation="vertical" size={0} style={{ width: '100%' }}>
                <Text type="secondary" style={{ fontSize: 12 }}>
                  {t('charts.heatmap.xAxisLabel', 'X-Axis (Columns)')}
                </Text>
                <Select
                  value={xAxis}
                  onChange={(value) => setXAxis(value as OverlapHeatmapXAxis)}
                  options={xAxisOptions}
                  style={{ width: '100%' }}
                  size="small"
                />
              </Space>
            </Col>
            <Col xs={24} sm={12} md={6}>
              <Space orientation="vertical" size={0} style={{ width: '100%' }}>
                <Text type="secondary" style={{ fontSize: 12 }}>
                  {t('charts.heatmap.yAxisLabel', 'Y-Axis (Rows)')}
                </Text>
                <Select
                  value={yAxis}
                  onChange={(value) => setYAxis(value as OverlapHeatmapYAxis)}
                  options={yAxisOptions}
                  style={{ width: '100%' }}
                  size="small"
                />
              </Space>
            </Col>
            <Col xs={24} sm={12} md={6}>
              <Space orientation="vertical" size={0} style={{ width: '100%' }}>
                <Text type="secondary" style={{ fontSize: 12 }}>
                  {t('charts.heatmap.topNLabel', 'Top N Items')}
                </Text>
                <InputNumber
                  value={topN}
                  onChange={(value) => setTopN(value || 50)}
                  min={10}
                  max={100}
                  step={10}
                  style={{ width: '100%' }}
                  size="small"
                />
              </Space>
            </Col>
            <Col xs={24} sm={12} md={6}>
              <Space orientation="vertical" size={0} style={{ width: '100%' }}>
                <Text type="secondary" style={{ fontSize: 12 }}>
                  {t('charts.heatmap.metricLabel', 'Metric')}
                </Text>
                <Segmented
                  options={metricOptions}
                  value={metric}
                  onChange={(value) => setMetric(value as OverlapHeatmapMetric)}
                  size="small"
                />
              </Space>
            </Col>
          </Row>
        </Card>
      )}

      {/* Summary Statistics */}
      {heatmapData && (
        <Row gutter={[16, 16]}>
          <Col xs={12} sm={6}>
            <Card size="small">
              <Statistic
                title={t('charts.heatmap.totalCombinations', 'Total Combinations')}
                value={heatmapData.total_combinations}
              />
            </Card>
          </Col>
          <Col xs={12} sm={6}>
            <Card size="small">
              <Statistic
                title={t('charts.heatmap.validCombinations', 'Valid Combinations')}
                value={heatmapData.valid_combinations}
                suffix={
                  <Text type="secondary" style={{ fontSize: 12 }}>
                    (
                    {(
                      (heatmapData.valid_combinations / heatmapData.total_combinations) *
                      100
                    ).toFixed(0)}
                    %)
                  </Text>
                }
              />
            </Card>
          </Col>
          <Col xs={12} sm={6}>
            <Card size="small">
              <Statistic
                title={getAxisLabel(xAxis, t)}
                value={heatmapData.x_labels.length}
              />
            </Card>
          </Col>
          <Col xs={12} sm={6}>
            <Card size="small">
              <Statistic
                title={getAxisLabel(yAxis, t)}
                value={heatmapData.y_labels.length}
              />
            </Card>
          </Col>
        </Row>
      )}

      {/* Heatmap Chart */}
      <Card>
        {isLoading ? (
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
          />
        )}
      </Card>
    </Space>
  )
}

export default OverlapHeatmapMatrix
