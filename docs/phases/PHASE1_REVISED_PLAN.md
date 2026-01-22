# Phase 1 前端功能增强 - 修订方案

**项目**: Human LncRNA Atlas - 前端增强（技术栈对齐版）
**版本**: v2.0
**日期**: 2025-11-27
**状态**: ✅ 技术栈已对齐，待实施

---

> 更新（2026-01）：本文档为 2025-11 的 Phase 1 修订计划稿保留。当前项目已进入 Phase 3.x，Stats/Regulations 等核心 API 已实现，MSW Mock 已移除或仅保留空框架。\
> 文中出现的 “Mock/后端待实现/未实现” 等描述仅代表当时阶段，请以 `docs/CURRENT_STATUS.md` 与代码实现为准。

## 📊 技术栈对齐报告

### 实际技术栈（经验证）

| 技术 | 实际版本 | 原方案假设 | 状态 |
|------|---------|-----------|------|
| **React** | 19.2.0 | 18.x | ⚠️ 需调整 |
| **Ant Design** | 6.0.0 | 5.x | ⚠️ 需调整 |
| **React Query** | 5.90.10 | 5.x | ✅ 一致 |
| **ECharts** | 6.0.0 | - | ✅ 已安装 |
| **echarts-for-react** | 3.0.5 | - | ✅ 已安装 |
| **file-saver** | 2.0.5 | - | ✅ 已安装 |
| **TypeScript** | 5.9.3 | 5.x | ✅ 一致 |

### 需要新增的依赖

```bash
# 仅需安装这些
npm install msw --save-dev
npm install xlsx
npm install -D rollup-plugin-visualizer
```

---

## ⚠️ 关键风险与调整措施

### 1. React 19 + AntD 6 兼容性调整

#### 主要变化

**AntD 5 → 6 Breaking Changes**:

1. **Table 组件**:
   - `columns` 类型保持兼容
   - `pagination` API 无变化
   - `rowKey` 保持不变
   - ✅ **现有代码无需修改**

2. **Collapse 组件**:
   - AntD 6 使用 `items` prop（数组）替代子组件
   - ⚠️ **需要调整方案中的 Collapse 代码**

3. **Form 组件**:
   - API 保持向后兼容
   - ✅ **无需修改**

#### 调整后的 Collapse 使用模式

```typescript
// ❌ 原方案（AntD 5 风格）
<Collapse defaultActiveKey={['filters']}>
  <Collapse.Panel key="filters" header="高级筛选">
    {/* 内容 */}
  </Collapse.Panel>
</Collapse>

// ✅ 修订方案（AntD 6）
<Collapse
  items={[
    {
      key: 'filters',
      label: <Space><FilterOutlined />高级筛选</Space>,
      children: <AdvancedFiltersContent />
    }
  ]}
/>
```

**React 19 变化**:
- `React.FC` 类型保持兼容
- Hooks API 无变化
- ✅ **无需调整**

---

### 2. BA 范围动态化（关键修正）

#### 问题分析

**原方案硬编码问题**:
```typescript
// ❌ 原方案：硬编码 0-100
<Slider min={0} max={100} />

// 后端实际情况
binding_affinity: Optional[Decimal]  // 无上限约束！
min_ba: Optional[float] = Field(ge=0)  // 只约束 ≥ 0
```

**实际数据范围**（需验证）:
- 理论范围：0 - ∞（Decimal 类型）
- 实际业务范围：需查询数据库 `SELECT MIN(binding_affinity), MAX(binding_affinity) FROM regulations`

#### 调整方案

**方案 A：后端提供范围端点（推荐）**

```python
# 后端新增 API
@router.get("/api/v1/stats/ba-range")
async def get_ba_range():
    """获取 BA 值的实际范围"""
    result = await db.fetch_one(
        "SELECT MIN(binding_affinity) as min_ba, MAX(binding_affinity) as max_ba FROM regulations"
    )
    return {
        "min": float(result["min_ba"] or 0),
        "max": float(result["max_ba"] or 100)
    }
```

```typescript
// 前端使用动态范围
const { data: baRange } = useQuery({
  queryKey: ['ba-range'],
  queryFn: async () => {
    const { data } = await apiClient.get('/api/v1/stats/ba-range')
    return data
  },
  staleTime: Infinity  // BA 范围不会频繁变化
})

<Slider
  min={baRange?.min || 0}
  max={baRange?.max || 100}
  step={0.1}
  value={[filters.min_ba || baRange?.min || 0, filters.max_ba || baRange?.max || 100]}
/>
```

**方案 B：前端配置化（临时方案）**

```typescript
// src/config/constants.ts
export const BA_CONFIG = {
  MIN: 0,
  MAX: 100,  // ⚠️ 根据实际数据调整此值
  STEP: 0.1,
  DEFAULT_MIN: 0,
  DEFAULT_MAX: 100
}

// 使用时
<Slider
  min={BA_CONFIG.MIN}
  max={BA_CONFIG.MAX}
  step={BA_CONFIG.STEP}
/>
```

**本次实施选择**：使用 **方案 B**，后续后端实现后切换到方案 A。

**直方图区间调整**:
```typescript
// ❌ 原方案：固定 10 个区间（0-10, 10-20, ..., 90-100）
buckets: [
  { min: 0, max: 10, label: '0-10' },
  // ...
  { min: 90, max: 100, label: '90-100' }
]

// ✅ 修订方案：动态计算区间
function generateBABuckets(min: number, max: number, numBuckets: number = 10) {
  const step = (max - min) / numBuckets
  return Array.from({ length: numBuckets }, (_, i) => ({
    min: min + i * step,
    max: min + (i + 1) * step,
    label: `${(min + i * step).toFixed(1)}-${(min + (i + 1) * step).toFixed(1)}`
  }))
}
```

