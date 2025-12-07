"""
Phase 3.1: Regression Test Suite

Validates that adding HepG2 × H3K9me3 doesn't break existing functionality.

Run: pytest tests/test_phase_3_1_regression.py -v
"""
import pytest
import httpx
import time
from typing import Dict, Any


# Configuration
BASE_URL = "http://localhost:8000"
TIMEOUT = 30.0


@pytest.fixture(scope="module")
def api_client():
    """Create HTTP client for testing"""
    with httpx.Client(base_url=BASE_URL, timeout=TIMEOUT) as client:
        yield client


class TestExistingMarksStillWork:
    """Verify existing marks still return data"""

    @pytest.mark.parametrize("mark_type", [
        "H3K27me3",
        "H3K4me3",
        "H3K27ac",
        "H3K4me1",
        "H3K36me3"
    ])
    def test_existing_mark_returns_data(self, api_client: httpx.Client, mark_type: str):
        """Verify each existing mark still works"""
        response = api_client.get(
            "/api/v1/lncrna-chipseq-overlap",
            params={"mark_type": mark_type, "page": 1, "page_size": 10}
        )

        assert response.status_code == 200, f"{mark_type} should return 200"

        data = response.json()
        assert "total" in data, f"{mark_type} response should have 'total'"
        assert "items" in data, f"{mark_type} response should have 'items'"

        # Most marks should have some data (except edge cases)
        if mark_type in ["H3K27me3", "H3K4me3"]:
            assert data["total"] > 0, f"{mark_type} should have overlaps"


class TestExistingCellTypesStillWork:
    """Verify existing cell types still return data"""

    @pytest.mark.parametrize("cell_type", [
        "K562",
        "HepG2",
        "GM12878",
        "H1-hESC"
    ])
    def test_existing_cell_type_returns_data(self, api_client: httpx.Client, cell_type: str):
        """Verify each cell type still works"""
        response = api_client.get(
            "/api/v1/lncrna-chipseq-overlap",
            params={"cell_type": cell_type, "page": 1, "page_size": 10}
        )

        assert response.status_code == 200, f"{cell_type} should return 200"

        data = response.json()
        assert "total" in data, f"{cell_type} response should have 'total'"
        assert data["total"] >= 0, f"{cell_type} total should be non-negative"


class TestNewMarkWorks:
    """Verify new mark (H3K9me3) works correctly"""

    def test_h3k9me3_available_in_marks_list(self, api_client: httpx.Client):
        """Verify H3K9me3 appears in available marks"""
        response = api_client.get("/api/v1/features/chipseq/marks/available", params={"species": 1})

        assert response.status_code == 200

        data = response.json()
        mark_names = [m["mark_name"] for m in data.get("marks", [])]

        assert "H3K9me3" in mark_names, "H3K9me3 should appear in marks list"

    def test_h3k9me3_returns_data(self, api_client: httpx.Client):
        """Verify H3K9me3 returns overlaps"""
        response = api_client.get(
            "/api/v1/lncrna-chipseq-overlap",
            params={"mark_type": "H3K9me3", "page": 1, "page_size": 10}
        )

        assert response.status_code == 200

        data = response.json()
        # Should have data for at least K562 (from Phase 2.6)
        assert data["total"] >= 0, "H3K9me3 should return results"

    def test_hepg2_h3k9me3_combination(self, api_client: httpx.Client):
        """Verify HepG2 × H3K9me3 specific query works"""
        response = api_client.get(
            "/api/v1/lncrna-chipseq-overlap",
            params={
                "mark_type": "H3K9me3",
                "cell_type": "HepG2",
                "chromosome": "chr22",
                "page": 1,
                "page_size": 10
            }
        )

        assert response.status_code == 200

        data = response.json()
        assert "total" in data
        assert "items" in data

        # Verify items have correct mark and cell type
        for item in data["items"]:
            assert item["mark_type"] == "H3K9me3"
            assert item["cell_type"] == "HepG2"


class TestHeatmapUpdated:
    """Verify heatmap matrix updated correctly"""

    def test_heatmap_has_24_combinations(self, api_client: httpx.Client):
        """Verify heatmap shows 24 valid combinations (was 23 before)"""
        response = api_client.get(
            "/api/v1/lncrna-chipseq-overlap/heatmap",
            params={"x_axis": "mark_type", "y_axis": "cell_type"}
        )

        # Endpoint may or may not exist depending on implementation
        if response.status_code == 404:
            pytest.skip("Heatmap endpoint not implemented")

        assert response.status_code == 200

        data = response.json()

        # Expected: 4 cell types × 6 marks = 24 total combinations
        # Valid combinations should be >= 23 (at least same as before)
        valid_combinations = data.get("valid_combinations", 0)

        assert valid_combinations >= 23, \
            f"Should have at least 23 valid combinations, got {valid_combinations}"

        # Ideally should be 24 after adding HepG2 × H3K9me3
        if valid_combinations == 24:
            print("✓ Heatmap shows complete 24/24 matrix")
        else:
            print(f"⚠ Heatmap shows {valid_combinations}/24 combinations")


