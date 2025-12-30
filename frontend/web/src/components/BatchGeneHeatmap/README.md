# 批量基因热图可视化组件 (Batch Gene Heatmap Visualization)

## Phase 2.10 - 批量基因热图可视化功能

本模块实现了大规模批量基因ChIP-seq热图可视化功能，支持同时分析多个基因的组蛋白修饰模式。

## 功能特性

### 核心功能
- **多基因选择**: 支持一次选择最多10个基因
- **大矩阵热图**: 动态计算高度，支持genes × marks × cell_types的三维数据展示
- **并行数据获取**: 使用TanStack Query的`useQueries`并行查询多个基因的数据
- **交互式可视化**: 基于ECharts的高性能热图渲染，支持点击交互
- **多指标支持**: 支持4种度量指标 (Fold Enrichment, Peak Count, Coverage, Avg Signal)
- **多语言支持**: 完整的i18n国际化支持 (英文/中文)

### 数据展示维度
- **X轴**: 组蛋白标记 (H3K4me3, H3K27me3, 等)
- **Y轴**: 基因 × 细胞类型组合 (动态分组)
- **颜色**: 根据选定的度量指标进行色彩映射

## 文件结构

```
src/components/BatchGeneHeatmap/
├── GeneSelector.tsx          # 基因多选器组件
├── BatchHeatmapMatrix.tsx    # 大矩阵热图组件
└── index.tsx                 # 完整集成示例

src/hooks/
└── useBatchGeneHeatmap.ts    # 批量查询Hook (useQueries)

src/api/
└── chipseq.ts               # 添加批量API方法

src/i18n/locales/
├── en/batchGeneHeatmap.json
└── zh-CN/batchGeneHeatmap.json
```

## 组件说明

### 1. GeneSelector 组件

多选基因的选择器组件。

**Props**:
```typescript
interface GeneSelectorProps {
  value?: GeneInfo[]                    // 当前选择的基因
  onChange?: (genes: GeneInfo[]) => void // 选择变化回调
  availableGenes?: GeneInfo[]           // 可用基因列表
  loading?: boolean                     // 加载状态
  maxCount?: number                     // 最大选择数 (默认10)
  showQuickAdd?: boolean                // 显示快速添加输入框
}
```

**示例使用**:
```tsx
const [selectedGenes, setSelectedGenes] = useState<GeneInfo[]>([])

<GeneSelector
  value={selectedGenes}
  onChange={setSelectedGenes}
  availableGenes={genesList}
  maxCount={10}
/>
```

### 2. BatchHeatmapMatrix 组件

大规模热图可视化组件。

**特点**:
- 自动计算图表高度: `height = 200 + rows × 35`
- 支持动态行标签 (基因名 + 细胞类型)
- 可配置标签显示 (根据数据规模自动隐藏)
- 完整的tooltip和交互支持

**Props**:
```typescript
interface BatchHeatmapMatrixProps {
  data: Array<{
    gene_name: string
    marks: string[]
    cell_types: string[]
    matrix: Array<Array<number | null>>
  }>
  metric?: HeatmapMetricType
  onMetricChange?: (metric: HeatmapMetricType) => void
  onCellClick?: (params: {...}) => void
  loading?: boolean
  error?: Error | null
}
```

### 3. useBatchGeneHeatmap Hook

使用React Query的useQueries进行并行数据查询。

**特点**:
- 并行查询多个基因数据
- 统一的加载和错误状态管理
- 自动数据聚合和格式转换

**使用示例**:
```tsx
const { data, isLoading, error, queryStatus } = useBatchGeneHeatmap(
  [
    { gene_id: 123, gene_name: 'BRCA1' },
    { gene_id: 456, gene_name: 'TP53' }
  ],
  ['H3K27me3', 'H3K4me3'],
  ['H1', 'HepG2'],
  'median_fold_enrichment'
)

// 获取单个基因的查询状态
queryStatus.forEach(status => {
  console.log(`${status.gene_name}: ${status.isPending ? 'loading' : 'done'}`)
})
```

### 4. API 方法

#### `chipseqApi.getHeatmapMatrix()`
获取单个基因的热图矩阵数据 (现有方法)

#### `chipseqApi.getBatchHeatmapMatrix()` (新增)
批量获取多个基因的热图数据

**参数**:
```typescript
getBatchHeatmapMatrix(
  geneIds: number[],           // 基因ID数组
  marks: MarkType[],           // 组蛋白标记
  cellTypes: string[],         // 细胞类型
  metric: HeatmapMetricType,   // 度量指标
  flanking?: number            // 侧翼区域 (默认10000)
)
```

#### `chipseqApi.exportBatchHeatmapToCSV()` (新增)
批量导出热图数据为CSV格式

## 使用示例

### 完整集成示例

```tsx
import BatchGeneHeatmapViewer from '@/components/BatchGeneHeatmap'

export function MyPage() {
  const [availableGenes, setAvailableGenes] = useState<GeneInfo[]>([])
  const [loading, setLoading] = useState(false)

  useEffect(() => {
    // 加载可用基因列表
    fetchAvailableGenes().then(setAvailableGenes)
  }, [])

  return (
    <BatchGeneHeatmapViewer
      availableGenes={availableGenes}
      initialGenes={[]}
      loadingGenes={loading}
      onGenesChange={(genes) => {
        console.log('Selected genes:', genes.map(g => g.gene_name))
      }}
    />
  )
}
```