---

### 3. 类型系统统一（避免双源漂移）

#### 现有结构

```
src/types/
└── api.ts  (OpenAPI 自动生成，1854 行)
```

**当前使用模式**（正确）:
```typescript
import type { components } from '@/types/api'
type RegulationListItem = components['schemas']['RegulationListItem']
```

#### 调整后的结构

```
src/types/
├── api.ts              (OpenAPI 自动生成，不修改)
├── api-extensions.ts   (✅ 新增：扩展类型)
└── index.ts            (✅ 新增：统一导出)
```

**api-extensions.ts**（仅包含新增类型）:

```typescript
import type { components } from './api'

// ============ 复用 OpenAPI 类型（别名） ============
export type Gene = components['schemas']['GeneListItem']
export type Regulation = components['schemas']['RegulationListItem']
export type NetworkNode = components['schemas']['NetworkNode']
export type NetworkEdge = components['schemas']['NetworkEdge']

// ============ 新增类型（历史：早期后端未实现阶段） ============

/**
 * 详细统计信息（用于 Stats 页面图表）
 * 状态：🔴 Mock（后端待实现）
 */
export interface DetailedStatsResponse {
  summary: {
    total_genes: number
    total_lncrna: number
    total_regulations: number
    total_traits: number
    total_species: number
    total_batches: number
  }

  species_distribution: Array<{
    species_id: number
    species_name: string
    gene_count: number
    lncrna_count: number
    regulation_count: number
  }>

  ba_distribution: {
    buckets: Array<{
      min: number
      max: number
      label: string
    }>
    counts: number[]
  }

  top_lncrnas: Array<{
    gene_id: number
    gene_name: string
    gene_ensembl_id: string
    regulation_count: number
    species_name: string
  }>

  top_targets: Array<{
    gene_id: number
    gene_name: string
    gene_ensembl_id: string
    regulated_by_count: number
    species_name: string
  }>
}

/**
 * BA 范围配置
 * 状态：🔴 Mock（后端待实现）
 */
export interface BARange {
  min: number
  max: number
}

/**
 * Regulations 扩展筛选参数
 * 状态：🟡 部分实现（现有 API 支持 min_ba，其他参数待扩展）
 */
export interface RegulationFilterParams {
  // 现有参数（已实现）
  page?: number
  page_size?: number
  min_ba?: number

  // 新增参数（后端待实现）
  max_ba?: number
  species_id?: number[]
  lncrna_gene_name?: string
  target_gene_name?: string
  chromosome?: string[]
  sort_by?: 'binding_affinity' | 'regulation_id' | 'lncrna_gene_name'
  order?: 'asc' | 'desc'
}

/**
 * 导出参数
 */
export interface ExportParams extends RegulationFilterParams {
  format: 'csv' | 'xlsx'
  limit?: number
}
```

**index.ts**（统一导出）:

```typescript
// 导出 OpenAPI 自动生成的类型
export * from './api'

// 导出扩展类型
export * from './api-extensions'

// 类型守卫（可选，用于运行时类型检查）
export const isRegulation = (obj: unknown): obj is Regulation => {
  return typeof obj === 'object' && obj !== null && 'regulation_id' in obj
}
```

**使用规范**:

```typescript
// ✅ 正确：从统一入口导入
import type { Regulation, DetailedStatsResponse, RegulationFilterParams } from '@/types'

// ❌ 错误：直接从 api.ts 导入
import type { components } from '@/types/api'
type Regulation = components['schemas']['RegulationListItem']  // 不要这样
```

---

### 4. 导出路径明确化

#### 决策：前端 + 后端混合导出

| 数据量 | 导出方式 | 格式 | 实现 |
|--------|---------|------|------|
| **< 1000 条** | 前端生成 | XLSX | ✅ Phase 1 |
| **1000 - 10000 条** | 前端生成（带警告） | XLSX/CSV | ✅ Phase 1 |
| **> 10000 条** | 后端生成 | CSV | 🔴 Phase 2 |

#### 实现逻辑

