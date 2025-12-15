#!/usr/bin/env python3
"""
Manual acceptance test script for batch heatmap matrix API endpoint.

NOTE: This is a manual validation script, NOT an automated pytest test.
      It was moved from frontend/backend/test_batch_heatmap.py to avoid
      pytest collection and allow independent manual execution.

Usage:
    python3 scripts/manual_batch_heatmap_check.py

Tests:
    1. Basic batch query with 3 genes
    2. Single gene (edge case)
    3. Maximum genes (10 genes)
    4. Different metrics
    5. Performance test with 10 genes
"""

import httpx
import json
import time
import statistics

# API Base URL
BASE_URL = "http://localhost:8000/api/v1/features/chipseq"

# Test genes (using IDs from database)
TEST_GENES = [17276, 17277, 17278, 17279, 17280, 17281, 17282, 17283, 17284, 17285]

# Test marks (common histone modifications)
TEST_MARKS = ["H3K27me3", "H3K4me3", "H3K27ac", "H3K4me1"]

# Test cell types
TEST_CELL_TYPES = ["K562", "HepG2", "GM12878"]


def print_section(title: str):
    """Print a section header"""
    print("\n" + "=" * 70)
    print(f"  {title}")
    print("=" * 70)


def print_result(test_name: str, status: str, details: str = ""):
    """Print test result"""
    status_symbol = "✓" if status == "PASS" else "✗"
    print(f"{status_symbol} {test_name}: {status}")
    if details:
        print(f"  {details}")


def test_basic_batch_query():
    """Test 1: Basic batch query with 3 genes"""
    print_section("Test 1: Basic Batch Query (3 Genes)")

    request_body = {
        "gene_ids": TEST_GENES[:3],
        "marks": TEST_MARKS[:2],
        "cell_types": TEST_CELL_TYPES,
        "metric": "median_fold_enrichment",
        "flanking": 10000,
        "include_details": False
    }

    print("Request body:")
    print(json.dumps(request_body, indent=2))

    try:
        with httpx.Client(timeout=30.0) as client:
            response = client.post(
                f"{BASE_URL}/genes/batch-heatmap-matrix",
                json=request_body
            )

        if response.status_code == 200:
            data = response.json()
            print_result("Basic Query", "PASS",
                f"Got {data['successful_genes']}/{data['total_genes']} genes in {data['query_time_ms']}ms")

            # Validate response structure
            assert "genes" in data, "Missing 'genes' field"
            assert "total_genes" in data, "Missing 'total_genes' field"
            assert "successful_genes" in data, "Missing 'successful_genes' field"
            assert "failed_genes" in data, "Missing 'failed_genes' field"
            assert "query_time_ms" in data, "Missing 'query_time_ms' field"

            # Validate each gene response
            for gene in data["genes"]:
                assert "gene_id" in gene, "Missing gene_id"
                assert "matrix" in gene, "Missing matrix"
                assert "cell_types" in gene, "Missing cell_types"
                assert "marks" in gene, "Missing marks"
                assert len(gene["matrix"]) == len(gene["cell_types"]), "Matrix rows mismatch"
                if gene["matrix"]:
                    assert len(gene["matrix"][0]) == len(gene["marks"]), "Matrix columns mismatch"

            print_result("Response Structure", "PASS", "All required fields present")
            return True
        else:
            print_result("Basic Query", "FAIL", f"HTTP {response.status_code}")
            print(f"Response: {response.text}")
            return False

    except Exception as e:
        print_result("Basic Query", "FAIL", str(e))
        return False


def test_single_gene():
    """Test 2: Single gene (edge case)"""
    print_section("Test 2: Single Gene Query")

    request_body = {
        "gene_ids": [TEST_GENES[0]],
        "marks": TEST_MARKS[:1],
        "cell_types": TEST_CELL_TYPES[:1],
        "metric": "peak_count",
        "flanking": 5000,
    }

    try:
        with httpx.Client(timeout=30.0) as client:
            response = client.post(
                f"{BASE_URL}/genes/batch-heatmap-matrix",
                json=request_body
            )

        if response.status_code == 200:
            data = response.json()
            assert data["total_genes"] == 1, "Should have 1 gene"
            print_result("Single Gene Query", "PASS",
                f"Gene {TEST_GENES[0]} processed in {data['query_time_ms']}ms")
            return True
        else:
            print_result("Single Gene Query", "FAIL", f"HTTP {response.status_code}")
            return False

    except Exception as e:
        print_result("Single Gene Query", "FAIL", str(e))
        return False


def test_multiple_metrics():
    """Test 3: Different metrics"""
    print_section("Test 3: Different Metrics")

    metrics = ["median_fold_enrichment", "peak_count", "total_coverage_bp", "avg_signal"]
    request_base = {
        "gene_ids": TEST_GENES[:2],
        "marks": TEST_MARKS[:2],
        "cell_types": TEST_CELL_TYPES[:2],
        "flanking": 10000,
    }

    all_passed = True
    for metric in metrics:
        request_body = {**request_base, "metric": metric}

        try:
            with httpx.Client(timeout=30.0) as client:
                response = client.post(
                    f"{BASE_URL}/genes/batch-heatmap-matrix",
                    json=request_body
                )

            if response.status_code == 200:
                data = response.json()
                print_result(f"Metric: {metric}", "PASS",
                    f"{data['successful_genes']} genes, {data['query_time_ms']}ms")
            else:
                print_result(f"Metric: {metric}", "FAIL", f"HTTP {response.status_code}")
                all_passed = False

        except Exception as e:
            print_result(f"Metric: {metric}", "FAIL", str(e))
            all_passed = False

    return all_passed


