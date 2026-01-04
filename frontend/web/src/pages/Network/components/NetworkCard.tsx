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
import { applyNetworkFilters } from '../utils/networkFiltering'
import { GeneDetailDrawer } from './GeneDetailDrawer'
import { ComparisonDrawer } from './ComparisonDrawer'
import type { NetworkCardProps } from '../types'

// 类型别名
type Core = cytoscape.Core
type NodeSingular = cytoscape.NodeSingular
type EdgeSingular = cytoscape.EdgeSingular

// cytoscape 调用包装（绕过 TypeScript 类型检查）
const createCytoscape = cytoscape as unknown as (options: cytoscape.CytoscapeOptions) => Core

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
  const onRefReadyRef = useRef(onRefReady)
  const tRef = useRef(t)
  const tooltipDivRef = useRef<HTMLDivElement | null>(null)
  const hoveredEdgeIdRef = useRef<string | null>(null)

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
  const [minBAApplied, setMinBAApplied] = useState<number>(0)
  const [nodeTypeFilter, setNodeTypeFilter] = useState<string>('all')
  const [minDegree, setMinDegree] = useState<number>(0)
  const [minDegreeApplied, setMinDegreeApplied] = useState<number>(0)
  const [currentLayout, setCurrentLayout] = useState<string>('concentric')
  const currentLayoutRef = useRef(currentLayout)

  useEffect(() => {
    currentLayoutRef.current = currentLayout
  }, [currentLayout])

  useEffect(() => {
    onRefReadyRef.current = onRefReady
  }, [onRefReady])

  useEffect(() => {
    tRef.current = t
  }, [t])

  // 布局切换函数
  const handleLayoutChange = (layoutName: string) => {
    setCurrentLayout(layoutName)
    currentLayoutRef.current = layoutName
    if (!cyRef.current) return

    const nodeCount = data?.nodes?.length ?? 0
    const edgeCount = data?.edges?.length ?? 0
    const shouldAnimate = nodeCount <= 300 && edgeCount <= 1000

    const layout = cyRef.current.layout(getLayoutConfig(layoutName, {
      animate: shouldAnimate,
      animationDuration: shouldAnimate ? 500 : 0
    }))
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
    enabled: !!selectedLncrnaForComparison && comparisonDrawerOpen,
    meta: { skipGlobalErrorHandler: true },
  })

  // Handler for opening comparison
  const handleCompareSpecies = (node: NodeSingular) => {
    const geneId = node.data('gene_id') as number
    const coreId = node.data('core_id') as number
    const geneName = node.data('label') as string

    setSelectedLncrnaForComparison({ geneId, coreId, geneName })
    setComparisonDrawerOpen(true)
  }

  const removeTooltipDiv = () => {
    const tooltipDiv = tooltipDivRef.current
    if (tooltipDiv && document.body.contains(tooltipDiv)) {
      document.body.removeChild(tooltipDiv)
    }
    tooltipDivRef.current = null
    hoveredEdgeIdRef.current = null
  }

  const ensureTooltipDiv = () => {
    if (tooltipDivRef.current && document.body.contains(tooltipDivRef.current)) {
      return tooltipDivRef.current
    }

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
      display: none;
      white-space: nowrap;
    `
    document.body.appendChild(tooltipDiv)
    tooltipDivRef.current = tooltipDiv
    return tooltipDiv
  }

  // 渲染 Cytoscape 图表：仅在 data/error/loading 变化时重建，避免过滤/交互导致 destroy+create
  useEffect(() => {
    if (!data || !containerRef.current || error || loading) return

    const elements = [
      ...data.nodes.map((node: NetworkNode) => {
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
      ...data.edges.map((edge: NetworkEdge) => ({
        data: {
          id: String(edge.regulation_id),
          source: edge.source,
          target: edge.target,
          ba: edge.binding_affinity || 0,
          regulation_id: edge.regulation_id
        }
      }))
    ]

    // 基于原始数据计算 BA 映射范围（避免过滤时频繁重建 style）
    // 注意：避免 Math.min(...arr) 在大数组下的参数长度上限与性能问题
    let minBARange = Number.POSITIVE_INFINITY
    let maxBARange = Number.NEGATIVE_INFINITY
    for (const edge of data.edges) {
      const ba = edge.binding_affinity
      if (ba == null || ba <= 0) continue
      if (ba < minBARange) minBARange = ba
      if (ba > maxBARange) maxBARange = ba
    }
    if (!Number.isFinite(minBARange) || !Number.isFinite(maxBARange)) {
      minBARange = 0
      maxBARange = 100
    } else if (minBARange === maxBARange) {
      maxBARange = minBARange + 1
    }

    const nodeCount = data.nodes?.length ?? 0
    const edgeCount = data.edges?.length ?? 0
    const shouldAnimate = nodeCount <= 300 && edgeCount <= 1000

    const layoutName = currentLayoutRef.current

    const cy = createCytoscape({
      container: containerRef.current,
      elements,
      style: [
        {
          selector: 'node.filtered-out',
          style: {
            'display': 'none'
          }
        },
        {
          selector: 'edge.filtered-out',
          style: {
            'display': 'none'
          }
        },
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
      layout: getLayoutConfig(layoutName, {
        animate: shouldAnimate,
        animationDuration: shouldAnimate ? 500 : 0
      })
    })

    cyRef.current = cy
    onRefReadyRef.current?.(cyRef as React.RefObject<Core>, true)

    const hideTooltip = () => {
      hoveredEdgeIdRef.current = null
      const tooltipDiv = tooltipDivRef.current
      if (tooltipDiv) {
        tooltipDiv.style.display = 'none'
      }
    }

    const updateTooltipPosition = (evt: cytoscape.EventObject) => {
      const tooltipDiv = tooltipDivRef.current
      if (!tooltipDiv) return
      const mouseEvent = evt.originalEvent as MouseEvent | undefined
      if (!mouseEvent) return
      tooltipDiv.style.left = `${mouseEvent.clientX + 10}px`
      tooltipDiv.style.top = `${mouseEvent.clientY + 10}px`
    }

    // tooltip：使用 delegated 事件，避免为每条 edge 绑定 mousemove
    const handleEdgeMouseOver = (evt: cytoscape.EventObject) => {
      const edge = evt.target as EdgeSingular
      const baRaw = edge.data('ba')
      if (baRaw === undefined || baRaw === null) return
      const ba = typeof baRaw === 'number' ? baRaw : Number(baRaw)
      if (Number.isNaN(ba)) return

      const tooltipDiv = ensureTooltipDiv()
      hoveredEdgeIdRef.current = edge.id()

      tooltipDiv.innerHTML = ''
      const labelSpan = document.createElement('strong')
      labelSpan.textContent = tRef.current('edge.bindingAffinityLabel')
      const valueSpan = document.createElement('span')
      valueSpan.textContent = ba.toFixed(2)
      tooltipDiv.appendChild(labelSpan)
      tooltipDiv.appendChild(valueSpan)
      tooltipDiv.style.display = 'block'
      updateTooltipPosition(evt)
    }

    const handleEdgeMouseMove = (evt: cytoscape.EventObject) => {
      const edge = evt.target as EdgeSingular
      if (hoveredEdgeIdRef.current !== edge.id()) return
      updateTooltipPosition(evt)
    }

    const handleEdgeMouseOut = (evt: cytoscape.EventObject) => {
      const edge = evt.target as EdgeSingular
      if (hoveredEdgeIdRef.current !== edge.id()) return
      hideTooltip()
    }

    const handleNodeTap = (evt: cytoscape.EventObject) => {
      const node = evt.target as NodeSingular
      const geneId = node.data('gene_id') as number | undefined
      if (geneId) {
        setSelectedGeneId(geneId)
        setDetailDrawerOpen(true)
      }
    }

    cy.on('mouseover', 'edge', handleEdgeMouseOver)
    cy.on('mousemove', 'edge', handleEdgeMouseMove)
    cy.on('mouseout', 'edge', handleEdgeMouseOut)
    cy.on('tap', 'node', handleNodeTap)

    return () => {
      hideTooltip()
      removeTooltipDiv()

      cy.off('mouseover', 'edge', handleEdgeMouseOver)
      cy.off('mousemove', 'edge', handleEdgeMouseMove)
      cy.off('mouseout', 'edge', handleEdgeMouseOut)
      cy.off('tap', 'node', handleNodeTap)

      cy.destroy()
      if (cyRef.current === cy) {
        cyRef.current = null
      }
      onRefReadyRef.current?.(cyRef as React.RefObject<Core>, false)
    }
  }, [data, error, loading])

  // 过滤器只对现有元素加/去 class，不触发实例重建
  useEffect(() => {
    if (!cyRef.current || !data) return

    const { filteredNodes, finalEdges } = applyNetworkFilters(
      data,
      minBAApplied,
      nodeTypeFilter,
      minDegreeApplied
    )

    const visibleNodeIds = new Set(filteredNodes.map((n: NetworkNode) => n.id))
    const visibleEdgeIds = new Set(finalEdges.map((e: NetworkEdge) => String(e.regulation_id)))

    const cy = cyRef.current
    cy.batch(() => {
      cy.nodes().forEach((node: NodeSingular) => {
        if (visibleNodeIds.has(node.id())) {
          node.removeClass('filtered-out')
        } else {
          node.addClass('filtered-out')
        }
      })
      cy.edges().forEach((edge: EdgeSingular) => {
        if (visibleEdgeIds.has(edge.id())) {
          edge.removeClass('filtered-out')
        } else {
          edge.addClass('filtered-out')
        }
      })
    })
  }, [data, minBAApplied, nodeTypeFilter, minDegreeApplied])

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
  }, [searchTerm, data])

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
                  {(minBAApplied > 0 || nodeTypeFilter !== 'all' || minDegreeApplied > 0) && (
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
                      onChange={(value) => setMinBA(value as number)}
                      onAfterChange={(value) => setMinBAApplied(value as number)}
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
                      onChange={(value) => setMinDegree(value as number)}
                      onAfterChange={(value) => setMinDegreeApplied(value as number)}
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
                      setMinBAApplied(0)
                      setNodeTypeFilter('all')
                      setMinDegree(0)
                      setMinDegreeApplied(0)
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
