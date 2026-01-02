# Human LncRNA Atlas - 数据库 Schema

## 目录结构

```
schema/
├── v2.3/                    # 当前版本 Schema
│   ├── 01_core.sql          # 核心表 (必需)
│   ├── 02_extension.sql     # ⚠️ 已弃用，使用 04 替代
│   ├── 03_sample_data.sql   # 示例数据 (开发/测试)
│   ├── 04_extension_phase2.sql  # 扩展表 (可选)
│   ├── 05_mv_lncrna_chipseq_overlaps.sql  # ChIP-seq overlaps 物化视图
│   ├── 06_mv_lncrna_chipseq_overlaps_epigenetic_summary_ba100.sql  # /analysis/summary 预聚合 (BA>=100)
│   └── 07_mv_analysis_summary_high_affinity_ba100.sql  # /analysis/summary (High Affinity) 预聚合 (BA>=100)
├── migrations/              # 增量迁移脚本
│
└── (另见) frontend/backend/sql/
	    └── chipseq_schema.sql   # ChIP-seq 表观遗传学扩展 (可选)
```

## 执行顺序

### 新环境初始化

```bash
# 1. 必需 - 核心表
psql -d lncrna_production -f schema/v2.3/01_core.sql

# 1.1 可选 - Analysis Summary 预聚合（加速 /analysis/summary 的 High Affinity）
psql -d lncrna_production -f schema/v2.3/07_mv_analysis_summary_high_affinity_ba100.sql

# 2. 可选 - 扩展功能 (RepeatMasker 基础)
psql -d lncrna_production -f schema/v2.3/04_extension_phase2.sql

# 3. 可选 - ChIP-seq 表观遗传学扩展 (分区表、mark types)
psql -d lncrna_production -f frontend/backend/sql/chipseq_schema.sql

# 4. 可选 - 物化视图 (用于预计算重叠，需先完成步骤 2-3)
psql -d lncrna_production -f schema/v2.3/05_mv_lncrna_chipseq_overlaps.sql

# 4.1 可选 - Epigenetic 预聚合 (加速 /analysis/summary，需先完成步骤 4)
psql -d lncrna_production -f schema/v2.3/06_mv_lncrna_chipseq_overlaps_epigenetic_summary_ba100.sql

# 5. 仅开发 - 示例数据
psql -d lncrna_production -f schema/v2.3/03_sample_data.sql
```

### 生产环境注意事项

- **不要执行** `02_extension.sql` (已弃用)
- **不要执行** `03_sample_data.sql` (仅测试用)
- 物化视图需要在数据导入后执行
- `frontend/backend/sql/chipseq_schema.sql` 会尝试 `CREATE EXTENSION IF NOT EXISTS btree_gist;`（用于复合 GiST 索引），请确保数据库允许创建扩展

## 版本说明

| 文件 | 版本 | 状态 | 说明 |
|------|------|------|------|
| 01_core.sql | v2.3 | ✅ 当前 | 核心基因、调控关系表 |
| 02_extension.sql | v2.3 | ⚠️ 弃用 | 使用 04 替代 |
| 03_sample_data.sql | v2.3 | ✅ 当前 | 开发测试数据 |
| 04_extension_phase2.sql | v2.3.1 | ✅ 当前 | IF NOT EXISTS 安全版 |
| 05_mv_lncrna_chipseq_overlaps.sql | v2.3 | ✅ 当前 | ChIP-seq 重叠物化视图 |
| 06_mv_lncrna_chipseq_overlaps_epigenetic_summary_ba100.sql | v2.3.3 | ✅ 当前 | Epigenetic 预聚合（BA>=100） |
| 07_mv_analysis_summary_high_affinity_ba100.sql | v2.3.4 | ✅ 当前 | Analysis Summary 预聚合（BA>=100） |
| frontend/backend/sql/chipseq_schema.sql | v1.0 | ✅ 当前 | ChIP-seq 表观遗传学扩展 |

## 迁移说明

增量迁移脚本位于 `migrations/` 目录，按日期命名。
