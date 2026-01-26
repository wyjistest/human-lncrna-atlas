# Sankey 流向图后端 API 可行性评估报告

**评估日期**: 2025-12-12
**评估者**: Backend API Developer (Claude Code)
**目标功能**: lncRNA → 靶基因 → 疾病 三层流向数据 API
> 更新（2026-01-26）：本报告为阶段性评估记录；现状以 `docs/CURRENT_STATUS.md` 为准。

---

## 执行摘要

| 指标 | 评估结果 |
|------|---------|
| **可行性评分** | **9.5/10** ⭐⭐⭐⭐⭐ |
| **数据完整性** | ✅ 完整（三层关联已打通） |
| **性能预估** | ✅ 优秀（20-60ms / 500 条） |
| **开发工作量** | ✅ 低（1-2 小时，可复用现有代码） |
| **推荐实施** | ✅ **强烈推荐** |

---

## 1. 数据库结构分析

### 1.1 相关表结构

#### **regulations** 表（调控关系）
```sql
regulations (
    regulation_id BIGINT PRIMARY KEY,
    lncrna_gene_id INT REFERENCES genes(gene_id),  -- lncRNA 基因
    target_gene_id INT REFERENCES genes(gene_id),  -- 靶基因
    binding_affinity NUMERIC,                       -- 结合亲和力
    species_id INT REFERENCES species(species_id)   -- 物种
)
```
- **记录数**: 804,630
- **索引**: ✅ `idx_reg_target` (target_gene_id), `idx_reg_lncrna` (lncrna_gene_id), `idx_reg_ba` (binding_affinity)

#### **genes** 表（基因信息）
```sql
genes (
    gene_id INT PRIMARY KEY,
    core_id INT REFERENCES core_genes(core_id),    -- 跨物种核心 ID
    gene_name VARCHAR(100),                         -- 基因名
    species_id INT REFERENCES species(species_id)   -- 物种
)
```
- **记录数**: 17,248
- **索引**: ✅ `idx_genes_core` (core_id), `idx_genes_name` (gene_name)

#### **trait_gene_associations** 表（疾病-基因关联）
```sql
trait_gene_associations (
    association_id INT PRIMARY KEY,
    core_id INT REFERENCES core_genes(core_id),     -- 基因核心 ID
    trait_id INT REFERENCES traits(trait_id),       -- 疾病 ID
    trait_snp_pvalue NUMERIC,                       -- GWAS p-value
    odds_ratio NUMERIC,                             -- 优势比
    fdr NUMERIC                                     -- 校正 p-value
)
```
- **记录数**: 67,763
- **索引**: ✅ `idx_tga_core` (core_id), `idx_tga_trait` (trait_id), `idx_tga_composite`

#### **traits** 表（疾病/性状）
```sql
traits (
    trait_id INT PRIMARY KEY,
    trait_name VARCHAR(200),                        -- 疾病名称
    trait_doid VARCHAR(50),                         -- DOID 编号
    trait_category VARCHAR(100)                     -- 疾病分类
)
```
- **记录数**: 273 疾病

---

### 1.2 关键字段关联方式

#### **三层关联路径**
```
lncRNA (genes.gene_id)
    ↓ regulations.lncrna_gene_id
靶基因 (genes.gene_id)
    ↓ genes.core_id → trait_gene_associations.core_id
疾病 (traits.trait_id)
```

#### **核心关联逻辑**
```sql
FROM regulations r
JOIN genes lnc ON r.lncrna_gene_id = lnc.gene_id           -- lncRNA 信息
JOIN genes g ON r.target_gene_id = g.gene_id                -- 靶基因信息
JOIN trait_gene_associations tga ON g.core_id = tga.core_id -- 通过 core_id 关联疾病
JOIN traits t ON tga.trait_id = t.trait_id                   -- 疾病信息
```

**✅ 数据关联完整性**: 所有三层数据均通过外键正确关联，**无缺失字段**。

---

## 2. 数据规模统计

### 2.1 完整三层路径统计（所有数据）

