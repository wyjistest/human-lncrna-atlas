/**
 * Chord Diagram Visualization Page
 *
 * Displays circular network diagram showing:
 * lncRNA ←→ Gene regulatory relationships
 *
 * Features:
 * - Interactive Chord/Circular Graph
 * - Species filter
 * - Binding affinity threshold slider
 * - Node limit control
 * - Statistics cards
 * - Detailed data table
 */

import { useState, useMemo, useRef } from 'react'
import {
  Card,
  Row,
  Col,
  Statistic,
  Table,
  Space,
  Select,
  Slider,
  Typography,
  Breadcrumb,
  Tooltip,
  Empty,
  Spin,
  Button,
} from 'antd'
import type { TableProps } from 'antd'
import {
  HomeOutlined,
  PartitionOutlined,
  InfoCircleOutlined,
  DownloadOutlined,
} from '@ant-design/icons'
import { Link } from 'react-router-dom'
import { useTranslation } from 'react-i18next'
import { useQuery } from '@tanstack/react-query'
import ReactECharts from 'echarts-for-react'
import type { EChartsOption } from 'echarts'
import type { ChordParams } from '@/types/echarts'

import { LoadingState } from '@/components/LoadingState'
import { ErrorState } from '@/components/ErrorState'
import { chordApi } from '@/api/chord'
import type { ChordNode, ChordLink } from '@/api/chord'
import { exportChartToPNG } from '@/utils/chart-export'

const { Title, Paragraph, Text } = Typography

/**
 * Species options for filter
 */
const SPECIES_OPTIONS = [
  { value: 1, label: 'Human' },
  { value: 2, label: 'Chimpanzee' },
  { value: 3, label: 'Macaque' },
  { value: 4, label: 'Marmoset' },
]

/**
 * Node category colors
 */
const CATEGORY_COLORS = {
  lncrna: '#5470c6', // Blue
  gene: '#91cc75', // Green
}

/**
 * Table row data structure
 */
interface ChordTableRow {
  key: string
  lncrna: string
  gene: string
  value: number
}

/**
 * Chord Diagram Visualization Page Component
 */
