/**
 * CellLineHeatmapMatrix Component
 * Phase 2.9 - Multi-dimensional heatmap: Cell Lines x Marks
 *
 * Visualizes ChIP-seq data as a matrix heatmap where:
 * - Y-axis: Cell types/lines
 * - X-axis: Histone modification marks
 * - Color intensity: Selected metric value
 *
 * Features:
 * - Interactive metric switching (fold enrichment, peak count, coverage, signal)
 * - Detailed tooltips with full statistics
 * - Cell click callback for drill-down navigation
 * - Responsive height based on number of cell types
 * - Missing data handling with visual indicators
 */

import { useMemo, useRef, useEffect } from 'react'
import ReactECharts from 'echarts-for-react'
import type { EChartsInstance } from 'echarts-for-react'
import { Card, Row, Col, Statistic, Space, Tag, Segmented, Empty, Typography } from 'antd'
import { useTranslation } from 'react-i18next'
import echarts from '@/utils/echarts'
import type { ECOption } from '@/utils/echarts'
import { getChartToolbox } from '@/utils/chart-export'
import { getCellTypeColor, getCellTypeLabel, CELL_TYPE_CONFIGS } from '@/config/cellTypeConfigs'
import { getMarkConfig, MARK_CONFIGS } from '@/config/markConfigs'
import type { HeatmapMatrixResponse, HeatmapMetricType, MarkType } from '@/types/chipseq'
import type { HeatmapParams, VisualMapFormatter } from '@/types/echarts'

const { Text } = Typography

interface CellLineHeatmapMatrixProps {
  /** Matrix data from API */
  data: HeatmapMatrixResponse
  /** Current metric to display */
  metric?: HeatmapMetricType
  /** Callback when metric changes */
  onMetricChange?: (metric: HeatmapMetricType) => void
  /** Callback when a cell is clicked */
  onCellClick?: (params: { cellType: string; mark: string; value: number | null }) => void
  /** Loading state */
  loading?: boolean
}

/**
 * Format metric value for display based on metric type
 */
function formatMetricValue(value: number | null, metric: HeatmapMetricType): string {
  if (value === null || value === undefined) return 'N/A'

  switch (metric) {
    case 'median_fold_enrichment':
      return `${value.toFixed(2)}x`
    case 'peak_count':
      return value.toLocaleString()
    case 'total_coverage_bp':
      if (value >= 1000000) return `${(value / 1000000).toFixed(2)} Mb`
      if (value >= 1000) return `${(value / 1000).toFixed(1)} kb`
      return `${value} bp`
    case 'avg_signal':
      return value.toFixed(2)
    default:
      return value.toString()
  }
}

/**
 * Get color range based on metric type
 */
function getColorRange(metric: HeatmapMetricType): string[] {
  const schemes: Record<HeatmapMetricType, string[]> = {
    median_fold_enrichment: ['#f0f5ff', '#1890ff', '#003a8c'],
    peak_count: ['#f6ffed', '#52c41a', '#135200'],
    total_coverage_bp: ['#fff0f6', '#eb2f96', '#9e1068'],
    avg_signal: ['#fff7e6', '#fa8c16', '#ad4e00'],
  }
  return schemes[metric] || schemes.median_fold_enrichment
}

/**
 * Get metric display label
 */
function getMetricLabel(metric: HeatmapMetricType, t: (key: string, fallback: string) => string): string {
  const labels: Record<HeatmapMetricType, string> = {
    median_fold_enrichment: t('detail.chipseq.cellLineCompare.foldEnrichment', 'Fold Enrichment'),
    peak_count: t('detail.chipseq.cellLineCompare.peakCount', 'Peak Count'),
    total_coverage_bp: t('detail.chipseq.cellLineCompare.coverage', 'Coverage'),
    avg_signal: t('detail.chipseq.cellLineCompare.avgSignal', 'Avg Signal'),
  }
  return labels[metric] || metric
}

/**
 * CellLineHeatmapMatrix Component
 *
 * Renders a heatmap matrix visualization showing ChIP-seq metrics
 * across multiple cell types (rows) and histone marks (columns).
 *
 * @example
 * ```tsx
 * <CellLineHeatmapMatrix
 *   data={matrixData}
 *   metric="median_fold_enrichment"
 *   onMetricChange={(m) => setMetric(m)}
 *   onCellClick={(params) => handleCellClick(params)}
 * />
 * ```
 */
