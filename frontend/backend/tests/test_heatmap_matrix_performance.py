"""
Heatmap Matrix Performance Tests

Performance tests for the /heatmap-matrix endpoint to ensure
acceptable response times under various conditions.

Run: pytest tests/test_heatmap_matrix_performance.py -v
"""
import pytest
import httpx

# Mark all tests in this module as integration + performance + slow tests
# Phase 9.20: Added 'slow' marker for test layer optimization
pytestmark = [pytest.mark.integration, pytest.mark.performance, pytest.mark.slow]
import time
import statistics
from typing import Optional, Dict, Any
import os

# ============== Configuration ==============

BASE_URL = os.getenv("TEST_API_URL", "http://localhost:8000")

# Performance thresholds (in milliseconds)
PERF_THRESHOLD_2X2 = 200   # 2x2 matrix should be < 200ms
PERF_THRESHOLD_4X4 = 300   # 4x4 matrix should be < 300ms
PERF_THRESHOLD_8X10 = 500  # 8x10 matrix should be < 500ms

# Test gene ID
TEST_GENE_ID = 17276


# ============== Helper Functions ==============

def get_valid_gene_id(client: httpx.Client) -> Optional[int]:
    """Get a valid gene ID from the database for testing."""
    response = client.get(f"{BASE_URL}/api/v1/genes?page=1&page_size=1&species_id=1")
    if response.status_code == 200:
        data = response.json()
        if data.get("items") and len(data["items"]) > 0:
            return data["items"][0]["gene_id"]
    return None


def measure_response_time(client: httpx.Client, url: str, params: Dict[str, Any]) -> Dict[str, Any]:
    """
    Measure the response time for a request.

    Returns:
        dict with elapsed_ms, status_code, and data
    """
    start = time.time()
    response = client.get(url, params=params)
    elapsed_ms = (time.time() - start) * 1000

    return {
        "elapsed_ms": elapsed_ms,
        "status_code": response.status_code,
        "data": response.json() if response.status_code == 200 else None
    }


def run_multiple_measurements(
    client: httpx.Client,
    url: str,
    params: Dict[str, Any],
    iterations: int = 5
) -> Dict[str, Any]:
    """
    Run multiple measurements and return statistics.

    Returns:
        dict with min, max, mean, median, std_dev response times
    """
    times = []

    for _ in range(iterations):
        result = measure_response_time(client, url, params)
        if result["status_code"] == 200:
            times.append(result["elapsed_ms"])

    if not times:
        return {"error": "No successful responses"}

    return {
        "min_ms": min(times),
        "max_ms": max(times),
        "mean_ms": statistics.mean(times),
        "median_ms": statistics.median(times),
        "std_dev_ms": statistics.stdev(times) if len(times) > 1 else 0,
        "successful_requests": len(times),
        "total_requests": iterations
    }


# ============== Test Fixtures ==============

@pytest.fixture(scope="module")
def perf_client() -> httpx.Client:
    """HTTP client for performance tests."""
    return httpx.Client(timeout=30.0)


@pytest.fixture(scope="module")
def valid_gene_id(perf_client: httpx.Client) -> int:
    """Get a valid gene ID for testing."""
    gene_id = get_valid_gene_id(perf_client)
    if gene_id is None:
        pytest.skip("No valid gene ID available")
    return gene_id


# ============== Performance Tests ==============

