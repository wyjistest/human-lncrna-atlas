#!/usr/bin/env python3
"""
Phase 3.1: Post-Import Validation Script for HepG2 × H3K9me3

Purpose: Validate data after importing to database

Usage:
    python3 scripts/phase_3_1_post_import_validation.py

Environment variables:
    DB_HOST, DB_PORT, DB_NAME, DB_USER, DB_PASSWORD
"""
import os
import sys
import psycopg2
from typing import Optional

# Configuration
DB_CONFIG = {
    "host": os.getenv("DB_HOST", "localhost"),
    "port": os.getenv("DB_PORT", "5432"),
    "database": os.getenv("DB_NAME", "lncrna_production"),
    "user": os.getenv("DB_USER", "amax"),
    "password": os.getenv("DB_PASSWORD", "")
}

# Expected data for Phase 3.1
EXPECTED_CELL_TYPE = "HepG2"
EXPECTED_MARK = "H3K9me3"
EXPECTED_MIN_PEAKS = 20000
EXPECTED_MAX_PEAKS = 150000

# Validation results
validation_results = {
    "passed": [],
    "warnings": [],
    "failed": [],
}


def log_pass(message: str):
    """Log passed validation"""
    print(f"✓ [PASS] {message}")
    validation_results["passed"].append(message)


def log_warn(message: str):
    """Log warning"""
    print(f"⚠ [WARN] {message}")
    validation_results["warnings"].append(message)


def log_fail(message: str):
    """Log failed validation"""
    print(f"✗ [FAIL] {message}")
    validation_results["failed"].append(message)


def log_info(message: str):
    """Log information"""
    print(f"ℹ [INFO] {message}")


def connect_db():
    """Create database connection"""
    try:
        conn = psycopg2.connect(**DB_CONFIG)
        return conn
    except Exception as e:
        print(f"[ERROR] Database connection failed: {e}")
        sys.exit(1)


def validate_experiment_exists(cur) -> Optional[int]:
    """
    Validate that HepG2 × H3K9me3 experiment exists

    Returns:
        experiment_id if exists, None otherwise
    """
    print("\n--- Validation 1: Experiment Exists ---")

    cur.execute("""
        SELECT e.experiment_id, e.experiment_name, e.cell_type, m.mark_name
        FROM chipseq_experiments e
        JOIN epigenetic_mark_types m ON e.mark_type_id = m.mark_type_id
        WHERE e.cell_type = %s AND m.mark_name = %s AND e.is_active = TRUE
    """, (EXPECTED_CELL_TYPE, EXPECTED_MARK))

    row = cur.fetchone()

    if row:
        exp_id, exp_name, cell_type, mark_name = row
        log_pass(f"Experiment exists: {exp_name} (ID: {exp_id})")
        log_info(f"Cell type: {cell_type}, Mark: {mark_name}")
        return exp_id
    else:
        log_fail(f"No experiment found for {EXPECTED_CELL_TYPE} × {EXPECTED_MARK}")
        return None


def validate_peak_count(cur, experiment_id: int) -> int:
    """
    Validate peak count is within expected range

    Returns:
        peak_count
    """
    print("\n--- Validation 2: Peak Count ---")

    cur.execute("""
        SELECT COUNT(*) as peak_count
        FROM chipseq_peaks
        WHERE experiment_id = %s
    """, (experiment_id,))

    peak_count = cur.fetchone()[0]
    log_info(f"Peak count: {peak_count:,}")

    if peak_count < EXPECTED_MIN_PEAKS:
        log_fail(f"Peak count ({peak_count:,}) is below expected minimum ({EXPECTED_MIN_PEAKS:,})")
    elif peak_count > EXPECTED_MAX_PEAKS:
        log_warn(f"Peak count ({peak_count:,}) is above expected maximum ({EXPECTED_MAX_PEAKS:,})")
    else:
        log_pass(f"Peak count is within expected range ({EXPECTED_MIN_PEAKS:,} - {EXPECTED_MAX_PEAKS:,})")

    return peak_count


def validate_no_duplicates(cur, experiment_id: int):
    """Validate no duplicate peaks"""
    print("\n--- Validation 3: Duplicate Peaks ---")

    cur.execute("""
        SELECT chromosome, peak_start, peak_end, COUNT(*) as count
        FROM chipseq_peaks
        WHERE experiment_id = %s
        GROUP BY chromosome, peak_start, peak_end
        HAVING COUNT(*) > 1
    """, (experiment_id,))

    duplicates = cur.fetchall()

    if duplicates:
        log_fail(f"Found {len(duplicates)} duplicate peak coordinates")
        for dup in duplicates[:5]:  # Show first 5
            log_info(f"  Duplicate: {dup[0]}:{dup[1]}-{dup[2]} (count: {dup[3]})")
    else:
        log_pass("No duplicate peaks found")


