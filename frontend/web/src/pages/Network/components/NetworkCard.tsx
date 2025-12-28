import { useState, useEffect, useRef, memo } from 'react'
import { Button, Space, Input, Dropdown, message, Collapse, Tag, Slider, Radio, Select } from 'antd'
import { SearchOutlined, DownloadOutlined, FileImageOutlined, FileTextOutlined, FilterOutlined, SwapOutlined } from '@ant-design/icons'
import { useQuery } from '@tanstack/react-query'
import { useTranslation } from 'react-i18next'
import { saveAs } from 'file-saver'
import cytoscape from 'cytoscape'
import type { GeneDetail, NetworkNode, NetworkEdge } from '@/types/network'
import { LoadingState } from '@/components/LoadingState'
import { ErrorState } from '@/components/ErrorState'
import { ConservationLegend } from '@/components/ConservationLegend'
import { parseConservationLabel, CONSERVATION_COLORS } from '@/types/conservation'
import { networkApi } from '@/api/network'
import { escapeCSV } from '@/utils/csv'
import { getLayoutConfig } from '../utils/cytoscapeLayouts'
import { exportCytoscapePngBlob } from '../utils/cytoscapeExport'
import { GeneDetailDrawer } from './GeneDetailDrawer'
import { ComparisonDrawer } from './ComparisonDrawer'
import type { NetworkCardProps } from '../types'

// 类型别名
type Core = cytoscape.Core
type NodeSingular = cytoscape.NodeSingular
type EdgeSingular = cytoscape.EdgeSingular

// cytoscape 调用包装（绕过 TypeScript 类型检查）
const createCytoscape = cytoscape as unknown as (options: cytoscape.CytoscapeOptions) => Core

const EDGE_TOOLTIP_SCRATCH = '_hlaEdgeTooltip'
type EdgeTooltipState = {
  tooltipDiv: HTMLDivElement
  updatePosition: (e: cytoscape.EventObject) => void
}

const cleanupEdgeTooltip = (edge: EdgeSingular) => {
  const scratch = edge.scratch(EDGE_TOOLTIP_SCRATCH) as EdgeTooltipState | null | undefined
  const tooltipDiv = scratch?.tooltipDiv ?? (edge.data('tooltipDiv') as HTMLDivElement | undefined)
  const updatePosition =
    scratch?.updatePosition ??
    (edge.data('updatePosition') as ((e: cytoscape.EventObject) => void) | undefined)

  if (tooltipDiv && document.body.contains(tooltipDiv)) {
    document.body.removeChild(tooltipDiv)
  }
  if (updatePosition) {
    edge.off('mousemove', updatePosition)
  }

  edge.scratch(EDGE_TOOLTIP_SCRATCH, null)
  edge.removeData('tooltipDiv')
  edge.removeData('updatePosition')
}

/**
 * NetworkCard Component
 * Displays a single species network visualization with Cytoscape.js
 * Features:
 * - Interactive network graph with conservation-based coloring
 * - Search and filtering capabilities
 * - Multiple layout algorithms
 * - Export to PNG/SVG/CSV/JSON
 * - Gene detail drawer
 * - Cross-species comparison
 */
