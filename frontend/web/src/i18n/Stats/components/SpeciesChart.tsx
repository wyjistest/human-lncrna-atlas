/**
 * 物种分布饼图
 * 展示各物种的调控关系数量分布
 */

import { useMemo } from 'react'
import ReactECharts from 'echarts-for-react'
import { useTranslation } from 'react-i18next'
import echarts from '@/utils/echarts'
import type { ECOption } from '@/utils/echarts'
import type { DetailedStatsResponse } from '@/types'
import { getChartToolbox } from '@/utils/chart-export'
import { createSpeciesTranslator } from '@/utils/species'

interface SpeciesChartProps {
  data: DetailedStatsResponse['species_distribution']
}

export function SpeciesChart({ data }: SpeciesChartProps) {
  const { t, i18n } = useTranslation('stats')
  const { t: tCommon } = useTranslation('common')

  const translateSpecies = createSpeciesTranslator(tCommon)

  const option: ECOption = useMemo(() => ({
    title: {
      text: t('charts.speciesDistribution'),
      left: 'center',
      top: 20,
      textStyle: {
        fontSize: 16,
        fontWeight: 'bold'
      }
    },

    toolbox: getChartToolbox(t('charts.speciesDistribution'), t('export.saveImage')),

    tooltip: {
      trigger: 'item',
      formatter: '{b}: {c} ({d}%)'
    },

    legend: {
      orient: 'vertical',
      left: 'left',
      top: 'middle'
    },

    series: [
      {
        type: 'pie',
        radius: ['40%', '70%'],
        center: ['60%', '50%'],
        data: data.map(s => ({
          name: translateSpecies(s.species_name),
          value: s.count
        })),
        emphasis: {
          itemStyle: {
            shadowBlur: 10,
            shadowOffsetX: 0,
            shadowColor: 'rgba(0, 0, 0, 0.5)'
          }
        },
        label: {
          show: true,
          formatter: '{b}\n{c} ({d}%)'
        }
      }
    ]
  }), [data, t, i18n.language, translateSpecies])

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
