# Human LncRNA Atlas 前端待办事项实施方案 (修订版)

**日期**: 2025-11-28
**版本**: v2.2 (2025-12-02 全部完成)
**状态**: ✅ 全部完成

> 更新（2026-01-24）：本文档为历史实施方案快照（已全部完成，用于回溯实现细节），不代表当前开发待办；现状以 `docs/CURRENT_STATUS.md` 为准。

---

## 一、待办事项总览 (最终状态)

| # | 任务 | 当前状态 | 复杂度 | 优先级 | 完成日期 |
|---|------|---------|--------|--------|----------|
| 1 | SVG 导出支持 | ✅ **已完成** | 中 | P1 | 2025-12-01 |
| 2 | PDF 分页优化 | ✅ **已完成** | 低 | P3 | 2025-11-28 |
| 3 | 布局算法 UI | ✅ **已完成** | 低 | P3 | 2025-11-28 |
| 4 | Gene 详情页 | ✅ **已完成** | 中 | P1 | 2025-12-01 |
| 5 | Disease 关联展示 | ✅ **已完成** | 中 | P2 | 2025-12-01 |
| 6 | Bundle 优化 | ✅ **已完成** | 低 | P3 | 2025-12-02 |
| 7 | ESLint 规则 | ✅ **已完成** | 低 | P3 | 2025-11-28 |
| 8 | 单元测试配置 | ✅ **已完成** | 中高 | P2 | 2025-11-28 |

---

## 二、关键发现 (代码审查结果)

### 已确认的现有实现

| 模块 | 位置 | 状态 |
|------|------|------|
| 布局选择器 UI | `Network/index.tsx` L746-760 | ✅ 已在 Collapse 过滤器中实现 |
| ECharts 按需导入 | `utils/echarts.ts` | ✅ 已配置 PieChart/BarChart/CanvasRenderer |
| Disease 关联 API | `GET /api/v1/diseases/{trait_id}/genes` | ✅ 后端已实现，返回分页数据 |
| 基因字段 | `GeneListItem` / `GeneDetail` | `gene_start`, `gene_end`, `gene_ensembl_id` |

### 需注意的类型/接口

```typescript
// ErrorState 组件签名 (src/components/ErrorState.tsx)
interface ErrorStateProps {
  error: Error | unknown  // 必需参数
  onRetry?: () => void
}
export const ErrorState = ({ error, onRetry }: ErrorStateProps) => { ... }

// useGeneDetail hook (src/hooks/useGenes.ts)
export const useGeneDetail = (geneId: number) => { ... }  // 接收 number，非 string

// GeneDetail schema (src/types/api.ts L429-477)
GeneDetail: {
  gene_id: number
  gene_name?: string | null
  gene_ensembl_id?: string | null
  gene_type: string
  species_name: string
  chromosome?: string | null
  gene_start?: number | null   // 非 start_position
  gene_end?: number | null     // 非 end_position
  regulation_count: number
  target_count: number
  disease_count: number
  orthologs?: OrthologInfo[]
}

// TraitGeneAssociationDetail (Disease 关联)
TraitGeneAssociationDetail: {
  association_id: number
  core_id: number
  gene_name?: string | null
  gene_type: string
  trait_id: number
  trait_name: string
  ontology_id: number
  ontology_name: string
  // ... 更多字段
}
```

---

## 三、各任务详细方案 (修订版)

---

### Task 1: SVG 导出支持 (修订)

**目标**: 为 Network 网络图添加真正的 SVG 导出功能

**当前状态**:
- `Network/index.tsx` L490-505 有占位代码，调用 `exportAsSVG()` 实际回退到 PNG
- 使用 `cyRef.current` 引用 Cytoscape 实例

**实施步骤**:

#### Step 1.1: 安装依赖并添加类型声明
```bash
cd <repo-root>/frontend/web
npm install cytoscape-svg
```

