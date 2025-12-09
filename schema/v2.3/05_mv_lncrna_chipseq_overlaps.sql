-- ============================================================================
-- Human LncRNA Atlas - Materialized View for lncRNA-ChIP-seq Overlaps
-- Version: 2.3.2
-- Date: 2025-12-09
-- Purpose: Optimize chr1 and other large chromosome overlap queries
-- ============================================================================
--
-- BACKGROUND:
-- The lncRNA-ChIP-seq overlap query performs a spatial join between:
--   - regulations table (804,630 records)
--   - chipseq_peaks_human table (4,620,036 records)
-- This join is extremely slow for large chromosomes (chr1 estimated 500K-1M overlaps).
--
-- SOLUTION:
-- Pre-compute all overlaps into a materialized view with appropriate indexes.
-- This reduces query time from minutes to milliseconds for filtered queries.
--
-- REFRESH STRATEGY:
-- - Initial creation: ~30-60 minutes (one-time)
-- - Refresh: REFRESH MATERIALIZED VIEW CONCURRENTLY (non-blocking)
-- - Recommended: Weekly refresh via cron job, or after data imports
--
-- STORAGE ESTIMATE:
-- - Estimated rows: 10-50 million overlaps
-- - Estimated size: 5-20 GB (depending on actual overlap count)
-- ============================================================================

\echo '========================================='
\echo 'Creating Materialized View: mv_lncrna_chipseq_overlaps'
\echo 'WARNING: This may take 30-60 minutes for initial creation'
\echo '========================================='

-- ============================================================================
-- 1. DROP EXISTING VIEW IF RECREATING
-- ============================================================================
-- Uncomment the following line if you need to recreate the view
-- DROP MATERIALIZED VIEW IF EXISTS mv_lncrna_chipseq_overlaps CASCADE;

-- ============================================================================
-- 2. CREATE MATERIALIZED VIEW
-- ============================================================================
CREATE MATERIALIZED VIEW IF NOT EXISTS mv_lncrna_chipseq_overlaps AS
SELECT
    -- Unique identifier for the overlap
    CONCAT('reg_', r.regulation_id, '_peak_', p.peak_id) AS overlap_id,

    -- Regulation table fields
    r.regulation_id,
    r.species_id,
    r.lncrna_gene_id,
    r.target_gene_id,
    r.best_peak_chr AS chromosome,
    r.best_peak_start AS lncrna_binding_start,
    r.best_peak_end AS lncrna_binding_end,
    r.binding_affinity,

    -- ChIP-seq peak fields
    p.peak_id,
    p.experiment_id,
    p.peak_start,
    p.peak_end,
    p.fold_enrichment,
    p.qvalue,

    -- Experiment metadata (denormalized for query performance)
    e.mark_type_id,
    e.cell_type,
    e.tissue_type,
    e.is_active AS experiment_is_active,

    -- Mark type info (denormalized)
    m.mark_name,
    m.mark_category,

    -- Gene names (denormalized for display)
    lnc.gene_name AS lncrna_name,
    tgt.gene_name AS target_gene_name,

    -- Pre-computed overlap region
    GREATEST(r.best_peak_start, p.peak_start) AS overlap_start,
    LEAST(r.best_peak_end, p.peak_end) AS overlap_end,
    LEAST(r.best_peak_end, p.peak_end) - GREATEST(r.best_peak_start, p.peak_start) AS overlap_length

FROM regulations r
-- Join gene names
JOIN genes lnc ON r.lncrna_gene_id = lnc.gene_id
JOIN genes tgt ON r.target_gene_id = tgt.gene_id
-- Spatial join with ChIP-seq peaks (human partition for performance)
JOIN chipseq_peaks_human p ON
    r.best_peak_chr = p.chromosome AND
    r.best_peak_start < p.peak_end AND
    r.best_peak_end > p.peak_start AND
    r.species_id = p.species_id
-- Join experiment metadata
JOIN chipseq_experiments e ON p.experiment_id = e.experiment_id
-- Join mark type info
JOIN epigenetic_mark_types m ON e.mark_type_id = m.mark_type_id
WHERE
    r.species_id = 1  -- Human only for now
    AND e.is_active = TRUE
WITH DATA;

\echo 'Materialized view created successfully'

-- ============================================================================
-- 3. CREATE INDEXES FOR COMMON QUERY PATTERNS
-- ============================================================================

\echo 'Creating indexes...'

