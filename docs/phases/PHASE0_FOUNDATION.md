# Phase 0: 前置基础建设（必须先完成）

**项目**: Human LncRNA Atlas - 前置基础
**优先级**: 🔴 P0（阻塞 Phase 1 的基础设施）
**预计时间**: 1.5 小时
**状态**: 🗄️ 历史归档（Phase 0 已完成）

---

> 更新（2026-01）：本文档为早期“计划/清单”保留稿。当前项目已进入 Phase 3.x，Stats/Regulations 等核心 API 已实现，MSW Mock 已移除或仅保留空框架。\
> 文中出现的 “Mock/后端待实现/未实现” 等描述仅代表当时阶段，请以 `docs/CURRENT_STATUS.md` 与代码实现为准。

## 🎯 目标

完成以下 4 个基础任务，为 Phase 1 开发扫清障碍：

1. ✅ **统一类型出口** + 按需导入封装
2. ✅ **MSW 启动顺序**（安全启动，避免首屏报错）
3. ✅ **BA 范围配置**（统一配置，供 Slider/直方图使用）
4. ✅ **导出上限与提示**（前端分页 fetch + UI 校验）

---

## 📋 Phase 0 任务清单

### Task 1: 统一类型出口（30min）

#### 1.1 创建类型扩展文件

**文件**: `src/types/api-extensions.ts`

```typescript
import type { components } from './api'

// ============ 复用 OpenAPI 类型（别名，方便使用） ============
export type Gene = components['schemas']['GeneListItem']
export type GeneDetail = components['schemas']['GeneDetail']
export type Regulation = components['schemas']['RegulationListItem']
export type RegulationDetail = components['schemas']['RegulationDetail']
export type NetworkNode = components['schemas']['NetworkNode']
export type NetworkEdge = components['schemas']['NetworkEdge']
export type NetworkData = components['schemas']['NetworkData']
export type Trait = components['schemas']['TraitListItem']

// 分页响应类型
export type PaginatedResponse<T> = {
  items: T[]
  total: number
  page: number
  page_size: number
  total_pages: number
}

// ============ 新增类型（历史：早期后端未实现阶段） ============

/**
 * 详细统计信息（用于 Stats 页面图表）
 * 状态：✅ 已实现（历史说明）
 * API: GET /api/v1/stats/detailed
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
 * 状态：✅ 已实现（历史说明）
 * API: GET /api/v1/stats/ba-range
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

  // 新增参数（后端待实现，Phase 1 暂不使用）
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

/**
 * 导出结果
 */
export type ExportResult =
  | { success: true }
  | {
      success: false
      error: 'DATA_TOO_LARGE' | 'EXPORT_FAILED' | 'NO_DATA'
      total?: number
      limit?: number
      message?: string
    }
```

#### 1.2 创建统一导出文件

**文件**: `src/types/index.ts`

```typescript
/**
 * 类型系统统一导出文件
 *
 * ⚠️ 重要规范：
 * 1. 所有组件必须从 '@/types' 导入类型，禁止直接从 './api' 导入
 * 2. OpenAPI 生成的 types/api.ts 不应直接修改，扩展类型放在 api-extensions.ts
 * 3. 使用 ESLint 规则强制执行：no-restricted-imports
 */

// ============ 导出 OpenAPI 自动生成的类型 ============
export * from './api'

// ============ 导出扩展类型 ============
export * from './api-extensions'

// ============ 导出其他模块类型 ============
export * from './network'

// ============ 类型守卫（可选，用于运行时类型检查） ============
export const isRegulation = (obj: unknown): obj is import('./api-extensions').Regulation => {
  return typeof obj === 'object' && obj !== null && 'regulation_id' in obj
}

export const isPaginatedResponse = <T>(obj: unknown): obj is import('./api-extensions').PaginatedResponse<T> => {
  return (
    typeof obj === 'object' &&
    obj !== null &&
    'items' in obj &&
    'total' in obj &&
    'page' in obj &&
    'page_size' in obj
  )
}
```

#### 1.3 配置 ESLint 禁止直接引用

**文件**: `eslint.config.js`（新增规则）