| 维度 | 数量 |
|------|------|
| 参与的 lncRNA 数 | 1,955 |
| 参与的靶基因数 | 5,317 |
| 关联的疾病数 | 271 |
| 三层路径总数 | **13,443,179** |

**注意**: 由于一个基因可能关联多个疾病（平均约 10 个），路径数会显著膨胀。

---

### 2.2 适合可视化的数据量（BA >= 100）

| 维度 | 数量 |
|------|------|
| lncRNA 节点数 | 954 |
| 靶基因节点数 | 3,229 |
| 疾病节点数 | 243 |
| 三层路径总数 | **628,697** |

**推荐策略**: 使用 `binding_affinity >= 100` + `LIMIT` 控制返回数据量。

---

### 2.3 热门疾病数据分布

| 疾病 | 关联基因数 | 关联 lncRNA 数 |
|------|-----------|---------------|
| obesity（肥胖） | 940 | 638 |
| Abnormality of the nervous system（神经系统异常） | 426 | 425 |
| Rheumatoid arthritis（类风湿关节炎） | 421 | 340 |
| Arteriosclerosis（动脉硬化） | 413 | 349 |
| type 2 diabetes mellitus（2 型糖尿病） | 403 | 392 |
| asthma（哮喘） | 350 | 337 |
| Crohn's disease（克罗恩病） | 281 | 291 |

**可视化建议**: 支持按疾病筛选，避免一次性渲染所有数据。

---

## 3. 性能测试结果

### 3.1 查询方案对比

#### **方案 1: 直接 JOIN（推荐）**
```sql
SELECT
    lnc.gene_name as lncrna_name,
    g.gene_name as target_gene_name,
    t.trait_name as disease_name,
    r.binding_affinity
FROM regulations r
JOIN genes lnc ON r.lncrna_gene_id = lnc.gene_id
JOIN genes g ON r.target_gene_id = g.gene_id
JOIN trait_gene_associations tga ON g.core_id = tga.core_id
JOIN traits t ON tga.trait_id = t.trait_id
WHERE r.species_id = 1
  AND r.binding_affinity >= 150
LIMIT 500
```

**性能**: 28ms / 500 条
**优点**: 简单直接，适合小规模数据
**缺点**: 数据未去重（同一 lncRNA-基因-疾病可能多条）

---

#### **方案 2: 聚合去重**
```sql
SELECT
    lnc.gene_name as lncrna_name,
    g.gene_name as target_gene_name,
    t.trait_name as disease_name,
    COUNT(*) as flow_count,              -- 流量大小
    AVG(r.binding_affinity) as avg_ba,
    MAX(r.binding_affinity) as max_ba
FROM regulations r
JOIN genes lnc ON r.lncrna_gene_id = lnc.gene_id
JOIN genes g ON r.target_gene_id = g.gene_id
JOIN trait_gene_associations tga ON g.core_id = tga.core_id
JOIN traits t ON tga.trait_id = t.trait_id
WHERE r.species_id = 1
  AND r.binding_affinity >= 150
GROUP BY lnc.gene_name, g.gene_name, t.trait_name
LIMIT 500
```

**性能**: 56ms / 500 条（去重后）
**优点**: 数据去重，流量值可用于可视化粗细
**缺点**: 稍慢（2x），但仍在可接受范围

---

#### **方案 3: 分层查询（推荐用于大规模数据）**
```sql
-- Step 1: 先查询疾病-基因关联（数据量小，快速）
SELECT DISTINCT t.trait_id, t.trait_name, g.gene_id, g.gene_name
FROM trait_gene_associations tga
JOIN traits t ON tga.trait_id = t.trait_id
JOIN genes g ON tga.core_id = g.core_id
WHERE g.species_id = 1
LIMIT 50

-- Step 2: 根据基因 ID 查询调控关系（利用索引）
SELECT r.target_gene_id, lnc.gene_name, r.binding_affinity
FROM regulations r
JOIN genes lnc ON r.lncrna_gene_id = lnc.gene_id
WHERE r.target_gene_id = ANY(:gene_ids)
  AND r.species_id = 1
  AND r.binding_affinity >= 150
LIMIT 500
```

