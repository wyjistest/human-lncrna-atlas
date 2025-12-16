-- Regulation 表索引迁移脚本
--
-- 目的：优化 regulation 相关查询性能
-- 问题：regulations 表有 80 万+ 行，频繁 JOIN 和 ORDER BY 导致全表扫描
-- 解决方案：添加覆盖索引支持常用查询模式
--
-- 执行方式：
--   psql -d lncrna_production -f add_regulation_indexes.sql
--
-- ⚠️ 生产环境风险提示：
--   1. DROP INDEX 会获取表的排他锁（ACCESS EXCLUSIVE），阻塞所有读写操作
--   2. 对于 80 万行的表，锁表时间可能达到数秒
--   3. 建议在低峰期执行，或改用以下安全方式：
--      - 使用 CREATE INDEX CONCURRENTLY（不阻塞写入，但需要更长时间）
--      - 使用 DROP INDEX CONCURRENTLY（PostgreSQL 11+）
--      - 跳过 DROP IF EXISTS，仅在索引不存在时创建
--
-- 生产环境推荐执行方式（无锁）：
--   CREATE INDEX CONCURRENTLY IF NOT EXISTS idx_xxx ON table(column);
--   -- 验证索引正常工作后再清理旧索引

-- ============================================================================
-- Step 1: 添加单列索引（用于 JOIN 优化）
-- ============================================================================

-- 索引 1: lncrna_gene_id 上的索引
-- 用途：JOIN genes ON regulations.lncrna_gene_id = genes.gene_id
-- 优化查询：regulations.py:208, genes.py:152, export.py:155
DROP INDEX IF EXISTS idx_regulations_lncrna_gene_id;
CREATE INDEX idx_regulations_lncrna_gene_id
ON regulations(lncrna_gene_id);

-- 索引 2: target_gene_id 上的索引
-- 用途：JOIN genes ON regulations.target_gene_id = genes.gene_id
-- 优化查询：regulations.py:209, export.py:155, network.py:300+
DROP INDEX IF EXISTS idx_regulations_target_gene_id;
CREATE INDEX idx_regulations_target_gene_id
ON regulations(target_gene_id);

-- ============================================================================
-- Step 2: 添加复合索引（用于过滤+排序优化）
-- ============================================================================

-- 索引 3: (species_id, binding_affinity DESC) 复合索引
-- 用途：按物种过滤并按亲和力排序的查询
-- 优化查询模式：
--   WHERE species_id IN (...)
--   ORDER BY binding_affinity DESC
DROP INDEX IF EXISTS idx_regulations_species_ba;
CREATE INDEX idx_regulations_species_ba
ON regulations(species_id, binding_affinity DESC);

-- 索引 4: (species_id, target_chromosome) 复合索引
-- 用途：按物种和染色体过滤的查询
-- 优化查询：chipseq overlaps 相关查询
DROP INDEX IF EXISTS idx_regulations_species_chr;
CREATE INDEX idx_regulations_species_chr
ON regulations(species_id, target_chromosome);

-- ============================================================================
-- Step 3: 更新表统计信息
-- ============================================================================
ANALYZE regulations;

-- ============================================================================
-- Step 4: 验证索引创建成功
-- ============================================================================
DO $$
DECLARE
    idx_count INTEGER;
BEGIN
    SELECT COUNT(*) INTO idx_count
    FROM pg_indexes
    WHERE tablename = 'regulations'
    AND indexname IN (
        'idx_regulations_lncrna_gene_id',
        'idx_regulations_target_gene_id',
        'idx_regulations_species_ba',
        'idx_regulations_species_chr'
    );

    IF idx_count = 4 THEN
        RAISE NOTICE '✅ Successfully created 4 regulation indexes';
    ELSE
        RAISE WARNING '⚠️ Expected 4 indexes, found %', idx_count;
    END IF;
END
$$;

-- ============================================================================
-- 索引大小估算（80万行表）
-- ============================================================================
-- lncrna_gene_id: ~20 MB (INTEGER)
-- target_gene_id: ~20 MB (INTEGER)
-- species_ba: ~30 MB (INTEGER + NUMERIC DESC)
-- species_chr: ~25 MB (INTEGER + VARCHAR)
-- 总计约增加 ~100 MB 磁盘空间