```javascript
import js from '@eslint/js'
import globals from 'globals'
import reactHooks from 'eslint-plugin-react-hooks'
import reactRefresh from 'eslint-plugin-react-refresh'
import tseslint from 'typescript-eslint'

export default tseslint.config(
  { ignores: ['dist'] },
  {
    extends: [js.configs.recommended, ...tseslint.configs.recommended],
    files: ['**/*.{ts,tsx}'],
    languageOptions: {
      ecmaVersion: 2020,
      globals: globals.browser,
    },
    plugins: {
      'react-hooks': reactHooks,
      'react-refresh': reactRefresh,
    },
    rules: {
      ...reactHooks.configs.recommended.rules,
      'react-refresh/only-export-components': [
        'warn',
        { allowConstantExport: true },
      ],

      // ✅ 新增：禁止直接从 api.ts 导入
      'no-restricted-imports': [
        'error',
        {
          patterns: [
            {
              group: ['**/types/api'],
              message: '禁止直接从 types/api.ts 导入，请使用 @/types 统一入口'
            }
          ]
        }
      ]
    },
  },
)
```

#### 1.4 按需导入封装

**文件**: `src/utils/echarts.ts`

```typescript
/**
 * ECharts 按需导入配置（基于 ECharts 6）
 *
 * ⚠️ 重要：仅导入需要的组件，避免 bundle 膨胀
 * 当前导入：PieChart, BarChart (共约 280KB gzip)
 */

import * as echarts from 'echarts/core'

// ============ 图表类型 ============
import { PieChart, BarChart } from 'echarts/charts'

// ============ 组件 ============
import {
  TitleComponent,
  TooltipComponent,
  LegendComponent,
  GridComponent
} from 'echarts/components'

// ============ 渲染器 ============
import { CanvasRenderer } from 'echarts/renderers'

// ============ 类型定义 ============
import type {
  PieSeriesOption,
  BarSeriesOption
} from 'echarts/charts'

import type {
  TitleComponentOption,
  TooltipComponentOption,
  LegendComponentOption,
  GridComponentOption
} from 'echarts/components'

// 组合选项类型
export type ECOption = echarts.ComposeOption<
  | PieSeriesOption
  | BarSeriesOption
  | TitleComponentOption
  | TooltipComponentOption
  | LegendComponentOption
  | GridComponentOption
>

// ============ 注册组件 ============
echarts.use([
  PieChart,
  BarChart,
  TitleComponent,
  TooltipComponent,
  LegendComponent,
  GridComponent,
  CanvasRenderer
])

// ✅ 验证导出
console.log('✅ ECharts initialized:', {
  version: echarts.version,
  components: ['PieChart', 'BarChart', 'Title', 'Tooltip', 'Legend', 'Grid', 'Canvas']
})

export default echarts
```

> 更新（2026-01-23）：以下为历史验收清单，保留用于回溯，不作为当前待办。

**验证清单（历史）**:
- [x] `src/types/api-extensions.ts` 创建成功（历史记录）
- [x] `src/types/index.ts` 统一导出（历史记录）
- [x] `eslint.config.js` 添加 no-restricted-imports 规则（历史记录）
- [x] `src/utils/echarts.ts` 按需导入配置（历史记录）
- [x] 运行 `npm run lint` 无错误（历史记录）

---

### Task 2: MSW 安全启动（30min）

> 更新（2026-01-23）：真实 API 已上线，MSW Mock 已移除（仅保留空 handlers）。以下步骤为历史记录，仅供参考。

#### 2.1 环境变量配置

**文件**: `.env`（Git 提交，生产默认值）

```bash
# API 配置
VITE_API_BASE_URL=http://<YOUR_SERVER_IP>:6004

# MSW 配置（生产默认关闭）
VITE_USE_MOCK=false
```

**文件**: `.env.development`（已存在，更新）

```bash
# 开发环境配置
VITE_API_BASE_URL=http://localhost:8000

# ✅ 开发环境启用 MSW
VITE_USE_MOCK=true
```

**文件**: `.gitignore`（确保环境文件配置正确）

```bash
# 环境变量
.env.local
.env.development.local
.env.production.local

# ⚠️ 注意：.env 和 .env.development 应该提交到 Git
# 只忽略 .local 后缀的文件
```

#### 2.2 MSW Handlers（先创建空框架）

**文件**: `src/mocks/handlers.ts`

