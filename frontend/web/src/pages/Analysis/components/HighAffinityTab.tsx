/**
 * High Affinity Regulatory Network Analysis Tab
 *
 * Displays high binding affinity regulatory relationships with:
 * - Statistics cards
 * - BA distribution histogram
 * - Top 20 lncRNAs bar chart
 * - Data table with pagination
 */

import { useState, useMemo } from 'react'
import { Card, Row, Col, Statistic, Table, Space, Button, InputNumber, Select } from 'antd'
import { DownloadOutlined } from '@ant-design/icons'
import { useTranslation } from 'react-i18next'
import ReactECharts from 'echarts-for-react'
import { useHighAffinityData, useAnalysisSummary } from '@/hooks/useAnalysis'
import { LoadingState } from '@/components/LoadingState'
import { ErrorState } from '@/components/ErrorState'
import echarts from '@/utils/echarts'
import { getChartToolbox } from '@/utils/chart-export'
import { escapeHtml } from '@/utils/escapeHtml'
import type { ECOption } from '@/utils/echarts'
import type { HighAffinityRecord } from '@/api/analysis'
import type { TooltipFormatterParams } from '@/types/echarts'

export default function HighAffinityTab() {
  const { t } = useTranslation('analysis')
  const { t: tCommon } = useTranslation('common')

  const [minBa, setMinBa] = useState(100)
  const [speciesId, setSpeciesId] = useState<number | undefined>(undefined)
  const [page, setPage] = useState(1)
  const pageSize = 20

  // Fetch summary and data
  const { data: summary } = useAnalysisSummary()
  const { data, isLoading, error, refetch } = useHighAffinityData({
    min_ba: minBa,
    species_id: speciesId,
    limit: 1000, // Get enough for charts
    offset: (page - 1) * pageSize,
  })

  // BA distribution chart
  const baDistributionOption: ECOption = useMemo(() => {
    if (!data?.data) return {}

    // Create 20 bins for BA distribution
    const bins: number[] = new Array(20).fill(0)
    const binSize = 10 // Each bin covers 10 BA units
    const minValue = 100

    data.data.forEach((record) => {
      const binIndex = Math.min(Math.floor((record.binding_affinity - minValue) / binSize), 19)
      if (binIndex >= 0) bins[binIndex]++
    })

    return {
      title: {
        text: t('highAffinity.charts.baDistribution'),
        left: 'center',
        textStyle: { fontSize: 16, fontWeight: 'bold' },
      },
      toolbox: getChartToolbox('ba-distribution', t('common.export')),
      tooltip: {
        trigger: 'axis',
        formatter: (params: unknown) => {
          const paramsArr = params as TooltipFormatterParams[]
          const p = paramsArr[0]
          const value = p.value as number
          const baRange = `${minValue + p.dataIndex * binSize}-${minValue + (p.dataIndex + 1) * binSize}`
          return `BA Range: ${escapeHtml(baRange)}<br/>Count: ${value}`
        },
      },
      xAxis: {
        type: 'category',
        name: 'Binding Affinity',
        data: Array.from({ length: 20 }, (_, i) => `${minValue + i * binSize}`),
        axisLabel: { rotate: 45 },
      },
      yAxis: {
        type: 'value',
        name: 'Count',
      },
      series: [
        {
          type: 'bar',
          data: bins,
          itemStyle: { color: '#1890ff' },
        },
      ],
      grid: { bottom: 80, left: 60, right: 40 },
    }
  }, [data, t])

  // Top 20 lncRNAs chart
  const topLncrnasOption: ECOption = useMemo(() => {
    if (!data?.data) return {}

    // Count targets per lncRNA
    const lncrnaCounts = data.data.reduce((acc, record) => {
      const name = record.lncrna_name || 'Unknown'
      acc[name] = (acc[name] || 0) + 1
      return acc
    }, {} as Record<string, number>)

    // Get top 20
    const topLncrnas = Object.entries(lncrnaCounts)
      .sort(([, a], [, b]) => b - a)
      .slice(0, 20)

    return {
      title: {
        text: t('highAffinity.charts.topLncrnas'),
        left: 'center',
        textStyle: { fontSize: 16, fontWeight: 'bold' },
      },
      toolbox: getChartToolbox('top-lncrnas', t('common.export')),
      tooltip: {
        trigger: 'axis',
        axisPointer: { type: 'shadow' },
      },
      xAxis: {
        type: 'value',
        name: 'Target Count',
      },
      yAxis: {
        type: 'category',
        data: topLncrnas.map(([name]) => name).reverse(),
        axisLabel: { fontSize: 10 },
      },
      series: [
        {
          type: 'bar',
          data: topLncrnas.map(([, count]) => count).reverse(),
          itemStyle: { color: '#52c41a' },
        },
      ],
      grid: { left: 120, right: 40 },
    }
  }, [data, t])

  // Table columns
  const columns = [
    {
      title: t('highAffinity.table.lncrna'),
      dataIndex: 'lncrna_name',
      key: 'lncrna_name',
      width: 150,
    },
    {
      title: t('highAffinity.table.target'),
      dataIndex: 'target_name',
      key: 'target_name',
      width: 150,
    },
    {
      title: t('highAffinity.table.ba'),
      dataIndex: 'binding_affinity',
      key: 'binding_affinity',
      width: 120,
      render: (ba: number) => ba?.toFixed(2) || '-',
      sorter: (a: HighAffinityRecord, b: HighAffinityRecord) => a.binding_affinity - b.binding_affinity,
    },
    {
      title: t('highAffinity.table.species'),
      dataIndex: 'species_name',
      key: 'species_name',
      width: 120,
    },
    {
      title: t('highAffinity.table.chromosome'),
      dataIndex: 'chr',
      key: 'chr',
      width: 100,
    },
  ]

  if (isLoading) return <LoadingState message={t('common.loading')} />
  if (error) return <ErrorState error={error} onRetry={refetch} />

  return (
    <div>
      <p style={{ color: '#666', marginBottom: 24 }}>{t('highAffinity.description')}</p>

      {/* Statistics Cards */}
      <Row gutter={16} style={{ marginBottom: 32 }}>
        <Col xs={24} sm={12} md={6}>
          <Card>
            <Statistic
              title={t('highAffinity.stats.totalRegulations')}
              value={summary?.high_affinity.total_regulations || 0}
              styles={{ content: { color: '#1890ff' } }}
            />
          </Card>
        </Col>
        <Col xs={24} sm={12} md={6}>
          <Card>
            <Statistic
              title={t('highAffinity.stats.uniqueLncrnas')}
              value={summary?.high_affinity.unique_lncrnas || 0}
              styles={{ content: { color: '#52c41a' } }}
            />
          </Card>
        </Col>
        <Col xs={24} sm={12} md={6}>
          <Card>
            <Statistic
              title={t('highAffinity.stats.avgBa')}
              value={summary?.high_affinity.avg_ba || 0}
              precision={2}
              styles={{ content: { color: '#faad14' } }}
            />
          </Card>
        </Col>
        <Col xs={24} sm={12} md={6}>
          <Card>
            <Statistic
              title={t('highAffinity.stats.maxBa')}
              value={summary?.high_affinity.max_ba || 0}
              precision={2}
              styles={{ content: { color: '#f5222d' } }}
            />
          </Card>
        </Col>
      </Row>

      {/* Charts */}
      <Row gutter={16} style={{ marginBottom: 32 }}>
        <Col xs={24} lg={12}>
          <Card>
            <ReactECharts
              echarts={echarts}
              option={baDistributionOption}
              style={{ height: 400 }}
              notMerge
              lazyUpdate
            />
          </Card>
        </Col>
        <Col xs={24} lg={12}>
          <Card>
            <ReactECharts
              echarts={echarts}
              option={topLncrnasOption}
              style={{ height: 400 }}
              notMerge
              lazyUpdate
            />
          </Card>
        </Col>
      </Row>

      {/* Filters */}
      <Card title={t('highAffinity.title')} style={{ marginBottom: 16 }}>
        <Space wrap style={{ marginBottom: 16 }}>
          <span>Minimum BA:</span>
          <InputNumber
            min={50}
            max={300}
            value={minBa}
            onChange={(val) => val && setMinBa(val)}
            style={{ width: 120 }}
          />
          <span>Species:</span>
          <Select
            style={{ width: 150 }}
            value={speciesId}
            onChange={setSpeciesId}
            allowClear
            placeholder="All species"
          >
            <Select.Option value={1}>{tCommon('species.human')}</Select.Option>
            <Select.Option value={2}>{tCommon('species.chimp')}</Select.Option>
            <Select.Option value={3}>{tCommon('species.macaque')}</Select.Option>
            <Select.Option value={4}>{tCommon('species.marmoset')}</Select.Option>
          </Select>
          <Button type="primary" onClick={() => refetch()}>
            {t('common.refresh')}
          </Button>
          <Button icon={<DownloadOutlined />}>{t('common.exportCsv')}</Button>
        </Space>

        <Table
          columns={columns}
          dataSource={data?.data || []}
          rowKey={(record) => `${record.lncrna_gene_id}-${record.target_gene_id}-${record.species_id}-${record.start_in_genome}-${record.end_in_genome}`}
          pagination={{
            current: page,
            pageSize,
            total: data?.total || 0,
            onChange: setPage,
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
