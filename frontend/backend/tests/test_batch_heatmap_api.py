"""
Batch Heatmap API Tests

Tests for batch gene heatmap matrix endpoint with multiple genes.
This module tests the bulk heatmap functionality including:
- Batch processing of 3, 10, 50 genes
- Performance requirements (10 genes < 1s)
- Response structure validation
- Error handling for invalid inputs

Run: pytest tests/test_batch_heatmap_api.py -v
"""
import pytest
import httpx
import time
from typing import List, Dict, Any
import os

# Mark all tests in this module as integration tests
pytestmark = pytest.mark.integration

# ============== Configuration ==============

BASE_URL = os.getenv("TEST_API_URL", "http://localhost:8000")
API_PREFIX = "/api/v1"

# Performance thresholds (in milliseconds)
PERF_THRESHOLD_BATCH_3 = 500    # 3 genes < 500ms
PERF_THRESHOLD_BATCH_10 = 1000  # 10 genes < 1000ms (1s)
PERF_THRESHOLD_BATCH_50 = 3000  # 50 genes < 3000ms (3s)

# Test gene IDs
TEST_GENE_IDS = [17276, 17277, 17278, 17279, 17280, 17281, 17282, 17283, 17284, 17285]


# ============== Helper Functions ==============

def get_valid_gene_ids(client: httpx.Client, limit: int = 10) -> List[int]:
    """Get valid gene IDs from the database for testing."""
    response = client.get(
        f"{BASE_URL}{API_PREFIX}/genes",
        params={"page": 1, "page_size": limit, "species_id": 1}
    )
    if response.status_code == 200:
        data = response.json()
        if data.get("items") and len(data["items"]) > 0:
            return [item["gene_id"] for item in data["items"][:limit]]
    return []


def measure_batch_response_time(
    client: httpx.Client,
    gene_ids: List[int],
    marks: str = "H3K27me3,H3K4me3",
    cell_types: str = "K562,HepG2"
) -> Dict[str, Any]:
    """
    Measure the response time for batch heatmap request.

    Returns:
        dict with elapsed_ms, status_code, data, and row count
    """
    url = f"{BASE_URL}{API_PREFIX}/features/chipseq/genes/batch-heatmap-matrix"
    payload = {
        "gene_ids": gene_ids,
        "marks": [m.strip() for m in marks.split(",") if m.strip()],
        "cell_types": [c.strip() for c in cell_types.split(",") if c.strip()],
        "metric": "median_fold_enrichment"
    }

    start = time.time()
    response = client.post(url, json=payload)
    elapsed_ms = (time.time() - start) * 1000

    data = response.json() if response.status_code == 200 else None

    return {
        "elapsed_ms": elapsed_ms,
        "status_code": response.status_code,
        "data": data,
        "gene_count": len(gene_ids),
        "expected_rows": len(gene_ids),
        "actual_rows": len(data.get("genes", [])) if data else 0
    }


# ============== Test Fixtures ==============

@pytest.fixture(scope="module")
def batch_client() -> httpx.Client:
    """HTTP client for batch tests."""
    return httpx.Client(timeout=30.0)


@pytest.fixture(scope="module")
def batch_gene_ids(batch_client: httpx.Client) -> List[int]:
    """Get valid gene IDs for batch testing."""
    gene_ids = get_valid_gene_ids(batch_client, limit=50)
    if not gene_ids or len(gene_ids) < 3:
        pytest.skip("Need at least 3 valid gene IDs for batch tests")
    return gene_ids


# ============== Batch Heatmap Tests ==============

