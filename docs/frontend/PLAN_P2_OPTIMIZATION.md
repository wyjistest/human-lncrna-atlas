# P2 优化方案：SVG 导出 + PDF 分页 + 布局算法

**日期**: 2025-11-28
**版本**: v1.0

---

## 一、现状分析

### 1.1 ECharts 图表导出

| 项目 | 当前状态 | 问题 |
|------|----------|------|
| 渲染器 | CanvasRenderer | 仅支持 PNG，无法导出矢量 SVG |
| toolbox | saveAsImage (PNG) | 放大后失真 |
| 文件 | `src/utils/echarts.ts` | 未注册 SVGRenderer |

### 1.2 PDF 分页

| 项目 | 当前状态 | 问题 |
|------|----------|------|
| 实现 | `pdf-export.ts` L81-115 | 每页重复添加完整图片 |
| 裁剪 | 无 | 图片溢出页面边界 |
| 表现 | 内容超出时重叠 | 用户体验差 |

**问题代码分析**：
```typescript
// 当前实现（有问题）
while (heightLeft > 0) {
  pdf.addImage(imgData, 'PNG', margin, position, imgWidth, imgHeight)  // ❌ 每页都添加完整图片
  heightLeft -= availableHeight
}
```

### 1.3 Cytoscape 网络图

| 项目 | 当前状态 | 问题 |
|------|----------|------|
| 布局 | 固定 `cose` | 无法切换，大图时不够清晰 |
| 导出 | `cy.png()` | 无 SVG 支持 |
| 插件 | 无 | 需要 `cytoscape-svg` |

---

## 二、方案设计

### 2.1 SVG 导出支持

#### 方案 A：ECharts 双渲染器（推荐）

**原理**：保留 CanvasRenderer 用于显示，导出时临时切换到 SVGRenderer

**实现步骤**：

1. **注册 SVGRenderer**
```typescript
// src/utils/echarts.ts
import { CanvasRenderer, SVGRenderer } from 'echarts/renderers'
echarts.use([..., CanvasRenderer, SVGRenderer])
```

2. **新增 SVG 导出函数**
```typescript
// src/utils/chart-export.ts
export function exportChartToSVG(
  chartInstance: EChartsInstance,
  filename: string
): boolean {
  const svgDataUrl = chartInstance.getDataURL({
    type: 'svg',
    pixelRatio: 1,
    backgroundColor: '#fff'
  })

  // 转换 data URL 为 SVG 文件
  const svgContent = atob(svgDataUrl.split(',')[1])
  const blob = new Blob([svgContent], { type: 'image/svg+xml' })
  saveAs(blob, `${filename}.svg`)
  return true
}
```

3. **更新 toolbox 配置**
```typescript
// src/utils/chart-export.ts
export function getChartToolbox(title: string) {
  return {
    show: true,
    right: 20,
    top: 10,
    feature: {
      saveAsImage: {
        type: 'png',
        name: title,
        pixelRatio: 2,
        title: 'PNG',
        backgroundColor: '#fff'
      },
      // 自定义 SVG 按钮
      mySvgExport: {
        show: true,
        title: 'SVG',
        icon: 'path://M...',  // SVG icon path
        onclick: function(ecModel, api) {
          // 触发自定义事件，由组件处理
          api.dispatchAction({ type: 'exportSVG' })
        }
      }
    }
  }
}
```

**优点**：
- 兼容现有 Canvas 显示
- 按需使用 SVG 导出
- 增量修改，风险低

**缺点**：
- Bundle 增加约 50KB (gzip)
- 需要修改每个图表组件

#### 方案 B：Cytoscape SVG 导出

**依赖**：`cytoscape-svg` 插件

```bash
npm install cytoscape-svg
```

**实现**：
```typescript
// BatchVisualizationModal.tsx
import cytoscapeSvg from 'cytoscape-svg'
cytoscape.use(cytoscapeSvg)

const handleExportSVG = () => {
  const svgContent = cyRef.current.svg({
    full: true,
    scale: 1,
    bg: '#ffffff'
  })
  const blob = new Blob([svgContent], { type: 'image/svg+xml' })
  saveAs(blob, `network-${Date.now()}.svg`)
}
```

---

### 2.2 PDF 分页优化

#### 方案：Canvas 分片 + 逐页渲染

**原理**：将长图裁剪成多个 canvas 片段，每页一个片段

**实现步骤**：

