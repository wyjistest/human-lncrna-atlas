# Phase 3 功能方案：批量操作 + 报告导出

**日期**: 2025-11-27
**版本**: v1.0
**状态**: 待审核

> **现状说明**: 本文档为未来规划，不代表当前已实现或待办；现状请以 `docs/CURRENT_STATUS.md` 为准。

---

## 一、功能概述

| 功能模块 | 子功能 | 优先级 |
|---------|--------|--------|
| Regulations 批量操作 | 行选择 | P0 |
| | 批量导出选中行 | P0 |
| | 批量可视化（网络图） | P1 |
| Stats 导出 | 图表截图 (PNG/SVG) | P0 |
| | PDF 报告生成 | P1 |

---

## 二、Regulations 批量操作

### 2.1 行选择功能

**目标**: 支持用户在表格中选择多行数据进行批量操作。

#### 技术方案

Ant Design Table 原生支持 `rowSelection`：

```typescript
// src/pages/Regulations/index.tsx

const [selectedRowKeys, setSelectedRowKeys] = useState<React.Key[]>([])
const [selectedRows, setSelectedRows] = useState<RegulationListItem[]>([])

const rowSelection: TableProps<RegulationListItem>['rowSelection'] = {
  type: 'checkbox',
  selectedRowKeys,
  onChange: (keys, rows) => {
    setSelectedRowKeys(keys)
    setSelectedRows(rows)
  },
  // 跨页保持选择
  preserveSelectedRowKeys: true,
  // 全选时的提示
  selections: [
    Table.SELECTION_ALL,
    Table.SELECTION_INVERT,
    Table.SELECTION_NONE,
    {
      key: 'selectVisible',
      text: '选择当前页',
      onSelect: (changeableRowKeys) => {
        setSelectedRowKeys(changeableRowKeys)
      }
    }
  ],
  // 列头固定宽度
  columnWidth: 48,
}

<Table
  rowSelection={rowSelection}
  columns={columns}
  dataSource={data?.items}
  rowKey="regulation_id"
  // ...
/>
```

#### UI 设计

```
┌─────────────────────────────────────────────────────────────────┐
│ [已选择 15 条] [清空选择] [批量导出 ▼] [批量可视化]    [筛选...]│
├─────────────────────────────────────────────────────────────────┤
│ ☑ │ ID    │ lncRNA  │ Target  │ Species │ Chr  │ BA    │ ...   │
├───┼───────┼─────────┼─────────┼─────────┼──────┼───────┼───────┤
│ ☑ │ 1     │ CATG... │ BRCA1   │ 人类    │ chr17│ 65.5  │       │
│ ☐ │ 2     │ CATG... │ TP53    │ 人类    │ chr17│ 72.3  │       │
│ ☑ │ 3     │ CATG... │ EGFR    │ 黑猩猩  │ chr7 │ 58.1  │       │
└───┴───────┴─────────┴─────────┴─────────┴──────┴───────┴───────┘
                                        共 804,630 条 | 第 1/8047 页
```

#### 选择状态栏组件

```typescript
// src/pages/Regulations/components/SelectionToolbar.tsx

interface SelectionToolbarProps {
  selectedCount: number
  selectedRows: RegulationListItem[]
  onClear: () => void
  onExport: (format: 'csv' | 'xlsx') => void
  onVisualize: () => void
}

export function SelectionToolbar({
  selectedCount,
  selectedRows,
  onClear,
  onExport,
  onVisualize
}: SelectionToolbarProps) {
  if (selectedCount === 0) return null

  return (
    <Alert
      type="info"
      showIcon
      message={
        <Space>
          <span>已选择 <b>{selectedCount}</b> 条记录</span>
          <Button size="small" onClick={onClear}>清空选择</Button>
          <Dropdown menu={{
            items: [
              { key: 'csv', label: '导出 CSV', onClick: () => onExport('csv') },
              { key: 'xlsx', label: '导出 XLSX', onClick: () => onExport('xlsx') }
            ]
          }}>
            <Button size="small">批量导出 <DownOutlined /></Button>
          </Dropdown>
          <Button
            size="small"
            type="primary"
            onClick={onVisualize}
            disabled={selectedCount > 100}  // 限制可视化数量
          >
            批量可视化
          </Button>
          {selectedCount > 100 && (
            <Tooltip title="可视化最多支持 100 条数据">
              <InfoCircleOutlined />
            </Tooltip>
          )}
        </Space>
      }
      style={{ marginBottom: 16 }}
    />
  )
}
```

