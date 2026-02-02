# 数据库设计二次修正总结

> 更新（2026-01-24）：本文档为历史修正总结快照，用于回溯审查与修正原因；现状以 `docs/CURRENT_STATUS.md` 为准。

**日期**: 2025-11-20
**版本**: v2.2 (二次修正)
**修正来源**: 第二轮技术审查

---

## 审查结论

审查者发现了**3个严重问题**，其中**问题3最为致命**，完全推翻了之前的JSON契约设计。

> "Network snapshot contract still reintroduces species-specific identifiers – that contradicts the earlier fix where trait associations were moved to core_id precisely to avoid per-species churn."

这是一个**设计层面的根本性错误**，必须立即修正。

---

## 问题1：gen_random_uuid()会导致schema创建失败 🔴

### 严重程度：🔴 **阻塞级**（schema无法执行）

### 问题描述

```sql
CREATE TABLE network_jobs (
    job_id UUID PRIMARY KEY DEFAULT gen_random_uuid(),  -- ❌ 函数不存在
    ...
);
```

**错误信息**：
```
ERROR:  function gen_random_uuid() does not exist
HINT:  No function matches the given name and argument types.
       You might need to add explicit type casts.
```

### 根本原因

PostgreSQL默认没有`gen_random_uuid()`函数，需要安装`pgcrypto`或`uuid-ossp`扩展。

### 修正方案

```sql
-- 【修正】脚本开头添加扩展
CREATE EXTENSION IF NOT EXISTS pgcrypto;

-- 或者使用uuid-ossp
-- CREATE EXTENSION IF NOT EXISTS "uuid-ossp";
-- 然后使用 uuid_generate_v4()
```

### 影响

- ✅ 修正前：schema脚本无法执行，项目卡在第一步
- ✅ 修正后：一键执行成功

---

## 问题2：core_id序列定义了但没用上 ⚠️

### 严重程度：⚠️⚠️ **中高级**（导致数据一致性问题）

### 问题描述

```sql
-- 定义了序列
CREATE SEQUENCE core_id_seq START WITH 100000000;

-- 但core_id列没有DEFAULT
CREATE TABLE core_id_assignments (
    core_id INTEGER PRIMARY KEY,  -- ❌ 没有DEFAULT nextval('core_id_seq')
    ...
);
```

**后果**：
- 每次插入必须手动指定core_id
- 不同导入脚本可能硬编码ID，导致冲突
- 失去序列的自动生成和一致性保证

### 修正方案

```sql
-- 【修正】添加DEFAULT
CREATE TABLE core_id_assignments (
    core_id INTEGER PRIMARY KEY DEFAULT nextval('core_id_seq'),
    ...
);
```

### 使用示例

```python
# 修正前（容易出错）
core_id = generate_manual_id()  # 每个脚本自己生成，容易冲突
insert_core_gene(core_id=core_id, ...)

# 修正后（自动生成，保证唯一）
insert_core_gene(...)  # core_id自动从序列生成
```

---

## 问题3：JSON契约仍用species-specific ID 🔴🔴🔴

### 严重程度：🔴🔴🔴 **设计错误级**（完全违背之前修正的初衷）

### 问题描述

**v2.1的设计（错误）**：

```json
{
  "nodes": {
    "lncrnas": ["CATG00000000034.1", "CATG00000000011.1"],  // ❌ species-specific ID
    "core_ids": {
      "CATG00000000034.1": 12345,  // core_id只是个映射
      "CATG00000000011.1": 67890
    }
  },
  "edges": [
    {
      "source": "CATG00000000034.1",  // ❌ species-specific ID
      "target": "ENSG00000012048.1",
      "weight": 75.5
    }
  ]
}
```

### 为什么这是错的？

#### 原因1：与第一次修正矛盾

我们在**第一次修正**时，把`trait_gene_associations`从`gene_id`改为`core_id`，目的是：
> "未来做跨物种分析时，最自然的粒度是core_id，而不是某个物种的gene_id。"

结果在`network_snapshots`里又用回了species-specific ID（ENSG/CATG），**完全矛盾**！

