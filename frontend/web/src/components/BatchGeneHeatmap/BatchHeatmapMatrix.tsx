/**
 * BatchHeatmapMatrix Component
 * Large-scale heatmap visualization for multiple genes x marks x cell types
 * Y-axis: Gene × Cell Type combinations
 * X-axis: Histone Marks
 * Phase 2.10 - Batch Gene Heatmap Feature
 */

import { useMemo, useRef, useEffect } from 'react'
import ReactECharts from 'echarts-for-react'
import type { EChartsInstance } from 'echarts-for-react'
import { Card, Row, Col, Space, Tag, Segmented, Empty, Typography, Spin, Alert } from 'antd'
import { useTranslation } from 'react-i18next'
import echarts from '@/utils/echarts'
import type { ECOption } from '@/utils/echarts'
import { getChartToolbox } from '@/utils/chart-export'
import { getCellTypeColor, getCellTypeLabel, CELL_TYPE_CONFIGS } from '@/config/cellTypeConfigs'
import { getMarkConfig, MARK_CONFIGS } from '@/config/markConfigs'
import type { HeatmapMetricType, MarkType } from '@/types/chipseq'

const { Text } = Typography

interface BatchHeatmapMatrixProps {
  /** Matrix data: genes x marks x cellTypes */
  data: Array<{
    gene_name: string
    gene_id: number
    marks: string[]
    cell_types: string[]
    matrix: Array<Array<number | null>>
  }>
  /** Current metric to display */
  metric?: HeatmapMetricType
  /** Callback when metric changes */
  onMetricChange?: (metric: HeatmapMetricType) => void
  /** Callback when a cell is clicked */
  onCellClick?: (params: {
    gene_name: string
    cellType: string
    mark: string
    value: number | null
  }) => void
  /** Loading state */
  loading?: boolean
  /** Error state */
  error?: Error | null
}

/**
 * Format metric value for display
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
function getMetricLabel(
  metric: HeatmapMetricType,
  t: (key: string, fallback: string) => string
): string {
  const labels: Record<HeatmapMetricType, string> = {
    median_fold_enrichment: t('detail.chipseq.cellLineCompare.foldEnrichment', 'Fold Enrichment'),
    peak_count: t('detail.chipseq.cellLineCompare.peakCount', 'Peak Count'),
    total_coverage_bp: t('detail.chipseq.cellLineCompare.coverage', 'Coverage'),
    avg_signal: t('detail.chipseq.cellLineCompare.avgSignal', 'Avg Signal'),
  }
  return labels[metric] || metric
}

/**
 * BatchHeatmapMatrix Component
 *
 * Renders a large-scale heatmap showing ChIP-seq metrics across:
 * - Multiple genes
 * - Multiple histone marks (X-axis)
 * - Multiple cell types (Y-axis, grouped by gene)
 *
 * Dynamically calculates chart height based on data dimensions.
 *
 * @example
 * ```tsx
 * <BatchHeatmapMatrix
 *   data={batchMatrixData}
 *   metric="median_fold_enrichment"
 *   onMetricChange={(m) => setMetric(m)}
 * />
 * ```
 */
