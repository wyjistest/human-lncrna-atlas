/**
 * CellLineHeatmap Component
 * Phase 2.6 - Visualize ChIP-seq signal across cell lines using ECharts heatmap
 *
 * Displays comparison metrics for the same histone mark across different cell lines:
 * - Average signal values
 * - Fold enrichment
 * - Peak counts
 * - Coverage statistics
 */

import { useMemo } from 'react'
import ReactECharts from 'echarts-for-react'
import { Row, Col, Card, Statistic, Space, Typography, Tag, Segmented, Empty } from 'antd'
import { useTranslation } from 'react-i18next'
import echarts from '@/utils/echarts'
import type { ECOption } from '@/utils/echarts'
import { getChartToolbox } from '@/utils/chart-export'
import { getCellTypeColor, getCellTypeLabel, CELL_TYPE_CONFIGS } from '@/config/cellTypeConfigs'
import { getMarkConfig } from '@/config/markConfigs'
import type { CellLineComparisonResponse } from '@/types/chipseq'

const { Text, Title } = Typography

type MetricType = 'signal' | 'fold_enrichment' | 'peak_count' | 'coverage'

interface CellLineHeatmapProps {
  /** Comparison data from API */
  data: CellLineComparisonResponse
  /** Current metric to display */
  metric?: MetricType
  /** Callback when metric changes */
  onMetricChange?: (metric: MetricType) => void
  /** Loading state */
  loading?: boolean
}

/**
 * Get metric value from cell line entry
 */
function getMetricValue(
  entry: CellLineComparisonResponse['cell_lines'][0],
  metric: MetricType
): number {
  switch (metric) {
    case 'signal':
      return entry.avg_signal || 0
    case 'fold_enrichment':
      return entry.median_fold_enrichment || 0
    case 'peak_count':
      return entry.total_peaks
    case 'coverage':
      return entry.total_coverage_bp
    default:
      return 0
  }
}

/**
 * Format metric value for display
 */
function formatMetricValue(value: number, metric: MetricType): string {
  switch (metric) {
    case 'signal':
      return value.toFixed(2)
    case 'fold_enrichment':
      return `${value.toFixed(2)}x`
    case 'peak_count':
      return value.toLocaleString()
    case 'coverage':
      if (value >= 1000000) return `${(value / 1000000).toFixed(2)} Mb`
      if (value >= 1000) return `${(value / 1000).toFixed(1)} kb`
      return `${value} bp`
    default:
      return value.toString()
  }
}

/**
 * CellLineHeatmap Component
 *
 * Visualizes ChIP-seq metrics across multiple cell lines for the same mark.
 * Supports multiple visualization metrics and interactive tooltips.
 *
 * @example
 * ```tsx
 * <CellLineHeatmap
 *   data={cellLineComparisonData}
 *   metric="fold_enrichment"
 *   onMetricChange={(m) => setMetric(m)}
 * />
 * ```
 */