export const NetworkCard = memo(({
  speciesId: _speciesId,
  speciesName,
  data,
  loading,
  error,
  onRefReady,
  lncrnaCoreId,
  lncrnaGeneId
}: NetworkCardProps) => {
  const { t } = useTranslation('network')
  const containerRef = useRef<HTMLDivElement>(null)
  const cyRef = useRef<Core | null>(null)
  const [selectedGeneId, setSelectedGeneId] = useState<number | null>(null)
  const [detailDrawerOpen, setDetailDrawerOpen] = useState(false)
  const [searchTerm, setSearchTerm] = useState('')
  const [searchResults, setSearchResults] = useState<Array<{id: string, label: string}>>([])

  // Cross-species comparison state
  const [comparisonDrawerOpen, setComparisonDrawerOpen] = useState(false)
  const [selectedLncrnaForComparison, setSelectedLncrnaForComparison] = useState<{
    geneId: number
    coreId: number
    geneName: string
  } | null>(null)

  // 高级过滤器状态
  const [minBA, setMinBA] = useState<number>(0)
  const [nodeTypeFilter, setNodeTypeFilter] = useState<string>('all')
  const [minDegree, setMinDegree] = useState<number>(0)
  const [currentLayout, setCurrentLayout] = useState<string>('concentric')

  // 布局切换函数
  const handleLayoutChange = (layoutName: string) => {
    if (!cyRef.current) return

    setCurrentLayout(layoutName)
    const layout = cyRef.current.layout(getLayoutConfig(layoutName))
    layout.run()
  }

  // 获取基因详情
  const { data: geneDetail, isLoading: detailLoading } = useQuery<GeneDetail | null>({
    queryKey: ['gene-detail', selectedGeneId],
    queryFn: async ({ signal }) => {
      if (!selectedGeneId) return null
      const res = await networkApi.getGeneDetail(selectedGeneId, signal)
      return res.data
    },
    enabled: !!selectedGeneId && detailDrawerOpen
  })

  // Cross-species comparison query
  const { data: comparisonData, isLoading: comparisonLoading, error: comparisonError } = useQuery({
    queryKey: ['species-comparison', selectedLncrnaForComparison?.geneId],
    queryFn: async ({ signal }) => {
      if (!selectedLncrnaForComparison?.geneId) return null
      const res = await networkApi.compareSpecies(selectedLncrnaForComparison.geneId, {
        min_ba: 0,
        max_targets_per_species: 100
      }, signal)
      return res.data
    },
    enabled: !!selectedLncrnaForComparison && comparisonDrawerOpen
  })

  // Handler for opening comparison
  const handleCompareSpecies = (node: NodeSingular) => {
    const geneId = node.data('gene_id') as number
    const coreId = node.data('core_id') as number
    const geneName = node.data('label') as string

    setSelectedLncrnaForComparison({ geneId, coreId, geneName })
    setComparisonDrawerOpen(true)
  }

  // 确保组件卸载时总是销毁Cytoscape实例和清理tooltip
  useEffect(() => {
    return () => {
      // 清理所有残留的tooltip
      document.querySelectorAll('[data-cy-tooltip]').forEach(el => {
        if (document.body.contains(el)) {
          document.body.removeChild(el)
        }
      })

      // 销毁Cytoscape实例
      if (cyRef.current) {
        cyRef.current.edges().forEach((edge: EdgeSingular) => cleanupEdgeTooltip(edge))
        cyRef.current.destroy()
        cyRef.current = null
      }
    }
  }, [])

  // 当error或loading状态时，销毁现有实例
  useEffect(() => {
    if (error || loading) {
      if (cyRef.current) {
        cyRef.current.edges().forEach((edge: EdgeSingular) => cleanupEdgeTooltip(edge))
        cyRef.current.destroy()
        cyRef.current = null
      }
    }
  }, [error, loading])

  // 渲染Cytoscape图表
  useEffect(() => {
    if (!data || !containerRef.current || error || loading) return

    // 清理所有残留的tooltip
    document.querySelectorAll('[data-cy-tooltip]').forEach(el => {
      if (document.body.contains(el)) {
        document.body.removeChild(el)
      }
    })

    // 销毁旧实例
    if (cyRef.current) {
      cyRef.current.edges().forEach((edge: EdgeSingular) => cleanupEdgeTooltip(edge))
      cyRef.current.off('mouseover', 'edge')
      cyRef.current.off('mouseout', 'edge')
      cyRef.current.off('tap', 'node')
      cyRef.current.destroy()
      cyRef.current = null
    }

    // 应用过滤器
    const filteredEdges = data.edges.filter((edge: NetworkEdge) => {
      const ba = edge.binding_affinity || 0
      return ba >= minBA
    })

    const nodeDegrees = new Map<string, number>()
    filteredEdges.forEach((edge: NetworkEdge) => {
      nodeDegrees.set(edge.source, (nodeDegrees.get(edge.source) || 0) + 1)
      nodeDegrees.set(edge.target, (nodeDegrees.get(edge.target) || 0) + 1)
    })

    const filteredNodes = data.nodes.filter((node: NetworkNode) => {
      if (nodeTypeFilter !== 'all' && node.type !== nodeTypeFilter) {
        return false
      }
      const degree = nodeDegrees.get(node.id) || 0
      return degree >= minDegree
    })

    const nodeIds = new Set(filteredNodes.map((n: NetworkNode) => n.id))
    const finalEdges = filteredEdges.filter((edge: NetworkEdge) =>
      nodeIds.has(edge.source) && nodeIds.has(edge.target)
    )

    const elements = [
      ...filteredNodes.map((node: NetworkNode) => {
        const conservationData = parseConservationLabel(
          node.conservation_label,
          node.conservation_count
        )
        return {
          data: {
            id: node.id,
            label: node.label,
            type: node.type,
            gene_id: node.gene_id,
            core_id: node.core_id,
            conservation: conservationData.category
          }
        }
      }),
      ...finalEdges.map((edge: NetworkEdge) => ({
        data: {
          source: edge.source,
          target: edge.target,
          ba: edge.binding_affinity || 0,
          regulation_id: edge.regulation_id
        }
      }))
    ]

    // 动态计算BA值范围
    const baValues = finalEdges
      .map((e: NetworkEdge) => e.binding_affinity)
      .filter((ba: number) => ba != null && ba > 0)

    const minBARange = baValues.length > 0 ? Math.min(...baValues) : 0
    let maxBARange = baValues.length > 0 ? Math.max(...baValues) : 100

    if (minBARange === maxBARange) {
      maxBARange = minBARange + 1
    }

    cyRef.current = createCytoscape({
      container: containerRef.current,
      elements,
      style: [
        {
          selector: 'node[type="lncRNA"]',
          style: {
            'shape': 'ellipse',
            'background-color': '#1890ff',
            'label': 'data(label)',
            'width': 50,
            'height': 50,
            'font-size': 10,
            'text-valign': 'center',
            'text-halign': 'center',
            'color': '#000',
            'text-outline-width': 2,
            'text-outline-color': '#fff'
          }
        },
        {
          selector: 'node[type="protein_coding"]',
          style: {
            'shape': 'rectangle',
            'background-color': '#52c41a',
            'label': 'data(label)',
            'width': 45,
            'height': 45,
            'font-size': 10,
            'text-valign': 'center',
            'text-halign': 'center',
            'color': '#000',
            'text-outline-width': 2,
            'text-outline-color': '#fff'
          }
        },
        {
          selector: 'edge',
          style: {
            'width': `mapData(ba, ${minBARange}, ${maxBARange}, 1, 5)`,
            'line-color': `mapData(ba, ${minBARange}, ${maxBARange}, #d9d9d9, #ff4d4f)`,
            'target-arrow-color': `mapData(ba, ${minBARange}, ${maxBARange}, #d9d9d9, #ff4d4f)`,
            'target-arrow-shape': 'triangle',
            'curve-style': 'bezier',
            'opacity': 0.8
          }
        },
        {
          selector: 'node.highlighted',
          style: {
            'border-width': 4,
            'border-color': '#faad14',
            'z-index': 999
          }
        },
        {
          selector: 'node[conservation="high"]',
          style: {
            'background-color': CONSERVATION_COLORS.high
          }
        },
        {
          selector: 'node[conservation="medium"]',
          style: {
            'background-color': CONSERVATION_COLORS.medium
          }
        },
        {
          selector: 'node[conservation="low"]',
          style: {
            'background-color': CONSERVATION_COLORS.low
          }
        },
        {
          selector: 'node[conservation="unknown"]',
          style: {
            'background-color': CONSERVATION_COLORS.unknown
          }
        }
      ],
      layout: getLayoutConfig(currentLayout)
    })

    // 通知父组件 cyRef 已准备好
    onRefReady?.(cyRef as React.RefObject<Core>, true)

    // 添加边的tooltip
    cyRef.current.on('mouseover', 'edge', (evt: cytoscape.EventObject) => {
      const edge = evt.target as EdgeSingular
      const baRaw = edge.data('ba')
      if (baRaw === undefined || baRaw === null) return
      const ba = typeof baRaw === 'number' ? baRaw : Number(baRaw)
      if (Number.isNaN(ba)) return

      cleanupEdgeTooltip(edge)

      const tooltipDiv = document.createElement('div')
      tooltipDiv.setAttribute('data-cy-tooltip', 'true')
      tooltipDiv.style.cssText = `
        position: fixed;
        background: white;
        padding: 8px 12px;
        border-radius: 4px;
        box-shadow: 0 2px 8px rgba(0,0,0,0.15);
        font-size: 12px;
        pointer-events: none;
        z-index: 9999;
      `
      const labelSpan = document.createElement('strong')
      labelSpan.textContent = t('edge.bindingAffinityLabel')
      const valueSpan = document.createElement('span')
      valueSpan.textContent = ba.toFixed(2)
      tooltipDiv.appendChild(labelSpan)
      tooltipDiv.appendChild(valueSpan)
      document.body.appendChild(tooltipDiv)

      const origEvent = evt.originalEvent as MouseEvent | undefined
      if (origEvent) {
        tooltipDiv.style.left = `${origEvent.clientX + 10}px`
        tooltipDiv.style.top = `${origEvent.clientY + 10}px`
      }

      const updatePosition = (e: cytoscape.EventObject) => {
        if (tooltipDiv && document.body.contains(tooltipDiv)) {
          const mouseEvent = e.originalEvent as MouseEvent | undefined
          if (mouseEvent) {
            tooltipDiv.style.left = `${mouseEvent.clientX + 10}px`
            tooltipDiv.style.top = `${mouseEvent.clientY + 10}px`
          }
        }
      }

      edge.on('mousemove', updatePosition)
      edge.scratch(EDGE_TOOLTIP_SCRATCH, { tooltipDiv, updatePosition } satisfies EdgeTooltipState)
    })

    cyRef.current.on('mouseout', 'edge', (evt: cytoscape.EventObject) => {
      const edge = evt.target as EdgeSingular
      cleanupEdgeTooltip(edge)
    })

    // 添加节点点击事件
    cyRef.current.on('tap', 'node', (evt: cytoscape.EventObject) => {
      const node = evt.target as NodeSingular
      const geneId = node.data('gene_id') as number | undefined
      if (geneId) {
        setSelectedGeneId(geneId)
        setDetailDrawerOpen(true)
      }
    })

    return () => {
      document.querySelectorAll('[data-cy-tooltip]').forEach(el => {
        if (document.body.contains(el)) {
          document.body.removeChild(el)
        }
      })

      if (cyRef.current) {
        cyRef.current.edges().forEach((edge: EdgeSingular) => cleanupEdgeTooltip(edge))
        cyRef.current.off('mouseover', 'edge')
        cyRef.current.off('mouseout', 'edge')
        cyRef.current.off('tap', 'node')
      }
    }
  }, [data, error, loading, minBA, nodeTypeFilter, minDegree, currentLayout, t, onRefReady])

  // 独立的搜索高亮 Effect
  useEffect(() => {
    if (!cyRef.current) return

    cyRef.current.nodes().removeClass('highlighted')

    if (searchTerm) {
      const newResults: Array<{id: string, label: string}> = []
      cyRef.current.nodes().forEach((node: NodeSingular) => {
        const nodeLabel = node.data('label') as string
        const nodeId = node.data('id') as string
        if (nodeLabel.toLowerCase().includes(searchTerm.toLowerCase()) || nodeId.toLowerCase().includes(searchTerm.toLowerCase())) {
          node.addClass('highlighted')
          newResults.push({ id: nodeId, label: nodeLabel })
        }
      })
      setSearchResults(newResults)

      if (newResults.length === 1) {
        const node = cyRef.current.$id(newResults[0].id)
        cyRef.current.animate({
          center: { eles: node },
          zoom: 2
        }, {
          duration: 500
        })
      }
    } else {
      setSearchResults([])
    }
  }, [searchTerm, data, minBA, nodeTypeFilter, minDegree, currentLayout])

  const handleSearch = (value: string) => {
    setSearchTerm(value)
  }

  const highlightNode = (nodeId: string) => {
    if (!cyRef.current) return

    const node = cyRef.current.$id(nodeId)
    cyRef.current.nodes().removeClass('highlighted')
    node.addClass('highlighted')

    cyRef.current.animate({
      center: { eles: node },
      zoom: 2
    }, {
      duration: 500
    })
  }

  // 导出功能
  const exportAsPNG = async () => {
    if (!cyRef.current) {
      message.error(t('export.networkNotLoaded'))
      return
    }

    const messageKey = `png-${speciesName}-${Date.now()}`
    try {
      message.loading({ content: t('export.generating', { species: speciesName, format: 'PNG' }), key: messageKey, duration: 0 })

      const blob = exportCytoscapePngBlob(cyRef.current, {
        bg: 'white',
        full: true,
        scale: 2,
      })

      const url = URL.createObjectURL(blob)
      const a = document.createElement('a')
      a.href = url
      a.download = `network-${speciesName}-${Date.now()}.png`
      a.click()
      URL.revokeObjectURL(url)
      message.success({ content: t('export.success', { species: speciesName, format: 'PNG' }), key: messageKey })
    } catch (error) {
      message.error({ content: t('export.failed', { species: speciesName, format: 'PNG' }), key: messageKey })
      console.error(error)
    }
  }

  const exportAsSVG = () => {
    if (!cyRef.current) {
      message.error(t('export.networkNotLoaded'))
      return
    }

    const messageKey = `svg-${speciesName}-${Date.now()}`
    message.loading({ content: t('export.generating', { species: speciesName, format: 'SVG' }), key: messageKey, duration: 0 })

    try {
      const svgContent = cyRef.current.svg({
        full: true,
        scale: 2,
        bg: '#ffffff'
      })

      const blob = new Blob([svgContent], { type: 'image/svg+xml;charset=utf-8' })
      saveAs(blob, `network-${speciesName}-${Date.now()}.svg`)
      message.success({ content: t('export.success', { species: speciesName, format: 'SVG' }), key: messageKey })
    } catch (error) {
      console.error('SVG export failed:', error)
      message.error({ content: t('export.failed', { species: speciesName, format: 'SVG' }), key: messageKey })
    }
  }

  const exportAsCSV = () => {
    if (!data) {
      message.error(t('export.noData'))
      return
    }

    const messageKey = `csv-${speciesName}-${Date.now()}`
    message.loading({ content: t('export.generating', { species: speciesName, format: 'CSV' }), key: messageKey, duration: 0 })
    setTimeout(() => {
      try {
        const nodeHeaders = ['ID', 'Label', 'Type', 'Gene ID', 'Core ID']
        const nodeRows = data.nodes.map((n: NetworkNode) =>
          [escapeCSV(n.id), escapeCSV(n.label), escapeCSV(n.type), escapeCSV(n.gene_id), escapeCSV(n.core_id)].join(',')
        )
        const nodeCSV = [nodeHeaders.join(','), ...nodeRows].join('\n')

        const edgeHeaders = ['Source', 'Target', 'Binding Affinity', 'Regulation ID']
        const edgeRows = data.edges.map((e: NetworkEdge) =>
          [escapeCSV(e.source), escapeCSV(e.target), escapeCSV(e.binding_affinity), escapeCSV(e.regulation_id)].join(',')
        )
        const edgeCSV = [edgeHeaders.join(','), ...edgeRows].join('\n')

        const csvContent = `Nodes:\n${nodeCSV}\n\nEdges:\n${edgeCSV}`
        const blob = new Blob([csvContent], { type: 'text/csv;charset=utf-8;' })
        const url = URL.createObjectURL(blob)
        const a = document.createElement('a')
        a.href = url
        a.download = `network-data-${speciesName}-${Date.now()}.csv`
        a.click()
        URL.revokeObjectURL(url)
        message.success({ content: t('export.success', { species: speciesName, format: 'CSV' }), key: messageKey })
      } catch (error) {
        message.error({ content: t('export.failed', { species: speciesName, format: 'CSV' }), key: messageKey })
        console.error(error)
      }
    }, 0)
  }

  const exportAsJSON = () => {
    if (!data) {
      message.error(t('export.noData'))
      return
    }

    const messageKey = `json-${speciesName}-${Date.now()}`
    message.loading({ content: t('export.generating', { species: speciesName, format: 'JSON' }), key: messageKey, duration: 0 })
    setTimeout(() => {
      try {
        const jsonContent = JSON.stringify(data, null, 2)
        const blob = new Blob([jsonContent], { type: 'application/json' })
        const url = URL.createObjectURL(blob)
        const a = document.createElement('a')
        a.href = url
        a.download = `network-data-${speciesName}-${Date.now()}.json`
        a.click()
        URL.revokeObjectURL(url)
        message.success({ content: t('export.success', { species: speciesName, format: 'JSON' }), key: messageKey })
      } catch (error) {
        message.error({ content: t('export.failed', { species: speciesName, format: 'JSON' }), key: messageKey })
        console.error(error)
      }
    }, 0)
  }

  if (loading) {
    return (
      <div style={{
        border: '1px solid #d9d9d9',
        borderRadius: 8,
        padding: 16,
        aspectRatio: '1/1',
        display: 'flex',
        alignItems: 'center',
        justifyContent: 'center'
      }}>
        <LoadingState />
      </div>
    )
  }

  if (error) {
    return (
      <div style={{
        border: '1px solid #d9d9d9',
        borderRadius: 8,
        padding: 16,
        aspectRatio: '1/1'
      }}>
        <h3>{speciesName}</h3>
        <ErrorState error={error} />
      </div>
    )
  }

  if (!data || data.nodes?.length === 0) {
    return (
      <div style={{
        border: '1px solid #d9d9d9',
        borderRadius: 8,
        padding: 16,
        aspectRatio: '1/1',
        display: 'flex',
        flexDirection: 'column',
        alignItems: 'center',
        justifyContent: 'center'
      }}>
        <h3>{speciesName}</h3>
        <div style={{ color: '#999', marginTop: 20 }}>{t('card.noData')}</div>
      </div>
    )
  }

  return (
    <>
      <div style={{
        border: '1px solid #d9d9d9',
        borderRadius: 8,
        padding: 16,
        backgroundColor: '#fff'
      }}>
        <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: 8 }}>
          <h3 style={{ margin: 0 }}>{speciesName}</h3>
          <Space size="small">
            <Input.Search
              placeholder={t('card.searchPlaceholder')}
              value={searchTerm}
              onChange={(e) => setSearchTerm(e.target.value)}
              onSearch={handleSearch}
              allowClear
              style={{ width: 200 }}
              size="small"
              prefix={<SearchOutlined />}
            />
            {lncrnaCoreId && lncrnaGeneId && (
              <Button
                size="small"
                icon={<SwapOutlined />}
                onClick={() => {
                  const lncrnaNode = cyRef.current?.nodes('[type="lncRNA"]').first()
                  if (lncrnaNode) {
                    handleCompareSpecies(lncrnaNode)
                  } else {
                    message.warning(t('comparison.noLncrnaSelected'))
                  }
                }}
              >
                {t('comparison.button')}
              </Button>
            )}
            <Dropdown
              menu={{
                items: [
                  {
                    key: 'png',
                    label: t('export.png'),
                    icon: <FileImageOutlined />,
                    onClick: exportAsPNG
                  },
                  {
                    key: 'svg',
                    label: t('export.svg'),
                    icon: <FileImageOutlined />,
                    onClick: exportAsSVG
                  },
                  {
                    type: 'divider'
                  },
                  {
                    key: 'csv',
                    label: t('export.csv'),
                    icon: <FileTextOutlined />,
                    onClick: exportAsCSV
                  },
                  {
                    key: 'json',
                    label: t('export.json'),
                    icon: <FileTextOutlined />,
                    onClick: exportAsJSON
                  }
                ]
              }}
            >
              <Button size="small" icon={<DownloadOutlined />}>
                {t('export.button')}
              </Button>
            </Dropdown>
          </Space>
        </div>
        <p style={{ fontSize: 12, color: '#666', marginBottom: 8 }}>
          {t('card.nodes')}: {data.nodes?.length || 0} |
          {t('card.edges')}: {data.edges?.length || 0} |
          {t('card.lncrna')}: {data.stats?.lncrna_count || 0} |
          {t('card.targetGenes')}: {data.stats?.protein_coding_count || 0}
          {searchResults.length > 0 && ` | ${t('card.searchResults')}: ${searchResults.length}`}
        </p>

        {/* 高级过滤器 */}
        <Collapse
          size="small"
          style={{ marginBottom: 8 }}
          items={[
            {
              key: 'filters',
              label: (
                <span style={{ fontSize: 12 }}>
                  <FilterOutlined /> {t('filters.title')}
                  {(minBA > 0 || nodeTypeFilter !== 'all' || minDegree > 0) && (
                    <Tag color="blue" style={{ marginLeft: 8, fontSize: 11 }}>{t('filters.enabled')}</Tag>
                  )}
                </span>
              ),
              children: (
                <Space orientation="vertical" style={{ width: '100%' }} size="small">
                  <div>
                    <div style={{ fontSize: 12, marginBottom: 4 }}>
                      {t('filters.baThreshold')}: {minBA}
                    </div>
                    <Slider
                      min={0}
                      max={100}
                      value={minBA}
                      onChange={setMinBA}
                      marks={{ 0: '0', 50: '50', 100: '100' }}
                      tooltip={{ formatter: (value) => t('filters.baTooltip', { value }) }}
                    />
                  </div>
                  <div>
                    <div style={{ fontSize: 12, marginBottom: 4 }}>{t('filters.nodeType')}:</div>
                    <Radio.Group
                      value={nodeTypeFilter}
                      onChange={(e) => setNodeTypeFilter(e.target.value)}
                      size="small"
                    >
                      <Radio.Button value="all">{t('filters.all')}</Radio.Button>
                      <Radio.Button value="lncRNA">lncRNA</Radio.Button>
                      <Radio.Button value="protein_coding">{t('filters.targetGene')}</Radio.Button>
                    </Radio.Group>
                  </div>
                  <div>
                    <div style={{ fontSize: 12, marginBottom: 4 }}>
                      {t('filters.minDegree')}: {minDegree}
                    </div>
                    <Slider
                      min={0}
                      max={10}
                      value={minDegree}
                      onChange={setMinDegree}
                      marks={{ 0: '0', 5: '5', 10: '10' }}
                      tooltip={{ formatter: (value) => t('filters.degreeTooltip', { value }) }}
                    />
                  </div>
                  <div>
                    <div style={{ fontSize: 12, marginBottom: 4 }}>{t('filters.layout')}:</div>
                    <Select
                      value={currentLayout}
                      onChange={handleLayoutChange}
                      size="small"
                      style={{ width: '100%' }}
                      options={[
                        { label: t('layouts.concentric'), value: 'concentric' },
                        { label: t('layouts.cose'), value: 'cose' },
                        { label: t('layouts.circle'), value: 'circle' },
                        { label: t('layouts.grid'), value: 'grid' },
                        { label: t('layouts.breadthfirst'), value: 'breadthfirst' },
                        { label: t('layouts.random'), value: 'random' }
                      ]}
                    />
                  </div>
                  <Button
                    size="small"
                    onClick={() => {
                      setMinBA(0)
                      setNodeTypeFilter('all')
                      setMinDegree(0)
                      handleLayoutChange('concentric')
                    }}
                  >
                    {t('filters.resetAll')}
                  </Button>
                </Space>
              )
            }
          ]}
        />

        {searchResults.length > 1 && (
          <div style={{ marginBottom: 8, fontSize: 12 }}>
            <span style={{ color: '#666' }}>{t('card.clickToLocate')}:</span>
            {searchResults.slice(0, 5).map((result) => (
              <Button
                key={result.id}
                type="link"
                size="small"
                onClick={() => highlightNode(result.id)}
                style={{ padding: '0 4px' }}
              >
                {result.label || result.id}
              </Button>
            ))}
            {searchResults.length > 5 && <span style={{ color: '#999' }}>...</span>}
          </div>
        )}

        {/* Network container with conservation legend */}
        <div style={{ position: 'relative', aspectRatio: '1/1', width: '100%' }}>
          <div ref={containerRef} style={{ width: '100%', height: '100%' }} />
          <ConservationLegend position="top-right" compact />
        </div>
      </div>

      {/* Gene Detail Drawer */}
      <GeneDetailDrawer
        open={detailDrawerOpen}
        onClose={() => setDetailDrawerOpen(false)}
        geneDetail={geneDetail || null}
        loading={detailLoading}
      />

      {/* Cross-species Comparison Drawer */}
      <ComparisonDrawer
        open={comparisonDrawerOpen}
        onClose={() => {
          setComparisonDrawerOpen(false)
          setSelectedLncrnaForComparison(null)
        }}
        selectedLncrna={selectedLncrnaForComparison}
        comparisonData={comparisonData ?? null}
        loading={comparisonLoading}
        error={comparisonError ?? null}
      />
    </>
  )
})

NetworkCard.displayName = 'NetworkCard'
