/**
 * 批量可视化网络图弹窗
 * 使用 Cytoscape.js 展示 lncRNA-Target 调控关系网络
 *
 * v2.0: 支持多种布局算法切换
 */

import { useEffect, useMemo, useRef, useState } from 'react'
import { Modal, Button, Space, Badge, message, Spin, Alert, Select, Tooltip } from 'antd'
import { DownloadOutlined, QuestionCircleOutlined } from '@ant-design/icons'
import { useTranslation } from 'react-i18next'
import cytoscape from 'cytoscape'

// 类型定义 (cytoscape 3.x 类型在命名空间下)
type Core = cytoscape.Core
import type { components } from '@/types/api'
import { BATCH_LIMITS } from '@/config/constants'

type RegulationListItem = components['schemas']['RegulationListItem']

// ============ 布局配置 ============

type LayoutName = 'cose' | 'circle' | 'concentric' | 'breadthfirst' | 'grid'

// 本地 LayoutOptions 类型定义（cytoscape 3.x 不再导出此类型）
interface LayoutOptions {
  name: string
  animate?: boolean
  spacingFactor?: number
  nodeRepulsion?: () => number
  idealEdgeLength?: () => number
  concentric?: (node: cytoscape.NodeSingular) => number
  levelWidth?: () => number
  directed?: boolean
  condense?: boolean
}

// cytoscape 调用包装
const createCytoscape = cytoscape as unknown as (options: cytoscape.CytoscapeOptions) => Core

const LAYOUT_CONFIGS: Record<LayoutName, LayoutOptions> = {
  cose: {
    name: 'cose',
    nodeRepulsion: () => 8000,
    idealEdgeLength: () => 100,
    animate: false
  },
  circle: {
    name: 'circle',
    animate: false,
    spacingFactor: 1.5
  },
  concentric: {
    name: 'concentric',
    concentric: (node) => node.degree(),
    levelWidth: () => 2,
    animate: false,
    spacingFactor: 1.5
  },
  breadthfirst: {
    name: 'breadthfirst',
    directed: true,
    spacingFactor: 1.2,
    animate: false
  },
  grid: {
    name: 'grid',
    animate: false,
    condense: true,
    spacingFactor: 1.2
  }
}

interface BatchVisualizationModalProps {
  open: boolean
  onClose: () => void
  data: RegulationListItem[]
}