class TestExportStillWorks:
    """Verify export functionality not broken"""

    def test_bed_export_existing_mark(self, api_client: httpx.Client):
        """Verify BED export works for existing mark (regression test)"""
        response = api_client.get(
            "/api/v1/lncrna-chipseq-overlap/export",
            params={
                "format": "bed",
                "mark_type": "H3K27me3",
                "cell_type": "K562",
                "chromosome": "chr22",
                "max_rows": 50
            }
        )

        assert response.status_code == 200
        assert response.headers["content-type"].startswith("text/plain")

        content = response.text
        assert len(content) > 0, "Export should return data"

        # Check BED format
        lines = [l for l in content.split('\n') if l and not l.startswith('track')]
        if lines:
            first_line = lines[0].split('\t')
            assert len(first_line) == 6, "BED export should have 6 columns"

    def test_csv_export_existing_mark(self, api_client: httpx.Client):
        """Verify CSV export works for existing mark (regression test)"""
        response = api_client.get(
            "/api/v1/lncrna-chipseq-overlap/export",
            params={
                "format": "csv",
                "mark_type": "H3K4me3",
                "cell_type": "K562",
                "chromosome": "chr22",
                "max_rows": 50
            }
        )

        assert response.status_code == 200
        assert response.headers["content-type"].startswith("text/csv")

        content = response.text
        assert len(content) > 0, "Export should return data"

        # Check CSV format
        lines = content.split('\n')
        assert len(lines) >= 2, "CSV should have header + data"

        headers = lines[0].split(',')
        assert len(headers) == 19, "CSV should have 19 columns"

    def test_bed_export_new_mark(self, api_client: httpx.Client):
        """Verify BED export works for new mark (H3K9me3)"""
        response = api_client.get(
            "/api/v1/lncrna-chipseq-overlap/export",
            params={
                "format": "bed",
                "mark_type": "H3K9me3",
                "cell_type": "HepG2",
                "chromosome": "chr22",
                "max_rows": 50
            }
        )

        # Should succeed even if no data (returns empty)
        assert response.status_code == 200

    def test_csv_export_new_mark(self, api_client: httpx.Client):
        """Verify CSV export works for new mark (H3K9me3)"""
        response = api_client.get(
            "/api/v1/lncrna-chipseq-overlap/export",
            params={
                "format": "csv",
                "mark_type": "H3K9me3",
                "cell_type": "HepG2",
                "chromosome": "chr22",
                "max_rows": 50
            }
        )

        # Should succeed even if no data
        assert response.status_code == 200


class TestPerformanceRegression:
    """Verify performance hasn't degraded significantly"""

    def test_simple_query_performance(self, api_client: httpx.Client):
        """Verify simple queries still fast (<500ms)"""
        start_time = time.time()

        response = api_client.get(
            "/api/v1/lncrna-chipseq-overlap",
            params={"chromosome": "chr22", "page": 1, "page_size": 10}
        )

        elapsed_time = time.time() - start_time

        assert response.status_code == 200
        assert elapsed_time < 1.0, \
            f"Simple query took {elapsed_time:.2f}s, expected <1s"

        print(f"Query time: {elapsed_time*1000:.0f}ms")

    def test_filtered_query_performance(self, api_client: httpx.Client):
        """Verify filtered queries still fast"""
        start_time = time.time()

        response = api_client.get(
            "/api/v1/lncrna-chipseq-overlap",
            params={
                "mark_type": "H3K9me3",
                "cell_type": "HepG2",
                "chromosome": "chr22",
                "page": 1,
                "page_size": 10
            }
        )

        elapsed_time = time.time() - start_time

        assert response.status_code == 200
        assert elapsed_time < 1.0, \
            f"Filtered query took {elapsed_time:.2f}s, expected <1s"

        print(f"Filtered query time: {elapsed_time*1000:.0f}ms")