```typescript
import { http, HttpResponse } from 'msw'
import type { DetailedStatsResponse } from '@/types'

/**
 * MSW API Handlers
 *
 * ⚠️ 状态说明（历史）：
 * - ✅ 当前：真实 API 已上线，Mock 已移除（仅保留空 handlers）
 * - 🧭 以下内容为历史示例
 */

export const handlers = [
  // ============ Stats API（历史示例） ============
  http.get('/api/v1/stats/detailed', () => {
    console.log('📊 [MSW] GET /api/v1/stats/detailed')

    // ✅ 已废弃：Stats API 已实现，不再需要 mockDetailedStats（见 src/mocks/handlers.ts）
    return HttpResponse.json<DetailedStatsResponse>({
      summary: {
        total_genes: 0,
        total_lncrna: 0,
        total_regulations: 0,
        total_traits: 0,
        total_species: 0,
        total_batches: 0
      },
      species_distribution: [],
      ba_distribution: { buckets: [], counts: [] },
      top_lncrnas: [],
      top_targets: []
    })
  }),

  // ============ BA Range API（历史示例） ============
  http.get('/api/v1/stats/ba-range', () => {
    console.log('📊 [MSW] GET /api/v1/stats/ba-range')

    return HttpResponse.json({
      min: 50,
      max: 756  // 历史示例：当前后端会返回真实范围（约 50-756）
    })
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

#### 2.3 安全启动逻辑

**文件**: `src/main.tsx`（完整替换）

```typescript
import React from 'react'
import ReactDOM from 'react-dom/client'
import App from './App'
import './index.css'

/**
 * MSW 启动逻辑
 *
 * ✅ 安全检查：
 * 1. 生产环境强制禁用（import.meta.env.PROD）
 * 2. 开发环境根据 VITE_USE_MOCK 决定
 * 3. 异步启动完成后再挂载 App（避免首屏请求未拦截）
 */
async function enableMocking() {
  // ============ 三重检查 ============

  // 1️⃣ 生产环境强制禁用
  if (import.meta.env.PROD) {
    console.log('🚫 Production build: MSW disabled')
    return
  }

  // 2️⃣ 检查构建模式
  const isDevelopment = import.meta.env.MODE === 'development'
  if (!isDevelopment) {
    console.log('🚫 Non-development mode: MSW disabled')
    return
  }

  // 3️⃣ 检查环境变量
  const mockEnabled = import.meta.env.VITE_USE_MOCK === 'true'
  if (!mockEnabled) {
    console.log('🚫 MSW disabled (VITE_USE_MOCK=false)')
    return
  }

  // ============ 启动 MSW ============
  console.warn('⚠️ MSW enabled (Development mode)')

  const { worker } = await import('./mocks/browser')

  // ✅ 异步启动，确保 Service Worker 注册完成
  await worker.start({
    // ✅ 使用 'warn' 而非 'bypass'，便于发现漏 Mock 的接口
    onUnhandledRequest: 'warn',

    // ✅ 显示详细日志，便于调试
    quiet: false,

    // ✅ 过滤已知的第三方请求（避免干扰）
    onUnhandledRequest(req, print) {
      // 忽略静态资源
      const url = req.url
      if (
        url.includes('/assets/') ||
        url.includes('/fonts/') ||
        url.includes('/images/') ||
        url.includes('.svg') ||
        url.includes('.png') ||
        url.includes('.jpg')
      ) {
        return
      }

      // 忽略 Vite HMR
      if (url.includes('/@vite/') || url.includes('/@fs/')) {
        return
      }

      // ✅ 其他未处理的请求打印警告
      print.warning()
    }
  })

  console.log('✅ MSW started successfully')
}

// ============ 确保 MSW 启动完成后再挂载 App ============
enableMocking().then(() => {
  ReactDOM.createRoot(document.getElementById('root')!).render(
    <React.StrictMode>
      <App />
    </React.StrictMode>
  )
})
```

#### 2.4 安装 MSW（历史记录）

```bash
cd <repo-root>/frontend/web

# 安装依赖
npm install msw --save-dev

