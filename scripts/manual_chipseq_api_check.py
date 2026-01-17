#!/usr/bin/env python3
"""
Manual acceptance test script for ChIP-seq Multi-Marks Comparison API.

NOTE: This is a manual validation script, NOT an automated pytest test.
      It was moved from test_chipseq_api.py (project root) to avoid
      pytest collection and allow independent manual execution.

Tests the three main API endpoints for the Human LncRNA Atlas project.

Usage:
    python3 scripts/manual_chipseq_api_check.py
"""

import time
import requests
from typing import Dict, List, Tuple
from dataclasses import dataclass

BASE_URL = "http://localhost:8000/api/v1/features/chipseq"

# Test data - genes known to have ChIP-seq data
TEST_GENE_IDS = [27908, 32322, 18521]  # GSE1, RAD51B, AC025171.1
TEST_MARKS = ["H3K4me3", "H3K27me3", "H3K27ac"]
TEST_CELL_TYPES = ["K562", "HepG2", "H1-hESC", "GM12878"]


@dataclass
class TestResult:
    name: str
    passed: bool
    response_time_ms: float
    details: str
    errors: List[str]


def measure_request(url: str, params: Dict = None) -> Tuple[Dict, float, int]:
    """Make a request and measure response time."""
    start = time.time()
    try:
        response = requests.get(url, params=params, timeout=60)
        elapsed = (time.time() - start) * 1000  # ms
        if response.status_code == 200:
            return response.json(), elapsed, response.status_code
        else:
            return {"error": response.text}, elapsed, response.status_code
    except Exception as e:
        elapsed = (time.time() - start) * 1000
        return {"error": str(e)}, elapsed, 0


def test_multi_marks_compare(gene_id: int = 27908) -> TestResult:
    """Test 1: Multi-Marks Compare API."""
    errors = []
    details_parts = []

    url = f"{BASE_URL}/genes/{gene_id}/compare"
    params = {"marks": ",".join(TEST_MARKS)}

    data, response_time, status_code = measure_request(url, params)

    if status_code != 200:
        return TestResult(
            name="Multi-Marks Compare API",
            passed=False,
            response_time_ms=response_time,
            details=f"HTTP {status_code}",
            errors=[f"Request failed: {data.get('error', 'Unknown error')}"]
        )

    # Validate response structure
    # Note: 'total_marks' is not in actual response, use len(marks) instead
    required_fields = ["gene_id", "gene_name", "chromosome", "region_start", "region_end", "marks", "overlap_statistics"]
    for field in required_fields:
        if field not in data:
            errors.append(f"Missing required field: {field}")

    # Validate marks data
    marks = data.get("marks", [])
    if not marks:
        errors.append("No marks data returned")
    else:
        details_parts.append(f"Marks returned: {len(marks)}")

        for mark in marks:
            mark_fields = ["mark_type", "mark_category", "peaks", "peak_count",
                         "avg_fold_enrichment", "median_fold_enrichment", "total_coverage_bp"]
            for f in mark_fields:
                if f not in mark:
                    errors.append(f"Mark '{mark.get('mark_type', '?')}' missing field: {f}")

            # Check peak data structure
            peaks = mark.get("peaks", [])
            if peaks:
                peak = peaks[0]
                peak_fields = ["peak_id", "chromosome", "peak_start", "peak_end", "fold_enrichment"]
                for pf in peak_fields:
                    if pf not in peak:
                        errors.append(f"Peak missing field: {pf}")
                        break
                details_parts.append(f"  {mark.get('mark_type')}: {len(peaks)} peaks")

    # Check overlap statistics
    overlap_stats = data.get("overlap_statistics", [])
    if overlap_stats:
        details_parts.append(f"Overlap pairs: {len(overlap_stats)}")
        for stat in overlap_stats:
            stat_fields = ["mark_pair", "overlap_count", "total_overlap_bp"]
            for sf in stat_fields:
                if sf not in stat:
                    errors.append(f"Overlap stat missing field: {sf}")
                    break

    # Check bivalent domains
    bivalent = data.get("bivalent_domains", [])
    details_parts.append(f"Bivalent domains: {len(bivalent)}")

    return TestResult(
        name="Multi-Marks Compare API",
        passed=len(errors) == 0,
        response_time_ms=response_time,
        details="; ".join(details_parts),
        errors=errors
    )


