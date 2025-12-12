import { useState, useEffect, useRef, memo, useMemo } from 'react'
import { Button, Space, Select, message, Drawer, Descriptions, Tag, Input, Dropdown, Slider, Radio, Collapse, Modal, Checkbox, Alert, Table, Tabs } from 'antd'
import { SearchOutlined, DownloadOutlined, FileImageOutlined, FileTextOutlined, FilterOutlined, SwapOutlined } from '@ant-design/icons'
import { useQueries, useQuery } from '@tanstack/react-query'
import { useTranslation } from 'react-i18next'
import { networkApi } from '@/api/network'
import { diseasesApi } from '@/api/diseases'
import { LoadingState } from '@/components/LoadingState'
import { ErrorState } from '@/components/ErrorState'
import cytoscape from 'cytoscape'
import cytoscapeSvg from 'cytoscape-svg'
// 类型扩展由 src/types/cytoscape-ext.d.ts 提供

// 类型别名
type Core = cytoscape.Core
type NodeSingular = cytoscape.NodeSingular

// cytoscape 调用包装（绕过 TypeScript 类型检查）
const createCytoscape = cytoscape as unknown as (options: cytoscape.CytoscapeOptions) => Core
import type { GeneDetail } from '@/types/network'
import JSZip from 'jszip'
import { saveAs } from 'file-saver'
import { ConservationLegend } from '@/components/ConservationLegend'
import { parseConservationLabel, CONSERVATION_COLORS } from '@/types/conservation'

// 注册 cytoscape-svg 插件 - 模块作用域执行一次，添加 SSR 保护
if (typeof window !== 'undefined') {
  cytoscape.use(cytoscapeSvg)
}

// 物种ID到翻译key的映射
const SPECIES_KEYS: Record<number, string> = {
  1: 'human',
  2: 'chimpanzee',
  3: 'macaque',
  4: 'marmoset'
}

// 物种ID到英文名的映射（用于文件名，保持不变）
const SPECIES_EN_NAMES: Record<number, string> = {
  1: 'Human',
  2: 'Chimpanzee',
  3: 'Macaque',
  4: 'Marmoset'
}

/**
 * CSV 转义函数（防止 CSV 注入和公式注入）
 * 安全措施：
 * 1. 以 =, +, -, @, \t, \r 开头的字符串前添加单引号防止公式注入
 * 2. 包含逗号、双引号、换行符的字符串用双引号包裹
 */
const escapeCSV = (val: unknown): string => {
  let str = String(val ?? '')

  // 防止 CSV 公式注入：Excel/Sheets 会将这些字符开头的内容解释为公式
  if (/^[=+\-@\t\r]/.test(str)) {
    str = "'" + str
  }

  // 处理需要引号包裹的特殊字符
  if (str.includes(',') || str.includes('"') || str.includes('\n') || str.includes('\r')) {
    return `"${str.replace(/"/g, '""')}"`
  }
  return str
}

interface NetworkCardProps {
  speciesId: number
  speciesName: string
  data: any
  loading: boolean
  error: any
  onRefReady?: (cyRef: React.RefObject<Core>, isReady: boolean) => void
  lncrnaCoreId?: number  // NEW: For cross-species comparison
  lncrnaGeneId?: number  // NEW: For cross-species comparison
}