# 初始化 Service Worker
npx msw init public/ --save
```

**验证清单（历史）**:
- [x] `.env` 配置 `VITE_USE_MOCK=false`
- [x] `.env.development` 配置 `VITE_USE_MOCK=true`
- [x] `public/mockServiceWorker.js` 已生成
- [x] `src/mocks/handlers.ts` 创建（空框架）
- [x] `src/main.tsx` 更新为安全启动逻辑
- [x] 运行 `npm run dev`，控制台显示 "✅ MSW started successfully"
- [x] Network 面板显示请求带 "[MSW]" 标记

---

### Task 3: BA 范围统一配置（15min）

> 更新（2026-01-23）：BA 范围由后端接口返回真实值，前端已使用动态范围；以下配置为历史示例。

#### 3.1 配置文件

**文件**: `src/config/constants.ts`

```typescript
/**
 * 全局配置常量
 *
 * ⚠️ BA 范围配置说明（历史）：
 * - 当前：后端 /api/v1/stats/ba-range 返回真实范围
 * - 常量仅作为 fallback/示例
 * - 历史查询：SELECT MIN(binding_affinity), MAX(binding_affinity) FROM regulations;
 */

// ============ BA（Binding Affinity）配置 ============
export const BA_CONFIG = {
  /** 最小值（后端约束 >= 0） */
  MIN: 0,

  /** 最大值（⚠️ 临时值，需根据实际数据调整） */
  MAX: 100,

  /** 滑块步长 */
  STEP: 0.1,

  /** 默认筛选范围 - 最小值 */
  DEFAULT_MIN: 0,

  /** 默认筛选范围 - 最大值 */
  DEFAULT_MAX: 100,

  /** 直方图区间数量 */
  HISTOGRAM_BUCKETS: 10
} as const

// ============ 导出限制配置 ============
export const EXPORT_LIMITS = {
  /** 数据量超过此值时显示警告 */
  WARN: 1000,

  /** 前端导出上限（Phase 1） */
  MAX_FRONTEND: 10000,

  /** 后端导出上限（Phase 2，暂未使用） */
  MAX_BACKEND: 50000,

  /** 分页获取数据时每页大小 */
  FETCH_PAGE_SIZE: 200
} as const

// ============ 物种选项 ============
export const SPECIES_OPTIONS = [
  { label: '人类', value: 1 },
  { label: '黑猩猩', value: 2 },
  { label: '猕猴', value: 3 },
  { label: '狨猴', value: 4 }
] as const

// ============ 染色体选项 ============
export const CHROMOSOME_OPTIONS = [
  'chr1', 'chr2', 'chr3', 'chr4', 'chr5', 'chr6', 'chr7', 'chr8', 'chr9', 'chr10',
  'chr11', 'chr12', 'chr13', 'chr14', 'chr15', 'chr16', 'chr17', 'chr18', 'chr19',
  'chr20', 'chr21', 'chr22', 'chrX', 'chrY'
].map(chr => ({ label: chr, value: chr })) as const

// ============ 工具函数：生成 BA 区间 ============

/**
 * 动态生成 BA 分布区间（用于直方图）
 *
 * @param min - 最小值（默认使用 BA_CONFIG.MIN）
 * @param max - 最大值（默认使用 BA_CONFIG.MAX）
 * @param numBuckets - 区间数量（默认 10）
 * @returns 区间数组
 */
export function generateBABuckets(
  min: number = BA_CONFIG.MIN,
  max: number = BA_CONFIG.MAX,
  numBuckets: number = BA_CONFIG.HISTOGRAM_BUCKETS
) {
  const step = (max - min) / numBuckets

  return Array.from({ length: numBuckets }, (_, i) => ({
    min: min + i * step,
    max: min + (i + 1) * step,
    label: `${(min + i * step).toFixed(1)}-${(min + (i + 1) * step).toFixed(1)}`
  }))
}

// ============ Feature Flags（用于生产环境切换） ============

/**
 * 功能开关配置
 *
 * ⚠️ 用于控制 Mock 数据与真实 API 的切换
 */
export const FEATURE_FLAGS = {
  /** Stats 详细统计 API（默认使用 Mock） */
  USE_MOCK_STATS: import.meta.env.VITE_USE_MOCK === 'true',

  /** BA 范围动态获取（当前已启用，历史示例） */
  USE_DYNAMIC_BA_RANGE: true,

  /** 后端导出功能（Phase 2） */
  USE_BACKEND_EXPORT: false
} as const
```

#### 3.2 使用示例

**在 Slider 中使用**:
```typescript
import { BA_CONFIG } from '@/config/constants'

