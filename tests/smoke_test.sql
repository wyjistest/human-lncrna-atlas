-- ============================================================================
-- 冒烟测试 + 查询基准
-- ============================================================================
-- 版本: v2.3
-- 用途: 快速验证数据库功能 + 性能基准
-- 执行: psql -d lncrna_network -f tests/smoke_test.sql
-- ============================================================================

\timing on
\echo '========================================='
\echo '冒烟测试 + 查询基准'
\echo '========================================='
\echo ''

-- ============================================================================
-- 1. 基础验证
-- ============================================================================

\echo '1️⃣  表结构验证'
\echo ''

SELECT
    'core_tables' AS check_type,
    COUNT(*) AS actual,
    12 AS expected,
    CASE WHEN COUNT(*) = 12 THEN '✅' ELSE '❌' END AS status
FROM information_schema.tables
WHERE table_schema = 'public'
  AND table_name IN ('species', 'core_id_assignments', 'core_genes', 'genes',
                      'traits', 'ontologies', 'trait_gene_associations',
                      'import_batches', 'regulations', 'sequences',
                      'network_jobs', 'network_snapshots');

-- ============================================================================
-- 2. 数据完整性验证
-- ============================================================================

\echo ''
\echo '2️⃣  数据完整性验证'
\echo ''

-- 2.1 species表
SELECT 'species_count' AS check, COUNT(*) AS value, '4' AS expected
FROM species;

-- 2.2 genes表外键完整性
SELECT 'genes_with_invalid_species' AS check, COUNT(*) AS value, '0' AS expected
FROM genes
WHERE species_id NOT IN (SELECT species_id FROM species);

-- 2.3 regulations外键完整性
SELECT 'regulations_orphan_lncrna' AS check, COUNT(*) AS value, '0' AS expected
FROM regulations
WHERE lncrna_gene_id NOT IN (SELECT gene_id FROM genes);

SELECT 'regulations_orphan_target' AS check, COUNT(*) AS value, '0' AS expected
FROM regulations
WHERE target_gene_id NOT IN (SELECT gene_id FROM genes);

-- 2.4 trait_gene_associations外键完整性
SELECT 'tga_orphan_core_id' AS check, COUNT(*) AS value, '0' AS expected
FROM trait_gene_associations
WHERE core_id NOT IN (SELECT core_id FROM core_genes);

-- ============================================================================
-- 3. 索引存在性验证
-- ============================================================================

\echo ''
\echo '3️⃣  索引存在性验证（核心索引）'
\echo ''

SELECT
    'core_indexes' AS check_type,
    COUNT(*) AS actual,
    17 AS expected,
    CASE WHEN COUNT(*) >= 17 THEN '✅' ELSE '❌' END AS status
FROM pg_indexes
WHERE schemaname = 'public'
  AND indexname IN (
    'idx_genes_species', 'idx_genes_core', 'idx_genes_ensembl',
    'idx_genes_name', 'idx_genes_location',
    'idx_reg_species', 'idx_reg_lncrna', 'idx_reg_target', 'idx_reg_batch',
    'idx_reg_species_lnc_ba', 'idx_reg_species_target', 'idx_reg_ba', 'idx_reg_location',
    'idx_tga_core', 'idx_tga_trait', 'idx_tga_ontology', 'idx_tga_composite'
  );

-- ============================================================================
-- 4. 性能基准查询（基于文档7.1/7.2节）
-- ============================================================================

\echo ''
\echo '4️⃣  性能基准查询'
\echo ''

-- Benchmark 1: 查询autism MTG的调控网络
\echo 'Benchmark 1: Autism MTG网络查询'
\echo 'Expected: < 500ms on production data'
\echo ''

EXPLAIN (ANALYZE, BUFFERS, FORMAT TEXT)
WITH target_genes AS (
    SELECT g.gene_id, g.gene_name, g.core_id
    FROM genes g
    JOIN trait_gene_associations tga ON g.core_id = tga.core_id
    WHERE tga.trait_id = (SELECT trait_id FROM traits WHERE trait_name = 'autism spectrum disorder')
      AND tga.ontology_id = (SELECT ontology_id FROM ontologies WHERE ontology_name = 'middle temporal gyrus')
      AND g.species_id = 1
)
SELECT
    lnc.gene_name AS lncrna,
    tgt.gene_name AS target,
    r.binding_affinity,
    COUNT(*) OVER() AS total_edges
