-- 0001_regulations_indexes (DOWN)
--
-- 回滚：删除 0001_regulations_indexes.up.sql 创建的索引。
--
-- 推荐执行：
--   bash frontend/backend/scripts/db_migrate.sh down 0001_regulations_indexes

\echo '== [0001] Dropping regulations indexes (CONCURRENTLY) =='

DROP INDEX CONCURRENTLY IF EXISTS idx_regulations_species_chr;
DROP INDEX CONCURRENTLY IF EXISTS idx_regulations_species_ba;
DROP INDEX CONCURRENTLY IF EXISTS idx_regulations_target_gene_id;
DROP INDEX CONCURRENTLY IF EXISTS idx_regulations_lncrna_gene_id;

ANALYZE regulations;

DO $$
DECLARE
  idx_count INTEGER;
BEGIN
  SELECT COUNT(*) INTO idx_count
  FROM pg_class c
  JOIN pg_namespace n ON n.oid = c.relnamespace
  WHERE n.nspname = 'public'
    AND c.relname IN (
      'idx_regulations_lncrna_gene_id',
      'idx_regulations_target_gene_id',
      'idx_regulations_species_ba',
      'idx_regulations_species_chr'
    );

  IF idx_count = 0 THEN
    RAISE NOTICE '✅ [0001] regulations indexes removed (0/4)';
  ELSE
    RAISE EXCEPTION '❌ [0001] expected 0 regulations indexes, found %', idx_count;
  END IF;
END
$$;
