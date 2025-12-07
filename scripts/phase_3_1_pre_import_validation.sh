#!/bin/bash
################################################################################
# Phase 3.1: Pre-Import Validation Script for HepG2 × H3K9me3
#
# Purpose: Validate data files before importing to database
#
# Usage:
#   bash scripts/phase_3_1_pre_import_validation.sh <peaks_file>
#
# Example:
#   bash scripts/phase_3_1_pre_import_validation.sh data/HepG2_H3K9me3.narrowPeak.gz
################################################################################

set -euo pipefail

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

# Validation results
PASS_COUNT=0
FAIL_COUNT=0
WARN_COUNT=0

log_pass() {
    echo -e "${GREEN}[PASS]${NC} $1"
    ((PASS_COUNT++))
}

log_fail() {
    echo -e "${RED}[FAIL]${NC} $1"
    ((FAIL_COUNT++))
}

log_warn() {
    echo -e "${YELLOW}[WARN]${NC} $1"
    ((WARN_COUNT++))
}

log_info() {
    echo -e "[INFO] $1"
}

################################################################################
# Validation Functions
################################################################################

validate_file_exists() {
    local file=$1
    if [ -f "$file" ]; then
        log_pass "File exists: $file"
        return 0
    else
        log_fail "File not found: $file"
        return 1
    fi
}

validate_file_size() {
    local file=$1
    local min_size=$((5 * 1024 * 1024))   # 5 MB
    local max_size=$((50 * 1024 * 1024))  # 50 MB

    local size=$(stat -c%s "$file" 2>/dev/null || stat -f%z "$file" 2>/dev/null)
    local size_mb=$((size / 1024 / 1024))

    log_info "File size: ${size_mb} MB"

    if [ "$size" -lt "$min_size" ]; then
        log_warn "File size (${size_mb} MB) is smaller than expected (>5 MB). Data might be incomplete."
        return 1
    elif [ "$size" -gt "$max_size" ]; then
        log_warn "File size (${size_mb} MB) is larger than expected (<50 MB). Contains unusually many peaks."
        return 1
    else
        log_pass "File size is reasonable (${size_mb} MB)"
        return 0
    fi
}

validate_peak_format() {
    local file=$1
    local format=$2  # narrowPeak or broadPeak

    log_info "Validating peak format: $format"

    # Decompress if needed
    if [[ "$file" == *.gz ]]; then
        local sample=$(zcat "$file" | head -100)
    else
        local sample=$(head -100 "$file")
    fi

    # Skip header lines
    local data_lines=$(echo "$sample" | grep -v "^#" | grep -v "^track" | grep -v "^browser")

    if [ -z "$data_lines" ]; then
        log_fail "No data lines found in file (only headers)"
        return 1
    fi

    # Check column count
    local expected_cols=10  # narrowPeak
    if [ "$format" == "broadPeak" ]; then
        expected_cols=9
    fi

    local invalid_count=0
    while IFS= read -r line; do
        local col_count=$(echo "$line" | awk '{print NF}')
        if [ "$col_count" -ne "$expected_cols" ]; then
            ((invalid_count++))
        fi
    done <<< "$data_lines"

    if [ "$invalid_count" -gt 0 ]; then
        log_fail "Found $invalid_count lines with incorrect column count (expected: $expected_cols)"
        return 1
    else
        log_pass "Peak format is valid ($format with $expected_cols columns)"
        return 0
    fi
}

validate_peak_count() {
    local file=$1
    local min_peaks=20000
    local max_peaks=150000

    # Count peaks
    if [[ "$file" == *.gz ]]; then
        local peak_count=$(zcat "$file" | grep -v "^#" | grep -v "^track" | grep -v "^browser" | wc -l)
    else
        local peak_count=$(grep -v "^#" "$file" | grep -v "^track" | grep -v "^browser" | wc -l)
    fi

    log_info "Peak count: $peak_count"

    if [ "$peak_count" -lt "$min_peaks" ]; then
        log_fail "Peak count ($peak_count) is below expected range (>$min_peaks for H3K9me3)"
        return 1
    elif [ "$peak_count" -gt "$max_peaks" ]; then
        log_warn "Peak count ($peak_count) is above expected range (<$max_peaks). Unusually high."
        return 1
    else
        log_pass "Peak count is reasonable ($peak_count peaks)"
        return 0
    fi
}

validate_chromosome_names() {
    local file=$1

    # Extract chromosome names
    if [[ "$file" == *.gz ]]; then
        local chroms=$(zcat "$file" | grep -v "^#" | grep -v "^track" | grep -v "^browser" | cut -f1 | sort -u)
    else
        local chroms=$(grep -v "^#" "$file" | grep -v "^track" | grep -v "^browser" | cut -f1 | sort -u)
    fi

    # Check if chromosomes follow UCSC format (chr1, chr2, etc.)
    local invalid_chroms=$(echo "$chroms" | grep -v "^chr")

    if [ -n "$invalid_chroms" ]; then
        log_fail "Found chromosomes without 'chr' prefix: $(echo $invalid_chroms | head -5)"
        return 1
    else
        log_pass "All chromosomes use UCSC naming (chr1, chr2, ...)"
        return 0
    fi
}