```typescript
// src/utils/export.ts
import { saveAs } from 'file-saver'
import type { RegulationFilterParams } from '@/types'

const EXPORT_LIMITS = {
  WARN: 1000,     // 超过此数量显示警告
  MAX_FRONTEND: 10000,  // 前端导出上限
  MAX_BACKEND: 50000    // 后端导出上限（Phase 2）
}

/**
 * 导出 Regulations（Phase 1：仅前端导出）
 */
export async function exportRegulations(
  filters: RegulationFilterParams,
  format: 'csv' | 'xlsx',
  total: number
) {
  // 1. 数据量检查
  if (total > EXPORT_LIMITS.MAX_FRONTEND) {
    return {
      success: false,
      error: 'DATA_TOO_LARGE',
      total,
      limit: EXPORT_LIMITS.MAX_FRONTEND,
      message: `数据量过大（${total} 条），请缩小筛选范围或联系管理员`
    }
  }

  // 2. 显示警告（可选）
  if (total > EXPORT_LIMITS.WARN) {
    console.warn(`[Export] Large dataset: ${total} records`)
    // 可选：显示 Modal 确认
  }

  try {
    // 3. 获取完整数据（分页获取）
    const allData = await fetchAllRegulations(filters, total)

    // 4. 生成文件
    if (format === 'csv') {
      return exportToCSV(allData)
    } else {
      return await exportToXLSX(allData)  // 动态导入 XLSX
    }
  } catch (error) {
    return {
      success: false,
      error: 'EXPORT_FAILED',
      message: error instanceof Error ? error.message : '导出失败'
    }
  }
}

/**
 * 分页获取所有数据
 */
async function fetchAllRegulations(filters: RegulationFilterParams, total: number) {
  const PAGE_SIZE = 200
  const pages = Math.ceil(total / PAGE_SIZE)
  const allData: any[] = []

  for (let page = 1; page <= pages; page++) {
    const { data } = await apiClient.get('/api/v1/regulations', {
      params: { ...filters, page, page_size: PAGE_SIZE }
    })
    allData.push(...data.items)
  }

  return allData
}

/**
 * 导出为 CSV（前端生成）
 */
function exportToCSV(data: any[]) {
  const escapeCSV = (val: unknown): string => {
    const str = String(val ?? '')
    if (str.includes(',') || str.includes('"') || str.includes('\n')) {
      return `"${str.replace(/"/g, '""')}"`
    }
    return str
  }

  const headers = ['ID', 'lncRNA', 'Target', 'Species', 'Chr', 'Start', 'End', 'BA', 'Peaks']
  const rows = data.map(r => [
    escapeCSV(r.regulation_id),
    escapeCSV(r.lncrna_gene_name),
    escapeCSV(r.target_gene_name),
    escapeCSV(r.species_name),
    escapeCSV(r.target_chromosome),
    escapeCSV(r.target_start),
    escapeCSV(r.target_end),
    escapeCSV(r.binding_affinity),
    escapeCSV(r.num_peaks)
  ].join(','))

  const csv = [headers.join(','), ...rows].join('\n')
  const blob = new Blob([csv], { type: 'text/csv;charset=utf-8;' })
  saveAs(blob, `regulations-${Date.now()}.csv`)

  return { success: true }
}

/**
 * 导出为 XLSX（动态导入库）
 */
async function exportToXLSX(data: any[]) {
  // ✅ 动态导入，减少初始 bundle 大小
  const XLSX = await import('xlsx')

  const worksheet = XLSX.utils.json_to_sheet(data.map(r => ({
    'ID': r.regulation_id,
    'lncRNA': r.lncrna_gene_name,
    'Target': r.target_gene_name,
    'Species': r.species_name,
    'Chr': r.target_chromosome,
    'Start': r.target_start,
    'End': r.target_end,
    'BA': r.binding_affinity,
    'Peaks': r.num_peaks
  })))

  const workbook = XLSX.utils.book_new()
  XLSX.utils.book_append_sheet(workbook, worksheet, 'Regulations')

  XLSX.writeFile(workbook, `regulations-${Date.now()}.xlsx`)

  return { success: true }
}
```

---

### 5. MSW 配置安全性

#### 环境变量配置

```bash
# .env（Git 提交，生产默认值）
VITE_API_BASE_URL=http://<YOUR_SERVER_IP>:6004
VITE_USE_MOCK=false  # ✅ 默认关闭

# .env.development（Git 忽略，开发环境）
VITE_API_BASE_URL=http://localhost:8000
VITE_USE_MOCK=true   # ✅ 开发时启用

# .env.production（Git 忽略，生产环境）
VITE_API_BASE_URL=https://production-api.example.com
VITE_USE_MOCK=false  # ✅ 生产禁用
```

#### 安全启动逻辑

```typescript
// src/main.tsx（修订版）
import React from 'react'
import ReactDOM from 'react-dom/client'
import App from './App'

async function enableMocking() {
  // ✅ 三重检查
  const isDevelopment = import.meta.env.MODE === 'development'
  const mockEnabled = import.meta.env.VITE_USE_MOCK === 'true'
  const isProduction = import.meta.env.PROD

  // 生产环境强制禁用
  if (isProduction) {
    console.log('🚫 Production build: MSW disabled')
    return
  }

  // 开发环境根据环境变量决定
  if (!isDevelopment || !mockEnabled) {
    console.log('🚫 MSW disabled (VITE_USE_MOCK=false)')
    return
  }

  console.warn('⚠️ MSW enabled (Development mode only)')

  const { worker } = await import('./mocks/browser')

  // ✅ 异步启动后再挂载 App
  await worker.start({
    onUnhandledRequest: 'warn',
    quiet: false  // 显示拦截日志，便于调试
  })

  console.log('✅ MSW started successfully')
}

// ✅ 确保 MSW 启动完成后再挂载 React
enableMocking().then(() => {
  ReactDOM.createRoot(document.getElementById('root')!).render(
    <React.StrictMode>
      <App />
    </React.StrictMode>
  )
})
```

---

### 6. Bundle 优化策略

#### 目标

| Chunk | 目标大小 (gzip) | 优化手段 |
|-------|----------------|---------|
| **main** | < 500 KB | 代码分割、Tree shaking |
| **echarts** | < 300 KB | 按需导入组件 |
| **xlsx** | < 200 KB | 动态 import |
| **总计** | < 1.5 MB | manualChunks 配置 |

#### ECharts 按需导入配置

```typescript
// src/utils/echarts.ts（修订版，基于 ECharts 6）
import * as echarts from 'echarts/core'
import { PieChart, BarChart } from 'echarts/charts'
import {
  TitleComponent,
  TooltipComponent,
  LegendComponent,
  GridComponent
} from 'echarts/components'
import { CanvasRenderer } from 'echarts/renderers'

// ✅ 注册所需组件（按需）
echarts.use([
  PieChart,
  BarChart,
  TitleComponent,
  TooltipComponent,
  LegendComponent,
  GridComponent,
  CanvasRenderer
])