```typescript
// src/utils/pdf-export.ts

export async function exportToPDF(
  element: HTMLElement,
  options: PDFExportOptions = {}
): Promise<boolean> {
  const { title, includeTimestamp = true, filename } = options

  const [{ default: jsPDF }, { default: html2canvas }] = await Promise.all([
    import('jspdf'),
    import('html2canvas')
  ])

  // 1. 截图配置
  const canvas = await html2canvas(element, {
    scale: 2,
    useCORS: true,
    backgroundColor: '#ffffff'
  })

  // 2. 创建 PDF
  const pdf = new jsPDF({ orientation: 'portrait', unit: 'mm', format: 'a4' })
  const pageWidth = pdf.internal.pageSize.getWidth()
  const pageHeight = pdf.internal.pageSize.getHeight()
  const margin = 15

  // 3. 计算尺寸
  const contentWidth = pageWidth - margin * 2
  const headerHeight = includeTimestamp ? 35 : 25
  const footerHeight = 15
  const contentHeight = pageHeight - headerHeight - footerHeight

  // 图片缩放比例
  const imgScale = contentWidth / canvas.width
  const scaledImgHeight = canvas.height * imgScale

  // 4. 计算需要多少页
  const totalPages = Math.ceil(scaledImgHeight / contentHeight)

  // 5. 逐页渲染
  for (let page = 0; page < totalPages; page++) {
    if (page > 0) pdf.addPage()

    // 添加标题（仅首页）
    if (page === 0) {
      pdf.setFontSize(18)
      pdf.setFont('helvetica', 'bold')
      pdf.text(title || 'Report', pageWidth / 2, 20, { align: 'center' })

      if (includeTimestamp) {
        pdf.setFontSize(10)
        pdf.setTextColor(128)
        pdf.text(`Generated: ${new Date().toLocaleString()}`, pageWidth / 2, 28, { align: 'center' })
        pdf.setTextColor(0)
      }
    }

    // 6. 裁剪 canvas 片段
    const srcY = page * (contentHeight / imgScale)  // 源图片 Y 坐标
    const srcH = Math.min(contentHeight / imgScale, canvas.height - srcY)  // 源高度

    // 创建裁剪后的 canvas
    const sliceCanvas = document.createElement('canvas')
    sliceCanvas.width = canvas.width
    sliceCanvas.height = srcH
    const ctx = sliceCanvas.getContext('2d')!
    ctx.drawImage(
      canvas,
      0, srcY,           // 源起点
      canvas.width, srcH, // 源尺寸
      0, 0,              // 目标起点
      canvas.width, srcH  // 目标尺寸
    )

    // 7. 添加裁剪后的图片
    const sliceImgData = sliceCanvas.toDataURL('image/png')
    const destY = page === 0 ? headerHeight : margin
    const destH = srcH * imgScale

    pdf.addImage(sliceImgData, 'PNG', margin, destY, contentWidth, destH)

    // 8. 添加页脚
    pdf.setFontSize(8)
    pdf.setTextColor(128)
    pdf.text(
      `Human LncRNA Atlas | Page ${page + 1} / ${totalPages}`,
      pageWidth / 2,
      pageHeight - 10,
      { align: 'center' }
    )
  }

  pdf.save(`${filename}-${Date.now()}.pdf`)
  return true
}
```

**关键改进**：

| 改进点 | 原实现 | 新实现 |
|--------|--------|--------|
| 图片处理 | 重复添加完整图片 | Canvas 裁剪后分片 |
| 页面计算 | position 偏移 | 精确计算每页内容高度 |
| 内存占用 | 高（多份完整图片） | 低（按需裁剪） |
| 渲染质量 | 可能溢出 | 精确贴合页面 |

---

### 2.3 网络图布局算法选择

#### 方案：布局切换器组件

**支持的布局**：

| 布局 | 名称 | 适用场景 | 复杂度 |
|------|------|----------|--------|
| `cose` | 力导向 | 通用，展示聚类 | O(n²) |
| `circle` | 圆形 | 展示所有节点 | O(n) |
| `concentric` | 同心圆 | 按度数分层 | O(n) |
| `breadthfirst` | 树状 | 层级关系 | O(n+e) |
| `grid` | 网格 | 大量节点 | O(n) |
| `cola` | 约束力导向 | 高质量布局 | O(n²)（需插件） |

**实现**：

