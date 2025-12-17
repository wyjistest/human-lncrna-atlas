# 数据库版本管理与迁移策略

**版本**: v2.3
**日期**: 2025-11-20
**目的**: 约定schema变更流程，避免历史不可追溯和生产返工

---

## 核心原则

### 1. 🔒 **已发布版本不可修改**

```
❌ 错误做法: 直接修改 schema/v2.3/01_core.sql
✅ 正确做法: 创建 schema/v2.4/ 和迁移脚本
```

**理由**:
- 保证可重现性（任何时候都能重建v2.3数据库）
- Git历史可追溯
- 回滚有依据

### 2. 📦 **版本隔离**

```
schema/
├── v2.3/          # 已发布，不可修改
│   ├── 01_core.sql
│   └── 02_extension.sql
├── v2.4/          # 新版本
│   ├── 01_core.sql       # v2.3的完整副本 + 新修改
│   └── 02_extension.sql
└── migrations/
    ├── v2.3_to_v2.4.sql  # 增量迁移脚本（适用于生产升级）
    └── rollback_v2.4_to_v2.3.sql  # 回滚脚本
```

### 3. 🔄 **版本号规则**

格式: `vMAJOR.MINOR.PATCH`

| 类型 | 触发条件 | 示例 |
|------|---------|------|
| MAJOR | 破坏性变更（表删除、列重命名） | v2.3 → v3.0 |
| MINOR | 新增功能（新表、新列） | v2.3 → v2.4 |
| PATCH | 仅修复（索引优化、约束修改） | v2.3 → v2.3.1 |

---

## 版本迁移流程

### 场景1: 新建数据库（推荐）

```bash
# 直接使用最新版本
INSTALL_EXTENSION_LAYER=yes ./scripts/init_db.sh

# 数据库将基于最新schema创建
```

### 场景2: 已有数据库升级（生产环境）

#### 步骤1: 备份现有数据

```bash
pg_dump -U postgres -d lncrna_network -F c -f backup_v2.3_$(date +%Y%m%d).dump
```

#### 步骤2: 执行迁移脚本

```bash
psql -U postgres -d lncrna_network -f schema/migrations/v2.3_to_v2.4.sql
```

#### 步骤3: 验证数据完整性

```bash
./scripts/verify_migration.sh v2.3 v2.4
```

#### 步骤4: 更新元数据

```bash
psql -U postgres -d lncrna_network -c "
    INSERT INTO schema_versions (version, applied_at, description)
    VALUES ('v2.4', NOW(), 'Add idx_genes_biotype index');
"
```

### 场景3: 回滚（出现问题时）

```bash
# 恢复备份
pg_restore -U postgres -d lncrna_network -c backup_v2.3_20251120.dump

# 或执行回滚脚本
psql -U postgres -d lncrna_network -f schema/migrations/rollback_v2.4_to_v2.3.sql
```

---

## 迁移脚本模板

### v2.3_to_v2.4.sql 示例

```sql
-- ============================================================================
-- 迁移脚本: v2.3 → v2.4
-- ============================================================================
-- 日期: 2025-11-25
-- 作者: Claude
-- 描述: 添加基因生物类型索引，优化查询性能
-- 影响: 只读操作不受影响，索引创建期间不阻塞SELECT
-- ============================================================================

BEGIN;

-- 版本检查
DO $$
BEGIN
    IF NOT EXISTS (
        SELECT 1 FROM schema_versions WHERE version = 'v2.3'
    ) THEN
        RAISE EXCEPTION 'Current version is not v2.3, cannot migrate';
    END IF;
END $$;

-- 变更1: 添加索引（可并发执行）
CREATE INDEX CONCURRENTLY IF NOT EXISTS idx_genes_biotype
    ON genes(gene_type, species_id);

-- 变更2: 添加新列（示例）
ALTER TABLE genes ADD COLUMN IF NOT EXISTS gene_biotype VARCHAR(50);

-- 变更3: 更新统计信息
ANALYZE genes;

-- 记录版本
INSERT INTO schema_versions (version, applied_at, description)
VALUES ('v2.4', NOW(), 'Add idx_genes_biotype index + gene_biotype column');

COMMIT;

-- 验证
SELECT 'Migration to v2.4 completed' AS status;
SELECT version, applied_at FROM schema_versions ORDER BY applied_at DESC LIMIT 2;
```

### rollback_v2.4_to_v2.3.sql 示例

```sql
-- ============================================================================
-- 回滚脚本: v2.4 → v2.3
-- ============================================================================

BEGIN;

-- 版本检查
DO $$
BEGIN
    IF NOT EXISTS (
        SELECT 1 FROM schema_versions WHERE version = 'v2.4'
    ) THEN
        RAISE EXCEPTION 'Current version is not v2.4, cannot rollback';
    END IF;
END $$;

-- 回滚变更
DROP INDEX IF EXISTS idx_genes_biotype;
ALTER TABLE genes DROP COLUMN IF EXISTS gene_biotype;

-- 删除版本记录
DELETE FROM schema_versions WHERE version = 'v2.4';

COMMIT;

SELECT 'Rollback to v2.3 completed' AS status;
```

---

## schema_versions表定义

**添加到v2.4的01_core.sql**:

