# Regulations API 前端集成方案

**Phase 5.2 - Task 2: Regulations Options API 优化**

生成时间: 2025-12-10
状态: 准备就绪 ✅
复用模式: Phase 5.1 Diseases API + Phase 5.2 Genes API

> 更新（2026-01-24）：本文档为前端集成方案快照（含 2026-01 状态补充），不代表当前开发待办；现状以 `docs/CURRENT_STATUS.md` 为准。

---

## 1. 执行摘要

### 1.1 任务目标

为 **Regulations** 页面准备两个轻量级 API 的前端集成：
- `/api/v1/regulations/lncrna-options` - lncRNA 选项列表（用于筛选器）
- `/api/v1/regulations/target-options` - 靶基因选项列表（用于筛选器）

**2026-01 状态更新**

- ✅ 后端已实现上述两个端点（含缓存）：`frontend/backend/app/routers/regulations.py`
- ⚠️ 前端当前仍使用 `lncrna_gene_name` / `target_gene_name` 的模糊搜索输入框；本方案中“改为下拉选择器 + 使用 gene_id 参数”的步骤属于可选增强（未默认启用）

### 1.2 优化收益预估

| 指标 | 当前状态 | 优化后 | 说明 |
|------|---------|--------|------|
| **用户体验** | 手动输入基因名 | 下拉选择 + 搜索 | 减少拼写错误 |
| **数据准确性** | 模糊匹配 | 精确ID匹配 | 避免歧义 |
| **前端性能** | 每次输入查询 | 缓存选项 10 分钟 | 减少 API 调用 |
| **后端性能** | 每次扫描全表 | Redis 缓存 30 分钟 | 降低数据库负载 |

### 1.3 现有 Regulations API

当前已实现的端点（无需改动）：

| 端点 | 方法 | 功能 | 状态 |
|------|------|------|------|
| `/api/v1/regulations` | GET | 获取调控关系列表（分页） | ✅ 已实现 |
| `/api/v1/regulations/{id}` | GET | 获取调控关系详情（含序列） | ✅ 已实现 |
| `/api/v1/regulations/gene/{id}` | GET | 获取基因的调控关系 | ✅ 已实现 |

---

## 2. 后端 API 设计建议

### 2.1 新增端点 1: lncRNA 选项

**端点**: `GET /api/v1/regulations/lncrna-options`

**功能**: 返回所有 lncRNA 基因及其调控数量，用于筛选器下拉选择。

**查询参数**:
```typescript
{
  species_id?: number  // 可选：按物种过滤
}
```

**响应结构**:
```typescript
{
  "lncrnas": [
    {
      "gene_id": 1,
      "gene_ensembl_id": "ENSG00000000003",
      "gene_name": "TSPAN6",
      "species_id": 1,
      "species_name": "人类",
      "regulation_count": 42  // 该 lncRNA 调控的靶基因数量
    }
  ]
}
```

**SQL 查询示例**:
```sql
SELECT
  g.gene_id,
  g.gene_ensembl_id,
  g.gene_name,
  g.species_id,
  s.display_name as species_name,
  COUNT(r.regulation_id) as regulation_count
FROM genes g
JOIN species s ON g.species_id = s.species_id
JOIN regulations r ON g.gene_id = r.lncrna_gene_id
WHERE g.gene_type = 'lncRNA'
  AND (:species_id IS NULL OR g.species_id = :species_id)
GROUP BY g.gene_id, g.gene_ensembl_id, g.gene_name, g.species_id, s.display_name
HAVING COUNT(r.regulation_id) > 0
ORDER BY regulation_count DESC, g.gene_name ASC;
```

**性能优化**:
- Redis 缓存键: `lncrna:regulations:lncrna-options:{species_id}`
- 缓存时长: 30 分钟
- 预计响应时间: 50-200ms（缓存命中 < 10ms）

---

### 2.2 新增端点 2: 靶基因选项

**端点**: `GET /api/v1/regulations/target-options`

**功能**: 返回所有被调控的靶基因及被调控次数。

**查询参数**:
```typescript
{
  species_id?: number  // 可选：按物种过滤
}
```

**响应结构**:
```typescript
{
  "targets": [
    {
      "gene_id": 2,
      "gene_ensembl_id": "ENSG00000000005",
      "gene_name": "TNMD",
      "species_id": 1,
      "species_name": "人类",
      "lncrna_count": 15  // 被多少个 lncRNA 调控
    }
  ]
}
```

**SQL 查询示例**:
```sql
SELECT
  g.gene_id,
  g.gene_ensembl_id,
  g.gene_name,
  g.species_id,
  s.display_name as species_name,
  COUNT(DISTINCT r.lncrna_gene_id) as lncrna_count
FROM genes g
JOIN species s ON g.species_id = s.species_id
JOIN regulations r ON g.gene_id = r.target_gene_id
WHERE r.target_gene_id IS NOT NULL
  AND (:species_id IS NULL OR g.species_id = :species_id)
GROUP BY g.gene_id, g.gene_ensembl_id, g.gene_name, g.species_id, s.display_name
HAVING COUNT(DISTINCT r.lncrna_gene_id) > 0
ORDER BY lncrna_count DESC, g.gene_name ASC;
```