```typescript
// src/pages/Regulations/components/BatchVisualizationModal.tsx

type LayoutName = 'cose' | 'circle' | 'concentric' | 'breadthfirst' | 'grid'

const LAYOUT_OPTIONS: { value: LayoutName; label: string; description: string }[] = [
  { value: 'cose', label: '力导向', description: '自动聚类，展示关联强度' },
  { value: 'circle', label: '圆形', description: '所有节点均匀分布' },
  { value: 'concentric', label: '同心圆', description: '按连接数分层' },
  { value: 'breadthfirst', label: '树状', description: '层级结构展示' },
  { value: 'grid', label: '网格', description: '大量节点时使用' }
]

const LAYOUT_CONFIGS: Record<LayoutName, cytoscape.LayoutOptions> = {
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
    animate: false
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
    condense: true
  }
}

// 组件内
const [layout, setLayout] = useState<LayoutName>('cose')

const handleLayoutChange = (newLayout: LayoutName) => {
  setLayout(newLayout)
  if (cyRef.current) {
    cyRef.current.layout(LAYOUT_CONFIGS[newLayout]).run()
  }
}

// JSX
<Select
  value={layout}
  onChange={handleLayoutChange}
  style={{ width: 120 }}
  options={LAYOUT_OPTIONS.map(o => ({
    value: o.value,
    label: o.label,
    title: o.description
  }))}
/>
```

**扩展：Cola 布局（可选）**

```bash
npm install cytoscape-cola
```

```typescript
import cola from 'cytoscape-cola'
cytoscape.use(cola)

// Cola 配置（高质量约束布局）
const colaConfig = {
  name: 'cola',
  animate: true,
  maxSimulationTime: 2000,
  ungrabifyWhileSimulating: true,
  nodeSpacing: () => 30
}
```

---

## 三、实现计划

### 3.1 文件变更清单

| 操作 | 文件 | 说明 |
|------|------|------|
| 修改 | `src/utils/echarts.ts` | 添加 SVGRenderer |
| 修改 | `src/utils/chart-export.ts` | 添加 SVG 导出函数 |
| 修改 | `src/utils/pdf-export.ts` | 重写分页逻辑 |
| 修改 | `BatchVisualizationModal.tsx` | 布局选择器 + SVG 导出 |
| 修改 | `SpeciesChart.tsx` | SVG 导出按钮 |
| 修改 | `BAChart.tsx` | SVG 导出按钮 |
| 修改 | `TopLncRNAChart.tsx` | SVG 导出按钮 |

### 3.2 新增依赖

```bash
npm install cytoscape-svg
# 可选：npm install cytoscape-cola
```

### 3.3 实施优先级

| 阶段 | 任务 | 影响范围 | 耗时估算 |
|------|------|----------|----------|
| **Phase 1** | PDF 分页优化 | pdf-export.ts | 中 |
| **Phase 2** | 网络图布局选择器 | BatchVisualizationModal | 中 |
| **Phase 3** | ECharts SVG 导出 | echarts.ts + 图表组件 | 中 |
| **Phase 4** | Cytoscape SVG 导出 | BatchVisualizationModal | 低 |

---

## 四、风险评估

| 风险 | 影响 | 缓解措施 |
|------|------|----------|
| SVGRenderer 增加 Bundle | 约 50KB | 动态导入 |
| Canvas 裁剪内存占用 | 大图时可能卡顿 | 添加进度提示 |
| cytoscape-svg 兼容性 | 可能有样式差异 | 测试后微调 |
| Cola 布局性能 | 大图时较慢 | 限制节点数或显示进度 |

---

## 五、验收标准

### 5.1 SVG 导出

- [ ] ECharts 图表可导出 SVG 文件
- [ ] SVG 在 AI/PS 中可编辑
- [ ] 矢量无损放大

### 5.2 PDF 分页

- [ ] 长内容正确分页
- [ ] 每页内容不溢出
- [ ] 页码正确显示
- [ ] 首页标题 + 时间戳

### 5.3 布局算法

- [ ] 5 种布局可切换
- [ ] 切换动画平滑
- [ ] 布局描述清晰
- [ ] 大图（100 节点）性能可接受

---

## 六、技术备忘

### 6.1 ECharts SVG 渲染器注意事项

```typescript
// SVG 渲染器不支持某些特性：
// - 阴影（shadow）
// - 模糊（blur）
// - 部分渐变效果

// 建议：显示用 Canvas，导出用 SVG
```

### 6.2 Canvas 裁剪 API

```typescript
// drawImage 的完整签名
ctx.drawImage(
  image,    // 源图像
  sx, sy,   // 源起点
  sWidth, sHeight,  // 源尺寸
  dx, dy,   // 目标起点
  dWidth, dHeight   // 目标尺寸
)
```

### 6.3 Cytoscape 布局事件

```typescript
cy.layout(options).run()

// 监听布局完成
cy.on('layoutstop', () => {
  console.log('Layout finished')
})
```

---

**文档版本**: v1.0
**作者**: Claude Code