export function BatchVisualizationModal({ open, onClose, data }: BatchVisualizationModalProps) {
  const { t, i18n } = useTranslation('regulations')
  const containerRef = useRef<HTMLDivElement>(null)
  const cyRef = useRef<Core | null>(null)
  const [loading, setLoading] = useState(false)
  const [nodeCount, setNodeCount] = useState(0)
  const [edgeCount, setEdgeCount] = useState(0)
  const [layout, setLayout] = useState<LayoutName>('cose')
  const layoutRef = useRef<LayoutName>('cose')

  useEffect(() => {
    layoutRef.current = layout
  }, [layout])

  // 布局选项（本地化）
  const layoutOptions = [
    { value: 'cose' as LayoutName, label: t('visualization.layouts.cose'), description: t('visualization.layoutDesc.cose') },
    { value: 'circle' as LayoutName, label: t('visualization.layouts.circle'), description: t('visualization.layoutDesc.circle') },
    { value: 'concentric' as LayoutName, label: t('visualization.layouts.concentric'), description: t('visualization.layoutDesc.concentric') },
    { value: 'breadthfirst' as LayoutName, label: t('visualization.layouts.breadthfirst'), description: t('visualization.layoutDesc.breadthfirst') },
    { value: 'grid' as LayoutName, label: t('visualization.layouts.grid'), description: t('visualization.layoutDesc.grid') }
  ]

  // 限制数据量
  const isOverLimit = data.length > BATCH_LIMITS.MAX_VISUALIZATION
  const displayData = useMemo(() => (
    isOverLimit ? data.slice(0, BATCH_LIMITS.MAX_VISUALIZATION) : data
  ), [data, isOverLimit])

  useEffect(() => {
    if (!open || !containerRef.current || displayData.length === 0) return

    setLoading(true)

    // 构建节点和边
    const nodes = new Map<string, { id: string; type: 'lncrna' | 'target'; label: string }>()
    const edges: { id: string; source: string; target: string; ba: number | null }[] = []

    // 过滤掉缺少关键字段的数据
    const validData = displayData.filter(
      reg => reg.lncrna_gene_name && reg.target_gene_name
    )

    validData.forEach((reg, index) => {
      // 使用 species_name + gene_name 作为唯一 ID，避免跨物种同名合并
      const species = reg.species_name || 'Unknown'
      const lncName = reg.lncrna_gene_name!
      const targetName = reg.target_gene_name!
      const lncId = `lnc_${species}_${lncName}`
      const targetId = `target_${species}_${targetName}`

      if (!nodes.has(lncId)) {
        nodes.set(lncId, { id: lncId, type: 'lncrna', label: lncName })
      }
      if (!nodes.has(targetId)) {
        nodes.set(targetId, { id: targetId, type: 'target', label: targetName })
      }

      edges.push({
        id: `edge_${index}`,
        source: lncId,
        target: targetId,
        ba: typeof reg.binding_affinity === 'string'
          ? parseFloat(reg.binding_affinity) || null
          : reg.binding_affinity ?? null
      })
    })

    setNodeCount(nodes.size)
    setEdgeCount(edges.length)

    // 延迟创建以确保 DOM 准备好
    const timer = setTimeout(() => {
      if (!containerRef.current) return

      try {
        cyRef.current = createCytoscape({
          container: containerRef.current,
          elements: [
            ...Array.from(nodes.values()).map(n => ({
              data: { id: n.id, label: n.label, type: n.type }
            })),
            ...edges.map(e => ({
              data: { id: e.id, source: e.source, target: e.target, ba: e.ba }
            }))
          ],
          style: [
            {
              selector: 'node[type="lncrna"]',
              style: {
                'background-color': '#1890ff',
                'label': 'data(label)',
                'font-size': '10px',
                'text-valign': 'bottom',
                'text-margin-y': 5,
                'width': 30,
                'height': 30
              }
            },
            {
              selector: 'node[type="target"]',
              style: {
                'background-color': '#52c41a',
                'label': 'data(label)',
                'font-size': '10px',
                'text-valign': 'bottom',
                'text-margin-y': 5,
                'width': 25,
                'height': 25
              }
            },
            {
              selector: 'edge',
              style: {
                'width': 1,
                'line-color': '#ccc',
                'target-arrow-color': '#ccc',
                'target-arrow-shape': 'triangle',
                'curve-style': 'bezier',
                'opacity': 0.6
              }
            },
            {
              selector: 'node:selected',
              style: {
                'border-width': 3,
                'border-color': '#ff4d4f'
              }
            },
            {
              selector: 'edge:selected',
              style: {
                'line-color': '#ff4d4f',
                'target-arrow-color': '#ff4d4f',
                'width': 2
              }
            }
          ],
          layout: LAYOUT_CONFIGS[layoutRef.current],
          wheelSensitivity: 0.3
        })

        setLoading(false)
      } catch (error) {
        console.error('Failed to create Cytoscape instance:', error)
        message.error('网络图创建失败')
        setLoading(false)
      }
    }, 100)

    return () => {
      clearTimeout(timer)
      if (cyRef.current) {
        cyRef.current.destroy()
        cyRef.current = null
      }
    }
  }, [open, displayData])

  // 布局切换处理
  const handleLayoutChange = (newLayout: LayoutName) => {
    setLayout(newLayout)
    if (cyRef.current) {
      setLoading(true)
      cyRef.current.layout(LAYOUT_CONFIGS[newLayout]).run()
      // 布局完成后取消 loading
      setTimeout(() => {
        setLoading(false)
        cyRef.current?.fit()
      }, 100)
    }
  }

  // 导出为 PNG
  const handleExportPNG = () => {
    if (!cyRef.current) {
      message.warning(t('visualization.notReady'))
      return
    }

    try {
      const png = cyRef.current.png({
        full: true,
        scale: 2,
        bg: '#ffffff'
      })

      const link = document.createElement('a')
      link.href = png
      link.download = `regulation-network-${Date.now()}.png`
      link.click()

      message.success(t('visualization.exportSuccess'))
    } catch (error) {
      console.error('Export failed:', error)
      message.error(t('visualization.exportFailed'))
    }
  }

  // 重置视图
  const handleResetView = () => {
    if (cyRef.current) {
      cyRef.current.fit()
      cyRef.current.center()
    }
  }

  const modalTitle = t('visualization.titleWithCount', {
    count: displayData.length,
    extra: isOverLimit ? ` / ${data.length}` : ''
  })

  return (
    <Modal
      title={modalTitle}
      open={open}
      onCancel={onClose}
      width={900}
      styles={{ body: { padding: '16px 24px' } }}
      footer={[
        <Button key="reset" onClick={handleResetView}>
          {t('visualization.resetView')}
        </Button>,
        <Button key="png" icon={<DownloadOutlined />} onClick={handleExportPNG}>
          {t('visualization.exportPng')}
        </Button>,
        <Button key="close" type="primary" onClick={onClose}>
          {i18n.language?.startsWith('en') ? 'Close' : '关闭'}
        </Button>
      ]}
    >
      {isOverLimit && (
        <Alert
          type="warning"
          message={t('visualization.overLimit', { limit: BATCH_LIMITS.MAX_VISUALIZATION })}
          style={{ marginBottom: 12 }}
          showIcon
        />
      )}

      <div style={{ marginBottom: 12, display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
        <Space>
          <Badge color="#1890ff" text={`${t('visualization.lncrna')} (${Array.from(new Set(displayData.map(d => d.lncrna_gene_name))).length})`} />
          <Badge color="#52c41a" text={`${t('visualization.targetGene')} (${Array.from(new Set(displayData.map(d => d.target_gene_name))).length})`} />
          <span style={{ marginLeft: 16, color: '#666', fontSize: 12 }}>
            {t('visualization.nodes')}: {nodeCount} | {t('visualization.edges')}: {edgeCount}
          </span>
        </Space>
        <Space>
          <span style={{ color: '#666', fontSize: 12 }}>{t('visualization.layout')}:</span>
          <Select
            value={layout}
            onChange={handleLayoutChange}
            style={{ width: 120 }}
            size="small"
            options={layoutOptions.map(o => ({
              value: o.value,
              label: (
                <Tooltip title={o.description} placement="left">
                  <span>{o.label}</span>
                </Tooltip>
              )
            }))}
          />
          <Tooltip title={t('visualization.layoutHelp')}>
            <QuestionCircleOutlined style={{ color: '#999' }} />
          </Tooltip>
        </Space>
      </div>

      <Spin spinning={loading} tip={t('visualization.renderTip')}>
        <div
          ref={containerRef}
          style={{
            width: '100%',
            height: 500,
            border: '1px solid #d9d9d9',
            borderRadius: 4,
            backgroundColor: '#fafafa'
          }}
        />
      </Spin>

      <div style={{ marginTop: 8, fontSize: 12, color: '#999' }}>
        {t('visualization.usageTip')}
      </div>
    </Modal>
  )
}