**性能优化**:
- Redis 缓存键: `lncrna:regulations:target-options:{species_id}`
- 缓存时长: 30 分钟
- 预计响应时间: 50-200ms（缓存命中 < 10ms）

---

### 2.3 后端实现文件清单

需要新增/修改的文件：

| 文件 | 说明 | 新增代码行数 |
|------|------|------------|
| `app/schemas/regulation.py` | 新增 `LncRNAOption`, `TargetOption`, `LncRNAOptionsResponse`, `TargetOptionsResponse` Schema | +30 行 |
| `app/routers/regulations.py` | 新增 `/lncrna-options` 和 `/target-options` 端点 | +120 行 |

**Schema 定义示例** (`app/schemas/regulation.py`):
```python
from pydantic import BaseModel, Field

class LncRNAOption(BaseModel):
    """lncRNA 选项（轻量级，用于下拉选择）"""
    gene_id: int
    gene_ensembl_id: str
    gene_name: str | None
    species_id: int
    species_name: str
    regulation_count: int = Field(description="该 lncRNA 调控的靶基因数量")

    class Config:
        from_attributes = True

class LncRNAOptionsResponse(BaseModel):
    """lncRNA 选项响应"""
    lncrnas: list[LncRNAOption]

class TargetOption(BaseModel):
    """靶基因选项（轻量级，用于下拉选择）"""
    gene_id: int
    gene_ensembl_id: str
    gene_name: str | None
    species_id: int
    species_name: str
    lncrna_count: int = Field(description="被多少个 lncRNA 调控")

    class Config:
        from_attributes = True

class TargetOptionsResponse(BaseModel):
    """靶基因选项响应"""
    targets: list[TargetOption]
```

**路由实现示例** (`app/routers/regulations.py`):
```python
@router.get("/lncrna-options", response_model=LncRNAOptionsResponse)
async def get_lncrna_options(
    species_id: Optional[int] = Query(None, description="物种ID（可选）"),
    db: Session = Depends(get_db),
    redis: Redis = Depends(get_redis)
):
    """获取 lncRNA 选项列表（轻量级 API，用于下拉选择）"""

    # 缓存键
    cache_key = f"lncrna:regulations:lncrna-options:{species_id or 'all'}"

    # 尝试从 Redis 获取缓存
    if redis:
        cached = await redis.get(cache_key)
        if cached:
            return LncRNAOptionsResponse.model_validate_json(cached)

    # 查询数据库
    query = (
        db.query(
            Gene.gene_id,
            Gene.gene_ensembl_id,
            Gene.gene_name,
            Gene.species_id,
            Species.display_name.label("species_name"),
            func.count(Regulation.regulation_id).label("regulation_count")
        )
        .join(Species, Gene.species_id == Species.species_id)
        .join(Regulation, Gene.gene_id == Regulation.lncrna_gene_id)
        .filter(Gene.gene_type == 'lncRNA')
    )

    if species_id:
        query = query.filter(Gene.species_id == species_id)

    results = query.group_by(
        Gene.gene_id, Gene.gene_ensembl_id, Gene.gene_name,
        Gene.species_id, Species.display_name
    ).having(func.count(Regulation.regulation_id) > 0).all()

    lncrnas = [
        LncRNAOption(
            gene_id=r.gene_id,
            gene_ensembl_id=r.gene_ensembl_id,
            gene_name=r.gene_name,
            species_id=r.species_id,
            species_name=r.species_name,
            regulation_count=r.regulation_count
        )
        for r in results
    ]

    response = LncRNAOptionsResponse(lncrnas=lncrnas)

    # 缓存到 Redis（30 分钟）
    if redis:
        await redis.setex(cache_key, 1800, response.model_dump_json())

    return response

@router.get("/target-options", response_model=TargetOptionsResponse)
async def get_target_options(
    species_id: Optional[int] = Query(None, description="物种ID（可选）"),
    db: Session = Depends(get_db),
    redis: Redis = Depends(get_redis)
):
    """获取靶基因选项列表（轻量级 API，用于下拉选择）"""

    # 实现类似逻辑...
```

---

## 3. 前端代码实现

### 3.1 TypeScript 类型定义

**文件**: `<repo-root>/frontend/web/src/api/regulations.ts`