#### 原因2：跨物种对比困难

**场景**：对比human vs chimp autism MTG网络

```javascript
// ❌ v2.1设计：需要复杂的映射
const humanSnapshot = await fetchNetwork(species='human', ...);
const chimpSnapshot = await fetchNetwork(species='chimp', ...);

// 节点ID完全不同
humanSnapshot.nodes.lncrnas  // ["CATG00000000034.1", "CATG00000000011.1"]
chimpSnapshot.nodes.lncrnas  // ["CATG00000000034.1_chimp", ...]  // 推测

// 必须通过core_ids反查才能找共有节点
const humanCores = humanSnapshot.nodes.lncrnas.map(
  id => humanSnapshot.nodes.core_ids[id]
);
const chimpCores = chimpSnapshot.nodes.lncrnas.map(
  id => chimpSnapshot.nodes.core_ids[id]
);
const commonCores = humanCores.filter(c => chimpCores.includes(c));

// 5行代码，而且容易出错
```

#### 原因3：前端代码耦合species

```javascript
// Cytoscape配置
const elements = {
  nodes: snapshot.nodes.lncrnas.map(geneId => ({  // CATG00000000034.1
    data: {
      id: geneId,  // ❌ species-specific ID作为节点ID
      ...
    }
  }))
};

// 问题：切换物种时，节点ID完全变了，无法复用前端逻辑
```

### 修正方案（v2.2）

**用core_id作为节点key**：

```json
{
  "nodes": {
    "lncrnas": [12345, 67890, 11223],             // ✅ core_id列表
    "targets": [99001, 99002, 99003],
    "dual_role": [88888],

    "names": {                                    // canonical基因名
      12345: "RP11-13K12.1",
      67890: "RP11-45K23.2",
      99001: "BRCA1",
      99002: "TP53"
    },

    "species_gene_ids": {                         // ✅ species-specific ID变为属性
      12345: "CATG00000000034.1",
      67890: "CATG00000000045.1",
      99001: "ENSG00000012048.1",
      99002: "ENSG00000141510.1"
    },

    "chromosomes": {                              // 可选：位置信息
      12345: "chr1",
      99001: "chr17"
    }
  },

  "edges": [
    {
      "source": 12345,                            // ✅ lncRNA core_id
      "target": 99001,                            // ✅ target core_id
      "weight": 75.5,
      "regulation_id": 123456
    }
  ]
}
```

### 修正后的优势

#### 优势1：跨物种对比极简

```javascript
// ✅ v2.2设计：一行代码
const humanSnapshot = await fetchNetwork(species='human', ...);
const chimpSnapshot = await fetchNetwork(species='chimp', ...);

// 直接比较节点ID（都是core_id）
const commonNodes = humanSnapshot.nodes.lncrnas.filter(
  core_id => chimpSnapshot.nodes.lncrnas.includes(core_id)
);

// 1行代码！清晰、高效
```

#### 优势2：与核心设计一致

| 表 | 关键字段 | 一致性 |
|---|---|---|
| `trait_gene_associations` | **core_id** | ✅ |
| `regulations` | lncrna_gene_id, target_gene_id | 通过genes.core_id关联 |
| `network_snapshots.nodes` | **core_id** | ✅ |
| `network_snapshots.edges` | **source/target = core_id** | ✅ |

**整个系统围绕core_id设计，逻辑一致！**

#### 优势3：前端代码解耦

```javascript
// Cytoscape配置
const elements = {
  nodes: snapshot.nodes.lncrnas.map(coreId => ({
    data: {
      id: coreId,                                    // ✅ core_id作为节点ID
      label: snapshot.nodes.names[coreId],           // 显示基因名
      geneId: snapshot.nodes.species_gene_ids[coreId],  // ENSG/CATG（用于查详情）
      chr: snapshot.nodes.chromosomes[coreId],
      type: 'lncRNA'
    }
  })),

  edges: snapshot.edges.map(edge => ({
    data: {
      source: edge.source,  // core_id
      target: edge.target,  // core_id
      weight: edge.weight
    }
  }))
};

// 切换物种时，只需重新fetch snapshot，Cytoscape配置逻辑不变
```