<Slider
  range
  min={BA_CONFIG.MIN}
  max={BA_CONFIG.MAX}
  step={BA_CONFIG.STEP}
  value={[filters.min_ba ?? BA_CONFIG.DEFAULT_MIN, filters.max_ba ?? BA_CONFIG.DEFAULT_MAX]}
/>
```

**在直方图中使用**:
```typescript
import { generateBABuckets, BA_CONFIG } from '@/config/constants'

// Mock 数据生成
export const mockDetailedStats: DetailedStatsResponse = {
  ba_distribution: {
    buckets: generateBABuckets(BA_CONFIG.MIN, BA_CONFIG.MAX),
    counts: [5234, 12456, 45678, ...]
  }
}
```

**现状说明（2026-01）**：
- `frontend/web/src/config/constants.ts` 已存在；`BA_CONFIG` 仅作为静态回退值
- 实际 BA 范围由后端 `/api/v1/stats/ba-range` 返回，前端通过 `useBARange` 动态获取
- `generateBABuckets()` 仍保留在 `constants.ts` 作为通用工具函数；是否补单测按需要决定
- `VITE_USE_MOCK` 仅用于可选 MSW 框架；当前 handlers 为空，默认无需开启

---

### Task 4: 导出限制与 UI 提示（30min）

> 更新（2026-01-23）：导出能力已实现，以下内容为历史记录，供回溯使用。

#### 4.1 导出工具函数（完整实现）

**文件**: `src/utils/export.ts`

```typescript
import { saveAs } from 'file-saver'
import type { RegulationFilterParams, ExportResult, Regulation } from '@/types'
import { EXPORT_LIMITS } from '@/config/constants'
import { apiClient } from '@/api/client'

/**
 * CSV 转义函数（防止 CSV 注入）
 */
function escapeCSV(val: unknown): string {
  const str = String(val ?? '')
  if (str.includes(',') || str.includes('"') || str.includes('\n') || str.includes('\r')) {
    return `"${str.replace(/"/g, '""')}"`
  }
  return str
}

/**
 * 分页获取所有数据
 *
 * ⚠️ 注意：
 * - 后端可能有限流，需控制并发
 * - 数据量大时会打多次请求，需显示进度
 */
async function fetchAllRegulations(
  filters: RegulationFilterParams,
  total: number,
  onProgress?: (current: number, total: number) => void
): Promise<Regulation[]> {
  const PAGE_SIZE = EXPORT_LIMITS.FETCH_PAGE_SIZE
  const totalPages = Math.ceil(total / PAGE_SIZE)
  const allData: Regulation[] = []

  for (let page = 1; page <= totalPages; page++) {
    const { data } = await apiClient.get('/api/v1/regulations', {
      params: {
        ...filters,
        page,
        page_size: PAGE_SIZE
      }
    })

    allData.push(...data.items)

    // 进度回调
    onProgress?.(allData.length, total)

    // ⚠️ 避免过快请求触发限流，稍微延迟
    if (page < totalPages) {
      await new Promise(resolve => setTimeout(resolve, 100))
    }
  }

  return allData
}

/**
 * 导出为 CSV（前端生成）
 */
function exportToCSV(data: Regulation[]): ExportResult {
  try {
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
    const blob = new Blob(['\uFEFF' + csv], { type: 'text/csv;charset=utf-8;' })  // ✅ 添加 BOM，Excel 兼容

    saveAs(blob, `regulations-${Date.now()}.csv`)

    return { success: true }
  } catch (error) {
    console.error('CSV export failed:', error)
    return {
      success: false,
      error: 'EXPORT_FAILED',
      message: error instanceof Error ? error.message : '导出失败'
    }
  }
}

/**
 * 导出为 XLSX（动态导入库）
 */