### 2.2 批量导出选中行

**目标**: 导出用户选中的数据行（无需分页获取）。

#### 技术方案

```typescript
// src/utils/export.ts 新增

export function exportSelectedRegulations(
  data: RegulationListItem[],
  format: 'csv' | 'xlsx'
): ExportResult {
  if (data.length === 0) {
    return { success: false, error: 'NO_DATA' }
  }

  if (format === 'csv') {
    return exportToCSV(data)
  } else {
    return exportToXLSX(data)
  }
}
```

#### 调用流程

```typescript
// src/pages/Regulations/index.tsx

const handleBatchExport = (format: 'csv' | 'xlsx') => {
  const result = exportSelectedRegulations(selectedRows, format)

  if (result.success) {
    message.success(`已导出 ${selectedRows.length} 条数据`)
    // 可选：导出后清空选择
    // setSelectedRowKeys([])
    // setSelectedRows([])
  } else {
    message.error('导出失败')
  }
}
```

### 2.3 批量可视化（网络图）

**目标**: 将选中的调控关系以网络图形式展示。

#### 技术方案

使用现有的 Cytoscape.js：

```typescript
// src/pages/Regulations/components/BatchVisualizationModal.tsx

import cytoscape from 'cytoscape'

interface BatchVisualizationModalProps {
  open: boolean
  onClose: () => void
  data: RegulationListItem[]
}

export function BatchVisualizationModal({ open, onClose, data }: BatchVisualizationModalProps) {
  const containerRef = useRef<HTMLDivElement>(null)
  const cyRef = useRef<cytoscape.Core | null>(null)

  useEffect(() => {
    if (!open || !containerRef.current || data.length === 0) return

    // 构建节点和边
    const nodes = new Map<string, { id: string; type: 'lncrna' | 'target'; label: string }>()
    const edges: { source: string; target: string; ba: number }[] = []

    data.forEach(reg => {
      const lncId = `lnc_${reg.lncrna_gene_name}`
      const targetId = `target_${reg.target_gene_name}`

      if (!nodes.has(lncId)) {
        nodes.set(lncId, { id: lncId, type: 'lncrna', label: reg.lncrna_gene_name })
      }
      if (!nodes.has(targetId)) {
        nodes.set(targetId, { id: targetId, type: 'target', label: reg.target_gene_name })
      }

      edges.push({
        source: lncId,
        target: targetId,
        ba: reg.binding_affinity
      })
    })

    // 创建 Cytoscape 实例
    cyRef.current = cytoscape({
      container: containerRef.current,
      elements: [
        ...Array.from(nodes.values()).map(n => ({
          data: { id: n.id, label: n.label, type: n.type }
        })),
        ...edges.map((e, i) => ({
          data: { id: `edge_${i}`, source: e.source, target: e.target, ba: e.ba }
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
            'text-margin-y': 5
          }
        },
        {
          selector: 'node[type="target"]',
          style: {
            'background-color': '#52c41a',
            'label': 'data(label)',
            'font-size': '10px',
            'text-valign': 'bottom',
            'text-margin-y': 5
          }
        },
        {
          selector: 'edge',
          style: {
            'width': 1,
            'line-color': '#ccc',
            'target-arrow-color': '#ccc',
            'target-arrow-shape': 'triangle',
            'curve-style': 'bezier'
          }
        }
      ],
      layout: {
        name: 'cose',  // 力导向布局
        nodeRepulsion: 8000,
        idealEdgeLength: 100
      }
    })

    return () => {
      cyRef.current?.destroy()
    }
  }, [open, data])

  // 导出网络图
  const handleExportImage = (format: 'png' | 'svg') => {
    if (!cyRef.current) return

    if (format === 'png') {
      const png = cyRef.current.png({ full: true, scale: 2 })
      const link = document.createElement('a')
      link.href = png
      link.download = `network-${Date.now()}.png`
      link.click()
    } else {
      const svg = cyRef.current.svg({ full: true })
      const blob = new Blob([svg], { type: 'image/svg+xml' })
      saveAs(blob, `network-${Date.now()}.svg`)
    }
  }

  return (
    <Modal
      title={`调控关系网络图（${data.length} 条）`}
      open={open}
      onCancel={onClose}
      width={900}
      footer={[
        <Button key="png" onClick={() => handleExportImage('png')}>
          导出 PNG
        </Button>,
        <Button key="svg" onClick={() => handleExportImage('svg')}>
          导出 SVG
        </Button>,
        <Button key="close" type="primary" onClick={onClose}>
          关闭
        </Button>
      ]}
    >
      <div style={{ marginBottom: 16 }}>
        <Space>
          <Badge color="#1890ff" text="lncRNA" />
          <Badge color="#52c41a" text="Target Gene" />
          <span style={{ marginLeft: 16, color: '#666' }}>
            节点数: {new Set(data.flatMap(d => [d.lncrna_gene_name, d.target_gene_name])).size}
          </span>
        </Space>
      </div>
      <div
        ref={containerRef}
        style={{ width: '100%', height: 500, border: '1px solid #d9d9d9', borderRadius: 4 }}
      />
    </Modal>
  )
}
```