export function CellLineHeatmapMatrix({
  data,
  metric = 'median_fold_enrichment',
  onMetricChange,
  onCellClick,
  loading = false,
}: CellLineHeatmapMatrixProps) {
  const { t, i18n } = useTranslation('genes')
  const isZh = i18n.language === 'zh-CN'
  const chartRef = useRef<ReactECharts>(null)

  // Metric options for segmented control
  const metricOptions = useMemo(
    () => [
      {
        value: 'median_fold_enrichment' as HeatmapMetricType,
        label: t('detail.chipseq.cellLineCompare.foldEnrichment', 'Fold Enrichment'),
      },
      {
        value: 'peak_count' as HeatmapMetricType,
        label: t('detail.chipseq.cellLineCompare.peakCount', 'Peak Count'),
      },
      {
        value: 'total_coverage_bp' as HeatmapMetricType,
        label: t('detail.chipseq.cellLineCompare.coverage', 'Coverage'),
      },
      {
        value: 'avg_signal' as HeatmapMetricType,
        label: t('detail.chipseq.cellLineCompare.avgSignal', 'Avg Signal'),
      },
    ],
    [t]
  )

  // Transform matrix to ECharts heatmap data format: [x, y, value]
  const heatmapData = useMemo(() => {
    const result: Array<[number, number, number | null]> = []

    for (let y = 0; y < data.cell_types.length; y++) {
      for (let x = 0; x < data.marks.length; x++) {
        const value = data.matrix[y]?.[x]
        result.push([x, y, value])
      }
    }

    return result
  }, [data.matrix, data.cell_types, data.marks])

  // Compute value range for color mapping (exclude null values)
  const valueRange = useMemo(() => {
    const validValues = heatmapData
      .map((d) => d[2])
      .filter((v): v is number => v !== null && v !== undefined)

    if (validValues.length === 0) {
      return { min: 0, max: 1 }
    }

    return {
      min: Math.min(...validValues, 0),
      max: Math.max(...validValues, 1),
    }
  }, [heatmapData])

  // Generate cell type labels (Y-axis)
  const cellTypeLabels = useMemo(
    () => data.cell_types.map((ct) => getCellTypeLabel(ct, i18n.language)),
    [data.cell_types, i18n.language]
  )

  // Generate mark labels (X-axis)
  const markLabels = useMemo(
    () =>
      data.marks.map((mark) => {
        const config = MARK_CONFIGS[mark as MarkType]
        return config?.shortName || mark
      }),
    [data.marks]
  )

  // ECharts option configuration
  const option: ECOption = useMemo(() => {
    return {
      title: {
        text: t('detail.chipseq.matrixHeatmap', 'Histone Marks Matrix'),
        left: 'center',
        top: 10,
        textStyle: { fontSize: 14, fontWeight: 'bold' },
      },
      toolbox: getChartToolbox(
        `heatmap-matrix-${data.gene_name}`,
        t('export.saveImage', 'Save as Image')
      ),
      tooltip: {
        position: 'top',
        formatter: (params: unknown) => {
          const p = params as HeatmapParams
          const dataArr = Array.isArray(p.data) ? p.data : p.data.value
          const [markIdx, cellIdx, value] = dataArr
          const cellType = data.cell_types[cellIdx]
          const mark = data.marks[markIdx]
          const cellConfig = CELL_TYPE_CONFIGS[cellType]
          const markConfig = getMarkConfig(mark as MarkType)

          const cellLabel = isZh ? cellConfig?.labelZh : cellConfig?.label
          const markLabel = markConfig?.displayName || mark

          const lines = [
            `<strong>${cellLabel || cellType}</strong>`,
            `<strong>${markLabel}</strong>`,
            `<br/>${getMetricLabel(metric, t)}: <strong>${formatMetricValue(value, metric)}</strong>`,
          ]

          // Add additional details if available
          if (data.details?.[cellType]?.[mark]) {
            const stats = data.details[cellType][mark]
            if (stats.peak_count !== undefined) {
              lines.push(`<br/>${t('detail.chipseq.totalPeaks', 'Peaks')}: ${stats.peak_count}`)
            }
            if (stats.total_coverage_bp !== undefined) {
              lines.push(
                `${t('detail.chipseq.cellLineCompare.coverage', 'Coverage')}: ${formatMetricValue(stats.total_coverage_bp, 'total_coverage_bp')}`
              )
            }
            if (stats.median_fold_enrichment !== undefined && metric !== 'median_fold_enrichment') {
              lines.push(
                `${t('detail.chipseq.foldEnrichment', 'Fold Enrichment')}: ${stats.median_fold_enrichment.toFixed(2)}x`
              )
            }
          }

          return lines.join('')
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
        data: markLabels,
        splitArea: { show: true },
        axisLabel: {
          rotate: 30,
          fontSize: 11,
          interval: 0,
        },
      },
      yAxis: {
        type: 'category',
        data: cellTypeLabels,
        splitArea: { show: true },
        axisLabel: {
          fontSize: 11,
          formatter: (value: string, _index: number) => {
            // Return label with color indicator prefix
            return `{dot|●} ${value}`
          },
          rich: {
            dot: {
              color: '#999',
              fontSize: 10,
            },
          },
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
          data: heatmapData,
          label: {
            show: data.marks.length <= 12 && data.cell_types.length <= 10,
            formatter: (params: unknown) => {
              const p = params as HeatmapParams
              const dataArr = Array.isArray(p.data) ? p.data : p.data.value
              const value = dataArr[2]
              if (value === null || value === undefined) return '-'
              // Shorter format for cell labels
              if (metric === 'peak_count') return value.toString()
              if (metric === 'total_coverage_bp') {
                if (value >= 1000000) return `${(value / 1000000).toFixed(1)}M`
                if (value >= 1000) return `${(value / 1000).toFixed(0)}k`
                return value.toString()
              }
              return value.toFixed(1)
            },
            fontSize: 10,
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
  }, [data, metric, heatmapData, valueRange, cellTypeLabels, markLabels, t, isZh])

  // Handle chart click events
  useEffect(() => {
    if (!chartRef.current || !onCellClick) return

    const chartInstance = chartRef.current.getEchartsInstance() as EChartsInstance

    const handleClick = (params: unknown) => {
      const p = params as HeatmapParams
      if (p.componentType === 'series' && p.seriesType === 'heatmap') {
        const dataArr = Array.isArray(p.data) ? p.data : p.data.value
        const [markIdx, cellIdx, value] = dataArr
        onCellClick({
          cellType: data.cell_types[cellIdx],
          mark: data.marks[markIdx],
          value,
        })
      }
    }

    chartInstance.on('click', handleClick)

    return () => {
      chartInstance.off('click', handleClick)
    }
  }, [onCellClick, data.cell_types, data.marks])

  // Handle empty state
  if (!data.matrix || data.matrix.length === 0 || data.valid_combinations === 0) {
    return (
      <Empty
        description={t(
          'detail.chipseq.cellLineCompare.noData',
          'No cell line comparison data available'
        )}
      />
    )
  }

  // Calculate dynamic chart height based on number of rows
  const chartHeight = Math.max(300, 200 + data.cell_types.length * 50)

  return (
    <Space orientation="vertical" size="middle" style={{ width: '100%' }}>
      {/* Header with gene info and metric selector */}
      <Card size="small">
        <Row gutter={[16, 16]} align="middle">
          <Col xs={24} md={10}>
            <Space orientation="vertical" size={0}>
              <Text strong style={{ fontSize: 16 }}>
                {data.gene_name}
              </Text>
              <Text type="secondary" style={{ fontSize: 12 }}>
                {data.chromosome}:{data.region_start.toLocaleString()}-
                {data.region_end.toLocaleString()}
              </Text>
            </Space>
          </Col>
          <Col xs={24} md={14}>
            <Segmented
              options={metricOptions}
              value={metric}
              onChange={(value) => onMetricChange?.(value as HeatmapMetricType)}
              block
            />
          </Col>
        </Row>
      </Card>

      {/* Summary Statistics */}
      <Row gutter={[16, 16]}>
        <Col xs={12} sm={6}>
          <Card size="small">
            <Statistic
              title={t('detail.chipseq.matrixTotalCombinations', 'Total Combinations')}
              value={data.total_combinations}
            />
          </Card>
        </Col>
        <Col xs={12} sm={6}>
          <Card size="small">
            <Statistic
              title={t('detail.chipseq.matrixValidCombinations', 'Valid Combinations')}
              value={data.valid_combinations}
              suffix={
                <Text type="secondary" style={{ fontSize: 12 }}>
                  ({((data.valid_combinations / data.total_combinations) * 100).toFixed(0)}%)
                </Text>
              }
            />
          </Card>
        </Col>
        <Col xs={12} sm={6}>
          <Card size="small">
            <Statistic
              title={t('detail.chipseq.cellLineCompare.totalCellLines', 'Cell Lines')}
              value={data.cell_types.length}
            />
          </Card>
        </Col>
        <Col xs={12} sm={6}>
          <Card size="small">
            <Statistic
              title={t('detail.chipseq.marksCount', 'Marks')}
              value={data.marks.length}
            />
          </Card>
        </Col>
      </Row>

      {/* Missing combinations warning */}
      {data.missing_combinations && data.missing_combinations.length > 0 && (
        <Card size="small">
          <Space wrap>
            <Text type="secondary">
              {t('detail.chipseq.missingCombinations', 'Missing data')}:
            </Text>
            {data.missing_combinations.slice(0, 5).map((combo, idx) => (
              <Tag key={idx} color="default">
                {combo.cell_type} / {combo.mark}
              </Tag>
            ))}
            {data.missing_combinations.length > 5 && (
              <Tag color="default">
                +{data.missing_combinations.length - 5} {t('common.more', 'more')}
              </Tag>
            )}
          </Space>
        </Card>
      )}

      {/* Heatmap Chart */}
      <Card loading={loading}>
        <ReactECharts
          ref={chartRef}
          echarts={echarts}
          option={option}
          style={{ height: chartHeight }}
          notMerge
          lazyUpdate
        />
      </Card>

      {/* Legend for cell types */}
      <Card size="small" title={t('detail.chipseq.cellTypes.legend', 'Cell Types')}>
        <Space wrap>
          {data.cell_types.map((cellType) => {
            const config = CELL_TYPE_CONFIGS[cellType]
            const label = isZh ? config?.labelZh : config?.label
            return (
              <Tag
                key={cellType}
                color={getCellTypeColor(cellType)}
                style={{ margin: '4px' }}
              >
                {label || cellType}
              </Tag>
            )
          })}
        </Space>
      </Card>
    </Space>
  )
}

export default CellLineHeatmapMatrix