export function BatchHeatmapMatrix({
  data,
  metric = 'median_fold_enrichment',
  onMetricChange,
  onCellClick,
  loading = false,
  error = null,
}: BatchHeatmapMatrixProps) {
  const { t, i18n } = useTranslation('genes')
  const isZh = i18n.language === 'zh-CN'
  const chartRef = useRef<ReactECharts>(null)

  // ALL HOOKS MUST BE CALLED BEFORE ANY CONDITIONAL RETURNS
  // Metric options
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

  // Flatten all unique marks and cell types (safe with empty data)
  const allMarks = useMemo(() => {
    if (!data || data.length === 0) return []
    const marks = new Set<string>()
    data.forEach((gene) => {
      gene.marks.forEach((m) => marks.add(m))
    })
    return Array.from(marks)
  }, [data])

  const allCellTypes = useMemo(() => {
    if (!data || data.length === 0) return []
    const cellTypes = new Set<string>()
    data.forEach((gene) => {
      gene.cell_types.forEach((ct) => cellTypes.add(ct))
    })
    return Array.from(cellTypes)
  }, [data])

  // Build Y-axis labels and heatmap data (safe with empty data)
  const { yLabels, heatmapData, valueRange } = useMemo(() => {
    if (!data || data.length === 0) {
      return {
        yLabels: [],
        heatmapData: [],
        valueRange: { min: 0, max: 1 },
      }
    }

    const labels: string[] = []
    const heatData: Array<[number, number, number | null]> = []
    const values: Array<number> = []

    let yIndex = 0

    // For each gene, add all cell type rows
    data.forEach((geneData) => {
      // Add gene name as separator/header
      labels.push(`${geneData.gene_name}`)
      yIndex++

      // Add rows for each cell type
      geneData.cell_types.forEach((cellType) => {
        const cellTypeLabel = getCellTypeLabel(cellType, i18n.language)
        labels.push(`  ${cellTypeLabel}`)

        // For each mark, find the corresponding value in the matrix
        geneData.marks.forEach((mark, markIdx) => {
          const cellTypeIdx = geneData.cell_types.indexOf(cellType)
          const value = geneData.matrix[cellTypeIdx]?.[markIdx]

          // Map mark to global mark index
          const globalMarkIdx = allMarks.indexOf(mark)
          heatData.push([globalMarkIdx, yIndex, value])

          if (value !== null && value !== undefined) {
            values.push(value)
          }
        })

        yIndex++
      })
    })

    // Compute value range
    const validValues = values.filter((v): v is number => v !== null && v !== undefined)
    const range =
      validValues.length > 0
        ? {
            min: Math.min(...validValues, 0),
            max: Math.max(...validValues, 1),
          }
        : { min: 0, max: 1 }

    return {
      yLabels: labels,
      heatmapData: heatData,
      valueRange: range,
    }
  }, [data, allMarks, i18n.language])

  // Generate X-axis mark labels
  const markLabels = useMemo(
    () =>
      allMarks.map((mark) => {
        const config = MARK_CONFIGS[mark as MarkType]
        return config?.shortName || mark
      }),
    [allMarks]
  )

  // Dynamic height calculation: base + row height * total rows
  const totalRows = yLabels.length
  const chartHeight = Math.max(400, 200 + totalRows * 35)

  // ECharts option configuration
  const option: ECOption = useMemo(() => {
    return {
      title: {
        text: t('batchGeneHeatmap.matrixTitle', 'Batch Gene ChIP-seq Heatmap'),
        left: 'center',
        top: 10,
        textStyle: { fontSize: 14, fontWeight: 'bold' },
      },
      toolbox: getChartToolbox(
        `batch-heatmap-matrix-${Date.now()}`,
        t('export.saveImage', 'Save as Image')
      ),
      tooltip: {
        position: 'top',
        formatter: (params: any) => {
          if (!params.data) return ''
          const [markIdx, cellIdx, value] = params.data
          const markName = allMarks[markIdx]
          const yLabel = yLabels[cellIdx]
          const markConfig = getMarkConfig(markName as MarkType)
          const markLabel = markConfig?.displayName || markName

          const lines = [
            `<strong>${yLabel}</strong>`,
            `<strong>${markLabel}</strong>`,
            `<br/>${getMetricLabel(metric, t)}: <strong>${formatMetricValue(value, metric)}</strong>`,
          ]

          return lines.join('')
        },
      },
      grid: {
        left: '20%',
        right: '12%',
        bottom: '20%',
        top: '12%',
      },
      xAxis: {
        type: 'category',
        data: markLabels,
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
        splitArea: { show: false },
        axisLabel: {
          fontSize: 10,
          interval: 0,
          formatter: (value: string) => {
            // Bold gene names, indent cell types
            if (value.startsWith('  ')) {
              return value
            }
            return `${value}`
          },
        },
      },
      visualMap: {
        min: valueRange.min,
        max: valueRange.max,
        calculable: true,
        orient: 'horizontal',
        left: 'center',
        bottom: '2%',
        itemWidth: 15,
        itemHeight: 100,
        inRange: {
          color: getColorRange(metric),
        },
        formatter: ((value: number) => formatMetricValue(value, metric)) as any,
      },
      series: [
        {
          name: getMetricLabel(metric, t),
          type: 'heatmap',
          data: heatmapData,
          label: {
            show: allMarks.length <= 12 && totalRows <= 30,
            formatter: (params: any) => {
              const value = params.data[2]
              if (value === null || value === undefined) return '-'

              if (metric === 'peak_count') return value.toString()
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
            borderWidth: 1,
            borderRadius: 2,
          },
        },
      ],
    }
  }, [metric, heatmapData, valueRange, allMarks, yLabels, markLabels, totalRows, t])

  // Handle chart click events
  useEffect(() => {
    if (!chartRef.current || !onCellClick || !data || data.length === 0) return

    const chartInstance = chartRef.current.getEchartsInstance() as EChartsInstance

    const handleClick = (params: any) => {
      if (params.componentType === 'series' && params.seriesType === 'heatmap') {
        const [markIdx, cellIdx, value] = params.data
        const markName = allMarks[markIdx]

        // Parse gene name and cell type from label
        let geneName = ''
        let cellType = ''

        // Find the gene this cell belongs to
        let currentYIdx = 0
        for (const gene of data) {
          currentYIdx++ // gene name row

          if (cellIdx < currentYIdx) {
            geneName = gene.gene_name
            break
          }

          if (cellIdx >= currentYIdx && cellIdx < currentYIdx + gene.cell_types.length) {
            geneName = gene.gene_name
            const relativeIdx = cellIdx - currentYIdx
            cellType = gene.cell_types[relativeIdx]
            break
          }

          currentYIdx += gene.cell_types.length
        }

        if (geneName && cellType) {
          onCellClick({
            gene_name: geneName,
            cellType,
            mark: markName,
            value,
          })
        }
      }
    }

    chartInstance.on('click', handleClick)

    return () => {
      chartInstance.off('click', handleClick)
    }
  }, [onCellClick, data, allMarks, yLabels])

  // NOW we can do conditional returns after all hooks
  // Validate data
  if (!data || data.length === 0) {
    return (
      <Card loading={loading}>
        <Empty
          description={t('batchGeneHeatmap.noData', 'No data available')}
          style={{ paddingTop: 48, paddingBottom: 48 }}
        />
      </Card>
    )
  }

  if (error) {
    return (
      <Card loading={loading}>
        <Alert
          type="error"
          message={t('batchGeneHeatmap.loadError', 'Failed to load data')}
          description={error.message}
          showIcon
        />
      </Card>
    )
  }

  return (
    <Space orientation="vertical" size="middle" style={{ width: '100%' }}>
      {/* Header with metric selector */}
      <Card size="small">
        <Row gutter={[16, 16]} align="middle">
          <Col xs={24} md={14}>
            <Text strong style={{ fontSize: 14 }}>
              {t('batchGeneHeatmap.matrixTitle', 'Batch Gene ChIP-seq Heatmap')}
            </Text>
            <br />
            <Text type="secondary" style={{ fontSize: 12 }}>
              {data.length} genes, {allMarks.length} marks, {allCellTypes.length} cell types
            </Text>
          </Col>
          <Col xs={24} md={10}>
            <Segmented
              options={metricOptions}
              value={metric}
              onChange={(value) => onMetricChange?.(value as HeatmapMetricType)}
              block
            />
          </Col>
        </Row>
      </Card>

      {/* Chart */}
      <Card loading={loading}>
        <Spin spinning={loading} delay={200}>
          <ReactECharts
            ref={chartRef}
            echarts={echarts}
            option={option}
            style={{ height: chartHeight, minHeight: 400 }}
            notMerge
            lazyUpdate
          />
        </Spin>
      </Card>

      {/* Legend */}
      <Card size="small" title={t('detail.chipseq.cellTypes.legend', 'Cell Types')}>
        <Space wrap>
          {allCellTypes.map((cellType) => {
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

      {/* Summary */}
      <Card size="small">
        <Space orientation="vertical" size={4} style={{ width: '100%', fontSize: 12, color: '#666' }}>
          <div>
            <span style={{ fontWeight: 500 }}>Total dimensions:</span> {data.length} genes × {allMarks.length}{' '}
            marks × {allCellTypes.length} cell types
          </div>
          <div>
            <span style={{ fontWeight: 500 }}>Data points:</span>{' '}
            {data.reduce((sum, g) => sum + g.marks.length * g.cell_types.length, 0)} total
          </div>
          <div style={{ marginTop: 8 }}>
            <span style={{ fontWeight: 500 }}>Genes:</span>{' '}
            {data.map((g) => g.gene_name).join(', ')}
          </div>
        </Space>
      </Card>
    </Space>
  )
}

export default BatchHeatmapMatrix