**完整代码**:
```typescript
import { apiClient } from './client'
import type { components, RegulationFilterParams } from '@/types'

type RegulationListItem = components['schemas']['RegulationListItem']
type RegulationDetail = components['schemas']['RegulationDetail']
type PaginatedResponse<T> = components['schemas']['PaginatedResponse_RegulationListItem_'] & { items: T[] }

/**
 * lncRNA 选项接口（轻量级，仅用于下拉选择）
 *
 * Phase 5.2 Task 2 - 优化 Regulations 页面筛选器
 *
 * 包含调控数量统计，帮助用户选择调控关系多的 lncRNA
 */
export interface LncRNAOption {
  gene_id: number
  gene_ensembl_id: string
  gene_name: string | null
  species_id: number
  species_name: string
  regulation_count: number  // 该 lncRNA 的调控数量
}

/**
 * lncRNA 选项响应接口
 */
export interface LncRNAOptionsResponse {
  lncrnas: LncRNAOption[]
}

/**
 * 靶基因选项接口（轻量级，仅用于下拉选择）
 *
 * Phase 5.2 Task 2 - 优化 Regulations 页面筛选器
 *
 * 包含被调控次数统计，帮助用户选择热门靶基因
 */
export interface TargetOption {
  gene_id: number
  gene_ensembl_id: string
  gene_name: string | null
  species_id: number
  species_name: string
  lncrna_count: number  // 被多少个 lncRNA 调控
}

/**
 * 靶基因选项响应接口
 */
export interface TargetOptionsResponse {
  targets: TargetOption[]
}

export const regulationsApi = {
  /**
   * 获取调控关系列表（支持多种筛选条件）
   *
   * 筛选参数：
   * - species_id / species_ids: 物种筛选（单个或逗号分隔的多个）
   * - chromosome / chromosomes: 染色体筛选（单个或逗号分隔的多个）
   * - min_ba / max_ba: BA 范围筛选
   * - lncrna_gene_name / target_gene_name: 基因名模糊搜索
   */
  list: (params: RegulationFilterParams) =>
    apiClient.get<PaginatedResponse<RegulationListItem>>('/api/v1/regulations', { params }),

  /**
   * 获取调控关系详情（包含序列数据）
   */
  getDetail: (regulationId: number) =>
    apiClient.get<RegulationDetail>(`/api/v1/regulations/${regulationId}`),

  /**
   * 获取 lncRNA 选项列表（轻量级 API）
   *
   * Phase 5.2 Task 2 - 新增方法
   *
   * 用途: Regulations 页面的 lncRNA 筛选下拉框
   *
   * 性能:
   * - 响应时间: 50-200ms (首次), < 10ms (缓存)
   * - 响应大小: 预计 500KB-1MB（取决于数据量）
   * - 后端缓存: Redis 30 分钟
   * - 前端缓存: 推荐 React Query 10 分钟
   *
   * @param params - 查询参数
   * @param params.species_id - 可选：按物种过滤
   * @returns Promise with lncrnas array
   *
   * @example
   * // 基础用法：获取所有 lncRNA
   * const { data } = useQuery({
   *   queryKey: ['lncrna-options'],
   *   queryFn: () => regulationsApi.getLncRNAOptions(),
   *   staleTime: 10 * 60 * 1000, // 10 分钟缓存
   * })
   *
   * @example
   * // 推荐：按物种过滤
   * const { data } = useQuery({
   *   queryKey: ['lncrna-options', speciesId],
   *   queryFn: () => regulationsApi.getLncRNAOptions({ species_id: speciesId }),
   *   staleTime: 10 * 60 * 1000,
   *   enabled: !!speciesId, // 只在物种选中时加载
   * })
   */
  getLncRNAOptions: async (params?: {
    species_id?: number
  }): Promise<LncRNAOptionsResponse> => {
    const response = await apiClient.get<LncRNAOptionsResponse>(
      '/api/v1/regulations/lncrna-options',
      { params }
    )
    return response.data
  },

  /**
   * 获取靶基因选项列表（轻量级 API）
   *
   * Phase 5.2 Task 2 - 新增方法
   *
   * 用途: Regulations 页面的靶基因筛选下拉框
   *
   * 性能:
   * - 响应时间: 50-200ms (首次), < 10ms (缓存)
   * - 响应大小: 预计 1-2MB（靶基因数量通常更多）
   * - 后端缓存: Redis 30 分钟
   * - 前端缓存: 推荐 React Query 10 分钟
   *
   * @param params - 查询参数
   * @param params.species_id - 可选：按物种过滤
   * @returns Promise with targets array
   *
   * @example
   * // 基础用法：获取所有靶基因
   * const { data } = useQuery({
   *   queryKey: ['target-options'],
   *   queryFn: () => regulationsApi.getTargetOptions(),
   *   staleTime: 10 * 60 * 1000, // 10 分钟缓存
   * })
   *
   * @example
   * // 推荐：按物种过滤
   * const { data } = useQuery({
   *   queryKey: ['target-options', speciesId],
   *   queryFn: () => regulationsApi.getTargetOptions({ species_id: speciesId }),
   *   staleTime: 10 * 60 * 1000,
   *   enabled: !!speciesId, // 只在物种选中时加载
   * })
   */
  getTargetOptions: async (params?: {
    species_id?: number
  }): Promise<TargetOptionsResponse> => {
    const response = await apiClient.get<TargetOptionsResponse>(
      '/api/v1/regulations/target-options',
      { params }
    )
    return response.data
  }
}
```

