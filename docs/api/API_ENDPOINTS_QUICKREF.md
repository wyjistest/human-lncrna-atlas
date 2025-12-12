# Regulations API 快速参考（Phase 5.2 Task 2）

## 新增端点

### 1. GET /api/v1/regulations/lncrna-options

获取有调控关系的 lncRNA 选项列表（用于下拉框）

**查询参数**:
- `species_id` (可选): int - 物种ID过滤

**响应示例**:
```json
{
  "lncrnas": [
    {
      "gene_id": 18568,
      "gene_ensembl_id": "ENSG00000225180.2",
      "gene_name": "AATK-AS1",
      "species_id": 1,
      "species_name": "人类",
      "regulation_count": 350
    }
  ]
}
```

**性能**:
- 首次: ~750ms (6,048 条)
- 缓存: ~100ms (7.5x 加速)
- TTL: 30 分钟

**前端调用**:
```typescript
const { data } = await api.get('/api/v1/regulations/lncrna-options', {
  params: { species_id: 1 }
});
```

---

### 2. GET /api/v1/regulations/target-options

获取被调控的靶基因选项列表（用于下拉框）

**查询参数**:
- `species_id` (可选): int - 物种ID过滤

**响应示例**:
```json
{
  "targets": [
    {
      "gene_id": 26960,
      "gene_ensembl_id": "ENSG00000115977",
      "gene_name": "AAK1",
      "species_id": 1,
      "species_name": "人类",
      "lncrna_count": 24
    }
  ]
}
```

**性能**:
- 首次: ~2,199ms (16,099 条)
- 缓存: ~130ms (17x 加速)
- TTL: 30 分钟

**前端调用**:
```typescript
const { data } = await api.get('/api/v1/regulations/target-options', {
  params: { species_id: 1 }
});
```

---

## 优化的现有端点

### 3. GET /api/v1/regulations

获取调控关系列表（已添加缓存）

**查询参数**:
- `page`: int (默认 1) - 页码
- `page_size`: int (默认 100, 最大 1000) - 每页数量
- `species_id`: int (可选) - 物种ID（单个）
- `species_ids`: str (可选) - 物种ID列表（逗号分隔，如 "1,2,3"）
- `lncrna_gene_id`: int (可选) - lncRNA 基因ID
- `target_gene_id`: int (可选) - 靶基因ID
- `lncrna_gene_name`: str (可选) - lncRNA 基因名（模糊搜索）
- `target_gene_name`: str (可选) - 靶基因名（模糊搜索）
- `min_ba`: float (可选) - 最小结合亲和力
- `max_ba`: float (可选) - 最大结合亲和力
- `chromosome`: str (可选) - 染色体（单个）
- `chromosomes`: str (可选) - 染色体列表（逗号分隔）

**响应示例**:
```json
{
  "items": [
    {
      "regulation_id": 1,
      "species_id": 1,
      "species_name": "人类",
      "lncrna_gene_id": 18568,
      "lncrna_gene_name": "AATK-AS1",
      "target_gene_id": 26960,
      "target_gene_name": "AAK1",
      "target_chromosome": "chr2",
      "target_start": 69600000,
      "target_end": 69700000,
      "binding_affinity": 0.95,
      "best_avg_ba": 0.92,
      "num_peaks": 5
    }
  ],
  "total": 804630,
  "page": 1,
  "page_size": 100,
  "total_pages": 8047
}
```

**性能**:
- 首次（无过滤）: ~710ms
- 缓存（无过滤）: ~28ms (25x 加速)
- 首次（带过滤）: ~408ms
- 缓存（带过滤）: ~55ms (7.4x 加速)
- TTL: 15 分钟

**前端调用**:
```typescript
const { data } = await api.get('/api/v1/regulations', {
  params: {
    page: 1,
    page_size: 100,
    species_id: 1,
    min_ba: 0.5
  }
});
```

---

## 使用场景

### 场景 1: 下拉框选项加载