```typescript
// src/types/cytoscape-svg.d.ts (新建类型声明文件)
// 注意：cytoscape-svg 不导出类型，需要本地声明

declare module 'cytoscape-svg' {
  import cytoscape from 'cytoscape'
  const ext: cytoscape.Ext
  export default ext
}

// 扩展 Cytoscape Core 类型，本地声明 SvgOptions
declare module 'cytoscape' {
  interface SvgExportOptions {
    full?: boolean
    scale?: number
    bg?: string
    quality?: number
  }

  interface Core {
    svg(options?: SvgExportOptions): string
  }
}
```

#### Step 1.2: 在 Network 组件注册插件
```typescript
// src/pages/Network/index.tsx 顶部
import cytoscape from 'cytoscape'
import cytoscapeSvg from 'cytoscape-svg'

// 注册插件 - 在模块作用域执行一次，添加 SSR 保护
if (typeof window !== 'undefined') {
  cytoscape.use(cytoscapeSvg)
}
```

#### Step 1.3: 修改 exportAsSVG 函数 (替换 L490-505)
```typescript
const exportAsSVG = () => {
  // null 保护
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
```

**涉及文件**:
1. `package.json` - 添加 cytoscape-svg
2. `src/types/cytoscape-svg.d.ts` - 新建类型声明
3. `src/pages/Network/index.tsx` - 插件注册 + 修改 exportAsSVG

**ECharts SVG 说明**:
- 当前 Stats 页面图表使用 CanvasRenderer，暂不改动
- 如需 SVG，需在 `utils/echarts.ts` 添加 `SVGRenderer` 并修改各图表组件的 `renderer` 选项
- 影响范围较大，建议作为独立任务处理

**验收标准**:
- [ ] Network 页面 SVG 导出菜单正常工作
- [ ] 导出的 SVG 文件可在浏览器/Illustrator 中打开
- [ ] TypeScript 编译无错误

---

### Task 2: PDF 分页优化

**当前状态**: `src/utils/pdf-export.ts` 已有完整实现 (256 行)，包含：
- Canvas 分片裁剪避免溢出
- 页码显示
- A4 纸张配置

**任务**: 验证现有实现，仅在发现问题时修复

**验收标准**:
- [ ] Stats 页面导出 PDF 分页正确
- [ ] 图表不在中间截断
- [ ] 页码显示正确

---

### Task 3: 布局算法 UI (已实现，改为验收)

**当前状态**:
- `Network/index.tsx` L62-131 已有 `getLayoutConfig()` 支持 6 种布局
- L746-760 已有布局选择器 UI (在 Collapse 过滤器中)
- L124-131 已有 `handleLayoutChange()` 函数

**已支持的布局**:
| 布局 | 配置 |
|------|------|
| concentric | 同心圆，lncRNA 在中心 |
| cose | 力导向布局 |
| circle | 圆形布局 |
| grid | 网格布局 |
| breadthfirst | 广度优先树 |
| random | 随机布局 |

**任务**: 验收现有实现，可选微调 cose 参数

**可选优化** (如需更好的布局效果):
```typescript
// 调整 cose 参数以获得更好的节点分布
case 'cose':
  return {
    name: 'cose',
    ...baseConfig,
    nodeRepulsion: () => 10000,      // 增加节点排斥力
    idealEdgeLength: () => 120,      // 增加理想边长
    edgeElasticity: () => 100,
    gravity: 0.2,                    // 降低重力
    numIter: 1500,                   // 增加迭代次数
    nodeDimensionsIncludeLabels: true
  }
```

**验收标准**:
- [ ] 布局选择器在过滤器面板中可用
- [ ] 切换布局有平滑动画
- [ ] 各布局正确渲染网络

---

### Task 4: Gene 详情页 (修订)

**目标**: 创建 Gene 详情页，展示单个基因的完整信息

**现有资源**:
- API: `GET /api/v1/genes/{gene_id}` 返回 `GeneDetail`
- Hook: `useGeneDetail(geneId: number)`
- 类型: `components['schemas']['GeneDetail']`

**实施步骤**:

#### Step 4.1: 添加缺失的 i18n keys