---

### 3.2 页面分析报告

#### 3.2.1 使用 Regulations API 的页面

| 页面 | 文件路径 | 用途 | 需要优化 |
|------|---------|------|---------|
| **Regulations 列表** | `src/pages/Regulations/index.tsx` | 主要页面，调控关系查询和展示 | ✅ 是 |
| **AdvancedFilters** | `src/pages/Regulations/components/AdvancedFilters.tsx` | 高级筛选器 | ✅ 是 |
| Network 页面 | `src/pages/Network/index.tsx` | 使用疾病选项（已优化） | ❌ 否 |
| GeneDetail 页面 | `src/pages/GeneDetail/index.tsx` | 查看基因的调控关系 | ❌ 否 |
| Stats 页面 | `src/pages/Stats/index.tsx` | 统计数据展示 | ❌ 否 |

#### 3.2.2 当前筛选器状态

**文件**: `src/pages/Regulations/components/AdvancedFilters.tsx`

**现有筛选器**:
```typescript
export interface FilterState {
  min_ba?: number           // BA 范围筛选（数字输入）
  max_ba?: number
  species_ids?: number[]    // 物种多选（下拉框）
  chromosomes?: string[]    // 染色体多选（下拉框）
  lncrna_gene_name?: string // lncRNA 基因名（文本输入 + 500ms 防抖）⚠️ 需优化
  target_gene_name?: string // 靶基因名（文本输入 + 500ms 防抖）⚠️ 需优化
}
```

**存在的问题**:
1. ⚠️ **用户体验差**: 需要手动输入完整基因名，容易拼写错误
2. ⚠️ **无智能提示**: 不知道哪些基因名可用
3. ⚠️ **低效查询**: 每次输入触发模糊搜索，数据库压力大

**优化方案**:
```typescript
export interface FilterState {
  min_ba?: number
  max_ba?: number
  species_ids?: number[]
  chromosomes?: string[]
  lncrna_gene_id?: number     // ✅ 改为 ID 精确匹配
  target_gene_id?: number     // ✅ 改为 ID 精确匹配
}
```

#### 3.2.3 改动范围预估

| 文件 | 改动类型 | 代码行数 | 复杂度 |
|------|---------|---------|-------|
| `src/api/regulations.ts` | 新增 API 方法 | +150 行 | ⭐ 简单 |
| `src/pages/Regulations/components/AdvancedFilters.tsx` | 替换输入框为选择器 | +80 行, -40 行 | ⭐⭐ 中等 |
| `src/pages/Regulations/index.tsx` | 调整 API 参数 | +5 行, -5 行 | ⭐ 简单 |

**总计**: 约 +235 行, -45 行 = **+190 行净增**

---

### 3.3 集成模板

#### 模板 1: lncRNA 选择器（推荐实现）

**文件**: `src/pages/Regulations/components/AdvancedFilters.tsx`

```typescript
import { useQuery } from '@tanstack/react-query'
import { Select, Space } from 'antd'
import { regulationsApi } from '@/api/regulations'

// 在 AdvancedFilters 组件内部

// 1. 获取 lncRNA 选项（根据物种 ID 过滤）
const { data: lncrnaOptions, isLoading: lncrnaLoading } = useQuery({
  queryKey: ['lncrna-options', filters.species_ids?.[0]], // 使用第一个物种 ID
  queryFn: () => regulationsApi.getLncRNAOptions({
    species_id: filters.species_ids?.[0]
  }),
  staleTime: 10 * 60 * 1000, // 10 分钟缓存
  enabled: true, // 始终启用，支持查看所有物种的 lncRNA
})

// 2. 渲染 lncRNA 选择器
<Form.Item label={t('filters.lncrnaName')} style={{ marginBottom: 12 }}>
  <Select
    showSearch
    allowClear
    loading={lncrnaLoading}
    placeholder={i18n.language?.startsWith('en') ? 'Select lncRNA' : '选择 lncRNA'}
    value={filters.lncrna_gene_id}
    onChange={(val) => onFilterChange('lncrna_gene_id', val)}
    style={{ width: '100%' }}
    options={lncrnaOptions?.lncrnas.map(lnc => ({
      value: lnc.gene_id,
      label: `${lnc.gene_name || lnc.gene_ensembl_id} (${lnc.regulation_count} targets)`,
      // 搜索优化：同时匹配基因名和 Ensembl ID
      searchValue: `${lnc.gene_name || ''} ${lnc.gene_ensembl_id}`
    }))}
    filterOption={(input, option) => {
      const searchValue = option?.searchValue?.toLowerCase() || ''
      return searchValue.includes(input.toLowerCase())
    }}
    // 优化：虚拟滚动支持大数据量
    virtual
    // 提示用户调控数量最多的 lncRNA
    dropdownRender={(menu) => (
      <>
        {lncrnaOptions && lncrnaOptions.lncrnas.length > 0 && (
          <div style={{ padding: '8px 12px', borderBottom: '1px solid #f0f0f0', fontSize: 12, color: '#999' }}>
            {t('filters.lncrnaHint', { count: lncrnaOptions.lncrnas.length })}
          </div>
        )}
        {menu}
      </>
    )}
  />
</Form.Item>
```

