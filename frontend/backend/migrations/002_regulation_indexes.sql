-- Migration: 002_regulation_indexes
-- Description: Add indexes for regulations table query optimization
-- Created: 2025-12-16
-- Idempotent: Yes (uses CREATE INDEX IF NOT EXISTS)
--
-- Purpose: Optimize regulation-related query performance
-- Problem: regulations table has 800K+ rows, frequent JOINs and ORDER BY cause full table scans
-- Solution: Add covering indexes for common query patterns
--
-- ⚠️ PRODUCTION WARNING: Index Creation Locking Behavior
-- ============================================================================
-- Standard CREATE INDEX acquires SHARE lock and blocks ALL writes (INSERT/UPDATE/DELETE)
-- during index building. For large tables (800K+ rows), this can take minutes to hours.
--
-- SAFE OPTIONS FOR PRODUCTION:
-- 1. Use CONCURRENTLY (requires manual execution outside transaction):
--    psql -U user -d dbname -c "CREATE INDEX CONCURRENTLY IF NOT EXISTS idx_name ON table(col);"
-- 2. Run during maintenance window when writes are stopped
-- 3. Create indexes BEFORE importing data (no blocking on empty tables)
--
-- CURRENT IMPLEMENTATION: Standard CREATE INDEX (for initial setup/dev)
-- For production with existing data, manually run CONCURRENTLY version (see below)
-- ============================================================================

-- ============================================================================
-- Step 1: Single column indexes (JOIN optimization)
-- ============================================================================

-- Index 1: lncrna_gene_id
-- Usage: JOIN genes ON regulations.lncrna_gene_id = genes.gene_id
CREATE INDEX IF NOT EXISTS idx_regulations_lncrna_gene_id
ON regulations(lncrna_gene_id);

-- Index 2: target_gene_id
-- Usage: JOIN genes ON regulations.target_gene_id = genes.gene_id
CREATE INDEX IF NOT EXISTS idx_regulations_target_gene_id
ON regulations(target_gene_id);

-- ============================================================================
-- Step 2: Composite indexes (filter + sort optimization)
-- ============================================================================

-- Index 3: (species_id, binding_affinity DESC)
-- Usage: WHERE species_id IN (...) ORDER BY binding_affinity DESC
CREATE INDEX IF NOT EXISTS idx_regulations_species_ba
ON regulations(species_id, binding_affinity DESC);

-- Index 4: (species_id, target_chromosome)
-- Usage: ChIP-seq overlap queries with species and chromosome filters
CREATE INDEX IF NOT EXISTS idx_regulations_species_chr
ON regulations(species_id, target_chromosome);

-- ============================================================================
-- Step 3: Update statistics
-- ============================================================================
ANALYZE regulations;

-- ============================================================================
-- PRODUCTION ALTERNATIVE: CONCURRENTLY Version (Manual Execution Required)
-- ============================================================================
-- Copy and run these commands via psql when the database has existing data:
--
-- psql -U user -d dbname <<'EOF'
-- CREATE INDEX CONCURRENTLY IF NOT EXISTS idx_regulations_lncrna_gene_id ON regulations(lncrna_gene_id);
-- CREATE INDEX CONCURRENTLY IF NOT EXISTS idx_regulations_target_gene_id ON regulations(target_gene_id);
-- CREATE INDEX CONCURRENTLY IF NOT EXISTS idx_regulations_species_ba ON regulations(species_id, binding_affinity DESC);
-- CREATE INDEX CONCURRENTLY IF NOT EXISTS idx_regulations_species_chr ON regulations(species_id, target_chromosome);
-- ANALYZE regulations;
-- EOF
--
-- Notes:
-- - CONCURRENTLY cannot be used in transactions (run each statement separately)
-- - If index build fails, manually drop the INVALID index before retrying
-- - Monitor progress: SELECT * FROM pg_stat_progress_create_index;