class TestBatchHeatmapAPI:
    """API tests for batch heatmap functionality"""

    def test_batch_3_genes_basic(self, batch_client: httpx.Client, batch_gene_ids: List[int]):
        """Test batch heatmap with 3 genes - basic functionality"""
        gene_ids = batch_gene_ids[:3]
        result = measure_batch_response_time(batch_client, gene_ids)

        # Skip if endpoint returns 404 (no data)
        if result["status_code"] == 404:
            pytest.skip("Batch heatmap endpoint not available")

        assert result["status_code"] == 200, \
            f"Expected 200, got {result['status_code']}"
        assert result["data"] is not None, \
            "Response data should not be None"
        assert "genes" in result["data"], \
            "Response should contain 'genes' field"
        assert len(result["data"]["genes"]) > 0, \
            "Batch response should contain at least one gene matrix"

        print(f"Batch 3 genes response time: {result['elapsed_ms']:.2f}ms")

    def test_batch_10_genes_performance(self, batch_client: httpx.Client, batch_gene_ids: List[int]):
        """Test batch heatmap with 10 genes - performance requirement < 1s"""
        gene_ids = batch_gene_ids[:10]
        result = measure_batch_response_time(batch_client, gene_ids)

        if result["status_code"] == 404:
            pytest.skip("Batch heatmap endpoint not available")

        assert result["status_code"] == 200, \
            f"Expected 200, got {result['status_code']}"
        assert result["elapsed_ms"] < PERF_THRESHOLD_BATCH_10, \
            f"Batch 10 genes response time {result['elapsed_ms']:.0f}ms exceeds {PERF_THRESHOLD_BATCH_10}ms threshold"

        print(f"Batch 10 genes response time: {result['elapsed_ms']:.2f}ms (target: <1000ms)")

    def test_batch_50_genes_performance(self, batch_client: httpx.Client, batch_gene_ids: List[int]):
        """Test batch heatmap with 50 genes - performance requirement < 3s"""
        if len(batch_gene_ids) < 50:
            pytest.skip(f"Need 50 genes, only have {len(batch_gene_ids)}")

        gene_ids = batch_gene_ids[:50]
        result = measure_batch_response_time(batch_client, gene_ids)

        if result["status_code"] == 404:
            pytest.skip("Batch heatmap endpoint not available")

        assert result["status_code"] == 200, \
            f"Expected 200, got {result['status_code']}"
        assert result["elapsed_ms"] < PERF_THRESHOLD_BATCH_50, \
            f"Batch 50 genes response time {result['elapsed_ms']:.0f}ms exceeds {PERF_THRESHOLD_BATCH_50}ms threshold"

        print(f"Batch 50 genes response time: {result['elapsed_ms']:.2f}ms (target: <3000ms)")

    def test_batch_response_structure(self, batch_client: httpx.Client, batch_gene_ids: List[int]):
        """Test batch heatmap response structure validation"""
        gene_ids = batch_gene_ids[:5]
        result = measure_batch_response_time(batch_client, gene_ids)

        if result["status_code"] == 404:
            pytest.skip("Batch heatmap endpoint not available")

        assert result["status_code"] == 200
        data = result["data"]

        # Validate top-level structure
        assert isinstance(data, dict), "Response should be a dictionary"
        assert "genes" in data, "Response should have 'genes' key"
        assert isinstance(data["genes"], list), "'genes' should be a list"

        # Validate each matrix structure
        for i, matrix in enumerate(data["genes"]):
            assert isinstance(matrix, dict), f"Matrix[{i}] should be a dictionary"
            assert "gene_id" in matrix, f"Matrix[{i}] should have 'gene_id'"
            assert "gene_name" in matrix, f"Matrix[{i}] should have 'gene_name'"
            assert "matrix" in matrix, f"Matrix[{i}] should have 'matrix'"
            assert isinstance(matrix["matrix"], list), f"Matrix[{i}] matrix should be a list"

        print(f"Response structure validated for {len(data['genes'])} matrices")

    def test_batch_different_marks(self, batch_client: httpx.Client, batch_gene_ids: List[int]):
        """Test batch heatmap with different histone marks"""
        gene_ids = batch_gene_ids[:5]
        marks_list = [
            "H3K27me3",
            "H3K27me3,H3K4me3",
            "H3K27me3,H3K4me3,H3K27ac",
        ]

        for marks in marks_list:
            result = measure_batch_response_time(
                batch_client,
                gene_ids,
                marks=marks,
                cell_types="K562,HepG2"
            )

            if result["status_code"] == 404:
                continue

            assert result["status_code"] == 200, \
                f"Failed for marks={marks}"

        print(f"Tested {len(marks_list)} different mark configurations")

    def test_batch_empty_gene_ids(self, batch_client: httpx.Client):
        """Test batch heatmap with empty gene IDs - should fail"""
        url = f"{BASE_URL}{API_PREFIX}/features/chipseq/genes/batch-heatmap-matrix"
        payload = {
            "gene_ids": [],
            "marks": ["H3K27me3", "H3K4me3"],
            "cell_types": ["K562", "HepG2"],
            "metric": "median_fold_enrichment"
        }

        response = batch_client.post(url, json=payload)

        # Schema min_length=1 会返回 422；也可能被后端拦截为 400
        assert response.status_code in [400, 422], \
            f"Expected 400 or 422, got {response.status_code}"

    def test_batch_invalid_gene_ids(self, batch_client: httpx.Client):
        """Test batch heatmap with invalid gene IDs - should fail gracefully"""
        url = f"{BASE_URL}{API_PREFIX}/features/chipseq/genes/batch-heatmap-matrix"
        payload = {
            "gene_ids": [999999, 999998, 999997],
            "marks": ["H3K27me3", "H3K4me3"],
            "cell_types": ["K562", "HepG2"],
            "metric": "median_fold_enrichment"
        }

        response = batch_client.post(url, json=payload)

        assert response.status_code == 200, \
            f"Expected 200, got {response.status_code}"

        data = response.json()
        assert "genes" in data and "failed_genes" in data, \
            "Response should include genes and failed_genes"
        assert set(payload["gene_ids"]).issubset(set(data.get("failed_genes", []))), \
            "All invalid gene IDs should be reported as failed"

    def test_batch_mixed_valid_invalid_genes(self, batch_client: httpx.Client, batch_gene_ids: List[int]):
        """Test batch heatmap with mix of valid and invalid gene IDs"""
        valid_ids = batch_gene_ids[:3]
        invalid_ids = [999999, 999998]
        mixed_ids = valid_ids + invalid_ids

        result = measure_batch_response_time(batch_client, mixed_ids)

        # Should still return 200 with valid genes processed
        assert result["status_code"] in [200, 404], \
            f"Expected 200 or 404, got {result['status_code']}"