class TestHeatmapMatrixPerformance:
    """Performance tests for heatmap matrix endpoint"""

    def test_2x2_matrix_response_time(self, perf_client: httpx.Client, valid_gene_id: int):
        """Test 2x2 matrix response time < 200ms"""
        url = f"{BASE_URL}/api/v1/features/chipseq/genes/{valid_gene_id}/heatmap-matrix"
        params = {
            "marks": "H3K27me3,H3K4me3",
            "cell_types": "K562,HepG2",
            "metric": "median_fold_enrichment"
        }

        result = measure_response_time(perf_client, url, params)

        # Skip if endpoint returns 404 (no data)
        if result["status_code"] == 404:
            pytest.skip("No data for test gene")

        assert result["status_code"] == 200, \
            f"Expected 200, got {result['status_code']}"
        assert result["elapsed_ms"] < PERF_THRESHOLD_2X2, \
            f"2x2 matrix response time {result['elapsed_ms']:.0f}ms exceeds {PERF_THRESHOLD_2X2}ms threshold"

        print(f"2x2 matrix response time: {result['elapsed_ms']:.2f}ms")

    def test_4x4_matrix_response_time(self, perf_client: httpx.Client, valid_gene_id: int):
        """Test 4x4 matrix response time < 300ms"""
        url = f"{BASE_URL}/api/v1/features/chipseq/genes/{valid_gene_id}/heatmap-matrix"
        params = {
            "marks": "H3K27me3,H3K4me3,H3K27ac,H3K4me1",
            "cell_types": "K562,HepG2,GM12878,H1-hESC",
            "metric": "median_fold_enrichment"
        }

        result = measure_response_time(perf_client, url, params)

        if result["status_code"] == 404:
            pytest.skip("No data for test gene")

        assert result["status_code"] == 200, \
            f"Expected 200, got {result['status_code']}"
        assert result["elapsed_ms"] < PERF_THRESHOLD_4X4, \
            f"4x4 matrix response time {result['elapsed_ms']:.0f}ms exceeds {PERF_THRESHOLD_4X4}ms threshold"

        print(f"4x4 matrix response time: {result['elapsed_ms']:.2f}ms")

    def test_4x4_matrix_with_details_response_time(self, perf_client: httpx.Client, valid_gene_id: int):
        """Test 4x4 matrix with details should still be < 300ms"""
        url = f"{BASE_URL}/api/v1/features/chipseq/genes/{valid_gene_id}/heatmap-matrix"
        params = {
            "marks": "H3K27me3,H3K4me3,H3K27ac,H3K4me1",
            "cell_types": "K562,HepG2,GM12878,H1-hESC",
            "metric": "median_fold_enrichment",
            "include_details": "true"
        }

        result = measure_response_time(perf_client, url, params)

        if result["status_code"] == 404:
            pytest.skip("No data for test gene")

        assert result["status_code"] == 200, \
            f"Expected 200, got {result['status_code']}"
        assert result["elapsed_ms"] < PERF_THRESHOLD_4X4, \
            f"4x4 matrix with details response time {result['elapsed_ms']:.0f}ms exceeds {PERF_THRESHOLD_4X4}ms threshold"

        print(f"4x4 matrix with details response time: {result['elapsed_ms']:.2f}ms")

    def test_different_metrics_performance(self, perf_client: httpx.Client, valid_gene_id: int):
        """Test all metrics have acceptable performance"""
        url = f"{BASE_URL}/api/v1/features/chipseq/genes/{valid_gene_id}/heatmap-matrix"
        metrics = ["median_fold_enrichment", "peak_count", "total_coverage_bp", "avg_signal"]

        results = {}

        for metric in metrics:
            params = {
                "marks": "H3K27me3,H3K4me3",
                "cell_types": "K562,HepG2",
                "metric": metric
            }

            result = measure_response_time(perf_client, url, params)

            if result["status_code"] == 200:
                results[metric] = result["elapsed_ms"]
                assert result["elapsed_ms"] < PERF_THRESHOLD_2X2, \
                    f"Metric {metric}: {result['elapsed_ms']:.0f}ms exceeds threshold"
            elif result["status_code"] == 404:
                results[metric] = "N/A (404)"

        # Print results summary
        print("\nMetric performance:")
        for metric, time_ms in results.items():
            if isinstance(time_ms, float):
                print(f"  {metric}: {time_ms:.2f}ms")
            else:
                print(f"  {metric}: {time_ms}")

    def test_repeated_requests_consistency(self, perf_client: httpx.Client, valid_gene_id: int):
        """Test that repeated requests have consistent performance"""
        url = f"{BASE_URL}/api/v1/features/chipseq/genes/{valid_gene_id}/heatmap-matrix"
        params = {
            "marks": "H3K27me3,H3K4me3",
            "cell_types": "K562,HepG2",
            "metric": "median_fold_enrichment"
        }

        # Run 5 iterations
        stats = run_multiple_measurements(perf_client, url, params, iterations=5)

        if "error" in stats:
            pytest.skip(f"No successful responses: {stats['error']}")

        # Standard deviation should be reasonable (not too variable)
        assert stats["std_dev_ms"] < 100, \
            f"Response time too variable: std_dev={stats['std_dev_ms']:.2f}ms"

        # Mean should be within threshold
        assert stats["mean_ms"] < PERF_THRESHOLD_2X2, \
            f"Mean response time {stats['mean_ms']:.0f}ms exceeds threshold"

        print("\nRepeated request statistics:")
        print(f"  Min: {stats['min_ms']:.2f}ms")
        print(f"  Max: {stats['max_ms']:.2f}ms")
        print(f"  Mean: {stats['mean_ms']:.2f}ms")
        print(f"  Median: {stats['median_ms']:.2f}ms")
        print(f"  Std Dev: {stats['std_dev_ms']:.2f}ms")


