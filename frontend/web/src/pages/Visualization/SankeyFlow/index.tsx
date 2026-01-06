/**
 * Sankey Flow Visualization Page
 *
 * Displays three-layer flow diagram showing:
 * lncRNA → Gene → Disease regulatory relationships
 *
 * Features:
 * - Interactive Sankey diagram
 * - Species filter
 * - Binding affinity threshold slider
 * - Disease name search
 * - Statistics cards
 * - Detailed data table
 */

import { useEffect, useMemo, useState } from 'react'
import { escapeHtml } from '@/utils/escapeHtml'
import {
  Card,
  Row,
  Col,
  Statistic,
  Table,
  Space,
  Input,
  Select,
  Slider,
  Typography,
  Breadcrumb,
  Tooltip,
  Empty,
  Spin,
} from 'antd'
import type { TableProps } from 'antd'
import {
  HomeOutlined,
  SearchOutlined,
  PartitionOutlined,
  InfoCircleOutlined,
} from '@ant-design/icons'
import { Link } from 'react-router-dom'
import { useTranslation } from 'react-i18next'
import { useQuery } from '@tanstack/react-query'
import ReactECharts from 'echarts-for-react'
import type { SankeyParams } from '@/types/echarts'
import echarts from '@/utils/echarts'
import type { ECOption } from '@/utils/echarts'

import { ErrorState } from '@/components/ErrorState'
import { visualizationApi } from '@/api/visualization'
import type { SankeyNode, SankeyLink } from '@/api/visualization'

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
 * Layer colors for Sankey nodes
 */
const LAYER_COLORS = {
  0: '#5470c6', // lncRNA - blue
  1: '#91cc75', // Gene - green
  2: '#ee6666', // Disease - red
}

/**
 * Table row data structure
 */
interface SankeyTableRow {
  key: string
  lncrna: string
  gene: string
  disease: string
  value: number
  flowCount: number
}

/**
 * Sankey Flow Visualization Page Component
 */
