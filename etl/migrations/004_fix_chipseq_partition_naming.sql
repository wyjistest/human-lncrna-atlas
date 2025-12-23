-- ============================================================================
-- 迁移脚本: ChIP-seq 分区表命名修复
-- Phase 9.20 - Codex 审查修复
-- ============================================================================
-- 问题: chipseq_peaks_mouse 分区名与实际物种定义不符
--       species_id=2 对应的是 Chimp（黑猩猩），而非 Mouse
-- 解决: 重命名分区表并添加缺失的物种分区
-- ============================================================================

-- 检查当前分区情况
SELECT
    inhrelid::regclass AS partition_name,
    pg_get_expr(relpartbound, inhrelid) AS partition_bound
FROM pg_inherits
JOIN pg_class ON pg_class.oid = inhrelid
WHERE inhparent = 'chipseq_peaks'::regclass;

-- ============================================================================
-- 步骤 1: 重命名错误的分区 (chipseq_peaks_mouse -> chipseq_peaks_chimp)
-- ============================================================================
BEGIN;

-- 检查 chipseq_peaks_mouse 是否存在
DO $$
BEGIN
    IF EXISTS (
        SELECT 1 FROM pg_class
        WHERE relname = 'chipseq_peaks_mouse'
    ) THEN
        -- 重命名分区表
        ALTER TABLE chipseq_peaks_mouse RENAME TO chipseq_peaks_chimp;
        RAISE NOTICE '✓ Renamed chipseq_peaks_mouse to chipseq_peaks_chimp';
    ELSE
        RAISE NOTICE '⚠ chipseq_peaks_mouse not found, skipping rename';
    END IF;
END $$;

COMMIT;

-- ============================================================================
-- 步骤 2: 添加缺失的物种分区
-- ============================================================================
BEGIN;

-- Macaque (species_id = 3) - 猕猴
DO $$
BEGIN
    IF NOT EXISTS (
        SELECT 1 FROM pg_inherits
        JOIN pg_class ON pg_class.oid = inhrelid
        WHERE inhparent = 'chipseq_peaks'::regclass
          AND pg_get_expr(relpartbound, inhrelid) LIKE '%3%'
    ) THEN
        CREATE TABLE IF NOT EXISTS chipseq_peaks_macaque PARTITION OF chipseq_peaks
            FOR VALUES IN (3);
        RAISE NOTICE '✓ Created chipseq_peaks_macaque partition';
    ELSE
        RAISE NOTICE '⚠ Macaque partition already exists';
    END IF;
END $$;

-- Marmoset (species_id = 4) - 狨猴
DO $$
BEGIN
    IF NOT EXISTS (
        SELECT 1 FROM pg_inherits
        JOIN pg_class ON pg_class.oid = inhrelid
        WHERE inhparent = 'chipseq_peaks'::regclass
          AND pg_get_expr(relpartbound, inhrelid) LIKE '%4%'
    ) THEN
        CREATE TABLE IF NOT EXISTS chipseq_peaks_marmoset PARTITION OF chipseq_peaks
            FOR VALUES IN (4);
        RAISE NOTICE '✓ Created chipseq_peaks_marmoset partition';
    ELSE
        RAISE NOTICE '⚠ Marmoset partition already exists';
    END IF;
END $$;

COMMIT;

-- ============================================================================
-- 验证修复结果
-- ============================================================================
SELECT
    'Partition Verification' as check_type,
    inhrelid::regclass AS partition_name,
    pg_get_expr(relpartbound, inhrelid) AS partition_bound
FROM pg_inherits
JOIN pg_class ON pg_class.oid = inhrelid
WHERE inhparent = 'chipseq_peaks'::regclass
ORDER BY partition_name;

-- 检查各分区数据量
SELECT
    'Data Distribution' as check_type,
    tableoid::regclass AS partition_name,
    COUNT(*) AS row_count
FROM chipseq_peaks
GROUP BY tableoid
ORDER BY partition_name;

-- ============================================================================
-- 执行方式:
--   psql -d lncrna_production -f etl/migrations/004_fix_chipseq_partition_naming.sql
--
-- 注意事项:
--   1. 此迁移是幂等的，可安全重复执行
--   2. 重命名操作不会移动数据，仅更改表名
--   3. 执行前建议备份数据库
-- ============================================================================