#### 限制和优化

| 限制项 | 值 | 原因 |
|--------|-----|------|
| 最大可视化数量 | 100 条 | 防止浏览器卡顿 |
| 节点合并 | 相同 lncRNA/Target 合并 | 减少重复 |
| 布局算法 | CoSE (力导向) | 自动分布节点 |

---

## 三、Stats 导出功能

### 3.1 图表截图 (PNG/SVG)

**目标**: 用户可以单独导出每个图表为图片。

#### 技术方案 A：使用 ECharts 内置导出

ECharts 原生支持导出，无需额外库：

```typescript
// src/pages/Stats/components/ChartExportWrapper.tsx

import ReactECharts from 'echarts-for-react'
import type { EChartsInstance } from 'echarts-for-react'

interface ChartExportWrapperProps {
  option: ECOption
  style?: React.CSSProperties
  title: string  // 用于文件名
}

export function ChartExportWrapper({ option, style, title }: ChartExportWrapperProps) {
  const chartRef = useRef<ReactECharts>(null)

  const handleExport = (format: 'png' | 'svg') => {
    const instance = chartRef.current?.getEchartsInstance()
    if (!instance) return

    if (format === 'png') {
      const url = instance.getDataURL({
        type: 'png',
        pixelRatio: 2,  // 高清
        backgroundColor: '#fff'
      })
      const link = document.createElement('a')
      link.href = url
      link.download = `${title}-${Date.now()}.png`
      link.click()
    } else {
      // SVG 需要使用 svg renderer
      const url = instance.getDataURL({
        type: 'svg'
      })
      const link = document.createElement('a')
      link.href = url
      link.download = `${title}-${Date.now()}.svg`
      link.click()
    }
  }

  // 添加 toolbox 到 option
  const optionWithToolbox = {
    ...option,
    toolbox: {
      show: true,
      right: 20,
      feature: {
        saveAsImage: {
          type: 'png',
          name: title,
          pixelRatio: 2
        }
      }
    }
  }

  return (
    <div style={{ position: 'relative' }}>
      <ReactECharts
        ref={chartRef}
        option={optionWithToolbox}
        style={style}
        notMerge={true}
      />
      {/* 自定义导出按钮（可选） */}
      <Dropdown
        menu={{
          items: [
            { key: 'png', label: '导出 PNG', onClick: () => handleExport('png') },
            { key: 'svg', label: '导出 SVG', onClick: () => handleExport('svg') }
          ]
        }}
        placement="bottomRight"
      >
        <Button
          size="small"
          icon={<DownloadOutlined />}
          style={{ position: 'absolute', top: 8, right: 8 }}
        >
          导出
        </Button>
      </Dropdown>
    </div>
  )
}
```