```json
// src/i18n/locales/zh-CN/common.json - 在 action 对象中添加
{
  "action": {
    // ... 现有 keys
    "back": "返回"
  }
}

// src/i18n/locales/en/common.json - 在 action 对象中添加
{
  "action": {
    // ... 现有 keys
    "back": "Back"
  }
}

// src/i18n/locales/zh-CN/genes.json - 添加 detail 对象
{
  "detail": {
    "title": "基因详情",
    "basicInfo": "基本信息",
    "statistics": "统计信息",
    "orthologs": "直系同源基因",
    "regulations": "调控关系",
    "noOrthologs": "暂无同源基因数据",
    "noRegulations": "暂无调控关系数据",
    "regulationCount": "调控关系数",
    "targetCount": "靶基因数",
    "diseaseCount": "关联疾病数",
    "notFound": "基因不存在"
  }
}

// src/i18n/locales/en/genes.json - 添加 detail 对象
{
  "detail": {
    "title": "Gene Detail",
    "basicInfo": "Basic Information",
    "statistics": "Statistics",
    "orthologs": "Orthologs",
    "regulations": "Regulations",
    "noOrthologs": "No ortholog data available",
    "noRegulations": "No regulation data available",
    "regulationCount": "Regulation Count",
    "targetCount": "Target Count",
    "diseaseCount": "Disease Count",
    "notFound": "Gene not found"
  }
}
```

#### Step 4.2: 添加路由
```tsx
// src/App.tsx
import GeneDetail from './pages/GeneDetail'

// 在 Routes 中添加
<Route path="genes/:geneId" element={<GeneDetail />} />
```