FROM regulations r
JOIN target_genes lnc ON r.lncrna_gene_id = lnc.gene_id
JOIN target_genes tgt ON r.target_gene_id = tgt.gene_id
WHERE r.binding_affinity >= 50
ORDER BY r.binding_affinity DESC
LIMIT 10;

-- Benchmark 2: 按物种统计regulations
\echo ''
\echo 'Benchmark 2: 按物种统计调控关系'
\echo 'Expected: < 100ms'
\echo ''

EXPLAIN (ANALYZE, BUFFERS)
SELECT
    s.species_code,
    COUNT(*) AS regulation_count,
    AVG(r.binding_affinity) AS avg_ba,
    MIN(r.binding_affinity) AS min_ba,
    MAX(r.binding_affinity) AS max_ba
FROM regulations r
JOIN species s ON r.species_id = s.species_id
WHERE r.binding_affinity >= 50
GROUP BY s.species_code
ORDER BY regulation_count DESC;

-- Benchmark 3: 查找BRCA1的所有调控者
\echo ''
\echo 'Benchmark 3: BRCA1调控者查询'
\echo 'Expected: < 50ms'
\echo ''

EXPLAIN (ANALYZE, BUFFERS)
SELECT
    lnc.gene_name AS lncrna,
    r.binding_affinity,
    r.target_chromosome,
    r.target_start,
    r.target_end
FROM regulations r
JOIN genes lnc ON r.lncrna_gene_id = lnc.gene_id
JOIN genes tgt ON r.target_gene_id = tgt.gene_id
WHERE tgt.gene_name = 'BRCA1'
  AND r.species_id = 1
  AND r.binding_affinity >= 50
ORDER BY r.binding_affinity DESC;

-- ============================================================================
-- 5. 数据质量检查
-- ============================================================================

\echo ''
\echo '5️⃣  数据质量检查'
\echo ''

-- 5.1 检查BA值范围
SELECT 'ba_out_of_range' AS check, COUNT(*) AS value, '0' AS expected
FROM regulations
WHERE binding_affinity < 0 OR binding_affinity > 1000;

-- 5.2 检查坐标合法性
SELECT 'invalid_coordinates' AS check, COUNT(*) AS value, '0' AS expected
FROM regulations
WHERE target_start IS NOT NULL AND target_end IS NOT NULL
  AND target_end <= target_start;

-- 5.3 检查必填字段
SELECT 'genes_missing_ensembl_id' AS check, COUNT(*) AS value, '0' AS expected
FROM genes
WHERE gene_ensembl_id IS NULL;

-- 5.4 检查重复数据
SELECT 'duplicate_genes' AS check, COUNT(*) - COUNT(DISTINCT (species_id, gene_ensembl_id)) AS value, '0' AS expected
FROM genes;

-- ============================================================================
-- 6. 性能统计
-- ============================================================================

\echo ''
\echo '6️⃣  表大小统计'
\echo ''

SELECT
    schemaname,
    tablename,
    pg_size_pretty(pg_total_relation_size(schemaname||'.'||tablename)) AS total_size,
    pg_size_pretty(pg_relation_size(schemaname||'.'||tablename)) AS table_size,
    pg_size_pretty(pg_indexes_size(schemaname||'.'||tablename)) AS index_size
FROM pg_tables
WHERE schemaname = 'public'
  AND tablename IN ('genes', 'regulations', 'sequences', 'trait_gene_associations')
ORDER BY pg_total_relation_size(schemaname||'.'||tablename) DESC;

-- ============================================================================
-- 总结
-- ============================================================================

\echo ''
\echo '========================================='
\echo '✅ 冒烟测试完成'
\echo ''
\echo '请检查上述输出:'
\echo '  - 所有 status 列应为 ✅'
\echo '  - expected 列应等于 actual/value'
\echo '  - 查询执行时间应在预期范围内'
\echo '========================================='