**性能**: 20ms（总计，两次查询）
**优点**: **最快**，适合大数据量，利用索引优化
**缺点**: 代码复杂度稍高

---

### 3.2 性能对比表

| 方案 | 查询时间 | 返回数据量 | 适用场景 |
|------|---------|-----------|---------|
| 方案 1（直接 JOIN） | 28ms | 500 条（原始） | 默认推荐 |
| 方案 2（聚合去重） | 56ms | 500 条（去重） | Sankey 流量可视化 |
| 方案 3（分层查询） | 20ms | 50 疾病 + 21 调控 | 大规模数据 |

**推荐**: **方案 2（聚合去重）**，适合 Sankey 图需求（流量值 = 重复路径数）。

---

## 4. 推荐 API 设计

### 4.1 端点定义

```
GET /api/v1/visualization/sankey-data
```

### 4.2 请求参数

| 参数 | 类型 | 必填 | 默认值 | 说明 |
|------|------|------|--------|------|
| `species_id` | int | 否 | 1 | 物种 ID（1=人类, 2=黑猩猩, 3=猕猴, 4=狨猴） |
| `min_ba` | float | 否 | 100.0 | 最小结合亲和力（筛选强调控关系） |
| `trait_name` | string | 否 | null | 疾病名称模糊搜索（如 "diabetes", "cancer"） |
| `limit` | int | 否 | 500 | 最大返回路径数（防止前端渲染过载） |

### 4.3 响应格式（Sankey 标准格式）

```json
{
  "success": true,
  "data": {
    "nodes": [
      {"id": "lncrna_1", "name": "MALAT1", "layer": 0},
      {"id": "gene_456", "name": "TP53", "layer": 1},
      {"id": "disease_3", "name": "lung cancer", "layer": 2}
    ],
    "links": [
      {
        "source": "lncrna_1",
        "target": "gene_456",
        "value": 150.5,           // binding_affinity
        "flow_count": 1           // 重复路径数（聚合时）
      },
      {
        "source": "gene_456",
        "target": "disease_3",
        "value": 0.0000012,       // trait_snp_pvalue
        "flow_count": 5
      }
    ]
  },
  "stats": {
    "lncrna_count": 18,
    "gene_count": 46,
    "disease_count": 65,
    "total_paths": 500
  },
  "query_params": {
    "species_id": 1,
    "min_ba": 100.0,
    "trait_name": null,
    "limit": 500
  }
}
```

### 4.4 推荐 SQL 实现（方案 2 改进版）

```sql
WITH sankey_data AS (
    SELECT
        lnc.gene_id as lncrna_id,
        lnc.gene_name as lncrna_name,
        g.gene_id as gene_id,
        g.gene_name as gene_name,
        t.trait_id as disease_id,
        t.trait_name as disease_name,
        AVG(r.binding_affinity) as avg_ba,
        AVG(tga.trait_snp_pvalue) as avg_pvalue,
        COUNT(*) as flow_count
    FROM regulations r
    JOIN genes lnc ON r.lncrna_gene_id = lnc.gene_id
    JOIN genes g ON r.target_gene_id = g.gene_id
    JOIN trait_gene_associations tga ON g.core_id = tga.core_id
    JOIN traits t ON tga.trait_id = t.trait_id
    WHERE r.species_id = :species_id
      AND r.binding_affinity >= :min_ba
      AND (:trait_name IS NULL OR t.trait_name ILIKE '%' || :trait_name || '%')
    GROUP BY lnc.gene_id, lnc.gene_name, g.gene_id, g.gene_name, t.trait_id, t.trait_name
    ORDER BY flow_count DESC, avg_ba DESC
    LIMIT :limit
)
SELECT * FROM sankey_data;
```

**性能预估**:
- 500 条: **50-80ms**
- 1000 条: **100-150ms**
- 5000 条: **300-500ms**

---

## 5. 性能优化建议

### 5.1 数据库层面

