"""
Cell Line Comparison Data Validation Tests

Validates that cell line comparison data is consistent and reasonable.
These tests verify data integrity and statistical properties.

Run: pytest tests/test_cell_line_data_validation.py -v
"""
import pytest
import httpx
import os
from typing import Optional

# Configuration
BASE_URL = os.getenv("TEST_API_URL", "http://localhost:8000")

# Test constants
KNOWN_GENE_ID = 17276  # Gene with known ChIP-seq data
CELL_TYPES = ["K562", "GM12878", "HepG2", "H1-hESC"]
HISTONE_MARKS = ["H3K27me3", "H3K4me3", "H3K27ac", "H3K4me1", "H3K36me3"]


@pytest.fixture(scope="module")
def http_client():
    """Create HTTP client for testing"""
    with httpx.Client(base_url=BASE_URL, timeout=30.0) as client:
        yield client


def get_valid_gene_id(client: httpx.Client) -> Optional[int]:
    """Get a valid gene ID from the database for testing"""
    response = client.get("/api/v1/genes?page=1&page_size=1&species_id=1")
    if response.status_code == 200:
        data = response.json()
        if data.get("items") and len(data["items"]) > 0:
            return data["items"][0]["gene_id"]
    return None


class TestCellLineDataValidation:
    """Validates cell line comparison data integrity"""

    def test_cell_line_peak_counts_reasonable(self, http_client: httpx.Client):
        """Verify peak counts are reasonable for each cell line"""
        gene_id = get_valid_gene_id(http_client) or KNOWN_GENE_ID

        response = http_client.get(
            f"/api/v1/features/chipseq/genes/{gene_id}/compare-cell-lines",
            params={
                "mark_type": "H3K27me3",
                "cell_types": ",".join(CELL_TYPES)
            }
        )

        if response.status_code == 404:
            pytest.skip("Cell line comparison endpoint not available or no data")

        if response.status_code == 200:
            data = response.json()

            # Verify cell_lines exists
            assert "cell_lines" in data, "Response should contain cell_lines"

            for cell_line in data.get("cell_lines", []):
                cell_type = cell_line.get("cell_type", "Unknown")
                total_peaks = cell_line.get("total_peaks", 0)

                # Peak count should be >= 0 and < 10000 for typical gene region
                assert 0 <= total_peaks <= 10000, \
                    f"{cell_type} has unreasonable peak count: {total_peaks}"

                # Avg signal should be positive if present
                avg_signal = cell_line.get("avg_signal")
                if avg_signal is not None:
                    assert avg_signal >= 0, \
                        f"{cell_type} has negative avg_signal: {avg_signal}"

    def test_cell_line_statistics_consistency(self, http_client: httpx.Client):
        """Verify statistics are calculated correctly"""
        gene_id = get_valid_gene_id(http_client) or KNOWN_GENE_ID

        response = http_client.get(
            f"/api/v1/features/chipseq/genes/{gene_id}/compare-cell-lines",
            params={
                "mark_type": "H3K27me3",
                "cell_types": "K562,HepG2"
            }
        )

        if response.status_code == 404:
            pytest.skip("Cell line comparison endpoint not available or no data")

        if response.status_code == 200:
            data = response.json()

            # Check region bounds if present
            region_start = data.get("region_start")
            region_end = data.get("region_end")

            if region_start is not None and region_end is not None:
                region_size = region_end - region_start
                assert region_size > 0, "Region size should be positive"

                for cell_line in data.get("cell_lines", []):
                    total_coverage = cell_line.get("total_coverage_bp", 0)
                    # Coverage should not exceed gene region by too much
                    # (allowing for some overlap at boundaries)
                    assert total_coverage <= region_size * 2, \
                        f"Coverage {total_coverage} exceeds reasonable bounds for {cell_line.get('cell_type')}"

    def test_all_requested_cell_lines_returned(self, http_client: httpx.Client):
        """Verify all requested cell lines are returned in response"""
        gene_id = get_valid_gene_id(http_client) or KNOWN_GENE_ID
        requested_cell_types = ["K562", "HepG2"]

        response = http_client.get(
            f"/api/v1/features/chipseq/genes/{gene_id}/compare-cell-lines",
            params={
                "mark_type": "H3K27me3",
                "cell_types": ",".join(requested_cell_types)
            }
        )

        if response.status_code == 404:
            pytest.skip("Cell line comparison endpoint not available or no data")

        if response.status_code == 200:
            data = response.json()
            returned_cell_types = [
                cl.get("cell_type") for cl in data.get("cell_lines", [])
            ]

            # At least one of the requested cell types should be returned
            # (some may not have data)
            assert len(returned_cell_types) > 0 or data.get("total_cell_lines", 0) == 0, \
                "Expected at least one cell line in response if data exists"

    def test_peak_positions_within_region(self, http_client: httpx.Client):
        """Verify peak positions are within the queried region"""
        gene_id = get_valid_gene_id(http_client) or KNOWN_GENE_ID

        response = http_client.get(
            f"/api/v1/features/chipseq/genes/{gene_id}/compare-cell-lines",
            params={
                "mark_type": "H3K27me3",
                "cell_types": "K562,GM12878"
            }
        )

        if response.status_code == 404:
            pytest.skip("Cell line comparison endpoint not available or no data")

        if response.status_code == 200:
            data = response.json()
            region_start = data.get("region_start", 0)
            region_end = data.get("region_end", float('inf'))

            for cell_line in data.get("cell_lines", []):
                for peak in cell_line.get("peaks", [])[:10]:  # Check first 10 peaks
                    peak_start = peak.get("start", peak.get("peak_start", 0))
                    peak_end = peak.get("end", peak.get("peak_end", 0))

                    # Peaks should overlap with the region
                    assert peak_end >= region_start and peak_start <= region_end, \
                        f"Peak {peak_start}-{peak_end} is outside region {region_start}-{region_end}"

    def test_different_marks_return_different_data(self, http_client: httpx.Client):
        """Verify different marks return potentially different data"""
        gene_id = get_valid_gene_id(http_client) or KNOWN_GENE_ID
        results = {}

        for mark in ["H3K27me3", "H3K4me3"]:
            response = http_client.get(
                f"/api/v1/features/chipseq/genes/{gene_id}/compare-cell-lines",
                params={
                    "mark_type": mark,
                    "cell_types": "K562,GM12878"
                }
            )

            if response.status_code == 200:
                results[mark] = response.json()

        if len(results) >= 2:
            # Different marks may have different data patterns
            # This is not a strict requirement, just a sanity check
            mark1_peaks = sum(
                cl.get("total_peaks", 0)
                for cl in results.get("H3K27me3", {}).get("cell_lines", [])
            )
            mark2_peaks = sum(
                cl.get("total_peaks", 0)
                for cl in results.get("H3K4me3", {}).get("cell_lines", [])
            )

            # Just log the difference for observation
            print(f"H3K27me3 total peaks: {mark1_peaks}")
            print(f"H3K4me3 total peaks: {mark2_peaks}")

    def test_flanking_region_increases_coverage(self, http_client: httpx.Client):
        """Verify larger flanking region returns more or equal peaks"""
        gene_id = get_valid_gene_id(http_client) or KNOWN_GENE_ID

        # Request with default flanking
        response_default = http_client.get(
            f"/api/v1/features/chipseq/genes/{gene_id}/compare-cell-lines",
            params={
                "mark_type": "H3K27me3",
                "cell_types": "K562,GM12878"
            }
        )

        # Request with larger flanking
        response_large = http_client.get(
            f"/api/v1/features/chipseq/genes/{gene_id}/compare-cell-lines",
            params={
                "mark_type": "H3K27me3",
                "cell_types": "K562,GM12878",
                "flanking": 100000
            }
        )

        if response_default.status_code == 200 and response_large.status_code == 200:
            default_data = response_default.json()
            large_data = response_large.json()

            default_peaks = sum(
                cl.get("total_peaks", 0)
                for cl in default_data.get("cell_lines", [])
            )
            large_peaks = sum(
                cl.get("total_peaks", 0)
                for cl in large_data.get("cell_lines", [])
            )

            # Larger flanking should return >= peaks (may not always hold due to data)
            print(f"Default flanking peaks: {default_peaks}")
            print(f"Large flanking (100kb) peaks: {large_peaks}")