export default function ChordDiagram() {
  const { t } = useTranslation('visualization')
  const chartRef = useRef<ReactECharts>(null)

  // State
  const [speciesId, setSpeciesId] = useState<number | undefined>(1)
  const [minBA, setMinBA] = useState(0)
  const [limit, setLimit] = useState(50)

  // API Query
  const {
    data: chordData,
    isLoading,
    error,
  } = useQuery({
    queryKey: ['chord-data', speciesId, minBA, limit],
    queryFn: () =>
      chordApi.getChordData({
        species_id: speciesId,
        min_ba: minBA > 0 ? minBA : undefined,
        limit,
      }),
    staleTime: 5 * 60 * 1000, // 5 minutes
  })

  // Transform data for ECharts Circular Graph
  const chartOption = useMemo(() => {
    if (!chordData || !chordData.nodes || !chordData.links) {
      return { series: [] } as EChartsOption
    }

    // Transform nodes for graph
    const nodes = chordData.nodes.map((node: ChordNode) => ({
      name: node.id,
      symbolSize: Math.sqrt(node.value) * 3, // Scale by sqrt for better visual balance
      category: node.category === 'lncrna' ? 0 : 1,
      label: {
        show: true,
        formatter: node.name,
        fontSize: 10,
      },
      itemStyle: {
        color: node.category === 'lncrna' ? CATEGORY_COLORS.lncrna : CATEGORY_COLORS.gene,
      },
    }))

    // Create id->name mapping for tooltip
    const idToName = new Map(chordData.nodes.map((n: ChordNode) => [n.id, n.name]))

    // Transform links
    const links = chordData.links.map((link: ChordLink) => ({
      source: link.source,
      target: link.target,
      value: link.value,
      lineStyle: {
        width: Math.log(link.value + 1) * 0.5, // Log scale for width
        curveness: 0.3,
      },
    }))

    return {
      title: {
        text: t('chord.chartTitle', 'lncRNA ←→ Gene Regulatory Network'),
        left: 'center',
        textStyle: {
          fontSize: 16,
          fontWeight: 'bold',
        },
      },
      tooltip: {
        trigger: 'item',
        formatter: (rawParams: unknown) => {
          const params = rawParams as ChordParams
          if (params.dataType === 'edge') {
            const sourceId = String(params.data.source ?? '')
            const targetId = String(params.data.target ?? '')
            const sourceName = idToName.get(sourceId) || sourceId
            const targetName = idToName.get(targetId) || targetId
            const value = params.data.value ?? 0
            return `
              <strong>${sourceName} ←→ ${targetName}</strong><br/>
              ${t('chord.bindingAffinity', 'Binding Affinity')}: <strong>${value.toFixed(2)}</strong>
            `
          } else {
            const nodeName = idToName.get(params.name) || params.name
            const nodeData = chordData.nodes.find((n: ChordNode) => n.id === params.name)
            return `
              <strong>${nodeName}</strong><br/>
              ${t('chord.category', 'Category')}: ${nodeData?.category === 'lncrna' ? 'LncRNA' : 'Gene'}<br/>
              ${t('chord.connections', 'Connections')}: ${nodeData?.value.toFixed(0) || 0}
            `
          }
        },
      },
      legend: [
        {
          data: [
            { name: 'LncRNA', icon: 'circle', itemStyle: { color: CATEGORY_COLORS.lncrna } },
            { name: 'Gene', icon: 'circle', itemStyle: { color: CATEGORY_COLORS.gene } },
          ],
          top: 40,
          left: 'center',
        },
      ],
      series: [
        {
          type: 'graph',
          layout: 'circular',
          circular: {
            rotateLabel: true,
          },
          data: nodes,
          links: links,
          categories: [{ name: 'LncRNA' }, { name: 'Gene' }],
          roam: true,
          label: {
            show: true,
            position: 'right',
            formatter: '{b}',
          },
          lineStyle: {
            color: 'source',
            curveness: 0.3,
          },
          emphasis: {
            focus: 'adjacency',
            lineStyle: {
              width: 3,
            },
          },
        },
      ],
    }
  }, [chordData, t])

  // Transform data for table
  const tableData: ChordTableRow[] = useMemo(() => {
    if (!chordData || !chordData.links || !chordData.nodes) {
      return []
    }

    const nodeMap = new Map(chordData.nodes.map((n) => [n.id, n]))

    return chordData.links.map((link: ChordLink, index: number) => {
      const sourceNode = nodeMap.get(link.source)
      const targetNode = nodeMap.get(link.target)

      return {
        key: `${link.source}-${link.target}-${index}`,
        lncrna: sourceNode?.category === 'lncrna' ? sourceNode.name : targetNode?.name || '-',
        gene: targetNode?.category === 'gene' ? targetNode.name : sourceNode?.name || '-',
        value: link.value,
      }
    })
  }, [chordData])

  // Table columns
  const columns: TableProps<ChordTableRow>['columns'] = useMemo(
    () => [
      {
        title: t('chord.table.lncrna', 'LncRNA'),
        dataIndex: 'lncrna',
        key: 'lncrna',
        width: 200,
      },
      {
        title: t('chord.table.gene', 'Gene'),
        dataIndex: 'gene',
        key: 'gene',
        width: 200,
      },
      {
        title: t('chord.table.bindingAffinity', 'Binding Affinity'),
        dataIndex: 'value',
        key: 'value',
        width: 150,
        render: (val: number) => val.toFixed(2),
        sorter: (a, b) => a.value - b.value,
      },
    ],
    [t]
  )

  // Handle chart export
  const handleExportChart = () => {
    const chartInstance = chartRef.current?.getEchartsInstance()
    exportChartToPNG(chartInstance, 'chord-diagram', { pixelRatio: 2, backgroundColor: '#fff' })
  }

  // Loading state
  if (isLoading && !chordData) {
    return <LoadingState />
  }

  // Error state
  if (error) {
    return <ErrorState error={error} />
  }

  return (
    <div style={{ padding: 24 }} data-testid="chord-diagram-page">
      {/* Breadcrumb */}
      <Breadcrumb
        style={{ marginBottom: 16 }}
        items={[
          {
            title: (
              <Link to="/">
                <HomeOutlined />
              </Link>
            ),
          },
          {
            title: (
              <>
                <PartitionOutlined />
                <span style={{ marginLeft: 4 }}>
                  {t('chord.breadcrumb', 'Chord Diagram')}
                </span>
              </>
            ),
          },
        ]}
      />

      {/* Page Header */}
      <Space orientation="vertical" size="small" style={{ width: '100%', marginBottom: 24 }}>
        <Title level={2}>{t('chord.title', 'Chord Diagram')}</Title>
        <Paragraph type="secondary">
          {t(
            'chord.description',
            'Visualize lncRNA-Gene regulatory relationships as a circular network. Node size represents connection degree, edge width represents binding affinity.'
          )}
        </Paragraph>
      </Space>

      {/* Statistics Cards */}
      <Row gutter={[16, 16]} style={{ marginBottom: 24 }}>
        <Col xs={24} sm={12} md={6}>
          <Card>
            <Statistic
              title={
                <Space>
                  {t('chord.stats.totalNodes', 'Total Nodes')}
                  <Tooltip title={t('chord.stats.totalNodesHelp', 'lncRNA + Gene nodes')}>
                    <InfoCircleOutlined style={{ color: '#999' }} />
                  </Tooltip>
                </Space>
              }
              value={chordData?.statistics?.total_nodes || 0}
              loading={isLoading}
              data-testid="stat-total-nodes"
            />
          </Card>
        </Col>
        <Col xs={24} sm={12} md={6}>
          <Card>
            <Statistic
              title={t('chord.stats.lncrnaNodes', 'LncRNA Nodes')}
              value={chordData?.statistics?.lncrna_count || 0}
              styles={{ content: { color: CATEGORY_COLORS.lncrna } }}
              loading={isLoading}
              data-testid="stat-lncrna-nodes"
            />
          </Card>
        </Col>
        <Col xs={24} sm={12} md={6}>
          <Card>
            <Statistic
              title={t('chord.stats.geneNodes', 'Gene Nodes')}
              value={chordData?.statistics?.gene_count || 0}
              styles={{ content: { color: CATEGORY_COLORS.gene } }}
              loading={isLoading}
              data-testid="stat-gene-nodes"
            />
          </Card>
        </Col>
        <Col xs={24} sm={12} md={6}>
          <Card>
            <Statistic
              title={t('chord.stats.totalLinks', 'Total Connections')}
              value={chordData?.statistics?.total_links || 0}
              loading={isLoading}
              data-testid="stat-total-links"
            />
          </Card>
        </Col>
      </Row>

      {/* Filters */}
      <Card
        title={t('chord.filters.title', 'Filters')}
        size="small"
        style={{ marginBottom: 16 }}
        data-testid="chord-filters"
      >
        <Row gutter={[16, 16]} align="middle">
          <Col xs={24} sm={12} md={8}>
            <Space orientation="vertical" style={{ width: '100%' }} size={4}>
              <Text type="secondary" style={{ fontSize: 12 }}>
                {t('chord.filters.species', 'Species')}
              </Text>
              <Select
                style={{ width: '100%' }}
                value={speciesId}
                onChange={setSpeciesId}
                options={[
                  { value: undefined, label: t('chord.filters.allSpecies', 'All Species') },
                  ...SPECIES_OPTIONS,
                ]}
                data-testid="species-select"
              />
            </Space>
          </Col>
          <Col xs={24} sm={12} md={8}>
            <Space orientation="vertical" style={{ width: '100%' }} size={4}>
              <Text type="secondary" style={{ fontSize: 12 }}>
                {t('chord.filters.minBA', 'Min. Binding Affinity')}: {minBA}
              </Text>
              <Slider
                min={0}
                max={100}
                value={minBA}
                onChange={setMinBA}
                marks={{ 0: '0', 50: '50', 100: '100' }}
                data-testid="ba-slider"
              />
            </Space>
          </Col>
          <Col xs={24} sm={12} md={8}>
            <Space orientation="vertical" style={{ width: '100%' }} size={4}>
              <Text type="secondary" style={{ fontSize: 12 }}>
                {t('chord.filters.limit', 'Node Limit')}: {limit}
              </Text>
              <Slider
                min={20}
                max={200}
                step={10}
                value={limit}
                onChange={setLimit}
                marks={{ 20: '20', 100: '100', 200: '200' }}
                data-testid="limit-slider"
              />
            </Space>
          </Col>
        </Row>
      </Card>

      {/* Chord Chart */}
      <Card
        title={t('chord.chartTitle', 'lncRNA ←→ Gene Regulatory Network')}
        extra={
          <Button
            icon={<DownloadOutlined />}
            onClick={handleExportChart}
            data-testid="export-button"
          >
            {t('chord.export', 'Export PNG')}
          </Button>
        }
        style={{ marginBottom: 16 }}
        data-testid="chord-chart-card"
      >
        {isLoading ? (
          <div style={{ height: 600, display: 'flex', alignItems: 'center', justifyContent: 'center' }}>
            <Spin size="large" />
          </div>
        ) : !chordData || chordData.nodes.length === 0 ? (
          <Empty
            description={t('chord.noData', 'No data available. Try adjusting filters.')}
            style={{ padding: '60px 0' }}
          />
        ) : (
          <ReactECharts
            ref={chartRef}
            option={chartOption}
            style={{ height: 600 }}
            opts={{ renderer: 'canvas' }}
            data-testid="chord-chart"
          />
        )}
      </Card>

      {/* Data Table */}
      <Card title={t('chord.table.title', 'Connection Details')} data-testid="chord-table-card">
        <Table<ChordTableRow>
          columns={columns}
          dataSource={tableData}
          loading={isLoading}
          pagination={{
            pageSize: 20,
            showSizeChanger: true,
            showTotal: (total) => t('chord.table.total', `Total ${total} connections`, { count: total }),
          }}
          scroll={{ x: 600 }}
          size="middle"
          data-testid="chord-table"
        />
      </Card>
    </div>
  )
}