#### 模板 2: 靶基因选择器（推荐实现）

```typescript
// 1. 获取靶基因选项（根据物种 ID 过滤）
const { data: targetOptions, isLoading: targetLoading } = useQuery({
  queryKey: ['target-options', filters.species_ids?.[0]],
  queryFn: () => regulationsApi.getTargetOptions({
    species_id: filters.species_ids?.[0]
  }),
  staleTime: 10 * 60 * 1000, // 10 分钟缓存
  enabled: true, // 始终启用
})

// 2. 渲染靶基因选择器
<Form.Item label={t('filters.targetName')} style={{ marginBottom: 12 }}>
  <Select
    showSearch
    allowClear
    loading={targetLoading}
    placeholder={i18n.language?.startsWith('en') ? 'Select target gene' : '选择靶基因'}
    value={filters.target_gene_id}
    onChange={(val) => onFilterChange('target_gene_id', val)}
    style={{ width: '100%' }}
    options={targetOptions?.targets.map(target => ({
      value: target.gene_id,
      label: `${target.gene_name || target.gene_ensembl_id} (${target.lncrna_count} lncRNAs)`,
      searchValue: `${target.gene_name || ''} ${target.gene_ensembl_id}`
    }))}
    filterOption={(input, option) => {
      const searchValue = option?.searchValue?.toLowerCase() || ''
      return searchValue.includes(input.toLowerCase())
    }}
    virtual
    dropdownRender={(menu) => (
      <>
        {targetOptions && targetOptions.targets.length > 0 && (
          <div style={{ padding: '8px 12px', borderBottom: '1px solid #f0f0f0', fontSize: 12, color: '#999' }}>
            {t('filters.targetHint', { count: targetOptions.targets.length })}
          </div>
        )}
        {menu}
      </>
    )}
  />
</Form.Item>
```

#### 模板 3: 优化后的 FilterState 类型

```typescript
export interface FilterState {
  min_ba?: number
  max_ba?: number
  species_ids?: number[]
  chromosomes?: string[]
  lncrna_gene_id?: number     // ✅ 改为 gene_id（精确匹配）
  target_gene_id?: number     // ✅ 改为 gene_id（精确匹配）
}
```

#### 模板 4: 修改 Regulations 页面的 API 参数

**文件**: `src/pages/Regulations/index.tsx`

**修改前**:
```typescript
const apiParams = useMemo(() => ({
  page,
  page_size: pageSize,
  min_ba: filters.min_ba,
  max_ba: filters.max_ba,
  species_ids: filters.species_ids?.join(','),
  chromosomes: filters.chromosomes?.join(','),
  lncrna_gene_name: filters.lncrna_gene_name, // ❌ 模糊搜索
  target_gene_name: filters.target_gene_name,  // ❌ 模糊搜索
}), [/* ... */])
```

**修改后**:
```typescript
const apiParams = useMemo(() => ({
  page,
  page_size: pageSize,
  min_ba: filters.min_ba,
  max_ba: filters.max_ba,
  species_ids: filters.species_ids?.join(','),
  chromosomes: filters.chromosomes?.join(','),
  lncrna_gene_id: filters.lncrna_gene_id, // ✅ 精确匹配
  target_gene_id: filters.target_gene_id,  // ✅ 精确匹配
}), [
  page,
  pageSize,
  filters.min_ba,
  filters.max_ba,
  filters.species_ids,
  filters.chromosomes,
  filters.lncrna_gene_id,  // ✅ 更新依赖
  filters.target_gene_id,  // ✅ 更新依赖
])
```

---

### 3.4 React Query 最佳实践

#### 1. 缓存策略

```typescript
// ✅ 推荐：使用物种 ID 作为缓存键的一部分
useQuery({
  queryKey: ['lncrna-options', speciesId], // 细粒度缓存
  queryFn: () => regulationsApi.getLncRNAOptions({ species_id: speciesId }),
  staleTime: 10 * 60 * 1000, // 10 分钟内不重新请求
  cacheTime: 30 * 60 * 1000, // 30 分钟后清除缓存
})

// ❌ 不推荐：不使用缓存键
useQuery({
  queryKey: ['lncrna-options'], // 无法区分不同物种
  queryFn: () => regulationsApi.getLncRNAOptions(),
})
```

#### 2. 条件加载