validate_coordinate_ranges() {
    local file=$1

    # Check if coordinates are valid (start < end, non-negative)
    if [[ "$file" == *.gz ]]; then
        local invalid_coords=$(zcat "$file" | grep -v "^#" | grep -v "^track" | grep -v "^browser" | \
            awk '$2 < 0 || $3 < 0 || $3 <= $2 {print}' | wc -l)
    else
        local invalid_coords=$(grep -v "^#" "$file" | grep -v "^track" | grep -v "^browser" | \
            awk '$2 < 0 || $3 < 0 || $3 <= $2 {print}' | wc -l)
    fi

    if [ "$invalid_coords" -gt 0 ]; then
        log_fail "Found $invalid_coords peaks with invalid coordinates (negative or start >= end)"
        return 1
    else
        log_pass "All peak coordinates are valid (start < end, non-negative)"
        return 0
    fi
}

validate_signal_values() {
    local file=$1

    # Check signal values (fold enrichment) in column 7
    if [[ "$file" == *.gz ]]; then
        local stats=$(zcat "$file" | grep -v "^#" | grep -v "^track" | grep -v "^browser" | \
            awk '{if ($7 != "." && $7 != "-1") print $7}' | \
            awk '{sum+=$1; count++; if($1>max) max=$1; if(min=="" || $1<min) min=$1}
                 END {if(count>0) printf "%.2f %.2f %.2f", sum/count, min, max; else print "N/A"}')
    else
        local stats=$(grep -v "^#" "$file" | grep -v "^track" | grep -v "^browser" | \
            awk '{if ($7 != "." && $7 != "-1") print $7}' | \
            awk '{sum+=$1; count++; if($1>max) max=$1; if(min=="" || $1<min) min=$1}
                 END {if(count>0) printf "%.2f %.2f %.2f", sum/count, min, max; else print "N/A"}')
    fi

    if [ "$stats" == "N/A" ]; then
        log_warn "No valid signal values found in file"
        return 1
    fi

    local avg=$(echo $stats | cut -d' ' -f1)
    local min=$(echo $stats | cut -d' ' -f2)
    local max=$(echo $stats | cut -d' ' -f3)

    log_info "Signal values (fold enrichment): min=$min, avg=$avg, max=$max"

    # Check if values are reasonable (typical range: 2-50 for H3K9me3)
    if (( $(echo "$avg < 1.5" | bc -l) )); then
        log_warn "Average fold enrichment ($avg) is lower than expected (>1.5)"
        return 1
    elif (( $(echo "$avg > 100" | bc -l) )); then
        log_warn "Average fold enrichment ($avg) is higher than expected (<100)"
        return 1
    else
        log_pass "Signal values are within reasonable range"
        return 0
    fi
}

validate_duplicate_peaks() {
    local file=$1

    # Check for duplicate peaks (same chr:start-end)
    if [[ "$file" == *.gz ]]; then
        local total_peaks=$(zcat "$file" | grep -v "^#" | grep -v "^track" | grep -v "^browser" | wc -l)
        local unique_peaks=$(zcat "$file" | grep -v "^#" | grep -v "^track" | grep -v "^browser" | \
            awk '{print $1":"$2"-"$3}' | sort -u | wc -l)
    else
        local total_peaks=$(grep -v "^#" "$file" | grep -v "^track" | grep -v "^browser" | wc -l)
        local unique_peaks=$(grep -v "^#" "$file" | grep -v "^track" | grep -v "^browser" | \
            awk '{print $1":"$2"-"$3}' | sort -u | wc -l)
    fi

    local duplicates=$((total_peaks - unique_peaks))

    if [ "$duplicates" -gt 0 ]; then
        log_warn "Found $duplicates duplicate peaks (same coordinates)"
        return 1
    else
        log_pass "No duplicate peaks found"
        return 0
    fi
}

################################################################################
# Main Validation
################################################################################

main() {
    if [ $# -lt 1 ]; then
        echo "Usage: $0 <peaks_file> [format]"
        echo "  peaks_file: Path to narrowPeak or broadPeak file"
        echo "  format:     narrowPeak (default) or broadPeak"
        exit 1
    fi

    local peaks_file=$1
    local format=${2:-narrowPeak}

    echo "=============================================================================="
    echo "Phase 3.1: Pre-Import Validation"
    echo "File: $peaks_file"
    echo "Format: $format"
    echo "=============================================================================="
    echo ""

    # Run validations
    validate_file_exists "$peaks_file" || exit 1
    echo ""

    validate_file_size "$peaks_file"
    echo ""

    validate_peak_format "$peaks_file" "$format"
    echo ""

    validate_peak_count "$peaks_file"
    echo ""

    validate_chromosome_names "$peaks_file"
    echo ""

    validate_coordinate_ranges "$peaks_file"
    echo ""

    validate_signal_values "$peaks_file"
    echo ""

    validate_duplicate_peaks "$peaks_file"
    echo ""

    # Summary
    echo "=============================================================================="
    echo "Validation Summary"
    echo "=============================================================================="
    echo -e "Passed:   ${GREEN}$PASS_COUNT${NC}"
    echo -e "Warnings: ${YELLOW}$WARN_COUNT${NC}"
    echo -e "Failed:   ${RED}$FAIL_COUNT${NC}"
    echo ""

    if [ "$FAIL_COUNT" -eq 0 ]; then
        echo -e "${GREEN}[SUCCESS]${NC} All critical validations passed. File is ready for import."
        exit 0
    else
        echo -e "${RED}[FAILURE]${NC} Some critical validations failed. Please fix issues before import."
        exit 1
    fi
}

main "$@"