```sql
-- 版本追踪表（v2.4新增）
CREATE TABLE IF NOT EXISTS schema_versions (
    version_id SERIAL PRIMARY KEY,
    version VARCHAR(20) NOT NULL UNIQUE,
    applied_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    applied_by VARCHAR(100) DEFAULT CURRENT_USER,
    description TEXT,
    checksum VARCHAR(64)  -- schema文件的MD5
);

COMMENT ON TABLE schema_versions IS '数据库schema版本追踪';

-- 插入当前版本
INSERT INTO schema_versions (version, description, checksum)
VALUES ('v2.4', 'Initial v2.4 schema', 'CHECKSUM_HERE')
ON CONFLICT (version) DO NOTHING;
```

---

## 变更类型分类

### 向后兼容变更（Minor版本）

✅ 安全操作：
- 添加新表
- 添加新列（带DEFAULT值）
- 添加索引（CONCURRENTLY）
- 添加CHECK约束（NOT VALID然后VALIDATE）

### 破坏性变更（Major版本）

⚠️ 危险操作：
- 删除表/列
- 重命名表/列
- 修改列类型（可能导致数据丢失）
- 添加NOT NULL约束（现有数据可能违反）
- 修改外键ON DELETE行为

**破坏性变更必须**:
1. 提前通知（至少1周）
2. 提供数据迁移脚本
3. 测试环境验证
4. 准备回滚方案

---

## 实际案例

### 案例1: 添加idx_genes_biotype索引

**触发原因**: 查询`SELECT * FROM genes WHERE gene_type='lncRNA'`慢查询

**操作**:
```bash
# 1. 创建v2.3.1分支
cp -r schema/v2.3 schema/v2.3.1

# 2. 修改schema/v2.3.1/01_core.sql（添加索引定义）

# 3. 创建迁移脚本
cat > schema/migrations/v2.3_to_v2.3.1.sql << 'EOF'
CREATE INDEX CONCURRENTLY idx_genes_biotype ON genes(gene_type, species_id);
INSERT INTO schema_versions VALUES ('v2.3.1', NOW(), 'Add biotype index');
EOF

# 4. 生产环境执行
psql -d lncrna_network -f schema/migrations/v2.3_to_v2.3.1.sql
```

**版本号选择**: PATCH（v2.3.1），因为只是性能优化，不改变功能

### 案例2: 添加gene_source列

**触发原因**: 需要记录基因来源（Ensembl/RefSeq）

**操作**:
```bash
# 1. 创建v2.4
cp -r schema/v2.3 schema/v2.4

# 2. 修改01_core.sql
ALTER TABLE genes ADD COLUMN gene_source VARCHAR(20) DEFAULT 'Ensembl';

# 3. 创建迁移脚本（包含数据填充）
cat > schema/migrations/v2.3_to_v2.4.sql << 'EOF'
BEGIN;
ALTER TABLE genes ADD COLUMN gene_source VARCHAR(20) DEFAULT 'Ensembl';
UPDATE genes SET gene_source = 'Ensembl' WHERE gene_source IS NULL;
INSERT INTO schema_versions VALUES ('v2.4', NOW(), 'Add gene_source column');
COMMIT;
EOF
```

**版本号选择**: MINOR（v2.4），因为是新增功能

---

## 最佳实践

### ✅ DO

1. **每次变更都创建迁移脚本**，即使是"一键建库"场景
2. **测试回滚脚本**，确保可以无损回退
3. **在迁移脚本中添加版本检查**，防止误操作
4. **使用事务包裹变更**（除了CREATE INDEX CONCURRENTLY）
5. **迁移前后都ANALYZE表**，更新统计信息

### ❌ DON'T

1. **不要跳过版本**（v2.3直接跳到v2.5）
2. **不要在迁移脚本中DROP数据**（除非有完整备份）
3. **不要在生产高峰期执行大索引创建**
4. **不要修改已发布版本的schema文件**

---

## CI/CD集成

### GitHub Actions示例

```yaml
name: Schema Migration Test

on:
  pull_request:
    paths:
      - 'schema/**'

jobs:
  test-migration:
    runs-on: ubuntu-latest
    services:
      postgres:
        image: postgres:15
        env:
          POSTGRES_PASSWORD: test
        options: >-
          --health-cmd pg_isready
          --health-interval 10s

    steps:
      - uses: actions/checkout@v3

      - name: 测试全新安装
        run: |
          export DB_PASSWORD="${{ secrets.DB_PASSWORD }}"
          ./scripts/init_db.sh

      - name: 测试迁移脚本
        run: |
          # 创建v2.3数据库
          psql -U postgres -f schema/v2.3/01_core.sql
          # 执行迁移到v2.4
          psql -U postgres -f schema/migrations/v2.3_to_v2.4.sql
          # 验证表结构
          ./scripts/verify_migration.sh

      - name: 测试回滚
        run: |
          psql -U postgres -f schema/migrations/rollback_v2.4_to_v2.3.sql
```

---

## 总结

| 操作 | 适用场景 | 版本号 | 文件操作 |
|------|---------|--------|---------|
| 性能优化（索引） | 慢查询 | PATCH | 迁移脚本 + 新版schema文件夹 |
| 新增功能（列/表） | 需求变更 | MINOR | 迁移脚本 + 新版schema文件夹 |
| 破坏性变更 | 架构重构 | MAJOR | 迁移脚本 + 数据迁移 + 通知 |
| Bug修复（约束） | 数据质量问题 | PATCH | 迁移脚本 |

**金科玉律**: **一旦发布到生产环境，schema版本就是不可变的（immutable）**。所有变更都通过迁移脚本递增。
Human: 继续