def test_performance_10_genes():
    """Test 4: Performance test with 10 genes"""
    print_section("Test 4: Performance Test (10 Genes)")

    request_body = {
        "gene_ids": TEST_GENES[:10],
        "marks": TEST_MARKS,
        "cell_types": TEST_CELL_TYPES,
        "metric": "median_fold_enrichment",
        "flanking": 10000,
        "include_details": True
    }

    print(f"Querying {len(request_body['gene_ids'])} genes with:")
    print(f"  - Marks: {', '.join(request_body['marks'])}")
    print(f"  - Cell types: {', '.join(request_body['cell_types'])}")
    print(f"  - Total combinations per gene: {len(request_body['marks']) * len(request_body['cell_types'])}")

    try:
        times = []

        for i in range(3):  # Run 3 times to get average
            with httpx.Client(timeout=60.0) as client:
                start = time.time()
                response = client.post(
                    f"{BASE_URL}/genes/batch-heatmap-matrix",
                    json=request_body
                )
                elapsed = time.time() - start

            if response.status_code == 200:
                data = response.json()
                times.append(data['query_time_ms'])
                print(f"  Run {i+1}: {data['query_time_ms']}ms (HTTP time: {elapsed*1000:.1f}ms)")
            else:
                print_result("Performance Test", "FAIL", f"HTTP {response.status_code}")
                return False

        avg_time = statistics.mean(times)
        min_time = min(times)
        max_time = max(times)

        print_result("Performance Test", "PASS",
            f"Average: {avg_time:.0f}ms | Min: {min_time}ms | Max: {max_time}ms")
        print(f"  Per gene average: {avg_time/10:.0f}ms")
        print(f"  Per gene-mark-celltype combination: {(avg_time/10)/(len(TEST_MARKS)*len(TEST_CELL_TYPES)):.1f}ms")

        return True

    except Exception as e:
        print_result("Performance Test", "FAIL", str(e))
        return False


def test_error_handling():
    """Test 5: Error handling"""
    print_section("Test 5: Error Handling")

    all_passed = True

    # Test: Empty gene list
    try:
        with httpx.Client(timeout=30.0) as client:
            response = client.post(
                f"{BASE_URL}/genes/batch-heatmap-matrix",
                json={
                    "gene_ids": [],
                    "marks": TEST_MARKS[:1],
                    "cell_types": TEST_CELL_TYPES[:1],
                }
            )

        if response.status_code == 422:  # Validation error
            print_result("Empty gene_ids", "PASS", "Correctly rejected")
        else:
            print_result("Empty gene_ids", "FAIL", f"Expected 422, got {response.status_code}")
            all_passed = False
    except Exception as e:
        print_result("Empty gene_ids", "FAIL", str(e))
        all_passed = False

    # Test: Non-existent genes
    try:
        with httpx.Client(timeout=30.0) as client:
            response = client.post(
                f"{BASE_URL}/genes/batch-heatmap-matrix",
                json={
                    "gene_ids": [999999, 999998],
                    "marks": TEST_MARKS[:1],
                    "cell_types": TEST_CELL_TYPES[:1],
                }
            )

        if response.status_code == 200:
            data = response.json()
            if len(data['failed_genes']) == 2:
                print_result("Non-existent genes", "PASS", "Correctly marked as failed")
            else:
                print_result("Non-existent genes", "FAIL", f"Expected 2 failed genes, got {len(data['failed_genes'])}")
                all_passed = False
        else:
            print_result("Non-existent genes", "FAIL", f"HTTP {response.status_code}")
            all_passed = False
    except Exception as e:
        print_result("Non-existent genes", "FAIL", str(e))
        all_passed = False

    return all_passed


def main():
    """Run all tests"""
    print("\n" + "=" * 70)
    print("  Batch Heatmap Matrix API - Test Suite")
    print("=" * 70)

    # Check if API is available
    try:
        with httpx.Client(timeout=5.0) as client:
            response = client.get(f"{BASE_URL}/marks")
        if response.status_code != 200:
            print("ERROR: API is not responding correctly")
            return 1
    except Exception:
        print(f"ERROR: Cannot connect to API at {BASE_URL}")
        print("Make sure the backend is running: python3 -m uvicorn app.main:app --reload")
        return 1

    print("✓ API is accessible")

    # Run tests
    results = []
    results.append(("Basic Batch Query", test_basic_batch_query()))
    results.append(("Single Gene Query", test_single_gene()))
    results.append(("Multiple Metrics", test_multiple_metrics()))
    results.append(("Performance Test", test_performance_10_genes()))
    results.append(("Error Handling", test_error_handling()))

    # Summary
    print_section("Test Summary")
    passed = sum(1 for _, result in results if result)
    total = len(results)

    for test_name, result in results:
        status = "PASS" if result else "FAIL"
        symbol = "✓" if result else "✗"
        print(f"{symbol} {test_name}: {status}")

    print(f"\nTotal: {passed}/{total} tests passed")

    return 0 if passed == total else 1


if __name__ == "__main__":
    exit(main())