async function exportToXLSX(data: Regulation[]): Promise<ExportResult> {
  try {
    // ✅ 动态导入，减少初始 bundle 大小
    const XLSX = await import('xlsx')

    const worksheet = XLSX.utils.json_to_sheet(data.map(r => ({
      'ID': r.regulation_id,
      'lncRNA': r.lncrna_gene_name || '',
      'Target': r.target_gene_name || '',
      'Species': r.species_name,
      'Chr': r.target_chromosome || '',
      'Start': r.target_start,
      'End': r.target_end,
      'BA': r.binding_affinity,
      'Peaks': r.num_peaks
    })))

    const workbook = XLSX.utils.book_new()
    XLSX.utils.book_append_sheet(workbook, worksheet, 'Regulations')

    XLSX.writeFile(workbook, `regulations-${Date.now()}.xlsx`)

    return { success: true }
  } catch (error) {
    console.error('XLSX export failed:', error)
    return {
      success: false,
      error: 'EXPORT_FAILED',
      message: error instanceof Error ? error.message : '导出失败'
    }
  }
}

/**
 * 导出 Regulations（主函数）
 *
 * @param filters - 筛选参数
 * @param format - 导出格式
 * @param total - 总记录数（用于校验）
 * @param onProgress - 进度回调
 */
export async function exportRegulations(
  filters: RegulationFilterParams,
  format: 'csv' | 'xlsx',
  total: number,
  onProgress?: (current: number, total: number) => void
): Promise<ExportResult> {
  // ============ 1. 数据量检查 ============

  if (total === 0) {
    return {
      success: false,
      error: 'NO_DATA',
      message: '没有可导出的数据'
    }
  }

  if (total > EXPORT_LIMITS.MAX_FRONTEND) {
    return {
      success: false,
      error: 'DATA_TOO_LARGE',
      total,
      limit: EXPORT_LIMITS.MAX_FRONTEND,
      message: `数据量过大（${total} 条），超过前端导出限制（${EXPORT_LIMITS.MAX_FRONTEND} 条）。请缩小筛选范围或联系管理员。`
    }
  }

  // ============ 2. 获取数据 ============

  try {
    console.log(`[Export] Fetching ${total} records...`)
    const allData = await fetchAllRegulations(filters, total, onProgress)
    console.log(`[Export] Fetched ${allData.length} records`)

    // ============ 3. 生成文件 ============

    if (format === 'csv') {
      return exportToCSV(allData)
    } else {
      return await exportToXLSX(allData)
    }
  } catch (error) {
    console.error('Export failed:', error)
    return {
      success: false,
      error: 'EXPORT_FAILED',
      message: error instanceof Error ? error.message : '导出失败，请重试'
    }
  }
}
```

#### 4.2 UI 集成示例（供 Phase 1 参考）

```typescript
// 在 Regulations 页面中使用

import { useState } from 'react'
import { Button, Dropdown, message, Modal, Progress } from 'antd'
import { DownloadOutlined } from '@ant-design/icons'
import { exportRegulations } from '@/utils/export'
import { EXPORT_LIMITS } from '@/config/constants'

