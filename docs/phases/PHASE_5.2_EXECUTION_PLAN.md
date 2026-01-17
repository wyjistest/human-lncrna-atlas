# Phase 5.2 全站性能优化执行计划

**日期**: 2025-12-10
**版本**: Phase 5.2
**前置条件**: Phase 5.1 完成（/diseases/options API，236x 加速）
**预计时间**: 2-3 天（18 人时）

---

## 执行摘要

基于 Phase 5.1 的成功经验（99.6% 性能提升），将相同的优化模式复制到 Genes、Regulations 和 Stats API，实现全站性能提升 50-100x。

### 优化目标

| API 类别 | 优化前 | 优化后 | 预期提升 |
|---------|--------|--------|----------|
| **Genes Options** | 500-1000ms | <50ms | **50-100x** |
| **Genes List** | 200ms | <100ms | **10-20x** |
| **Regulations Options** | 500-1000ms | <50ms | **80-150x** |
| **Regulations List** | 300ms | <150ms | **5-10x** |
| **Stats (缓存)** | 1000-2000ms | <30ms | **50-100x** |

**全站效果**：
- 平均页面加载时间减少 **80%**
- 数据库负载减少 **70%**
- 用户留存率提升 **预计 15-20%**

---

## 任务分解

### P0 级别：Genes API 优化 ⏱️ 8 人时

**优先级**: 最高（关键路径）
**依赖**: 无
**交付标准**: API 响应 <50ms，缓存命中率 >80%

#### Task 1.1: 创建 /genes/options 轻量级端点 (2h)

**目标**: 为基因选择器提供快速选项加载

**后端实现**:
```python
# app/routers/genes.py
@router.get("/options", response_model=GeneOptionsResponse)
def get_gene_options(
    species_id: Optional[int] = None,
    gene_type: Optional[str] = None,
    db: Session = Depends(get_db)
):
    # 缓存键: genes:options:{species_id}:{gene_type}
    # 只返回: gene_id, gene_ensembl_id, gene_name, species_id
    # TTL: 30 分钟
```

**Schema 定义**:
```python
# app/schemas/gene.py
class GeneOption(BaseModel):
    gene_id: int
    gene_ensembl_id: str
    gene_name: str
    species_id: int
    species_name: Optional[str] = None

class GeneOptionsResponse(BaseModel):
    genes: List[GeneOption]
```

**参考文件**:
- `/frontend/backend/app/routers/diseases.py` (Phase 5.1 成功案例)
- `/frontend/backend/app/core/cache.py` (缓存框架)

---

#### Task 1.2: 优化 list_genes 查询性能 (2h)

**当前问题**:
- 复杂 JOIN 查询（Gene + CoreGene + Species + Regulation）
- 每次都执行聚合计算 `COUNT(Regulation)`

**优化策略**:
1. **缓存热点查询**: 分页结果按查询参数缓存（5 分钟 TTL）
2. **查询优化**:
   - 避免不必要的 JOIN
   - 使用子查询分离聚合计算
   - 添加数据库索引（如需）

**缓存键设计**:
```python
cache_key = f"genes:list:{species_id}:{gene_type}:{page}:{page_size}"
```

---

#### Task 1.3: 前端 API 集成 (1.5h)

**文件**: `frontend/web/src/api/genes.ts`

**新增方法**:
```typescript
export const genesApi = {
  // 现有方法
  list: (params) => ...,
  detail: (geneId) => ...,

  // 新增
  getOptions: (params?: {
    species_id?: number
    gene_type?: string
  }) => apiClient.get<GeneOptionsResponse>('/api/v1/genes/options', { params })
}
```

**类型定义**:
```typescript
interface GeneOption {
  gene_id: number
  gene_ensembl_id: string
  gene_name: string
  species_id: number
  species_name?: string
}

interface GeneOptionsResponse {
  genes: GeneOption[]
}
```

---

#### Task 1.4: 性能测试与验证 (1.5h)

**基准测试**:
```bash
# API 性能测试
curl -w "Time: %{time_total}s\n" http://localhost:8000/api/v1/genes/options
curl -w "Time: %{time_total}s\n" "http://localhost:8000/api/v1/genes/options?species_id=1"

# 缓存验证
redis-cli KEYS "lncrna:genes:*"
redis-cli TTL "lncrna:genes:options:all"
```

