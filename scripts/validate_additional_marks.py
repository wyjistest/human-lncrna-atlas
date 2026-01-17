#!/usr/bin/env python3
"""
Validate H3K36me3 and H3K9me3 data for all cell types

This script performs comprehensive data validation for ChIP-seq epigenetic marks data,
checking coverage matrix, data quality, and consistency across cell types.

Usage:
    python3 scripts/validate_additional_marks.py
"""
import psycopg2
import sys
from typing import Dict, List, Tuple, Any
from collections import defaultdict

# Configuration - Use environment variables with fallbacks
import os

DB_CONFIG = {
    "host": os.getenv("DB_HOST", "localhost"),
    "port": os.getenv("DB_PORT", "5432"),
    "database": os.getenv("DB_NAME", "lncrna_production"),
    "user": os.getenv("DB_USER", "amax"),
    "password": os.getenv("DB_PASSWORD", "")
}

# Expected cell types and marks
EXPECTED_CELL_TYPES = ["K562", "HepG2", "GM12878", "H1-hESC"]
EXPECTED_MARKS = ["H3K27me3", "H3K4me3", "H3K27ac", "H3K4me1", "H3K36me3", "H3K9me3"]

# Minimum expected peaks per experiment (for quality check)
MIN_PEAKS_THRESHOLD = 100
MAX_PEAKS_THRESHOLD = 500000


def connect_db():
    """Create database connection"""
    try:
        conn = psycopg2.connect(**DB_CONFIG)
        return conn
    except Exception as e:
        print(f"[ERROR] Database connection failed: {e}")
        sys.exit(1)


def print_header(title: str):
    """Print formatted section header"""
    print("\n" + "=" * 60)
    print(f"  {title}")
    print("=" * 60)


def print_subheader(title: str):
    """Print formatted subsection header"""
    print(f"\n--- {title} ---")


def check_coverage_matrix(cur) -> Dict[str, Dict[str, int]]:
    """
    Check coverage matrix for all cell types and marks

    Returns:
        Dict mapping cell_type -> mark_name -> peak_count
    """
    print_header("Coverage Matrix")

    cur.execute("""
        SELECT
            e.cell_type,
            m.mark_name,
            COUNT(*) as peaks,
            COUNT(DISTINCT e.experiment_id) as experiments
        FROM chipseq_experiments e
        JOIN chipseq_peaks p ON e.experiment_id = p.experiment_id
        JOIN epigenetic_mark_types m ON e.mark_type_id = m.mark_type_id
        WHERE e.cell_type IN ('K562', 'HepG2', 'GM12878', 'H1-hESC')
        AND e.is_active = TRUE
        GROUP BY e.cell_type, m.mark_name
        ORDER BY e.cell_type, m.mark_name
    """)

    results = cur.fetchall()
    coverage = defaultdict(dict)

    # Print results in table format
    print(f"\n{'Cell Type':<12} {'Mark':<12} {'Experiments':>12} {'Peaks':>10}")
    print("-" * 50)

    for row in results:
        cell_type, mark_name, peaks, experiments = row
        coverage[cell_type][mark_name] = peaks
        print(f"{cell_type:<12} {mark_name:<12} {experiments:>12} {peaks:>10,}")

    # Print coverage summary matrix
    print_subheader("Coverage Matrix Summary")

    # Header row
    print(f"\n{'Cell Type':<12}", end="")
    for mark in EXPECTED_MARKS:
        print(f"{mark:>12}", end="")
    print()
    print("-" * (12 + 12 * len(EXPECTED_MARKS)))

    # Data rows
    for cell_type in EXPECTED_CELL_TYPES:
        print(f"{cell_type:<12}", end="")
        for mark in EXPECTED_MARKS:
            count = coverage.get(cell_type, {}).get(mark, 0)
            if count > 0:
                print(f"{count:>12,}", end="")
            else:
                print(f"{'---':>12}", end="")
        print()

    return dict(coverage)