const NetworkCard = memo(({ speciesId: _speciesId, speciesName, data, loading, error, onRefReady, lncrnaCoreId, lncrnaGeneId }: NetworkCardProps) => {
  const { t } = useTranslation('network')
  const containerRef = useRef<HTMLDivElement>(null)
  const cyRef = useRef<Core | null>(null)
  const [selectedGeneId, setSelectedGeneId] = useState<number | null>(null)
  const [detailDrawerOpen, setDetailDrawerOpen] = useState(false)
  const [searchTerm, setSearchTerm] = useState('')
  const [searchResults, setSearchResults] = useState<Array<{id: string, label: string}>>([])

  // NEW: Cross-species comparison state
  const [comparisonDrawerOpen, setComparisonDrawerOpen] = useState(false)
  const [selectedLncrnaForComparison, setSelectedLncrnaForComparison] = useState<{
    geneId: number
    coreId: number
    geneName: string
  } | null>(null)

  // Phase 3: 高级过滤器状态
  const [minBA, setMinBA] = useState<number>(0)
  const [nodeTypeFilter, setNodeTypeFilter] = useState<string>('all') // 'all' | 'lncRNA' | 'protein_coding'
  const [minDegree, setMinDegree] = useState<number>(0)
  const [currentLayout, setCurrentLayout] = useState<string>('concentric')

  // Phase 3: 布局配置函数
  const getLayoutConfig = (layoutName: string) => {
    const baseConfig = { animate: true, animationDuration: 500 }

    switch (layoutName) {
      case 'concentric':
        return {
          name: 'concentric',
          ...baseConfig,
          concentric: (node: NodeSingular) => node.data('type') === 'lncRNA' ? 2 : 1,
          levelWidth: () => 1,
          minNodeSpacing: 60
        }
      case 'cose':
        return {
          name: 'cose',
          ...baseConfig,
          nodeRepulsion: () => 8000,
          idealEdgeLength: () => 100,
          edgeElasticity: () => 100,
          nestingFactor: 1.2
        }
      case 'circle':
        return {
          name: 'circle',
          ...baseConfig,
          radius: 200,
          startAngle: -Math.PI / 2
        }
      case 'grid':
        return {
          name: 'grid',
          ...baseConfig,
          rows: undefined,
          cols: undefined
        }
      case 'breadthfirst':
        return {
          name: 'breadthfirst',
          ...baseConfig,
          directed: true,
          spacingFactor: 1.5,
          roots: '[type="lncRNA"]'  // 使用选择器字符串而不是节点集合
        }
      case 'random':
        return {
          name: 'random',
          ...baseConfig
        }
      default:
        return {
          name: 'concentric',
          ...baseConfig,
          concentric: (node: NodeSingular) => node.data('type') === 'lncRNA' ? 2 : 1,
          levelWidth: () => 1,
          minNodeSpacing: 60
        }
    }
  }

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
    queryFn: async () => {
      if (!selectedGeneId) return null
      const res = await networkApi.getGeneDetail(selectedGeneId)
      return res.data
    },
    enabled: !!selectedGeneId && detailDrawerOpen
  })

  // NEW: Cross-species comparison query
  const { data: comparisonData, isLoading: comparisonLoading, error: comparisonError } = useQuery({
    queryKey: ['species-comparison', selectedLncrnaForComparison?.geneId],
    queryFn: async () => {
      if (!selectedLncrnaForComparison?.geneId) return null
      const res = await networkApi.compareSpecies(selectedLncrnaForComparison.geneId, {
        min_ba: 0,
        max_targets_per_species: 100
      })
      return res.data
    },
    enabled: !!selectedLncrnaForComparison && comparisonDrawerOpen
  })

  // NEW: Handler for opening comparison
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
        cyRef.current.destroy()
        cyRef.current = null
      }
    }
  }, [])

  // 当error或loading状态时，销毁现有实例
  useEffect(() => {
    if (error || loading) {
      if (cyRef.current) {
        cyRef.current.destroy()
        cyRef.current = null
      }
    }
  }, [error, loading])

  // 渲染Cytoscape图表（不包含搜索依赖，避免重建）
  useEffect(() => {
    if (!data || !containerRef.current || error || loading) return

    // 清理所有残留的tooltip（在重建前）
    document.querySelectorAll('[data-cy-tooltip]').forEach(el => {
      if (document.body.contains(el)) {
        document.body.removeChild(el)
      }
    })

    // 销毁旧实例
    if (cyRef.current) {
      // 移除所有事件监听器
      cyRef.current.off('mouseover', 'edge')
      cyRef.current.off('mouseout', 'edge')
      cyRef.current.off('tap', 'node')
      cyRef.current.destroy()
      cyRef.current = null
    }

    // Phase 3: 应用过滤器
    // 1. 过滤边（BA阈值）
    const filteredEdges = data.edges.filter((edge: any) => {
      const ba = edge.binding_affinity || 0
      return ba >= minBA
    })

    // 2. 计算节点度数（连接数）
    const nodeDegrees = new Map<string, number>()
    filteredEdges.forEach((edge: any) => {
      nodeDegrees.set(edge.source, (nodeDegrees.get(edge.source) || 0) + 1)
      nodeDegrees.set(edge.target, (nodeDegrees.get(edge.target) || 0) + 1)
    })

    // 3. 过滤节点（类型 + 度数）
    const filteredNodes = data.nodes.filter((node: any) => {
      // 节点类型过滤
      if (nodeTypeFilter !== 'all' && node.type !== nodeTypeFilter) {
        return false
      }
      // 度数过滤
      const degree = nodeDegrees.get(node.id) || 0
      return degree >= minDegree
    })

    // 4. 获取保留节点的ID集合
    const nodeIds = new Set(filteredNodes.map((n: any) => n.id))

    // 5. 只保留两端节点都存在的边
    const finalEdges = filteredEdges.filter((edge: any) =>
      nodeIds.has(edge.source) && nodeIds.has(edge.target)
    )

    const elements = [
      ...filteredNodes.map((node: any) => {
        // Calculate conservation category from conservation_label if available
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
      ...finalEdges.map((edge: any) => ({
        data: {
          source: edge.source,
          target: edge.target,
          ba: edge.binding_affinity || 0,
          regulation_id: edge.regulation_id
        }
      }))
    ]

    // 动态计算BA值范围（基于过滤后的边）
    const baValues = finalEdges
      .map((e: any) => e.binding_affinity)
      .filter((ba: number) => ba != null && ba > 0)

    let minBARange = baValues.length > 0 ? Math.min(...baValues) : 0
    let maxBARange = baValues.length > 0 ? Math.max(...baValues) : 100

    // 处理边界情况：当所有BA值相等时，避免mapData退化
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
            'width': `mapData(ba, ${minBARange}, ${maxBARange}, 1, 5)`,  // 动态BA范围映射到宽度1-5
            'line-color': `mapData(ba, ${minBARange}, ${maxBARange}, #d9d9d9, #ff4d4f)`,  // 灰色到红色渐变
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
        // Conservation-based node colors (Tol Bright palette - color-blind safe)
        {
          selector: 'node[conservation="high"]',
          style: {
            'background-color': CONSERVATION_COLORS.high  // #228833 Green
          }
        },
        {
          selector: 'node[conservation="medium"]',
          style: {
            'background-color': CONSERVATION_COLORS.medium  // #CCBB44 Yellow
          }
        },
        {
          selector: 'node[conservation="low"]',
          style: {
            'background-color': CONSERVATION_COLORS.low  // #EE6677 Red
          }
        },
        {
          selector: 'node[conservation="unknown"]',
          style: {
            'background-color': CONSERVATION_COLORS.unknown  // #BBBBBB Gray
          }
        }
      ],
      layout: getLayoutConfig(currentLayout)
    })

    // 批量导出: 通知父组件 cyRef 已准备好
    onRefReady?.(cyRef as React.RefObject<Core>, true)

    // 添加边的tooltip（使用正确的 Cytoscape 事件类型避免内存泄漏）
    cyRef.current.on('mouseover', 'edge', (evt: cytoscape.EventObject) => {
      const edge = evt.target
      const ba = edge.data('ba')
      if (ba === undefined) return

      // 创建tooltip（使用安全的 DOM 方法避免 XSS）
      const tooltipDiv = document.createElement('div')
      tooltipDiv.setAttribute('data-cy-tooltip', 'true')  // 添加标识用于清理
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
      // 使用安全的 DOM 方法创建内容
      const labelSpan = document.createElement('strong')
      labelSpan.textContent = t('edge.bindingAffinityLabel')
      const valueSpan = document.createElement('span')
      valueSpan.textContent = ba.toFixed(2)
      tooltipDiv.appendChild(labelSpan)
      tooltipDiv.appendChild(valueSpan)
      document.body.appendChild(tooltipDiv)

      // 初始位置设置（使用原始事件的坐标）
      const origEvent = evt.originalEvent as MouseEvent | undefined
      if (origEvent) {
        tooltipDiv.style.left = `${origEvent.clientX + 10}px`
        tooltipDiv.style.top = `${origEvent.clientY + 10}px`
      }

      // 更新tooltip位置（使用 Cytoscape 事件类型）
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
      edge.data('tooltipDiv', tooltipDiv)
      edge.data('updatePosition', updatePosition)
    })

    cyRef.current.on('mouseout', 'edge', (evt: cytoscape.EventObject) => {
      const edge = evt.target
      const tooltipDiv = edge.data('tooltipDiv') as HTMLDivElement | undefined
      const updatePosition = edge.data('updatePosition') as ((e: cytoscape.EventObject) => void) | undefined

      if (tooltipDiv && document.body.contains(tooltipDiv)) {
        document.body.removeChild(tooltipDiv)
      }
      if (updatePosition) {
        edge.off('mousemove', updatePosition)
      }
      edge.removeData('tooltipDiv')
      edge.removeData('updatePosition')
    })

    // 添加节点点击事件
    cyRef.current.on('tap', 'node', (evt) => {
      const node = evt.target
      const geneId = node.data('gene_id')
      if (geneId) {
        setSelectedGeneId(geneId)
        setDetailDrawerOpen(true)
      }
    })

    // Cleanup函数：在effect重新运行或组件卸载时执行
    return () => {
      // 清理所有tooltip
      document.querySelectorAll('[data-cy-tooltip]').forEach(el => {
        if (document.body.contains(el)) {
          document.body.removeChild(el)
        }
      })

      // 移除事件监听器
      if (cyRef.current) {
        cyRef.current.off('mouseover', 'edge')
        cyRef.current.off('mouseout', 'edge')
        cyRef.current.off('tap', 'node')
      }
    }
  }, [data, error, loading, minBA, nodeTypeFilter, minDegree, currentLayout])

  // 独立的搜索高亮 Effect（不触发图表重建）
  useEffect(() => {
    if (!cyRef.current) return

    // 清除所有高亮
    cyRef.current.nodes().removeClass('highlighted')

    // 如果有搜索词，应用高亮
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

      // 如果只有一个结果，自动定位
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
  }, [searchTerm])

  // 搜索功能（简化版，高亮逻辑由 useEffect 统一处理）
  const handleSearch = (value: string) => {
    setSearchTerm(value)
  }

  const highlightNode = (nodeId: string) => {
    if (!cyRef.current) return

    const node = cyRef.current.$id(nodeId)

    // 清除其他高亮
    cyRef.current.nodes().removeClass('highlighted')

    // 高亮选中节点
    node.addClass('highlighted')

    // 定位到节点
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

      // Cytoscape的png()方法返回 Blob（当 output: 'blob' 时）
      const png = cyRef.current.png({
        output: 'blob',
        bg: 'white',
        full: true,
        scale: 2  // 2x分辨率
      }) as unknown as Blob

      const url = URL.createObjectURL(png)
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
    // 使用setTimeout避免大图时阻塞UI
    message.loading({ content: t('export.generating', { species: speciesName, format: 'CSV' }), key: messageKey, duration: 0 })
    setTimeout(() => {
      try {
        // 导出节点（使用 escapeCSV 防止注入）
        const nodeHeaders = ['ID', 'Label', 'Type', 'Gene ID', 'Core ID']
        const nodeRows = data.nodes.map((n: any) =>
          [escapeCSV(n.id), escapeCSV(n.label), escapeCSV(n.type), escapeCSV(n.gene_id), escapeCSV(n.core_id)].join(',')
        )
        const nodeCSV = [nodeHeaders.join(','), ...nodeRows].join('\n')

        // 导出边（使用 escapeCSV 防止注入）
        const edgeHeaders = ['Source', 'Target', 'Binding Affinity', 'Regulation ID']
        const edgeRows = data.edges.map((e: any) =>
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
    // 使用setTimeout避免大图时阻塞UI
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
            {/* NEW: Compare Across Species button */}
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

        {/* Phase 3: 高级过滤器 */}
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
                <Space direction="vertical" style={{ width: '100%' }} size="small">
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
          {/* Conservation legend - positioned top-right */}
          <ConservationLegend position="top-right" compact />
        </div>
      </div>

      {/* 基因详情抽屉 */}
      <Drawer
        title={t('drawer.title')}
        placement="right"
        onClose={() => setDetailDrawerOpen(false)}
        open={detailDrawerOpen}
        width={400}
      >
        {detailLoading ? (
          <LoadingState />
        ) : geneDetail ? (
          <Descriptions column={1} bordered size="small">
            <Descriptions.Item label={t('drawer.geneName')}>{geneDetail.gene_name}</Descriptions.Item>
            <Descriptions.Item label={t('drawer.ensemblId')}>{geneDetail.gene_ensembl_id}</Descriptions.Item>
            <Descriptions.Item label={t('drawer.ensemblLink')}>
              {geneDetail.gene_ensembl_id?.startsWith('ENSG') ? (
                <a
                  href={`https://www.ensembl.org/Homo_sapiens/Gene/Summary?g=${geneDetail.gene_ensembl_id.replace(/_(marmoset|macaque|chimpanzee|chimp)$/i, '')}`}
                  target="_blank"
                  rel="noopener noreferrer"
                  style={{ color: '#1890ff', textDecoration: 'underline' }}
                >
                  {t('drawer.viewInEnsembl')}
                </a>
              ) : (
                <span style={{ color: '#999' }}>{t('drawer.ensemblLinkNA')}</span>
              )}
            </Descriptions.Item>
            <Descriptions.Item label={t('drawer.fantomLink')}>
              <a
                href={`https://fantom.gsc.riken.jp/cat/v1/#/genes/${geneDetail.gene_ensembl_id?.replace(/_(marmoset|macaque|chimpanzee|chimp)$/i, '')}`}
                target="_blank"
                rel="noopener noreferrer"
                style={{ color: '#1890ff', textDecoration: 'underline' }}
              >
                {t('drawer.viewInFantom')}
              </a>
            </Descriptions.Item>
            <Descriptions.Item label={t('drawer.geneType')}>
              <Tag color={geneDetail.gene_type === 'lncRNA' ? 'blue' : 'green'}>
                {geneDetail.gene_type}
              </Tag>
            </Descriptions.Item>
            <Descriptions.Item label={t('drawer.speciesLabel')}>
              <Tag color="orange" style={{ fontSize: 13, padding: '2px 8px' }}>
                {geneDetail.species_name}
              </Tag>
              <span style={{ marginLeft: 8, fontSize: 12, color: '#666' }}>
                (ID: {geneDetail.species_id})
              </span>
            </Descriptions.Item>
            <Descriptions.Item label={t('drawer.conservationLabel')}>
              <Tag
                color={geneDetail.conservation_count === 4 ? 'green' : geneDetail.conservation_count === 1 ? 'red' : 'blue'}
                style={{ fontSize: 14, padding: '4px 12px', fontWeight: 'bold', fontFamily: 'monospace' }}
              >
                {geneDetail.conservation_label}
              </Tag>
              <span style={{ marginLeft: 8, fontSize: 12, color: '#666' }}>
                {t('drawer.conservationCount', { count: geneDetail.conservation_count })}
              </span>
              <div style={{ marginTop: 4, fontSize: 11, color: '#999' }}>
                {geneDetail.conservation_label[0] === '1' && t('species.human') + ' '}
                {geneDetail.conservation_label[1] === '1' && t('species.chimpanzee') + ' '}
                {geneDetail.conservation_label[2] === '1' && t('species.macaque') + ' '}
                {geneDetail.conservation_label[3] === '1' && t('species.marmoset')}
              </div>
            </Descriptions.Item>
            <Descriptions.Item label={t('drawer.chromosome')}>{geneDetail.chromosome || 'N/A'}</Descriptions.Item>
            <Descriptions.Item label={t('drawer.startPosition')}>{geneDetail.gene_start?.toLocaleString() || 'N/A'}</Descriptions.Item>
            <Descriptions.Item label={t('drawer.endPosition')}>{geneDetail.gene_end?.toLocaleString() || 'N/A'}</Descriptions.Item>
            <Descriptions.Item label={t('drawer.strand')}>{geneDetail.strand || 'N/A'}</Descriptions.Item>
            <Descriptions.Item label={t('drawer.coreId')}>{geneDetail.core_id}</Descriptions.Item>
            <Descriptions.Item label={t('drawer.asSource')}>
              {geneDetail.connections?.as_source || 0}
            </Descriptions.Item>
            <Descriptions.Item label={t('drawer.asTarget')}>
              {geneDetail.connections?.as_target || 0}
            </Descriptions.Item>
            <Descriptions.Item label={t('drawer.totalRegulations')}>
              {geneDetail.connections?.total || 0}
            </Descriptions.Item>
            <Descriptions.Item label={t('drawer.totalBA')}>
              {geneDetail.connections?.total_ba?.toFixed(2) || 0}
            </Descriptions.Item>
          </Descriptions>
        ) : (
          <div>{t('drawer.noData')}</div>
        )}
      </Drawer>

      {/* NEW: Cross-species comparison drawer */}
      <Drawer
        title={t('comparison.title')}
        placement="right"
        onClose={() => {
          setComparisonDrawerOpen(false)
          setSelectedLncrnaForComparison(null)
        }}
        open={comparisonDrawerOpen}
        width={800}
      >
        {comparisonLoading ? (
          <LoadingState />
        ) : comparisonError ? (
          <ErrorState error={comparisonError} />
        ) : comparisonData ? (
          <div>
            {/* Summary Information */}
            <Descriptions column={1} bordered size="small" style={{ marginBottom: 16 }}>
              <Descriptions.Item label={t('comparison.lncrnaLabel')}>
                {selectedLncrnaForComparison?.geneName}
              </Descriptions.Item>
              <Descriptions.Item label={t('comparison.coreIdLabel')}>
                {comparisonData.lncrna_core_id}
              </Descriptions.Item>
              <Descriptions.Item label={t('comparison.conservedTargetsLabel')}>
                <Tag color="blue" style={{ fontSize: 14, padding: '4px 12px' }}>
                  {comparisonData.conserved_target_count}
                </Tag>
                <span style={{ marginLeft: 8, color: '#666' }}>
                  {t('comparison.conservedCount', {
                    count: comparisonData.conserved_target_count,
                    speciesCount: Object.keys(comparisonData.species_networks).length
                  })}
                </span>
              </Descriptions.Item>
            </Descriptions>

            {/* Species-wise comparison tabs */}
            <Tabs
              items={Object.entries(comparisonData.species_networks).map(([speciesIdStr, speciesData]) => {
                const sid = parseInt(speciesIdStr)
                const speciesKey = SPECIES_KEYS[sid] || 'unknown'
                const speciesName = t(`species.${speciesKey}`, { id: sid })

                // Build conserved targets set for highlighting
                const conservedSet = new Set(comparisonData.conserved_targets)

                return {
                  key: speciesIdStr,
                  label: (
                    <span>
                      {speciesName}
                      <Tag color="blue" style={{ marginLeft: 8 }}>
                        {t('comparison.targetCount', { count: speciesData.target_count })}
                      </Tag>
                    </span>
                  ),
                  children: (
                    <div>
                      {speciesData.truncated && (
                        <Alert
                          message={t('comparison.truncatedWarning', {
                            count: speciesData.target_count,
                            total: speciesData.total_target_count
                          })}
                          type="info"
                          showIcon
                          style={{ marginBottom: 12 }}
                        />
                      )}
                      <Table
                        dataSource={speciesData.targets}
                        rowKey={(record, index) => `${record.target_gene_id}-${record.target_core_id}-${index}`}
                        size="small"
                        pagination={{ pageSize: 20, showSizeChanger: true }}
                        columns={[
                          {
                            title: t('comparison.targetGene'),
                            dataIndex: 'target_name',
                            key: 'target_name',
                            render: (name) => name || '-'
                          },
                          {
                            title: t('comparison.coreId'),
                            dataIndex: 'target_core_id',
                            key: 'target_core_id'
                          },
                          {
                            title: t('comparison.bindingAffinity'),
                            dataIndex: 'binding_affinity',
                            key: 'binding_affinity',
                            render: (ba) => ba?.toFixed(2) || '-',
                            sorter: (a, b) => (a.binding_affinity || 0) - (b.binding_affinity || 0)
                          },
                          {
                            title: t('comparison.conserved'),
                            dataIndex: 'target_core_id',
                            key: 'conserved',
                            render: (coreId) => {
                              const isConserved = conservedSet.has(coreId)
                              if (isConserved) {
                                // Count how many species this target appears in
                                const count = Object.values(comparisonData.species_networks).filter(
                                  (sn) => sn.targets.some((t) => t.target_core_id === coreId)
                                ).length
                                return (
                                  <Tag color="green">
                                    {t('comparison.conservedIn', { count })}
                                  </Tag>
                                )
                              }
                              return <span style={{ color: '#999' }}>-</span>
                            },
                            filters: [
                              { text: t('comparison.conserved'), value: 'conserved' },
                              { text: t('comparison.notConserved'), value: 'not_conserved' }
                            ],
                            onFilter: (value, record) => {
                              const isConserved = conservedSet.has(record.target_core_id)
                              return value === 'conserved' ? isConserved : !isConserved
                            }
                          }
                        ]}
                      />
                    </div>
                  )
                }
              })}
            />
          </div>
        ) : (
          <div>{t('comparison.noDataForSpecies')}</div>
        )}
      </Drawer>
    </>
  )
})

NetworkCard.displayName = 'NetworkCard'

export default function Network() {
  const { t } = useTranslation('network')
  const [speciesIds, setSpeciesIds] = useState<number[]>([1])
  const [traitId, setTraitId] = useState<number>()
  const [ontologyId, setOntologyId] = useState<number>()
  const [queryTrigger, setQueryTrigger] = useState(0)

  // 本地化物种选项
  const speciesOptions = useMemo(() => [
    { label: t('species.human'), value: 1 },
    { label: t('species.chimpanzee'), value: 2 },
    { label: t('species.macaque'), value: 3 },
    { label: t('species.marmoset'), value: 4 },
  ], [t])

  // 获取物种名称的辅助函数
  const getSpeciesName = (speciesId: number) => {
    const key = SPECIES_KEYS[speciesId]
    return key ? t(`species.${key}`) : t('species.unknown', { id: speciesId })
  }

  // 批量导出: 收集所有 NetworkCard 的 cyRef 和数据
  const networkCardsRef = useRef<Map<number, {
    cyRef: React.RefObject<Core>
    data: any
    speciesName: string
    isReady: boolean
  }>>(new Map())

  // 获取有网络数据的组合
  const { data: availableCombinations } = useQuery({
    queryKey: ['available-combinations'],
    queryFn: async () => {
      const res = await networkApi.getAvailableCombinations()
      return res.data.combinations
    }
  })

  // 获取疾病选项列表（轻量级 API）
  const {
    data: diseaseOptions,
    isLoading: diseaseOptionsLoading,
    isError: diseaseOptionsError,
    refetch: refetchDiseaseOptions
  } = useQuery({
    queryKey: ['disease-options'],
    queryFn: diseasesApi.getOptions,
    staleTime: 10 * 60 * 1000, // 10分钟缓存，选项不常变化
  })

  // 根据选中的物种和有数据的组合过滤疾病和Ontology
  // 显示至少一个选中物种有数据的组合
  const availableForSelectedSpecies = availableCombinations?.filter((c: any) =>
    speciesIds.some(speciesId => c.species_id === speciesId)
  )

  const availableTraitIds = new Set((availableForSelectedSpecies ?? []).map((c: any) => c.trait_id))

  // 后端已去重，直接过滤可用的疾病即可（O(n) 复杂度）
  const traits = useMemo(() => {
    if (!diseaseOptions?.traits) return []
    return diseaseOptions.traits.filter(t => availableTraitIds.has(t.trait_id))
  }, [diseaseOptions?.traits, availableTraitIds])

  // Ontology 仍然需要从完整数据获取，因为需要 ontology_name
  // 这里暂时保持从 availableCombinations 推断
  const ontologies = useMemo(() => {
    if (!availableForSelectedSpecies || !traitId) return []
    const ontologyMap = new Map<number, string>()

    availableForSelectedSpecies
      .filter((c: any) => c.trait_id === traitId)
      .forEach((c: any) => {
        if (!ontologyMap.has(c.ontology_id)) {
          ontologyMap.set(c.ontology_id, c.ontology_name || `Ontology ${c.ontology_id}`)
        }
      })

    return Array.from(ontologyMap.entries()).map(([id, name]) => ({
      ontology_id: id,
      ontology_name: name
    }))
  }, [availableForSelectedSpecies, traitId])

  // 使用 useQueries 并行查询多个物种
  const networkQueries = useQueries({
    queries: speciesIds.map(speciesId => ({
      queryKey: ['network', speciesId, traitId, ontologyId, queryTrigger],
      queryFn: async () => {
        if (!traitId || !ontologyId) return null
        const res = await networkApi.getDiseaseNetwork({
          species_id: speciesId,
          trait_id: traitId,
          ontology_id: ontologyId,
          min_ba: 0
        })
        return res.data
      },
      enabled: queryTrigger > 0 && !!traitId && !!ontologyId,
      staleTime: 0  // 禁用缓存，每次查询都获取最新数据
    }))
  })

  const handleQuery = () => {
    if (!traitId || !ontologyId) {
      message.warning(t('query.selectDiseaseOntology'))
      return
    }
    if (speciesIds.length === 0) {
      message.warning(t('species.selectAtLeast1'))
      return
    }
    // 递增 trigger 强制刷新
    setQueryTrigger(prev => prev + 1)
  }

  const handleSpeciesChange = (values: number[]) => {
    if (values.length > 4) {
      message.warning(t('species.max4Warning'))
      return
    }
    setSpeciesIds(values)
    // 物种变化时，清空已选的疾病和Ontology，因为可用选项会变化
    setTraitId(undefined)
    setOntologyId(undefined)
    // 清理 networkCardsRef 中不再选中的物种数据
    const newSpeciesSet = new Set(values)
    Array.from(networkCardsRef.current.keys()).forEach(id => {
      if (!newSpeciesSet.has(id)) {
        networkCardsRef.current.delete(id)
      }
    })
    // 重置queryTrigger，隐藏旧的网络结果
    setQueryTrigger(0)
  }

  // 批量导出: 生成 CSV 内容（使用 escapeCSV 防止注入）
  const generateCSV = (data: any) => {
    const nodeHeaders = ['ID', 'Label', 'Type', 'Gene ID', 'Core ID']
    const nodeRows = data.nodes.map((n: any) =>
      [escapeCSV(n.id), escapeCSV(n.label), escapeCSV(n.type), escapeCSV(n.gene_id), escapeCSV(n.core_id)].join(',')
    )
    const nodeCSV = [nodeHeaders.join(','), ...nodeRows].join('\n')

    const edgeHeaders = ['Source', 'Target', 'Binding Affinity', 'Regulation ID']
    const edgeRows = data.edges.map((e: any) =>
      [escapeCSV(e.source), escapeCSV(e.target), escapeCSV(e.binding_affinity), escapeCSV(e.regulation_id)].join(',')
    )
    const edgeCSV = [edgeHeaders.join(','), ...edgeRows].join('\n')

    return `Nodes:\n${nodeCSV}\n\nEdges:\n${edgeCSV}`
  }

  // 批量导出: 主函数
  const handleBatchExport = () => {
    // 校验所有物种是否已加载完成
    const notReady = speciesIds.filter(id => {
      const card = networkCardsRef.current.get(id)
      return !card || !card.isReady
    })

    if (notReady.length > 0) {
      const notReadyNames = notReady.map(id => getSpeciesName(id)).join(', ')
      message.warning({
        content: t('batchExport.notReady', { count: notReady.length, names: notReadyNames }),
        duration: 4
      })
      return
    }

    // 获取疾病和 Ontology 名称，兜底使用 ID
    const traitName = traits?.find((t: any) => t.trait_id === traitId)?.trait_name || `trait-${traitId || 'unknown'}`
    const ontologyName = ontologies?.find((o: any) => o.ontology_id === ontologyId)?.ontology_name || `ontology-${ontologyId || 'unknown'}`

    let selectedFormats: string[] = ['png', 'csv']

    Modal.confirm({
      title: t('batchExport.title'),
      width: 500,
      content: (
        <div>
          <p style={{ marginBottom: 16 }}>
            {t('batchExport.speciesCount', { count: speciesIds.length })}
          </p>
          <p style={{ fontSize: 12, color: '#666', marginBottom: 12 }}>
            {t('batchExport.diseaseLabel')}: {traitName}<br />
            {t('batchExport.ontologyLabel')}: {ontologyName}
          </p>
          <div style={{ marginBottom: 12 }}>
            <div style={{ marginBottom: 8, fontWeight: 500 }}>{t('batchExport.selectFormats')}:</div>
            <Checkbox.Group
              defaultValue={['png', 'csv']}
              onChange={(values) => {
                selectedFormats = values as string[]
              }}
            >
              <Space direction="vertical">
                <Checkbox value="png">{t('batchExport.pngFormat')}</Checkbox>
                <Checkbox value="csv">{t('batchExport.csvFormat')}</Checkbox>
                <Checkbox value="json">{t('batchExport.jsonFormat')}</Checkbox>
              </Space>
            </Checkbox.Group>
          </div>
          <p style={{ fontSize: 12, color: '#999' }}>
            {t('batchExport.zipNote')}
          </p>
        </div>
      ),
      okText: t('batchExport.startExport'),
      cancelText: t('batchExport.cancel'),
      onOk: async () => {
        // 校验是否选择了至少一个导出格式
        if (selectedFormats.length === 0) {
          message.warning(t('batchExport.selectAtLeastOne'))
          return Promise.reject() // 阻止 Modal 关闭
        }

        const messageKey = `batch-export-${Date.now()}`

        try {
          message.loading({
            content: t('batchExport.preparing'),
            key: messageKey,
            duration: 0
          })

          // 检查是否有可导出的卡片（只检查当前选中的物种）
          const readyCards = speciesIds
            .map(id => {
              const card = networkCardsRef.current.get(id)
              return card ? [id, card] as [number, typeof card] : null
            })
            .filter((entry): entry is [number, NonNullable<typeof entry>[1]] =>
              entry !== null &&
              entry[1].isReady &&
              !!entry[1].cyRef.current &&
              !!entry[1].data
            )

          if (readyCards.length === 0) {
            message.warning({
              content: t('batchExport.noExportable'),
              key: messageKey
            })
            return
          }

          const zip = new JSZip()

          // 生成时间戳（用于文件名）
          const timestamp = new Date().toISOString().replace(/[:.]/g, '-').slice(0, 19)
          const safeTraitName = traitName.replace(/[^a-zA-Z0-9]/g, '-').replace(/-+/g, '-').replace(/^-|-$/g, '')
          const safeOntologyName = ontologyName.replace(/[^a-zA-Z0-9]/g, '-').replace(/-+/g, '-').replace(/^-|-$/g, '')


          // ========== PNG 导出（合并图 + 单独图）==========
          if (selectedFormats.includes('png')) {
            message.loading({
              content: t('batchExport.generatingImages'),
              key: messageKey,
              duration: 0
            })

            // 在 try 外部定义，确保 catch 块可以访问（用于清理内存）
            let speciesImages: Array<{
              speciesId: number
              speciesName: string
              imageElement: HTMLImageElement
              objectURL: string
              blob: Blob
              width: number
              height: number
            }> = []

            try {
              // 1. 导出每个物种的 PNG（只渲染一次，使用 Object URL）

              for (const [speciesId, card] of readyCards) {
                const { cyRef, speciesName } = card
                if (!cyRef.current) continue


                // 只导出一次 blob（避免重复渲染）
                const blob = cyRef.current.png({
                  output: 'blob',
                  bg: 'white',
                  full: true,
                  scale: 2
                }) as unknown as Blob

                // 使用 Object URL 代替 base64（节省内存，提高性能）
                const objectURL = URL.createObjectURL(blob)

                // 创建临时 Image 对象获取尺寸
                const img = new Image()
                img.crossOrigin = 'Anonymous' // 在设置 src 之前设置跨域属性
                
                await new Promise((resolve, reject) => {
                  img.onload = () => {
                    resolve(null)
                  }
                  img.onerror = (error) => {
                    console.error(`❌ ${speciesName} Image 加载失败:`, error)
                    URL.revokeObjectURL(objectURL) // 清理失败的 URL
                    reject(error)
                  }
                  img.src = objectURL
                })

                speciesImages.push({
                  speciesId,
                  speciesName,
                  imageElement: img, // 直接保存 Image 元素（已加载完成）
                  objectURL, // 保存 URL 用于后续清理
                  blob,
                  width: img.width,
                  height: img.height
                })

                // 给 UI 线程喘息时间（避免主线程阻塞）
                await new Promise(resolve => setTimeout(resolve, 0))
              }

              if (speciesImages.length === 0) {
                throw new Error('没有可导出的图像')
              }

              // 2. 先将单张图片添加到 ZIP (防止后续合并图失败导致完全没有输出)
              for (const { speciesId, blob } of speciesImages) {
                const speciesEnName = SPECIES_EN_NAMES[speciesId] || `species-${speciesId}`
                const safeSpeciesName = speciesEnName.replace(/[^a-zA-Z0-9]/g, '-')
                const individualFileName = `${safeSpeciesName}-${safeTraitName}-${safeOntologyName}-${timestamp}.png`
                zip.file(individualFileName, blob)
              }

              // 3. 计算合并后的画布尺寸
              const cols = Math.ceil(Math.sqrt(speciesImages.length)) // 2x2 或 3x3
              const rows = Math.ceil(speciesImages.length / cols)
              const padding = 40 // 图像之间的间距
              const titleHeight = 60 // 每个图像上方的标题高度

              // 找到最大的图像尺寸
              const maxWidth = Math.max(...speciesImages.map(img => img.width))
              const maxHeight = Math.max(...speciesImages.map(img => img.height))

              const cellWidth = maxWidth
              const cellHeight = maxHeight + titleHeight
              const canvasWidth = cols * cellWidth + (cols + 1) * padding
              const canvasHeight = rows * cellHeight + (rows + 1) * padding


              // 4. 创建画布并绘制
              const canvas = document.createElement('canvas')
              canvas.width = canvasWidth
              canvas.height = canvasHeight
              const ctx = canvas.getContext('2d')
              
              if (!ctx) {
                throw new Error('Canvas context creation failed')
              }

              // 填充白色背景
              ctx.fillStyle = 'white'
              ctx.fillRect(0, 0, canvasWidth, canvasHeight)

              // 绘制每个物种的图像
              for (let i = 0; i < speciesImages.length; i++) {
                const { speciesName, imageElement, width, height } = speciesImages[i]
                const col = i % cols
                const row = Math.floor(i / cols)

                const x = padding + col * (cellWidth + padding)
                const y = padding + row * (cellHeight + padding)

                // 绘制标题
                ctx.fillStyle = '#000'
                ctx.font = 'bold 32px Arial'
                ctx.textAlign = 'center'
                ctx.fillText(speciesName, x + cellWidth / 2, y + 40)

                // 绘制图像（居中）- 直接使用已加载的 Image 元素
                const imgX = x + (cellWidth - width) / 2
                const imgY = y + titleHeight
                
                // imageElement.crossOrigin 已在加载前设置
                ctx.drawImage(imageElement, imgX, imgY, width, height)

              }

              // 5. 转换为 Blob 并添加到 ZIP（合并图）
              try {
                const mergedBlob = await new Promise<Blob>((resolve, reject) => {
                  canvas.toBlob((blob) => {
                    if (blob) resolve(blob)
                    else reject(new Error('Canvas toBlob failed'))
                  }, 'image/png')
                })

                const mergedFileName = `network-comparison-${safeTraitName}-${safeOntologyName}-${timestamp}.png`
                zip.file(mergedFileName, mergedBlob)
              } catch (mergeError) {
                console.error('⚠️ 合并图像生成失败 (可能是尺寸过大):', mergeError)
                message.warning(t('batchExport.mergeImageFailed'))
              }

              // 清理所有 Object URL，释放内存
              speciesImages.forEach(({ objectURL }) => {
                URL.revokeObjectURL(objectURL)
              })

            } catch (error) {
              console.error('❌ PNG 导出失败:', error)
              message.error(t('batchExport.pngFailed'))

              // 错误时也要清理 Object URL
              if (speciesImages && speciesImages.length > 0) {
                speciesImages.forEach(({ objectURL }) => {
                  URL.revokeObjectURL(objectURL)
                })
              }
            }
          }

          // ========== CSV 和 JSON 导出（每个物种单独文件）==========
          for (const [speciesId, card] of readyCards) {
            const { data, speciesName } = card
            const speciesEnName = SPECIES_EN_NAMES[speciesId] || `species-${speciesId}`
            const safeSpeciesName = speciesEnName.replace(/[^a-zA-Z0-9]/g, '-')
            const prefix = `${safeSpeciesName}-${safeTraitName}-${safeOntologyName}-${timestamp}`

            // 导出 CSV
            if (selectedFormats.includes('csv') && data) {
              try {
                const csv = generateCSV(data)
                zip.file(`${prefix}.csv`, csv)
              } catch (error) {
                console.error(`❌ ${speciesName} CSV 导出失败:`, error)
              }
            }

            // 导出 JSON
            if (selectedFormats.includes('json') && data) {
              try {
                const json = JSON.stringify(data, null, 2)
                zip.file(`${prefix}.json`, json)
              } catch (error) {
                console.error(`❌ ${speciesName} JSON 导出失败:`, error)
              }
            }
          }

          message.loading({
            content: t('batchExport.packing'),
            key: messageKey,
            duration: 0
          })

          const blob = await zip.generateAsync({ type: 'blob' })

          // 使用相同的时间戳作为 ZIP 文件名
          const zipFileName = `network-comparison-${timestamp}.zip`
          saveAs(blob, zipFileName)

          // 显式销毁 loading，然后显示成功消息
          message.destroy(messageKey)
          message.success({
            content: t('batchExport.success', { count: readyCards.length }),
            duration: 3
          })
        } catch (error) {
          console.error('批量导出失败:', error)
          // 显式销毁 loading，然后显示错误消息
          message.destroy(messageKey)
          message.error({
            content: t('batchExport.failed'),
            duration: 3
          })
        }
      }
    })
  }

  // 计算网格列数
  const gridColumns = speciesIds.length === 1 ? 1 : 2

  return (
    <div style={{ padding: 24 }}>
      <h1>{t('title')}</h1>
      <p style={{ color: '#666', marginBottom: 16 }}>
        {t('description')}
      </p>
      <Space style={{ marginBottom: 16 }} wrap>
        <span>{t('species.label')}:</span>
        <Select
          mode="multiple"
          value={speciesIds}
          onChange={handleSpeciesChange}
          style={{ minWidth: 200 }}
          maxTagCount={2}
          placeholder={t('species.placeholder')}
          options={speciesOptions}
        />
        <span>{t('disease.label')}:</span>
        <Select
          placeholder={t('disease.placeholder')}
          value={traitId}
          onChange={(v) => {
            setTraitId(v)
            setOntologyId(undefined)
            setQueryTrigger(0)
          }}
          style={{ width: 250 }}
          showSearch
          loading={diseaseOptionsLoading}
          disabled={diseaseOptionsLoading || diseaseOptionsError}
          filterOption={(input, option) => {
            const label = typeof option?.label === 'string' ? option.label : ''
            return label.toLowerCase().includes(input.toLowerCase())
          }}
          options={traits?.map((tr: any) => ({ label: tr.trait_name, value: tr.trait_id }))}
        />
        <span>{t('ontology.label')}:</span>
        <Select
          placeholder={t('ontology.placeholder')}
          value={ontologyId}
          onChange={(v) => {
            setOntologyId(v)
            setQueryTrigger(0)
          }}
          style={{ width: 250 }}
          disabled={!traitId}
          showSearch
          filterOption={(input, option) => {
            const label = typeof option?.label === 'string' ? option.label : ''
            return label.toLowerCase().includes(input.toLowerCase())
          }}
          options={ontologies?.map((o: any) => ({ label: o.ontology_name, value: o.ontology_id }))}
        />
        <Button type="primary" onClick={handleQuery} disabled={!traitId || !ontologyId}>
          {t('query.button')}
        </Button>
        {/* 批量导出按钮 */}
        {queryTrigger > 0 && speciesIds.length > 0 && (
          <Button
            icon={<DownloadOutlined />}
            onClick={handleBatchExport}
            disabled={networkQueries.some(q => q.isLoading || !q.data)}
          >
            {t('batchExport.buttonWithCount', { count: speciesIds.length })}
          </Button>
        )}
      </Space>

      {diseaseOptionsError && (
        <Alert
          type="warning"
          message={t('disease.loadError') || 'Failed to load disease options'}
          description={t('disease.loadErrorDesc') || 'Please try refreshing the page'}
          action={
            <Button size="small" onClick={() => refetchDiseaseOptions()}>
              {t('disease.retry') || 'Retry'}
            </Button>
          }
          style={{ marginBottom: 16 }}
          showIcon
          closable
        />
      )}

      {queryTrigger > 0 && (
        <div style={{
          display: 'grid',
          gridTemplateColumns: `repeat(${gridColumns}, 1fr)`,
          gap: 20,
          maxWidth: gridColumns === 1 ? 800 : 1600,
          margin: '0 auto'
        }}>
          {speciesIds.map((speciesId, index) => {
            const query = networkQueries[index]
            const speciesName = getSpeciesName(speciesId)

            return (
              <NetworkCard
                key={speciesId}
                speciesId={speciesId}
                speciesName={speciesName}
                data={query.data}
                loading={query.isLoading}
                error={query.error}
                onRefReady={(cyRef, isReady) => {
                  // 收集 cyRef 用于批量导出
                  networkCardsRef.current.set(speciesId, {
                    cyRef,
                    data: query.data,
                    speciesName,
                    isReady: isReady && !query.isLoading && !query.error && !!query.data
                  })
                }}
              />
            )
          })}
        </div>
      )}
    </div>
  )
}