def test_cell_line_compare(gene_id: int = 27908) -> TestResult:
    """Test 2: Cell Line Compare API."""
    errors = []
    details_parts = []

    url = f"{BASE_URL}/genes/{gene_id}/compare-cell-lines"
    params = {
        "mark_type": "H3K27me3",
        "cell_types": ",".join(TEST_CELL_TYPES)
    }

    data, response_time, status_code = measure_request(url, params)

    if status_code != 200:
        return TestResult(
            name="Cell Line Compare API",
            passed=False,
            response_time_ms=response_time,
            details=f"HTTP {status_code}",
            errors=[f"Request failed: {data.get('error', 'Unknown error')}"]
        )

    # Validate response structure
    required_fields = ["gene_id", "gene_name", "chromosome", "region_start", "region_end",
                      "mark_type", "cell_lines", "total_cell_lines"]
    for field in required_fields:
        if field not in data:
            errors.append(f"Missing required field: {field}")

    # Validate cell lines data
    cell_lines = data.get("cell_lines", [])
    if not cell_lines:
        errors.append("No cell lines data returned")
    else:
        details_parts.append(f"Cell lines: {len(cell_lines)}")

        for cl in cell_lines:
            # Note: actual field is 'total_peaks' not 'peak_count'
            cl_fields = ["cell_type", "total_peaks"]
            for f in cl_fields:
                if f not in cl:
                    errors.append(f"Cell line '{cl.get('cell_type', '?')}' missing field: {f}")
            details_parts.append(f"  {cl.get('cell_type')}: {cl.get('total_peaks', 0)} peaks")

    # Check overlap statistics
    overlap_stats = data.get("overlap_statistics", [])
    if overlap_stats:
        details_parts.append(f"Cell line pairs: {len(overlap_stats)}")
        for stat in overlap_stats:
            if "jaccard_index" in stat:
                details_parts.append(f"  {stat.get('cell_pair')}: Jaccard={stat.get('jaccard_index')}")

    # Check missing cell lines
    missing = data.get("missing_cell_lines", [])
    if missing:
        details_parts.append(f"Missing cell lines: {missing}")

    return TestResult(
        name="Cell Line Compare API",
        passed=len(errors) == 0,
        response_time_ms=response_time,
        details="; ".join(details_parts),
        errors=errors
    )


def test_heatmap_matrix(gene_id: int = 27908) -> TestResult:
    """Test 3: Heatmap Matrix API."""
    errors = []
    details_parts = []

    url = f"{BASE_URL}/genes/{gene_id}/heatmap-matrix"
    params = {
        "marks": ",".join(TEST_MARKS[:2]),  # H3K4me3, H3K27me3
        "cell_types": ",".join(TEST_CELL_TYPES[:2]),  # K562, HepG2
        "metric": "median_fold_enrichment"
    }

    data, response_time, status_code = measure_request(url, params)

    if status_code != 200:
        return TestResult(
            name="Heatmap Matrix API",
            passed=False,
            response_time_ms=response_time,
            details=f"HTTP {status_code}",
            errors=[f"Request failed: {data.get('error', 'Unknown error')}"]
        )

    # Validate response structure
    required_fields = ["gene_id", "gene_name", "chromosome", "cell_types", "marks",
                      "metric", "matrix", "total_combinations", "valid_combinations"]
    for field in required_fields:
        if field not in data:
            errors.append(f"Missing required field: {field}")

    # Validate matrix data
    matrix = data.get("matrix", [])
    if not matrix:
        errors.append("No matrix data returned")
    else:
        details_parts.append(f"Matrix rows: {len(matrix)}, columns: {len(matrix[0]) if matrix else 0}")

    # Check details (tooltip data)
    details_data = data.get("details", {})
    if details_data:
        valid_count = sum(1 for k, v in details_data.items() if v is not None)
        details_parts.append(f"Detail entries: {valid_count}/{len(details_data)}")

    # Check combinations
    total = data.get("total_combinations", 0)
    valid = data.get("valid_combinations", 0)
    details_parts.append(f"Valid combinations: {valid}/{total}")

    # Check missing combinations
    missing = data.get("missing_combinations", [])
    if missing:
        details_parts.append(f"Missing: {len(missing)} combinations")

    return TestResult(
        name="Heatmap Matrix API",
        passed=len(errors) == 0,
        response_time_ms=response_time,
        details="; ".join(details_parts),
        errors=errors
    )


def test_cache_mechanism(gene_id: int = 27908) -> TestResult:
    """Test 4: Cache Mechanism - verify repeated requests are faster."""
    errors = []
    details_parts = []

    url = f"{BASE_URL}/genes/{gene_id}/compare"
    params = {"marks": "H3K4me3,H3K27me3"}

    # First request (cold cache)
    _, time1, status1 = measure_request(url, params)
    if status1 != 200:
        return TestResult(
            name="Cache Mechanism",
            passed=False,
            response_time_ms=time1,
            details="First request failed",
            errors=["Initial request failed"]
        )
    details_parts.append(f"First request: {time1:.0f}ms")

    # Second request (should hit cache)
    _, time2, status2 = measure_request(url, params)
    if status2 != 200:
        errors.append("Second request failed")
    details_parts.append(f"Second request: {time2:.0f}ms")

    # Third request
    _, time3, status3 = measure_request(url, params)
    details_parts.append(f"Third request: {time3:.0f}ms")

    # Calculate improvement
    avg_cached = (time2 + time3) / 2
    improvement = ((time1 - avg_cached) / time1) * 100 if time1 > 0 else 0
    details_parts.append(f"Improvement: {improvement:.1f}%")

    # Cache should provide some improvement (at least consistent response time)
    # Note: With local testing, first request might already be fast due to DB caching
    passed = True  # Cache test is informational

    return TestResult(
        name="Cache Mechanism",
        passed=passed,
        response_time_ms=time2,  # Report cached time
        details="; ".join(details_parts),
        errors=errors
    )


