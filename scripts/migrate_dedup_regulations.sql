-- ============================================================================
-- 去重迁移脚本：为存量数据库创建 regulations 唯一索引
-- ============================================================================
-- 用途：在已存在重复数据的数据库上安全创建唯一索引
--
-- 要求：PostgreSQL 15+ (使用 NULLS NOT DISTINCT 特性)
--
-- 运行方式：
--   psql -U amax -d lncrna_production -f scripts/migrate_dedup_regulations.sql
--
-- 注意事项：
--   1. 请先备份数据库
--   2. 建议在低峰期执行（会锁表）
--   3. 执行时间取决于数据量（80万条约需 1-2 分钟）
--
-- 修复历史:
--   2025-12-13: 使用 keep_mapping 表替代重复 JOIN，确保唯一映射
--   2025-12-18: 添加 NULLS NOT DISTINCT 确保 NULL 值也参与去重
-- ============================================================================

BEGIN;

-- Step 0: 检查 PostgreSQL 版本（需要 >= 15）
DO $$
DECLARE
    pg_version integer;
BEGIN
    SELECT current_setting('server_version_num')::integer INTO pg_version;
    IF pg_version < 150000 THEN
        RAISE EXCEPTION 'PostgreSQL 15+ required for NULLS NOT DISTINCT. Current version: %',
                        current_setting('server_version');
    ELSE
        RAISE NOTICE 'PostgreSQL version check passed: %', current_setting('server_version');
    END IF;
END $$;

-- Step 1: 创建临时表记录保留的记录和唯一键映射
-- 包含唯一键列以便后续精确匹配
CREATE TEMP TABLE keep_mapping AS
SELECT
    MIN(regulation_id) as keep_id,
    species_id,
    lncrna_gene_id,
    target_gene_id,
    lncrna_start,
    lncrna_end,
    dna_start,
    dna_end
FROM regulations
GROUP BY species_id, lncrna_gene_id, target_gene_id,
         lncrna_start, lncrna_end, dna_start, dna_end;

-- 创建索引加速后续查询
CREATE INDEX idx_keep_mapping_key ON keep_mapping (
    species_id, lncrna_gene_id, target_gene_id,
    lncrna_start, lncrna_end, dna_start, dna_end
);

-- Step 2: 找出要删除的记录（重复组中非最小 ID 的记录）
CREATE TEMP TABLE delete_regulations AS
SELECT r.regulation_id
FROM regulations r
WHERE r.regulation_id NOT IN (SELECT keep_id FROM keep_mapping);

-- Step 3: 为保留的 regulation 但缺少 sequences 行的记录创建空行
-- 这样后续 UPDATE 才能将删除记录的序列迁移过去
INSERT INTO sequences (regulation_id, lncrna_sequence, dna_sequence)
SELECT km.keep_id, NULL, NULL
FROM keep_mapping km
WHERE NOT EXISTS (
    SELECT 1 FROM sequences s WHERE s.regulation_id = km.keep_id
)
AND EXISTS (
    -- 只有当删除组中有序列数据时才创建
    SELECT 1
    FROM regulations r_del
    JOIN sequences s_del ON r_del.regulation_id = s_del.regulation_id
    WHERE r_del.regulation_id IN (SELECT regulation_id FROM delete_regulations)
      AND r_del.species_id IS NOT DISTINCT FROM km.species_id
      AND r_del.lncrna_gene_id IS NOT DISTINCT FROM km.lncrna_gene_id
      AND r_del.target_gene_id IS NOT DISTINCT FROM km.target_gene_id
      AND r_del.lncrna_start IS NOT DISTINCT FROM km.lncrna_start
      AND r_del.lncrna_end IS NOT DISTINCT FROM km.lncrna_end
      AND r_del.dna_start IS NOT DISTINCT FROM km.dna_start
      AND r_del.dna_end IS NOT DISTINCT FROM km.dna_end
);

