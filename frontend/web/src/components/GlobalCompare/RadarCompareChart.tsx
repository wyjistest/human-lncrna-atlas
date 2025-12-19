/**
 * RadarCompareChart Component
 * Phase 2.5 - ECharts radar chart for multi-mark comparison
 *
 * Displays a radar/spider chart showing multiple marks compared across
 * different dimensions like peak count, signal strength, coverage, etc.
 *
 * Features:
 * - Multi-series radar for comparing marks
 * - Dynamic indicator scaling based on data
 * - Color-coded by mark type
 * - Interactive legend and tooltips
 * - i18n support
 */

import { useMemo } from 'react'
import { escapeHtml } from '@/utils/escapeHtml'
import ReactECharts from 'echarts-for-react'
import { Empty } from 'antd'
import { useTranslation } from 'react-i18next'
import echarts from '@/utils/echarts'
import type { ECOption } from '@/utils/echarts'
import { getChartToolbox } from '@/utils/chart-export'
import { getMarkColor, getMarkConfig } from '@/config/markConfigs'
import type { GlobalMarkSummary } from '@/types/globalCompare'
import type { RadarParams } from '@/types/echarts'

interface RadarCompareChartProps {
  /** Mark summary data for comparison */
  data: GlobalMarkSummary[]
  /** Loading state */
  loading?: boolean
  /** Chart height */
  height?: number
  /** Radar shape: circle or polygon */
  shape?: 'circle' | 'polygon'
}

/**
 * Normalize value to 0-100 scale for radar display
 */
function normalizeValue(value: number, max: number): number {
  if (max === 0) return 0
  return (value / max) * 100
}

/**
 * Format large numbers for display
 */
function formatNumber(value: number): string {
  if (value >= 1000000) return `${(value / 1000000).toFixed(1)}M`
  if (value >= 1000) return `${(value / 1000).toFixed(1)}K`
  return value.toFixed(0)
}

/**
 * RadarCompareChart Component
 *
 * Renders a radar chart comparing multiple marks across various dimensions.
 *
 * @example
 * ```tsx
 * <RadarCompareChart
 *   data={markSummaries}
 *   height={450}
 *   shape="polygon"
 * />
 * ```
 */
