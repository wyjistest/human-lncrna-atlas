/**
 * CompareCharts Component
 * Phase 2.2/2.5 - ECharts visualizations for multi-mark comparison
 *
 * Charts included:
 * - Bar chart: Peak counts comparison across marks
 * - Signal distribution: Line chart showing signal value distributions
 * - Position distribution: Stacked bar chart for position breakdown
 * - Overlap statistics: Heatmap/matrix showing overlap between marks (Phase 2.5)
 * - Peak width distribution: Box plot showing peak width percentiles (Phase 2.5)
 */

import { useMemo } from 'react'
import ReactECharts from 'echarts-for-react'
import { Row, Col, Card, Empty, Statistic, Space, Typography } from 'antd'
import { useTranslation } from 'react-i18next'
import echarts from '@/utils/echarts'
import type { ECOption } from '@/utils/echarts'
import { getChartToolbox } from '@/utils/chart-export'
import { getMarkColor, getMarkConfig } from '@/config/markConfigs'
import type { MarkType, ChIPSeqCompareResponse, MarkComparisonData, OverlapRegion } from '@/types/chipseq'
import type { TooltipFormatterParams, BarParams, HeatmapParams, BoxplotParams } from '@/types/echarts'

const { Text } = Typography

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
        formatter: (params: unknown) => {
          const arr = params as TooltipFormatterParams[]
          const p = arr[0]
          const config = getMarkConfig(p.name as MarkType)
          return `<strong>${config.displayName}</strong><br/>Peaks: ${(p.value as number).toLocaleString()}`
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
            formatter: (params: unknown) => {
              const p = params as BarParams
              return (p.value as number).toLocaleString()
            },
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
 * Signal/Enrichment Comparison Chart
 * Bar chart comparing fold enrichment values (avg and max)
 * Note: Uses fold_enrichment as proxy for signal values since the compare API
 * doesn't return signal_value directly
 */
function SignalComparisonChart({
  data,
  marks,
}: {
  data: MarkComparisonData[]
  marks: MarkType[]
}) {
  const { t } = useTranslation('genes')

  // Check if we have actual data to display
  const hasData = data.some(
    (d) => d.summary.avg_signal > 0 || d.summary.max_signal > 0
  )

  const option: ECOption = useMemo(() => {
    const sortedData = [...data].sort(
      (a, b) => marks.indexOf(a.mark_type) - marks.indexOf(b.mark_type)
    )

    return {
      title: {
        text: t('detail.chipseq.charts.enrichmentComparison', 'Enrichment Comparison'),
        subtext: t('detail.chipseq.charts.enrichmentSubtitle', 'Fold enrichment over background'),
        left: 'center',
        top: 5,
        textStyle: { fontSize: 14, fontWeight: 'bold' },
        subtextStyle: { fontSize: 11, color: '#888' },
      },
      toolbox: getChartToolbox(
        t('detail.chipseq.charts.enrichmentComparison', 'Enrichment Comparison'),
        t('export.saveImage', 'Save as Image')
      ),
      tooltip: {
        trigger: 'axis',
        axisPointer: { type: 'shadow' },
        formatter: (params: unknown) => {
          const arr = params as TooltipFormatterParams[]
          if (!Array.isArray(arr) || arr.length === 0) return ''
          const markName = arr[0].name
          const avgVal = (arr[0]?.value as number) ?? 0
          const maxVal = (arr[1]?.value as number) ?? 0
          return [
            `<strong>${markName}</strong>`,
            `${t('detail.chipseq.avgFoldEnrichment', 'Avg Fold Enrichment')}: ${avgVal.toFixed(2)}x`,
            `${t('detail.chipseq.maxFoldEnrichment', 'Max Fold Enrichment')}: ${maxVal.toFixed(2)}x`,
          ].join('<br/>')
        },
      },
      legend: {
        data: [
          t('detail.chipseq.avgFoldEnrichment', 'Avg Enrichment'),
          t('detail.chipseq.maxFoldEnrichment', 'Max Enrichment'),
        ],
        top: 40,
      },
      xAxis: {
        type: 'category',
        data: sortedData.map((d) => getMarkConfig(d.mark_type).shortName),
        axisLabel: { rotate: 0, fontSize: 11 },
      },
      yAxis: {
        type: 'value',
        name: t('detail.chipseq.foldEnrichment', 'Fold Enrichment'),
        nameLocation: 'middle',
        nameGap: 50,
        axisLabel: {
          formatter: '{value}x',
        },
      },
      grid: {
        left: '12%',
        right: '8%',
        bottom: '15%',
        top: '28%',
      },
      series: [
        {
          name: t('detail.chipseq.avgFoldEnrichment', 'Avg Enrichment'),
          type: 'bar',
          data: sortedData.map((d) => ({
            value: d.summary.avg_signal, // This is actually avg_fold_enrichment
            itemStyle: { color: getMarkColor(d.mark_type) },
          })),
          barMaxWidth: 40,
          label: {
            show: true,
            position: 'top',
            formatter: (params: unknown) => {
              const p = params as BarParams
              return `${(p.value as number).toFixed(1)}x`
            },
            fontSize: 9,
          },
        },
        {
          name: t('detail.chipseq.maxFoldEnrichment', 'Max Enrichment'),
          type: 'bar',
          data: sortedData.map((d) => ({
            value: d.summary.max_signal, // This is actually max_fold_enrichment
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

  // Show empty state if no data
  if (!hasData) {
    return (
      <Empty
        image={Empty.PRESENTED_IMAGE_SIMPLE}
        description={t(
          'detail.chipseq.noEnrichmentData',
          'Enrichment data not available'
        )}
        style={{ padding: 48 }}
      />
    )
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
        formatter: (params: unknown) => {
          const arr = params as TooltipFormatterParams[]
          const p = arr[0]
          return `${p.name}: ${(p.value as number).toFixed(2)}x`
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
            formatter: (params: unknown) => {
              const p = params as BarParams
              return `${(p.value as number).toFixed(1)}x`
            },
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
 * Overlap Statistics Display
 * Shows overlap region counts between mark pairs
 */
function OverlapStatsCard({
  overlapRegions,
  marks,
}: {
  overlapRegions?: OverlapRegion[]
  marks: MarkType[]
}) {
  const { t } = useTranslation('genes')

  if (!overlapRegions || overlapRegions.length === 0) {
    return null
  }

  // Filter only overlaps between selected marks
  const relevantOverlaps = overlapRegions.filter(
    (r) => marks.includes(r.mark1) && marks.includes(r.mark2)
  )

  if (relevantOverlaps.length === 0) {
    return null
  }

  return (
    <Card
      size="small"
      title={t('detail.chipseq.charts.overlapStats', 'Overlap Statistics')}
    >
      <Space orientation="vertical" size="middle" style={{ width: '100%' }}>
        {relevantOverlaps.map((overlap, idx) => (
          <div
            key={idx}
            style={{
              display: 'flex',
              justifyContent: 'space-between',
              alignItems: 'center',
              padding: '8px 12px',
              backgroundColor: '#fafafa',
              borderRadius: 4,
            }}
          >
            <Space>
              <span
                style={{
                  display: 'inline-block',
                  width: 12,
                  height: 12,
                  borderRadius: 2,
                  backgroundColor: getMarkColor(overlap.mark1),
                }}
              />
              <Text>{getMarkConfig(overlap.mark1).shortName}</Text>
              <Text type="secondary">&</Text>
              <span
                style={{
                  display: 'inline-block',
                  width: 12,
                  height: 12,
                  borderRadius: 2,
                  backgroundColor: getMarkColor(overlap.mark2),
                }}
              />
              <Text>{getMarkConfig(overlap.mark2).shortName}</Text>
            </Space>
            <Space size="large">
              <Statistic
                title={t('detail.chipseq.bivalent.regionCount', 'Regions')}
                value={overlap.region_count}
                styles={{ content: { fontSize: 16 } }}
              />
              <Statistic
                title={t('detail.chipseq.bivalent.totalBp', 'Coverage')}
                value={overlap.total_bp}
                suffix="bp"
                styles={{ content: { fontSize: 16 } }}
              />
            </Space>
          </div>
        ))}
      </Space>
    </Card>
  )
}

/**
 * Peak Width Distribution Chart
 * Box plot showing peak width percentiles (p25, p50, p75) for each mark
 */
function PeakWidthDistributionChart({
  data,
  marks,
}: {
  data: MarkComparisonData[]
  marks: MarkType[]
}) {
  const { t } = useTranslation('genes')

  // Check if any mark has peak width percentiles data
  const hasData = data.some((d) => d.summary.peak_width_percentiles)

  const option: ECOption = useMemo(() => {
    const sortedData = [...data].sort(
      (a, b) => marks.indexOf(a.mark_type) - marks.indexOf(b.mark_type)
    )

    // Filter only marks with percentile data
    const marksWithData = sortedData.filter((d) => d.summary.peak_width_percentiles)

    if (marksWithData.length === 0) {
      return {}
    }

    // Prepare boxplot data: [min, Q1, median, Q3, max]
    // Since we only have p25, p50, p75, we'll estimate min/max
    const boxplotData = marksWithData.map((d) => {
      const percentiles = d.summary.peak_width_percentiles!
      const iqr = percentiles.p75 - percentiles.p25
      const estimatedMin = Math.max(0, percentiles.p25 - 1.5 * iqr)
      const estimatedMax = percentiles.p75 + 1.5 * iqr

      return {
        value: [estimatedMin, percentiles.p25, percentiles.p50, percentiles.p75, estimatedMax],
        itemStyle: { color: getMarkColor(d.mark_type), borderColor: getMarkColor(d.mark_type) },
      }
    })

    return {
      title: {
        text: t('detail.chipseq.charts.peakWidthDistribution', 'Peak Width Distribution'),
        left: 'center',
        top: 10,
        textStyle: { fontSize: 14, fontWeight: 'bold' },
      },
      toolbox: getChartToolbox(
        t('detail.chipseq.charts.peakWidthDistribution', 'Peak Width'),
        t('export.saveImage', 'Save as Image')
      ),
      tooltip: {
        trigger: 'item',
        formatter: (params: unknown) => {
          const p = params as BoxplotParams
          const [min, q1, median, q3, max] = p.value
          return [
            `<strong>${p.name}</strong>`,
            `Max: ${max.toFixed(0)} bp`,
            `Q3 (75%): ${q3.toFixed(0)} bp`,
            `Median: ${median.toFixed(0)} bp`,
            `Q1 (25%): ${q1.toFixed(0)} bp`,
            `Min: ${min.toFixed(0)} bp`,
          ].join('<br/>')
        },
      },
      grid: {
        left: '15%',
        right: '10%',
        bottom: '15%',
        top: '20%',
      },
      xAxis: {
        type: 'category',
        data: marksWithData.map((d) => getMarkConfig(d.mark_type).shortName),
        axisLabel: { rotate: 0, fontSize: 11 },
      },
      yAxis: {
        type: 'value',
        name: t('detail.chipseq.charts.peakWidthBp', 'Peak Width (bp)'),
        nameLocation: 'middle',
        nameGap: 50,
      },
      series: [
        {
          name: 'Peak Width',
          type: 'boxplot',
          data: boxplotData,
        },
      ],
    }
  }, [data, marks, t])

  if (!hasData) {
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
 * Overlap Heatmap Chart
 * Matrix visualization showing overlap intensity between mark pairs
 */
function OverlapHeatmapChart({
  overlapRegions,
  marks,
}: {
  overlapRegions?: OverlapRegion[]
  marks: MarkType[]
}) {
  const { t } = useTranslation('genes')

  const option: ECOption = useMemo(() => {
    if (!overlapRegions || overlapRegions.length === 0 || marks.length < 2) {
      return {}
    }

    // Create matrix data for heatmap
    const markLabels = marks.map((m) => getMarkConfig(m).shortName)
    const heatmapData: Array<[number, number, number]> = []
    const maxValue = Math.max(...overlapRegions.map((r) => r.region_count), 1)

    // Build the heatmap matrix
    marks.forEach((mark1, i) => {
      marks.forEach((mark2, j) => {
        if (i === j) {
          // Diagonal - self overlap (full count)
          heatmapData.push([i, j, -1]) // -1 indicates self
        } else {
          const overlap = overlapRegions.find(
            (r) =>
              (r.mark1 === mark1 && r.mark2 === mark2) ||
              (r.mark1 === mark2 && r.mark2 === mark1)
          )
          heatmapData.push([i, j, overlap ? overlap.region_count : 0])
        }
      })
    })

    return {
      title: {
        text: t('detail.chipseq.charts.overlapHeatmap', 'Mark Overlap Heatmap'),
        left: 'center',
        top: 10,
        textStyle: { fontSize: 14, fontWeight: 'bold' },
      },
      toolbox: getChartToolbox(
        t('detail.chipseq.charts.overlapHeatmap', 'Overlap Heatmap'),
        t('export.saveImage', 'Save as Image')
      ),
      tooltip: {
        position: 'top',
        formatter: (params: unknown) => {
          const p = params as HeatmapParams
          const dataArr = Array.isArray(p.data) ? p.data : p.data.value
          const [x, y, value] = dataArr
          if (value === -1) {
            return `${markLabels[x]}: Self`
          }
          return `${markLabels[x]} & ${markLabels[y]}: ${value} regions`
        },
      },
      grid: {
        left: '15%',
        right: '15%',
        bottom: '15%',
        top: '20%',
      },
      xAxis: {
        type: 'category',
        data: markLabels,
        splitArea: { show: true },
        axisLabel: { fontSize: 11 },
      },
      yAxis: {
        type: 'category',
        data: markLabels,
        splitArea: { show: true },
        axisLabel: { fontSize: 11 },
      },
      visualMap: {
        min: 0,
        max: maxValue,
        calculable: true,
        orient: 'horizontal',
        left: 'center',
        bottom: '0%',
        inRange: {
          color: ['#f0f5ff', '#1890ff', '#003a8c'],
        },
      },
      series: [
        {
          name: 'Overlap',
          type: 'heatmap',
          data: heatmapData.filter((d) => d[2] !== -1), // Exclude self
          label: {
            show: true,
            formatter: (params: unknown) => {
              const p = params as HeatmapParams
              const dataArr = Array.isArray(p.data) ? p.data : p.data.value
              return (dataArr[2] ?? 0).toString()
            },
          },
          emphasis: {
            itemStyle: {
              shadowBlur: 10,
              shadowColor: 'rgba(0, 0, 0, 0.5)',
            },
          },
        },
      ],
    }
  }, [overlapRegions, marks, t])

  if (!overlapRegions || overlapRegions.length === 0 || marks.length < 2) {
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

  // Check if we have overlap data
  const hasOverlapData = compareData.overlap_regions && compareData.overlap_regions.length > 0

  // Check if we have peak width percentiles data
  const hasPeakWidthData = compareData.marks.some(
    (m) => m.summary.peak_width_percentiles
  )

  return (
    <Row gutter={[16, 16]}>
      {/* Overlap Statistics Card (Phase 2.5) */}
      {hasOverlapData && (
        <Col xs={24}>
          <OverlapStatsCard
            overlapRegions={compareData.overlap_regions}
            marks={selectedMarks}
          />
        </Col>
      )}

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

      {/* Peak Width Distribution Chart (Phase 2.5) */}
      {hasPeakWidthData && (
        <Col xs={24} lg={12}>
          <Card size="small" loading={loading}>
            <PeakWidthDistributionChart
              data={compareData.marks}
              marks={selectedMarks}
            />
          </Card>
        </Col>
      )}

      {/* Overlap Heatmap Chart (Phase 2.5) */}
      {hasOverlapData && selectedMarks.length >= 2 && (
        <Col xs={24} lg={12}>
          <Card size="small" loading={loading}>
            <OverlapHeatmapChart
              overlapRegions={compareData.overlap_regions}
              marks={selectedMarks}
            />
          </Card>
        </Col>
      )}
    </Row>
  )
}

export default CompareCharts