-- Step 4: 迁移 sequences 数据
-- 使用 keep_mapping 确保唯一映射，避免多行 UPDATE 非确定性
-- 使用 NULLIF 处理空字符串（'' 视为缺失值）
UPDATE sequences s_keep
SET
    lncrna_sequence = COALESCE(
        NULLIF(s_keep.lncrna_sequence, ''),
        (
            SELECT NULLIF(s_del.lncrna_sequence, '')
            FROM sequences s_del
            JOIN regulations r_del ON s_del.regulation_id = r_del.regulation_id
            WHERE r_del.regulation_id IN (SELECT regulation_id FROM delete_regulations)
              AND r_del.species_id IS NOT DISTINCT FROM km.species_id
              AND r_del.lncrna_gene_id IS NOT DISTINCT FROM km.lncrna_gene_id
              AND r_del.target_gene_id IS NOT DISTINCT FROM km.target_gene_id
              AND r_del.lncrna_start IS NOT DISTINCT FROM km.lncrna_start
              AND r_del.lncrna_end IS NOT DISTINCT FROM km.lncrna_end
              AND r_del.dna_start IS NOT DISTINCT FROM km.dna_start
              AND r_del.dna_end IS NOT DISTINCT FROM km.dna_end
              AND NULLIF(s_del.lncrna_sequence, '') IS NOT NULL
            ORDER BY r_del.regulation_id  -- 确定性选择最小 ID 的序列
            LIMIT 1
        )
    ),
    dna_sequence = COALESCE(
        NULLIF(s_keep.dna_sequence, ''),
        (
            SELECT NULLIF(s_del.dna_sequence, '')
            FROM sequences s_del
            JOIN regulations r_del ON s_del.regulation_id = r_del.regulation_id
            WHERE r_del.regulation_id IN (SELECT regulation_id FROM delete_regulations)
              AND r_del.species_id IS NOT DISTINCT FROM km.species_id
              AND r_del.lncrna_gene_id IS NOT DISTINCT FROM km.lncrna_gene_id
              AND r_del.target_gene_id IS NOT DISTINCT FROM km.target_gene_id
              AND r_del.lncrna_start IS NOT DISTINCT FROM km.lncrna_start
              AND r_del.lncrna_end IS NOT DISTINCT FROM km.lncrna_end
              AND r_del.dna_start IS NOT DISTINCT FROM km.dna_start
              AND r_del.dna_end IS NOT DISTINCT FROM km.dna_end
              AND NULLIF(s_del.dna_sequence, '') IS NOT NULL
            ORDER BY r_del.regulation_id
            LIMIT 1
        )
    )
FROM keep_mapping km
WHERE s_keep.regulation_id = km.keep_id;

-- Step 5: 删除重复记录的 sequences
DELETE FROM sequences
WHERE regulation_id IN (SELECT regulation_id FROM delete_regulations);

-- Step 6: 删除重复的 regulations 记录
DELETE FROM regulations
WHERE regulation_id IN (SELECT regulation_id FROM delete_regulations);

-- Step 7: 报告删除的行数
DO $$
DECLARE
    deleted_count INTEGER;
BEGIN
    SELECT COUNT(*) INTO deleted_count FROM delete_regulations;
    RAISE NOTICE 'Deleted % duplicate regulation records', deleted_count;
END $$;

-- Step 8: 创建 NULL 安全唯一索引
-- NULLS NOT DISTINCT 确保 NULL 值也参与去重（PG15+ 特性）
DROP INDEX IF EXISTS idx_regulations_unique_key;
CREATE UNIQUE INDEX idx_regulations_unique_key
ON regulations (species_id, lncrna_gene_id, target_gene_id, lncrna_start, lncrna_end, dna_start, dna_end)
NULLS NOT DISTINCT;

-- Step 9: 清理临时表
DROP TABLE IF EXISTS keep_mapping;
DROP TABLE IF EXISTS delete_regulations;

COMMIT;

-- 验证
SELECT 'Migration completed. Unique index created.' AS status;
SELECT COUNT(*) AS total_regulations FROM regulations;