#### Step 4.3: 创建详情页组件
```tsx
// src/pages/GeneDetail/index.tsx
import { useParams, useNavigate } from 'react-router-dom'
import { useGeneDetail } from '@/hooks/useGenes'
import { useTranslation } from 'react-i18next'
import { Card, Descriptions, Button, Tag, Divider, Table, Result } from 'antd'
import { ArrowLeftOutlined, LinkOutlined } from '@ant-design/icons'
import { LoadingState } from '@/components/LoadingState'
import { ErrorState } from '@/components/ErrorState'

// 物种名翻译映射 - 支持中文名和英文名
const SPECIES_NAME_TO_KEY: Record<string, string> = {
  // 中文名
  '人类': 'human',
  '黑猩猩': 'chimpanzee',
  '猕猴': 'macaque',
  '狨猴': 'marmoset',
  // 英文名 (API 可能返回)
  'Human': 'human',
  'Chimpanzee': 'chimpanzee',
  'Macaque': 'macaque',
  'Marmoset': 'marmoset',
  'human': 'human',
  'chimpanzee': 'chimpanzee',
  'macaque': 'macaque',
  'marmoset': 'marmoset'
}

export default function GeneDetail() {
  const { geneId } = useParams<{ geneId: string }>()
  const navigate = useNavigate()
  const { t } = useTranslation('genes')
  const { t: tCommon } = useTranslation('common')

  // 转换为 number，处理 NaN 情况
  const geneIdNum = geneId ? parseInt(geneId, 10) : 0
  const isValidId = !isNaN(geneIdNum) && geneIdNum > 0

  // useGeneDetail 内部 enabled: !!geneId，传入 0 时不会发请求
  const { data: gene, isLoading, error } = useGeneDetail(isValidId ? geneIdNum : 0)

  // 翻译物种名
  const translateSpecies = (speciesName: string) => {
    const key = SPECIES_NAME_TO_KEY[speciesName]
    return key ? tCommon(`species.${key}`) : speciesName
  }

  // 清理 Ensembl ID 后缀
  const cleanEnsemblId = (id: string | null | undefined) => {
    if (!id) return null
    return id.replace(/_(marmoset|macaque|chimpanzee|chimp)$/i, '')
  }

  if (isLoading) return <LoadingState />
  if (error) return <ErrorState error={error} onRetry={() => window.location.reload()} />
  if (!gene) return <Result status="404" title="404" subTitle={t('detail.notFound')} />

  const cleanId = cleanEnsemblId(gene.gene_ensembl_id)

  return (
    <div style={{ padding: 24 }}>
      <Button
        icon={<ArrowLeftOutlined />}
        onClick={() => navigate('/genes')}
        style={{ marginBottom: 16 }}
      >
        {tCommon('action.back')}
      </Button>

      <Card title={`${t('detail.title')}: ${gene.gene_name || gene.gene_id}`}>
        {/* 基本信息 */}
        <Descriptions title={t('detail.basicInfo')} column={2} bordered size="small">
          <Descriptions.Item label="Gene ID">{gene.gene_id}</Descriptions.Item>
          <Descriptions.Item label="Core ID">{gene.core_id}</Descriptions.Item>
          <Descriptions.Item label="Ensembl ID">
            {cleanId ? (
              <a
                href={`https://www.ensembl.org/Homo_sapiens/Gene/Summary?g=${cleanId}`}
                target="_blank"
                rel="noopener noreferrer"
              >
                {gene.gene_ensembl_id} <LinkOutlined />
              </a>
            ) : (
              gene.gene_ensembl_id || 'N/A'
            )}
          </Descriptions.Item>
          <Descriptions.Item label={t('columns.type')}>
            <Tag color={gene.gene_type === 'lncRNA' ? 'blue' : 'green'}>
              {gene.gene_type}
            </Tag>
          </Descriptions.Item>
          <Descriptions.Item label={t('columns.species')}>
            {translateSpecies(gene.species_name)}
          </Descriptions.Item>
          <Descriptions.Item label={t('columns.chromosome')}>
            {gene.chromosome || 'N/A'}
          </Descriptions.Item>
          <Descriptions.Item label={t('columns.start')}>
            {gene.gene_start?.toLocaleString() || 'N/A'}
          </Descriptions.Item>
          <Descriptions.Item label={t('columns.end')}>
            {gene.gene_end?.toLocaleString() || 'N/A'}
          </Descriptions.Item>
        </Descriptions>

        <Divider />

        {/* 统计信息 */}
        <Descriptions title={t('detail.statistics')} column={3} size="small">
          <Descriptions.Item label={t('detail.regulationCount')}>
            <Tag color="blue">{gene.regulation_count}</Tag>
          </Descriptions.Item>
          <Descriptions.Item label={t('detail.targetCount')}>
            <Tag color="green">{gene.target_count}</Tag>
          </Descriptions.Item>
          <Descriptions.Item label={t('detail.diseaseCount')}>
            <Tag color="orange">{gene.disease_count}</Tag>
          </Descriptions.Item>
        </Descriptions>

        <Divider />

        {/* 直系同源基因 */}
        {gene.orthologs && gene.orthologs.length > 0 && (
          <>
            <h4>{t('detail.orthologs')}</h4>
            <Table
              dataSource={gene.orthologs}
              rowKey="gene_id"
              size="small"
              pagination={false}
              columns={[
                { title: t('columns.species'), dataIndex: 'species_name', render: translateSpecies },
                { title: t('columns.geneName'), dataIndex: 'gene_name' },
                { title: 'Ensembl ID', dataIndex: 'gene_ensembl_id' },
                { title: t('columns.chromosome'), dataIndex: 'chromosome' },
              ]}
            />
          </>
        )}
      </Card>
    </div>
  )
}
```

#### Step 4.4: Genes 列表页添加跳转链接
```tsx
// src/pages/Genes/index.tsx

// 1. 在文件顶部添加 import
import { useNavigate } from 'react-router-dom'