export default function Regulations() {
  const [exportProgress, setExportProgress] = useState<{ current: number; total: number } | null>(null)

  const handleExport = async (format: 'csv' | 'xlsx') => {
    const total = data?.total || 0

    // ============ 1. 校验数据量 ============
    if (total === 0) {
      message.warning('没有可导出的数据')
      return
    }

    // ============ 2. 大数据量提示 ============
    if (total > EXPORT_LIMITS.WARN && total <= EXPORT_LIMITS.MAX_FRONTEND) {
      const confirmed = await new Promise<boolean>(resolve => {
        Modal.confirm({
          title: '数据量较大',
          content: `将导出 ${total} 条记录，可能需要一些时间。是否继续？`,
          okText: '继续导出',
          cancelText: '取消',
          onOk: () => resolve(true),
          onCancel: () => resolve(false)
        })
      })

      if (!confirmed) return
    }

    // ============ 3. 显示进度 ============
    const progressModal = Modal.info({
      title: '正在导出...',
      content: <Progress percent={0} />,
      footer: null,
      closable: false
    })

    // ============ 4. 执行导出 ============
    const result = await exportRegulations(
      filters,
      format,
      total,
      (current, total) => {
        const percent = Math.round((current / total) * 100)
        progressModal.update({
          content: <Progress percent={percent} status="active" />
        })
      }
    )

    progressModal.destroy()

    // ============ 5. 处理结果 ============
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

  return (
    <Dropdown menu={{ items: exportMenuItems }}>
      <Button icon={<DownloadOutlined />}>导出数据</Button>
    </Dropdown>
  )
}
```

**现状说明（2026-01）**：
- 导出逻辑已迁移到后端（openpyxl），避免前端 `xlsx` 依赖的漏洞风险
- `frontend/web/src/utils/export.ts` 负责调用后端导出接口并处理下载；小量选中行支持本地 CSV
- CSV 防注入转义在 `frontend/web/src/utils/csv.ts`（`escapeCSV`）
- 前端仍保留导出上限与 UI 提示（见 `EXPORT_LIMITS` 与导出结果处理）

---

## ✅ Phase 0 完成标准

### 验收清单

#### Task 1: 统一类型出口（历史）
- [x] `src/types/api-extensions.ts` 创建，包含所有扩展类型（历史记录）
- [x] `src/types/index.ts` 统一导出（历史记录）
- [x] `eslint.config.js` 配置 no-restricted-imports 规则（历史记录）
- [x] `src/utils/echarts.ts` 按需导入，控制台显示版本号（历史记录）
- [x] 运行 `npm run lint` 无错误（历史记录）

#### Task 2: MSW 安全启动（历史）
- [x] `.env` 配置 `VITE_USE_MOCK=false`
- [x] `.env.development` 配置 `VITE_USE_MOCK=true`
- [x] `public/mockServiceWorker.js` 已生成
- [x] `src/mocks/handlers.ts` 空框架创建
- [x] `src/main.tsx` 安全启动逻辑
- [x] 运行 `npm run dev`，控制台显示 "✅ MSW started successfully"
- [x] Network 面板显示 "[MSW]" 标记
- [x] onUnhandledRequest 设置为 'warn'

#### Task 3: BA 范围统一配置（历史）
- [x] `src/config/constants.ts` 创建
- [x] `BA_CONFIG` 配置正确
- [x] `generateBABuckets()` 函数测试通过
- [x] `FEATURE_FLAGS` 配置正确

#### Task 4: 导出限制与提示（历史）
- [x] `src/utils/export.ts` 创建（历史记录）
- [x] `escapeCSV()` 防注入测试通过（历史记录）
- [x] `fetchAllRegulations()` 分页逻辑正确（历史记录）
- [x] `exportToXLSX()` 动态导入（历史记录）
- [x] 导出上限校验逻辑完整（历史记录）

---

## 🚀 依赖安装

> 更新（2026-01-23）：MSW 已移除，以下命令仅为历史安装记录。

```bash
cd <repo-root>/frontend/web

# ✅ Phase 0 需要安装的依赖
npm install msw --save-dev
npm install xlsx
npm install -D rollup-plugin-visualizer

# 初始化 MSW
npx msw init public/ --save

# 验证安装
npm list msw xlsx rollup-plugin-visualizer
```

---

## 📊 时间估算

| 任务 | 时间 | 说明 |
|------|------|------|
| Task 1: 统一类型出口 | 30min | 创建文件 + ESLint 配置 |
| Task 2: MSW 安全启动 | 30min | 环境变量 + 启动逻辑 |
| Task 3: BA 范围配置 | 15min | 配置文件 + 工具函数 |
| Task 4: 导出限制（历史） | 30min | 完整实现 + 测试 |
| **总计** | **1.75h** | - |

---

## 🔄 与 Phase 1 的关系

**Phase 0 完成后**，Phase 1 才能顺利进行：

| Phase 1 任务 | 依赖 Phase 0 | 说明 |
|-------------|-------------|------|
| Stats 图表 | Task 1（echarts.ts） | 按需导入配置 |
| Stats Mock 数据（已废弃） | Task 2（MSW）+ Task 3（BA 配置） | 历史 Mock 框架 + BA 区间生成 |
| Regulations 筛选 | Task 3（constants.ts） | BA_CONFIG, SPECIES_OPTIONS |
| Regulations 导出 | Task 4（export.ts） | 完整导出逻辑 |

---

## 🎯 后续清理事项

**Phase 0 完成后需确认删除**：

1. ❌ 删除 PHASE1_IMPLEMENTATION_PLAN.md 中提到的 jsPDF（未使用）
2. ❌ 删除 VirtualTable 引用（未使用）
3. ✅ 确认 XLSX 仅动态导入
4. ✅ 确认所有类型从 `@/types` 导入，而非 `@/types/api`

---

**文档版本**: v1.0
**最后更新**: 2025-11-27
**作者**: Claude Code
**状态**: ✅ 准备实施