export default function SankeyFlow() {
  const { t } = useTranslation('visualization')

  // State
  const [speciesId, setSpeciesId] = useState<number>(1)
  const [minBA, setMinBA] = useState(100)
  const [traitInput, setTraitInput] = useState('')
  const [traitSearch, setTraitSearch] = useState('')
  const [limit, setLimit] = useState(100)

  // Debounce trait search to avoid firing a request on every keystroke
  useEffect(() => {
    const timer = setTimeout(() => {
      setTraitSearch(traitInput.trim())
    }, 500)
    return () => clearTimeout(timer)
  }, [traitInput])

  // API Query
  const {
    data: sankeyData,
    isLoading,
    error,
  } = useQuery({
    queryKey: ['sankey-data', speciesId, minBA, traitSearch, limit],
    queryFn: ({ signal }) =>
      visualizationApi.getSankeyData(
        {
          species_id: speciesId,
          min_ba: minBA,
          trait_name: traitSearch || undefined,
          limit,
        },
        signal
      ),
    staleTime: 5 * 60 * 1000, // 5 minutes
    meta: { skipGlobalErrorHandler: true },
  })

  // Transform data for ECharts Sankey
  const chartOption: ECOption = useMemo(() => {
    if (!sankeyData || !sankeyData.nodes || !sankeyData.links) {
      return { series: [] }
    }

    // Transform nodes to add colors based on layer
    // Use id as the unique key, name for display label
    const nodes = sankeyData.nodes.map((node: SankeyNode) => ({
      name: node.id, // ECharts uses name as unique ID
      label: {
        formatter: node.name, // Display the actual name
      },
      itemStyle: {
        color: LAYER_COLORS[node.layer as keyof typeof LAYER_COLORS] || '#999',
      },
    }))

    // Create id->name mapping for tooltip
    const idToName = new Map(sankeyData.nodes.map((n: SankeyNode) => [n.id, n.name]))

    // Transform links
    const links = sankeyData.links.map((link: SankeyLink) => ({
      source: link.source,
      target: link.target,
      value: link.value,
    }))

    return {
      title: {
        text: t('sankey.chartTitle', 'lncRNA → Gene → Disease Flow'),
        left: 'center',
        textStyle: {
          fontSize: 16,
          fontWeight: 'bold',
        },
      },
      tooltip: {
        trigger: 'item',
        triggerOn: 'mousemove',
        formatter: (rawParams: unknown) => {
          const params = rawParams as SankeyParams
          if (params.dataType === 'edge') {
            const sourceId = String(params.data.source ?? '')
            const targetId = String(params.data.target ?? '')
            const sourceName = idToName.get(sourceId) || sourceId
            const targetName = idToName.get(targetId) || targetId
            const value = params.data.value ?? 0
            return `
              <strong>${escapeHtml(sourceName)} → ${escapeHtml(targetName)}</strong><br/>
              ${t('sankey.flowValue', 'Flow Value')}: <strong>${value.toFixed(2)}</strong>
            `
          } else {
            const nodeName = idToName.get(params.name) || params.name
            return `<strong>${escapeHtml(nodeName)}</strong>`
          }
        },
      },
      series: [
        {
          type: 'sankey',
          layout: 'none',
          emphasis: {
            focus: 'adjacency',
          },
          data: nodes,
          links: links,
          levels: [
            {
              depth: 0,
              itemStyle: {
                color: LAYER_COLORS[0],
              },
              lineStyle: {
                color: 'source',
                opacity: 0.6,
              },
            },
            {
              depth: 1,
              itemStyle: {
                color: LAYER_COLORS[1],
              },
              lineStyle: {
                color: 'source',
                opacity: 0.6,
              },
            },
            {
              depth: 2,
              itemStyle: {
                color: LAYER_COLORS[2],
              },
              lineStyle: {
                color: 'source',
                opacity: 0.6,
              },
            },
          ],
          lineStyle: {
            color: 'gradient',
            curveness: 0.5,
          },
          label: {
            fontSize: 10,
          },
        },
      ],
    }
  }, [sankeyData, t])

  // Transform data for table
  const tableData: SankeyTableRow[] = useMemo(() => {
    if (!sankeyData || !sankeyData.links || !sankeyData.nodes) {
      return []
    }

    // Create node lookup map
    const nodeMap = new Map(sankeyData.nodes.map(n => [n.id, n]))

    // Group links by disease (layer 2 nodes)
    const rows: SankeyTableRow[] = []

    sankeyData.links.forEach((link: SankeyLink, index: number) => {
      const sourceNode = nodeMap.get(link.source)
      const targetNode = nodeMap.get(link.target)

      if (sourceNode && targetNode) {
        // Find the disease node (layer 2)
        // This is simplified - in reality, you might need to trace the full path
        rows.push({
          key: `${link.source}-${link.target}-${index}`,
          lncrna: sourceNode.layer === 0 ? sourceNode.name : '-',
          gene: sourceNode.layer === 1 ? sourceNode.name : targetNode.layer === 1 ? targetNode.name : '-',
          disease: targetNode.layer === 2 ? targetNode.name : '-',
          value: link.value,
          flowCount: link.flow_count,
        })
      }
    })

    return rows
  }, [sankeyData])

  // Table columns
  const columns: TableProps<SankeyTableRow>['columns'] = useMemo(
    () => [
      {
        title: t('sankey.table.lncrna', 'LncRNA'),
        dataIndex: 'lncrna',
        key: 'lncrna',
        width: 150,
      },
      {
        title: t('sankey.table.gene', 'Gene'),
        dataIndex: 'gene',
        key: 'gene',
        width: 150,
      },
      {
        title: t('sankey.table.disease', 'Disease'),
        dataIndex: 'disease',
        key: 'disease',
        width: 200,
      },
      {
        title: t('sankey.table.flowValue', 'Flow Value'),
        dataIndex: 'value',
        key: 'value',
        width: 120,
        render: (val: number) => val.toFixed(2),
        sorter: (a, b) => a.value - b.value,
      },
      {
        title: t('sankey.table.connections', 'Connections'),
        dataIndex: 'flowCount',
        key: 'flowCount',
        width: 120,
        sorter: (a, b) => a.flowCount - b.flowCount,
      },
    ],
    [t]
  )

  // Handle search with debounce
  const handleSearch = (value: string) => {
    setTraitInput(value)
  }

  // Error state
  if (error) {
    return <ErrorState error={error} />
  }

  return (
    <div style={{ padding: 24 }} data-testid="sankey-flow-page">
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
                  {t('sankey.breadcrumb', 'Sankey Flow')}
                </span>
              </>
            ),
          },
        ]}
      />

      {/* Page Header */}
      <Space orientation="vertical" size="small" style={{ width: '100%', marginBottom: 24 }}>
        <Title level={1}>{t('sankey.title', 'Sankey Flow Diagram')}</Title>
        <Paragraph type="secondary">
          {t(
            'sankey.description',
            'Visualize three-layer regulatory relationships: lncRNA → Gene → Disease. Explore how lncRNAs regulate genes associated with diseases.'
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
                  {t('sankey.stats.totalNodes', 'Total Nodes')}
                  <Tooltip title={t('sankey.stats.totalNodesHelp', 'lncRNA + Gene + Disease nodes')}>
                    <InfoCircleOutlined style={{ color: '#999' }} />
                  </Tooltip>
                </Space>
              }
              value={sankeyData?.statistics?.total_nodes || 0}
              loading={isLoading}
              data-testid="stat-total-nodes"
            />
          </Card>
        </Col>
        <Col xs={24} sm={12} md={6}>
          <Card>
            <Statistic
              title={t('sankey.stats.lncrnaNodes', 'LncRNA Nodes')}
              value={sankeyData?.statistics?.lncrna_count || 0}
              styles={{ content: { color: LAYER_COLORS[0] } }}
              loading={isLoading}
              data-testid="stat-lncrna-nodes"
            />
          </Card>
        </Col>
        <Col xs={24} sm={12} md={6}>
          <Card>
            <Statistic
              title={t('sankey.stats.geneNodes', 'Gene Nodes')}
              value={sankeyData?.statistics?.gene_count || 0}
              styles={{ content: { color: LAYER_COLORS[1] } }}
              loading={isLoading}
              data-testid="stat-gene-nodes"
            />
          </Card>
        </Col>
        <Col xs={24} sm={12} md={6}>
          <Card>
            <Statistic
              title={t('sankey.stats.diseaseNodes', 'Disease Nodes')}
              value={sankeyData?.statistics?.disease_count || 0}
              styles={{ content: { color: LAYER_COLORS[2] } }}
              loading={isLoading}
              data-testid="stat-disease-nodes"
            />
          </Card>
        </Col>
      </Row>

      {/* Filters */}
      <Card
        title={t('sankey.filters.title', 'Filters')}
        size="small"
        style={{ marginBottom: 16 }}
        data-testid="sankey-filters"
      >
        <Row gutter={[16, 16]} align="middle">
          <Col xs={24} sm={12} md={6}>
            <Space orientation="vertical" style={{ width: '100%' }} size={4}>
              <Text type="secondary" style={{ fontSize: 12 }}>
                {t('sankey.filters.species', 'Species')}
              </Text>
              <Select
                style={{ width: '100%' }}
                value={speciesId}
                onChange={setSpeciesId}
                options={SPECIES_OPTIONS}
                data-testid="species-select"
              />
            </Space>
          </Col>
          <Col xs={24} sm={12} md={6}>
            <Space orientation="vertical" style={{ width: '100%' }} size={4}>
              <Text type="secondary" style={{ fontSize: 12 }}>
                {t('sankey.filters.disease', 'Disease/Trait')}
              </Text>
              <Input
                placeholder={t('sankey.filters.diseasePlaceholder', 'e.g., diabetes')}
                prefix={<SearchOutlined />}
                value={traitInput}
                onChange={(e) => handleSearch(e.target.value)}
                allowClear
                data-testid="disease-search"
              />
            </Space>
          </Col>
          <Col xs={24} sm={12} md={6}>
            <Space orientation="vertical" style={{ width: '100%' }} size={4}>
              <Text type="secondary" style={{ fontSize: 12 }}>
                {t('sankey.filters.minBA', 'Min. Binding Affinity')}: {minBA}
              </Text>
              <div data-testid="ba-slider">
                <Slider
                  min={0}
                  max={100}
                  value={minBA}
                  onChange={setMinBA}
                  marks={{ 0: '0', 50: '50', 100: '100' }}
                />
              </div>
            </Space>
          </Col>
          <Col xs={24} sm={12} md={6}>
            <Space orientation="vertical" style={{ width: '100%' }} size={4}>
              <Text type="secondary" style={{ fontSize: 12 }}>
                {t('sankey.filters.limit', 'Node Limit')}: {limit}
              </Text>
              <div data-testid="limit-slider">
                <Slider
                  min={50}
                  max={500}
                  step={50}
                  value={limit}
                  onChange={setLimit}
                  marks={{ 50: '50', 250: '250', 500: '500' }}
                />
              </div>
            </Space>
          </Col>
        </Row>
      </Card>

      {/* Sankey Chart */}
      <Card
        title={t('sankey.chartTitle', 'lncRNA → Gene → Disease Flow')}
        style={{ marginBottom: 16 }}
        data-testid="sankey-chart-card"
      >
        {isLoading ? (
          <div style={{ height: 600, display: 'flex', alignItems: 'center', justifyContent: 'center' }}>
            <Spin size="large" />
          </div>
        ) : !sankeyData || sankeyData.nodes.length === 0 ? (
          <Empty
            description={t('sankey.noData', 'No data available. Try adjusting filters.')}
            style={{ padding: '60px 0' }}
          />
        ) : (
          <ReactECharts
            echarts={echarts}
            option={chartOption}
            style={{ height: 600 }}
            opts={{ renderer: 'canvas' }}
            data-testid="sankey-chart"
          />
        )}
      </Card>

      {/* Data Table */}
      <Card
        title={t('sankey.table.title', 'Flow Details')}
        data-testid="sankey-table-card"
      >
        <Table<SankeyTableRow>
          columns={columns}
          dataSource={tableData}
          loading={isLoading}
          pagination={{
            pageSize: 20,
            showSizeChanger: true,
            showTotal: (total) => t('sankey.table.total', `Total ${total} flows`, { count: total }),
          }}
          scroll={{ x: 800 }}
          size="middle"
          data-testid="sankey-table"
        />
      </Card>
    </div>
  )
}
