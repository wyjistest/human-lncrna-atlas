-- ============================================================================
-- Migration: Fix regulations unique constraint for NULL safety
-- ============================================================================
-- Date: 2025-12-18
-- Issue: PostgreSQL unique indexes don't consider NULL = NULL, so rows with
--        NULL in lncrna_start/lncrna_end/dna_start/dna_end can be duplicated.
--
-- Solution: Use NULLS NOT DISTINCT (PostgreSQL 15+) to treat NULL as equal
--
-- Requires: PostgreSQL 15 or later
--
-- Usage:
--   psql -U amax -d lncrna_production -f 002_fix_regulations_unique_null_safe.sql
--
-- Rollback:
--   DROP INDEX IF EXISTS idx_regulations_unique_key;
--   CREATE UNIQUE INDEX idx_regulations_unique_key
--   ON regulations (species_id, lncrna_gene_id, target_gene_id,
--                   lncrna_start, lncrna_end, dna_start, dna_end);
-- ============================================================================

BEGIN;

-- Step 1: Check PostgreSQL version (must be >= 15)
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

-- Step 2: Drop existing index (if exists)
DROP INDEX IF EXISTS idx_regulations_unique_key;
DROP INDEX IF EXISTS idx_regulations_unique_key_nullsafe;

-- Step 3: Create NULL-safe unique index using NULLS NOT DISTINCT
-- This treats NULL values as equal for uniqueness purposes
CREATE UNIQUE INDEX idx_regulations_unique_key
ON regulations (
    species_id,
    lncrna_gene_id,
    target_gene_id,
    lncrna_start,
    lncrna_end,
    dna_start,
    dna_end
) NULLS NOT DISTINCT;

-- Step 4: Verify the index was created with correct properties
DO $$
DECLARE
    idx_nulls_distinct boolean;
BEGIN
    -- Check index exists
    IF NOT EXISTS (
        SELECT 1 FROM pg_indexes
        WHERE indexname = 'idx_regulations_unique_key'
    ) THEN
        RAISE EXCEPTION '❌ Failed to create index idx_regulations_unique_key';
    END IF;

    -- Check NULLS NOT DISTINCT property (indnullsnotdistinct column in pg_index)
    SELECT NOT indnullsnotdistinct INTO idx_nulls_distinct
    FROM pg_index
    WHERE indexrelid = 'idx_regulations_unique_key'::regclass;

    IF idx_nulls_distinct THEN
        RAISE EXCEPTION '❌ Index created but NULLS NOT DISTINCT not applied';
    END IF;

    RAISE NOTICE '✅ NULL-safe unique index created successfully with NULLS NOT DISTINCT';
END $$;

-- Step 5: Display index info for verification
DO $$
DECLARE
    idx_def text;
BEGIN
    SELECT indexdef INTO idx_def
    FROM pg_indexes
    WHERE indexname = 'idx_regulations_unique_key';
    RAISE NOTICE 'Index definition: %', idx_def;
END $$;

COMMIT;

-- ============================================================================
-- Notes on ETL compatibility
-- ============================================================================
-- The ETL import_regulations.py has been updated to use IS NOT DISTINCT FROM
-- in WHERE NOT EXISTS and JOIN clauses for NULL-safe comparisons.
--
-- This ensures:
-- 1. Database layer: NULLS NOT DISTINCT prevents duplicate rows with NULL
-- 2. ETL layer: IS NOT DISTINCT FROM correctly detects existing NULL rows
--
-- Both layers work together for complete NULL-safe deduplication.
-- ============================================================================
