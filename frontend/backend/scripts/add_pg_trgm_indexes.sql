-- pg_trgm GIN 索引迁移脚本
--
-- 目的：优化 ILIKE '%pattern%' 模糊搜索性能
-- 问题：PostgreSQL 对 ILIKE '%..%' 默认使用全表扫描，大数据量时极慢
-- 方案：使用 pg_trgm 扩展的三元组索引，支持模糊匹配的索引查找
--
-- 受影响的查询：
-- 1. traits.trait_name - 疾病名称搜索（visualization.py, export.py）
-- 2. chipseq_experiments.cell_type - 细胞类型搜索（chipseq_experiments.py）
-- 3. genes.gene_name / genes.gene_ensembl_id - 基因模糊搜索（genes.py, regulations.py）
--
-- 执行方式：
--   psql -d lncrna_production -f add_pg_trgm_indexes.sql
--
-- NOTE (推荐，带审计/可回滚)：
--   bash frontend/backend/scripts/db_migrate.sh up 0002_pg_trgm_search_indexes
--   bash frontend/backend/scripts/db_migrate.sh down 0002_pg_trgm_search_indexes
--
-- 或在 Python 中执行：
--   from sqlalchemy import text
--   db.execute(text(open('add_pg_trgm_indexes.sql').read()))
--   db.commit()

-- ============================================================================
-- Step 1: 启用 pg_trgm 扩展
-- ============================================================================
-- 需要超级用户权限，如果没有权限请联系 DBA
CREATE EXTENSION IF NOT EXISTS pg_trgm;

-- 验证扩展已安装
DO $$
BEGIN
    IF NOT EXISTS (SELECT 1 FROM pg_extension WHERE extname = 'pg_trgm') THEN
        RAISE EXCEPTION 'pg_trgm extension is not installed. Please install it first.';
    END IF;
    RAISE NOTICE 'pg_trgm extension is available';
END
$$;

-- ============================================================================
-- Step 2: 创建 GIN 索引
-- ============================================================================

-- 索引 1: traits.trait_name
-- 用途：疾病/性状名称的模糊搜索
-- 查询示例：WHERE trait_name ILIKE '%diabetes%'
DROP INDEX IF EXISTS idx_traits_trait_name_trgm;
CREATE INDEX idx_traits_trait_name_trgm
ON traits USING GIN (trait_name gin_trgm_ops);

-- 索引 2: chipseq_experiments.cell_type
-- 用途：细胞类型的模糊搜索
-- 查询示例：WHERE cell_type ILIKE '%liver%'
DROP INDEX IF EXISTS idx_chipseq_experiments_cell_type_trgm;
CREATE INDEX idx_chipseq_experiments_cell_type_trgm
ON chipseq_experiments USING GIN (cell_type gin_trgm_ops);

-- 索引 3: genes.gene_name
-- 用途：基因名称的模糊搜索（typeahead / filter）
-- 查询示例：WHERE gene_name ILIKE '%TP53%'
DROP INDEX IF EXISTS idx_genes_gene_name_trgm;
CREATE INDEX idx_genes_gene_name_trgm
ON genes USING GIN (gene_name gin_trgm_ops);

-- 索引 4: genes.gene_ensembl_id
-- 用途：Ensembl ID 的模糊搜索（typeahead / filter）
-- 查询示例：WHERE gene_ensembl_id ILIKE '%ENSG000001%'
DROP INDEX IF EXISTS idx_genes_gene_ensembl_id_trgm;
CREATE INDEX idx_genes_gene_ensembl_id_trgm
ON genes USING GIN (gene_ensembl_id gin_trgm_ops);

-- ============================================================================
-- Step 3: 更新表统计信息
-- ============================================================================
-- 确保查询规划器能正确使用新索引
ANALYZE traits;
ANALYZE chipseq_experiments;
ANALYZE genes;

-- ============================================================================
-- Step 4: 验证索引创建成功
-- ============================================================================
DO $$
DECLARE
    idx_count INTEGER;
BEGIN
    SELECT COUNT(*) INTO idx_count
    FROM pg_indexes
    WHERE indexname IN (
        'idx_traits_trait_name_trgm',
        'idx_chipseq_experiments_cell_type_trgm',
        'idx_genes_gene_name_trgm',
        'idx_genes_gene_ensembl_id_trgm'
    );

    IF idx_count = 4 THEN
        RAISE NOTICE '✅ Successfully created 4 pg_trgm GIN indexes';
    ELSE
        RAISE WARNING '⚠️ Expected 4 indexes, found %', idx_count;
    END IF;
END
$$;

-- ============================================================================
-- 性能验证查询（可选）
-- ============================================================================
-- 执行以下查询验证索引被使用：
--
-- EXPLAIN ANALYZE
-- SELECT * FROM traits WHERE trait_name ILIKE '%diabetes%' LIMIT 10;
--
-- 期望看到：Bitmap Index Scan on idx_traits_trait_name_trgm
-- 而非：Seq Scan on traits

-- ============================================================================
-- 索引大小估算
-- ============================================================================
-- 三元组索引大小约为原列数据大小的 1-3 倍
-- 对于 traits 表（约 1 万行）预计增加约 1-5 MB
-- 对于 chipseq_experiments 表，根据 cell_type 列数据量估算