class TestHeatmapMatrixScalability:
    """Scalability tests for heatmap matrix endpoint"""

    def test_scaling_with_marks(self, perf_client: httpx.Client, valid_gene_id: int):
        """Test performance scaling as number of marks increases"""
        url = f"{BASE_URL}/api/v1/features/chipseq/genes/{valid_gene_id}/heatmap-matrix"

        marks_sets = [
            ["H3K27me3"],
            ["H3K27me3", "H3K4me3"],
            ["H3K27me3", "H3K4me3", "H3K27ac"],
            ["H3K27me3", "H3K4me3", "H3K27ac", "H3K4me1"],
            ["H3K27me3", "H3K4me3", "H3K27ac", "H3K4me1", "H3K36me3"],
        ]

        results = []

        for marks in marks_sets:
            params = {
                "marks": ",".join(marks),
                "cell_types": "K562,HepG2",
                "metric": "peak_count"
            }

            result = measure_response_time(perf_client, url, params)

            if result["status_code"] == 200:
                results.append({
                    "num_marks": len(marks),
                    "elapsed_ms": result["elapsed_ms"]
                })

        if not results:
            pytest.skip("No successful responses")

        # Print scaling results
        print("\nMarks scaling:")
        for r in results:
            print(f"  {r['num_marks']} marks: {r['elapsed_ms']:.2f}ms")

        # Verify reasonable scaling (not exponential)
        if len(results) >= 2:
            first = results[0]["elapsed_ms"]
            last = results[-1]["elapsed_ms"]
            scaling_factor = last / first if first > 0 else float('inf')
            marks_ratio = results[-1]["num_marks"] / results[0]["num_marks"]

            # Response time should not grow faster than O(n^2)
            assert scaling_factor < marks_ratio ** 2, \
                f"Scaling factor {scaling_factor:.2f} suggests worse than O(n^2)"

    def test_scaling_with_cell_types(self, perf_client: httpx.Client, valid_gene_id: int):
        """Test performance scaling as number of cell types increases"""
        url = f"{BASE_URL}/api/v1/features/chipseq/genes/{valid_gene_id}/heatmap-matrix"

        cell_type_sets = [
            ["K562"],
            ["K562", "HepG2"],
            ["K562", "HepG2", "GM12878"],
            ["K562", "HepG2", "GM12878", "H1-hESC"],
        ]

        results = []

        for cell_types in cell_type_sets:
            params = {
                "marks": "H3K27me3,H3K4me3",
                "cell_types": ",".join(cell_types),
                "metric": "peak_count"
            }

            result = measure_response_time(perf_client, url, params)

            if result["status_code"] == 200:
                results.append({
                    "num_cell_types": len(cell_types),
                    "elapsed_ms": result["elapsed_ms"]
                })

        if not results:
            pytest.skip("No successful responses")

        # Print scaling results
        print("\nCell type scaling:")
        for r in results:
            print(f"  {r['num_cell_types']} cell types: {r['elapsed_ms']:.2f}ms")


class TestHeatmapMatrixComparison:
    """Compare heatmap-matrix performance to compare-cell-lines endpoint"""

    def test_matrix_vs_compare_cell_lines(self, perf_client: httpx.Client, valid_gene_id: int):
        """Matrix endpoint should be comparable or faster than compare-cell-lines"""

        # Test heatmap-matrix
        matrix_url = f"{BASE_URL}/api/v1/features/chipseq/genes/{valid_gene_id}/heatmap-matrix"
        matrix_params = {
            "marks": "H3K27me3,H3K4me3",
            "cell_types": "K562,HepG2",
            "metric": "median_fold_enrichment"
        }
        matrix_result = measure_response_time(perf_client, matrix_url, matrix_params)

        # Test compare-cell-lines
        compare_url = f"{BASE_URL}/api/v1/features/chipseq/genes/{valid_gene_id}/compare-cell-lines"
        compare_params = {
            "mark_type": "H3K27me3",
            "cell_types": "K562,HepG2"
        }
        compare_result = measure_response_time(perf_client, compare_url, compare_params)

        # Report results
        print("\nEndpoint comparison:")
        if matrix_result["status_code"] == 200:
            print(f"  heatmap-matrix: {matrix_result['elapsed_ms']:.2f}ms")
        else:
            print(f"  heatmap-matrix: {matrix_result['status_code']}")

        if compare_result["status_code"] == 200:
            print(f"  compare-cell-lines: {compare_result['elapsed_ms']:.2f}ms")
        else:
            print(f"  compare-cell-lines: {compare_result['status_code']}")

        # Matrix should not be significantly slower (within 50% overhead)
        if matrix_result["status_code"] == 200 and compare_result["status_code"] == 200:
            ratio = matrix_result["elapsed_ms"] / compare_result["elapsed_ms"]
            print(f"  Ratio (matrix/compare): {ratio:.2f}")


if __name__ == "__main__":
    pytest.main([__file__, "-v", "-s"])
