-- ============================================================================
-- Human LncRNA Atlas - Epigenetic Summary Materialized View (BA >= 100)
-- Version: 2.3.3
-- Date: 2026-01-01
-- Purpose: Speed up /analysis/summary (Epigenetic) by pre-aggregating counts
-- Depends: schema/v2.3/05_mv_lncrna_chipseq_overlaps.sql
-- ============================================================================

\echo '========================================='
\echo 'Creating Materialized View: mv_lncrna_chipseq_overlaps_epigenetic_summary_ba100'
\echo 'Depends on: mv_lncrna_chipseq_overlaps'
\echo '========================================='

-- High-confidence overlaps only (aligns with /analysis/summary default: BA >= 100).
-- Output cardinality is small (mark_name x cell_type x category), so reads are fast.
CREATE MATERIALIZED VIEW IF NOT EXISTS mv_lncrna_chipseq_overlaps_epigenetic_summary_ba100 AS
SELECT
    o.mark_name,
    o.mark_category,
    o.cell_type,
    COUNT(*) AS overlap_count
FROM mv_lncrna_chipseq_overlaps o
WHERE o.binding_affinity >= 100
GROUP BY o.mark_name, o.mark_category, o.cell_type
WITH DATA;

\echo 'Creating indexes...'

-- Unique index is required for REFRESH MATERIALIZED VIEW CONCURRENTLY.
CREATE UNIQUE INDEX IF NOT EXISTS idx_mv_overlap_epi_summary_ba100_unique
    ON mv_lncrna_chipseq_overlaps_epigenetic_summary_ba100(mark_name, mark_category, cell_type);

\echo 'Analyzing...'
ANALYZE mv_lncrna_chipseq_overlaps_epigenetic_summary_ba100;

\echo ''
\echo 'Materialized View Statistics:'
SELECT
    'mv_lncrna_chipseq_overlaps_epigenetic_summary_ba100' AS view_name,
    COUNT(*) AS total_rows,
    COUNT(DISTINCT mark_name) AS unique_marks,
    COUNT(DISTINCT cell_type) AS unique_cell_types
FROM mv_lncrna_chipseq_overlaps_epigenetic_summary_ba100;

\echo ''
\echo '========================================='
\echo 'Epigenetic Summary MV Setup Complete!'
\echo ''
\echo 'Usage:'
\echo '  - Query: SELECT * FROM mv_lncrna_chipseq_overlaps_epigenetic_summary_ba100;'
\echo '  - Refresh (after base MV): REFRESH MATERIALIZED VIEW CONCURRENTLY mv_lncrna_chipseq_overlaps_epigenetic_summary_ba100;'
\echo '========================================='
