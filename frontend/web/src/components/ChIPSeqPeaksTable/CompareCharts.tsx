/**
 * CompareCharts Component
 * Phase 2.2 - ECharts visualizations for multi-mark comparison
 *
 * Charts included:
 * - Bar chart: Peak counts comparison across marks
 * - Signal distribution: Line chart showing signal value distributions
 * - Position distribution: Stacked bar chart for position breakdown
 */

import { useMemo } from 'react'
import ReactECharts from 'echarts-for-react'
import { Row, Col, Card, Empty } from 'antd'
import { useTranslation } from 'react-i18next'
import echarts from '@/utils/echarts'
import type { ECOption } from '@/utils/echarts'
import { getChartToolbox } from '@/utils/chart-export'
import { getMarkColor, getMarkConfig } from '@/config/markConfigs'
import type { MarkType, ChIPSeqCompareResponse, MarkComparisonData } from '@/types/chipseq'

interface CompareChartsProps {
  /** Comparison data from API */
  compareData: ChIPSeqCompareResponse | undefined
  /** Selected marks for comparison */
  selectedMarks: MarkType[]
  /** Loading state */
  loading?: boolean
}

/**
 * Peak Count Bar Chart
 * Compares total peak counts across selected marks
 */
function PeakCountChart({
  data,
  marks,
}: {
  data: MarkComparisonData[]
  marks: MarkType[]
}) {
  const { t } = useTranslation('genes')

  const option: ECOption = useMemo(() => {
    const sortedData = [...data].sort(
      (a, b) => marks.indexOf(a.mark_type) - marks.indexOf(b.mark_type)
    )

    return {
      title: {
        text: t('detail.chipseq.charts.peakCounts', 'Peak Counts by Mark'),
        left: 'center',
        top: 10,
        textStyle: { fontSize: 14, fontWeight: 'bold' },
      },
      toolbox: getChartToolbox(
        t('detail.chipseq.charts.peakCounts', 'Peak Counts'),
        t('export.saveImage', 'Save as Image')
      ),
      tooltip: {
        trigger: 'axis',
        axisPointer: { type: 'shadow' },
        formatter: (params: any) => {
          const p = params[0]
          const config = getMarkConfig(p.name as MarkType)
          return `<strong>${config.displayName}</strong><br/>Peaks: ${p.value.toLocaleString()}`
        },
      },
      xAxis: {
        type: 'category',
        data: sortedData.map((d) => d.mark_type),
        axisLabel: {
          rotate: 45,
          fontSize: 11,
          formatter: (value: string) => getMarkConfig(value as MarkType).shortName,
        },
      },
      yAxis: {
        type: 'value',
        name: t('detail.chipseq.totalPeaks', 'Total Peaks'),
        nameLocation: 'middle',
        nameGap: 45,
        axisLabel: {
          formatter: (value: number) => {
            if (value >= 1000) return `${(value / 1000).toFixed(1)}K`
            return value.toString()
          },
        },
      },
      grid: {
        left: '12%',
        right: '8%',
        bottom: '20%',
        top: '15%',
      },
      series: [
        {
          type: 'bar',
          data: sortedData.map((d) => ({
            value: d.summary.total_peaks,
            itemStyle: { color: getMarkColor(d.mark_type) },
          })),
          barMaxWidth: 50,
          label: {
            show: true,
            position: 'top',
            formatter: (params: any) => params.value.toLocaleString(),
            fontSize: 10,
          },
        },
      ],
    }
  }, [data, marks, t])

  return (
    <ReactECharts
      echarts={echarts}
      option={option}
      style={{ height: 350 }}
      notMerge
      lazyUpdate
    />
  )
}

/**
 * Average Signal Comparison Chart
 * Bar chart comparing average signal values
 */