class TestBatchHeatmapScalability:
    """Scalability tests for batch heatmap processing"""

    def test_batch_scaling_performance(self, batch_client: httpx.Client, batch_gene_ids: List[int]):
        """Test performance scaling with increasing batch size"""
        batch_sizes = [3, 5, 10]
        results = []

        for size in batch_sizes:
            if size > len(batch_gene_ids):
                continue

            gene_ids = batch_gene_ids[:size]
            result = measure_batch_response_time(batch_client, gene_ids)

            if result["status_code"] == 200:
                results.append({
                    "size": size,
                    "elapsed_ms": result["elapsed_ms"],
                    "time_per_gene": result["elapsed_ms"] / size
                })

        # Verify reasonable scaling
        if len(results) >= 2:
            # Time per gene should be relatively consistent
            first_tpg = results[0]["time_per_gene"]
            last_tpg = results[-1]["time_per_gene"]

            # Allow up to 50% variance in time per gene
            ratio = last_tpg / first_tpg if first_tpg > 0 else 1
            assert ratio < 1.5, \
                f"Time per gene scaling issue: {first_tpg:.2f}ms -> {last_tpg:.2f}ms (ratio: {ratio:.2f})"

        print("\nBatch scaling results:")
        for r in results:
            print(f"  {r['size']} genes: {r['elapsed_ms']:.2f}ms ({r['time_per_gene']:.2f}ms/gene)")


if __name__ == "__main__":
    pytest.main([__file__, "-v", "-s"])