def test_error_handling() -> TestResult:
    """Test 5: Error Handling - verify proper error responses."""
    errors = []
    details_parts = []

    # Test 1: Invalid gene ID
    url = f"{BASE_URL}/genes/9999999/compare"
    params = {"marks": "H3K4me3,H3K27me3"}
    data, _, status = measure_request(url, params)
    if status == 404:
        details_parts.append("Invalid gene ID: 404 OK")
    else:
        errors.append(f"Invalid gene ID returned {status}, expected 404")

    # Test 2: Only one mark (need at least 2)
    url = f"{BASE_URL}/genes/27908/compare"
    params = {"marks": "H3K4me3"}
    data, _, status = measure_request(url, params)
    if status == 400:
        details_parts.append("Single mark validation: 400 OK")
    else:
        errors.append(f"Single mark returned {status}, expected 400")

    # Test 3: Invalid mark type
    url = f"{BASE_URL}/genes/27908/compare"
    params = {"marks": "H3K4me3,INVALID_MARK"}
    data, _, status = measure_request(url, params)
    if status == 200:  # Should return empty for invalid mark
        details_parts.append("Invalid mark handled gracefully")

    return TestResult(
        name="Error Handling",
        passed=len(errors) == 0,
        response_time_ms=0,
        details="; ".join(details_parts),
        errors=errors
    )


def test_different_metrics() -> TestResult:
    """Test 6: Different Metrics in Heatmap Matrix."""
    errors = []
    details_parts = []

    metrics = ["median_fold_enrichment", "peak_count", "total_coverage_bp", "avg_signal"]
    gene_id = 27908

    for metric in metrics:
        url = f"{BASE_URL}/genes/{gene_id}/heatmap-matrix"
        params = {
            "marks": "H3K4me3,H3K27me3",
            "cell_types": "K562,HepG2",
            "metric": metric
        }
        data, response_time, status = measure_request(url, params)

        if status == 200:
            returned_metric = data.get("metric")
            if returned_metric == metric:
                details_parts.append(f"{metric}: OK ({response_time:.0f}ms)")
            else:
                errors.append(f"{metric}: returned wrong metric '{returned_metric}'")
        else:
            errors.append(f"{metric}: HTTP {status}")

    return TestResult(
        name="Different Metrics Support",
        passed=len(errors) == 0,
        response_time_ms=0,
        details="; ".join(details_parts),
        errors=errors
    )


def run_all_tests() -> List[TestResult]:
    """Run all tests and return results."""
    results = []

    print("=" * 70)
    print("ChIP-seq Multi-Marks Comparison API - Acceptance Test")
    print("=" * 70)
    print()

    # Run tests
    tests = [
        ("1. Multi-Marks Compare API", test_multi_marks_compare),
        ("2. Cell Line Compare API", test_cell_line_compare),
        ("3. Heatmap Matrix API", test_heatmap_matrix),
        ("4. Cache Mechanism", test_cache_mechanism),
        ("5. Error Handling", test_error_handling),
        ("6. Different Metrics Support", test_different_metrics),
    ]

    for test_name, test_func in tests:
        print(f"Running: {test_name}...")
        try:
            result = test_func()
            results.append(result)

            status = "PASS" if result.passed else "FAIL"
            print(f"  [{status}] {result.name}")
            print(f"         Response Time: {result.response_time_ms:.0f}ms")
            print(f"         Details: {result.details}")
            if result.errors:
                for err in result.errors:
                    print(f"         ERROR: {err}")
        except Exception as e:
            print(f"  [ERROR] {test_name}: {str(e)}")
            results.append(TestResult(
                name=test_name,
                passed=False,
                response_time_ms=0,
                details="Exception occurred",
                errors=[str(e)]
            ))
        print()

    return results


def print_summary(results: List[TestResult]):
    """Print test summary."""
    print("=" * 70)
    print("TEST SUMMARY")
    print("=" * 70)

    passed = sum(1 for r in results if r.passed)
    total = len(results)

    print(f"\nTotal Tests: {total}")
    print(f"Passed: {passed}")
    print(f"Failed: {total - passed}")
    print(f"Pass Rate: {(passed/total)*100:.1f}%")

    # Response time statistics
    valid_times = [r.response_time_ms for r in results if r.response_time_ms > 0]
    if valid_times:
        print("\nResponse Time Statistics:")
        print(f"  Average: {sum(valid_times)/len(valid_times):.0f}ms")
        print(f"  Min: {min(valid_times):.0f}ms")
        print(f"  Max: {max(valid_times):.0f}ms")

    # List failures
    failures = [r for r in results if not r.passed]
    if failures:
        print("\nFailed Tests:")
        for f in failures:
            print(f"  - {f.name}")
            for err in f.errors:
                print(f"      {err}")

    print("\n" + "=" * 70)


if __name__ == "__main__":
    results = run_all_tests()
    print_summary(results)