```typescript
// ✅ 推荐：仅在需要时加载
const { data } = useQuery({
  queryKey: ['lncrna-options', speciesId],
  queryFn: () => regulationsApi.getLncRNAOptions({ species_id: speciesId }),
  enabled: !!speciesId, // 只在物种选中时加载
})

// ⚠️ 可选：始终加载所有数据（适用于数据量小的场景）
const { data } = useQuery({
  queryKey: ['lncrna-options'],
  queryFn: () => regulationsApi.getLncRNAOptions(),
  enabled: true, // 页面加载时立即获取
})
```

#### 3. 错误处理

```typescript
const { data, isLoading, error } = useQuery({
  queryKey: ['lncrna-options', speciesId],
  queryFn: () => regulationsApi.getLncRNAOptions({ species_id: speciesId }),
  retry: 2, // 失败时重试 2 次
  retryDelay: 1000, // 重试间隔 1 秒
  onError: (err) => {
    message.error(t('filters.loadLncRNAOptionsFailed'))
    console.error('Load lncRNA options failed:', err)
  }
})

// UI 中处理 loading 和 error 状态
{error && (
  <Alert
    type="error"
    message={t('filters.loadLncRNAOptionsFailed')}
    description={error.message}
    style={{ marginBottom: 12 }}
  />
)}
```

#### 4. 性能优化：虚拟滚动

```typescript
<Select
  showSearch
  virtual // ✅ 启用虚拟滚动，支持大数据量
  optionHeight={32} // 可选：自定义选项高度
  listHeight={256} // 可选：下拉列表高度
  options={lncrnaOptions?.lncrnas.map(/* ... */)}
/>
```

---

## 4. 国际化支持

### 4.1 新增翻译键

**文件**: `frontend/web/src/i18n/locales/zh-CN/regulations.json`

```json
{
  "filters": {
    "lncrnaName": "lncRNA 基因",
    "targetName": "靶基因",
    "lncrnaHint": "共 {{count}} 个 lncRNA 基因",
    "targetHint": "共 {{count}} 个靶基因",
    "loadLncRNAOptionsFailed": "加载 lncRNA 选项失败",
    "loadTargetOptionsFailed": "加载靶基因选项失败",
    "selectLncRNA": "选择 lncRNA（可搜索）",
    "selectTarget": "选择靶基因（可搜索）"
  }
}
```

**文件**: `frontend/web/src/i18n/locales/en-US/regulations.json`

```json
{
  "filters": {
    "lncrnaName": "lncRNA Gene",
    "targetName": "Target Gene",
    "lncrnaHint": "{{count}} lncRNA genes available",
    "targetHint": "{{count}} target genes available",
    "loadLncRNAOptionsFailed": "Failed to load lncRNA options",
    "loadTargetOptionsFailed": "Failed to load target options",
    "selectLncRNA": "Select lncRNA (searchable)",
    "selectTarget": "Select target gene (searchable)"
  }
}
```

---

## 5. 测试计划

### 5.1 单元测试

**文件**: `frontend/web/src/api/__tests__/regulations.test.ts`

```typescript
import { describe, it, expect, vi } from 'vitest'
import { regulationsApi } from '../regulations'
import { apiClient } from '../client'

vi.mock('../client')

describe('regulationsApi.getLncRNAOptions', () => {
  it('should fetch lncRNA options without filters', async () => {
    const mockResponse = {
      data: {
        lncrnas: [
          {
            gene_id: 1,
            gene_ensembl_id: 'ENSG00000000003',
            gene_name: 'TSPAN6',
            species_id: 1,
            species_name: '人类',
            regulation_count: 42
          }
        ]
      }
    }

    vi.mocked(apiClient.get).mockResolvedValue(mockResponse)

    const result = await regulationsApi.getLncRNAOptions()

    expect(apiClient.get).toHaveBeenCalledWith(
      '/api/v1/regulations/lncrna-options',
      { params: undefined }
    )
    expect(result.lncrnas).toHaveLength(1)
    expect(result.lncrnas[0].regulation_count).toBe(42)
  })

  it('should filter by species_id', async () => {
    const mockResponse = { data: { lncrnas: [] } }
    vi.mocked(apiClient.get).mockResolvedValue(mockResponse)

    await regulationsApi.getLncRNAOptions({ species_id: 1 })

    expect(apiClient.get).toHaveBeenCalledWith(
      '/api/v1/regulations/lncrna-options',
      { params: { species_id: 1 } }
    )
  })
})

describe('regulationsApi.getTargetOptions', () => {
  it('should fetch target options without filters', async () => {
    const mockResponse = {
      data: {
        targets: [
          {
            gene_id: 2,
            gene_ensembl_id: 'ENSG00000000005',
            gene_name: 'TNMD',
            species_id: 1,
            species_name: '人类',
            lncrna_count: 15
          }
        ]
      }
    }

    vi.mocked(apiClient.get).mockResolvedValue(mockResponse)

    const result = await regulationsApi.getTargetOptions()

    expect(result.targets).toHaveLength(1)
    expect(result.targets[0].lncrna_count).toBe(15)
  })
})
```

