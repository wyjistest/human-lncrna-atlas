/**
 * Epigenetic Mark Association Analysis Tab
 *
 * Displays ChIP-seq overlap analysis with:
 * - Statistics cards (total overlaps, by mark type)
 * - Mark distribution bar chart
 * - Data table with pagination
 */

import { useState, useMemo } from 'react'
import { Card, Row, Col, Statistic, Table, Space, Button, Select, Tag } from 'antd'
import { DownloadOutlined } from '@ant-design/icons'
import { useTranslation } from 'react-i18next'
import ReactECharts from 'echarts-for-react'
import { useEpigeneticData, useAnalysisSummary } from '@/hooks/useAnalysis'
import { LoadingState } from '@/components/LoadingState'
import { ErrorState } from '@/components/ErrorState'
import echarts from '@/utils/echarts'
import { getChartToolbox } from '@/utils/chart-export'
import type { ECOption } from '@/utils/echarts'
import type { ChIPSeqOverlapRecord } from '@/api/analysis'

const HISTONE_MARKS = [
  { value: 'H3K4me1', label: 'H3K4me1', color: '#1890ff', type: 'active' },
  { value: 'H3K4me3', label: 'H3K4me3', color: '#52c41a', type: 'active' },
  { value: 'H3K27ac', label: 'H3K27ac', color: '#faad14', type: 'active' },
  { value: 'H3K36me3', label: 'H3K36me3', color: '#13c2c2', type: 'active' },
  { value: 'H3K9me3', label: 'H3K9me3', color: '#f5222d', type: 'repressive' },
  { value: 'H3K27me3', label: 'H3K27me3', color: '#722ed1', type: 'repressive' },
]

