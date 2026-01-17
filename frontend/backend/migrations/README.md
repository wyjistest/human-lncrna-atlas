# Database Migrations

Simple, lightweight migration system for managing PostgreSQL schema changes.

## Quick Start

```bash
# Check migration status
python3 migrations/run_migrations.py --status

# Preview changes (dry run)
python3 migrations/run_migrations.py --dry-run

# Apply pending migrations
python3 migrations/run_migrations.py
```

## How It Works

1. Migrations are numbered SQL files: `001_description.sql`, `002_description.sql`, etc.
2. Applied migrations are tracked in `schema_migrations` table
3. Runner applies pending migrations in order, skipping already-applied ones

## Creating New Migrations

1. Create file with next number: `004_your_description.sql`
2. Add header comment:
   ```sql
   -- Migration: 004_your_description
   -- Description: Brief description of changes
   -- Created: YYYY-MM-DD
   -- Idempotent: Yes/No
   ```
3. Use `IF NOT EXISTS` / `IF EXISTS` for idempotent operations
4. Test in development before applying to production

## Migration Files

| File | Description |
|------|-------------|
| `001_pg_trgm_indexes.sql` | GIN indexes for ILIKE pattern matching |
| `002_regulation_indexes.sql` | Performance indexes for regulations table |
| `003_regulations_best_peak_indexes.sql` | best_peak location indexes for overlap/IGV queries |

## Production Deployment

⚠️ **WARNING: Index Creation Locks**

Migrations containing `CREATE INDEX` (without `CONCURRENTLY`) will **LOCK the table** and **BLOCK ALL WRITES** during index building. For large tables (100K+ rows), this can take minutes to hours.

**Safe Options:**
1. **Empty Database**: Run migrations before importing data (no blocking)
2. **Maintenance Window**: Apply during scheduled downtime
3. **CONCURRENTLY**: Prefer `CREATE INDEX CONCURRENTLY` on live databases (non-blocking)
   - Option A: Run manually via `psql`
   - Option B: Put `CONCURRENTLY` statements into a migration file; the runner auto-detects and runs them in `AUTOCOMMIT` mode (outside a transaction)

```bash
# 1. Check current status
python3 migrations/run_migrations.py --status

# 2. Review pending migrations
python3 migrations/run_migrations.py --dry-run

# 3a. For EMPTY database or maintenance window:
python3 migrations/run_migrations.py

# 3b. For LIVE database with data (SAFE - No Locking):
# Option A: Manually run CONCURRENTLY version (see migration file comments)
psql -U user -d dbname -c "CREATE INDEX CONCURRENTLY IF NOT EXISTS idx_name ON table(col);"

# Option B: Create a migration using CONCURRENTLY and run the migration runner
# (the runner will automatically switch to AUTOCOMMIT for that migration file)
# python3 migrations/run_migrations.py

# 4. Verify indexes created
psql -d lncrna_production -c "\\di+ idx_*"
```

## Rolling Back

Migrations don't auto-rollback. For manual rollback:

1. Remove version from `schema_migrations` table
2. Manually reverse the changes (DROP INDEX, etc.)

```sql
-- Example: Roll back migration 002
DELETE FROM schema_migrations WHERE version = '002';
DROP INDEX IF EXISTS idx_regulations_lncrna_gene_id;
DROP INDEX IF EXISTS idx_regulations_target_gene_id;
DROP INDEX IF EXISTS idx_regulations_species_ba;
DROP INDEX IF EXISTS idx_regulations_species_chr;
```
