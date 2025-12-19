/**
 * BA 分布直方图
 * 展示结合亲和力的分布情况
 */

import { useMemo } from 'react'
import { escapeHtml } from '@/utils/escapeHtml'
import ReactECharts from 'echarts-for-react'
import { useTranslation } from 'react-i18next'
import echarts from '@/utils/echarts'
import type { ECOption } from '@/utils/echarts'
import type { BADistribution } from '@/types'
import { getChartToolbox } from '@/utils/chart-export'

interface BAChartProps {
  data: BADistribution[]
}

export function BAChart({ data }: BAChartProps) {
  const { t } = useTranslation('stats')

  // 生成 X 轴标签
  const labels = data.map(b => `${b.range_start.toFixed(0)}-${b.range_end.toFixed(0)}`)
  const counts = data.map(b => b.count)

  const regulationCountLabel = t('table.regulationCount')
  const baRangeLabel = t('table.baRange')

  const option: ECOption = useMemo(() => ({
    title: {
      text: t('charts.baDistribution'),
      left: 'center',
      top: 20,
      textStyle: {
        fontSize: 16,
        fontWeight: 'bold'
      }
    },

    toolbox: getChartToolbox(t('charts.baDistribution'), t('export.saveImage')),

    tooltip: {
      trigger: 'axis',
      axisPointer: {
        type: 'shadow'
      },
      formatter: (params: unknown) => {
        const p = (params as { name: string; value: number }[])[0]
        return `BA: ${escapeHtml(p.name)}<br/>${regulationCountLabel}: ${p.value.toLocaleString()}`
      }
    },

    xAxis: {
      type: 'category',
      data: labels,
      axisLabel: {
        rotate: 45,
        fontSize: 11
      },
      name: baRangeLabel,
      nameLocation: 'middle',
      nameGap: 35
    },

    yAxis: {
      type: 'value',
      name: regulationCountLabel,
      nameLocation: 'middle',
      nameGap: 50,
      axisLabel: {
        formatter: (value: number) => {
          if (value >= 1000000) return `${(value / 1000000).toFixed(1)}M`
          if (value >= 1000) return `${(value / 1000).toFixed(1)}K`
          return value.toString()
        }
      }
    },

    grid: {
      left: '15%',
      right: '10%',
      bottom: '20%',
      top: '15%'
    },

    series: [
      {
        type: 'bar',
        data: counts,
        itemStyle: {
          color: new echarts.graphic.LinearGradient(0, 0, 0, 1, [
            { offset: 0, color: '#83bff6' },
            { offset: 0.5, color: '#188df0' },
            { offset: 1, color: '#188df0' }
          ])
        }
      }
    ]
  }), [labels, counts, t, regulationCountLabel, baRangeLabel])

  return (
    <ReactECharts
      echarts={echarts}
      option={option}
      style={{ height: 400 }}
      notMerge={true}
      lazyUpdate={true}
    />
  )
}