```typescript
// 在组件挂载时加载选项
useEffect(() => {
  Promise.all([
    api.get('/api/v1/regulations/lncrna-options', { params: { species_id: 1 } }),
    api.get('/api/v1/regulations/target-options', { params: { species_id: 1 } })
  ]).then(([lncrnas, targets]) => {
    setLncRNAOptions(lncrnas.data.lncrnas);
    setTargetOptions(targets.data.targets);
  });
}, []);
```

### 场景 2: 表格数据分页

```typescript
const fetchRegulations = async (page: number, filters: RegulationFilters) => {
  const { data } = await api.get('/api/v1/regulations', {
    params: {
      page,
      page_size: 100,
      ...filters
    }
  });
  return data;
};
```

### 场景 3: 复杂过滤查询

```typescript
const searchRegulations = async (criteria: SearchCriteria) => {
  const { data } = await api.get('/api/v1/regulations', {
    params: {
      page: 1,
      page_size: 50,
      species_id: criteria.speciesId,
      lncrna_gene_name: criteria.lncRNAName,
      target_gene_name: criteria.targetName,
      min_ba: criteria.minBA,
      chromosome: criteria.chromosome
    }
  });
  return data;
};
```

---

## 性能基准

| 端点 | 数据量 | 首次响应 | 缓存响应 | 加速比 |
|------|--------|----------|----------|--------|
| lncrna-options | 6,048 | 750ms | 100ms | 7.5x |
| target-options | 16,099 | 2,199ms | 130ms | 17x |
| list (default) | 804,630 | 710ms | 28ms | 25x |
| list (filtered) | 496,064 | 408ms | 55ms | 7.4x |

---

## 缓存说明

1. **自动缓存**: 所有端点都自动使用 Redis 缓存
2. **参数敏感**: 不同的查询参数会生成不同的缓存键
3. **自动过期**: 缓存会在 TTL 到期后自动清除
4. **无需前端处理**: 缓存逻辑完全在后端，前端无需关心

---

## 错误处理

所有端点遵循统一的错误响应格式：

```json
{
  "detail": "错误描述信息"
}
```

常见错误：
- `400 Bad Request`: 参数验证失败
- `404 Not Found`: 资源不存在
- `500 Internal Server Error`: 服务器错误

---

## TypeScript 类型定义建议

```typescript
// LncRNA Option
interface LncRNAOption {
  gene_id: number;
  gene_ensembl_id: string;
  gene_name: string | null;
  species_id: number;
  species_name: string;
  regulation_count: number;
}

// Target Option
interface TargetOption {
  gene_id: number;
  gene_ensembl_id: string;
  gene_name: string | null;
  species_id: number;
  species_name: string;
  lncrna_count: number;
}

// Regulation List Item
interface RegulationListItem {
  regulation_id: number;
  species_id: number;
  species_name: string;
  lncrna_gene_id: number;
  lncrna_gene_name: string | null;
  target_gene_id: number;
  target_gene_name: string | null;
  target_chromosome: string | null;
  target_start: number | null;
  target_end: number | null;
  binding_affinity: number | null;
  best_avg_ba: number | null;
  num_peaks: number | null;
}

// Paginated Response
interface PaginatedResponse<T> {
  items: T[];
  total: number;
  page: number;
  page_size: number;
  total_pages: number;
}
```

---

## 测试命令

```bash
# 测试 lncRNA 选项
curl "http://localhost:8000/api/v1/regulations/lncrna-options" | jq

# 测试靶基因选项（人类）
curl "http://localhost:8000/api/v1/regulations/target-options?species_id=1" | jq

# 测试列表（第一页）
curl "http://localhost:8000/api/v1/regulations?page=1&page_size=10" | jq

# 测试复杂过滤
curl "http://localhost:8000/api/v1/regulations?species_id=1&min_ba=0.8&page=1" | jq
```

---

## 相关文档

- 详细优化报告: `REGULATIONS_CACHE_OPTIMIZATION_REPORT.md`
- 完整验证报告: `FINAL_VERIFICATION.md`
- API 概览: `REGULATIONS_API_SUMMARY.md`
- Swagger UI: http://localhost:8000/docs

---

**更新日期**: 2025-12-10
**适用版本**: Phase 5.2 Task 2+