def check_data_quality(cur) -> List[Dict[str, Any]]:
    """
    Check data quality metrics for each experiment
    """
    print_header("Data Quality Check")

    cur.execute("""
        SELECT
            e.experiment_id,
            e.experiment_name,
            e.cell_type,
            m.mark_name,
            COUNT(p.peak_id) as peak_count,
            AVG(p.fold_enrichment) as avg_fold_enrichment,
            MIN(p.fold_enrichment) as min_fold_enrichment,
            MAX(p.fold_enrichment) as max_fold_enrichment,
            AVG(p.qvalue) as avg_qvalue,
            MIN(p.qvalue) as min_qvalue,
            AVG(p.peak_width) as avg_peak_width
        FROM chipseq_experiments e
        JOIN epigenetic_mark_types m ON e.mark_type_id = m.mark_type_id
        LEFT JOIN chipseq_peaks p ON e.experiment_id = p.experiment_id
        WHERE e.cell_type IN ('K562', 'HepG2', 'GM12878', 'H1-hESC')
        AND e.is_active = TRUE
        GROUP BY e.experiment_id, e.experiment_name, e.cell_type, m.mark_name
        ORDER BY e.cell_type, m.mark_name
    """)

    results = cur.fetchall()
    quality_issues = []

    print(f"\n{'Experiment':<40} {'Cell':<10} {'Mark':<10} {'Peaks':>8} {'AvgFE':>8} {'AvgQ':>10}")
    print("-" * 96)

    for row in results:
        exp_id, exp_name, cell_type, mark_name, peak_count, avg_fe, min_fe, max_fe, avg_q, min_q, avg_width = row

        # Truncate experiment name for display
        display_name = exp_name[:38] + ".." if len(exp_name) > 40 else exp_name

        # Format values
        avg_fe_str = f"{avg_fe:.2f}" if avg_fe else "N/A"
        avg_q_str = f"{avg_q:.2e}" if avg_q else "N/A"

        print(f"{display_name:<40} {cell_type:<10} {mark_name:<10} {peak_count or 0:>8,} {avg_fe_str:>8} {avg_q_str:>10}")

        # Check for quality issues
        issues = []
        if peak_count is None or peak_count == 0:
            issues.append("No peaks")
        elif peak_count < MIN_PEAKS_THRESHOLD:
            issues.append(f"Low peak count ({peak_count} < {MIN_PEAKS_THRESHOLD})")
        elif peak_count > MAX_PEAKS_THRESHOLD:
            issues.append(f"High peak count ({peak_count} > {MAX_PEAKS_THRESHOLD})")

        if avg_fe and avg_fe < 2.0:
            issues.append(f"Low avg fold enrichment ({avg_fe:.2f})")

        if issues:
            quality_issues.append({
                "experiment_id": exp_id,
                "experiment_name": exp_name,
                "cell_type": cell_type,
                "mark_name": mark_name,
                "issues": issues
            })

    # Print quality issues summary
    if quality_issues:
        print_subheader("Quality Issues Found")
        for issue in quality_issues:
            print(f"  [WARN] {issue['cell_type']}/{issue['mark_name']}: {', '.join(issue['issues'])}")
    else:
        print("\n[OK] No quality issues detected")

    return quality_issues


def check_missing_combinations(cur, coverage: Dict[str, Dict[str, int]]) -> List[Tuple[str, str]]:
    """
    Check for missing cell type / mark combinations
    """
    print_header("Missing Data Check")

    missing = []

    for cell_type in EXPECTED_CELL_TYPES:
        for mark in EXPECTED_MARKS:
            if mark not in coverage.get(cell_type, {}):
                missing.append((cell_type, mark))

    if missing:
        print("\n[WARN] Missing combinations:")
        for cell_type, mark in missing:
            print(f"  - {cell_type} / {mark}")
    else:
        print("\n[OK] All expected cell type / mark combinations are present")

    return missing