function SignalComparisonChart({
  data,
  marks,
}: {
  data: MarkComparisonData[]
  marks: MarkType[]
}) {
  const { t } = useTranslation('genes')

  const option: ECOption = useMemo(() => {
    const sortedData = [...data].sort(
      (a, b) => marks.indexOf(a.mark_type) - marks.indexOf(b.mark_type)
    )

    return {
      title: {
        text: t('detail.chipseq.charts.signalComparison', 'Signal Comparison'),
        left: 'center',
        top: 10,
        textStyle: { fontSize: 14, fontWeight: 'bold' },
      },
      toolbox: getChartToolbox(
        t('detail.chipseq.charts.signalComparison', 'Signal Comparison'),
        t('export.saveImage', 'Save as Image')
      ),
      tooltip: {
        trigger: 'axis',
        axisPointer: { type: 'shadow' },
      },
      legend: {
        data: [
          t('detail.chipseq.avgSignal', 'Avg Signal'),
          t('detail.chipseq.maxSignal', 'Max Signal'),
        ],
        top: 35,
      },
      xAxis: {
        type: 'category',
        data: sortedData.map((d) => getMarkConfig(d.mark_type).shortName),
        axisLabel: { rotate: 0, fontSize: 11 },
      },
      yAxis: {
        type: 'value',
        name: t('detail.chipseq.signalValue', 'Signal Value'),
        nameLocation: 'middle',
        nameGap: 50,
      },
      grid: {
        left: '12%',
        right: '8%',
        bottom: '15%',
        top: '25%',
      },
      series: [
        {
          name: t('detail.chipseq.avgSignal', 'Avg Signal'),
          type: 'bar',
          data: sortedData.map((d) => ({
            value: d.summary.avg_signal,
            itemStyle: { color: getMarkColor(d.mark_type) },
          })),
          barMaxWidth: 40,
        },
        {
          name: t('detail.chipseq.maxSignal', 'Max Signal'),
          type: 'bar',
          data: sortedData.map((d) => ({
            value: d.summary.max_signal,
            itemStyle: {
              color: getMarkColor(d.mark_type),
              opacity: 0.5,
            },
          })),
          barMaxWidth: 40,
        },
      ],
    }
  }, [data, marks, t])

  return (
    <ReactECharts
      echarts={echarts}
      option={option}
      style={{ height: 350 }}
      notMerge
      lazyUpdate
    />
  )
}

/**
 * Position Distribution Stacked Bar Chart
 * Shows distribution of peaks across genomic positions for each mark
 */
function PositionDistributionChart({
  data,
  marks,
}: {
  data: MarkComparisonData[]
  marks: MarkType[]
}) {
  const { t } = useTranslation('genes')

  const option: ECOption = useMemo(() => {
    const sortedData = [...data].sort(
      (a, b) => marks.indexOf(a.mark_type) - marks.indexOf(b.mark_type)
    )

    // Get all unique positions across all marks
    const allPositions = new Set<string>()
    sortedData.forEach((d) => {
      Object.keys(d.summary.position_distribution || {}).forEach((pos) =>
        allPositions.add(pos)
      )
    })
    const positions = Array.from(allPositions).sort()

    // Position colors
    const positionColors: Record<string, string> = {
      promoter: '#52c41a',
      upstream: '#1890ff',
      downstream: '#722ed1',
      exon: '#fa8c16',
      intron: '#13c2c2',
      gene_body: '#eb2f96',
      intergenic: '#8c8c8c',
    }

    return {
      title: {
        text: t('detail.chipseq.charts.positionDistribution', 'Position Distribution'),
        left: 'center',
        top: 10,
        textStyle: { fontSize: 14, fontWeight: 'bold' },
      },
      toolbox: getChartToolbox(
        t('detail.chipseq.charts.positionDistribution', 'Position Distribution'),
        t('export.saveImage', 'Save as Image')
      ),
      tooltip: {
        trigger: 'axis',
        axisPointer: { type: 'shadow' },
      },
      legend: {
        data: positions,
        top: 35,
        type: 'scroll',
      },
      xAxis: {
        type: 'category',
        data: sortedData.map((d) => getMarkConfig(d.mark_type).shortName),
      },
      yAxis: {
        type: 'value',
        name: t('detail.chipseq.peakCount', 'Peak Count'),
        nameLocation: 'middle',
        nameGap: 50,
      },
      grid: {
        left: '12%',
        right: '8%',
        bottom: '15%',
        top: '25%',
      },
      series: positions.map((position) => ({
        name: position,
        type: 'bar' as const,
        stack: 'total',
        emphasis: { focus: 'series' as const },
        data: sortedData.map(
          (d) => d.summary.position_distribution?.[position] || 0
        ),
        itemStyle: {
          color: positionColors[position.toLowerCase()] || '#8c8c8c',
        },
      })),
    }
  }, [data, marks, t])

  if (!data.some((d) => Object.keys(d.summary.position_distribution || {}).length > 0)) {
    return null
  }

  return (
    <ReactECharts
      echarts={echarts}
      option={option}
      style={{ height: 350 }}
      notMerge
      lazyUpdate
    />
  )
}