#### 各图表适配

```typescript
// src/pages/Stats/components/SpeciesChart.tsx
export function SpeciesChart({ data }: SpeciesChartProps) {
  const option = { /* ... */ }

  return (
    <ChartExportWrapper
      option={option}
      style={{ height: 400 }}
      title="物种分布"
    />
  )
}

// src/pages/Stats/components/BAChart.tsx
export function BAChart({ data }: BAChartProps) {
  const option = { /* ... */ }

  return (
    <ChartExportWrapper
      option={option}
      style={{ height: 400 }}
      title="BA分布"
    />
  )
}
```

### 3.2 PDF 报告生成

**目标**: 生成包含所有统计信息和图表的 PDF 报告。

#### 依赖安装

```bash
npm install jspdf html2canvas
npm install -D @types/html2canvas
```

#### 技术方案

```typescript
// src/utils/pdf-export.ts

import jsPDF from 'jspdf'
import html2canvas from 'html2canvas'

interface PDFExportOptions {
  title?: string
  includeTimestamp?: boolean
}

export async function exportStatsToPDF(
  containerRef: HTMLElement,
  options: PDFExportOptions = {}
): Promise<void> {
  const { title = 'Human LncRNA Atlas 统计报告', includeTimestamp = true } = options

  // 创建 PDF（A4 尺寸）
  const pdf = new jsPDF({
    orientation: 'portrait',
    unit: 'mm',
    format: 'a4'
  })

  const pageWidth = pdf.internal.pageSize.getWidth()
  const pageHeight = pdf.internal.pageSize.getHeight()
  const margin = 15

  // 添加标题
  pdf.setFontSize(20)
  pdf.setFont('helvetica', 'bold')
  pdf.text(title, pageWidth / 2, 20, { align: 'center' })

  // 添加时间戳
  if (includeTimestamp) {
    pdf.setFontSize(10)
    pdf.setFont('helvetica', 'normal')
    pdf.text(
      `生成时间: ${new Date().toLocaleString('zh-CN')}`,
      pageWidth / 2,
      28,
      { align: 'center' }
    )
  }

  // 截图容器内容
  const canvas = await html2canvas(containerRef, {
    scale: 2,
    useCORS: true,
    backgroundColor: '#ffffff',
    logging: false
  })

  const imgData = canvas.toDataURL('image/png')
  const imgWidth = pageWidth - margin * 2
  const imgHeight = (canvas.height * imgWidth) / canvas.width

  // 分页处理
  let heightLeft = imgHeight
  let position = 35  // 标题下方开始
  let page = 1

  while (heightLeft > 0) {
    if (page > 1) {
      pdf.addPage()
      position = margin
    }

    const availableHeight = pageHeight - position - margin
    const sliceHeight = Math.min(availableHeight, heightLeft)

    pdf.addImage(
      imgData,
      'PNG',
      margin,
      position - (imgHeight - heightLeft),
      imgWidth,
      imgHeight
    )

    heightLeft -= availableHeight
    page++
  }

  // 添加页脚
  const totalPages = pdf.getNumberOfPages()
  for (let i = 1; i <= totalPages; i++) {
    pdf.setPage(i)
    pdf.setFontSize(8)
    pdf.setTextColor(128)
    pdf.text(
      `Human LncRNA Atlas | 第 ${i} / ${totalPages} 页`,
      pageWidth / 2,
      pageHeight - 10,
      { align: 'center' }
    )
  }

  // 下载
  pdf.save(`lncrna-atlas-report-${Date.now()}.pdf`)
}
```

#### Stats 页面集成