// 2. 在组件内部添加 hook
export default function Genes() {
  const navigate = useNavigate()  // 添加此行
  // ... 其他现有代码

// 3. 在 columns 数组末尾添加操作列
{
  title: tCommon('action.view'),  // 使用现有的 action.view key
  key: 'actions',
  width: 80,
  fixed: 'right' as const,
  render: (_: unknown, record: GeneListItem) => (
    <Button
      type="link"
      size="small"
      onClick={() => navigate(`/genes/${record.gene_id}`)}
    >
      {tCommon('link.view')}  // "查看 →" / "View →"
    </Button>
  )
}
```

**涉及文件**:
1. `src/App.tsx` - 路由配置
2. `src/pages/GeneDetail/index.tsx` - 新建
3. `src/pages/Genes/index.tsx` - 添加跳转
4. `src/i18n/locales/*/common.json` - 添加 action.back
5. `src/i18n/locales/*/genes.json` - 添加 detail 命名空间

**验收标准**:
- [ ] 点击 Genes 列表的"查看"可跳转详情页
- [ ] 详情页正确显示基因信息
- [ ] 返回按钮正常工作
- [ ] TypeScript 编译无错误

---

### Task 5: Disease 关联展示 (修订)

**重要发现**: 后端 API 已存在！

```
GET /api/v1/diseases/{trait_id}/genes
返回: PaginatedResponse_TraitGeneAssociationDetail_
```

**目标**: 在 Diseases 页面添加行展开或 Drawer 展示关联基因

**实施步骤**:

#### Step 5.1: 添加前端 API 和 Hook
```typescript
// src/api/diseases.ts - 添加方法和类型
import type { components } from '@/types'

type TraitGeneAssociationDetail = components['schemas']['TraitGeneAssociationDetail']
type PaginatedResponse<T> = {
  items: T[]
  total: number
  page: number
  page_size: number
  total_pages: number
}

export const diseasesApi = {
  // ... 现有方法
  getGenes: (traitId: number, params?: { page?: number; page_size?: number; gene_type?: string }) =>
    apiClient.get<PaginatedResponse<TraitGeneAssociationDetail>>(
      `/api/v1/diseases/${traitId}/genes`,
      { params }
    )
}

// src/hooks/useDiseases.ts - 添加 hook
// 注意：需要解构 { data } 因为 apiClient.get 返回 AxiosResponse
export function useDiseaseGenes(traitId: number, params?: { page?: number; page_size?: number }) {
  return useQuery({
    queryKey: ['disease', traitId, 'genes', params],
    queryFn: async () => {
      const { data } = await diseasesApi.getGenes(traitId, params)
      return data  // 返回实际数据，不是 AxiosResponse
    },
    enabled: !!traitId
  })
}
```

**注意**: 当前 API 返回的数据包含多个 ontology 的关联，如需按特定 ontology 过滤，
可在 params 中添加 ontology_id 参数（需后端支持），或在前端进行过滤。

#### Step 5.2: 添加 i18n keys
```json
// src/i18n/locales/zh-CN/diseases.json 添加
{
  "association": {
    "title": "关联基因",
    "geneName": "基因名称",
    "geneType": "基因类型",
    "ontology": "本体论",
    "oddsRatio": "比值比",
    "fdr": "FDR",
    "noData": "暂无关联基因"
  }
}

// src/i18n/locales/en/diseases.json 添加
{
  "association": {
    "title": "Associated Genes",
    "geneName": "Gene Name",
    "geneType": "Gene Type",
    "ontology": "Ontology",
    "oddsRatio": "Odds Ratio",
    "fdr": "FDR",
    "noData": "No associated genes"
  }
}
```

#### Step 5.3: Diseases 页面添加行展开
```tsx
// src/pages/Diseases/index.tsx

// 添加展开行渲染组件
const ExpandedRow = ({ traitId }: { traitId: number }) => {
  const { t } = useTranslation('diseases')
  const { data, isLoading } = useDiseaseGenes(traitId, { page: 1, page_size: 10 })

  if (isLoading) return <Spin size="small" />
  if (!data?.items?.length) return <div style={{ color: '#999' }}>{t('association.noData')}</div>

  return (
    <Table
      dataSource={data.items}
      rowKey="association_id"
      size="small"
      pagination={false}
      columns={[
        { title: t('association.geneName'), dataIndex: 'gene_name' },
        { title: t('association.geneType'), dataIndex: 'gene_type' },
        { title: t('association.ontology'), dataIndex: 'ontology_name' },
        { title: t('association.oddsRatio'), dataIndex: 'odds_ratio' },
        { title: t('association.fdr'), dataIndex: 'fdr' },
      ]}
    />
  )
}

// 在主 Table 中添加 expandable
<Table
  // ... 其他 props
  expandable={{
    expandedRowRender: (record) => <ExpandedRow traitId={record.trait_id} />,
    rowExpandable: (record) => record.gene_count > 0
  }}
/>
```

**涉及文件**:
1. `src/api/diseases.ts` - API 方法
2. `src/hooks/useDiseases.ts` - Hook
3. `src/pages/Diseases/index.tsx` - 行展开 UI
4. `src/i18n/locales/*/diseases.json` - 翻译

**验收标准**:
- [ ] Diseases 表格行可展开
- [ ] 展开后显示关联基因列表
- [ ] 无关联基因时显示提示
- [ ] 支持分页 (可选)

---

### Task 6: Bundle 优化 (修订)

**当前状态**:
- ECharts 已按需导入 (`src/utils/echarts.ts`)
- Vite 已配置基础 code splitting

**剩余优化项**:

#### Step 6.1: 添加 terser 压缩配置
```typescript
// vite.config.ts
// 注意：保持现有 manualChunks 命名格式 (xxx-vendor)，避免缓存失效
export default defineConfig({
  plugins: [react()],
  resolve: {
    alias: {
      '@': path.resolve(__dirname, './src'),
    },
  },
  build: {
    minify: 'terser',  // 使用 terser 压缩（构建时间稍长但压缩率更高）
    terserOptions: {
      compress: {
        drop_console: true,   // 移除 console.*
        drop_debugger: true   // 移除 debugger
      }
    },
    rollupOptions: {
      output: {
        manualChunks: {
          // 保持现有命名格式
          'react-vendor': ['react', 'react-dom', 'react-router-dom'],
          'antd-vendor': ['antd', '@ant-design/icons'],
          'query-vendor': ['@tanstack/react-query'],
          // 新增：大型库单独分包
          'echarts-vendor': ['echarts'],
          'cytoscape-vendor': ['cytoscape']
        }
      }
    },
    chunkSizeWarningLimit: 600,
  },
})
```

**说明**:
- terser 压缩无需额外安装依赖（Vite 内置支持）
- 构建时间会增加，但压缩率更好
- manualChunks 命名保持 `xxx-vendor` 格式与现有配置一致

#### Step 6.2: 分析 bundle 大小
```bash
npm run build
# 检查 dist/assets 目录下各 chunk 大小
```

**涉及文件**:
1. `vite.config.ts` - 构建配置

**验收标准**:
- [ ] 生产构建成功
- [ ] 主 bundle < 500KB (gzipped)
- [ ] 无 console.log 输出

---

### Task 7: ESLint 规则

**实施步骤**: 增强 `eslint.config.js` 规则

```javascript
// eslint.config.js
export default [
  // ... 现有配置
  {
    rules: {
      '@typescript-eslint/no-explicit-any': 'warn',
      '@typescript-eslint/no-unused-vars': ['warn', { argsIgnorePattern: '^_' }],
      'react-hooks/rules-of-hooks': 'error',
      'react-hooks/exhaustive-deps': 'warn',
      'no-console': ['warn', { allow: ['warn', 'error'] }],
      'prefer-const': 'warn'
    }
  }
]
```

**验收标准**:
- [ ] `npm run lint` 无 error
- [ ] warnings 可控

---

### Task 8: 单元测试配置 (修订)

**实施步骤**:

#### Step 8.1: 安装依赖
```bash
npm install -D vitest @testing-library/react @testing-library/jest-dom @testing-library/user-event jsdom
```

#### Step 8.2: 配置 Vitest
```typescript
// vitest.config.ts
import { defineConfig } from 'vitest/config'
import react from '@vitejs/plugin-react'
import path from 'path'

export default defineConfig({
  plugins: [react()],
  test: {
    globals: true,
    environment: 'jsdom',
    setupFiles: './src/test/setup.ts',
    include: ['src/**/*.{test,spec}.{ts,tsx}'],
  },
  resolve: {
    alias: {
      '@': path.resolve(__dirname, './src')
    }
  }
})
```

#### Step 8.3: 测试 Setup
```typescript
// src/test/setup.ts
import '@testing-library/jest-dom'
import { vi } from 'vitest'