### 5.2 集成测试（Playwright）

**文件**: `frontend/web/tests/regulations-filters.spec.ts`

```typescript
import { test, expect } from '@playwright/test'

test.describe('Regulations Filters', () => {
  test('should load lncRNA options in select', async ({ page }) => {
    await page.goto('/regulations')

    // 展开高级筛选
    await page.click('text=高级筛选')

    // 打开 lncRNA 选择器
    await page.click('input[placeholder*="选择 lncRNA"]')

    // 等待选项加载
    await page.waitForSelector('.ant-select-item-option', { timeout: 5000 })

    // 验证选项数量
    const options = await page.locator('.ant-select-item-option').count()
    expect(options).toBeGreaterThan(0)

    // 验证选项格式：基因名 (调控数量)
    const firstOption = await page.locator('.ant-select-item-option').first().textContent()
    expect(firstOption).toMatch(/\(.+\stargets\)/)
  })

  test('should search lncRNA by name', async ({ page }) => {
    await page.goto('/regulations')
    await page.click('text=高级筛选')

    // 输入搜索关键词
    await page.fill('input[placeholder*="选择 lncRNA"]', 'TSPAN')

    // 等待过滤结果
    await page.waitForTimeout(300)

    // 验证过滤后的选项
    const filteredOptions = await page.locator('.ant-select-item-option:visible').count()
    expect(filteredOptions).toBeGreaterThan(0)
  })

  test('should filter regulations by selected lncRNA', async ({ page }) => {
    await page.goto('/regulations')
    await page.click('text=高级筛选')

    // 选择第一个 lncRNA
    await page.click('input[placeholder*="选择 lncRNA"]')
    await page.click('.ant-select-item-option:first-child')

    // 等待表格更新
    await page.waitForSelector('.ant-table-tbody tr', { timeout: 5000 })

    // 验证表格中的 lncRNA 基因名一致
    const lncRNANames = await page.locator('.ant-table-tbody td:nth-child(2)').allTextContents()
    const uniqueNames = new Set(lncRNANames)
    expect(uniqueNames.size).toBe(1) // 所有行的 lncRNA 应该相同
  })
})
```

---

## 6. 性能优化建议

### 6.1 前端优化

| 策略 | 说明 | 收益 |
|------|------|------|
| **虚拟滚动** | Select 组件启用 `virtual` 属性 | 支持渲染 10,000+ 选项 |
| **搜索索引** | 使用 `searchValue` 属性优化搜索 | 搜索速度提升 50% |
| **React Query 缓存** | `staleTime: 10min` | 减少 90% 重复请求 |
| **条件加载** | `enabled: !!speciesId` | 避免不必要的 API 调用 |
| **本地过滤** | 前端过滤选项，无需请求后端 | 即时响应 |

### 6.2 后端优化

| 策略 | 说明 | 收益 |
|------|------|------|
| **Redis 缓存** | 缓存 30 分钟 | 响应时间从 200ms → 10ms |
| **数据库索引** | `genes(gene_type, species_id)` | 查询速度提升 10x |
| **SQL 优化** | 使用 `COUNT(DISTINCT ...)` | 减少内存占用 |
| **分组缓存** | 按 `species_id` 分别缓存 | 缓存命中率提升 |

---

## 7. 迁移路径

### 阶段 1: 后端实现（Backend Agent）

1. ✅ 定义 Schema (`app/schemas/regulation.py`)
2. ✅ 实现 lncRNA Options 端点 (`app/routers/regulations.py`)
3. ✅ 实现 Target Options 端点
4. ✅ 添加 Redis 缓存
5. ✅ 编写单元测试

### 阶段 2: 前端集成（Frontend Agent）

1. ✅ 更新 `src/api/regulations.ts`（已添加类型与 options API 方法）
2. ⏸️（可选增强）修改 `FilterState` 类型（`lncrna_gene_name` → `lncrna_gene_id`）
3. ⏸️（可选增强）修改 `AdvancedFilters.tsx`（替换输入框为选择器）
4. ⏸️（可选增强）修改 `index.tsx`（调整 API 参数，使用 gene_id）
5. ⏸️（可选增强）补齐选择器相关国际化
6. ⏸️（可选增强）补齐/更新单元测试

### 阶段 3: 测试验证（Playwright Agent）

1. ⏸️（可选增强）为 options selector 路径补齐 Playwright 覆盖
2. ⏸️（可选增强）性能测试（加载时间、缓存命中率）
3. ⏸️（可选增强）UI 测试（下拉框交互、搜索功能）
4. ⏸️（可选增强）回归测试（确保原有功能正常）

---

## 8. 风险评估

