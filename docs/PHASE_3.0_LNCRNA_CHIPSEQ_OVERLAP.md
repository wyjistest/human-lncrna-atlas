# Phase 3.0: LncRNA-ChIP-seq Overlap Analysis

> **状态**: Planning → In Progress
> **创建日期**: 2025-12-07
> **预计完成**: 2025-12-21 (2 weeks)
> **负责人**: Development Team
> **优先级**: High (P0)

---

## 📋 目录

- [1. 项目概述](#1-项目概述)
- [2. 技术架构](#2-技术架构)
- [3. 开发任务清单](#3-开发任务清单)
  - [Phase 1: MVP 核心功能 (5 天)](#phase-1-mvp-核心功能-5-天)
  - [Phase 2: 高级功能 (5 天)](#phase-2-高级功能-5-天)
  - [Phase 3: 测试和优化 (4 天)](#phase-3-测试和优化-4-天)
- [4. 验收标准](#4-验收标准)
- [5. 风险和依赖](#5-风险和依赖)
- [6. 进度追踪](#6-进度追踪)

---

## 1. 项目概述

### 1.1 功能描述

开发 **lncRNA 结合位点与 ChIP-seq peaks 的基因组区间重叠分析** 功能，打通调控网络数据和表观遗传数据。

### 1.2 核心价值

- **科研价值**: 揭示 lncRNA 调控的表观遗传机制
- **数据整合**: 连接 80 万调控关系 + 225 万 ChIP-seq peaks
- **分析能力**: 支持多维度筛选（mark 类型、细胞系、染色体、BA 阈值）
- **可视化**: 提供表格、统计卡片、Heatmap、图表等多种展示方式

### 1.3 技术可行性验证

✅ **性能测试通过** (2025-12-07):
- 基础重叠查询 (chr1): **2.913 ms**
- 带过滤查询 (chr1, H3K27me3, BA≥60): **0.601 ms**
- 索引优化完善: `idx_regulations_igv` + `chipseq_peaks_*_idx`

✅ **架构适配性**:
- 后端: 100% 复用 ChIP-seq API 模式
- 前端: 80% 组件可复用

---

## 2. 技术架构

### 2.1 数据流设计

```
┌─────────────────────────────────────────────────────────────┐
│                        User Interface                        │
│  (React Components: Table, Charts, Filters)                 │
└────────────────────────┬────────────────────────────────────┘
                         │
                         ▼
┌─────────────────────────────────────────────────────────────┐
│                     React Query Layer                        │
│  (useLncRNAChIPSeqOverlaps, useSummary, useHeatmap)        │
└────────────────────────┬────────────────────────────────────┘
                         │
                         ▼
┌─────────────────────────────────────────────────────────────┐
│                    FastAPI Endpoints                         │
│  GET /api/v1/lncrna-chipseq-overlap                         │
│  GET /api/v1/lncrna-chipseq-overlap/summary                 │
│  GET /api/v1/lncrna-chipseq-overlap/heatmap                 │
└────────────────────────┬────────────────────────────────────┘
                         │
                         ▼
┌─────────────────────────────────────────────────────────────┐
│                    PostgreSQL Database                       │
│  regulations (80万) JOIN chipseq_peaks (225万)              │
│  使用空间索引: idx_regulations_igv                           │
└─────────────────────────────────────────────────────────────┘
```

### 2.2 核心查询逻辑

```sql
-- 区间重叠判断条件
SELECT
    r.regulation_id,
    r.lncrna_gene_id,
    r.target_gene_id,
    r.binding_affinity,
    p.peak_id,
    p.fold_enrichment,
    p.qvalue,
    m.mark_name,
    e.cell_type,
    -- 计算重叠区间
    GREATEST(r.best_peak_start, p.peak_start) AS overlap_start,
    LEAST(r.best_peak_end, p.peak_end) AS overlap_end,
    LEAST(r.best_peak_end, p.peak_end) - GREATEST(r.best_peak_start, p.peak_start) AS overlap_length
FROM regulations r
JOIN chipseq_peaks_human p ON
    r.species_id = p.species_id
    AND r.best_peak_chr = p.chromosome
    AND r.best_peak_start < p.peak_end      -- 区间重叠条件
    AND r.best_peak_end > p.peak_start      -- 区间重叠条件
JOIN chipseq_experiments e ON p.experiment_id = e.experiment_id
JOIN epigenetic_mark_types m ON e.mark_type_id = m.mark_type_id
WHERE
    r.species_id = 1
    AND e.is_active = TRUE
    AND (:mark_type IS NULL OR m.mark_name = ANY(:mark_type))
    AND (:cell_type IS NULL OR e.cell_type = ANY(:cell_type))
    AND (:min_ba IS NULL OR r.binding_affinity >= :min_ba)
    AND (:min_peak_strength IS NULL OR p.fold_enrichment >= :min_peak_strength)
    AND (:max_qvalue IS NULL OR p.qvalue IS NULL OR p.qvalue <= :max_qvalue)
ORDER BY r.binding_affinity DESC, p.fold_enrichment DESC
LIMIT :page_size OFFSET :offset;
```

### 2.3 API 契约

#### 端点 1: 获取重叠数据 (分页)

```
GET /api/v1/lncrna-chipseq-overlap
```

**Query Parameters**:
```typescript
{
  lncrna_gene_id?: number          // 可选，特定 lncRNA
  target_gene_id?: number          // 可选，特定靶基因
  mark_type?: string               // 可选，"H3K27me3,H3K4me3"
  cell_type?: string               // 可选，"K562,GM12878"
  chromosome?: string              // 可选，"chr1"
  min_overlap_length?: number      // 可选，最小重叠长度 (bp)
  min_binding_affinity?: number    // 可选，最小 BA 值
  min_peak_strength?: number       // 可选，最小 fold enrichment
  max_qvalue?: number              // 可选，最大 Q-value (默认 0.05)
  page?: number                    // 分页，默认 1
  page_size?: number               // 每页大小，默认 100，最大 1000
  sort_by?: string                 // 排序字段
  sort_order?: 'asc' | 'desc'      // 排序方向
}
```

**Response**:
```typescript
{
  total: number
  page: number
  page_size: number
  items: OverlapResult[]
}

interface OverlapResult {
  overlap_id: string               // "reg_{regulation_id}_peak_{peak_id}"
  lncrna_gene_id: number
  lncrna_name: string
  target_gene_id: number
  target_gene_name: string
  mark_type: string
  mark_category: 'repressive' | 'activating' | 'bivalent_component'
  cell_type: string
  chromosome: string
  lncrna_binding_start: number
  lncrna_binding_end: number
  peak_start: number
  peak_end: number
  overlap_start: number
  overlap_end: number
  overlap_length: number
  binding_affinity: number
  peak_fold_enrichment: number
  peak_qvalue: number | null
}
```

#### 端点 2: 统计摘要

```
GET /api/v1/lncrna-chipseq-overlap/summary
```

**Response**:
```typescript
{
  total_overlaps: number
  unique_lncrnas: number
  unique_target_genes: number
  unique_marks: number
  unique_cell_types: number
  avg_overlap_length: number
  avg_binding_affinity: number
  avg_peak_strength: number
  by_mark_type: Array<{
    mark_type: string
    count: number
    avg_strength: number
  }>
  by_cell_type: Array<{
    cell_type: string
    count: number
  }>
}
```

#### 端点 3: Heatmap 矩阵

```
GET /api/v1/lncrna-chipseq-overlap/heatmap
```

**Query Parameters**:
```typescript
{
  x_axis: 'mark_type' | 'cell_type'
  y_axis: 'lncrna' | 'target_gene'
  metric: 'count' | 'avg_strength' | 'total_overlap_length'
  top_n?: number  // 最多返回 top N 个基因，默认 100
}
```

**Response**:
```typescript
{
  matrix: number[][]           // 矩阵值 [y][x]
  x_labels: string[]           // X 轴标签
  y_labels: string[]           // Y 轴标签
  metric: string               // 度量单位
  max_value: number            // 矩阵最大值（用于 colormap）
}
```

---

## 3. 开发任务清单

### Phase 1: MVP 核心功能 (5 天)

#### 🔨 任务 1.1: 后端 API 基础框架 (Day 1)

**负责人**: Backend Developer
**预计时间**: 1 天

**子任务**:
- [ ] 创建文件 `frontend/backend/app/routers/lncrna_chipseq_overlap.py`
- [ ] 创建 Pydantic schemas `frontend/backend/app/schemas/lncrna_chipseq_overlap.py`
  - [ ] `OverlapFilters` (查询参数)
  - [ ] `OverlapResult` (单条结果)
  - [ ] `OverlapResponse` (分页响应)
  - [ ] `OverlapSummary` (统计摘要)
- [ ] 在 `main.py` 中注册路由
- [ ] 创建基础端点 `GET /lncrna-chipseq-overlap` (返回空列表)

**验收标准**:
- ✅ API 端点可访问，返回 200 状态码
- ✅ Swagger 文档自动生成
- ✅ 参数验证正常工作（负数被拒绝，超大 page_size 被限制）

**测试要求**:
```bash
# 手动测试
curl "http://localhost:8000/api/v1/lncrna-chipseq-overlap?page=1&page_size=10"

# 预期: {"total": 0, "page": 1, "page_size": 10, "items": []}
```

---

#### 🔨 任务 1.2: 实现核心 SQL 查询逻辑 (Day 1-2)

**负责人**: Backend Developer
**预计时间**: 1.5 天

**子任务**:
- [ ] 实现 `get_lncrna_chipseq_overlaps()` 函数
  - [ ] 编写 SQL 查询（参考 2.2 节）
  - [ ] 支持多条件筛选（mark_type, cell_type, chromosome, BA, peak_strength, qvalue）
  - [ ] 实现分页和排序
  - [ ] 计算 overlap_start, overlap_end, overlap_length
- [ ] 添加查询优化
  - [ ] 使用 PreparedStatement (SQLAlchemy `text()`)
  - [ ] 添加查询超时保护（timeout=30s）
  - [ ] 限制最大结果集（max_page_size=1000）

**验收标准**:
- ✅ 查询返回正确的重叠结果
- ✅ 筛选条件工作正常（mark_type, cell_type, BA 等）
- ✅ 分页逻辑正确（page 1, page 2 数据不重复）
- ✅ 查询响应时间 < 2s（目标 < 1s）
- ✅ 空结果时返回 `{"total": 0, "items": []}`

**测试要求**:
```bash
# 测试基础查询
curl "http://localhost:8000/api/v1/lncrna-chipseq-overlap?chromosome=chr1&page=1&page_size=10"

# 测试筛选
curl "http://localhost:8000/api/v1/lncrna-chipseq-overlap?mark_type=H3K27me3&min_binding_affinity=60&page=1&page_size=10"

# 测试性能
time curl "http://localhost:8000/api/v1/lncrna-chipseq-overlap?chromosome=chr1&page=1&page_size=100"
```

**SQL 性能验证**:
```sql
-- 在 psql 中测试执行计划
EXPLAIN ANALYZE
SELECT ...  -- 完整查询
WHERE r.best_peak_chr = 'chr1'
LIMIT 100;

-- 预期: Execution Time < 50 ms
```

---

#### 🔨 任务 1.3: 前端类型定义和 API 集成 (Day 2)

**负责人**: Frontend Developer
**预计时间**: 0.5 天

**子任务**:
- [ ] 创建 TypeScript 类型 `frontend/web/src/types/lncRNAChIPSeqOverlap.ts`
  ```typescript
  export type OverlapFilters = { ... }
  export type OverlapResult = { ... }
  export type OverlapResponse = { ... }
  export type OverlapSummary = { ... }
  ```
- [ ] 创建 API 客户端 `frontend/web/src/api/lncRNAChIPSeqOverlapApi.ts`
  ```typescript
  export const lncRNAChIPSeqOverlapApi = {
    getOverlaps: (filters: OverlapFilters) => ...
    getSummary: (filters?: OverlapFilters) => ...
    getHeatmap: (config: HeatmapConfig) => ...
  }
  ```

**验收标准**:
- ✅ TypeScript 类型无编译错误
- ✅ API 客户端可以成功调用后端端点
- ✅ 返回数据类型匹配 TypeScript 定义

**测试要求**:
```typescript
// 在浏览器 console 测试
import { lncRNAChIPSeqOverlapApi } from '@/api/lncRNAChIPSeqOverlapApi'

const response = await lncRNAChIPSeqOverlapApi.getOverlaps({
  chromosome: 'chr1',
  page: 1,
  page_size: 10
})

console.log(response.data) // 应该返回数据
```

---

#### 🔨 任务 1.4: React Query Hooks (Day 2-3)

**负责人**: Frontend Developer
**预计时间**: 0.5 天

**子任务**:
- [ ] 创建 `frontend/web/src/hooks/useLncRNAChIPSeqOverlap.ts`
  ```typescript
  export function useLncRNAChIPSeqOverlaps(filters, options) { ... }
  export function useLncRNAChIPSeqOverlapSummary(filters) { ... }
  export function useLncRNAChIPSeqHeatmap(config) { ... }
  export function usePrefetchOverlaps() { ... }
  ```
- [ ] 配置缓存策略 (staleTime: 30 * 60 * 1000)
- [ ] 添加错误处理和重试逻辑

**验收标准**:
- ✅ Hooks 正常工作，自动缓存数据
- ✅ 错误处理正确（网络错误、API 错误）
- ✅ 加载状态正确（isLoading, isFetching）

---

#### 🔨 任务 1.5: 改造 FilterPanel 组件 (Day 3)

**负责人**: Frontend Developer
**预计时间**: 0.5 天

**子任务**:
- [ ] 复制 `ChIPSeqPeaksTable/FilterPanel.tsx` → `LncRNAChIPSeqOverlapTable/OverlapFilterPanel.tsx`
- [ ] 添加新筛选项:
  - [ ] Target Gene 搜索框 (AutoComplete)
  - [ ] 最小重叠长度滑块 (Slider, 0-10000 bp)
  - [ ] 染色体选择器 (Select, chr1-chr22 + chrX + chrY)
- [ ] 保留现有筛选项:
  - [ ] Mark 类型 (MarkSelector, 多选)
  - [ ] 细胞系 (Select, 多选)
  - [ ] 最小 BA (InputNumber)
  - [ ] 最小 Peak 强度 (InputNumber)
  - [ ] 最大 Q-value (InputNumber)

**验收标准**:
- ✅ 所有筛选项正常工作
- ✅ 筛选条件改变时触发 API 查询
- ✅ 重置按钮清空所有筛选条件

---

#### 🔨 任务 1.6: 改造 Table 组件 (Day 3)

**负责人**: Frontend Developer
**预计时间**: 0.5 天

**子任务**:
- [ ] 复制 `ChIPSeqPeaksTable/PeaksTable.tsx` → `LncRNAChIPSeqOverlapTable/OverlapTable.tsx`
- [ ] 调整列定义:
  ```typescript
  columns = [
    { title: 'lncRNA', dataIndex: 'lncrna_name', width: 150 },
    { title: 'Target Gene', dataIndex: 'target_gene_name', width: 150 },
    { title: 'Mark', dataIndex: 'mark_type', width: 100, render: (v) => <Tag color={getMarkColor(v)}>{v}</Tag> },
    { title: 'Cell Type', dataIndex: 'cell_type', width: 120 },
    { title: 'Chr', dataIndex: 'chromosome', width: 80 },
    { title: 'Overlap Start', dataIndex: 'overlap_start', width: 120, sorter: true },
    { title: 'Overlap Length', dataIndex: 'overlap_length', width: 120, sorter: true },
    { title: 'BA', dataIndex: 'binding_affinity', width: 80, sorter: true },
    { title: 'Peak Strength', dataIndex: 'peak_fold_enrichment', width: 120, sorter: true },
    { title: 'Q-value', dataIndex: 'peak_qvalue', width: 100, render: (v) => v?.toExponential(2) }
  ]
  ```
- [ ] 配置分页（100 行/页，支持 10/20/50/100/500/1000）
- [ ] 配置排序（支持多列排序）

**验收标准**:
- ✅ 表格正确展示所有列
- ✅ 分页正常工作
- ✅ 排序正常工作
- ✅ 加载状态和空状态正确显示

---

#### 🔨 任务 1.7: 统计卡片组件 (Day 4)

**负责人**: Frontend Developer
**预计时间**: 0.3 天

**子任务**:
- [ ] 复制 `ChIPSeqPeaksTable/StatsCards.tsx` → `LncRNAChIPSeqOverlapTable/OverlapStatsCards.tsx`
- [ ] 调整统计维度:
  ```typescript
  <Row gutter={[16, 16]}>
    <Col xs={24} sm={12} md={6}>
      <Card><Statistic title="总重叠数" value={summary.total_overlaps} /></Card>
    </Col>
    <Col xs={24} sm={12} md={6}>
      <Card><Statistic title="涉及 lncRNA" value={summary.unique_lncrnas} /></Card>
    </Col>
    <Col xs={24} sm={12} md={6}>
      <Card><Statistic title="涉及靶基因" value={summary.unique_target_genes} /></Card>
    </Col>
    <Col xs={24} sm={12} md={6}>
      <Card><Statistic title="平均重叠长度" value={summary.avg_overlap_length} suffix="bp" /></Card>
    </Col>
  </Row>
  ```

**验收标准**:
- ✅ 统计卡片正确展示数据
- ✅ 数字格式化正确（千分位分隔符）

---

#### 🔨 任务 1.8: 主容器组件 (Day 4-5)

**负责人**: Frontend Developer
**预计时间**: 1 天

**子任务**:
- [ ] 创建 `frontend/web/src/components/LncRNAChIPSeqOverlapTable/index.tsx`
- [ ] 组装所有子组件:
  ```tsx
  <Space direction="vertical" size="large" style={{ width: '100%' }}>
    <OverlapStatsCards summary={summaryData} />
    <OverlapFilterPanel filters={filters} onFiltersChange={handleFiltersChange} />
    <Card title={`重叠分析结果 (${data.total})`}>
      <OverlapTable
        items={data.items}
        total={data.total}
        page={data.page}
        pageSize={data.page_size}
        filters={filters}
        onFiltersChange={handleFiltersChange}
      />
    </Card>
  </Space>
  ```
- [ ] 实现状态管理（filters, page, sort）
- [ ] 添加 Loading 和 Error 状态处理

**验收标准**:
- ✅ 所有子组件正确渲染
- ✅ 筛选、分页、排序联动正常
- ✅ 加载和错误状态友好提示

---

#### 🔨 任务 1.9: 路由和页面集成 (Day 5)

**负责人**: Frontend Developer
**预计时间**: 0.5 天

**子任务**:
- [ ] 在 `App.tsx` 中添加新路由:
  ```tsx
  <Route
    path="/lncrna-chipseq-overlap"
    element={<LncRNAChIPSeqOverlapPage />}
  />
  ```
- [ ] 创建页面组件 `frontend/web/src/pages/LncRNAChIPSeqOverlapPage.tsx`
- [ ] 添加页面标题和面包屑导航
- [ ] 在导航菜单中添加入口

**验收标准**:
- ✅ 访问 `/lncrna-chipseq-overlap` 可以打开页面
- ✅ 页面标题和面包屑正确显示
- ✅ 导航菜单有入口链接

---

#### 🔨 任务 1.10: 国际化翻译 (Day 5)

**负责人**: Frontend Developer
**预计时间**: 0.3 天

**子任务**:
- [ ] 添加中文翻译 `frontend/web/src/i18n/locales/zh-CN/overlap.json`:
  ```json
  {
    "title": "lncRNA-ChIP-seq 重叠分析",
    "filters": {
      "targetGene": "靶基因",
      "minOverlapLength": "最小重叠长度",
      "chromosome": "染色体"
    },
    "table": {
      "lncRNA": "lncRNA",
      "targetGene": "靶基因",
      "overlapLength": "重叠长度",
      "bindingAffinity": "结合亲和力"
    }
  }
  ```
- [ ] 添加英文翻译 `frontend/web/src/i18n/locales/en/overlap.json`
- [ ] 在组件中使用 `useTranslation('overlap')`

**验收标准**:
- ✅ 中英文切换正常
- ✅ 所有文本都已翻译（无硬编码中文/英文）

---

### Phase 2: 高级功能 (5 天)

#### 🔨 任务 2.1: 统计摘要 API 端点 (Day 6)

**负责人**: Backend Developer
**预计时间**: 0.5 天

**子任务**:
- [ ] 实现 `GET /api/v1/lncrna-chipseq-overlap/summary` 端点
- [ ] SQL 查询:
  ```sql
  SELECT
    COUNT(*) AS total_overlaps,
    COUNT(DISTINCT r.lncrna_gene_id) AS unique_lncrnas,
    COUNT(DISTINCT r.target_gene_id) AS unique_target_genes,
    COUNT(DISTINCT m.mark_name) AS unique_marks,
    COUNT(DISTINCT e.cell_type) AS unique_cell_types,
    AVG(overlap_length) AS avg_overlap_length,
    AVG(r.binding_affinity) AS avg_binding_affinity,
    AVG(p.fold_enrichment) AS avg_peak_strength
  FROM ...
  ```
- [ ] 添加 by_mark_type 和 by_cell_type 分组统计

**验收标准**:
- ✅ 返回正确的统计数据
- ✅ 查询响应时间 < 1s

---

#### 🔨 任务 2.2: Mark 分布柱状图 (Day 6)

**负责人**: Frontend Developer
**预计时间**: 0.5 天

**子任务**:
- [ ] 创建 `OverlapMarkDistributionChart.tsx`
- [ ] 使用 ECharts 渲染柱状图:
  ```typescript
  const option = {
    xAxis: { type: 'category', data: markTypes },
    yAxis: { type: 'value', name: 'Overlap Count' },
    series: [{
      type: 'bar',
      data: counts,
      itemStyle: { color: (params) => getMarkColor(markTypes[params.dataIndex]) }
    }]
  }
  ```

**验收标准**:
- ✅ 图表正确展示 mark 分布
- ✅ 颜色与 mark 配置一致

---

#### 🔨 任务 2.3: 细胞系分布饼图 (Day 6-7)

**负责人**: Frontend Developer
**预计时间**: 0.5 天

**子任务**:
- [ ] 创建 `OverlapCellTypeChart.tsx`
- [ ] 使用 ECharts 渲染饼图

**验收标准**:
- ✅ 图表正确展示细胞系分布
- ✅ 颜色与细胞系配置一致

---

#### 🔨 任务 2.4: Heatmap API 端点 (Day 7)

**负责人**: Backend Developer
**预计时间**: 1 天

**子任务**:
- [ ] 实现 `GET /api/v1/lncrna-chipseq-overlap/heatmap` 端点
- [ ] 支持不同的轴配置 (x_axis, y_axis, metric)
- [ ] 实现 top_n 限制（避免返回过大矩阵）

**验收标准**:
- ✅ 返回正确的矩阵数据
- ✅ 支持不同的轴和度量组合

---

#### 🔨 任务 2.5: Heatmap 组件 (Day 8)

**负责人**: Frontend Developer
**预计时间**: 1 天

**子任务**:
- [ ] 创建 `OverlapHeatmapMatrix.tsx`
- [ ] 复用 `CellLineHeatmapMatrix.tsx` 的逻辑
- [ ] 使用 ECharts heatmap 渲染

**验收标准**:
- ✅ 热力图正确展示数据
- ✅ 支持轴切换（mark × lncRNA, mark × target gene）
- ✅ 支持度量切换（count, avg_strength）

---

#### 🔨 任务 2.6: 导出功能 (Day 9)

**负责人**: Frontend Developer
**预计时间**: 0.5 天

**子任务**:
- [ ] 创建 `OverlapExportButton.tsx`
- [ ] 实现 CSV 导出
- [ ] 实现 BED 导出（可选）

**验收标准**:
- ✅ CSV 导出包含所有列
- ✅ 文件名格式: `lncrna-chipseq-overlap-{date}.csv`
- ✅ 下载正常工作

---

#### 🔨 任务 2.7: 性能优化 (Day 9-10)

**负责人**: Full Stack
**预计时间**: 1 天

**子任务**:
- [ ] 后端: 添加 Redis 缓存（统计摘要）
- [ ] 前端: 虚拟滚动配置（Table virtual scroll）
- [ ] 前端: 图表懒加载（React.lazy）
- [ ] 前端: 预设筛选方案（高可信度、抑制性 Marks 等）

**验收标准**:
- ✅ 表格渲染 10,000 行 < 1s
- ✅ 筛选响应时间 < 100ms
- ✅ 统计摘要缓存 30 分钟

---

### Phase 3: 测试和优化 (4 天)

#### 🔨 任务 3.1: 后端单元测试 (Day 11)

**负责人**: Backend Developer
**预计时间**: 1 天

**子任务**:
- [ ] 创建 `tests/test_lncrna_chipseq_overlap_unit.py`
- [ ] 测试区间重叠逻辑（20 tests）
- [ ] 测试 API 参数验证（15 tests）
- [ ] 测试边界条件（10 tests）

**验收标准**:
- ✅ 单元测试覆盖率 ≥ 95%
- ✅ 所有测试通过

---

#### 🔨 任务 3.2: 后端集成测试 (Day 11-12)

**负责人**: Backend Developer
**预计时间**: 1 天

**子任务**:
- [ ] 创建 `tests/test_lncrna_chipseq_overlap_integration.py`
- [ ] 测试数据库查询正确性（15 tests）
- [ ] 测试性能基准（10 tests）
- [ ] 测试大数据量（5 tests）

**验收标准**:
- ✅ 集成测试覆盖率 ≥ 85%
- ✅ 性能测试通过（查询 < 2s）

---

#### 🔨 任务 3.3: E2E 测试 (Day 12-13)

**负责人**: QA / Frontend Developer
**预计时间**: 1.5 天

**子任务**:
- [ ] 创建 `frontend/web/e2e/lncrna-chipseq-overlap.spec.ts`
- [ ] 测试用户筛选流程（10 tests）
- [ ] 测试分页和排序（8 tests）
- [ ] 测试导出功能（4 tests）
- [ ] 跨浏览器测试（Chrome, Firefox, Safari）

**验收标准**:
- ✅ E2E 测试覆盖关键路径 100%
- ✅ 所有浏览器测试通过

---

#### 🔨 任务 3.4: 文档和代码 Review (Day 14)

**负责人**: Team Lead
**预计时间**: 0.5 天

**子任务**:
- [ ] API 文档完善（Swagger 注释）
- [ ] README 更新
- [ ] 代码 Review 和优化
- [ ] 性能监控配置

**验收标准**:
- ✅ API 文档完整准确
- ✅ 代码符合项目规范
- ✅ 无 P0/P1 级代码问题

---

## 4. 验收标准

### 4.1 功能验收

- [ ] **核心功能**:
  - [x] API 端点正常工作（/overlap, /summary, /heatmap）
  - [x] 前端页面可访问，组件正常渲染
  - [x] 筛选、分页、排序功能正常
  - [x] 统计卡片正确展示数据

- [ ] **高级功能**:
  - [x] Mark 分布图和细胞系分布图正常渲染
  - [x] Heatmap 正常工作，支持轴切换
  - [x] 导出功能正常（CSV 格式）

- [ ] **国际化**:
  - [x] 中英文切换正常
  - [x] 所有文本已翻译

### 4.2 性能验收

- [ ] **API 性能**:
  - [x] 单基因查询 < 2s（目标 < 1s）
  - [x] 统计摘要查询 < 1s
  - [x] 分页查询 < 1s
  - [x] Heatmap 查询 < 3s

- [ ] **前端性能**:
  - [x] 首屏加载时间 < 2s
  - [x] 表格渲染 10,000 行 < 1s
  - [x] 筛选响应时间 < 100ms
  - [x] 图表渲染 < 1s

### 4.3 质量验收

- [ ] **测试覆盖**:
  - [x] 单元测试覆盖率 ≥ 85%
  - [x] 集成测试通过（30+ tests）
  - [x] E2E 测试通过（25+ tests）

- [ ] **代码质量**:
  - [x] TypeScript 无编译错误
  - [x] ESLint / Prettier 检查通过
  - [x] 无 P0/P1 级 Bug

### 4.4 文档验收

- [ ] **API 文档**:
  - [x] Swagger 文档完整
  - [x] 所有端点有描述和示例

- [ ] **用户文档**:
  - [x] 功能使用说明
  - [x] FAQ 常见问题

---

## 5. 风险和依赖

### 5.1 高风险项

| 风险 | 影响 | 缓解措施 | 责任人 | 状态 |
|------|------|---------|--------|------|
| regulations 表坐标数据不完整 | 🔴 High | 先验证数据质量，对缺失数据返回 NULL | Backend Dev | ⏳ Pending |
| 用户全基因组查询导致超时 | 🔴 High | API 强制要求至少一个筛选条件 | Backend Dev | ⏳ Pending |
| 大结果集渲染性能问题 | 🟡 Medium | 使用虚拟滚动 + 分页限制 | Frontend Dev | ⏳ Pending |

### 5.2 依赖项

| 依赖项 | 状态 | 备注 |
|--------|------|------|
| PostgreSQL 索引优化 | ✅ 完成 | idx_regulations_igv 已存在 |
| ChIP-seq 数据完整性 | ✅ 完成 | 225 万 peaks 已导入 |
| Regulations 数据完整性 | ⏳ 待验证 | 需运行数据质量检查 |
| 现有 ChIP-seq 组件 | ✅ 完成 | 可直接复用 |

---

## 6. 进度追踪

### 6.1 整体进度

```
Phase 1 (MVP):        [░░░░░░░░░░] 0%  (Day 1-5)
Phase 2 (Advanced):   [░░░░░░░░░░] 0%  (Day 6-10)
Phase 3 (Testing):    [░░░░░░░░░░] 0%  (Day 11-14)
─────────────────────────────────────────
总体进度:              [░░░░░░░░░░] 0%
```

### 6.2 每日站会检查清单

**Daily Standup Questions**:
1. 昨天完成了什么？
2. 今天计划做什么？
3. 有什么阻碍吗？
4. 需要帮助吗？

### 6.3 里程碑检查点

| 里程碑 | 日期 | 状态 | 交付物 |
|--------|------|------|--------|
| **M1: 数据质量验证** | Day 1 | ⏳ Pending | 数据质量报告 |
| **M2: MVP 后端完成** | Day 2 | ⏳ Pending | API 可用，Swagger 文档 |
| **M3: MVP 前端完成** | Day 5 | ⏳ Pending | 可用的 UI 页面 |
| **M4: 高级功能完成** | Day 10 | ⏳ Pending | Heatmap + 图表 + 导出 |
| **M5: 测试完成** | Day 13 | ⏳ Pending | 测试报告（85%+ 覆盖）|
| **M6: 上线准备** | Day 14 | ⏳ Pending | 文档 + Review 完成 |

---

## 7. 快速启动指南

### 7.1 Day 1 立即行动

#### Step 1: 数据质量验证

```bash
cd <repo-root>

# 1. 验证 regulations 表坐标数据完整性
psql -U amax -d lncrna_production <<'EOF'
\timing

SELECT
    COUNT(*) AS total_regulations,
    COUNT(best_peak_chr) AS has_chr,
    COUNT(best_peak_start) AS has_start,
    COUNT(best_peak_end) AS has_end,
    ROUND(100.0 * COUNT(best_peak_chr) / COUNT(*), 2) AS chr_coverage_pct
FROM regulations
WHERE species_id = 1;

-- 查看各染色体的数据分布
SELECT
    best_peak_chr AS chromosome,
    COUNT(*) AS regulation_count
FROM regulations
WHERE species_id = 1
  AND best_peak_chr IS NOT NULL
GROUP BY best_peak_chr
ORDER BY regulation_count DESC
LIMIT 25;
EOF
```

#### Step 2: 创建后端文件结构

```bash
cd <repo-root>/frontend/backend

# 创建文件
touch routers/lncrna_chipseq_overlap.py
touch schemas/lncrna_chipseq_overlap.py

# 开始开发
code routers/lncrna_chipseq_overlap.py
```

#### Step 3: 创建前端文件结构

```bash
cd <repo-root>/frontend/web/src

# 创建目录和文件
mkdir -p components/LncRNAChIPSeqOverlapTable
mkdir -p pages
mkdir -p types
mkdir -p api
mkdir -p hooks
mkdir -p i18n/locales/zh-CN/overlap.json
mkdir -p i18n/locales/en/overlap.json

# 开始开发
code components/LncRNAChIPSeqOverlapTable/index.tsx
```

### 7.2 开发环境准备

```bash
# 后端
cd <repo-root>/frontend/backend
source venv/bin/activate
python3 -m uvicorn main:app --reload --host 0.0.0.0 --port 8000

# 前端
cd <repo-root>/frontend/web
npm run dev

# 数据库
psql -U amax -d lncrna_production
```

---

## 8. 参考资源

### 8.1 现有代码参考

- **后端 ChIP-seq API**: `frontend/backend/app/routers/chipseq.py`
- **前端 ChIP-seq 组件**: `frontend/web/src/components/ChIPSeqPeaksTable/`
- **数据库 Schema**: `schema/v2.3/01_core.sql`, `schema/v2.3/04_extension_phase2.sql`
- **测试示例**: `frontend/backend/tests/test_chipseq_api.py`

### 8.2 技术文档

- **FastAPI**: https://fastapi.tiangolo.com/
- **React Query**: https://tanstack.com/query/latest/docs/react/overview
- **Ant Design**: https://ant.design/components/overview/
- **ECharts**: https://echarts.apache.org/handbook/en/get-started/
- **PostgreSQL 空间查询**: https://www.postgresql.org/docs/current/rangetypes.html

### 8.3 项目文档

- **Phase 2.3 架构设计**: `docs/PHASE_2.3_CHIPSEQ_ARCHITECTURE.md`
- **数据库设计**: `docs/DATABASE_DESIGN_FINAL.md`
- **API 使用指南**: `frontend/backend/docs/API_GUIDE.md`

---

## 9. 更新日志

| 日期 | 版本 | 变更内容 | 作者 |
|------|------|---------|------|
| 2025-12-07 | v1.0 | 初始版本，完整开发计划 | Claude (AI Assistant) |

---

**文档状态**: ✅ 已完成
**下一步行动**: 运行 Day 1 数据质量验证脚本

---

**注意事项**:
1. 所有任务的 checkbox 请在完成后打勾 ✅
2. 每日更新进度条和里程碑状态
3. 遇到阻碍及时记录在风险表中
4. 重要决策和变更记录在更新日志中