| 优化措施 | 状态 | 说明 |
|---------|------|------|
| 索引覆盖 | ✅ 已优化 | 所有 JOIN 字段均有索引 |
| LIMIT 限制 | ✅ 推荐 | 防止返回过多数据（建议 500-2000） |
| 聚合查询 | ✅ 推荐 | 使用 GROUP BY 去重（方案 2） |
| 物化视图 | ⚠️ 可选 | 如果频繁查询，可考虑预计算 |

### 5.2 API 层面

| 优化措施 | 优先级 | 说明 |
|---------|--------|------|
| Redis 缓存 | 🔴 高 | 缓存热门疾病查询结果（TTL 30min） |
| 分页支持 | 🟡 中 | 支持 offset/limit（大数据集） |
| 响应压缩 | 🟢 低 | Gzip 压缩（减少传输大小） |
| 异步查询 | 🟢 低 | 超过 5000 条时使用后台任务 |

### 5.3 前端可视化层面

| 建议 | 说明 |
|------|------|
| 限制节点数 | Sankey 图节点数建议 < 100（性能和可读性） |
| 分层渲染 | 先渲染主要流向（flow_count > 阈值） |
| 交互筛选 | 支持动态过滤疾病/lncRNA/基因 |
| 数据采样 | 超过 1000 条时自动采样显示 |

---

## 6. 潜在风险与解决方案

### 6.1 风险识别

| 风险 | 级别 | 描述 | 影响 |
|------|------|------|------|
| 数据膨胀 | 🟡 中 | 一个基因关联多个疾病（平均 10 个） | 返回数据量大 |
| 可视化过载 | 🟡 中 | 节点数过多导致 Sankey 图无法渲染 | 前端性能 |
| 去重策略 | 🟢 低 | 需明确定义"重复路径"的聚合规则 | 数据准确性 |

### 6.2 解决方案

#### **数据膨胀**
- ✅ 使用 `GROUP BY` 聚合（方案 2）
- ✅ 限制返回数量（`LIMIT 500-2000`）
- ✅ 支持疾病筛选（减少数据范围）

#### **可视化过载**
- ✅ 前端采样（仅显示 Top N 流向）
- ✅ 阈值过滤（`flow_count >= 3`，过滤弱关联）
- ✅ 分层展开（初始仅显示疾病层，点击展开基因/lncRNA）

#### **去重策略**
```sql
-- 推荐规则：
-- 1. 同一 (lncRNA, 基因, 疾病) 三元组视为一条路径
-- 2. flow_count = 该路径重复次数
-- 3. avg_ba = 平均结合亲和力
-- 4. avg_pvalue = 平均 GWAS p-value
GROUP BY lnc.gene_id, g.gene_id, t.trait_id
```

---

## 7. 代码复用评估

### 7.1 可复用的现有代码

| 文件 | 可复用代码 | 说明 |
|------|-----------|------|
| `app/routers/export.py` | `export_disease_network()` 函数 | 已实现疾病网络查询逻辑（90% 可复用） |
| `app/schemas/export.py` | `NetworkNode`, `NetworkEdge` | 网络数据结构定义（需适配 Sankey 格式） |
| `app/routers/diseases.py` | `get_disease_options()` | 疾病选项查询（支持筛选参数） |

### 7.2 需新增的代码

| 文件 | 新增内容 | 代码量估算 |
|------|---------|-----------|
| `app/routers/visualization.py` | `/sankey-data` 端点 | ~150 行 |
| `app/schemas/visualization.py` | Sankey 响应格式 Schema | ~50 行 |
| `app/utils/sankey_builder.py` | 数据聚合和格式转换逻辑 | ~100 行 |

**总工作量**: **~300 行代码，1-2 小时**

---

## 8. 最终可行性评估

### 8.1 综合评分矩阵

