-- ============================================================================
-- Human LncRNA Atlas - Analysis Summary (High Affinity) Materialized Views
-- Version: 2.3.4
-- Date: 2026-01-01
-- Purpose: Speed up /analysis/summary cache-miss (High Affinity section)
-- Depends: schema/v2.3/01_core.sql (regulations/genes)
-- ============================================================================

\echo '========================================='
\echo 'Creating Materialized Views: analysis summary (BA >= 100)'
\echo '========================================='

-- ============================================================================
-- 1) High Affinity overall stats (single row)
-- ============================================================================

-- Keep semantics aligned with app/routers/analysis.py:
-- - BA threshold is fixed at 100
-- - No species filter (aggregates across all species)
CREATE MATERIALIZED VIEW IF NOT EXISTS mv_analysis_high_affinity_stats_ba100 AS
SELECT
    1 AS id,
    COUNT(*) AS total_regulations,
    COUNT(DISTINCT lncrna_gene_id) AS unique_lncrnas,
    COUNT(DISTINCT target_gene_id) AS unique_targets,
    AVG(binding_affinity) AS avg_ba,
    MAX(binding_affinity) AS max_ba
FROM regulations
WHERE binding_affinity >= 100
WITH DATA;

-- Unique index is required for REFRESH MATERIALIZED VIEW CONCURRENTLY.
CREATE UNIQUE INDEX IF NOT EXISTS idx_mv_analysis_high_affinity_stats_ba100_unique
    ON mv_analysis_high_affinity_stats_ba100(id);

ANALYZE mv_analysis_high_affinity_stats_ba100;

-- ============================================================================
-- 2) Top lncRNAs (by distinct target count, BA >= 100)
-- ============================================================================

-- Keep semantics aligned with app/routers/analysis.py:
-- - Grouped by genes.gene_name (may aggregate same names across species, consistent with current API)
-- - Stable tie-break uses lncrna_name ASC after the existing ORDER BY fields
CREATE MATERIALIZED VIEW IF NOT EXISTS mv_analysis_top_lncrnas_ba100 AS
WITH per_lncrna AS (
    SELECT
        lnc.gene_name AS lncrna_name,
        COUNT(DISTINCT r.target_gene_id) AS target_count,
        AVG(r.binding_affinity) AS avg_ba
    FROM regulations r
    JOIN genes lnc ON r.lncrna_gene_id = lnc.gene_id
    WHERE r.binding_affinity >= 100
    GROUP BY lnc.gene_name
),
ranked AS (
    SELECT
        ROW_NUMBER() OVER (
            ORDER BY target_count DESC, avg_ba DESC, lncrna_name ASC
        ) AS row_num,
        lncrna_name,
        target_count,
        avg_ba
    FROM per_lncrna
)
SELECT
    row_num,
    lncrna_name,
    target_count,
    avg_ba
FROM ranked
WHERE row_num <= 20
WITH DATA;

-- Unique index is required for REFRESH MATERIALIZED VIEW CONCURRENTLY.
CREATE UNIQUE INDEX IF NOT EXISTS idx_mv_analysis_top_lncrnas_ba100_unique
    ON mv_analysis_top_lncrnas_ba100(row_num);

ANALYZE mv_analysis_top_lncrnas_ba100;

-- ============================================================================
-- 3) Quick sanity output
-- ============================================================================

\echo ''
\echo 'Materialized View Statistics:'
SELECT
    'mv_analysis_high_affinity_stats_ba100' AS view_name,
    COUNT(*) AS total_rows
FROM mv_analysis_high_affinity_stats_ba100;

SELECT
    'mv_analysis_top_lncrnas_ba100' AS view_name,
    COUNT(*) AS total_rows
FROM mv_analysis_top_lncrnas_ba100;

\echo ''
\echo '========================================='
\echo 'Analysis Summary MVs Setup Complete!'
\echo ''
\echo 'Usage:'
\echo '  - Refresh:'
\echo '      REFRESH MATERIALIZED VIEW CONCURRENTLY mv_analysis_high_affinity_stats_ba100;'
\echo '      REFRESH MATERIALIZED VIEW CONCURRENTLY mv_analysis_top_lncrnas_ba100;'
\echo '========================================='