| 风险 | 影响 | 缓解措施 |
|------|------|---------|
| **数据量过大** | 选择器加载慢 | 1. 启用虚拟滚动<br>2. 按物种过滤<br>3. 前端限制显示数量 |
| **缓存失效** | 数据不一致 | 1. 后端更新时清除缓存<br>2. 前端定期刷新<br>3. 提供手动刷新按钮 |
| **后端接口不可用/不可达** | 前端报错 | 1. 添加错误边界<br>2. 优雅降级（保留输入框）<br>3. 清晰的错误提示 |
| **用户习惯** | 不适应新 UI | 1. 保留搜索功能<br>2. 添加使用提示<br>3. 渐进式迁移 |

---

## 9. 成功案例参考

### Phase 5.1: Diseases API 优化（已完成）

| 指标 | 优化结果 |
|------|---------|
| API 响应时间 | 4951ms → 7-50ms (**99% ↓**) |
| 响应大小 | 240KB → 20KB (**92% ↓**) |
| 返回数据 | 500 条（含重复） → 273 条（去重） |
| 缓存命中 | 0% → Redis 30min |

**经验教训**:
- ✅ 轻量级 API 极大提升用户体验
- ✅ 后端去重 + Redis 缓存是性能关键
- ✅ 前端 React Query 缓存减少重复请求
- ✅ Playwright 测试确保功能正确性

### Phase 5.2 Task 1: Genes API 优化（已完成）

| 指标 | 优化结果 |
|------|---------|
| API 响应时间（首次） | 308ms |
| API 响应时间（缓存） | 238ms |
| 缓存加速比 | 1.29x |
| 返回数据 | 17,248 条（所有基因） |

**经验教训**:
- ✅ 虚拟滚动支持大数据量
- ✅ 分组缓存提升命中率
- ✅ 类型安全的 API 定义

---

## 10. 下一步行动

### 前端准备工作（本文档完成）

- [x] 定义 TypeScript 类型
- [x] 编写 API 方法模板
- [x] 设计 UI 集成方案
- [x] 准备集成测试用例
- [x] 编写国际化翻译

### 后端开发工作（已完成）

> 更新（2026-01-30）：后端已实现上述端点与缓存（以 `frontend/backend/app/routers/regulations.py` 为准）。

- ✅ 实现 `/api/v1/regulations/lncrna-options` 端点（已完成）
- ✅ 实现 `/api/v1/regulations/target-options` 端点（已完成）
- ✅ 添加 Redis 缓存（已完成）
- ✅ 回归锚点/单测覆盖（例如：`frontend/backend/tests/test_api_snapshot_overlap_compare_unit.py`）
- ✅ 文档与说明（本文件 + `docs/api/REGULATIONS_API_SUMMARY.md`）

### 前端集成工作（可选增强）

> 说明：前端“选择器 + gene_id”属于可选增强，已拆分为可追踪 issue：
> - #79（功能改造）
> - #80（测试覆盖）

- ✅ 更新 `src/api/regulations.ts`（已完成）
- （可选增强，Tracked in #79）修改 `AdvancedFilters.tsx`
- （可选增强，Tracked in #79）修改 `index.tsx`
- （可选增强，Tracked in #79/#80）补齐相关国际化与测试覆盖

### 测试验证工作（可选增强）

- （可选增强，Tracked in #80）运行 Playwright 集成测试
- （可选增强，Tracked in #80）性能基准测试
- （可选增强，Tracked in #80）UI 交互测试
- （可选增强，Tracked in #80）回归测试

---

## 11. 附录

### A. 相关文件清单

| 文件 | 说明 |
|------|------|
| `frontend/web/src/api/regulations.ts` | Regulations API 客户端 |
| `frontend/web/src/pages/Regulations/index.tsx` | Regulations 主页面 |
| `frontend/web/src/pages/Regulations/components/AdvancedFilters.tsx` | 高级筛选器组件 |
| `frontend/backend/app/routers/regulations.py` | 后端路由（待实现新端点） |
| `frontend/backend/app/schemas/regulation.py` | 后端 Schema（待新增类型） |

### B. API 对比表

| API | 用途 | 响应字段 | 数据量 |
|-----|------|---------|-------|
| `GET /api/v1/regulations` | 获取调控关系列表 | 13 个字段 | 分页（100 条/页） |
| `GET /api/v1/regulations/{id}` | 获取调控详情 | 30+ 字段（含序列） | 单条 |
| `GET /api/v1/regulations/lncrna-options` ⭐ | 获取 lncRNA 选项 | 6 个字段 | 全量（预计 1000-3000 条） |
| `GET /api/v1/regulations/target-options` ⭐ | 获取靶基因选项 | 6 个字段 | 全量（预计 5000-10000 条） |

⭐ = 本次新增端点

---

**文档版本**: v1.0
**最后更新**: 2025-12-10
**作者**: Frontend Agent (Claude Sonnet 4.5)
**审核**: 待 Backend Agent 和 Playwright Agent 验证