/**
 * Fold Enrichment Comparison Chart
 */
function FoldEnrichmentChart({
  data,
  marks,
}: {
  data: MarkComparisonData[]
  marks: MarkType[]
}) {
  const { t } = useTranslation('genes')

  const option: ECOption = useMemo(() => {
    const sortedData = [...data].sort(
      (a, b) => marks.indexOf(a.mark_type) - marks.indexOf(b.mark_type)
    )

    return {
      title: {
        text: t('detail.chipseq.charts.foldEnrichment', 'Avg Fold Enrichment'),
        left: 'center',
        top: 10,
        textStyle: { fontSize: 14, fontWeight: 'bold' },
      },
      toolbox: getChartToolbox(
        t('detail.chipseq.charts.foldEnrichment', 'Fold Enrichment'),
        t('export.saveImage', 'Save as Image')
      ),
      tooltip: {
        trigger: 'axis',
        axisPointer: { type: 'shadow' },
        formatter: (params: any) => {
          const p = params[0]
          return `${p.name}: ${p.value.toFixed(2)}x`
        },
      },
      xAxis: {
        type: 'category',
        data: sortedData.map((d) => getMarkConfig(d.mark_type).shortName),
      },
      yAxis: {
        type: 'value',
        name: t('detail.chipseq.foldEnrichment', 'Fold Enrichment'),
        nameLocation: 'middle',
        nameGap: 40,
        axisLabel: {
          formatter: '{value}x',
        },
      },
      grid: {
        left: '12%',
        right: '8%',
        bottom: '15%',
        top: '15%',
      },
      series: [
        {
          type: 'bar',
          data: sortedData.map((d) => ({
            value: d.summary.avg_fold_enrichment,
            itemStyle: {
              color: new echarts.graphic.LinearGradient(0, 0, 0, 1, [
                { offset: 0, color: getMarkColor(d.mark_type) },
                { offset: 1, color: `${getMarkColor(d.mark_type)}88` },
              ]),
            },
          })),
          barMaxWidth: 50,
          label: {
            show: true,
            position: 'top',
            formatter: (params: any) => `${params.value.toFixed(1)}x`,
            fontSize: 10,
          },
        },
      ],
    }
  }, [data, marks, t])

  return (
    <ReactECharts
      echarts={echarts}
      option={option}
      style={{ height: 350 }}
      notMerge
      lazyUpdate
    />
  )
}

/**
 * CompareCharts Component
 *
 * Container for all comparison charts.
 * Displays side-by-side visualizations for multi-mark comparison.
 *
 * @example
 * ```tsx
 * <CompareCharts
 *   compareData={comparisonData}
 *   selectedMarks={['H3K27me3', 'H3K4me3']}
 * />
 * ```
 */
export function CompareCharts({
  compareData,
  selectedMarks,
  loading = false,
}: CompareChartsProps) {
  const { t } = useTranslation('genes')

  if (!compareData || compareData.marks.length === 0) {
    return (
      <Empty
        description={t(
          'detail.chipseq.noComparisonData',
          'Select marks to compare'
        )}
      />
    )
  }

  return (
    <Row gutter={[16, 16]}>
      {/* Peak Count Chart */}
      <Col xs={24} lg={12}>
        <Card size="small" loading={loading}>
          <PeakCountChart data={compareData.marks} marks={selectedMarks} />
        </Card>
      </Col>

      {/* Signal Comparison Chart */}
      <Col xs={24} lg={12}>
        <Card size="small" loading={loading}>
          <SignalComparisonChart data={compareData.marks} marks={selectedMarks} />
        </Card>
      </Col>

      {/* Fold Enrichment Chart */}
      <Col xs={24} lg={12}>
        <Card size="small" loading={loading}>
          <FoldEnrichmentChart data={compareData.marks} marks={selectedMarks} />
        </Card>
      </Col>

      {/* Position Distribution Chart */}
      <Col xs={24} lg={12}>
        <Card size="small" loading={loading}>
          <PositionDistributionChart
            data={compareData.marks}
            marks={selectedMarks}
          />
        </Card>
      </Col>
    </Row>
  )
}

export default CompareCharts