#### 优势4：多物种叠加展示

```javascript
// 场景：在同一个图上叠加human和chimp的网络

// 加载两个物种的数据
const humanSnapshot = await fetchNetwork(species='human', ...);
const chimpSnapshot = await fetchNetwork(species='chimp', ...);

// 合并节点（去重）
const allCoreIds = new Set([
  ...humanSnapshot.nodes.lncrnas,
  ...humanSnapshot.nodes.targets,
  ...chimpSnapshot.nodes.lncrnas,
  ...chimpSnapshot.nodes.targets
]);

const nodes = Array.from(allCoreIds).map(coreId => ({
  data: {
    id: coreId,
    label: humanSnapshot.nodes.names[coreId] || chimpSnapshot.nodes.names[coreId],
    // 标记这个节点在哪些物种存在
    inHuman: humanSnapshot.nodes.lncrnas.includes(coreId) ||
             humanSnapshot.nodes.targets.includes(coreId),
    inChimp: chimpSnapshot.nodes.lncrnas.includes(coreId) ||
             chimpSnapshot.nodes.targets.includes(coreId)
  }
}));

// 如果用species-specific ID，这种叠加几乎不可能实现！
```

---

## 对比总结

| 设计 | v2.1（错误） | v2.2（修正） |
|------|------------|------------|
| 节点key | `"CATG00000000034.1"` | `12345` (core_id) |
| 边source/target | species-specific ID | core_id |
| 跨物种对比 | 5行代码，复杂 | 1行代码，简单 |
| 与trait设计一致性 | ❌ 矛盾 | ✅ 一致 |
| 前端node.id | species-specific | core_id |
| 多物种叠加 | 几乎不可能 | 简单实现 |
| 未来添加新物种 | 节点ID全变 | 节点ID不变 |

---

## 修正后的schema文件

**文件**: `schema_mvp_core.sql` (v2.2)

**关键修正**：

1. ✅ 开头添加`CREATE EXTENSION pgcrypto`
2. ✅ `core_id_assignments.core_id`添加`DEFAULT nextval('core_id_seq')`
3. ✅ `network_snapshots`的JSON契约改为core_id作为key

**验证方式**：

```bash
# 测试schema可执行
psql -U lncrna_admin -d lncrna_network -f schema_mvp_core.sql

# 应该没有错误，成功创建所有表
```

---

## 风险评估

| 修正 | 返工风险降低 | 兼容性影响 |
|------|-------------|-----------|
| 添加pgcrypto扩展 | 🔴🔴🔴 → ✅ | 无（向下兼容） |
| core_id添加DEFAULT | ⚠️⚠️ → ✅ | 无（可选覆盖） |
| JSON契约改core_id | 🔴🔴🔴 → ✅ | **需要修改draw_multispecies_network.py** |

**注意**：JSON契约修正会影响现有`draw_multispecies_network.py`的输出格式，需要同步修改。

---

## 后续行动

### 立即执行

1. ✅ 使用v2.2版schema_mvp_core.sql创建数据库
2. ⚠️ 修改`draw_multispecies_network.py`的网络构建函数，输出core_id格式的JSON
3. ⚠️ 更新数据导入脚本，使用自动生成的core_id

### 文档同步

- [ ] 更新`DATABASE_DESIGN_FINAL.md`（已过期）
- [x] 创建本文档`REVISION_SUMMARY_V2.md`

---

## 审查者评价

> "这三个问题都是实施时会立即爆炸的bug，尤其是第3个问题完全颠覆了刚才的修正。"

**我的回应**：

完全同意。第3个问题是我的**设计盲点**——我修正了`trait_gene_associations`改用core_id，却在`network_snapshots`里又用回了species-specific ID，这是**逻辑矛盾**。

审查者的洞察力非常敏锐，这次修正**真正**解决了跨物种分析的核心问题。

---

**修正完成日期**: 2025-11-20
**状态**: ✅ 所有严重问题已修正，ready for implementation