def check_experiment_metadata(cur):
    """
    Check experiment metadata completeness
    """
    print_header("Experiment Metadata Check")

    cur.execute("""
        SELECT
            e.experiment_id,
            e.experiment_name,
            e.cell_type,
            m.mark_name,
            e.source_database,
            e.source_accession,
            e.reference_genome,
            e.created_at
        FROM chipseq_experiments e
        JOIN epigenetic_mark_types m ON e.mark_type_id = m.mark_type_id
        WHERE e.cell_type IN ('K562', 'HepG2', 'GM12878', 'H1-hESC')
        AND e.is_active = TRUE
        ORDER BY e.cell_type, m.mark_name, e.created_at DESC
    """)

    results = cur.fetchall()

    print(f"\n{'Cell Type':<12} {'Mark':<12} {'Source':<10} {'Genome':<10} {'Created':<20}")
    print("-" * 74)

    for row in results:
        exp_id, exp_name, cell_type, mark_name, source, source_accession, genome, created = row
        source_str = source or "N/A"
        genome_str = genome or "N/A"
        created_str = created.strftime("%Y-%m-%d %H:%M") if created else "N/A"
        print(f"{cell_type:<12} {mark_name:<12} {source_str:<10} {genome_str:<10} {created_str:<20}")


def check_peak_distribution(cur):
    """
    Check peak distribution across chromosomes
    """
    print_header("Peak Distribution by Chromosome")

    cur.execute("""
        SELECT
            p.chromosome,
            COUNT(*) as peak_count
        FROM chipseq_peaks p
        JOIN chipseq_experiments e ON p.experiment_id = e.experiment_id
        WHERE e.cell_type IN ('K562', 'HepG2', 'GM12878', 'H1-hESC')
        AND e.is_active = TRUE
        GROUP BY p.chromosome
        ORDER BY
            CASE
                WHEN p.chromosome ~ '^chr[0-9]+$' THEN CAST(SUBSTRING(p.chromosome FROM 4) AS INTEGER)
                WHEN p.chromosome = 'chrX' THEN 23
                WHEN p.chromosome = 'chrY' THEN 24
                WHEN p.chromosome = 'chrM' THEN 25
                ELSE 26
            END
    """)

    results = cur.fetchall()
    total_peaks = sum(row[1] for row in results)

    print(f"\n{'Chromosome':<12} {'Peaks':>12} {'Percentage':>12}")
    print("-" * 38)

    for row in results:
        chrom, count = row
        pct = (count / total_peaks * 100) if total_peaks > 0 else 0
        print(f"{chrom:<12} {count:>12,} {pct:>11.2f}%")

    print("-" * 38)
    print(f"{'Total':<12} {total_peaks:>12,} {100.0:>11.2f}%")


def check_global_stats(cur):
    """
    Check global statistics
    """
    print_header("Global Statistics")

    cur.execute("""
        SELECT
            COUNT(DISTINCT e.experiment_id) as total_experiments,
            COUNT(DISTINCT e.cell_type) as cell_types,
            COUNT(DISTINCT m.mark_name) as mark_types,
            COUNT(p.peak_id) as total_peaks
        FROM chipseq_experiments e
        JOIN epigenetic_mark_types m ON e.mark_type_id = m.mark_type_id
        LEFT JOIN chipseq_peaks p ON e.experiment_id = p.experiment_id
        WHERE e.cell_type IN ('K562', 'HepG2', 'GM12878', 'H1-hESC')
        AND e.is_active = TRUE
    """)

    row = cur.fetchone()
    total_exp, cell_types, mark_types, total_peaks = row

    print(f"\n  Total Experiments: {total_exp:,}")
    print(f"  Cell Types:        {cell_types}")
    print(f"  Mark Types:        {mark_types}")
    print(f"  Total Peaks:       {total_peaks:,}")