// Mock window.matchMedia (Antd 需要)
Object.defineProperty(window, 'matchMedia', {
  writable: true,
  value: vi.fn().mockImplementation(query => ({
    matches: false,
    media: query,
    onchange: null,
    addListener: vi.fn(),
    removeListener: vi.fn(),
    addEventListener: vi.fn(),
    removeEventListener: vi.fn(),
    dispatchEvent: vi.fn(),
  })),
})
```

#### Step 8.4: 示例测试 (按真实组件签名)
```typescript
// src/components/__tests__/ErrorState.test.tsx
import { render, screen } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { describe, it, expect, vi } from 'vitest'
import { ErrorState } from '../ErrorState'  // 命名导出

// Mock i18n
vi.mock('react-i18next', () => ({
  useTranslation: () => ({
    t: (key: string) => key
  })
}))

describe('ErrorState', () => {
  it('renders error message', () => {
    const error = new Error('Test error message')
    render(<ErrorState error={error} />)

    expect(screen.getByText('error.loadFailed')).toBeInTheDocument()
    expect(screen.getByText('Test error message')).toBeInTheDocument()
  })

  it('renders retry button when onRetry provided', async () => {
    const onRetry = vi.fn()
    render(<ErrorState error={new Error('test')} onRetry={onRetry} />)

    const retryButton = screen.getByRole('button', { name: /error.retry/i })
    expect(retryButton).toBeInTheDocument()

    await userEvent.click(retryButton)
    expect(onRetry).toHaveBeenCalledOnce()
  })

  it('handles unknown error type', () => {
    render(<ErrorState error="string error" />)
    expect(screen.getByText('error.unknown')).toBeInTheDocument()
  })
})
```

#### Step 8.5: 添加 npm scripts
```json
// package.json
{
  "scripts": {
    "test": "vitest",
    "test:run": "vitest run",
    "test:coverage": "vitest run --coverage"
  }
}
```

**涉及文件**:
1. `package.json` - 依赖和脚本
2. `vitest.config.ts` - 新建
3. `src/test/setup.ts` - 新建
4. `src/components/__tests__/ErrorState.test.tsx` - 示例测试

**验收标准**:
- [ ] `npm test` 可正常运行
- [ ] 示例测试通过
- [ ] TypeScript 编译无错误

---

## 四、依赖变更汇总

### 新增生产依赖
```json
{
  "cytoscape-svg": "^0.4.0"
}
```

### 新增开发依赖
```json
{
  "vitest": "^3.0.0",
  "@testing-library/react": "^16.0.0",
  "@testing-library/jest-dom": "^6.6.0",
  "@testing-library/user-event": "^14.5.0",
  "jsdom": "^25.0.0"
}
```

---

## 五、执行顺序建议

```
Phase 1 (快速胜利 ~1.5h):
├── Task 7: ESLint 规则 (0.5h)
├── Task 3: 布局算法验收 (0.5h)
└── Task 2: PDF 分页验收 (0.5h)