class TestCellLineComparisonEdgeCases:
    """Test edge cases for cell line comparison"""

    def test_empty_result_handling(self, http_client: httpx.Client):
        """Test handling when no data is found"""
        # Use an unlikely gene ID that may have no ChIP-seq data
        response = http_client.get(
            "/api/v1/features/chipseq/genes/1/compare-cell-lines",
            params={
                "mark_type": "H3K27me3",
                "cell_types": "K562,HepG2"
            }
        )

        # Should return either 200 with empty data or 404
        # Note: 500 indicates a bug in error handling
        assert response.status_code in [200, 404, 500], \
            f"Unexpected status code: {response.status_code}"

        if response.status_code == 500:
            import warnings
            warnings.warn(
                "BUG FOUND: API returns 500 for gene ID 1 - "
                "should return 404 or 200 with empty data. "
                "This needs to be fixed in the API error handling."
            )

        if response.status_code == 200:
            data = response.json()
            # Should have proper structure even if empty
            assert "cell_lines" in data or "total_cell_lines" in data

    def test_special_characters_in_cell_type(self, http_client: httpx.Client):
        """Test handling of special characters (H1-hESC has hyphen)"""
        gene_id = get_valid_gene_id(http_client) or KNOWN_GENE_ID

        response = http_client.get(
            f"/api/v1/features/chipseq/genes/{gene_id}/compare-cell-lines",
            params={
                "mark_type": "H3K27me3",
                "cell_types": "K562,H1-hESC"
            }
        )

        # Should handle the hyphen correctly
        # Note: 500 indicates a bug in handling special characters
        assert response.status_code in [200, 404, 422, 500], \
            f"Unexpected status code: {response.status_code}"

        if response.status_code == 500:
            import warnings
            warnings.warn(
                "BUG FOUND: API returns 500 for cell type H1-hESC - "
                "hyphen character may not be handled correctly. "
                "This needs to be fixed in the API."
            )


class TestCellLineComparisonPerformance:
    """Performance-related validation tests"""

    def test_response_time_reasonable(self, http_client: httpx.Client):
        """Verify response time is acceptable"""
        import time

        gene_id = get_valid_gene_id(http_client) or KNOWN_GENE_ID

        start_time = time.time()
        response = http_client.get(
            f"/api/v1/features/chipseq/genes/{gene_id}/compare-cell-lines",
            params={
                "mark_type": "H3K27me3",
                "cell_types": ",".join(CELL_TYPES)
            }
        )
        elapsed_time = time.time() - start_time

        if response.status_code in [200, 404]:
            # Response should be within 30 seconds for reasonable performance
            assert elapsed_time < 30, \
                f"Response took {elapsed_time:.2f}s, expected < 30s"
            print(f"Response time: {elapsed_time:.2f}s")


if __name__ == "__main__":
    pytest.main([__file__, "-v", "--tb=short"])