**Playwright 测试**（可选）:
- 创建 `gene-options-performance.spec.ts`
- 测量 API 响应时间
- 验证缓存效果

**验收标准**:
- ✅ 首次查询 <100ms
- ✅ 缓存命中 <20ms
- ✅ 响应大小 <100KB
- ✅ 返回基因数 >0

---

### P1 级别：Regulations API 缓存 ⏱️ 6 人时

**优先级**: 高
**依赖**: 无
**交付标准**: 缓存命中率 >70%，响应时间减少 50%+

#### Task 2.1: 创建 /regulations/lncrna-options 端点 (1.5h)

**目标**: 为 lncRNA 选择器提供快速选项

```python
@router.get("/lncrna-options", response_model=LncRNAOptionsResponse)
def get_lncrna_options(
    species_id: Optional[int] = None,
    db: Session = Depends(get_db)
):
    # 返回有调控关系的 lncRNA
    # 缓存 30 分钟
```

---

#### Task 2.2: 创建 /regulations/target-options 端点 (1.5h)

**目标**: 为靶基因选择器提供快速选项

```python
@router.get("/target-options", response_model=TargetOptionsResponse)
def get_target_options(
    species_id: Optional[int] = None,
    db: Session = Depends(get_db)
):
    # 返回作为靶基因的基因列表
    # 缓存 30 分钟
```

---

#### Task 2.3: 为现有端点添加缓存 (2h)

**目标**: 为 `/regulations` list 端点添加缓存

**策略**:
- 热点查询缓存（TTL 15 分钟）
- 按 lncrna_id/target_id 分组缓存
- 缓存键: `regulations:list:{lncrna_id}:{target_id}:{species_id}:{page}`

**代码示例**:
```python
@router.get("", response_model=PaginatedResponse[RegulationDetail])
def list_regulations(...):
    cache_key = cache._make_key(f"regulations:list:{lncrna_id}:{target_id}:{page}")
    cached = cache.get(cache_key)
    if cached is not None:
        return cached

    # ... 查询逻辑 ...

    cache.set(cache_key, result, 900)  # 15 分钟
    return result
```

---

#### Task 2.4: 前端集成与测试 (1h)

**文件**: `frontend/web/src/api/regulations.ts`

**新增方法**:
```typescript
export const regulationsApi = {
  // 现有方法
  list: (params) => ...,
  detail: (id) => ...,

  // 新增
  getLncRNAOptions: (params?: { species_id?: number }) => ...,
  getTargetOptions: (params?: { species_id?: number }) => ...,
}
```

---

### P2 级别：Stats API 缓存扩展 ⏱️ 4 人时

**优先级**: 中
**依赖**: 无
**交付标准**: 统计页面秒开（<100ms）

#### Task 3.1: 为未缓存端点添加 Redis 缓存 (2h)

**当前状态**:
- ✅ `/stats/overview` 已缓存（1 小时）

**新增缓存**:
- `/stats/top-genes` - Top-N 基因排行
- `/stats/top-diseases` - Top-N 疾病排行
- `/stats/species-distribution` - 物种分布统计
- `/stats/ba-distribution` - 结合亲和力分布

**缓存策略**:
```python
# 统计数据缓存 1 小时（变化不频繁）
cache.set(cache_key, result, CacheService.TTL_STATS)  # 3600 秒
```

---

#### Task 3.2: 实现缓存预热机制 (1h)

**目标**: 启动时自动预加载热点数据

```python
# app/core/cache_warmup.py (新文件)
async def warmup_cache():
    """应用启动时预热缓存"""
    # 预加载统计数据
    await warmup_stats()
    # 预加载热门基因
    await warmup_top_genes()
    # 预加载热门疾病
    await warmup_top_diseases()

# main.py
@app.on_event("startup")
async def startup():
    await warmup_cache()
```

---

#### Task 3.3: 监控与测试 (1h)

**Redis 监控命令**:
```bash
# 查看所有统计缓存
redis-cli KEYS "lncrna:stats:*"

# 查看缓存命中情况
redis-cli INFO stats | grep keyspace_hits

# 查看内存使用
redis-cli INFO memory | grep used_memory_human
```

**性能测试**:
```bash
# 测试统计 API
for endpoint in overview top-genes top-diseases species-distribution; do
  echo "Testing /stats/$endpoint"
  curl -w "Time: %{time_total}s\n" "http://localhost:8000/api/v1/stats/$endpoint"
done
```