export default echarts
```

#### Vite 配置

```typescript
// vite.config.ts（新增 bundle 优化）
import { defineConfig } from 'vite'
import react from '@vitejs/plugin-react'
import { visualizer } from 'rollup-plugin-visualizer'

export default defineConfig({
  plugins: [
    react(),
    // Bundle 分析（仅在需要时启用）
    process.env.ANALYZE === 'true' && visualizer({
      filename: 'dist/stats.html',
      open: true,
      gzipSize: true
    })
  ],

  build: {
    rollupOptions: {
      output: {
        // ✅ 手动分包
        manualChunks(id) {
          // Vendor 分离
          if (id.includes('node_modules')) {
            if (id.includes('echarts')) return 'echarts'
            if (id.includes('xlsx')) return 'xlsx'
            if (id.includes('antd')) return 'antd'
            if (id.includes('react') || id.includes('react-dom')) return 'react'
            return 'vendor'
          }
        }
      }
    },

    // 代码压缩配置
    minify: 'terser',
    terserOptions: {
      compress: {
        drop_console: true,  // 生产环境移除 console
        drop_debugger: true
      }
    },

    // Chunk 大小警告阈值
    chunkSizeWarningLimit: 600  // KB
  }
})
```

#### 验证脚本

```json
// package.json（新增脚本）
{
  "scripts": {
    "dev": "vite",
    "build": "tsc -b && vite build",
    "analyze": "ANALYZE=true npm run build",
    "preview": "vite preview"
  }
}
```

---

## 📋 修订后的实施清单

### Phase 1A: 前置准备（30min）

#### 1. 依赖安装
```bash
cd <repo-root>/frontend/web

# ✅ 仅安装缺失的依赖
npm install msw --save-dev
npm install xlsx
npm install -D rollup-plugin-visualizer

# 初始化 MSW
npx msw init public/ --save
```

#### 2. 环境变量配置
```bash
# 更新 .env
echo "VITE_USE_MOCK=false" >> .env

# 更新 .env.development
echo "VITE_USE_MOCK=true" >> .env.development
```

#### 3. 创建文件结构
```bash
# 类型定义
touch src/types/api-extensions.ts
touch src/types/index.ts

# Mock 配置
mkdir -p src/mocks/data
touch src/mocks/browser.ts
touch src/mocks/server.ts
touch src/mocks/handlers.ts
touch src/mocks/data/stats.mock.ts

# 工具函数
mkdir -p src/utils
touch src/utils/echarts.ts
touch src/utils/export.ts
touch src/config/constants.ts

# Hooks
touch src/hooks/useDetailedStats.ts

# Stats 组件
mkdir -p src/pages/Stats/components
touch src/pages/Stats/components/SpeciesChart.tsx
touch src/pages/Stats/components/BAChart.tsx
touch src/pages/Stats/components/TopLncRNAChart.tsx

# Regulations 组件
mkdir -p src/pages/Regulations/components
touch src/pages/Regulations/components/AdvancedFilters.tsx
```

**验证清单**:
- [ ] `public/mockServiceWorker.js` 已生成
- [ ] `.env.development` 包含 `VITE_USE_MOCK=true`
- [ ] 文件结构创建完成

---

### Phase 1B: 类型系统（15min）

#### 1. 创建类型定义

**文件**: `src/types/api-extensions.ts`（使用上面"类型系统统一"一节的完整代码）

**文件**: `src/types/index.ts`
```typescript
export * from './api'
export * from './api-extensions'
```

**文件**: `src/config/constants.ts`
```typescript
// BA 范围配置（静态回退；优先从 /api/v1/stats/ba-range 动态获取）
export const BA_CONFIG = {
  MIN: 50,
  MAX: 756,  // 实际数据 max 约 755.99（四舍五入取整）
  STEP: 1,
  DEFAULT_MIN: undefined,
  DEFAULT_MAX: undefined,
  HISTOGRAM_BUCKETS: 10  // 直方图区间数量
}

export const EXPORT_LIMITS = {
  WARN: 1000,
  MAX_FRONTEND: 10000,
  MAX_BACKEND: 50000
}

export const SPECIES_OPTIONS = [
  { label: '人类', value: 1 },
  { label: '黑猩猩', value: 2 },
  { label: '猕猴', value: 3 },
  { label: '狨猴', value: 4 }
]

