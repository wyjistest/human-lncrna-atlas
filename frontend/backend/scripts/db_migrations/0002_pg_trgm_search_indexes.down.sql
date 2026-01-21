-- 0002_pg_trgm_search_indexes (DOWN)
--
-- 回滚：删除 0002_pg_trgm_search_indexes.up.sql 创建的 GIN trigram 索引。
-- 注意：默认不 DROP EXTENSION pg_trgm（可能被其他对象依赖）。
--
-- 推荐执行：
--   bash frontend/backend/scripts/db_migrate.sh down 0002_pg_trgm_search_indexes

\echo '== [0002] Dropping trigram GIN indexes (CONCURRENTLY) =='

DROP INDEX CONCURRENTLY IF EXISTS idx_genes_gene_ensembl_id_trgm;
DROP INDEX CONCURRENTLY IF EXISTS idx_genes_gene_name_trgm;
DROP INDEX CONCURRENTLY IF EXISTS idx_chipseq_experiments_cell_type_trgm;
DROP INDEX CONCURRENTLY IF EXISTS idx_traits_trait_name_trgm;

ANALYZE traits;
ANALYZE chipseq_experiments;
ANALYZE genes;

DO $$
DECLARE
  idx_count INTEGER;
BEGIN
  SELECT COUNT(*) INTO idx_count
  FROM pg_class c
  JOIN pg_namespace n ON n.oid = c.relnamespace
  WHERE n.nspname = 'public'
    AND c.relname IN (
    'idx_traits_trait_name_trgm',
    'idx_chipseq_experiments_cell_type_trgm',
    'idx_genes_gene_name_trgm',
    'idx_genes_gene_ensembl_id_trgm'
  );

  IF idx_count = 0 THEN
    RAISE NOTICE '✅ [0002] pg_trgm indexes removed (0/4)';
  ELSE
    RAISE EXCEPTION '❌ [0002] expected 0 pg_trgm indexes, found %', idx_count;
  END IF;
END
$$;
