-- 0001_regulations_indexes (UP)
--
-- 目标：为 regulations 常用 JOIN / 过滤 / 排序模式补齐索引，降低大表全表扫描风险。
-- 特性：可审计（db_migrate.sh 会写入 schema_migration_events）/ 可回滚（对应 down.sql）。
--
-- 推荐执行：
--   bash frontend/backend/scripts/db_migrate.sh up 0001_regulations_indexes
--
-- 说明：
-- - 使用 CONCURRENTLY 避免长时间阻塞写入（代价：耗时更久，且不能包在事务里）。
-- - 若需手工执行：psql -v ON_ERROR_STOP=1 -f <this-file>

\echo '== [0001] Creating regulations indexes (CONCURRENTLY) =='

CREATE INDEX CONCURRENTLY IF NOT EXISTS idx_regulations_lncrna_gene_id
  ON regulations(lncrna_gene_id);

CREATE INDEX CONCURRENTLY IF NOT EXISTS idx_regulations_target_gene_id
  ON regulations(target_gene_id);

CREATE INDEX CONCURRENTLY IF NOT EXISTS idx_regulations_species_ba
  ON regulations(species_id, binding_affinity DESC);

CREATE INDEX CONCURRENTLY IF NOT EXISTS idx_regulations_species_chr
  ON regulations(species_id, target_chromosome);

ANALYZE regulations;

DO $$
DECLARE
  idx_count INTEGER;
BEGIN
  SELECT COUNT(*) INTO idx_count
  FROM pg_class c
  JOIN pg_index i ON i.indexrelid = c.oid
  JOIN pg_namespace n ON n.oid = c.relnamespace
  WHERE n.nspname = 'public'
    AND c.relname IN (
      'idx_regulations_lncrna_gene_id',
      'idx_regulations_target_gene_id',
      'idx_regulations_species_ba',
      'idx_regulations_species_chr'
    )
    AND i.indisvalid = TRUE;

  IF idx_count = 4 THEN
    RAISE NOTICE '✅ [0001] regulations indexes ready (4/4)';
  ELSE
    RAISE EXCEPTION '❌ [0001] expected 4 regulations indexes, found %', idx_count;
  END IF;
END
$$;