| 评估维度 | 得分 | 权重 | 加权分 | 说明 |
|---------|------|------|--------|------|
| 数据完整性 | 10/10 | 30% | 3.0 | ✅ 三层关联完整，无缺失字段 |
| 查询性能 | 9/10 | 25% | 2.25 | ✅ 28-56ms（优秀），支持优化到 20ms |
| 索引优化 | 10/10 | 15% | 1.5 | ✅ 所有关键字段均有索引 |
| 代码复用 | 9/10 | 15% | 1.35 | ✅ 90% 代码可复用，开发成本低 |
| 可扩展性 | 9/10 | 10% | 0.9 | ✅ 支持分页、筛选、缓存 |
| 风险控制 | 9/10 | 5% | 0.45 | ✅ 已识别风险，有缓解方案 |

**最终评分**: **9.45/10** ⭐⭐⭐⭐⭐

---

### 8.2 可行性结论

✅ **强烈推荐实施 Sankey 流向图 API**

**核心理由**:
1. **数据关联完整**: 三层路径（lncRNA → 基因 → 疾病）已在数据库中打通，无需额外数据清洗
2. **性能优异**: 查询响应时间 20-60ms（500 条），远低于可接受阈值（< 2s）
3. **开发成本低**: 可复用 90% 现有代码，预计 1-2 小时完成
4. **科研价值高**: 可直观展示 lncRNA 调控网络与疾病关联，支持治疗靶点研究

**预期效果**:
- 用户可交互式探索 lncRNA-基因-疾病关联
- 支持按疾病筛选（如 "diabetes"），快速定位相关 lncRNA
- 流量粗细可视化调控强度（binding affinity）和疾病关联强度（p-value）

---

## 9. 实施路线图

### 阶段 1: 核心功能（1 小时）
- [ ] 创建 `/api/v1/visualization/sankey-data` 端点
- [ ] 实现 SQL 查询逻辑（方案 2: 聚合去重）
- [ ] 定义 Sankey 响应格式 Schema

### 阶段 2: 优化与测试（30 分钟）
- [ ] 添加 Redis 缓存（TTL 30min）
- [ ] 添加查询参数验证（min_ba, limit）
- [ ] 性能测试（500/1000/2000 条）

### 阶段 3: 文档与集成（30 分钟）
- [ ] 更新 API 文档（Swagger）
- [ ] 提供前端集成示例（ECharts Sankey）
- [ ] 编写使用指南

**总时间**: **2 小时**

---

## 10. 附录

### 10.1 样例数据

#### 三层路径样例（未去重）
```json
{
  "lncrna_name": "CATG00000042135.1",
  "target_gene_name": "CTD-2545M3.8",
  "disease_name": "Abnormality of the nervous system",
  "binding_affinity": 755.99,
  "trait_snp_pvalue": 0.000007
}
```

#### 聚合后样例（去重）
```json
{
  "lncrna_name": "CATG00000042135.1",
  "target_gene_name": "CTD-2545M3.8",
  "disease_name": "Abnormality of the nervous system",
  "flow_count": 3,
  "avg_ba": 752.34,
  "max_ba": 755.99,
  "avg_pvalue": 0.0000065
}
```

---

### 10.2 前端 ECharts Sankey 集成示例

```typescript
import { useQuery } from '@tanstack/react-query';
import { getSankeyData } from '@/api/visualization';
import ReactECharts from 'echarts-for-react';

const SankeyChart = () => {
  const { data } = useQuery({
    queryKey: ['sankey', { min_ba: 150 }],
    queryFn: () => getSankeyData({ min_ba: 150, limit: 500 })
  });

  const option = {
    series: [{
      type: 'sankey',
      data: data?.data.nodes,
      links: data?.data.links.map(link => ({
        source: link.source,
        target: link.target,
        value: link.flow_count  // 流量粗细
      }))
    }]
  };

  return <ReactECharts option={option} />;
};
```

---

### 10.3 参考资料

- [PostgreSQL JOIN 性能优化](https://www.postgresql.org/docs/current/using-explain.html)
- [ECharts Sankey 图文档](https://echarts.apache.org/en/option.html#series-sankey)
- [现有 disease-network API](http://localhost:8000/api/v1/export/disease-network)

---

**报告生成时间**: 2025-12-12
**数据库版本**: PostgreSQL 14+
**测试环境**: 804,630 条 regulations 记录，67,763 条疾病关联记录
