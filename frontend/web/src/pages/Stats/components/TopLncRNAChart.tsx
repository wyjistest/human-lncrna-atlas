/**
 * Top lncRNA 条形图 + 链接列表
 * 展示调控关系最多的 lncRNA
 */

import { useMemo } from 'react'
import ReactECharts from 'echarts-for-react'
import { Table } from 'antd'
import { LinkOutlined } from '@ant-design/icons'
import { useTranslation } from 'react-i18next'
import echarts from '@/utils/echarts'
import type { ECOption } from '@/utils/echarts'
import type { DetailedStatsResponse } from '@/types'
import { getChartToolbox } from '@/utils/chart-export'
import { createSpeciesTranslator } from '@/utils/species'

// FANTOM CAT 链接前缀
// 格式: http://fantom.gsc.riken.jp/cat/v1/#/genes/CATG00000102578.1
const FANTOM_BASE_URL = 'https://fantom.gsc.riken.jp/cat/v1/#/genes/'

interface TopLncRNAChartProps {
  data: DetailedStatsResponse['top_lncrnas']
}

export function TopLncRNAChart({ data }: TopLncRNAChartProps) {
  const { t } = useTranslation('stats')
  const { t: tCommon } = useTranslation('common')

  const translateSpecies = createSpeciesTranslator(tCommon)

  // 反转数据（ECharts 条形图从下往上）
  const reversedData = [...data].reverse()

  const speciesLabel = t('table.species')
  const regulationCountLabel = t('table.regulationCount')

  const option: ECOption = useMemo(() => ({
    title: {
      text: t('charts.topLncRNA'),
      left: 'center',
      top: 10,
      textStyle: {
        fontSize: 16,
        fontWeight: 'bold'
      }
    },

    toolbox: getChartToolbox(t('charts.topLncRNA'), t('export.saveImage')),

    tooltip: {
      trigger: 'axis',
      axisPointer: {
        type: 'shadow'
      },
      formatter: (params: unknown) => {
        const p = (params as { name: string; value: number; data: { species: string } }[])[0]
        return `
          <strong>${p.name}</strong><br/>
          ${speciesLabel}: ${p.data.species}<br/>
          ${regulationCountLabel}: ${p.value.toLocaleString()}
        `
      }
    },

    grid: {
      left: '30%',
      right: '15%',
      bottom: '10%',
      top: '15%',
      containLabel: true
    },

    xAxis: {
      type: 'value',
      name: regulationCountLabel,
      nameLocation: 'middle',
      nameGap: 35
    },

    yAxis: {
      type: 'category',
      data: reversedData.map(l => l.gene_name),
      axisLabel: {
        fontSize: 10
      }
    },

    series: [
      {
        type: 'bar',
        data: reversedData.map(l => ({
          value: l.regulation_count,
          species: translateSpecies(l.species_name)
        })),
        itemStyle: {
          color: '#5470c6'
        },
        label: {
          show: true,
          position: 'right',
          formatter: '{c}'
        }
      }
    ]
  }), [reversedData, t, speciesLabel, regulationCountLabel, translateSpecies])

  // 表格列定义
  const columns = useMemo(() => [
    {
      title: t('table.rank'),
      key: 'rank',
      width: 60,
      render: (_: unknown, __: unknown, index: number) => index + 1
    },
    {
      title: t('table.lncrna'),
      dataIndex: 'gene_name',
      key: 'gene_name',
      render: (name: string, record: any) => {
        // 使用 gene_ensembl_id 并去掉物种后缀
        const ensemblId = record.gene_ensembl_id?.replace(/_(marmoset|macaque|chimpanzee|chimp)$/i, '') || name
        return (
          <a
            href={`${FANTOM_BASE_URL}${ensemblId}`}
            target="_blank"
            rel="noopener noreferrer"
            style={{ display: 'flex', alignItems: 'center', gap: 4 }}
          >
            {name} <LinkOutlined />
          </a>
        )
      }
    },
    {
      title: speciesLabel,
      dataIndex: 'species_name',
      key: 'species_name',
      width: 80,
      render: (name: string) => translateSpecies(name)
    },
    {
      title: t('table.count'),
      dataIndex: 'regulation_count',
      key: 'regulation_count',
      width: 80,
      render: (v: number) => v.toLocaleString()
    }
  ], [t, speciesLabel, translateSpecies])

  return (
    <div>
      <ReactECharts
        echarts={echarts}
        option={option}
        style={{ height: 350 }}
        notMerge={true}
        lazyUpdate={true}
      />
      <Table
        dataSource={data}
        columns={columns}
        rowKey="gene_id"
        size="small"
        pagination={false}
        style={{ marginTop: 16 }}
      />
    </div>
  )
}