export function RadarCompareChart({
  data,
  loading = false,
  height = 450,
  shape = 'polygon',
}: RadarCompareChartProps) {
  const { t } = useTranslation('globalCompare')

  // Calculate max values for each dimension
  const maxValues = useMemo(() => {
    if (!data || data.length === 0) {
      return {
        total_peaks: 1,
        avg_signal: 1,
        total_coverage_bp: 1,
        cell_type_count: 1,
        gene_count: 1,
        avg_fold_enrichment: 1,
      }
    }

    return {
      total_peaks: Math.max(...data.map((d) => d.total_peaks), 1),
      avg_signal: Math.max(...data.map((d) => d.avg_signal), 1),
      total_coverage_bp: Math.max(...data.map((d) => d.total_coverage_bp), 1),
      cell_type_count: Math.max(...data.map((d) => d.cell_type_count), 1),
      gene_count: Math.max(...data.map((d) => d.gene_count), 1),
      avg_fold_enrichment: Math.max(...data.map((d) => d.avg_fold_enrichment), 1),
    }
  }, [data])

  // Radar indicator configuration
  const indicators = useMemo(
    () => [
      {
        name: t('charts.radar.peakCount', 'Peak Count'),
        max: 100,
        key: 'total_peaks' as const,
      },
      {
        name: t('charts.radar.avgSignal', 'Avg Signal'),
        max: 100,
        key: 'avg_signal' as const,
      },
      {
        name: t('charts.radar.coverage', 'Coverage'),
        max: 100,
        key: 'total_coverage_bp' as const,
      },
      {
        name: t('charts.radar.cellTypes', 'Cell Types'),
        max: 100,
        key: 'cell_type_count' as const,
      },
      {
        name: t('charts.radar.geneCount', 'Gene Count'),
        max: 100,
        key: 'gene_count' as const,
      },
      {
        name: t('charts.radar.foldEnrichment', 'Fold Enrichment'),
        max: 100,
        key: 'avg_fold_enrichment' as const,
      },
    ],
    [t]
  )

  // ECharts option configuration
  const option: ECOption = useMemo(() => {
    if (!data || data.length === 0) {
      return {}
    }

    // Prepare series data
    const seriesData = data.map((mark) => ({
      name: getMarkConfig(mark.mark_type)?.displayName || mark.mark_type,
      value: [
        normalizeValue(mark.total_peaks, maxValues.total_peaks),
        normalizeValue(mark.avg_signal, maxValues.avg_signal),
        normalizeValue(mark.total_coverage_bp, maxValues.total_coverage_bp),
        normalizeValue(mark.cell_type_count, maxValues.cell_type_count),
        normalizeValue(mark.gene_count, maxValues.gene_count),
        normalizeValue(mark.avg_fold_enrichment, maxValues.avg_fold_enrichment),
      ],
      // Store original values for tooltip
      originalValues: {
        total_peaks: mark.total_peaks,
        avg_signal: mark.avg_signal,
        total_coverage_bp: mark.total_coverage_bp,
        cell_type_count: mark.cell_type_count,
        gene_count: mark.gene_count,
        avg_fold_enrichment: mark.avg_fold_enrichment,
      },
      itemStyle: {
        color: getMarkColor(mark.mark_type),
      },
      lineStyle: {
        color: getMarkColor(mark.mark_type),
        width: 2,
      },
      areaStyle: {
        color: new echarts.graphic.LinearGradient(0, 0, 0, 1, [
          { offset: 0, color: `${getMarkColor(mark.mark_type)}66` },
          { offset: 1, color: `${getMarkColor(mark.mark_type)}11` },
        ]),
      },
    }))

    return {
      title: {
        text: t('charts.radar.title', 'Multi-Mark Comparison'),
        left: 'center',
        top: 10,
        textStyle: {
          fontSize: 16,
          fontWeight: 'bold',
        },
      },
      toolbox: getChartToolbox(
        t('charts.radar.title', 'Multi-Mark Comparison'),
        t('export.saveImage', 'Save as Image')
      ),
      legend: {
        data: data.map((m) => getMarkConfig(m.mark_type)?.displayName || m.mark_type),
        top: 40,
        type: 'scroll',
        orient: 'horizontal',
      },
      tooltip: {
        trigger: 'item',
        formatter: (params: unknown) => {
          const p = params as RadarParams & { data?: { originalValues?: GlobalMarkSummary } }
          if (!p.data || !p.data.originalValues) return ''

          const markName = p.name
          const originalValues = p.data.originalValues

          const lines = [
            `<strong>${escapeHtml(markName)}</strong>`,
            `${t('charts.radar.peakCount', 'Peaks')}: ${formatNumber(originalValues.total_peaks)}`,
            `${t('charts.radar.avgSignal', 'Avg Signal')}: ${originalValues.avg_signal.toFixed(2)}`,
            `${t('charts.radar.coverage', 'Coverage')}: ${formatNumber(originalValues.total_coverage_bp)} bp`,
            `${t('charts.radar.cellTypes', 'Cell Types')}: ${originalValues.cell_type_count}`,
            `${t('charts.radar.geneCount', 'Genes')}: ${formatNumber(originalValues.gene_count)}`,
            `${t('charts.radar.foldEnrichment', 'Avg Enrichment')}: ${originalValues.avg_fold_enrichment.toFixed(2)}x`,
          ]

          return lines.join('<br/>')
        },
      },
      radar: {
        indicator: indicators.map((ind) => ({
          name: ind.name,
          max: ind.max,
        })),
        shape: shape,
        center: ['50%', '55%'],
        radius: '65%',
        axisName: {
          color: '#333',
          fontSize: 12,
        },
        splitNumber: 5,
        splitArea: {
          areaStyle: {
            color: ['#fff', '#f5f5f5'],
          },
        },
        axisLine: {
          lineStyle: {
            color: '#ddd',
          },
        },
        splitLine: {
          lineStyle: {
            color: '#ddd',
          },
        },
      },
      series: [
        {
          type: 'radar',
          data: seriesData,
          emphasis: {
            lineStyle: {
              width: 3,
            },
          },
        },
      ],
    }
  }, [data, maxValues, indicators, shape, t])

  // Handle empty state
  if (!data || data.length === 0) {
    return (
      <Empty
        image={Empty.PRESENTED_IMAGE_SIMPLE}
        description={t('charts.noData', 'No data available for radar chart')}
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
      data-testid="radar-compare-chart"
    />
  )
}

export default RadarCompareChart