def run_validation():
    """
    Run all validation checks
    """
    print("\n" + "=" * 60)
    print("  ChIP-seq Data Validation Report")
    print("  H3K36me3 and H3K9me3 for All Cell Types")
    print("=" * 60)

    conn = connect_db()
    cur = conn.cursor()

    try:
        # Run all checks
        check_global_stats(cur)
        coverage = check_coverage_matrix(cur)
        check_data_quality(cur)
        missing = check_missing_combinations(cur, coverage)
        check_experiment_metadata(cur)
        check_peak_distribution(cur)

        # Final summary
        print_header("Validation Summary")

        total_combinations = len(EXPECTED_CELL_TYPES) * len(EXPECTED_MARKS)
        present_combinations = sum(len(marks) for marks in coverage.values())

        print(f"\n  Expected combinations:  {total_combinations}")
        print(f"  Present combinations:   {present_combinations}")
        print(f"  Missing combinations:   {len(missing)}")

        if len(missing) == 0:
            print("\n  [PASS] All expected data is present")
            return True
        else:
            print(f"\n  [WARN] Missing {len(missing)} combinations")
            return False

    finally:
        cur.close()
        conn.close()


def test_heatmap_api():
    """
    Test the heatmap matrix API endpoint
    """
    print_header("Heatmap Matrix API Test")

    try:
        import urllib.request
        import json

        # Test API endpoint
        base_url = os.getenv("API_URL", "http://localhost:8000")
        gene_id = 17276  # Known gene ID
        marks = ",".join(EXPECTED_MARKS)
        cell_types = ",".join(EXPECTED_CELL_TYPES)

        url = f"{base_url}/api/v1/features/chipseq/genes/{gene_id}/heatmap-matrix"
        url += f"?marks={marks}&cell_types={cell_types}&metric=median_fold_enrichment"

        print(f"\n  Testing: GET {url[:80]}...")

        try:
            with urllib.request.urlopen(url, timeout=10) as response:
                data = json.loads(response.read().decode())

                print("\n  [OK] API Response Status: 200")
                print(f"  Gene: {data.get('gene_name', 'N/A')} (ID: {data.get('gene_id', 'N/A')})")
                print(f"  Total Combinations: {data.get('total_combinations', 'N/A')}")
                print(f"  Valid Combinations: {data.get('valid_combinations', 'N/A')}")

                # Print matrix preview
                matrix = data.get('matrix', [])
                if matrix:
                    print("\n  Matrix Preview (first 2 rows):")
                    cell_types_list = data.get('cell_types', [])
                    # Note: marks available via data.get('marks', [])

                    for i, cell_type in enumerate(cell_types_list[:2]):
                        row_values = []
                        for j, val in enumerate(matrix[i][:4] if i < len(matrix) else []):
                            if val is not None:
                                row_values.append(f"{val:.2f}")
                            else:
                                row_values.append("---")
                        print(f"    {cell_type}: {', '.join(row_values)}")

                return True

        except urllib.error.HTTPError as e:
            print(f"\n  [ERROR] API returned HTTP {e.code}: {e.reason}")
            return False
        except urllib.error.URLError as e:
            print(f"\n  [WARN] API not reachable: {e.reason}")
            print("  Skipping API test (backend may not be running)")
            return None

    except ImportError as e:
        print(f"\n  [WARN] Cannot test API: {e}")
        return None


if __name__ == "__main__":
    success = run_validation()

    # Also test API if available
    api_result = test_heatmap_api()

    # Print final status
    print("\n" + "=" * 60)
    print("  Final Status")
    print("=" * 60)
    print(f"\n  Database Validation: {'PASS' if success else 'WARN (missing data)'}")
    if api_result is True:
        print("  API Test: PASS")
    elif api_result is False:
        print("  API Test: FAIL")
    else:
        print("  API Test: SKIPPED")

    sys.exit(0 if success else 1)