export const CHROMOSOME_OPTIONS = [
  'chr1', 'chr2', 'chr3', 'chr4', 'chr5', 'chr6', 'chr7', 'chr8', 'chr9', 'chr10',
  'chr11', 'chr12', 'chr13', 'chr14', 'chr15', 'chr16', 'chr17', 'chr18', 'chr19',
  'chr20', 'chr21', 'chr22', 'chrX', 'chrY'
].map(chr => ({ label: chr, value: chr }))
```

**验证**:
```bash
npm run type-check  # 应该无错误
```

---

### Phase 1C: MSW 配置（30min）

#### 1. Mock 数据

> 更新（2026-01）：Stats API 已实现真实后端，MSW Mock 已移除；仓库中 `src/mocks/*` 目前仅保留空框架与占位文件（见 `frontend/web/src/mocks/handlers.ts`、`frontend/web/src/mocks/data/stats.mock.ts`）。以下内容为历史示例，供参考。

**文件**: `src/mocks/data/stats.mock.ts`（历史示例：原方案 mockDetailedStats）

```typescript
import type { DetailedStatsResponse } from '@/types'
import { BA_CONFIG } from '@/config/constants'

// ✅ 动态生成 BA 区间
function generateBABuckets(min: number, max: number, numBuckets: number) {
  const step = (max - min) / numBuckets
  return Array.from({ length: numBuckets }, (_, i) => ({
    min: min + i * step,
    max: min + (i + 1) * step,
    label: `${(min + i * step).toFixed(1)}-${(min + (i + 1) * step).toFixed(1)}`
  }))
}

export const mockDetailedStats: DetailedStatsResponse = {
  summary: {
    total_genes: 80234,
    total_lncrna: 28456,
    total_regulations: 1234567,
    total_traits: 150,
    total_species: 4,
    total_batches: 12
  },

  species_distribution: [
    { species_id: 1, species_name: '人类', gene_count: 35000, lncrna_count: 12000, regulation_count: 560000 },
    { species_id: 2, species_name: '黑猩猩', gene_count: 28000, lncrna_count: 9500, regulation_count: 380000 },
    { species_id: 3, species_name: '猕猴', gene_count: 10000, lncrna_count: 4200, regulation_count: 200000 },
    { species_id: 4, species_name: '狨猴', gene_count: 7234, lncrna_count: 2756, regulation_count: 94567 }
  ],

  ba_distribution: {
    buckets: generateBABuckets(BA_CONFIG.MIN, BA_CONFIG.MAX, BA_CONFIG.HISTOGRAM_BUCKETS),
    counts: [5234, 12456, 45678, 123456, 234567, 345678, 256789, 123456, 45678, 12345]
  },

  top_lncrnas: [
    { gene_id: 1001, gene_name: 'H19', gene_ensembl_id: 'ENSG00000130600', regulation_count: 1234, species_name: '人类' },
    { gene_id: 1002, gene_name: 'MALAT1', gene_ensembl_id: 'ENSG00000251562', regulation_count: 987, species_name: '人类' },
    { gene_id: 1003, gene_name: 'NEAT1', gene_ensembl_id: 'ENSG00000245532', regulation_count: 856, species_name: '人类' },
    { gene_id: 1004, gene_name: 'XIST', gene_ensembl_id: 'ENSG00000229807', regulation_count: 743, species_name: '人类' },
    { gene_id: 1005, gene_name: 'MEG3', gene_ensembl_id: 'ENSG00000214548', regulation_count: 678, species_name: '人类' },
    { gene_id: 1006, gene_name: 'HOTAIR', gene_ensembl_id: 'ENSG00000228630', regulation_count: 623, species_name: '人类' },
    { gene_id: 1007, gene_name: 'GAS5', gene_ensembl_id: 'ENSG00000234741', regulation_count: 589, species_name: '人类' },
    { gene_id: 1008, gene_name: 'TUG1', gene_ensembl_id: 'ENSG00000253352', regulation_count: 512, species_name: '黑猩猩' },
    { gene_id: 1009, gene_name: 'DANCR', gene_ensembl_id: 'ENSG00000226950', regulation_count: 478, species_name: '人类' },
    { gene_id: 1010, gene_name: 'LINC00152', gene_ensembl_id: 'ENSG00000245694', regulation_count: 445, species_name: '人类' }
  ],

  top_targets: [
    { gene_id: 2001, gene_name: 'TP53', gene_ensembl_id: 'ENSG00000141510', regulated_by_count: 856, species_name: '人类' },
    { gene_id: 2002, gene_name: 'MYC', gene_ensembl_id: 'ENSG00000136997', regulated_by_count: 743, species_name: '人类' },
    { gene_id: 2003, gene_name: 'EGFR', gene_ensembl_id: 'ENSG00000146648', regulated_by_count: 678, species_name: '人类' },
    { gene_id: 2004, gene_name: 'KRAS', gene_ensembl_id: 'ENSG00000133703', regulated_by_count: 623, species_name: '人类' },
    { gene_id: 2005, gene_name: 'BRCA1', gene_ensembl_id: 'ENSG00000012048', regulated_by_count: 589, species_name: '人类' },
    { gene_id: 2006, gene_name: 'VEGFA', gene_ensembl_id: 'ENSG00000112715', regulated_by_count: 512, species_name: '人类' },
    { gene_id: 2007, gene_name: 'BCL2', gene_ensembl_id: 'ENSG00000171791', regulated_by_count: 478, species_name: '黑猩猩' },
    { gene_id: 2008, gene_name: 'PTEN', gene_ensembl_id: 'ENSG00000171862', regulated_by_count: 445, species_name: '人类' },
    { gene_id: 2009, gene_name: 'RB1', gene_ensembl_id: 'ENSG00000139687', regulated_by_count: 412, species_name: '人类' },
    { gene_id: 2010, gene_name: 'APC', gene_ensembl_id: 'ENSG00000134982', regulated_by_count: 389, species_name: '人类' }
  ]
}
```

#### 2. Handlers

**文件**: `src/mocks/handlers.ts`
```typescript
import { http, HttpResponse } from 'msw'
import type { DetailedStatsResponse } from '@/types'
import { mockDetailedStats } from './data/stats.mock'

export const handlers = [
  // Stats API
  http.get('/api/v1/stats/detailed', () => {
    console.log('📊 [MSW] GET /api/v1/stats/detailed')
    return HttpResponse.json<DetailedStatsResponse>(mockDetailedStats)
  })
]
```

**文件**: `src/mocks/browser.ts`
```typescript
import { setupWorker } from 'msw/browser'
import { handlers } from './handlers'

export const worker = setupWorker(...handlers)
```

**文件**: `src/mocks/server.ts`（测试环境用）
```typescript
import { setupServer } from 'msw/node'
import { handlers } from './handlers'

export const server = setupServer(...handlers)
```

#### 3. 集成到主入口

**文件**: `src/main.tsx`（使用上面"MSW 配置安全性"一节的代码）

**验证**:
```bash
npm run dev
# 打开浏览器控制台，应该看到：
# ⚠️ MSW enabled (Development mode only)
# ✅ MSW started successfully
```

---

### Phase 1D: Stats 页面（2.5h）

#### 1. ECharts 配置

**文件**: `src/utils/echarts.ts`（使用上面"Bundle 优化策略"一节的代码）

#### 2. Hook

**文件**: `src/hooks/useDetailedStats.ts`
```typescript
import { useQuery } from '@tanstack/react-query'
import { apiClient } from '@/api/client'
import type { DetailedStatsResponse } from '@/types'

export function useDetailedStats() {
  return useQuery({
    queryKey: ['stats-detailed'],
    queryFn: async () => {
      const { data } = await apiClient.get<DetailedStatsResponse>('/api/v1/stats/detailed')
      return data
    },
    staleTime: 10 * 60 * 1000  // 10分钟缓存
  })
}
```

#### 3. 图表组件

**文件**: `src/pages/Stats/components/SpeciesChart.tsx`（使用原方案代码，无需修改）

**文件**: `src/pages/Stats/components/BAChart.tsx`（使用原方案代码，无需修改）

**文件**: `src/pages/Stats/components/TopLncRNAChart.tsx`（使用原方案代码，无需修改）

#### 4. 主页面

**文件**: `src/pages/Stats/index.tsx`（使用原方案代码，但 Suspense fallback 调整）

```typescript
import { lazy, Suspense } from 'react'
import { Card, Row, Col, Spin, Statistic } from 'antd'
import { useDetailedStats } from '@/hooks/useDetailedStats'
import { LoadingState } from '@/components/LoadingState'
import { ErrorState } from '@/components/ErrorState'

const SpeciesChart = lazy(() => import('./components/SpeciesChart').then(m => ({ default: m.SpeciesChart })))
const BAChart = lazy(() => import('./components/BAChart').then(m => ({ default: m.BAChart })))
const TopLncRNAChart = lazy(() => import('./components/TopLncRNAChart').then(m => ({ default: m.TopLncRNAChart })))

export default function Stats() {
  const { data, isLoading, error } = useDetailedStats()

  if (isLoading) return <LoadingState />
  if (error) return <ErrorState error={error} />
  if (!data) return null

  const ChartFallback = () => (
    <div style={{ display: 'flex', justifyContent: 'center', alignItems: 'center', height: 400 }}>
      <Spin size="large" />
    </div>
  )

  return (
    <div style={{ padding: 24 }}>
      <h1>数据库统计概览</h1>

      {/* 统计卡片 */}
      <Row gutter={16} style={{ marginTop: 24, marginBottom: 32 }}>
        <Col xs={12} sm={8} md={4}>
          <Card><Statistic title="总基因数" value={data.summary.total_genes} /></Card>
        </Col>
        <Col xs={12} sm={8} md={4}>
          <Card><Statistic title="lncRNA" value={data.summary.total_lncrna} /></Card>
        </Col>
        <Col xs={12} sm={8} md={4}>
          <Card><Statistic title="调控关系" value={data.summary.total_regulations} /></Card>
        </Col>
        <Col xs={12} sm={8} md={4}>
          <Card><Statistic title="疾病关联" value={data.summary.total_traits} /></Card>
        </Col>
        <Col xs={12} sm={8} md={4}>
          <Card><Statistic title="物种" value={data.summary.total_species} /></Card>
        </Col>
        <Col xs={12} sm={8} md={4}>
          <Card><Statistic title="批次" value={data.summary.total_batches} /></Card>
        </Col>
      </Row>

      {/* 数据分布 */}
      <h2 style={{ marginBottom: 16 }}>📈 数据分布</h2>
      <Row gutter={16} style={{ marginBottom: 32 }}>
        <Col xs={24} lg={12}>
          <Card>
            <Suspense fallback={<ChartFallback />}>
              <SpeciesChart data={data.species_distribution} />
            </Suspense>
          </Card>
        </Col>
        <Col xs={24} lg={12}>
          <Card>
            <Suspense fallback={<ChartFallback />}>
              <BAChart data={data.ba_distribution} />
            </Suspense>
          </Card>
        </Col>
      </Row>

      {/* Top 排行榜 */}
      <h2 style={{ marginBottom: 16 }}>🏆 Top 10 榜单</h2>
      <Row gutter={16}>
        <Col xs={24} xl={12}>
          <Card title="Top 10 调控最多的 lncRNA">
            <Suspense fallback={<ChartFallback />}>
              <TopLncRNAChart data={data.top_lncrnas} />
            </Suspense>
          </Card>
        </Col>
        <Col xs={24} xl={12}>
          <Card title="Top 10 被调控最多的靶基因">
            <Suspense fallback={<ChartFallback />}>
              <TopLncRNAChart data={data.top_targets} />
            </Suspense>
          </Card>
        </Col>
      </Row>
    </div>
  )
}
```

**验证**:
```bash
npm run dev
# 访问 /stats 页面，检查：
# 1. 6个统计卡片正常显示
# 2. 3个图表正常渲染
# 3. 控制台无错误
```

---

### Phase 1E: Regulations 筛选器（1.5h）

#### 1. 筛选器组件

**文件**: `src/pages/Regulations/components/AdvancedFilters.tsx`（使用 AntD 6 的 Collapse items API）

```typescript
import { Form, Select, Input, Slider, Collapse, Button, Space } from 'antd'
import { FilterOutlined } from '@ant-design/icons'
import type { RegulationFilterParams } from '@/types'
import { BA_CONFIG, SPECIES_OPTIONS, CHROMOSOME_OPTIONS } from '@/config/constants'