```typescript
// src/pages/Stats/index.tsx

import { exportStatsToPDF } from '@/utils/pdf-export'

export default function StatsPage() {
  const containerRef = useRef<HTMLDivElement>(null)
  const [exporting, setExporting] = useState(false)

  const handleExportPDF = async () => {
    if (!containerRef.current) return

    setExporting(true)
    try {
      await exportStatsToPDF(containerRef.current, {
        title: 'Human LncRNA Atlas 统计报告'
      })
      message.success('PDF 报告已生成')
    } catch (error) {
      message.error('PDF 生成失败')
      console.error(error)
    } finally {
      setExporting(false)
    }
  }

  return (
    <div>
      {/* 页面头部 */}
      <div style={{ display: 'flex', justifyContent: 'space-between', marginBottom: 24 }}>
        <Title level={2}>数据统计</Title>
        <Space>
          <Dropdown menu={{
            items: [
              { key: 'pdf', label: '导出 PDF 报告', onClick: handleExportPDF },
              { key: 'all-png', label: '导出所有图表 (PNG)', onClick: handleExportAllCharts }
            ]
          }}>
            <Button icon={<DownloadOutlined />} loading={exporting}>
              导出报告 <DownOutlined />
            </Button>
          </Dropdown>
        </Space>
      </div>

      {/* 报告内容区域 */}
      <div ref={containerRef}>
        {/* 统计卡片 */}
        <Row gutter={16}>...</Row>

        {/* 图表区域 */}
        <Row gutter={16}>...</Row>
      </div>
    </div>
  )
}
```

#### 批量导出所有图表

```typescript
// src/pages/Stats/index.tsx

const chartRefs = {
  species: useRef<ReactECharts>(null),
  ba: useRef<ReactECharts>(null),
  topLncrna: useRef<ReactECharts>(null)
}

const handleExportAllCharts = async () => {
  const charts = [
    { ref: chartRefs.species, name: '物种分布' },
    { ref: chartRefs.ba, name: 'BA分布' },
    { ref: chartRefs.topLncrna, name: 'Top-lncRNA' }
  ]

  for (const chart of charts) {
    const instance = chart.ref.current?.getEchartsInstance()
    if (!instance) continue

    const url = instance.getDataURL({
      type: 'png',
      pixelRatio: 2,
      backgroundColor: '#fff'
    })

    const link = document.createElement('a')
    link.href = url
    link.download = `${chart.name}-${Date.now()}.png`
    link.click()

    // 间隔下载，避免浏览器拦截
    await new Promise(r => setTimeout(r, 300))
  }

  message.success('所有图表已导出')
}
```

---

## 四、文件变更清单

### 4.1 新增文件

| 文件路径 | 说明 |
|---------|------|
| `src/pages/Regulations/components/SelectionToolbar.tsx` | 选择状态栏组件 |
| `src/pages/Regulations/components/BatchVisualizationModal.tsx` | 批量可视化弹窗 |
| `src/pages/Stats/components/ChartExportWrapper.tsx` | 图表导出包装器 |
| `src/utils/pdf-export.ts` | PDF 导出工具 |

### 4.2 修改文件

| 文件路径 | 变更内容 |
|---------|---------|
| `src/pages/Regulations/index.tsx` | 添加 rowSelection、选择状态栏、批量操作 |
| `src/pages/Stats/index.tsx` | 添加 PDF 导出按钮、chartRefs |
| `src/pages/Stats/components/SpeciesChart.tsx` | 使用 ChartExportWrapper |
| `src/pages/Stats/components/BAChart.tsx` | 使用 ChartExportWrapper |
| `src/pages/Stats/components/TopLncRNAChart.tsx` | 使用 ChartExportWrapper |
| `src/utils/export.ts` | 新增 exportSelectedRegulations |
| `src/config/constants.ts` | 新增 BATCH_LIMITS 配置 |

### 4.3 新增依赖

```bash
npm install jspdf html2canvas
npm install -D @types/html2canvas
```

---

## 五、配置常量

```typescript
// src/config/constants.ts 已更新

export const BATCH_LIMITS = {
  /** 批量导出选中行上限（与 EXPORT_LIMITS.MAX_FRONTEND 对齐） */
  MAX_EXPORT: EXPORT_LIMITS.MAX_FRONTEND,  // = 10000

  /** 批量可视化上限（防止浏览器卡顿） */
  MAX_VISUALIZATION: 100
} as const

export const PDF_CONFIG = {
  PAGE_SIZE: 'a4',
  MARGIN: 15,
  TITLE_FONT_SIZE: 20,
  SCALE: 2,
} as const
```

