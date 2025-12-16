-- Migration: 001_pg_trgm_indexes
-- Description: Add pg_trgm GIN indexes for ILIKE pattern matching optimization
-- Created: 2025-12-16
-- Idempotent: Yes (uses CREATE ... IF NOT EXISTS)
--
-- Purpose: Optimize ILIKE '%pattern%' fuzzy search performance
-- Problem: PostgreSQL uses sequential scan for ILIKE with wildcards on both sides
-- Solution: Use pg_trgm extension's trigram indexes for indexed pattern matching
--
-- Affected queries:
--   1. traits.trait_name - Disease name search (visualization.py, export.py)
--   2. chipseq_experiments.cell_type - Cell type search (chipseq_experiments.py)

-- ============================================================================
-- Step 1: Enable pg_trgm extension
-- ============================================================================
CREATE EXTENSION IF NOT EXISTS pg_trgm;

-- ============================================================================
-- Step 2: Create GIN indexes (idempotent)
-- ============================================================================

-- Index 1: traits.trait_name
-- Usage: WHERE trait_name ILIKE '%diabetes%'
CREATE INDEX IF NOT EXISTS idx_traits_trait_name_trgm
ON traits USING GIN (trait_name gin_trgm_ops);

-- Index 2: chipseq_experiments.cell_type
-- Usage: WHERE cell_type ILIKE '%liver%'
CREATE INDEX IF NOT EXISTS idx_chipseq_experiments_cell_type_trgm
ON chipseq_experiments USING GIN (cell_type gin_trgm_ops);

-- ============================================================================
-- Step 3: Update statistics
-- ============================================================================
ANALYZE traits;
ANALYZE chipseq_experiments;