interface AdvancedFiltersProps {
  filters: RegulationFilterParams
  onFilterChange: (key: keyof RegulationFilterParams, value: any) => void
  onReset: () => void
}

export const AdvancedFilters: React.FC<AdvancedFiltersProps> = ({
  filters,
  onFilterChange,
  onReset
}) => {
  return (
    <Collapse
      size="small"
      style={{ marginBottom: 16 }}
      items={[
        {
          key: 'filters',
          label: (
            <Space>
              <FilterOutlined />
              <span>高级筛选</span>
            </Space>
          ),
          children: (
            <Form layout="vertical">
              <Space direction="vertical" style={{ width: '100%' }} size="middle">
                {/* 物种筛选 */}
                <Form.Item label="物种" style={{ marginBottom: 0 }}>
                  <Select
                    mode="multiple"
                    placeholder="选择物种"
                    value={filters.species_id}
                    onChange={(val) => onFilterChange('species_id', val)}
                    options={SPECIES_OPTIONS}
                    style={{ width: '100%' }}
                    maxTagCount="responsive"
                    allowClear
                  />
                </Form.Item>

                {/* 基因搜索 */}
                <Space style={{ width: '100%' }}>
                  <Form.Item label="lncRNA 基因名" style={{ marginBottom: 0, flex: 1 }}>
                    <Input
                      placeholder="例: H19, MALAT1"
                      value={filters.lncrna_gene_name}
                      onChange={(e) => onFilterChange('lncrna_gene_name', e.target.value)}
                      allowClear
                    />
                  </Form.Item>

                  <Form.Item label="靶基因名" style={{ marginBottom: 0, flex: 1 }}>
                    <Input
                      placeholder="例: TP53, MYC"
                      value={filters.target_gene_name}
                      onChange={(e) => onFilterChange('target_gene_name', e.target.value)}
                      allowClear
                    />
                  </Form.Item>
                </Space>

                {/* 染色体筛选 */}
                <Form.Item label="染色体" style={{ marginBottom: 0 }}>
                  <Select
                    mode="multiple"
                    placeholder="选择染色体"
                    value={filters.chromosome}
                    onChange={(val) => onFilterChange('chromosome', val)}
                    options={CHROMOSOME_OPTIONS}
                    style={{ width: '100%' }}
                    maxTagCount="responsive"
                    allowClear
                  />
                </Form.Item>

                {/* BA 范围 */}
                <Form.Item
                  label={`Binding Affinity 范围: ${filters.min_ba ?? BA_CONFIG.DEFAULT_MIN} - ${filters.max_ba ?? BA_CONFIG.DEFAULT_MAX}`}
                  style={{ marginBottom: 0 }}
                >
                  <Slider
                    range
                    min={BA_CONFIG.MIN}
                    max={BA_CONFIG.MAX}
                    step={BA_CONFIG.STEP}
                    value={[
                      filters.min_ba ?? BA_CONFIG.DEFAULT_MIN,
                      filters.max_ba ?? BA_CONFIG.DEFAULT_MAX
                    ]}
                    onChange={(val) => {
                      onFilterChange('min_ba', val[0])
                      onFilterChange('max_ba', val[1])
                    }}
                    marks={{
                      [BA_CONFIG.MIN]: BA_CONFIG.MIN.toString(),
                      25: '25',
                      50: '50',
                      75: '75',
                      [BA_CONFIG.MAX]: BA_CONFIG.MAX.toString()
                    }}
                  />
                </Form.Item>

                {/* 操作按钮 */}
                <Button onClick={onReset}>重置筛选</Button>
              </Space>
            </Form>
          )
        }
      ]}
    />
  )
}
```

#### 2. 主页面集成

**文件**: `src/pages/Regulations/index.tsx`（扩展现有代码）

```typescript
import { useState } from 'react'
import { Table, Button, Dropdown, Space, message, Modal } from 'antd'
import { DownloadOutlined } from '@ant-design/icons'
import type { TableProps, MenuProps } from 'antd'
import { useRegulations } from '@/hooks/useRegulations'
import { LoadingState } from '@/components/LoadingState'
import { ErrorState } from '@/components/ErrorState'
import { AdvancedFilters } from './components/AdvancedFilters'
import { exportRegulations } from '@/utils/export'
import type { Regulation, RegulationFilterParams } from '@/types'

