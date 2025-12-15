/**
 * Disease Association Network Analysis Tab
 *
 * Displays disease-gene-lncRNA network analysis with:
 * - Statistics cards (diseases, lncRNAs, genes, connections)
 * - Network preview (simplified visualization)
 * - Node list table
 */

import { useState, useMemo } from 'react'
import { Card, Row, Col, Statistic, Table, Space, Button, Input, Tag, Empty } from 'antd'
import { DownloadOutlined, SearchOutlined } from '@ant-design/icons'
import { useTranslation } from 'react-i18next'
import ReactECharts from 'echarts-for-react'
import { useDiseaseData, useAnalysisSummary } from '@/hooks/useAnalysis'
import { LoadingState } from '@/components/LoadingState'
import { ErrorState } from '@/components/ErrorState'
import echarts from '@/utils/echarts'
import { getChartToolbox } from '@/utils/chart-export'
import type { DiseaseNetworkNode, DiseaseNetworkEdge } from '@/api/analysis'

export default function DiseaseTab() {
  const { t } = useTranslation('analysis')

  const [traitName, setTraitName] = useState<string>('')

  // Fetch summary and data
  const { data: summary } = useAnalysisSummary()
  const { data, isLoading, error, refetch } = useDiseaseData({
    trait_name: traitName || undefined,
    limit: 100,
  })

  // Network preview chart
  const networkPreviewOption: any = useMemo(() => {
    if (!data?.nodes || data.nodes.length === 0) return {}

    // Create nodes with categories
    const nodes = data.nodes.map((node: DiseaseNetworkNode) => ({
      id: node.id,
      name: node.name,
      category: node.type === 'disease' ? 0 : node.type === 'gene' ? 1 : 2,
      symbolSize: node.type === 'disease' ? 50 : node.type === 'gene' ? 30 : 35,
    }))

    // Create links
    const links = data.edges.map((edge: DiseaseNetworkEdge) => ({
      source: edge.source,
      target: edge.target,
      value: edge.weight,
      lineStyle: {
        color: edge.type === 'disease-gene' ? '#f5222d' : '#1890ff',
        width: Math.min(Math.max(1, edge.weight / 50), 5),
      },
    }))

    return {
      title: {
        text: t('disease.charts.networkPreview'),
        subtext: `${data.nodes.length} nodes, ${data.edges.length} edges`,
        left: 'center',
        textStyle: { fontSize: 16, fontWeight: 'bold' },
      },
      toolbox: getChartToolbox('disease-network', t('common.export')),
      tooltip: {
        trigger: 'item',
        formatter: (params: any) => {
          if (params.dataType === 'edge') {
            return `Weight: ${params.value?.toFixed(2) || '-'}`
          }
          return `${params.name} (${params.data.category === 0 ? 'Disease' : params.data.category === 1 ? 'Gene' : 'lncRNA'})`
        },
      },
      legend: {
        data: ['Disease', 'Gene', 'lncRNA'],
        bottom: 10,
      },
      series: [
        {
          type: 'graph',
          layout: 'force',
          data: nodes,
          links: links,
          categories: [
            { name: 'Disease', itemStyle: { color: '#f5222d' } },
            { name: 'Gene', itemStyle: { color: '#52c41a' } },
            { name: 'lncRNA', itemStyle: { color: '#1890ff' } },
          ],
          roam: true,
          label: {
            show: true,
            position: 'right',
            fontSize: 10,
          },
          force: {
            repulsion: 200,
            edgeLength: 100,
            gravity: 0.1,
          },
          emphasis: {
            focus: 'adjacency',
            lineStyle: {
              width: 4,
            },
          },
        },
      ],
    }
  }, [data, t])

  // Table columns for nodes
  const columns = [
    {
      title: 'ID',
      dataIndex: 'id',
      key: 'id',
      width: 150,
      ellipsis: true,
    },
    {
      title: 'Name',
      dataIndex: 'name',
      key: 'name',
      width: 200,
      ellipsis: true,
    },
    {
      title: 'Type',
      dataIndex: 'type',
      key: 'type',
      width: 120,
      render: (type: string) => {
        const colors: Record<string, string> = {
          disease: 'red',
          gene: 'green',
          lncrna: 'blue',
        }
        return <Tag color={colors[type] || 'default'}>{type}</Tag>
      },
      filters: [
        { text: 'Disease', value: 'disease' },
        { text: 'Gene', value: 'gene' },
        { text: 'lncRNA', value: 'lncrna' },
      ],
      onFilter: (value: any, record: DiseaseNetworkNode) => record.type === value,
    },
  ]

  if (isLoading) return <LoadingState message={t('common.loading')} />
  if (error) return <ErrorState error={error} onRetry={refetch} />

  const hasData = data?.nodes && data.nodes.length > 0

  return (
    <div>
      <p style={{ color: '#666', marginBottom: 24 }}>{t('disease.description')}</p>

      {/* Statistics Cards */}
      <Row gutter={16} style={{ marginBottom: 32 }}>
        <Col xs={24} sm={12} md={6}>
          <Card>
            <Statistic
              title={t('disease.stats.totalDiseases')}
              value={summary?.disease.total_diseases || 0}
              styles={{ content: { color: '#f5222d' } }}
            />
          </Card>
        </Col>
        <Col xs={24} sm={12} md={6}>
          <Card>
            <Statistic
              title={t('disease.stats.totalLncrnas')}
              value={summary?.disease.total_lncrnas || 0}
              styles={{ content: { color: '#1890ff' } }}
            />
          </Card>
        </Col>
        <Col xs={24} sm={12} md={6}>
          <Card>
            <Statistic
              title={t('disease.stats.totalGenes')}
              value={summary?.disease.total_genes || 0}
              styles={{ content: { color: '#52c41a' } }}
            />
          </Card>
        </Col>
        <Col xs={24} sm={12} md={6}>
          <Card>
            <Statistic
              title={t('disease.stats.avgConnections')}
              value={summary?.disease.avg_connections || 0}
              precision={1}
              styles={{ content: { color: '#faad14' } }}
            />
          </Card>
        </Col>
      </Row>

      {/* Filters */}
      <Card style={{ marginBottom: 16 }}>
        <Space wrap>
          <Input
            prefix={<SearchOutlined />}
            placeholder="Search disease/trait name"
            value={traitName}
            onChange={(e) => setTraitName(e.target.value)}
            style={{ width: 300 }}
            allowClear
          />
          <Button type="primary" onClick={() => refetch()}>
            {t('common.refresh')}
          </Button>
          <Button icon={<DownloadOutlined />}>{t('common.exportCsv')}</Button>
        </Space>
      </Card>

      {/* Network Preview */}
      {hasData ? (
        <Row gutter={16} style={{ marginBottom: 32 }}>
          <Col xs={24}>
            <Card title={t('disease.charts.networkPreview')}>
              <ReactECharts
                echarts={echarts}
                option={networkPreviewOption}
                style={{ height: 500 }}
                notMerge
                lazyUpdate
              />
            </Card>
          </Col>
        </Row>
      ) : (
        <Card style={{ marginBottom: 32 }}>
          <Empty description={t('common.noData')} />
        </Card>
      )}

      {/* Node Table */}
      <Card title={`Network Nodes (${data?.nodes?.length || 0})`}>
        <Table
          columns={columns}
          dataSource={data?.nodes || []}
          rowKey={(record) => record.id}
          pagination={{
            pageSize: 20,
            showSizeChanger: false,
            showTotal: (total) => t('common.total', { count: total }),
          }}
          scroll={{ x: 500 }}
          size="small"
        />
      </Card>
    </div>
  )
}
