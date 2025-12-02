# Phase 1 前端功能增强实施方案

**项目**: Human LncRNA Atlas - 前端增强
**版本**: v1.0
**日期**: 2025-11-27
**状态**: 📋 待实施

---

## 📋 目录

- [一、项目背景](#一项目背景)
- [二、实施目标](#二实施目标)
- [三、API 契约定义](#三api-契约定义)
- [四、类型系统设计](#四类型系统设计)
- [五、Mock 配置方案](#五mock-配置方案)
- [六、功能详细设计](#六功能详细设计)
- [七、文件结构](#七文件结构)
- [八、实施检查清单](#八实施检查清单)
- [九、测试策略](#九测试策略)
- [十、风险缓解措施](#十风险缓解措施)

---

## 一、项目背景

### 1.1 当前状态

| 页面 | 当前功能 | 缺失功能 |
|------|---------|---------|
| **Regulations** | BA阈值筛选、分页 | 多维筛选、导出、详情 |
| **Stats** | 4个数字卡片 | 图表、分布、趋势 |
| **Home** | 4个统计卡片 + 4个入口 | 搜索、热门数据 |

### 1.2 技术栈

```typescript
✅ 已有：
- React 18 + TypeScript
- Ant Design 5.x
- React Query (数据缓存)
- React Router (路由)

📦 新增：
- ECharts 5.x (图表)
- XLSX.js (导出)
- MSW (Mock API)
```

---

## 二、实施目标

### 2.1 Phase 1 目标

**核心功能**（必须完成）：
1. ✅ Stats 页面 - 3个可视化图表
2. ✅ Regulations 页面 - 高级筛选器
3. ✅ Regulations 页面 - CSV/XLSX 导出

**成功指标**：
- 首屏加载时间 < 2s
- 筛选响应时间 < 500ms
- 图表渲染时间 < 1s
- Bundle 总大小 < 1.5MB (gzip)

### 2.2 Phase 2 目标（未来）

- Home 页面全局搜索
- Regulations 批量操作
- Stats 导出 PDF 报告

---

## 三、API 契约定义

### 3.1 详细统计 API

```typescript
/**
 * GET /api/v1/stats/detailed
 *
 * 状态: 🔴 Mock (后端待实现)
 * 用途: 获取数据库详细统计信息，用于 Stats 页面图表
 */
interface DetailedStatsResponse {
  summary: {
    total_genes: number
    total_lncrna: number
    total_regulations: number
    total_traits: number
    total_species: number
    total_batches: number
  }

  // 物种分布（饼图数据）
  species_distribution: Array<{
    species_id: number
    species_name: string
    gene_count: number
    lncrna_count: number
    regulation_count: number
  }>

  // BA 分布（直方图数据）
  ba_distribution: {
    buckets: Array<{
      min: number
      max: number
      label: string  // "0-10", "10-20", ...
    }>
    counts: number[]  // 每个区间的调控关系数量
  }

  // Top 10 lncRNA（按调控数量排序）
  top_lncrnas: Array<{
    gene_id: number
    gene_name: string
    gene_ensembl_id: string
    regulation_count: number
    species_name: string
  }>

  // Top 10 靶基因（按被调控数量排序）
  top_targets: Array<{
    gene_id: number
    gene_name: string
    gene_ensembl_id: string
    regulated_by_count: number
    species_name: string
  }>
}

/**
 * 后端 SQL 参考（PostgreSQL）
 */
/*
-- 物种分布
SELECT
  s.species_id,
  s.species_name,
  COUNT(DISTINCT g.gene_id) as gene_count,
  COUNT(DISTINCT CASE WHEN g.gene_type = 'lncRNA' THEN g.gene_id END) as lncrna_count,
  COUNT(r.regulation_id) as regulation_count
FROM species s
LEFT JOIN genes g ON s.species_id = g.species_id
LEFT JOIN regulations r ON g.gene_id IN (r.lncrna_gene_id, r.target_gene_id)
GROUP BY s.species_id, s.species_name
ORDER BY s.species_id;

-- BA 分布
SELECT
  FLOOR(binding_affinity / 10) * 10 as bucket_min,
  FLOOR(binding_affinity / 10) * 10 + 10 as bucket_max,
  COUNT(*) as count
FROM regulations
GROUP BY FLOOR(binding_affinity / 10)
ORDER BY bucket_min;

-- Top 10 lncRNA
SELECT
  g.gene_id,
  g.gene_name,
  g.gene_ensembl_id,
  s.species_name,
  COUNT(r.regulation_id) as regulation_count
FROM genes g
JOIN regulations r ON g.gene_id = r.lncrna_gene_id
JOIN species s ON g.species_id = s.species_id
WHERE g.gene_type = 'lncRNA'
GROUP BY g.gene_id, g.gene_name, g.gene_ensembl_id, s.species_name
ORDER BY regulation_count DESC
LIMIT 10;

-- Top 10 靶基因
SELECT
  g.gene_id,
  g.gene_name,
  g.gene_ensembl_id,
  s.species_name,
  COUNT(r.regulation_id) as regulated_by_count
FROM genes g
JOIN regulations r ON g.gene_id = r.target_gene_id
JOIN species s ON g.species_id = s.species_id
GROUP BY g.gene_id, g.gene_name, g.gene_ensembl_id, s.species_name
ORDER BY regulated_by_count DESC
LIMIT 10;
*/
```

### 3.2 Regulations 筛选 API（扩展现有）

```typescript
/**
 * GET /api/v1/regulations
 *
 * 状态: 🟡 部分实现 (需扩展参数)
 * 现有参数: page, page_size, min_ba
 * 新增参数: max_ba, species_id[], lncrna_gene_name, target_gene_name, chromosome[]
 */
interface RegulationFilterParams {
  // 基础分页（已存在）
  page?: number
  page_size?: number

  // BA 范围筛选
  min_ba?: number
  max_ba?: number           // 🆕 新增

  // 多维筛选（新增）
  species_id?: number[]     // 🆕 物种多选
  lncrna_gene_name?: string // 🆕 lncRNA 模糊搜索
  target_gene_name?: string // 🆕 靶基因模糊搜索
  chromosome?: string[]     // 🆕 染色体多选

  // 排序（新增）
  sort_by?: 'binding_affinity' | 'regulation_id' | 'lncrna_gene_name' | 'target_gene_name'
  order?: 'asc' | 'desc'
}

/**
 * 后端实现参考（FastAPI）
 */
/*
from fastapi import APIRouter, Query
from typing import List, Optional

@router.get("/regulations")
async def get_regulations(
    page: int = 1,
    page_size: int = Query(100, le=200),  # 最大 200
    min_ba: Optional[float] = None,
    max_ba: Optional[float] = None,
    species_id: Optional[List[int]] = Query(None),
    lncrna_gene_name: Optional[str] = None,
    target_gene_name: Optional[str] = None,
    chromosome: Optional[List[str]] = Query(None),
    sort_by: str = 'regulation_id',
    order: str = 'desc'
):
    query = """
        SELECT
            r.regulation_id,
            lnc.gene_name as lncrna_gene_name,
            tgt.gene_name as target_gene_name,
            s.species_name,
            r.binding_affinity,
            r.num_peaks,
            tgt.chromosome as target_chromosome,
            tgt.gene_start as target_start,
            tgt.gene_end as target_end
        FROM regulations r
        JOIN genes lnc ON r.lncrna_gene_id = lnc.gene_id
        JOIN genes tgt ON r.target_gene_id = tgt.gene_id
        JOIN species s ON lnc.species_id = s.species_id
        WHERE 1=1
    """

    params = {}

    if min_ba is not None:
        query += " AND r.binding_affinity >= :min_ba"
        params['min_ba'] = min_ba

    if max_ba is not None:
        query += " AND r.binding_affinity <= :max_ba"
        params['max_ba'] = max_ba

    if species_id:
        query += " AND lnc.species_id = ANY(:species_id)"
        params['species_id'] = species_id

    if lncrna_gene_name:
        query += " AND lnc.gene_name ILIKE :lncrna_pattern"
        params['lncrna_pattern'] = f"%{lncrna_gene_name}%"

    if target_gene_name:
        query += " AND tgt.gene_name ILIKE :target_pattern"
        params['target_pattern'] = f"%{target_gene_name}%"

    if chromosome:
        query += " AND tgt.chromosome = ANY(:chromosome)"
        params['chromosome'] = chromosome

    # 排序
    query += f" ORDER BY r.{sort_by} {order.upper()}"

    # 分页
    query += " LIMIT :limit OFFSET :offset"
    params['limit'] = page_size
    params['offset'] = (page - 1) * page_size

    results = await db.fetch_all(query, params)
    total = await db.fetch_val("SELECT COUNT(*) FROM (" + query.split("ORDER BY")[0] + ") t", params)

    return {
        "items": results,
        "total": total,
        "page": page,
        "page_size": page_size
    }
*/
```

### 3.3 Regulations 导出 API

```typescript
/**
 * GET /api/v1/regulations/export
 *
 * 状态: 🔴 Mock (后端待实现)
 * 用途: 导出筛选后的调控关系为 CSV/XLSX
 */
interface RegulationExportParams extends RegulationFilterParams {
  format: 'csv' | 'xlsx'
  limit?: number              // 导出限制（默认 10000）
  include_header?: boolean    // 是否包含表头（默认 true）
}

// Response: Blob (application/csv 或 application/vnd.openxmlformats-officedocument.spreadsheetml.sheet)

/**
 * 后端实现参考（小数据量，同步导出）
 */
/*
@router.get("/regulations/export")
async def export_regulations(
    format: str = 'csv',
    limit: int = Query(10000, le=50000),
    **filters: RegulationFilterParams
):
    # 1. 查询数据（使用相同的筛选逻辑）
    query = build_regulation_query(filters)
    query += f" LIMIT {limit}"
    results = await db.fetch_all(query)

    # 2. 生成文件
    if format == 'csv':
        import csv
        from io import StringIO

        output = StringIO()
        writer = csv.DictWriter(output, fieldnames=['regulation_id', 'lncrna_gene_name', ...])
        writer.writeheader()
        writer.writerows(results)

        return Response(
            content=output.getvalue(),
            media_type="text/csv",
            headers={"Content-Disposition": f"attachment; filename=regulations-{datetime.now()}.csv"}
        )

    elif format == 'xlsx':
        import openpyxl
        from io import BytesIO

        wb = openpyxl.Workbook()
        ws = wb.active
        ws.append(['regulation_id', 'lncrna_gene_name', ...])

        for row in results:
            ws.append(list(row.values()))

        output = BytesIO()
        wb.save(output)
        output.seek(0)

        return Response(
            content=output.getvalue(),
            media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
            headers={"Content-Disposition": f"attachment; filename=regulations-{datetime.now()}.xlsx"}
        )
*/

/**
 * 后端实现参考（大数据量，异步导出）
 */
/*
@router.post("/regulations/export-async")
async def export_regulations_async(
    background_tasks: BackgroundTasks,
    **params: RegulationExportParams
):
    task_id = str(uuid.uuid4())

    # 创建任务记录
    await db.execute(
        "INSERT INTO export_tasks (task_id, status, filters, format) VALUES ($1, 'pending', $2, $3)",
        task_id, json.dumps(params), params.format
    )

    # 添加后台任务
    background_tasks.add_task(generate_export_file, task_id, params)

    return {"task_id": task_id, "status": "pending"}

@router.get("/export-tasks/{task_id}")
async def get_export_task(task_id: str):
    task = await db.fetchrow("SELECT * FROM export_tasks WHERE task_id = $1", task_id)
    return {
        "task_id": task_id,
        "status": task["status"],  # pending | processing | completed | failed
        "download_url": task["file_url"] if task["status"] == "completed" else None
    }
*/
```

---

## 四、类型系统设计

### 4.1 类型定义策略

```typescript
// ==================== 文件结构 ====================
// src/types/
//   ├── api.ts              (OpenAPI 自动生成，不手动修改)
//   ├── api-extensions.ts   (扩展类型，继承 api.ts)
//   └── index.ts            (统一导出)

// ==================== api-extensions.ts ====================
import { components } from './api'

// ✅ 复用 OpenAPI 生成的基础类型
export type Gene = components['schemas']['GeneListItem']
export type Regulation = components['schemas']['RegulationListItem']
export type Trait = components['schemas']['TraitListItem']

// ✅ 扩展新接口的类型（后端未实现时）
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

// ✅ Regulations 筛选参数（扩展现有 API）
export interface RegulationFilterParams {
  // 基础分页参数（已存在）
  page?: number
  page_size?: number
  min_ba?: number

  // 新增参数（后端待实现）
  max_ba?: number
  species_id?: number[]
  lncrna_gene_name?: string
  target_gene_name?: string
  chromosome?: string[]
  sort_by?: 'binding_affinity' | 'regulation_id' | 'lncrna_gene_name' | 'target_gene_name'
  order?: 'asc' | 'desc'
}

// ✅ 导出参数
export interface RegulationExportParams extends RegulationFilterParams {
  format: 'csv' | 'xlsx'
  limit?: number
  include_header?: boolean
}

// ==================== index.ts ====================
export * from './api'           // 导出 OpenAPI 类型
export * from './api-extensions' // 导出扩展类型
```

### 4.2 类型使用规范

```typescript
// ✅ 正确：从统一入口导入
import { Gene, Regulation, DetailedStatsResponse } from '@/types'

// ❌ 错误：直接从 api.ts 导入
import { components } from '@/types/api'
type Gene = components['schemas']['GeneListItem']  // 不要这样

// ✅ 正确：MSW Handler 使用类型
import { http, HttpResponse } from 'msw'
import type { DetailedStatsResponse } from '@/types'

export const handlers = [
  http.get('/api/v1/stats/detailed', (): HttpResponse<DetailedStatsResponse> => {
    return HttpResponse.json({
      summary: { /* TypeScript 会校验类型 */ },
      species_distribution: [ /* ... */ ]
    })
  })
]
```

---

## 五、Mock 配置方案

### 5.1 MSW 安装与初始化

```bash
# 1. 安装依赖
npm install msw --save-dev

# 2. 初始化 MSW（生成 Service Worker）
npx msw init public/ --save

# 3. 验证 public/mockServiceWorker.js 已生成
```

### 5.2 Mock 文件结构

```
src/mocks/
├── browser.ts      # 浏览器环境 MSW 配置
├── server.ts       # Node 测试环境 MSW 配置
├── handlers.ts     # API handlers 定义
└── data/
    ├── stats.mock.ts        # Stats 页面 Mock 数据
    └── regulations.mock.ts  # Regulations 页面 Mock 数据
```

### 5.3 Mock 数据示例

```typescript
// ==================== src/mocks/data/stats.mock.ts ====================
import type { DetailedStatsResponse } from '@/types'

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
    {
      species_id: 1,
      species_name: '人类',
      gene_count: 35000,
      lncrna_count: 12000,
      regulation_count: 560000
    },
    {
      species_id: 2,
      species_name: '黑猩猩',
      gene_count: 28000,
      lncrna_count: 9500,
      regulation_count: 380000
    },
    {
      species_id: 3,
      species_name: '猕猴',
      gene_count: 10000,
      lncrna_count: 4200,
      regulation_count: 200000
    },
    {
      species_id: 4,
      species_name: '狨猴',
      gene_count: 7234,
      lncrna_count: 2756,
      regulation_count: 94567
    }
  ],

  ba_distribution: {
    buckets: [
      { min: 0, max: 10, label: '0-10' },
      { min: 10, max: 20, label: '10-20' },
      { min: 20, max: 30, label: '20-30' },
      { min: 30, max: 40, label: '30-40' },
      { min: 40, max: 50, label: '40-50' },
      { min: 50, max: 60, label: '50-60' },
      { min: 60, max: 70, label: '60-70' },
      { min: 70, max: 80, label: '70-80' },
      { min: 80, max: 90, label: '80-90' },
      { min: 90, max: 100, label: '90-100' }
    ],
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

### 5.4 Handlers 定义

```typescript
// ==================== src/mocks/handlers.ts ====================
import { http, HttpResponse } from 'msw'
import type { DetailedStatsResponse } from '@/types'
import { mockDetailedStats } from './data/stats.mock'

export const handlers = [
  // ==================== Stats API ====================
  http.get('/api/v1/stats/detailed', (): HttpResponse<DetailedStatsResponse> => {
    console.log('📊 [MSW] GET /api/v1/stats/detailed')
    return HttpResponse.json(mockDetailedStats)
  }),

  // ==================== Regulations Export API ====================
  http.get('/api/v1/regulations/export', ({ request }) => {
    const url = new URL(request.url)
    const format = url.searchParams.get('format') || 'csv'

    console.log(`📥 [MSW] GET /api/v1/regulations/export?format=${format}`)

    if (format === 'csv') {
      const csv = `ID,lncRNA,Target,Species,BA\n1001,H19,TP53,人类,85.2\n1002,MALAT1,MYC,人类,72.1`

      return new HttpResponse(csv, {
        headers: {
          'Content-Type': 'text/csv',
          'Content-Disposition': `attachment; filename=regulations-${Date.now()}.csv`
        }
      })
    }

    return new HttpResponse(null, { status: 400, statusText: 'Unsupported format' })
  })
]
```

### 5.5 浏览器配置

```typescript
// ==================== src/mocks/browser.ts ====================
import { setupWorker } from 'msw/browser'
import { handlers } from './handlers'

export const worker = setupWorker(...handlers)
```

### 5.6 测试环境配置

```typescript
// ==================== src/mocks/server.ts ====================
import { setupServer } from 'msw/node'
import { handlers } from './handlers'

export const server = setupServer(...handlers)
```

### 5.7 主入口集成

```typescript
// ==================== src/main.tsx ====================
import React from 'react'
import ReactDOM from 'react-dom/client'
import App from './App'

async function enableMocking() {
  // ✅ 双重检查：环境变量 + 构建模式
  const shouldMock =
    import.meta.env.VITE_USE_MOCK === 'true' &&
    import.meta.env.MODE === 'development'

  if (!shouldMock) {
    console.log('🚫 Mock Service Worker 已禁用')
    return
  }

  console.warn('⚠️ Mock Service Worker 已启用 (仅开发环境)')

  const { worker } = await import('./mocks/browser')
  return worker.start({
    // ✅ 使用 warn 而非 bypass，便于发现漏 Mock 的接口
    onUnhandledRequest: 'warn',

    // ✅ 静默已知的第三方请求
    onUnhandledRequest(req, print) {
      // 忽略字体、图片等静态资源
      if (req.url.includes('/fonts/') || req.url.includes('/images/')) {
        return
      }

      // 忽略已知的第三方服务
      if (req.url.includes('google-analytics.com')) {
        return
      }

      // 其他未处理的请求打印警告
      print.warning()
    }
  })
}

enableMocking().then(() => {
  ReactDOM.createRoot(document.getElementById('root')!).render(
    <React.StrictMode>
      <App />
    </React.StrictMode>
  )
})
```

### 5.8 测试配置

```typescript
// ==================== src/setupTests.ts ====================
import '@testing-library/jest-dom'
import { server } from './mocks/server'

// ✅ 在所有测试前启动 MSW
beforeAll(() => server.listen({ onUnhandledRequest: 'error' }))

// ✅ 每个测试后重置 handlers
afterEach(() => server.resetHandlers())

// ✅ 所有测试后关闭
afterAll(() => server.close())
```

### 5.9 环境变量配置

```bash
# ==================== .env ====================
# 生产默认配置（Git 提交）
VITE_USE_MOCK=false

# ==================== .env.development ====================
# 开发环境（Git 忽略）
VITE_USE_MOCK=true

# ==================== .env.production ====================
# 生产环境（Git 忽略）
VITE_USE_MOCK=false
```

---

## 六、功能详细设计

### 6.1 Stats 页面 - 物种分布饼图

#### 组件代码

```typescript
// ==================== src/pages/Stats/components/SpeciesChart.tsx ====================
import ReactECharts from 'echarts-for-react'
import type { EChartsOption } from 'echarts'
import echarts from '@/utils/echarts'
import type { DetailedStatsResponse } from '@/types'

interface SpeciesChartProps {
  data: DetailedStatsResponse['species_distribution']
}

export const SpeciesChart: React.FC<SpeciesChartProps> = ({ data }) => {
  const option: EChartsOption = {
    title: {
      text: '物种基因分布',
      left: 'center',
      top: 20,
      textStyle: {
        fontSize: 16,
        fontWeight: 'bold'
      }
    },

    tooltip: {
      trigger: 'item',
      formatter: '{b}: {c} ({d}%)'
    },

    legend: {
      orient: 'vertical',
      left: 'left',
      top: 'middle'
    },

    series: [
      {
        type: 'pie',
        radius: ['40%', '70%'],  // 环形图
        center: ['60%', '50%'],  // 右移，给图例留空间
        data: data.map(s => ({
          name: s.species_name,
          value: s.gene_count
        })),
        emphasis: {
          itemStyle: {
            shadowBlur: 10,
            shadowOffsetX: 0,
            shadowColor: 'rgba(0, 0, 0, 0.5)'
          }
        },
        label: {
          show: true,
          formatter: '{b}\n{c} ({d}%)'
        }
      }
    ]
  }

  return (
    <ReactECharts
      echarts={echarts}
      option={option}
      style={{ height: 400 }}
      notMerge={true}
      lazyUpdate={true}
    />
  )
}
```

### 6.2 Stats 页面 - BA 分布直方图

```typescript
// ==================== src/pages/Stats/components/BAChart.tsx ====================
import ReactECharts from 'echarts-for-react'
import type { EChartsOption } from 'echarts'
import echarts from '@/utils/echarts'
import type { DetailedStatsResponse } from '@/types'

interface BAChartProps {
  data: DetailedStatsResponse['ba_distribution']
}

export const BAChart: React.FC<BAChartProps> = ({ data }) => {
  const option: EChartsOption = {
    title: {
      text: 'Binding Affinity 分布',
      left: 'center',
      top: 20,
      textStyle: {
        fontSize: 16,
        fontWeight: 'bold'
      }
    },

    tooltip: {
      trigger: 'axis',
      axisPointer: {
        type: 'shadow'
      },
      formatter: (params: any) => {
        const { name, value } = params[0]
        return `${name}<br/>调控关系数: ${value.toLocaleString()}`
      }
    },

    xAxis: {
      type: 'category',
      data: data.buckets.map(b => b.label),
      axisLabel: {
        rotate: 45,
        fontSize: 11
      },
      name: 'BA 区间',
      nameLocation: 'middle',
      nameGap: 35
    },

    yAxis: {
      type: 'value',
      name: '调控关系数',
      nameLocation: 'middle',
      nameGap: 50,
      axisLabel: {
        formatter: (value: number) => {
          if (value >= 1000000) return `${(value / 1000000).toFixed(1)}M`
          if (value >= 1000) return `${(value / 1000).toFixed(1)}K`
          return value.toString()
        }
      }
    },

    grid: {
      left: '15%',
      right: '10%',
      bottom: '20%',
      top: '15%'
    },

    series: [
      {
        type: 'bar',
        data: data.counts,
        itemStyle: {
          color: new echarts.graphic.LinearGradient(0, 0, 0, 1, [
            { offset: 0, color: '#83bff6' },
            { offset: 0.5, color: '#188df0' },
            { offset: 1, color: '#188df0' }
          ])
        },
        label: {
          show: false
        }
      }
    ]
  }

  return (
    <ReactECharts
      echarts={echarts}
      option={option}
      style={{ height: 400 }}
      notMerge={true}
      lazyUpdate={true}
    />
  )
}
```

### 6.3 Stats 页面 - Top 10 lncRNA 条形图

```typescript
// ==================== src/pages/Stats/components/TopLncRNAChart.tsx ====================
import ReactECharts from 'echarts-for-react'
import type { EChartsOption } from 'echarts'
import echarts from '@/utils/echarts'
import type { DetailedStatsResponse } from '@/types'

interface TopLncRNAChartProps {
  data: DetailedStatsResponse['top_lncrnas']
}

export const TopLncRNAChart: React.FC<TopLncRNAChartProps> = ({ data }) => {
  // ✅ 反转数据（ECharts 条形图从下往上）
  const reversedData = [...data].reverse()

  const option: EChartsOption = {
    title: {
      text: 'Top 10 调控最多的 lncRNA',
      left: 'center',
      top: 20,
      textStyle: {
        fontSize: 16,
        fontWeight: 'bold'
      }
    },

    tooltip: {
      trigger: 'axis',
      axisPointer: {
        type: 'shadow'
      },
      formatter: (params: any) => {
        const { name, value, data } = params[0]
        return `
          <strong>${name}</strong><br/>
          Ensembl ID: ${data.ensembl_id}<br/>
          物种: ${data.species}<br/>
          调控数量: ${value.toLocaleString()}
        `
      }
    },

    grid: {
      left: '15%',
      right: '10%',
      bottom: '10%',
      top: '15%',
      containLabel: true
    },

    xAxis: {
      type: 'value',
      name: '调控关系数',
      nameLocation: 'middle',
      nameGap: 35
    },

    yAxis: {
      type: 'category',
      data: reversedData.map(l => l.gene_name),
      axisLabel: {
        fontSize: 12
      }
    },

    series: [
      {
        type: 'bar',
        data: reversedData.map(l => ({
          value: l.regulation_count,
          ensembl_id: l.gene_ensembl_id,
          species: l.species_name
        })),
        itemStyle: {
          color: '#5470c6'
        },
        label: {
          show: true,
          position: 'right',
          formatter: (params: any) => params.value.toLocaleString()
        }
      }
    ]
  }

  return (
    <ReactECharts
      echarts={echarts}
      option={option}
      style={{ height: 500 }}
      notMerge={true}
      lazyUpdate={true}
    />
  )
}
```

### 6.4 Stats 主页面集成

```typescript
// ==================== src/pages/Stats/index.tsx ====================
import { lazy, Suspense } from 'react'
import { Card, Row, Col, Spin, Statistic } from 'antd'
import { useDetailedStats } from '@/hooks/useDetailedStats'
import { LoadingState } from '@/components/LoadingState'
import { ErrorState } from '@/components/ErrorState'

// ✅ 懒加载图表组件
const SpeciesChart = lazy(() => import('./components/SpeciesChart').then(m => ({ default: m.SpeciesChart })))
const BAChart = lazy(() => import('./components/BAChart').then(m => ({ default: m.BAChart })))
const TopLncRNAChart = lazy(() => import('./components/TopLncRNAChart').then(m => ({ default: m.TopLncRNAChart })))

export default function Stats() {
  const { data, isLoading, error } = useDetailedStats()

  if (isLoading) return <LoadingState />
  if (error) return <ErrorState error={error} />
  if (!data) return null

  return (
    <div style={{ padding: 24 }}>
      <h1>数据库统计概览</h1>

      {/* 总体统计卡片 */}
      <Row gutter={16} style={{ marginTop: 24, marginBottom: 32 }}>
        <Col xs={12} sm={8} md={4}>
          <Card>
            <Statistic title="总基因数" value={data.summary.total_genes} />
          </Card>
        </Col>
        <Col xs={12} sm={8} md={4}>
          <Card>
            <Statistic title="lncRNA" value={data.summary.total_lncrna} />
          </Card>
        </Col>
        <Col xs={12} sm={8} md={4}>
          <Card>
            <Statistic title="调控关系" value={data.summary.total_regulations} />
          </Card>
        </Col>
        <Col xs={12} sm={8} md={4}>
          <Card>
            <Statistic title="疾病关联" value={data.summary.total_traits} />
          </Card>
        </Col>
        <Col xs={12} sm={8} md={4}>
          <Card>
            <Statistic title="物种" value={data.summary.total_species} />
          </Card>
        </Col>
        <Col xs={12} sm={8} md={4}>
          <Card>
            <Statistic title="批次" value={data.summary.total_batches} />
          </Card>
        </Col>
      </Row>

      {/* 数据分布图表 */}
      <h2 style={{ marginBottom: 16 }}>📈 数据分布</h2>
      <Row gutter={16} style={{ marginBottom: 32 }}>
        <Col xs={24} lg={12}>
          <Card>
            <Suspense fallback={<Spin size="large" style={{ display: 'block', margin: '100px auto' }} />}>
              <SpeciesChart data={data.species_distribution} />
            </Suspense>
          </Card>
        </Col>
        <Col xs={24} lg={12}>
          <Card>
            <Suspense fallback={<Spin size="large" style={{ display: 'block', margin: '100px auto' }} />}>
              <BAChart data={data.ba_distribution} />
            </Suspense>
          </Card>
        </Col>
      </Row>

      {/* Top 排行榜 */}
      <h2 style={{ marginBottom: 16 }}>🏆 Top 10 榜单</h2>
      <Row gutter={16}>
        <Col xs={24} xl={12}>
          <Card>
            <Suspense fallback={<Spin size="large" style={{ display: 'block', margin: '100px auto' }} />}>
              <TopLncRNAChart data={data.top_lncrnas} />
            </Suspense>
          </Card>
        </Col>
        <Col xs={24} xl={12}>
          <Card>
            <Suspense fallback={<Spin size="large" style={{ display: 'block', margin: '100px auto' }} />}>
              {/* Top Targets 图表（结构类似 TopLncRNAChart） */}
              <TopLncRNAChart data={data.top_targets} />
            </Suspense>
          </Card>
        </Col>
      </Row>
    </div>
  )
}
```

### 6.5 Regulations 高级筛选器

```typescript
// ==================== src/pages/Regulations/components/AdvancedFilters.tsx ====================
import { Form, Select, Input, Slider, Collapse, Button, Space } from 'antd'
import { FilterOutlined } from '@ant-design/icons'
import type { RegulationFilterParams } from '@/types'

interface AdvancedFiltersProps {
  filters: RegulationFilterParams
  onFilterChange: (key: keyof RegulationFilterParams, value: any) => void
  onReset: () => void
}

const SPECIES_OPTIONS = [
  { label: '人类', value: 1 },
  { label: '黑猩猩', value: 2 },
  { label: '猕猴', value: 3 },
  { label: '狨猴', value: 4 }
]

const CHROMOSOME_OPTIONS = [
  'chr1', 'chr2', 'chr3', 'chr4', 'chr5', 'chr6', 'chr7', 'chr8', 'chr9', 'chr10',
  'chr11', 'chr12', 'chr13', 'chr14', 'chr15', 'chr16', 'chr17', 'chr18', 'chr19', 'chr20',
  'chr21', 'chr22', 'chrX', 'chrY'
].map(chr => ({ label: chr, value: chr }))

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
                  />
                </Form.Item>

                {/* BA 范围 */}
                <Form.Item
                  label={`Binding Affinity 范围: ${filters.min_ba || 0} - ${filters.max_ba || 100}`}
                  style={{ marginBottom: 0 }}
                >
                  <Slider
                    range
                    min={0}
                    max={100}
                    value={[filters.min_ba || 0, filters.max_ba || 100]}
                    onChange={(val) => {
                      onFilterChange('min_ba', val[0])
                      onFilterChange('max_ba', val[1])
                    }}
                    marks={{
                      0: '0',
                      25: '25',
                      50: '50',
                      75: '75',
                      100: '100'
                    }}
                  />
                </Form.Item>

                {/* 操作按钮 */}
                <Space>
                  <Button onClick={onReset}>重置筛选</Button>
                </Space>
              </Space>
            </Form>
          )
        }
      ]}
    />
  )
}
```

### 6.6 Regulations 导出功能

```typescript
// ==================== src/utils/export.ts ====================
import { saveAs } from 'file-saver'
import type { RegulationFilterParams } from '@/types'
import { apiClient } from '@/api/client'

const MAX_EXPORT_SIZE = 10000

/**
 * 导出 Regulations 为 CSV/XLSX
 */
export const exportRegulations = async (
  filters: RegulationFilterParams,
  format: 'csv' | 'xlsx',
  total: number
) => {
  // ✅ 检查数据量
  if (total > MAX_EXPORT_SIZE) {
    return {
      success: false,
      error: 'DATA_TOO_LARGE',
      total,
      limit: MAX_EXPORT_SIZE
    }
  }

  try {
    // ✅ 调用导出 API
    const response = await apiClient.get('/api/v1/regulations/export', {
      params: {
        ...filters,
        format,
        limit: MAX_EXPORT_SIZE
      },
      responseType: 'blob'
    })

    // ✅ 下载文件
    const blob = response.data
    const filename = `regulations-${Date.now()}.${format}`
    saveAs(blob, filename)

    return { success: true }
  } catch (error) {
    console.error('Export failed:', error)
    return {
      success: false,
      error: 'EXPORT_FAILED',
      message: error.message
    }
  }
}

/**
 * 动态加载 XLSX 库并导出
 */
export const exportToExcel = async (data: any[], filename: string) => {
  // ✅ 动态导入，减少初始 bundle 大小
  const XLSX = await import('xlsx')

  const worksheet = XLSX.utils.json_to_sheet(data)
  const workbook = XLSX.utils.book_new()
  XLSX.utils.book_append_sheet(workbook, worksheet, 'Regulations')

  // ✅ 生成 Excel 文件
  XLSX.writeFile(workbook, filename)
}
```

---

## 七、文件结构

```
frontend/web/
├── src/
│   ├── types/
│   │   ├── api.ts                    (OpenAPI 自动生成)
│   │   ├── api-extensions.ts         (✅ 新增：扩展类型)
│   │   └── index.ts                  (✅ 修改：统一导出)
│   │
│   ├── mocks/                         (✅ 新增：Mock 配置)
│   │   ├── browser.ts
│   │   ├── server.ts
│   │   ├── handlers.ts
│   │   └── data/
│   │       ├── stats.mock.ts
│   │       └── regulations.mock.ts
│   │
│   ├── utils/
│   │   ├── echarts.ts                (✅ 新增：ECharts 按需配置)
│   │   └── export.ts                 (✅ 新增：导出工具函数)
│   │
│   ├── hooks/
│   │   └── useDetailedStats.ts       (✅ 新增：Stats 数据获取)
│   │
│   ├── pages/
│   │   ├── Stats/
│   │   │   ├── index.tsx             (✅ 修改：集成图表)
│   │   │   ├── components/
│   │   │   │   ├── SpeciesChart.tsx  (✅ 新增)
│   │   │   │   ├── BAChart.tsx       (✅ 新增)
│   │   │   │   └── TopLncRNAChart.tsx(✅ 新增)
│   │   │   └── __tests__/
│   │   │       └── Stats.test.tsx    (✅ 新增)
│   │   │
│   │   └── Regulations/
│   │       ├── index.tsx             (✅ 修改：集成筛选器)
│   │       ├── components/
│   │       │   └── AdvancedFilters.tsx (✅ 新增)
│   │       └── __tests__/
│   │           ├── Regulations.test.tsx (✅ 新增)
│   │           └── export.test.tsx   (✅ 新增)
│   │
│   ├── main.tsx                       (✅ 修改：启动 MSW)
│   └── setupTests.ts                  (✅ 新增：测试配置)
│
├── .env                               (✅ 修改：Mock 开关)
├── .env.development                   (✅ 新增)
└── package.json                       (✅ 修改：新增依赖)
```

---

## 八、实施检查清单

### 8.1 前置准备（30-45min）

#### 依赖安装

```bash
# MSW
npm install msw --save-dev
npx msw init public/ --save

# ECharts
npm install echarts echarts-for-react

# 导出库
npm install xlsx file-saver
npm install -D @types/file-saver

# Bundle 分析
npm install -D rollup-plugin-visualizer
```

#### 文件创建

```bash
# 类型定义
mkdir -p src/types
touch src/types/api-extensions.ts

# Mock 配置
mkdir -p src/mocks/data
touch src/mocks/browser.ts
touch src/mocks/server.ts
touch src/mocks/handlers.ts
touch src/mocks/data/stats.mock.ts
touch src/mocks/data/regulations.mock.ts

# 工具函数
mkdir -p src/utils
touch src/utils/echarts.ts
touch src/utils/export.ts

# Hooks
mkdir -p src/hooks
touch src/hooks/useDetailedStats.ts

# Stats 组件
mkdir -p src/pages/Stats/components
mkdir -p src/pages/Stats/__tests__
touch src/pages/Stats/components/SpeciesChart.tsx
touch src/pages/Stats/components/BAChart.tsx
touch src/pages/Stats/components/TopLncRNAChart.tsx
touch src/pages/Stats/__tests__/Stats.test.tsx

# Regulations 组件
mkdir -p src/pages/Regulations/components
mkdir -p src/pages/Regulations/__tests__
touch src/pages/Regulations/components/AdvancedFilters.tsx
touch src/pages/Regulations/__tests__/Regulations.test.tsx
touch src/pages/Regulations/__tests__/export.test.tsx

# 测试配置
touch src/setupTests.ts

# 环境变量
touch .env.development
```

#### 检查清单

- [ ] 所有依赖已安装
- [ ] `public/mockServiceWorker.js` 已生成
- [ ] 文件结构创建完成
- [ ] `.env.development` 配置 `VITE_USE_MOCK=true`

---

### 8.2 类型定义（15min）

- [ ] `src/types/api-extensions.ts`
  - [ ] `DetailedStatsResponse` 接口
  - [ ] `RegulationFilterParams` 接口
  - [ ] `RegulationExportParams` 接口

- [ ] `src/types/index.ts`
  - [ ] 导出 `api.ts` 类型
  - [ ] 导出 `api-extensions.ts` 类型

**验证**：
```bash
npm run type-check
```

---

### 8.3 Mock 配置（30min）

- [ ] `src/mocks/data/stats.mock.ts`
  - [ ] 完整的 `mockDetailedStats` 数据
  - [ ] 符合 `DetailedStatsResponse` 类型

- [ ] `src/mocks/handlers.ts`
  - [ ] `GET /api/v1/stats/detailed` handler
  - [ ] `GET /api/v1/regulations/export` handler
  - [ ] 使用类型安全的 `HttpResponse<T>`

- [ ] `src/mocks/browser.ts`
  - [ ] `setupWorker` 配置

- [ ] `src/mocks/server.ts`
  - [ ] `setupServer` 配置

- [ ] `src/main.tsx`
  - [ ] `enableMocking()` 函数
  - [ ] 双重检查（环境变量 + 构建模式）
  - [ ] `onUnhandledRequest: 'warn'`

- [ ] `src/setupTests.ts`
  - [ ] `beforeAll`、`afterEach`、`afterAll` 配置

**验证**：
```bash
npm run dev
# 打开浏览器控制台，检查 MSW 启动日志
# Network 面板应该显示 "[MSW]" 标记的请求
```

---

### 8.4 ECharts 配置（15min）

- [ ] `src/utils/echarts.ts`
  - [ ] 按需导入所需组件
  - [ ] `echarts.use([...])` 注册
  - [ ] 导出配置好的 `echarts` 实例

**验证**：
```typescript
// 测试导入
import echarts from '@/utils/echarts'
console.log(echarts.version)  // 应该输出版本号
```

---

### 8.5 Stats 页面实现（2-3h）

#### Hooks

- [ ] `src/hooks/useDetailedStats.ts`
  - [ ] 使用 React Query
  - [ ] `queryKey: ['stats-detailed']`
  - [ ] `staleTime: 10 * 60 * 1000` (10分钟缓存)

#### 图表组件

- [ ] `src/pages/Stats/components/SpeciesChart.tsx`
  - [ ] 环形饼图
  - [ ] Tooltip 配置
  - [ ] Legend 配置
  - [ ] 响应式尺寸

- [ ] `src/pages/Stats/components/BAChart.tsx`
  - [ ] 直方图
  - [ ] 渐变色
  - [ ] Y轴数值格式化（K/M）

- [ ] `src/pages/Stats/components/TopLncRNAChart.tsx`
  - [ ] 条形图
  - [ ] 数据反转（从下往上）
  - [ ] Label 显示

#### 主页面

- [ ] `src/pages/Stats/index.tsx`
  - [ ] 6个统计卡片
  - [ ] 3个图表（Suspense 包裹）
  - [ ] 响应式布局（Grid）
  - [ ] Loading、Error 状态

**验证**：
```bash
npm run dev
# 访问 /stats 页面
# 检查图表是否正常渲染
# 检查控制台无错误
```

---

### 8.6 Regulations 筛选器（1.5-2h）

#### 筛选器组件

- [ ] `src/pages/Regulations/components/AdvancedFilters.tsx`
  - [ ] 物种多选（Select）
  - [ ] lncRNA/靶基因搜索（Input）
  - [ ] 染色体多选（Select）
  - [ ] BA 范围滑块（Slider）
  - [ ] 重置按钮

#### 主页面集成

- [ ] `src/pages/Regulations/index.tsx`
  - [ ] 集中式 `filters` 状态
  - [ ] `updateFilter` 函数
  - [ ] React Query `queryKey` 绑定
  - [ ] Table `rowKey="regulation_id"`
  - [ ] `preserveSelectedRowKeys: true`

**验证**：
```bash
# 1. 测试筛选功能
- 选择物种 → 数据更新
- 输入基因名 → 数据过滤
- 调整 BA 范围 → 数据变化

# 2. 测试分页
- 切换页码 → 选中状态保持
- 更改 pageSize → 数据重新加载
```

---

### 8.7 Regulations 导出（1-1.5h）

#### 工具函数

- [ ] `src/utils/export.ts`
  - [ ] `exportRegulations()` 函数
  - [ ] 数据量检查（> 10000 条）
  - [ ] 调用导出 API
  - [ ] 使用 `saveAs` 下载

#### UI 集成

- [ ] `src/pages/Regulations/index.tsx`
  - [ ] 导出按钮 + Dropdown
  - [ ] CSV/XLSX 格式选择
  - [ ] 大数据量 Modal 提示

**验证**：
```bash
# 1. 正常导出
- 点击"导出 CSV" → 下载文件
- 打开文件 → 数据正确

# 2. 空结果导出
- 筛选到 0 条结果
- 点击导出 → 提示"没有可导出的数据"

# 3. 大数据量导出
- Mock 返回 total > 10000
- 点击导出 → 显示 Modal 提示
```

---

### 8.8 测试（30min）

#### 单元测试

- [ ] `src/pages/Stats/__tests__/Stats.test.tsx`
  - [ ] 渲染测试
  - [ ] API 错误场景

- [ ] `src/pages/Regulations/__tests__/Regulations.test.tsx`
  - [ ] 筛选功能测试
  - [ ] 分页测试

- [ ] `src/pages/Regulations/__tests__/export.test.tsx`
  - [ ] Mock `saveAs`
  - [ ] 验证导出参数
  - [ ] 空结果场景

**运行测试**：
```bash
npm run test -- --coverage
# 目标：覆盖率 > 70%
```

---

### 8.9 Bundle 优化（15min）

- [ ] `vite.config.ts`
  - [ ] `manualChunks` 配置
  - [ ] `terserOptions` 配置

- [ ] 构建分析
  ```bash
  npm run build
  npm run analyze
  ```

- [ ] 检查 Bundle 大小
  - [ ] `main` chunk < 500KB
  - [ ] `echarts` chunk < 300KB
  - [ ] `export` chunk < 200KB
  - [ ] 总大小 < 1.5MB (gzip)

---

### 8.10 文档更新（15min）

- [ ] **API 契约文档**
  - [ ] 创建 `API_CONTRACTS.md`
  - [ ] 列出所有新增 API
  - [ ] 标注实现状态（Mock/Real）

- [ ] **开发日志**
  - [ ] 更新 `CHANGELOG.md`
  - [ ] 记录 Phase 1 完成内容

- [ ] **README 更新**
  - [ ] 添加 Mock 开关说明
  - [ ] 添加开发流程指引

---

## 九、测试策略

### 9.1 测试环境配置

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
    setupFiles: './src/setupTests.ts',
    coverage: {
      provider: 'v8',
      reporter: ['text', 'json', 'html'],
      exclude: [
        'node_modules/',
        'src/setupTests.ts',
        'src/mocks/**'
      ]
    }
  },
  resolve: {
    alias: {
      '@': path.resolve(__dirname, './src')
    }
  }
})
```

### 9.2 测试用例示例

```typescript
// src/pages/Stats/__tests__/Stats.test.tsx
import { render, screen, waitFor } from '@testing-library/react'
import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import Stats from '../index'
import { server } from '@/mocks/server'
import { http, HttpResponse } from 'msw'

const queryClient = new QueryClient({
  defaultOptions: {
    queries: { retry: false }
  }
})

const wrapper = ({ children }: { children: React.ReactNode }) => (
  <QueryClientProvider client={queryClient}>
    {children}
  </QueryClientProvider>
)

describe('Stats Page', () => {
  it('should render summary cards', async () => {
    render(<Stats />, { wrapper })

    await waitFor(() => {
      expect(screen.getByText('总基因数')).toBeInTheDocument()
      expect(screen.getByText('80234')).toBeInTheDocument()
    })
  })

  it('should render charts', async () => {
    render(<Stats />, { wrapper })

    await waitFor(() => {
      expect(screen.getByText('物种基因分布')).toBeInTheDocument()
      expect(screen.getByText('Binding Affinity 分布')).toBeInTheDocument()
    })
  })

  it('should handle API error', async () => {
    server.use(
      http.get('/api/v1/stats/detailed', () => {
        return new HttpResponse(null, { status: 500 })
      })
    )

    render(<Stats />, { wrapper })

    await waitFor(() => {
      expect(screen.getByText(/加载失败/)).toBeInTheDocument()
    })
  })
})
```

---

## 十、风险缓解措施

### 10.1 风险矩阵

| 风险 | 影响 | 概率 | 缓解措施 | 检查点 |
|------|------|------|---------|--------|
| **后端 API 缺失** | 高 | 高 | 1. 先定义类型契约<br>2. 使用 MSW Mock<br>3. 前后端并行开发 | ✅ API 契约文档<br>✅ Mock 数据准备 |
| **大数据性能** | 高 | 中 | 1. 服务端分页（优先）<br>2. 限制 pageSize ≤ 200<br>3. 图表数据采样 | ✅ 分页测试<br>✅ 性能监控 |
| **状态漂移** | 中 | 中 | 1. 筛选器状态提升<br>2. React Query queryKey 绑定<br>3. rowKey 稳定性 | ✅ 状态一致性测试 |
| **Bundle 过大** | 中 | 高 | 1. ECharts 按需导入<br>2. 导出库动态 import<br>3. Bundle 分析 | ✅ 打包大小 < 1.5MB |
| **样式冲突** | 低 | 低 | 1. 沿用 Ant Design 主题<br>2. 响应式断点统一 | ✅ 视觉一致性检查 |
| **测试覆盖不足** | 中 | 中 | 1. Mock First 开发<br>2. 单元测试 + 集成测试 | ✅ 覆盖率 > 70% |

### 10.2 关键决策记录

| 决策 | 理由 | 替代方案 |
|------|------|---------|
| **MSW 而非 Mock.js** | 1. 更接近真实 API<br>2. 浏览器和 Node 统一<br>3. 支持 TypeScript | Mock.js、json-server |
| **ECharts 而非 Recharts** | 1. 性能更好<br>2. 图表类型丰富<br>3. 生态成熟 | Recharts、Chart.js |
| **服务端分页而非虚拟滚动** | 1. 减少前端内存压力<br>2. 更好的性能<br>3. 符合 RESTful 规范 | 虚拟滚动、无限滚动 |
| **动态 import 导出库** | 1. 减少初始 bundle<br>2. 按需加载<br>3. 提升首屏速度 | 静态导入 |

---

## 十一、下一步行动

### 11.1 Phase 1 实施（下次会话）

**时间估算**：5-6 小时

1. **前置准备** (45min)
   - 安装依赖
   - 创建文件结构
   - 配置 Mock

2. **Stats 页面** (2.5h)
   - 3 个图表组件
   - 主页面集成
   - 基础测试

3. **Regulations 筛选** (1.5h)
   - 筛选器组件
   - 状态管理
   - 集成测试

4. **Regulations 导出** (1h)
   - 导出工具函数
   - UI 集成
   - 测试

5. **验收测试** (30min)
   - 手动测试
   - Bundle 分析
   - 文档更新

### 11.2 Phase 2 规划（未来）

- Home 页面全局搜索
- Regulations 批量操作
- Stats 导出 PDF 报告
- 性能优化（虚拟滚动、WebWorker）

---

## 十二、参考资料

### 12.1 技术文档

- [MSW 官方文档](https://mswjs.io/)
- [ECharts 官方文档](https://echarts.apache.org/)
- [React Query 官方文档](https://tanstack.com/query/latest)
- [Ant Design 官方文档](https://ant.design/)

### 12.2 内部文档

- [API 类型定义](./web/src/types/api.ts)
- [数据库设计文档](../docs/DATABASE_DESIGN_FINAL.md)
- [前端架构文档](./SESSION_NETWORK_VISUALIZATION.md)

---

**文档版本**: v1.0
**最后更新**: 2025-11-27
**作者**: Claude Code
**状态**: ✅ 准备就绪，可开始实施