export default function Regulations() {
  const [page, setPage] = useState(1)
  const [pageSize, setPageSize] = useState(100)
  const [filters, setFilters] = useState<RegulationFilterParams>({})

  const { data, isLoading, error } = useRegulations({
    page,
    page_size: pageSize,
    ...filters
  })

  // 更新单个筛选器
  const updateFilter = (key: keyof RegulationFilterParams, value: any) => {
    setFilters(prev => ({ ...prev, [key]: value }))
    setPage(1)  // 重置到第一页
  }

  // 重置筛选器
  const resetFilters = () => {
    setFilters({})
    setPage(1)
  }

  // 导出功能
  const handleExport = async (format: 'csv' | 'xlsx') => {
    const total = data?.total || 0

    if (total === 0) {
      message.warning('没有可导出的数据')
      return
    }

    const result = await exportRegulations(filters, format, total)

    if (!result.success) {
      if (result.error === 'DATA_TOO_LARGE') {
        Modal.warning({
          title: '数据量过大',
          content: `筛选结果共 ${result.total} 条记录，超过导出限制（${result.limit} 条）。请缩小筛选范围后重试。`,
          okText: '知道了'
        })
      } else {
        message.error(result.message || '导出失败')
      }
    } else {
      message.success('导出成功')
    }
  }

  const exportMenuItems: MenuProps['items'] = [
    {
      key: 'csv',
      label: '导出为 CSV',
      onClick: () => handleExport('csv')
    },
    {
      key: 'xlsx',
      label: '导出为 XLSX',
      onClick: () => handleExport('xlsx')
    }
  ]

  const columns: TableProps<Regulation>['columns'] = [
    { title: 'ID', dataIndex: 'regulation_id', width: 100 },
    { title: 'lncRNA', dataIndex: 'lncrna_gene_name', width: 150 },
    { title: 'Target Gene', dataIndex: 'target_gene_name', width: 150 },
    { title: 'Species', dataIndex: 'species_name', width: 100 },
    { title: 'Chr', dataIndex: 'target_chromosome', width: 80 },
    { title: 'Start', dataIndex: 'target_start', width: 120 },
    { title: 'End', dataIndex: 'target_end', width: 120 },
    { title: 'BA', dataIndex: 'binding_affinity', width: 100 },
    { title: 'Peaks', dataIndex: 'num_peaks', width: 80 },
  ]

  if (isLoading) return <LoadingState />
  if (error) return <ErrorState error={error} />

  return (
    <div style={{ padding: 24 }}>
      <Space style={{ marginBottom: 16, width: '100%', justifyContent: 'space-between' }}>
        <h1 style={{ margin: 0 }}>调控关系</h1>
        <Dropdown menu={{ items: exportMenuItems }}>
          <Button icon={<DownloadOutlined />}>
            导出数据
          </Button>
        </Dropdown>
      </Space>

      <AdvancedFilters
        filters={filters}
        onFilterChange={updateFilter}
        onReset={resetFilters}
      />

      <Table
        columns={columns}
        dataSource={data?.items}
        rowKey="regulation_id"
        pagination={{
          current: page,
          pageSize,
          total: data?.total,
          showSizeChanger: true,
          showTotal: (total) => `共 ${total} 条`,
          onChange: (p, ps) => {
            setPage(p)
            setPageSize(ps)
          },
        }}
      />
    </div>
  )
}
```

**验证**:
```bash
# 1. 测试筛选功能
- 选择物种 → 数据更新
- 输入基因名 → 数据过滤
- 调整 BA 范围 → 数据变化

