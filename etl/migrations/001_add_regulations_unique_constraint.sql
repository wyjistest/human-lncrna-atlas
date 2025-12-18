-- Migration: 001_add_regulations_unique_constraint.sql
-- Description: Add unique constraint to regulations table for deduplication support
-- Date: 2025-12-02
--
-- ⚠️ DEPRECATED: 请使用以下迁移脚本替代：
--   - 存量数据去重: scripts/migrate_dedup_regulations.sql
--   - 仅更新索引: etl/migrations/002_fix_regulations_unique_null_safe.sql
--
-- 此脚本已过时，原因：
--   - 不支持 NULLS NOT DISTINCT（需 PG15+）
--   - NULL 值可能导致重复行
--
-- This migration adds a unique constraint on the key columns that define
-- a unique regulation record. This enables ON CONFLICT DO NOTHING in the
-- import scripts to prevent duplicate imports.
--
-- Usage:
--   psql -U amax -d lncrna_production -f 001_add_regulations_unique_constraint.sql
--
-- Rollback:
--   DROP INDEX IF EXISTS idx_regulations_unique_key;

-- Create unique index for deduplication
-- This index covers the combination of columns that uniquely identify a regulation
CREATE UNIQUE INDEX IF NOT EXISTS idx_regulations_unique_key
ON regulations (
    species_id,
    lncrna_gene_id,
    target_gene_id,
    lncrna_start,
    lncrna_end,
    dna_start,
    dna_end
);

-- Verify the index was created
DO $$
BEGIN
    IF EXISTS (
        SELECT 1 FROM pg_indexes
        WHERE indexname = 'idx_regulations_unique_key'
    ) THEN
        RAISE NOTICE 'Index idx_regulations_unique_key created successfully';
    ELSE
        RAISE EXCEPTION 'Failed to create index idx_regulations_unique_key';
    END IF;
END $$;

-- Show index info
SELECT
    indexname,
    indexdef
FROM pg_indexes
WHERE tablename = 'regulations'
  AND indexname = 'idx_regulations_unique_key';