-- Unique index (required for CONCURRENTLY refresh)
CREATE UNIQUE INDEX IF NOT EXISTS idx_mv_overlap_unique
    ON mv_lncrna_chipseq_overlaps(regulation_id, peak_id);

-- Chromosome index (most common filter)
CREATE INDEX IF NOT EXISTS idx_mv_overlap_chr
    ON mv_lncrna_chipseq_overlaps(chromosome);

-- Chromosome + position for range queries
CREATE INDEX IF NOT EXISTS idx_mv_overlap_chr_pos
    ON mv_lncrna_chipseq_overlaps(chromosome, overlap_start, overlap_end);

-- Gene filters
CREATE INDEX IF NOT EXISTS idx_mv_overlap_lncrna
    ON mv_lncrna_chipseq_overlaps(lncrna_gene_id);
CREATE INDEX IF NOT EXISTS idx_mv_overlap_target
    ON mv_lncrna_chipseq_overlaps(target_gene_id);

-- Mark type filter (common use case)
CREATE INDEX IF NOT EXISTS idx_mv_overlap_mark
    ON mv_lncrna_chipseq_overlaps(mark_type_id);
CREATE INDEX IF NOT EXISTS idx_mv_overlap_mark_name
    ON mv_lncrna_chipseq_overlaps(mark_name);

-- Cell type filter
CREATE INDEX IF NOT EXISTS idx_mv_overlap_cell
    ON mv_lncrna_chipseq_overlaps(cell_type);

-- Binding affinity for filtering/sorting
CREATE INDEX IF NOT EXISTS idx_mv_overlap_ba
    ON mv_lncrna_chipseq_overlaps(binding_affinity DESC);

-- Overlap length for filtering/sorting
CREATE INDEX IF NOT EXISTS idx_mv_overlap_length
    ON mv_lncrna_chipseq_overlaps(overlap_length DESC);

-- Q-value filter
CREATE INDEX IF NOT EXISTS idx_mv_overlap_qvalue
    ON mv_lncrna_chipseq_overlaps(qvalue)
    WHERE qvalue IS NOT NULL;

-- Fold enrichment for sorting
CREATE INDEX IF NOT EXISTS idx_mv_overlap_fe
    ON mv_lncrna_chipseq_overlaps(fold_enrichment DESC NULLS LAST);

-- Composite index for common filter combinations
CREATE INDEX IF NOT EXISTS idx_mv_overlap_chr_mark
    ON mv_lncrna_chipseq_overlaps(chromosome, mark_name);
CREATE INDEX IF NOT EXISTS idx_mv_overlap_chr_cell
    ON mv_lncrna_chipseq_overlaps(chromosome, cell_type);
CREATE INDEX IF NOT EXISTS idx_mv_overlap_chr_ba
    ON mv_lncrna_chipseq_overlaps(chromosome, binding_affinity DESC);

\echo 'Indexes created successfully'

-- ============================================================================
-- 4. STATISTICS AND VERIFICATION
-- ============================================================================

-- Analyze for query optimizer
ANALYZE mv_lncrna_chipseq_overlaps;

-- Show row count and size
\echo ''
\echo 'Materialized View Statistics:'
SELECT
    'mv_lncrna_chipseq_overlaps' AS view_name,
    COUNT(*) AS total_rows,
    COUNT(DISTINCT chromosome) AS chromosomes,
    COUNT(DISTINCT lncrna_gene_id) AS unique_lncrnas,
    COUNT(DISTINCT target_gene_id) AS unique_targets,
    COUNT(DISTINCT mark_name) AS unique_marks,
    COUNT(DISTINCT cell_type) AS unique_cell_types
FROM mv_lncrna_chipseq_overlaps;

-- Show distribution by chromosome
\echo ''
\echo 'Distribution by Chromosome (Top 10):'
SELECT
    chromosome,
    COUNT(*) AS overlap_count,
    ROUND(COUNT(*) * 100.0 / SUM(COUNT(*)) OVER (), 2) AS percentage
FROM mv_lncrna_chipseq_overlaps
GROUP BY chromosome
ORDER BY overlap_count DESC
LIMIT 10;

-- Show storage size
\echo ''
\echo 'Storage Size:'
SELECT
    pg_size_pretty(pg_total_relation_size('mv_lncrna_chipseq_overlaps')) AS total_size,
    pg_size_pretty(pg_relation_size('mv_lncrna_chipseq_overlaps')) AS data_size,
    pg_size_pretty(pg_indexes_size('mv_lncrna_chipseq_overlaps')) AS index_size;

