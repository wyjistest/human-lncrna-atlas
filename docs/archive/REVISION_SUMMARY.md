# 数据库设计修正总结

**日期**: 2025-11-20
**版本**: v2.1 (基于审查意见修正)

---

## 审查结论总结

审查者评价：
> "核心层 + 扩展层的两层模型非常适合你现在的需求，整体方向是对的。只需要在几个关键点上收紧/澄清，就可以在保持灵活的前提下大幅降低未来重构风险。"

**三个严重级问题已全部修正** ✅

---

## 修正1：trait关联模型（最严重）

### 原设计问题

```sql
-- ❌ 错误：挂在物种特异gene_id上
CREATE TABLE trait_gene_associations (
    gene_id INTEGER REFERENCES genes(gene_id),
    trait_id INTEGER,
    ontology_id INTEGER
);
```

**返工风险**：
- 未来做跨物种分析（如"autism基因在chimp的网络"）时，需要绕一大圈
- 查询逻辑别扭：human gene_id → core_id → chimp gene_id
- table15数据的本质是"core基因与疾病关联"，不是"某物种基因与疾病关联"

### 修正后设计

```sql
-- ✅ 正确：直接挂core_id
CREATE TABLE trait_gene_associations (
    core_id INTEGER REFERENCES core_genes(core_id),  -- 直接关联core
    trait_id INTEGER,
    ontology_id INTEGER,
    evidence_species_id INTEGER DEFAULT 1,  -- 标记数据来自人类
    ...
);
```

**优势**：
- 跨物种查询直接用core_id，一次JOIN搞定
- 生物学语义正确：BRCA1与乳腺癌的关联是跨物种的
- 未来添加新物种无需修改trait关联

**查询对比**：

```sql
-- 修正后（简洁）
SELECT r.*
FROM regulations r
JOIN genes g ON r.target_gene_id = g.gene_id
WHERE g.core_id IN (
    SELECT core_id FROM trait_gene_associations
    WHERE trait_id = 10 AND ontology_id = 5
)
AND r.species_id = 2  -- chimp
AND r.binding_affinity >= 50;

-- vs 原设计（别扭）
SELECT r.*
FROM regulations r
JOIN genes chimp_g ON r.target_gene_id = chimp_g.gene_id
JOIN genes human_g ON chimp_g.core_id = human_g.core_id  -- 绕圈
JOIN trait_gene_associations tga ON human_g.gene_id = tga.gene_id
WHERE tga.trait_id = 10 AND r.species_id = 2;
```

---

## 修正2：network_snapshots JSON契约（严重）

### 原设计问题

```sql
-- ❌ 错误：没有定义结构
CREATE TABLE network_snapshots (
    snapshot_data JSONB  -- 什么结构？谁也不知道
);
```

**返工风险**：
- 后端API不知道返回什么格式
- 前端不知道怎么解析
- 等写到一半才发现结构不对，三方（数据库+API+前端）都得改

### 修正后设计

```sql
-- ✅ 正确：明确三个字段，每个字段有清晰契约
CREATE TABLE network_snapshots (
    nodes JSONB NOT NULL,       -- 契约：{lncrnas, targets, names, core_ids}
    edges JSONB NOT NULL,       -- 契约：[{source, target, weight, regulation_id}]
    statistics JSONB NOT NULL,  -- 契约：{total_genes, ba_stats, ...}
    ...
);

-- 添加CHECK约束验证结构
ALTER TABLE network_snapshots
    ADD CONSTRAINT check_nodes_structure
    CHECK (
        jsonb_typeof(nodes) = 'object' AND
        nodes ? 'lncrnas' AND
        nodes ? 'targets' AND
        nodes ? 'names' AND
        nodes ? 'core_ids'
    );
```

**契约文档**（schema_mvp_core.sql中完整注释）：

