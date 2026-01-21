-- 0002_pg_trgm_search_indexes (UP)
--
-- 目标：优化 ILIKE '%pattern%' 模糊搜索性能（使用 pg_trgm + GIN trigram ops）。
-- 覆盖：
-- - traits.trait_name（疾病/性状名称搜索）
-- - chipseq_experiments.cell_type（ChIP-seq experiments 过滤）
-- - genes.gene_name / genes.gene_ensembl_id（基因 typeahead / regulations 过滤）
--
-- 特性：可审计（db_migrate.sh 会写入 schema_migration_events）/ 可回滚（对应 down.sql）。
--
-- 推荐执行：
--   bash frontend/backend/scripts/db_migrate.sh up 0002_pg_trgm_search_indexes
--
-- 说明：
-- - CREATE INDEX CONCURRENTLY 不会阻塞写入（代价：耗时更久，且不能包在事务里）。
-- - pg_trgm 扩展通常需要较高权限；若无权限请联系 DBA。

\echo '== [0002] Enabling pg_trgm extension =='

CREATE EXTENSION IF NOT EXISTS pg_trgm;

\echo '== [0002] Creating trigram GIN indexes (CONCURRENTLY) =='

CREATE INDEX CONCURRENTLY IF NOT EXISTS idx_traits_trait_name_trgm
  ON traits USING GIN (trait_name gin_trgm_ops);

CREATE INDEX CONCURRENTLY IF NOT EXISTS idx_chipseq_experiments_cell_type_trgm
  ON chipseq_experiments USING GIN (cell_type gin_trgm_ops);

CREATE INDEX CONCURRENTLY IF NOT EXISTS idx_genes_gene_name_trgm
  ON genes USING GIN (gene_name gin_trgm_ops);

CREATE INDEX CONCURRENTLY IF NOT EXISTS idx_genes_gene_ensembl_id_trgm
  ON genes USING GIN (gene_ensembl_id gin_trgm_ops);

ANALYZE traits;
ANALYZE chipseq_experiments;
ANALYZE genes;

DO $$
DECLARE
  idx_count INTEGER;
BEGIN
  IF NOT EXISTS (SELECT 1 FROM pg_extension WHERE extname = 'pg_trgm') THEN
    RAISE EXCEPTION '❌ [0002] pg_trgm extension is not installed';
  END IF;

  SELECT COUNT(*) INTO idx_count
  FROM pg_class c
  JOIN pg_index i ON i.indexrelid = c.oid
  JOIN pg_namespace n ON n.oid = c.relnamespace
  WHERE n.nspname = 'public'
    AND c.relname IN (
      'idx_traits_trait_name_trgm',
      'idx_chipseq_experiments_cell_type_trgm',
      'idx_genes_gene_name_trgm',
      'idx_genes_gene_ensembl_id_trgm'
    )
    AND i.indisvalid = TRUE;

  IF idx_count = 4 THEN
    RAISE NOTICE '✅ [0002] pg_trgm indexes ready (4/4)';
  ELSE
    RAISE EXCEPTION '❌ [0002] expected 4 pg_trgm indexes, found %', idx_count;
  END IF;
END
$$;