-- ============================================================================
-- 5. HELPER FUNCTION FOR REFRESH
-- ============================================================================

CREATE OR REPLACE FUNCTION refresh_lncrna_chipseq_overlaps(
    use_concurrently BOOLEAN DEFAULT TRUE
)
RETURNS TABLE (
    status TEXT,
    rows_before BIGINT,
    rows_after BIGINT,
    duration_seconds NUMERIC
) AS $$
DECLARE
    start_time TIMESTAMP;
    end_time TIMESTAMP;
    v_rows_before BIGINT;
    v_rows_after BIGINT;
BEGIN
    start_time := clock_timestamp();

    -- Get row count before refresh
    SELECT COUNT(*) INTO v_rows_before FROM mv_lncrna_chipseq_overlaps;

    -- Refresh the view
    IF use_concurrently THEN
        -- Non-blocking refresh (requires unique index)
        REFRESH MATERIALIZED VIEW CONCURRENTLY mv_lncrna_chipseq_overlaps;
    ELSE
        -- Blocking refresh (faster but locks the view)
        REFRESH MATERIALIZED VIEW mv_lncrna_chipseq_overlaps;
    END IF;

    -- Get row count after refresh
    SELECT COUNT(*) INTO v_rows_after FROM mv_lncrna_chipseq_overlaps;

    -- Update statistics
    ANALYZE mv_lncrna_chipseq_overlaps;

    end_time := clock_timestamp();

    RETURN QUERY SELECT
        'SUCCESS'::TEXT,
        v_rows_before,
        v_rows_after,
        ROUND(EXTRACT(EPOCH FROM (end_time - start_time))::NUMERIC, 2);
END;
$$ LANGUAGE plpgsql;

COMMENT ON FUNCTION refresh_lncrna_chipseq_overlaps(BOOLEAN) IS
'Refresh the lncRNA-ChIP-seq overlaps materialized view.
Parameters:
  - use_concurrently: If TRUE (default), uses CONCURRENTLY option for non-blocking refresh.
                      If FALSE, uses blocking refresh which is faster but locks the view.
Returns: status, rows_before, rows_after, duration_seconds';

-- ============================================================================
-- 6. VIEW STATUS CHECK FUNCTION
-- ============================================================================

CREATE OR REPLACE FUNCTION check_mv_lncrna_chipseq_overlaps_status()
RETURNS TABLE (
    view_name TEXT,
    is_populated BOOLEAN,
    row_count BIGINT,
    last_refresh TIMESTAMP WITH TIME ZONE,
    data_size TEXT,
    index_size TEXT
) AS $$
BEGIN
    RETURN QUERY
    SELECT
        'mv_lncrna_chipseq_overlaps'::TEXT,
        (SELECT relispopulated FROM pg_class WHERE relname = 'mv_lncrna_chipseq_overlaps'),
        (SELECT COUNT(*) FROM mv_lncrna_chipseq_overlaps),
        NULL::TIMESTAMP WITH TIME ZONE,  -- PostgreSQL doesn't track last refresh time natively
        pg_size_pretty(pg_relation_size('mv_lncrna_chipseq_overlaps')),
        pg_size_pretty(pg_indexes_size('mv_lncrna_chipseq_overlaps'));
END;
$$ LANGUAGE plpgsql;

COMMENT ON FUNCTION check_mv_lncrna_chipseq_overlaps_status() IS
'Check the status of the lncRNA-ChIP-seq overlaps materialized view';

-- ============================================================================
-- COMPLETION
-- ============================================================================

\echo ''
\echo '========================================='
\echo 'Materialized View Setup Complete!'
\echo ''
\echo 'Usage:'
\echo '  - Query: SELECT * FROM mv_lncrna_chipseq_overlaps WHERE chromosome = ''chr1'';'
\echo '  - Refresh: SELECT * FROM refresh_lncrna_chipseq_overlaps();'
\echo '  - Status: SELECT * FROM check_mv_lncrna_chipseq_overlaps_status();'
\echo ''
\echo 'For scheduled refresh, add to crontab:'
\echo '  0 3 * * 0 psql -d lncrna_atlas -c "SELECT refresh_lncrna_chipseq_overlaps();"'
\echo '========================================='