### 单独使用 Hook

```tsx
function MyComponent() {
  const [selectedGenes, setSelectedGenes] = useState<GeneInfo[]>([])
  const [selectedMarks, setSelectedMarks] = useState<MarkType[]>(['H3K27me3', 'H3K4me3'])
  const [metric, setMetric] = useState<HeatmapMetricType>('median_fold_enrichment')

  const { data, isLoading, error } = useBatchGeneHeatmap(
    selectedGenes,
    selectedMarks,
    ['H1', 'HepG2'],
    metric,
    10000,
    { enabled: selectedGenes.length > 0 }
  )

  if (isLoading) return <Spin />
  if (error) return <Alert type="error" message={error.message} />

  return <BatchHeatmapMatrix data={data} metric={metric} />
}
```

## 性能优化

### 数据获取优化
1. **并行查询**: 使用`useQueries`并行获取多个基因的数据，而不是顺序查询
2. **缓存策略**: 30分钟的缓存时间，避免重复请求
3. **条件启用**: 使用`enabled`选项，仅在有选中的基因时才启动查询

### 渲染优化
1. **动态高度计算**: 根据数据行数动态计算图表高度，避免固定高度导致的滚动问题
2. **条件标签显示**: 数据量大时自动隐藏单元格标签，提升渲染性能
3. **Lazy Update**: 使用ECharts的`lazyUpdate`模式减少重排
4. **useMemo优化**: 所有计算密集的操作都使用useMemo缓存

## Context7 查询信息

本实现参考了以下库的最佳实践:

### 1. Apache ECharts (Heatmap 大数据集处理)
- 使用`visualMap`进行颜色映射
- 支持大数据集的高性能渲染
- 灵活的标签和tooltip配置

### 2. TanStack Query (React Query) - useQueries
- 动态并行查询: 可根据输入数组动态生成查询
- 统一的加载/错误状态管理
- 可选的`combine`函数用于结果聚合

### 3. Ant Design Select - 多选模式
- `mode="multiple"`: 启用多选功能
- `maxCount`: 限制最大选择数
- `tagRender`: 自定义标签渲染
- `optionFilterProp`: 自定义搜索过滤字段

## 国际化

所有组件都支持完整的i18n国际化。翻译键都以`batchGeneHeatmap.`为前缀。

**支持的语言**:
- English (en)
- 中文简体 (zh-CN)

### 添加新语言

在`src/i18n/locales/`下创建新的语言文件夹:
```
src/i18n/locales/
└── es/
    └── batchGeneHeatmap.json
```

## 后端API要求

### 现有端点

#### `GET /api/v1/features/chipseq/genes/{gene_id}/heatmap-matrix`
```
参数:
  marks: string (逗号分隔)
  cell_types: string (逗号分隔)
  metric: median_fold_enrichment|peak_count|total_coverage_bp|avg_signal
  flanking: number (可选)
```

### 新端点要求

#### `GET /api/v1/features/chipseq/batch/heatmap-matrix` (需实现)
```
参数:
  gene_ids: string (逗号分隔)
  marks: string (逗号分隔)
  cell_types: string (逗号分隔)
  metric: string
  flanking: number (可选)

响应:
  Array<HeatmapMatrixResponse>
```

#### `GET /api/v1/features/chipseq/batch/heatmap-matrix/export` (需实现)
```
参数:
  gene_ids: string (逗号分隔)
  marks: string (逗号分隔)
  cell_types: string (逗号分隔)
  metric: string
  format: csv

响应:
  CSV 文件下载
```

## 依赖项

- React 18+
- TypeScript
- @tanstack/react-query (v5+)
- antd (v5+)
- echarts (v5+)
- echarts-for-react (v3+)
- react-i18next

## 类型定义

```typescript
interface GeneInfo {
  gene_id: number
  gene_name: string
  chromosome?: string
  start?: number
  end?: number
}

interface HeatmapMatrixData {
  gene_name: string
  gene_id: number
  chromosome?: string
  marks: string[]
  cell_types: string[]
  matrix: Array<Array<number | null>>
}

type HeatmapMetricType =
  | 'median_fold_enrichment'
  | 'peak_count'
  | 'total_coverage_bp'
  | 'avg_signal'
```

## 故障排除

### 问题: 热图显示不完整
**解决**: 确保`BatchHeatmapMatrix`的`data`数组中的`matrix`维度正确

### 问题: 查询速度慢
**解决**:
1. 检查后端API响应时间
2. 减少选中的基因数量
3. 调整缓存时间参数

### 问题: 内存占用过高
**解决**:
1. 限制同时加载的基因数量 (maxCount)
2. 减少选中的cell types数量
3. 使用更小的flanking region

## 许可证

同项目主体许可证

## 更新日志

### v1.0.0 (2025-12-07)
- 初始实现: GeneSelector, BatchHeatmapMatrix, useBatchGeneHeatmap
- 并行查询支持
- 完整的i18n支持
- 导出功能