# 2. 测试重置
- 点击"重置筛选" → 所有筛选条件清空

# 3. 测试分页
- 切换页码 → 数据更新
```

---

### Phase 1F: 导出功能（1h）

#### 1. 工具函数

**文件**: `src/utils/export.ts`（使用上面"导出路径明确化"一节的完整代码）

#### 2. 验证

```bash
# 1. 正常导出
- 点击"导出数据" → 选择 CSV/XLSX → 下载文件
- 打开文件 → 数据正确

# 2. 空结果导出
- 筛选到 0 条结果
- 点击导出 → 提示"没有可导出的数据"

# 3. 大数据量导出
- Mock 返回 total > 10000
- 点击导出 → 显示 Modal 提示
```

---

### Phase 1G: Vite 配置优化（15min）

**文件**: `vite.config.ts`（使用上面"Bundle 优化策略"一节的代码）

**验证**:
```bash
npm run build
npm run analyze  # 查看 bundle 分析报告

# 检查：
# 1. dist/stats.html 打开
# 2. echarts chunk < 300 KB
# 3. xlsx chunk < 200 KB
# 4. 总大小 < 1.5 MB
```

---

## 📊 实施时间估算

| 阶段 | 任务 | 时间 | 累计 |
|------|------|------|------|
| **1A** | 前置准备 | 30min | 0.5h |
| **1B** | 类型系统 | 15min | 0.75h |
| **1C** | MSW 配置 | 30min | 1.25h |
| **1D** | Stats 页面 | 2.5h | 3.75h |
| **1E** | Regulations 筛选 | 1.5h | 5.25h |
| **1F** | 导出功能 | 1h | 6.25h |
| **1G** | Bundle 优化 | 15min | 6.5h |
| **总计** | - | **6.5h** | - |

---

## 🎯 关键决策总结

| 决策点 | 选择 | 理由 |
|--------|------|------|
| **React/AntD 版本** | 按实际版本（19/6）调整 | 避免兼容性问题 |
| **BA 范围** | 配置化（Phase 1）→ 动态（Phase 2） | 降低初期依赖，后续优化 |
| **类型定义** | api-extensions.ts 扩展 | 避免双源漂移 |
| **导出路径** | 前端（<10000）+ 后端（Phase 2） | 快速落地，渐进增强 |
| **MSW 环境** | 开发启用，生产禁用 | 安全第一 |
| **Bundle 优化** | 按需导入 + 动态 import | 满足 1.5MB 目标 |

---

## 🚀 下一步行动

1. **确认 BA 实际范围**：
   ```sql
   SELECT MIN(binding_affinity), MAX(binding_affinity) FROM regulations;
   ```
   如果 MAX > 100，更新 `BA_CONFIG.MAX`。

2. **开始实施**：按照清单从 Phase 1A 开始。

3. **验收标准**：
   - [ ] Stats 页面 3 个图表正常显示
   - [ ] Regulations 高级筛选功能正常
   - [ ] 导出 CSV/XLSX 成功
   - [ ] Bundle 大小 < 1.5MB
   - [ ] 生产环境 MSW 已禁用

---

**文档版本**: v2.0
**最后更新**: 2025-11-27
**作者**: Claude Code
**状态**: ✅ 技术栈已对齐，待实施