---

## 六、实现优先级

### P0（核心功能）- 预计 1 天

1. [ ] Regulations 行选择 (rowSelection + preserveSelectedRowKeys)
2. [ ] SelectionToolbar 组件
3. [ ] 批量导出选中行 (复用现有 CSV/XLSX 逻辑，上限 10000 条)
4. [ ] Stats 图表 PNG 导出 (ECharts getDataURL，仅 PNG)
5. [ ] 清理 .vite 预构建缓存

### P1（增强功能）- 预计 1-2 天

6. [ ] 批量可视化网络图 (Cytoscape，PNG 导出，限制 ≤100 条)
7. [ ] PDF 报告生成 (jsPDF + html2canvas 动态 import)
8. [ ] 批量导出所有图表
9. [ ] ChartExportWrapper 统一封装

### P2（优化项）- 预计 0.5 天

10. [ ] 导出进度提示
11. [ ] 网络图布局优化
12. [ ] PDF 分页优化
13. [ ] SVG 导出支持 (需动态注册 SVGRenderer + cytoscape-svg 插件)

---

## 七、技术约束与风险

### 7.1 已确认约束

| 约束 | 原因 | 处理方式 |
|------|------|---------|
| size-sensor 补丁 | React 19 严格模式 ResizeObserver bug | 已用 patch-package 固化 |
| 仅 CanvasRenderer | 当前按需导入未含 SVGRenderer | P0/P1 仅支持 PNG，P2 再考虑 SVG |
| Cytoscape SVG 需插件 | cy.svg() 依赖 cytoscape-svg | P0/P1 仅支持 PNG 导出 |
| 批量导出上限 | 与现有 EXPORT_LIMITS 对齐 | 选中行上限 10000 条 |
| 批量可视化上限 | 防止浏览器卡顿 | 限制 ≤100 条 |

### 7.2 动态导入要求

为减少首屏 bundle 体积，以下依赖必须动态导入：

```typescript
// PDF 导出 - 仅在用户点击时加载
const handleExportPDF = async () => {
  const [{ default: jsPDF }, { default: html2canvas }] = await Promise.all([
    import('jspdf'),
    import('html2canvas')
  ])
  // ...
}

// XLSX 导出 - 现有逻辑已是动态导入
const XLSX = await import('xlsx')
```

### 7.3 技术风险

| 风险 | 影响 | 缓解措施 |
|------|------|---------|
| html2canvas 对复杂图表支持有限 | PDF 图表模糊 | 改用 ECharts 原生导出后合成 |
| 大量选中行导出慢 | 用户体验差 | 限制上限 + 进度提示 |
| Cytoscape 大图渲染卡顿 | 浏览器卡死 | 限制节点数 100 |
| jsPDF 中文字体 | 中文乱码 | 使用 Base64 嵌入字体或英文报告 |
| .vite 缓存残留 | 旧 bundle 引发崩溃 | 实现前先清理 node_modules/.vite |

---

## 八、验收标准

### Regulations 批量操作

- [ ] 可以通过复选框选择单行/多行
- [ ] 支持全选、反选、选择当前页
- [ ] 跨页保持选择状态
- [ ] 选择后显示工具栏，显示选中数量
- [ ] 可批量导出为 CSV/XLSX
- [ ] 可批量可视化为网络图（≤100条）
- [ ] 网络图可导出为 PNG/SVG

### Stats 导出

- [ ] 每个图表有独立导出按钮
- [ ] 支持导出 PNG 格式
- [ ] 支持一键导出所有图表
- [ ] 支持导出 PDF 报告
- [ ] PDF 包含标题、时间戳、所有图表
- [ ] PDF 正确分页

---

**文档版本**: v1.0
**作者**: Claude Code
**审核状态**: 待用户确认