def validate_coordinates(cur, experiment_id: int):
    """Validate peak coordinates are valid"""
    print("\n--- Validation 4: Coordinate Validity ---")

    # Check for negative coordinates
    cur.execute("""
        SELECT COUNT(*) FROM chipseq_peaks
        WHERE experiment_id = %s AND (peak_start < 0 OR peak_end < 0)
    """, (experiment_id,))
    negative_count = cur.fetchone()[0]

    if negative_count > 0:
        log_fail(f"Found {negative_count} peaks with negative coordinates")
    else:
        log_pass("No negative coordinates found")

    # Check for start >= end
    cur.execute("""
        SELECT COUNT(*) FROM chipseq_peaks
        WHERE experiment_id = %s AND peak_start >= peak_end
    """, (experiment_id,))
    invalid_count = cur.fetchone()[0]

    if invalid_count > 0:
        log_fail(f"Found {invalid_count} peaks with start >= end")
    else:
        log_pass("All peaks have valid coordinate order (start < end)")


def validate_signal_values(cur, experiment_id: int):
    """Validate signal values (fold enrichment) are reasonable"""
    print("\n--- Validation 5: Signal Values ---")

    cur.execute("""
        SELECT
            COUNT(*) as total_peaks,
            AVG(fold_enrichment) as avg_fe,
            MIN(fold_enrichment) as min_fe,
            MAX(fold_enrichment) as max_fe,
            PERCENTILE_CONT(0.5) WITHIN GROUP (ORDER BY fold_enrichment) as median_fe
        FROM chipseq_peaks
        WHERE experiment_id = %s AND fold_enrichment IS NOT NULL
    """, (experiment_id,))

    row = cur.fetchone()

    if row and row[0] > 0:
        total, avg_fe, min_fe, max_fe, median_fe = row
        log_info("Fold enrichment statistics:")
        log_info(f"  Total peaks with FE: {total:,}")
        log_info(f"  Min: {min_fe:.2f}")
        log_info(f"  Avg: {avg_fe:.2f}")
        log_info(f"  Median: {median_fe:.2f}")
        log_info(f"  Max: {max_fe:.2f}")

        # Check if values are reasonable (typical range: 2-50 for H3K9me3)
        if avg_fe < 1.5:
            log_warn(f"Average fold enrichment ({avg_fe:.2f}) is lower than expected (>1.5)")
        elif avg_fe > 100:
            log_warn(f"Average fold enrichment ({avg_fe:.2f}) is higher than expected (<100)")
        else:
            log_pass("Signal values are within reasonable range")
    else:
        log_warn("No peaks with fold enrichment values found")


def validate_chromosome_distribution(cur, experiment_id: int):
    """Validate peaks are distributed across chromosomes"""
    print("\n--- Validation 6: Chromosome Distribution ---")

    cur.execute("""
        SELECT chromosome, COUNT(*) as count
        FROM chipseq_peaks
        WHERE experiment_id = %s
        GROUP BY chromosome
        ORDER BY
            CASE
                WHEN chromosome ~ '^chr[0-9]+$' THEN CAST(SUBSTRING(chromosome FROM 4) AS INTEGER)
                WHEN chromosome = 'chrX' THEN 23
                WHEN chromosome = 'chrY' THEN 24
                WHEN chromosome = 'chrM' THEN 25
                ELSE 26
            END
    """, (experiment_id,))

    chromosomes = cur.fetchall()

    if not chromosomes:
        log_fail("No chromosomes found")
        return

    log_info(f"Peaks distributed across {len(chromosomes)} chromosomes:")
    for chrom, count in chromosomes[:5]:  # Show first 5
        log_info(f"  {chrom}: {count:,} peaks")

    # Check if we have major chromosomes
    chrom_names = [c[0] for c in chromosomes]
    major_chroms = [f"chr{i}" for i in range(1, 23)] + ["chrX"]

    missing_major = [c for c in major_chroms if c not in chrom_names]

    if len(missing_major) > 5:
        log_warn(f"Missing peaks on {len(missing_major)} major chromosomes")
    elif len(missing_major) > 0:
        log_info(f"Missing peaks on {len(missing_major)} chromosomes: {', '.join(missing_major[:5])}")
        log_pass("Peaks found on most major chromosomes")
    else:
        log_pass("Peaks found on all major chromosomes")