---

## 关键文件清单

### 后端核心文件（需修改）

| 文件路径 | 改动类型 | 预计行数 | 说明 |
|---------|---------|---------|------|
| `app/routers/genes.py` | 新增 | +50 | /options 端点 |
| `app/routers/regulations.py` | 新增 | +80 | 两个 options 端点 + 缓存 |
| `app/routers/stats.py` | 修改 | +30 | 扩展缓存覆盖 |
| `app/schemas/gene.py` | 新增 | +15 | GeneOption Schema |
| `app/schemas/regulation.py` | 新增 | +20 | Options Schema |
| `app/core/cache_warmup.py` | 新建 | +50 | 缓存预热逻辑 |
| `main.py` | 修改 | +3 | 启动时预热 |

**总计**: 约 250 行新增代码

---

### 前端核心文件（需修改）

| 文件路径 | 改动类型 | 预计行数 | 说明 |
|---------|---------|---------|------|
| `src/api/genes.ts` | 新增 | +15 | getOptions() |
| `src/api/regulations.ts` | 新增 | +20 | 两个新方法 |
| `src/api/stats.ts` | 扩展 | +10 | 扩展方法（如需） |
| `src/types/gene.ts` | 新增 | +10 | 类型定义 |
| `src/types/regulation.ts` | 新增 | +15 | 类型定义 |

**总计**: 约 70 行新增代码

---

### 参考文件（模板和最佳实践）

| 文件路径 | 用途 |
|---------|------|
| `app/routers/diseases.py` | ✅ Phase 5.1 成功案例：/options 端点实现 |
| `app/core/cache.py` | ✅ 缓存框架核心：`cache._make_key()`, TTL 常量 |
| `frontend/web/src/api/diseases.ts` | ✅ 前端 API 参考：`getOptions()` 异步方法 |
| `frontend/web/PERFORMANCE_IMPROVEMENT_REPORT.md` | ✅ Phase 5.1 性能报告：优化效果验证 |

---

## 并行执行策略

### 时间线（2 天完成，3 人协同）

**Day 1 上午（4 小时）**:
- Backend Dev: Task 1.1 + 1.2（Genes API）
- Frontend Dev: 准备类型定义和 API 框架
- Test Engineer: 准备性能测试脚本

**Day 1 下午（4 小时）**:
- Backend Dev: Task 2.1 + 2.2（Regulations Options）
- Frontend Dev: Task 1.3（Genes 前端集成）
- Test Engineer: Task 1.4（Genes 性能测试）

**Day 2 上午（4 小时）**:
- Backend Dev: Task 2.3（Regulations 缓存）+ Task 3.1（Stats 缓存）
- Frontend Dev: Task 2.4（Regulations 前端集成）
- Test Engineer: Regulations 性能测试

**Day 2 下午（4 小时）**:
- Backend Dev: Task 3.2 + 3.3（缓存预热 + 监控）
- Frontend Dev: 前端编译验证 + 文档更新
- Test Engineer: 全站性能测试 + 生成报告

**Day 3（缓冲时间）**:
- 修复 Bug
- 完善文档
- Git 提交推送

---

## 风险评估与缓解

### 技术风险

| 风险 | 概率 | 影响 | 缓解措施 |
|------|------|------|----------|
| **缓存键冲突** | 低 | 中 | 使用命名空间隔离 `lncrna:genes:*` |
| **数据过期问题** | 低 | 中 | 30 分钟 TTL + 手动刷新 API |
| **SQL 查询性能未达预期** | 中 | 高 | 使用 EXPLAIN ANALYZE 优化，必要时添加索引 |
| **Redis 内存不足** | 低 | 高 | 监控内存使用，设置淘汰策略（LRU） |
| **缓存雪崩** | 极低 | 高 | 缓存 TTL 加随机抖动（±10%） |

### 时间风险

| 风险 | 概率 | 影响 | 缓解措施 |
|------|------|------|----------|
| **Genes API 超时** | 低 | 中 | Task 1.2 可推迟到 Phase 5.3 |
| **Regulations 复杂度超预期** | 中 | 中 | 先实现 Options 端点，列表缓存延后 |
| **前端集成延误** | 低 | 低 | 后端优先，前端可单独迭代 |
| **测试发现重大问题** | 中 | 高 | 预留 Day 3 作为缓冲时间 |

