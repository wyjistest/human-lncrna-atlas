/**
 * Cross-Species Conservation Pattern Analysis Tab
 *
 * Displays conservation patterns with:
 * - Statistics cards (4-species, 3-species, 2-species)
 * - Conservation level pie chart
 * - Data table with pagination
 */

import { useCallback, useMemo } from 'react'
import { Card, Row, Col, Statistic, Table, Space, Button, Select } from 'antd'
import { DownloadOutlined } from '@ant-design/icons'
import { useTranslation } from 'react-i18next'
import ReactECharts from 'echarts-for-react'
import { useConservationData, useAnalysisSummary } from '@/hooks/useAnalysis'
import { LoadingState } from '@/components/LoadingState'
import { ErrorState } from '@/components/ErrorState'
import echarts from '@/utils/echarts'
import { getChartToolbox } from '@/utils/chart-export'
import { escapeHtml } from '@/utils/escapeHtml'
import type { ECOption } from '@/utils/echarts'
import type { ConservationRecord } from '@/api/analysis'
import { useSearchParams } from 'react-router-dom'

const DEFAULT_PAGE = 1
const MAX_PAGE = 1_000_000

function parseIntParam(value: string | null, min: number, max: number): number | undefined {
  if (!value) return undefined
  const parsed = Number.parseInt(value, 10)
  if (Number.isNaN(parsed)) return undefined
  if (parsed < min || parsed > max) return undefined
  return parsed
}

