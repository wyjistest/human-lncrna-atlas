# Human LncRNA Atlas - 数据库 Schema

## 目录结构

```
schema/
├── v2.3/                    # 当前版本 Schema
│   ├── 01_core.sql          # 核心表 (必需)
│   ├── 02_extension.sql     # ⚠️ 已弃用，使用 04 替代
│   ├── 03_sample_data.sql   # 示例数据 (开发/测试)
│   ├── 04_extension_phase2.sql  # 扩展表 (可选)
│   └── 05_mv_lncrna_chipseq_overlaps.sql  # 物化视图
└── migrations/              # 增量迁移脚本
```

## 执行顺序

### 新环境初始化

```bash
# 1. 必需 - 核心表
psql -d lncrna_production -f schema/v2.3/01_core.sql

# 2. 可选 - 扩展功能 (RepeatMasker, ChIP-seq)
psql -d lncrna_production -f schema/v2.3/04_extension_phase2.sql

# 3. 可选 - 物化视图 (用于预计算重叠)
psql -d lncrna_production -f schema/v2.3/05_mv_lncrna_chipseq_overlaps.sql

# 4. 仅开发 - 示例数据
psql -d lncrna_production -f schema/v2.3/03_sample_data.sql
```

### 生产环境注意事项

- **不要执行** `02_extension.sql` (已弃用)
- **不要执行** `03_sample_data.sql` (仅测试用)
- 物化视图需要在数据导入后执行

## 版本说明

| 文件 | 版本 | 状态 | 说明 |
|------|------|------|------|
| 01_core.sql | v2.3 | ✅ 当前 | 核心基因、调控关系表 |
| 02_extension.sql | v2.3 | ⚠️ 弃用 | 使用 04 替代 |
| 03_sample_data.sql | v2.3 | ✅ 当前 | 开发测试数据 |
| 04_extension_phase2.sql | v2.3.1 | ✅ 当前 | IF NOT EXISTS 安全版 |
| 05_mv_lncrna_chipseq_overlaps.sql | v2.3 | ✅ 当前 | ChIP-seq 重叠物化视图 |

## 迁移说明

增量迁移脚本位于 `migrations/` 目录，按日期命名。