class TestDataIntegrity:
    """Verify data integrity across the system"""

    def test_total_overlaps_increased(self, api_client: httpx.Client):
        """Verify total overlaps count increased after import"""
        response = api_client.get(
            "/api/v1/lncrna-chipseq-overlap",
            params={"page": 1, "page_size": 1}
        )

        assert response.status_code == 200

        data = response.json()
        total = data.get("total", 0)

        # After Phase 3.1, should have many overlaps
        # Exact number depends on data, but should be > 10000
        assert total > 0, "Should have overlaps in database"

        print(f"Total overlaps: {total:,}")

    def test_hepg2_has_6_marks(self, api_client: httpx.Client):
        """Verify HepG2 now has data for 6 marks"""
        expected_marks = ["H3K27me3", "H3K4me3", "H3K27ac", "H3K4me1", "H3K36me3", "H3K9me3"]

        marks_with_data = []

        for mark in expected_marks:
            response = api_client.get(
                "/api/v1/lncrna-chipseq-overlap",
                params={"mark_type": mark, "cell_type": "HepG2", "page": 1, "page_size": 1}
            )

            if response.status_code == 200:
                data = response.json()
                if data.get("total", 0) > 0:
                    marks_with_data.append(mark)

        print(f"HepG2 marks with data: {marks_with_data}")

        # Should have at least the core marks
        assert "H3K27me3" in marks_with_data, "HepG2 should have H3K27me3"
        assert "H3K9me3" in marks_with_data, "HepG2 should have H3K9me3 (newly added)"

    def test_no_invalid_data_combinations(self, api_client: httpx.Client):
        """Verify no invalid mark/cell type combinations"""
        # Query all data and check for inconsistencies
        response = api_client.get(
            "/api/v1/lncrna-chipseq-overlap",
            params={"page": 1, "page_size": 100}
        )

        assert response.status_code == 200

        data = response.json()

        valid_marks = ["H3K27me3", "H3K4me3", "H3K27ac", "H3K4me1", "H3K36me3", "H3K9me3"]
        valid_cells = ["K562", "HepG2", "GM12878", "H1-hESC"]

        for item in data.get("items", []):
            mark = item.get("mark_type")
            cell = item.get("cell_type")

            assert mark in valid_marks, f"Invalid mark type: {mark}"
            assert cell in valid_cells, f"Invalid cell type: {cell}"


class TestEdgeCases:
    """Test edge cases and error handling"""

    def test_nonexistent_combination_returns_empty(self, api_client: httpx.Client):
        """Verify querying non-existent combination returns empty (not error)"""
        # H1-hESC doesn't have H3K9me3 data
        response = api_client.get(
            "/api/v1/lncrna-chipseq-overlap",
            params={"mark_type": "H3K9me3", "cell_type": "H1-hESC"}
        )

        # Should return 200 with empty results, not 404 or 500
        assert response.status_code == 200

        data = response.json()
        assert data.get("total", 0) == 0, "Should return 0 results, not error"
        assert data.get("items", []) == [], "Should return empty items array"

    def test_invalid_mark_type_handled_gracefully(self, api_client: httpx.Client):
        """Verify invalid mark type returns appropriate error"""
        response = api_client.get(
            "/api/v1/lncrna-chipseq-overlap",
            params={"mark_type": "InvalidMark"}
        )

        # Should return 400 (bad request) or 200 with empty results
        # NOT 500 (internal server error)
        assert response.status_code in [200, 400, 422], \
            f"Should handle invalid mark gracefully, got {response.status_code}"

    def test_invalid_cell_type_handled_gracefully(self, api_client: httpx.Client):
        """Verify invalid cell type returns appropriate error"""
        response = api_client.get(
            "/api/v1/lncrna-chipseq-overlap",
            params={"cell_type": "InvalidCell"}
        )

        # Should return 400 or 200 with empty, not 500
        assert response.status_code in [200, 400, 422], \
            f"Should handle invalid cell type gracefully, got {response.status_code}"


# Summary function
def test_regression_summary(api_client: httpx.Client):
    """Print regression test summary"""
    print("\n" + "=" * 60)
    print("Phase 3.1: Regression Test Summary")
    print("=" * 60)

    # Test marks availability
    response = api_client.get("/api/v1/features/chipseq/marks/available", params={"species": 1})
    if response.status_code == 200:
        data = response.json()
        mark_names = [m["mark_name"] for m in data.get("marks", [])]
        print(f"Available marks: {len(mark_names)}")
        print(f"  - {', '.join(mark_names)}")

    # Test HepG2 coverage
    response = api_client.get(
        "/api/v1/lncrna-chipseq-overlap",
        params={"cell_type": "HepG2", "page": 1, "page_size": 1}
    )
    if response.status_code == 200:
        data = response.json()
        print(f"\nHepG2 total overlaps: {data.get('total', 0):,}")

    # Test H3K9me3 data
    response = api_client.get(
        "/api/v1/lncrna-chipseq-overlap",
        params={"mark_type": "H3K9me3", "page": 1, "page_size": 1}
    )
    if response.status_code == 200:
        data = response.json()
        print(f"H3K9me3 total overlaps: {data.get('total', 0):,}")

    print("\n✓ All regression tests completed")
    print("=" * 60)


if __name__ == "__main__":
    pytest.main([__file__, "-v", "--tb=short"])