def validate_experiment_metadata(cur, experiment_id: int):
    """Validate experiment metadata is complete"""
    print("\n--- Validation 7: Experiment Metadata ---")

    cur.execute("""
        SELECT
            experiment_name, cell_type, tissue_type, cell_line,
            source_database, source_accession, reference_genome,
            peak_caller, created_at
        FROM chipseq_experiments
        WHERE experiment_id = %s
    """, (experiment_id,))

    row = cur.fetchone()

    if row:
        (exp_name, cell_type, tissue, cell_line,
         source_db, accession, genome, peak_caller, created) = row

        log_info("Experiment metadata:")
        log_info(f"  Name: {exp_name}")
        log_info(f"  Cell type: {cell_type}")
        log_info(f"  Tissue: {tissue or 'N/A'}")
        log_info(f"  Cell line: {cell_line or 'N/A'}")
        log_info(f"  Source: {source_db or 'N/A'}")
        log_info(f"  Accession: {accession or 'N/A'}")
        log_info(f"  Genome: {genome or 'N/A'}")
        log_info(f"  Peak caller: {peak_caller or 'N/A'}")
        log_info(f"  Created: {created}")

        # Check required fields
        if cell_type == EXPECTED_CELL_TYPE:
            log_pass("Cell type is correct")
        else:
            log_fail(f"Cell type mismatch: expected {EXPECTED_CELL_TYPE}, got {cell_type}")


def validate_coverage_matrix_complete(cur):
    """Validate that coverage matrix now shows 6/6 marks for HepG2"""
    print("\n--- Validation 8: Coverage Matrix Completeness ---")

    cur.execute("""
        SELECT m.mark_name, COUNT(*) as peaks
        FROM chipseq_experiments e
        JOIN chipseq_peaks p ON e.experiment_id = p.experiment_id
        JOIN epigenetic_mark_types m ON e.mark_type_id = m.mark_type_id
        WHERE e.cell_type = %s AND e.is_active = TRUE
        GROUP BY m.mark_name
        ORDER BY m.mark_name
    """, (EXPECTED_CELL_TYPE,))

    marks = cur.fetchall()

    if not marks:
        log_fail(f"No marks found for {EXPECTED_CELL_TYPE}")
        return

    log_info(f"{EXPECTED_CELL_TYPE} coverage:")
    for mark_name, peak_count in marks:
        log_info(f"  {mark_name}: {peak_count:,} peaks")

    # Check if H3K9me3 is present
    mark_names = [m[0] for m in marks]

    if EXPECTED_MARK in mark_names:
        log_pass(f"{EXPECTED_MARK} is present in coverage matrix")
    else:
        log_fail(f"{EXPECTED_MARK} is missing from coverage matrix")

    # Check if we have 6 marks (expected for HepG2 after Phase 3.1)
    expected_marks = ["H3K27me3", "H3K4me3", "H3K27ac", "H3K4me1", "H3K36me3", "H3K9me3"]
    missing_marks = [m for m in expected_marks if m not in mark_names]

    if len(mark_names) == 6 and len(missing_marks) == 0:
        log_pass(f"{EXPECTED_CELL_TYPE} now has complete coverage (6/6 marks)")
    elif len(missing_marks) > 0:
        log_warn(f"{EXPECTED_CELL_TYPE} is missing {len(missing_marks)} marks: {', '.join(missing_marks)}")
    else:
        log_pass(f"{EXPECTED_CELL_TYPE} has {len(mark_names)} marks")


def main():
    """Run all post-import validations"""
    print("=" * 80)
    print("Phase 3.1: Post-Import Validation")
    print(f"Target: {EXPECTED_CELL_TYPE} × {EXPECTED_MARK}")
    print("=" * 80)

    conn = connect_db()
    cur = conn.cursor()

    try:
        # Validation 1: Experiment exists
        experiment_id = validate_experiment_exists(cur)

        if not experiment_id:
            print("\n" + "=" * 80)
            print("[CRITICAL] Experiment not found. Cannot proceed with further validations.")
            print("=" * 80)
            sys.exit(1)

        # Validation 2-7: Data quality checks
        validate_peak_count(cur, experiment_id)
        validate_no_duplicates(cur, experiment_id)
        validate_coordinates(cur, experiment_id)
        validate_signal_values(cur, experiment_id)
        validate_chromosome_distribution(cur, experiment_id)
        validate_experiment_metadata(cur, experiment_id)

        # Validation 8: Coverage matrix
        validate_coverage_matrix_complete(cur)

        # Summary
        print("\n" + "=" * 80)
        print("Validation Summary")
        print("=" * 80)
        print(f"Passed:   {len(validation_results['passed'])}")
        print(f"Warnings: {len(validation_results['warnings'])}")
        print(f"Failed:   {len(validation_results['failed'])}")
        print("")

        if len(validation_results['failed']) == 0:
            print("✓ [SUCCESS] All validations passed. Data import is successful.")
            return_code = 0
        else:
            print("✗ [FAILURE] Some validations failed. Please review the issues above.")
            return_code = 1

        if len(validation_results['warnings']) > 0:
            print("")
            print("Warnings:")
            for warning in validation_results['warnings']:
                print(f"  - {warning}")

        print("=" * 80)

    finally:
        cur.close()
        conn.close()

    sys.exit(return_code)


if __name__ == "__main__":
    main()