```javascript
// nodes结构
{
  "lncrnas": ["CATG00000000034.1", ...],
  "targets": ["ENSG00000012048.1", ...],
  "dual_role": ["ENSG00000267506.1"],
  "names": {
    "CATG00000000034.1": "RP11-13K12.1",
    "ENSG00000012048.1": "BRCA1"
  },
  "core_ids": {
    "CATG00000000034.1": 12345,
    "ENSG00000012048.1": 67890
  }
}

// edges结构
[
  {
    "source": "CATG00000000034.1",
    "target": "ENSG00000012048.1",
    "weight": 75.5,
    "regulation_id": 12345
  }
]

// statistics结构
{
  "total_genes": 49,
  "lncrna_count": 18,
  "regulation_count": 341,
  "ba_stats": {
    "min": 50.03,
    "max": 80.69,
    "median": 55.18,
    "mean": 56.2
  }
}
```

**优势**：
- 前后端开发可以同步进行（契约明确）
- 与现有`draw_multispecies_network.py`输出对齐，直接复用
- CHECK约束防止写错数据

---

## 修正3：MVP范围简化（严重）

### 原设计问题

**表数量**：16张表（核心层10张 + 扩展层5张 + 缓存层2张）
**高级特性**：分区表 + GENERATED列 + GIN索引 + 复杂JOIN
**问题**：对1人、1-2周MVP来说太重

### 修正后设计

**Phase 1 - MVP核心（1周必完成）**

只实现**12张表**：
```
核心层：
1. species (4行)
2. core_id_assignments
3. core_genes
4. genes
5. traits
6. ontologies
7. trait_gene_associations (基于core_id)
8. import_batches
9. regulations (核心业务)
10. sequences (可选)

缓存层：
11. network_jobs
12. network_snapshots (带JSON契约)
```

**去掉的高级特性**（Phase 2/3再说）：
- ❌ genomic_features（扩展层）
- ❌ 分区表
- ❌ GENERATED列
- ❌ 复杂GIN索引

**保留必要优化**：
- ✅ 明确的索引策略（已写死在SQL中）
- ✅ CHECK约束
- ✅ 外键级联
- ✅ 批次追踪

**优势**：
- 开发压力减半
- 核心功能（lncRNA调控网络）完整可用
- 扩展层预留接口但不实现，不影响未来扩展

---

## 修正4：regulations表索引策略（中等）

### 原设计问题

只笼统说"建索引"，没有明确哪些字段组合。

### 修正后设计

**明确的索引策略**（直接写入SQL）：

```sql
-- 基础索引
CREATE INDEX idx_reg_species ON regulations(species_id);
CREATE INDEX idx_reg_lncrna ON regulations(lncrna_gene_id);
CREATE INDEX idx_reg_target ON regulations(target_gene_id);

-- 【重要】主力查询组合索引
CREATE INDEX idx_reg_species_lnc_ba
    ON regulations(species_id, lncrna_gene_id, binding_affinity DESC);

CREATE INDEX idx_reg_species_target
    ON regulations(species_id, target_gene_id);

-- BA阈值筛选专用（部分索引）
CREATE INDEX idx_reg_ba
    ON regulations(binding_affinity)
    WHERE binding_affinity >= 50;

-- 位置查询
CREATE INDEX idx_reg_location
    ON regulations(target_chromosome, target_start, target_end);
```

**说明**：
- `idx_reg_species_lnc_ba`：支持"按物种+lncRNA+BA筛选"（最常用）
- `idx_reg_ba WHERE >= 50`：部分索引，只索引高BA值，节省空间
- `idx_reg_location`：支持基因组位置范围查询

---

## 修正5：Multiz建模策略（中等）

### 原设计问题

说"预留alignment_blocks表"，与"扩展层统一用genomic_features"矛盾。

### 修正后策略

**优先级**：
1. **Phase 1-2**：不考虑Multiz
2. **Phase 3**：如果要导入Multiz，先尝试用`genomic_features`表达
3. **Phase 4**：只有确认需要复杂的序列比对查询时，才新建`alignment_blocks`

**理由**：
- 保持扩展层统一性
- 避免提前优化
- Multiz不是MVP核心需求