export default function EpigeneticTab() {
  const { t } = useTranslation('analysis')

  const [selectedMarks, setSelectedMarks] = useState<string[]>([])
  const [page, setPage] = useState(1)
  const pageSize = 20

  // Fetch summary and data
  const { data: summary } = useAnalysisSummary()
  const { data, isLoading, error, refetch } = useEpigeneticData({
    mark_names: selectedMarks.length > 0 ? selectedMarks : undefined,
    limit: 500,
    offset: (page - 1) * pageSize,
  })

  // Mark distribution chart
  const markDistributionOption: ECOption = useMemo(() => {
    if (!data?.data) return {}

    // Count by mark
    const markCounts = data.data.reduce((acc, record) => {
      acc[record.mark_name] = (acc[record.mark_name] || 0) + 1
      return acc
    }, {} as Record<string, number>)

    const marks = Object.keys(markCounts).sort()
    const counts = marks.map((mark) => markCounts[mark])

    return {
      title: {
        text: t('epigenetic.charts.markDistribution'),
        left: 'center',
        textStyle: { fontSize: 16, fontWeight: 'bold' },
      },
      toolbox: getChartToolbox('mark-distribution', t('common.export')),
      tooltip: {
        trigger: 'axis',
        axisPointer: { type: 'shadow' },
      },
      xAxis: {
        type: 'category',
        data: marks,
        axisLabel: { rotate: 45, fontSize: 10 },
      },
      yAxis: {
        type: 'value',
        name: 'Overlap Count',
      },
      series: [
        {
          type: 'bar',
          data: counts,
          itemStyle: {
            color: (params: { dataIndex: number }) => {
              const mark = marks[params.dataIndex]
              const markConfig = HISTONE_MARKS.find((m) => m.value === mark)
              return markConfig?.color || '#1890ff'
            },
          },
        },
      ],
      grid: { bottom: 80, left: 60, right: 40 },
    }
  }, [data, t])

  // Table columns
  const columns = [
    {
      title: t('epigenetic.table.lncrna'),
      dataIndex: 'lncrna_name',
      key: 'lncrna_name',
      width: 150,
    },
    {
      title: 'Target',
      dataIndex: 'target_name',
      key: 'target_name',
      width: 120,
    },
    {
      title: t('epigenetic.table.mark'),
      dataIndex: 'mark_name',
      key: 'mark_name',
      width: 120,
      render: (mark: string) => {
        const markConfig = HISTONE_MARKS.find((m) => m.value === mark)
        return (
          <Tag color={markConfig?.color || 'default'}>
            {mark}
          </Tag>
        )
      },
      filters: HISTONE_MARKS.map((mark) => ({ text: mark.label, value: mark.value })),
      onFilter: (value: boolean | React.Key, record: ChIPSeqOverlapRecord) => record.mark_name === value,
    },
    {
      title: t('epigenetic.table.cellType'),
      dataIndex: 'cell_type',
      key: 'cell_type',
      width: 120,
      ellipsis: true,
    },
    {
      title: t('epigenetic.table.peakScore'),
      dataIndex: 'peak_score',
      key: 'peak_score',
      width: 100,
      render: (score: number) => score?.toFixed(1) || '-',
      sorter: (a: ChIPSeqOverlapRecord, b: ChIPSeqOverlapRecord) =>
        (a.peak_score || 0) - (b.peak_score || 0),
    },
    {
      title: t('epigenetic.table.ba'),
      dataIndex: 'binding_affinity',
      key: 'binding_affinity',
      width: 100,
      render: (ba: number) => ba?.toFixed(2) || '-',
      sorter: (a: ChIPSeqOverlapRecord, b: ChIPSeqOverlapRecord) =>
        a.binding_affinity - b.binding_affinity,
    },
  ]

  if (isLoading) return <LoadingState message={t('common.loading')} />
  if (error) return <ErrorState error={error} onRetry={refetch} />

  return (
    <div>
      <p style={{ color: '#666', marginBottom: 24 }}>{t('epigenetic.description')}</p>

      {/* Statistics Cards */}
      <Row gutter={16} style={{ marginBottom: 32 }}>
        <Col xs={24} sm={12} md={6}>
          <Card>
            <Statistic
              title={t('epigenetic.stats.totalOverlaps')}
              value={summary?.epigenetic.total_overlaps || 0}
              styles={{ content: { color: '#1890ff' } }}
            />
          </Card>
        </Col>
        <Col xs={24} sm={12} md={6}>
          <Card>
            <Statistic
              title={t('epigenetic.stats.bivalentDomains')}
              value={summary?.epigenetic.bivalent_domains || 0}
              styles={{ content: { color: '#722ed1' } }}
            />
          </Card>
        </Col>
        <Col xs={24} sm={12} md={6}>
          <Card>
            <Statistic
              title={t('epigenetic.stats.activeMarks')}
              value={summary?.epigenetic.active_marks || 0}
              styles={{ content: { color: '#52c41a' } }}
            />
          </Card>
        </Col>
        <Col xs={24} sm={12} md={6}>
          <Card>
            <Statistic
              title={t('epigenetic.stats.repressiveMarks')}
              value={summary?.epigenetic.repressive_marks || 0}
              styles={{ content: { color: '#f5222d' } }}
            />
          </Card>
        </Col>
      </Row>

      {/* Chart */}
      <Row gutter={16} style={{ marginBottom: 32 }}>
        <Col xs={24} lg={16}>
          <Card>
            <ReactECharts
              echarts={echarts}
              option={markDistributionOption}
              style={{ height: 400 }}
              notMerge
              lazyUpdate
            />
          </Card>
        </Col>
        <Col xs={24} lg={8}>
          <Card title="Histone Marks">
            <Space orientation="vertical" style={{ width: '100%' }}>
              {HISTONE_MARKS.map((mark) => (
                <div key={mark.value} style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
                  <Tag color={mark.color}>{mark.label}</Tag>
                  <span style={{ fontSize: 12, color: '#666' }}>
                    {t(`epigenetic.marks.${mark.value}`)}
                  </span>
                </div>
              ))}
            </Space>
          </Card>
        </Col>
      </Row>

      {/* Filters and Table */}
      <Card title={t('epigenetic.title')} style={{ marginBottom: 16 }}>
        <Space wrap style={{ marginBottom: 16 }}>
          <span>Filter by Mark:</span>
          <Select
            mode="multiple"
            style={{ minWidth: 250 }}
            value={selectedMarks}
            onChange={setSelectedMarks}
            placeholder="Select marks"
            maxTagCount={2}
          >
            {HISTONE_MARKS.map((mark) => (
              <Select.Option key={mark.value} value={mark.value}>
                <Tag color={mark.color} style={{ marginRight: 4 }}>
                  {mark.label}
                </Tag>
                {mark.type === 'active' ? 'Active' : 'Repressive'}
              </Select.Option>
            ))}
          </Select>
          <Button type="primary" onClick={() => refetch()}>
            {t('common.refresh')}
          </Button>
          <Button icon={<DownloadOutlined />}>{t('common.exportCsv')}</Button>
        </Space>

        <Table
          columns={columns}
          dataSource={data?.data || []}
          rowKey={(record, index) => `${record.regulation_id}-${record.mark_name}-${index}`}
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