export function CellLineHeatmap({
  data,
  metric = 'fold_enrichment',
  onMetricChange,
  loading = false,
}: CellLineHeatmapProps) {
  const { t, i18n } = useTranslation('genes')
  const isZh = i18n.language === 'zh-CN'

  const markConfig = getMarkConfig(data.mark_type as any)

  // Metric options for segmented control
  const metricOptions = useMemo(
    () => [
      {
        value: 'fold_enrichment',
        label: t('detail.chipseq.cellLineCompare.foldEnrichment', 'Fold Enrichment'),
      },
      {
        value: 'signal',
        label: t('detail.chipseq.cellLineCompare.avgSignal', 'Avg Signal'),
      },
      {
        value: 'peak_count',
        label: t('detail.chipseq.cellLineCompare.peakCount', 'Peak Count'),
      },
      {
        value: 'coverage',
        label: t('detail.chipseq.cellLineCompare.coverage', 'Coverage'),
      },
    ],
    [t]
  )

  // Generate heatmap option
  const heatmapOption = useMemo(() => {
    if (!data.cell_lines || data.cell_lines.length === 0) {
      return {} as ECOption
    }

    // Prepare data for heatmap
    const cellTypes = data.cell_lines.map((cl) => cl.cell_type)
    const values = data.cell_lines.map((cl, idx) => {
      const value = getMetricValue(cl, metric)
      return [idx, 0, value]
    })

    const maxValue = Math.max(...values.map((v) => v[2] as number), 1)

    // Get cell type labels
    const cellTypeLabels = cellTypes.map((ct) => getCellTypeLabel(ct, i18n.language))

    // Get colors based on metric type
    const getColorRange = () => {
      switch (metric) {
        case 'fold_enrichment':
          return ['#f0f5ff', '#1890ff', '#003a8c']
        case 'signal':
          return ['#fff7e6', '#fa8c16', '#ad4e00']
        case 'peak_count':
          return ['#f6ffed', '#52c41a', '#135200']
        case 'coverage':
          return ['#fff0f6', '#eb2f96', '#9e1068']
        default:
          return ['#f0f5ff', '#1890ff', '#003a8c']
      }
    }

    return {
      title: {
        text: t('detail.chipseq.cellLineCompare.heatmapTitle', 'Cell Line Comparison: {{mark}}', {
          mark: data.mark_type,
        }),
        left: 'center',
        top: 10,
        textStyle: { fontSize: 14, fontWeight: 'bold' },
      },
      toolbox: getChartToolbox(
        t('detail.chipseq.cellLineCompare.heatmapTitle', 'Cell Line Comparison'),
        t('export.saveImage', 'Save as Image')
      ),
      tooltip: {
        position: 'top',
        formatter: (params: any) => {
          const cellType = cellTypes[params.data[0]]
          const cellConfig = CELL_TYPE_CONFIGS[cellType]
          const value = params.data[2]
          const formattedValue = formatMetricValue(value, metric)
          const label = isZh ? cellConfig?.labelZh : cellConfig?.label
          return [
            `<strong>${label || cellType}</strong>`,
            `<br/>`,
            `${metricOptions.find((o) => o.value === metric)?.label}: <strong>${formattedValue}</strong>`,
          ].join('')
        },
      },
      grid: {
        left: '20%',
        right: '10%',
        bottom: '15%',
        top: '20%',
      },
      xAxis: {
        type: 'category',
        data: [data.mark_type],
        splitArea: { show: true },
        axisLabel: {
          fontSize: 12,
          fontWeight: 'bold',
          color: markConfig?.color || '#333',
        },
      },
      yAxis: {
        type: 'category',
        data: cellTypeLabels,
        splitArea: { show: true },
        axisLabel: {
          fontSize: 11,
          formatter: (value: string, index: number) => {
            // Add cell type color indicator
            getCellTypeColor(cellTypes[index]) // Reference to keep variable used
            return `● ${value}`
          },
        },
      },
      visualMap: {
        min: 0,
        max: maxValue,
        calculable: true,
        orient: 'horizontal',
        left: 'center',
        bottom: '0%',
        itemWidth: 15,
        itemHeight: 100,
        inRange: {
          color: getColorRange(),
        },
        formatter: (value: number) => formatMetricValue(value, metric),
      },
      series: [
        {
          name: metric,
          type: 'heatmap',
          data: values,
          label: {
            show: true,
            formatter: (params: any) => formatMetricValue(params.data[2], metric),
            fontSize: 12,
            fontWeight: 'bold',
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
  }, [data, metric, t, i18n.language, isZh, markConfig, metricOptions])

  // Bar chart option for comparison
  const barChartOption: ECOption = useMemo(() => {
    if (!data.cell_lines || data.cell_lines.length === 0) {
      return {}
    }

    const cellTypes = data.cell_lines.map((cl) => cl.cell_type)
    const values = data.cell_lines.map((cl) => getMetricValue(cl, metric))
    const colors = cellTypes.map((ct) => getCellTypeColor(ct))

    return {
      title: {
        text: t('detail.chipseq.cellLineCompare.barChartTitle', '{{metric}} by Cell Line', {
          metric: metricOptions.find((o) => o.value === metric)?.label || metric,
        }),
        left: 'center',
        top: 10,
        textStyle: { fontSize: 14, fontWeight: 'bold' },
      },
      toolbox: getChartToolbox(
        t('detail.chipseq.cellLineCompare.barChartTitle', 'Cell Line Comparison'),
        t('export.saveImage', 'Save as Image')
      ),
      tooltip: {
        trigger: 'axis',
        axisPointer: { type: 'shadow' },
        formatter: (params: any) => {
          const p = params[0]
          const cellType = cellTypes[p.dataIndex]
          const cellConfig = CELL_TYPE_CONFIGS[cellType]
          const label = isZh ? cellConfig?.labelZh : cellConfig?.label
          return [
            `<strong>${label || cellType}</strong>`,
            `<br/>`,
            `${metricOptions.find((o) => o.value === metric)?.label}: <strong>${formatMetricValue(p.value, metric)}</strong>`,
          ].join('')
        },
      },
      grid: {
        left: '15%',
        right: '8%',
        bottom: '20%',
        top: '18%',
      },
      xAxis: {
        type: 'category',
        data: cellTypes.map((ct) => getCellTypeLabel(ct, i18n.language)),
        axisLabel: {
          rotate: 30,
          fontSize: 11,
          interval: 0,
        },
      },
      yAxis: {
        type: 'value',
        name: metricOptions.find((o) => o.value === metric)?.label,
        nameLocation: 'middle',
        nameGap: 45,
        axisLabel: {
          formatter: (value: number) => {
            if (metric === 'coverage') {
              if (value >= 1000000) return `${(value / 1000000).toFixed(1)}M`
              if (value >= 1000) return `${(value / 1000).toFixed(0)}k`
            }
            if (value >= 1000) return `${(value / 1000).toFixed(1)}k`
            return value.toString()
          },
        },
      },
      series: [
        {
          type: 'bar',
          data: values.map((v, idx) => ({
            value: v,
            itemStyle: {
              color: new echarts.graphic.LinearGradient(0, 0, 0, 1, [
                { offset: 0, color: colors[idx] },
                { offset: 1, color: `${colors[idx]}88` },
              ]),
            },
          })),
          barMaxWidth: 60,
          label: {
            show: true,
            position: 'top',
            formatter: (params: any) => formatMetricValue(params.value, metric),
            fontSize: 10,
          },
        },
      ],
    }
  }, [data, metric, t, i18n.language, isZh, metricOptions])

  if (!data.cell_lines || data.cell_lines.length === 0) {
    return (
      <Empty
        description={t('detail.chipseq.cellLineCompare.noData', 'No cell line comparison data available')}
      />
    )
  }

  return (
    <Space orientation="vertical" size="large" style={{ width: '100%' }}>
      {/* Header with mark info */}
      <Card size="small">
        <Row gutter={[16, 16]} align="middle">
          <Col xs={24} md={12}>
            <Space>
              <Title level={5} style={{ margin: 0 }}>
                {t('detail.chipseq.cellLineComparisonTitle', 'Cell Line Comparison for {{mark}}', {
                  mark: data.mark_type,
                })}
              </Title>
              <Tag color={markConfig?.color}>{data.mark_type}</Tag>
            </Space>
          </Col>
          <Col xs={24} md={12}>
            <Segmented
              options={metricOptions}
              value={metric}
              onChange={(value) => onMetricChange?.(value as MetricType)}
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
              title={t('detail.chipseq.cellLineCompare.totalCellLines', 'Cell Lines')}
              value={data.total_cell_lines}
            />
          </Card>
        </Col>
        <Col xs={12} sm={6}>
          <Card size="small">
            <Statistic
              title={t('detail.chipseq.cellLineCompare.commonPeaks', 'Common Peaks')}
              value={data.common_peaks}
            />
          </Card>
        </Col>
        <Col xs={12} sm={6}>
          <Card size="small">
            <Statistic
              title={t('detail.chipseq.cellLineCompare.region', 'Region')}
              value={`${data.chromosome}:${data.region_start.toLocaleString()}-${data.region_end.toLocaleString()}`}
              styles={{ content: { fontSize: 12 } }}
            />
          </Card>
        </Col>
        <Col xs={12} sm={6}>
          <Card size="small">
            <Statistic
              title={t('detail.chipseq.cellLineCompare.geneName', 'Gene')}
              value={data.gene_name}
            />
          </Card>
        </Col>
      </Row>

      {/* Charts */}
      <Row gutter={[16, 16]}>
        {/* Heatmap */}
        <Col xs={24} lg={12}>
          <Card size="small" loading={loading}>
            <ReactECharts
              echarts={echarts}
              option={heatmapOption}
              style={{ height: 200 + data.cell_lines.length * 50 }}
              notMerge
              lazyUpdate
            />
          </Card>
        </Col>

        {/* Bar Chart */}
        <Col xs={24} lg={12}>
          <Card size="small" loading={loading}>
            <ReactECharts
              echarts={echarts}
              option={barChartOption}
              style={{ height: 200 + data.cell_lines.length * 50 }}
              notMerge
              lazyUpdate
            />
          </Card>
        </Col>
      </Row>

      {/* Cell Line Details Table */}
      <Card
        size="small"
        title={t('detail.chipseq.cellLineCompare.detailsTitle', 'Cell Line Details')}
      >
        <Row gutter={[16, 16]}>
          {data.cell_lines.map((cl) => {
            const config = CELL_TYPE_CONFIGS[cl.cell_type]
            return (
              <Col key={cl.cell_type} xs={24} sm={12} md={8} lg={6}>
                <Card
                  size="small"
                  style={{ borderLeft: `4px solid ${getCellTypeColor(cl.cell_type)}` }}
                >
                  <Space orientation="vertical" size={4} style={{ width: '100%' }}>
                    <Text strong>
                      {isZh ? config?.labelZh : config?.label || cl.cell_type}
                    </Text>
                    <Row gutter={[8, 4]}>
                      <Col span={12}>
                        <Text type="secondary" style={{ fontSize: 12 }}>
                          {t('detail.chipseq.totalPeaks', 'Peaks')}
                        </Text>
                        <br />
                        <Text strong>{cl.total_peaks.toLocaleString()}</Text>
                      </Col>
                      <Col span={12}>
                        <Text type="secondary" style={{ fontSize: 12 }}>
                          {t('detail.chipseq.foldEnrichment', 'Fold Enrichment')}
                        </Text>
                        <br />
                        <Text strong>{cl.median_fold_enrichment?.toFixed(2) || 'N/A'}x</Text>
                      </Col>
                      <Col span={12}>
                        <Text type="secondary" style={{ fontSize: 12 }}>
                          {t('detail.chipseq.avgSignal', 'Avg Signal')}
                        </Text>
                        <br />
                        <Text strong>{cl.avg_signal?.toFixed(2) || 'N/A'}</Text>
                      </Col>
                      <Col span={12}>
                        <Text type="secondary" style={{ fontSize: 12 }}>
                          {t('detail.chipseq.cellLineCompare.coverage', 'Coverage')}
                        </Text>
                        <br />
                        <Text strong>{formatMetricValue(cl.total_coverage_bp, 'coverage')}</Text>
                      </Col>
                    </Row>
                  </Space>
                </Card>
              </Col>
            )
          })}
        </Row>
      </Card>
    </Space>
  )
}

export default CellLineHeatmap
