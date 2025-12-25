-- Migration: 003_regulations_best_peak_indexes
-- Description: Add best_peak location indexes for overlap/IGV queries
-- Created: 2025-12-25
-- Idempotent: Yes (uses CREATE INDEX IF NOT EXISTS)
--
-- Background:
-- - regulations has 800K+ rows.
-- - Several endpoints join/filter on regulations.best_peak_chr/start/end (not target_*):
--   - IGV track count queries
--   - ChIP-seq overlap fallback joins (when MV is unavailable)
--   - MV build/join driver (offline)
--
-- Problem:
-- - Core schema indexes cover target_chromosome/target_start/target_end but NOT best_peak_*.
-- - Without best_peak indexes, overlap queries can degrade into large scans on regulations.
--
-- Solution:
-- - Add composite B-tree indexes keyed by (species_id, best_peak_chr, best_peak_start/end).
-- - Use partial indexes to exclude rows without best_peak_chr (smaller/faster).
--
-- ⚠️ PRODUCTION WARNING: Index Creation Locking Behavior
-- ======================================================================
-- Standard CREATE INDEX acquires SHARE lock and blocks ALL writes during build.
-- For 800K+ rows this can still take noticeable time.
--
-- Safe production option:
-- - Run the CONCURRENTLY variants manually via psql (cannot run inside a transaction).
-- ======================================================================

-- Index 1: chr + start (supports conditions like best_peak_chr = ? AND best_peak_start < ?)
CREATE INDEX IF NOT EXISTS idx_regulations_best_peak_chr_start
ON regulations(species_id, best_peak_chr, best_peak_start)
INCLUDE (best_peak_end, binding_affinity)
WHERE best_peak_chr IS NOT NULL;

-- Index 2: chr + end (supports conditions like best_peak_chr = ? AND best_peak_end > ?)
CREATE INDEX IF NOT EXISTS idx_regulations_best_peak_chr_end
ON regulations(species_id, best_peak_chr, best_peak_end)
INCLUDE (best_peak_start, binding_affinity)
WHERE best_peak_chr IS NOT NULL;

ANALYZE regulations;

-- ======================================================================
-- PRODUCTION ALTERNATIVE: CONCURRENTLY Version (Manual Execution Required)
-- ======================================================================
-- psql -U user -d dbname <<'EOF'
-- CREATE INDEX CONCURRENTLY IF NOT EXISTS idx_regulations_best_peak_chr_start
--   ON regulations(species_id, best_peak_chr, best_peak_start)
--   INCLUDE (best_peak_end, binding_affinity)
--   WHERE best_peak_chr IS NOT NULL;
-- CREATE INDEX CONCURRENTLY IF NOT EXISTS idx_regulations_best_peak_chr_end
--   ON regulations(species_id, best_peak_chr, best_peak_end)
--   INCLUDE (best_peak_start, binding_affinity)
--   WHERE best_peak_chr IS NOT NULL;
-- ANALYZE regulations;
-- EOF
