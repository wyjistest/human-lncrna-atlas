# 数据库迁移（可审计 & 可回滚）

本项目目前以“脚本化迁移”为主（非 ORM/Alembic），目标是：

- **可审计**：每次迁移执行（up/down）都会写入数据库表 `schema_migration_events`，便于追溯“谁在何时对哪些对象做了什么”。
- **可回滚**：每个迁移都提供对应的 `*.down.sql`，用于回滚索引/结构变更。

## 1) 迁移目录结构

- 迁移文件：`frontend/backend/scripts/db_migrations/*.up.sql` 与 `*.down.sql`
- 执行入口：`frontend/backend/scripts/db_migrate.sh`

## 2) 如何执行（推荐）

### 2.1 查看可用迁移

```bash
bash frontend/backend/scripts/db_migrate.sh list
```

### 2.2 查看审计记录（最近 50 条）

```bash
bash frontend/backend/scripts/db_migrate.sh status
```

### 2.3 执行单个迁移

```bash
# 示例：启用 pg_trgm + 创建 trigram GIN 索引
bash frontend/backend/scripts/db_migrate.sh up 0002_pg_trgm_search_indexes
```

### 2.4 回滚单个迁移

```bash
bash frontend/backend/scripts/db_migrate.sh down 0002_pg_trgm_search_indexes
```

### 2.5 一次性执行所有未应用迁移

```bash
bash frontend/backend/scripts/db_migrate.sh up-all
```

## 3) 数据库连接配置

脚本优先使用标准 `psql` 环境变量（推荐）：

- `PGHOST` / `PGPORT` / `PGUSER` / `PGPASSWORD` / `PGDATABASE`

也支持项目风格变量（便于与其他脚本一致）：

- `DB_HOST` / `DB_PORT` / `DB_USER` / `DB_PASSWORD` / `DB_NAME`

示例（项目风格）：

```bash
DB_HOST="127.0.0.1" DB_PORT="5432" DB_USER="lncrna" DB_PASSWORD="postgres" DB_NAME="lncrna_production" \
  bash frontend/backend/scripts/db_migrate.sh up-all
```

## 4) 日志与止损

- 每次执行会生成一份日志（默认）：`docs/reports/db-migrations/<ts>_<migration>_<direction>.log`
- 可通过 `LOG_DIR` 覆盖输出目录（例如写到 `/tmp`）：

```bash
LOG_DIR="/tmp/db-migrations" bash frontend/backend/scripts/db_migrate.sh up 0001_regulations_indexes
```

**止损建议：**
- 所有索引迁移使用 `CONCURRENTLY`，避免长时间阻塞写入；但会更耗时，且不能放在事务里。
- 若执行失败，优先查看 log 文件；必要时可先执行对应 `down` 回滚，再排查重试。

## 5) 已内置迁移列表（当前）

- `0001_regulations_indexes`：regulations 常用 JOIN/过滤/排序索引
- `0002_pg_trgm_search_indexes`：pg_trgm + traits/chipseq_experiments/genes trigram GIN 索引