export default function ConservationTab() {
  const { t } = useTranslation('analysis')

  const [searchParams, setSearchParams] = useSearchParams()

  const minSpeciesCount = parseIntParam(searchParams.get('min_species_count'), 2, 4)
  const page = parseIntParam(searchParams.get('page'), 1, MAX_PAGE) ?? DEFAULT_PAGE
  const pageSize = 20

  const updateParams = useCallback((apply: (params: URLSearchParams) => void) => {
    setSearchParams((prev) => {
      const next = new URLSearchParams(prev)
      apply(next)
      return next
    }, { replace: true })
  }, [setSearchParams])

  // Fetch summary and data
  const { data: summary } = useAnalysisSummary()
  const { data, isLoading, error, refetch } = useConservationData({
    min_species_count: minSpeciesCount,
    limit: 500,
  })

  // Conservation level pie chart
  const conservationPieOption: ECOption = useMemo(() => {
    if (!summary?.conservation) return {}

    const conservationData = [
      { name: '4 Species', value: summary.conservation.four_species },
      { name: '3 Species', value: summary.conservation.three_species },
      { name: '2 Species', value: summary.conservation.two_species },
    ]

    return {
      title: {
        text: t('conservation.charts.speciesDistribution'),
        left: 'center',
        textStyle: { fontSize: 16, fontWeight: 'bold' },
      },
      toolbox: getChartToolbox('conservation-distribution', t('common.export')),
      tooltip: {
        trigger: 'item',
        formatter: (params: unknown) => {
          const p = params as { name: string; value: number; percent: number }
          return `${escapeHtml(p.name)}: ${p.value.toLocaleString()} (${p.percent.toFixed(1)}%)`
        },
      },
      legend: {
        orient: 'vertical',
        left: 'left',
        top: 'middle',
      },
      series: [
        {
          type: 'pie',
          radius: ['40%', '70%'],
          center: ['60%', '50%'],
          data: conservationData,
          emphasis: {
            itemStyle: {
              shadowBlur: 10,
              shadowOffsetX: 0,
              shadowColor: 'rgba(0, 0, 0, 0.5)',
            },
          },
          label: {
            show: true,
            formatter: '{b}\n{c} ({d}%)',
          },
          itemStyle: {
            color: (params: { dataIndex: number }) => {
              const colors = ['#1890ff', '#52c41a', '#faad14']
              return colors[params.dataIndex]
            },
          },
        },
      ],
    }
  }, [summary, t])

  // Table columns
  const columns = [
    {
      title: t('conservation.table.lncrna'),
      dataIndex: 'lncrna_names',
      key: 'lncrna_names',
      width: 200,
      ellipsis: true,
      render: (names: string[] | string) => {
        if (!names) return '-'
        const arr = Array.isArray(names) ? names : [names]
        return arr.join(', ')
      },
    },
    {
      title: t('conservation.table.speciesCount'),
      dataIndex: 'species_count',
      key: 'species_count',
      width: 120,
      sorter: (a: ConservationRecord, b: ConservationRecord) => a.species_count - b.species_count,
      render: (count: number) => (
        <span style={{ fontWeight: 'bold', color: count === 4 ? '#1890ff' : count === 3 ? '#52c41a' : '#faad14' }}>
          {count} / 4
        </span>
      ),
    },
    {
      title: t('conservation.table.regulationCount'),
      dataIndex: 'total_regulations',
      key: 'total_regulations',
      width: 140,
      sorter: (a: ConservationRecord, b: ConservationRecord) => a.total_regulations - b.total_regulations,
    },
    {
      title: 'Avg BA',
      dataIndex: 'avg_binding_affinity',
      key: 'avg_binding_affinity',
      width: 100,
      render: (val: number) => val?.toFixed(1) || '-',
    },
    {
      title: 'Targets',
      dataIndex: 'conserved_targets',
      key: 'conserved_targets',
      width: 150,
      ellipsis: true,
      render: (targets: string[] | string) => {
        if (!targets) return '-'
        const arr = Array.isArray(targets) ? targets : [targets]
        return arr.join(', ')
      },
    },
  ]

  if (isLoading) return <LoadingState message={t('common.loading')} />
  if (error) return <ErrorState error={error} onRetry={refetch} />

  return (
    <div>
      <p style={{ color: '#666', marginBottom: 24 }}>{t('conservation.description')}</p>

      {/* Statistics Cards */}
      <Row gutter={16} style={{ marginBottom: 32 }}>
        <Col xs={24} sm={12} md={6}>
          <Card>
            <Statistic
              title={t('conservation.stats.fourSpecies')}
              value={summary?.conservation.four_species || 0}
              styles={{ content: { color: '#1890ff' } }}
            />
          </Card>
        </Col>
        <Col xs={24} sm={12} md={6}>
          <Card>
            <Statistic
              title={t('conservation.stats.threeSpecies')}
              value={summary?.conservation.three_species || 0}
              styles={{ content: { color: '#52c41a' } }}
            />
          </Card>
        </Col>
        <Col xs={24} sm={12} md={6}>
          <Card>
            <Statistic
              title={t('conservation.stats.twoSpecies')}
              value={summary?.conservation.two_species || 0}
              styles={{ content: { color: '#faad14' } }}
            />
          </Card>
        </Col>
        <Col xs={24} sm={12} md={6}>
          <Card>
            <Statistic
              title={t('conservation.stats.totalConserved')}
              value={summary?.conservation.total_conserved || 0}
              styles={{ content: { color: '#f5222d' } }}
            />
          </Card>
        </Col>
      </Row>

      {/* Chart */}
      <Row gutter={16} style={{ marginBottom: 32 }}>
        <Col xs={24} lg={12}>
          <Card>
            <ReactECharts
              echarts={echarts}
              option={conservationPieOption}
              style={{ height: 400 }}
              notMerge
              lazyUpdate
            />
          </Card>
        </Col>
      </Row>

      {/* Filters and Table */}
      <Card title={t('conservation.title')} style={{ marginBottom: 16 }}>
        <Space wrap style={{ marginBottom: 16 }}>
          <span>Minimum Species Count:</span>
          <Select
            style={{ width: 150 }}
            value={minSpeciesCount}
            onChange={(value) => {
              updateParams((params) => {
                if (typeof value === 'number') params.set('min_species_count', String(value))
                else params.delete('min_species_count')
                params.delete('page')
              })
            }}
            allowClear
            placeholder="All"
          >
            <Select.Option value={2}>2+ Species</Select.Option>
            <Select.Option value={3}>3+ Species</Select.Option>
            <Select.Option value={4}>4 Species</Select.Option>
          </Select>
          <Button type="primary" onClick={() => refetch()}>
            {t('common.refresh')}
          </Button>
          <Button icon={<DownloadOutlined />}>{t('common.exportCsv')}</Button>
        </Space>

        <Table
          columns={columns}
          dataSource={data?.data || []}
          rowKey={(record) => record.core_id.toString()}
          pagination={{
            current: page,
            pageSize,
            total: data?.total || 0,
            onChange: (p) => {
              updateParams((params) => {
                if (p === DEFAULT_PAGE) params.delete('page')
                else params.set('page', String(p))
              })
            },
            showSizeChanger: false,
            showTotal: (total) => t('common.total', { count: total }),
          }}
          scroll={{ x: 700 }}
          size="small"
        />
      </Card>
    </div>
  )
}