---

## 修正6：attribute_schema验证机制（中等）

### 原设计问题

`feature_tracks.attribute_schema`只是JSONB注释，没有验证逻辑。

### 修正后策略

**导入时强制验证**（Python层）：

```python
def validate_and_import_feature(track_name, data_df):
    # 1. 从数据库拉schema
    schema = get_track_schema(track_name)
    required_fields = schema['fields'].keys()

    # 2. 验证字段完整性
    for field in required_fields:
        if field not in data_df.columns:
            raise ValueError(f"缺少必需字段: {field}")

    # 3. 验证字段类型
    for field, field_type in schema['fields'].items():
        validate_type(data_df[field], field_type)

    # 4. 通过验证后才导入
    import_features(data_df)
```

**说明**：
- attribute_schema从"文档"变为"强制约束"
- 避免导入时字段拼写错误（fold_enrichment vs fold_enrich）
- 数据质量保证

---

## 其他改进

### 改进7：CHECK约束范围

```sql
-- BA范围不写死[0, 1000]，避免未来数据变化时频繁修改约束
binding_affinity DECIMAL(10, 4) CHECK (binding_affinity >= 0)  -- 只保证非负
```

### 改进8：添加core_id_assignments追踪表

```sql
-- 追踪每个core_id的来源
CREATE TABLE core_id_assignments (
    core_id INTEGER PRIMARY KEY,
    assignment_source VARCHAR(50),  -- 'ortholog_table' 或 'auto_generated'
    created_at TIMESTAMP,
    notes TEXT
);

-- 自动生成序列（避免与ortholog冲突）
CREATE SEQUENCE core_id_seq START WITH 100000000;
```

---

## 对比总结

| 项目 | 原设计 | 修正后 | 返工风险降低 |
|------|--------|--------|-------------|
| trait关联 | gene_id | **core_id** | ⚠️⚠️⚠️ → ✅ |
| network_snapshots | 无契约 | **明确JSON契约** | ⚠️⚠️⚠️ → ✅ |
| MVP范围 | 16表+高级特性 | **12表+简化** | ⚠️⚠️ → ✅ |
| regulations索引 | 笼统说明 | **明确策略** | ⚠️⚠️ → ✅ |
| Multiz建模 | 单独表 | **统一feature层** | ⚠️ → ✅ |
| schema验证 | 无 | **Python层验证** | ⚠️ → ✅ |

---

## 实施建议

### Week 1: MVP核心

**Day 1**:
- 安装PostgreSQL 15
- 执行`schema_mvp_core.sql`
- 验证表结构

**Day 2-3**:
- 导入现有数据（regulations, traits, genes）
- 注意：trait_gene_associations改为基于core_id导入

**Day 4-5**:
- 测试核心查询（autism MTG网络）
- 验证性能（目标：<500ms）

### Week 2: API + 前端

**Day 6-8**:
- FastAPI实现
- network_snapshots按契约返回JSON
- API测试

**Day 9-11**:
- React + Cytoscape.js前端
- 按JSON契约解析数据
- E2E测试

### Week 3+: 扩展层（可选）

- 建扩展层表（feature_tracks, genomic_features）
- 导入第一批扩展数据（RepeatMasker或H3K27me3）
- 跨层查询测试

---

## 文件清单

| 文件 | 用途 | 状态 |
|------|------|------|
| `DATABASE_DESIGN_FINAL.md` | 完整设计文档 | 待更新 |
| `schema_mvp_core.sql` | MVP建表脚本（修正版） | ✅ 已生成 |
| `REVISION_SUMMARY.md` | 本文档 | ✅ 已生成 |

---

## 审查签字

| 角色 | 意见 | 日期 | 签名 |
|------|------|------|------|
| 原审查者 | 待确认修正是否充分 | | |
| 开发者 | 接受所有严重级修正 | 2025-11-20 | Claude |

---

**修正完成**。三个严重级问题已全部解决，返工风险大幅降低。