Phase 2 (核心功能 ~3.5h):
├── Task 1: SVG 导出 (1.5-2h)
└── Task 4: Gene 详情页 (2h)

Phase 3 (功能扩展 ~2h):
├── Task 5: Disease 关联 (1.5h)
└── Task 6: Bundle 优化 (0.5h)

Phase 4 (质量保障 ~3h):
└── Task 8: 单元测试配置 (3h)
```

---

## 六、验收清单

- [x] SVG 导出功能可用 (Task 1) ✅
- [x] PDF 导出分页正确 (Task 2) ✅
- [x] 布局切换 UI 验收 (Task 3) ✅
- [x] Gene 详情页可访问 (Task 4) ✅
- [x] Disease 关联可查看 (Task 5) ✅
- [x] Bundle 大小优化 (Task 6) ✅
- [x] ESLint 规则增强 (Task 7) ✅
- [x] 测试框架可运行 (Task 8) ✅

---

**文档版本**: v2.2
**创建时间**: 2025-11-28
**完成时间**: 2025-12-02
**修订说明**:
- v2.0: 根据代码审查结果修正类型/字段/API 不匹配问题
- v2.1: 完善实现细节 - cytoscape-svg 本地类型声明、SSR 保护、物种映射支持英文名、
        disease hook 正确解构 data、vite manualChunks 命名一致性、添加 notFound key
- v2.2: 标记所有任务为已完成，添加 esbuild.drop 配置移除生产环境 console
**作者**: Claude Code
