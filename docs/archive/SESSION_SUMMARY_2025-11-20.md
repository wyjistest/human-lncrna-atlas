# 数据库架构设计对话总结

**日期**: 2025-11-20
**任务**: 多物种lncRNA调控网络数据库架构设计
**状态**: ✅ 已完成，通过3轮审查

---

## 核心任务

将静态的Python脚本`draw_multispecies_network.py`（生成4物种lncRNA调控网络图）改造为数据库驱动的Web交互系统。

**需求**：
- 存储~100万条调控关系（4物种）
- 支持Web交互筛选（性状+组织+物种+BA阈值）
- 未来可扩展（RepeatMasker、H3K27me3、Multiz等）
- 1人开发，1-2周MVP

---

## 设计方案：两层架构

```
核心层（Core）：固定表结构，lncRNA调控网络专用
  - species, core_genes, genes, traits, ontologies
  - trait_gene_associations (基于core_id)
  - regulations (核心业务)
  - sequences (分离存储)
  - import_batches (批次追踪)
  - network_jobs, network_snapshots (缓存)

扩展层（Extension）：通用表结构，未来添加新数据类型
  - feature_tracks, genomic_features, feature_gene_links
  - (MVP阶段暂不实现)
```

**关键原则**：
- 核心业务简单、高性能
- 扩展灵活、不改核心schema
- 避免过度抽象

---

## 三轮审查修正

### 第一轮审查 → v2.1

**问题**：
1. ❌ `trait_gene_associations`挂在`gene_id`上，跨物种查询会返工
2. ❌ `network_snapshots`缺少JSON契约
3. ❌ MVP范围过大（16张表+高级特性）

**修正**：
- ✅ trait关联改为基于`core_id`（支持跨物种查询）
- ✅ 明确network_snapshots的JSON契约
- ✅ 简化到12张表（去掉分区、GENERATED列等高级特性）

### 第二轮审查 → v2.2

**问题**（致命）：
1. 🔴 `gen_random_uuid()`缺少`pgcrypto`扩展 → schema无法执行
2. ⚠️ `core_id_seq`定义了但未连接到列
3. 🔴🔴🔴 **JSON契约用species-specific ID作为key，与trait设计矛盾**

**修正**：
- ✅ 脚本开头添加`CREATE EXTENSION IF NOT EXISTS pgcrypto`
- ✅ `core_id_assignments.core_id`添加`DEFAULT nextval('core_id_seq')`
- ✅ **JSON契约改用core_id作为节点/边的key**

### 第三轮审查（最终）

**结论**: "No further blocking issues found. Schema已经solid."

---

## 关键设计决策

### 1. trait_gene_associations基于core_id

```sql
-- ✅ 正确（v2.1修正）
CREATE TABLE trait_gene_associations (
    core_id INTEGER REFERENCES core_genes(core_id),  -- 直接挂core_id
    trait_id INTEGER,
    ontology_id INTEGER,
    evidence_species_id INTEGER DEFAULT 1  -- 标记数据来自人类
);
```

**理由**：BRCA1与乳腺癌的关联是跨物种的，查询时用core_id直接关联。

### 2. network_snapshots JSON契约（v2.2核心修正）

**节点/边的key必须是core_id**，而非species-specific ID：

```json
{
  "nodes": {
    "lncrnas": [12345, 67890],           // ✅ core_id列表
    "names": {12345: "RP11-13K12.1"},
    "species_gene_ids": {12345: "CATG00000000034.1"}  // species ID变为属性
  },
  "edges": [
    {"source": 12345, "target": 99001, "weight": 75.5}  // ✅ core_id
  ]
}
```

**为什么关键**：
- 与trait设计一致（都用core_id）
- 跨物种对比：1行代码 vs 5行代码
- 前端node.id用core_id，物种切换时ID不变

### 3. MVP范围：12张表

**Phase 1（1周必完成）**：
- 核心层10张：species, core_genes, genes, traits, ontologies, trait_gene_associations, regulations, sequences, import_batches, core_id_assignments
- 缓存层2张：network_jobs, network_snapshots

**Phase 2+（可选）**：扩展层（genomic_features等）

---

## 最终交付物

| 文件 | 用途 | 状态 |
|------|------|------|
| `schema_mvp_core.sql` | MVP建表脚本（v2.2） | ✅ 可直接执行 |
| `DATABASE_DESIGN_FINAL.md` | 完整设计文档（v2.2） | ✅ 已同步 |
| `REVISION_SUMMARY.md` | 第一轮修正总结 | ℹ️ v2.1 |
| `REVISION_SUMMARY_V2.md` | 第二轮修正总结 | ✅ v2.2 |

---

## 技术栈

- **数据库**: PostgreSQL 15 + pgcrypto扩展
- **后端**: FastAPI + SQLAlchemy
- **前端**: React + Cytoscape.js
- **部署**: Docker Compose（4容器）

---

## 下一步行动

1. **立即可执行**：
   ```bash
   # 安装PostgreSQL 15
   sudo apt-get install postgresql-15

   # 执行schema
   psql -U postgres -d lncrna_network -f schema_mvp_core.sql
   ```

2. **数据导入**：
   - 修改现有导入脚本，trait关联改用core_id
   - 修改`draw_multispecies_network.py`，输出core_id格式的JSON

3. **API开发**：
   - FastAPI实现核心端点
   - network_snapshots按JSON契约返回

4. **前端开发**：
   - Cytoscape.js用core_id作为node.id
   - 按JSON契约解析数据

---

## 关键教训

1. **跨物种设计必须用core_id** - 从trait到network_snapshots保持一致
2. **JSON契约必须提前定死** - 否则数据库+API+前端三方返工
3. **MVP范围控制** - 避免过度设计，分阶段实施
4. **审查很重要** - 3轮审查发现了6个严重问题

---

## 审查者评价

> "No further blocking issues found. Schema已经solid, ready for implementation."

**状态**: ✅ 设计完成，可以开始实施
