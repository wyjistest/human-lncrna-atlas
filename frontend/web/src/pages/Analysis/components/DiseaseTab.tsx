/**
 * Disease Association Network Analysis Tab
 *
 * Displays disease-gene-lncRNA network analysis with:
 * - Statistics cards (diseases, lncRNAs, genes, connections)
 * - Network preview (simplified visualization)
 * - Node list table
 */

import { useCallback, useEffect, useMemo, useState } from 'react'
import { Card, Row, Col, Statistic, Table, Space, Button, Input, Tag, Empty, message } from 'antd'
import { DownloadOutlined, SearchOutlined } from '@ant-design/icons'
import { useTranslation } from 'react-i18next'
import ReactECharts from 'echarts-for-react'
import { analysisApi } from '@/api/analysis'
import { useDiseaseData, useAnalysisSummary } from '@/hooks/useAnalysis'
import { LoadingState } from '@/components/LoadingState'
import { ErrorState } from '@/components/ErrorState'
import echarts from '@/utils/echarts'
import { getChartToolbox } from '@/utils/chart-export'
import { escapeHtml } from '@/utils/escapeHtml'
import type { ECOption } from '@/utils/echarts'
import type { DiseaseNetworkNode, DiseaseNetworkEdge } from '@/api/analysis'
import { useSearchParams } from 'react-router-dom'

export default function DiseaseTab() {
  const { t } = useTranslation('analysis')

  const [searchParams, setSearchParams] = useSearchParams()
  const traitNameFilter = searchParams.get('trait_name')?.trim() || undefined

  const updateParams = useCallback((apply: (params: URLSearchParams) => void) => {
    setSearchParams((prev) => {
      const next = new URLSearchParams(prev)
      apply(next)
      return next
    }, { replace: true })
  }, [setSearchParams])

  const [traitNameInput, setTraitNameInput] = useState<string>(() => traitNameFilter ?? '')
  const [isExporting, setIsExporting] = useState(false)
  useEffect(() => {
    setTraitNameInput(traitNameFilter ?? '')
  }, [traitNameFilter])

  // Fetch summary and data
  const { data: summary } = useAnalysisSummary()
  const { data, isLoading, error, refetch } = useDiseaseData({
    trait_name: traitNameFilter,
    limit: 100,
  })

  const applyTraitFilter = () => {
    const trimmed = traitNameInput.trim()
    const nextFilter = trimmed ? trimmed : undefined
    if (nextFilter === traitNameFilter) {
      refetch()
      return
    }
    updateParams((params) => {
      if (nextFilter) params.set('trait_name', nextFilter)
      else params.delete('trait_name')
    })
  }

  const handleExport = async () => {
    if (!data?.nodes?.length) return

    setIsExporting(true)
    try {
      await analysisApi.exportDiseaseNetworkJson({
        trait_name: traitNameFilter,
        limit: data.query_params?.limit || data.edges.length || 100,
      })
    } catch (error) {
      console.error('Disease network export failed:', error)
      message.error(t('common.error'))
    } finally {
      setIsExporting(false)
    }
  }

  // Network preview chart
  const networkPreviewOption: ECOption = useMemo(() => {
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
        formatter: (params: unknown) => {
          const p = params as { dataType?: string; name?: string; value?: number; data?: { category?: number } }
          if (p.dataType === 'edge') {
            return `Weight: ${p.value?.toFixed(2) || '-'}`
          }
          const categoryLabel = p.data?.category === 0 ? 'Disease' : p.data?.category === 1 ? 'Gene' : 'lncRNA'
          return `${escapeHtml(p.name || '')} (${categoryLabel})`
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
      onFilter: (value: boolean | React.Key, record: DiseaseNetworkNode) => record.type === value,
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
            value={traitNameInput}
            onChange={(e) => {
              const value = e.target.value
              setTraitNameInput(value)
              if (!value.trim()) {
                updateParams((params) => {
                  params.delete('trait_name')
                })
              }
            }}
            onPressEnter={applyTraitFilter}
            style={{ width: 300 }}
            allowClear
          />
          <Button type="primary" onClick={applyTraitFilter}>
            {t('common.refresh')}
          </Button>
          <Button
            icon={<DownloadOutlined />}
            loading={isExporting}
            disabled={!data?.nodes?.length}
            onClick={() => { void handleExport() }}
          >
            {t('common.exportJson', 'Export JSON')}
          </Button>
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