**风险应对**：
- 若超期，P2 级别的 Stats 优化可推迟到 Phase 5.3
- 后端和前端并行开发可节省 30% 时间
- 复用 Phase 5.1 代码模板可降低实现风险

---

## 成功验收标准

### API 性能指标

| 端点 | 首次查询 | 缓存命中 | 响应大小 | 缓存命中率 |
|------|---------|---------|----------|------------|
| `/genes/options` | <100ms | <20ms | <100KB | >80% |
| `/genes` (list) | <200ms | <100ms | <200KB | >70% |
| `/regulations/lncrna-options` | <100ms | <20ms | <50KB | >80% |
| `/regulations/target-options` | <100ms | <20ms | <50KB | >80% |
| `/regulations` (list) | <300ms | <150ms | <300KB | >70% |
| `/stats/*` | <1000ms | <30ms | <50KB | >90% |

### 代码质量标准

- ✅ 所有端点返回 200 OK
- ✅ 无 SQL 注入漏洞
- ✅ 缓存键命名规范（`lncrna:{namespace}:*`）
- ✅ 错误处理完善（缓存失败降级到数据库）
- ✅ 日志记录完整（缓存命中/未命中）
- ✅ 类型注解完整（Python + TypeScript）

### 文档标准

- ✅ API 文档更新（Swagger UI）
- ✅ CLAUDE.md 更新（Phase 5.2 记录）
- ✅ 性能测试报告生成
- ✅ Redis 监控命令文档

### 测试标准

- ✅ 手动测试通过（curl 验证）
- ✅ 前端编译通过（`npm run build`）
- ✅ 性能基准测试通过
- ✅ 无重大 Bug（P0/P1 级别）

---

## 监控与维护

### Redis 缓存监控

**关键指标**:
```bash
# 缓存命中率
redis-cli INFO stats | grep keyspace_hits
redis-cli INFO stats | grep keyspace_misses

# 内存使用
redis-cli INFO memory | grep used_memory_human
redis-cli INFO memory | grep used_memory_peak_human

# 键空间统计
redis-cli INFO keyspace
```

**告警阈值**:
- 缓存命中率 < 60% → 检查缓存键设计
- 内存使用 > 80% → 考虑增加内存或优化 TTL
- 淘汰键数量激增 → 检查 maxmemory-policy

### 性能监控

**Prometheus 指标**（可选）:
```python
# metrics.py
from prometheus_client import Histogram, Counter

api_response_time = Histogram('api_response_seconds', 'API response time')
cache_hit_total = Counter('cache_hits_total', 'Cache hits')
cache_miss_total = Counter('cache_misses_total', 'Cache misses')
```

### 日志监控

**慢查询日志**:
```bash
# 查看 FastAPI 慢查询日志
grep "SLOW REQUEST" /tmp/fastapi.log

# 查看缓存统计
grep "cache" /tmp/fastapi.log | grep -E "HIT|MISS"
```

---

## 后续优化建议

### Phase 5.3（未来）

1. **缓存预热自动化**
   - 基于访问日志分析热点数据
   - 定时任务自动预热（每天凌晨）

2. **缓存失效通知**
   - 数据库更新时主动清除相关缓存
   - 使用 Redis Pub/Sub 通知前端刷新

3. **多级缓存架构**
   - L1: 浏览器缓存（HTTP Cache-Control）
   - L2: CDN 缓存（如有）
   - L3: Redis 缓存（现有）
   - L4: 数据库（最终数据源）

4. **查询结果分页优化**
   - 游标分页替代 offset 分页
   - 减少深分页性能问题

---

## 总结

Phase 5.2 将 Phase 5.1 的成功模式（236x 加速）系统化应用到全站，预期实现：

- **平均响应时间减少 80%**
- **数据库负载减少 70%**
- **用户体验显著提升**

**关键成功因素**:
1. ✅ 复用 Phase 5.1 成熟代码模板
2. ✅ Redis 缓存架构已就绪
3. ✅ 并行开发最大化效率
4. ✅ 详细计划降低风险

**执行信心**: 🟢 **高**（技术验证，团队熟悉，风险可控）

---

**计划制定**: 2025-12-10
**计划执行**: Phase 5.2
**计划状态**: ✅ 就绪，等待执行批准

**AI 协助**: Claude Sonnet 4.5 (1M context)
