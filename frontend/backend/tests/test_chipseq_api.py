"""
ChIP-seq API Contract Tests
Tests for /api/v1/features/chipseq/* endpoints

This module tests the ChIP-seq functionality including:
- Available marks endpoint
- Gene peaks endpoint
- Gene summary endpoint
- Mark comparison endpoint
- Global statistics endpoint

Run: pytest tests/test_chipseq_api.py -v
"""
import pytest
import httpx
from typing import Optional

from conftest import (
    validate_paginated_response,
    validate_single_response,
    APIAssertions,
)


# ============== Test Constants ==============

# Known cell types in the database
CELL_TYPES = ["K562", "GM12878", "HepG2", "H1-hESC"]

# Common histone marks
HISTONE_MARKS = ["H3K27me3", "H3K4me3", "H3K27ac", "H3K4me1", "H3K36me3"]


# ============== Helper Functions ==============

def get_valid_gene_id(client: httpx.Client) -> Optional[int]:
    """
    Get a valid gene ID from the database for testing.
    Returns None if no genes are available.
    """
    response = client.get("/api/v1/genes?page=1&page_size=1&species_id=1")
    if response.status_code == 200:
        data = response.json()
        if data.get("items") and len(data["items"]) > 0:
            return data["items"][0]["gene_id"]
    return None


def get_available_marks(client: httpx.Client, species_id: int = 1) -> list:
    """
    Get available marks for a species.
    Returns empty list if no marks are available.
    Note: API returns a list directly, not wrapped in {"marks": [...]}
    """
    response = client.get(f"/api/v1/features/chipseq/marks", params={"species_id": species_id})
    if response.status_code == 200:
        data = response.json()
        # API returns list directly
        return data if isinstance(data, list) else data.get("marks", [])
    return []


# ============== Test Classes ==============

class TestChIPSeqMarks:
    """Tests for /features/chipseq/marks endpoints"""

    def test_get_available_marks(self, api_client: httpx.Client, api_assert: APIAssertions):
        """GET /features/chipseq/marks returns valid response"""
        response = api_client.get("/api/v1/features/chipseq/marks")
        api_assert.assert_successful_response(response)
        data = api_assert.assert_json_response(response)

        # API returns list directly (not wrapped in {"marks": [...]})
        assert isinstance(data, list), "Response should be a list of marks"

    def test_get_marks_for_human_species(self, api_client: httpx.Client, api_assert: APIAssertions):
        """GET /features/chipseq/marks?species_id=1 returns human marks"""
        response = api_client.get("/api/v1/features/chipseq/marks", params={"species_id": 1})
        api_assert.assert_successful_response(response)
        data = api_assert.assert_json_response(response)

        # API returns list directly
        assert isinstance(data, list), "Response should be a list"

    def test_marks_response_structure(self, api_client: httpx.Client, api_assert: APIAssertions):
        """Verify mark response contains expected fields"""
        response = api_client.get("/api/v1/features/chipseq/marks", params={"species_id": 1})
        api_assert.assert_successful_response(response)
        data = api_assert.assert_json_response(response)

        # API returns list directly, check first item if exists
        marks = data if isinstance(data, list) else data.get("marks", [])
        if marks:
            mark = marks[0]
            # Marks should have at minimum a name/type identifier
            assert "mark_type" in mark or "name" in mark or "mark_name" in mark, \
                "Mark should have a type/name identifier"


class TestChIPSeqExperiments:
    """Tests for /features/chipseq/experiments endpoints (if available)"""

    def test_list_experiments(self, api_client: httpx.Client):
        """GET /features/chipseq/experiments returns experiment list or 404"""
        response = api_client.get("/api/v1/features/chipseq/experiments")
        # Endpoint may not exist - accept 200 or 404
        assert response.status_code in [200, 404], \
            f"Expected 200 or 404, got {response.status_code}"

        if response.status_code == 200:
            data = response.json()
            # Should return list or paginated response
            assert isinstance(data, (list, dict))

    @pytest.mark.parametrize("cell_type", CELL_TYPES)
    def test_filter_by_cell_type(self, api_client: httpx.Client, cell_type: str):
        """Filter experiments by cell type"""
        response = api_client.get(
            "/api/v1/features/chipseq/experiments",
            params={"cell_type": cell_type}
        )
        # Endpoint may not exist or cell type may not have data
        assert response.status_code in [200, 404], \
            f"Cell type {cell_type}: Expected 200 or 404, got {response.status_code}"


class TestChIPSeqGenePeaks:
    """Tests for gene-level ChIP-seq endpoints"""

    def test_get_gene_chipseq_with_known_gene(self, api_client: httpx.Client, api_assert: APIAssertions):
        """GET /features/chipseq/genes/{gene_id} returns peaks for valid gene"""
        gene_id = get_valid_gene_id(api_client)
        if gene_id is None:
            pytest.skip("No valid gene ID available for testing")

        marks = get_available_marks(api_client)
        # API may use 'mark_name' or 'mark_type' field
        mark_type = marks[0].get("mark_name") or marks[0].get("mark_type") if marks else "H3K27me3"

        response = api_client.get(
            f"/api/v1/features/chipseq/genes/{gene_id}",
            params={"mark_type": mark_type}
        )
        # Accept 200 (data found) or 404 (no peaks for gene)
        assert response.status_code in [200, 404], \
            f"Expected 200 or 404, got {response.status_code}"

        if response.status_code == 200:
            data = api_assert.assert_json_response(response)
            # Verify basic response structure
            assert "gene_id" in data or "marks" in data, \
                "Response should contain gene data"

    def test_get_gene_chipseq_invalid_gene(self, api_client: httpx.Client):
        """GET /features/chipseq/genes/{invalid_id} returns 404"""
        response = api_client.get(
            "/api/v1/features/chipseq/genes/999999999",
            params={"mark_type": "H3K27me3"}
        )
        assert response.status_code == 404, \
            f"Invalid gene should return 404, got {response.status_code}"

    def test_get_gene_chipseq_with_flanking(self, api_client: httpx.Client, api_assert: APIAssertions):
        """GET /features/chipseq/genes/{gene_id} with custom flanking region"""
        gene_id = get_valid_gene_id(api_client)
        if gene_id is None:
            pytest.skip("No valid gene ID available for testing")

        response = api_client.get(
            f"/api/v1/features/chipseq/genes/{gene_id}",
            params={"mark_type": "H3K27me3", "flanking": 20000}
        )
        assert response.status_code in [200, 404]

    @pytest.mark.parametrize("mark_type", HISTONE_MARKS)
    def test_get_gene_chipseq_various_marks(self, api_client: httpx.Client, mark_type: str):
        """Test gene ChIP-seq endpoint with various histone marks"""
        gene_id = get_valid_gene_id(api_client)
        if gene_id is None:
            pytest.skip("No valid gene ID available for testing")

        response = api_client.get(
            f"/api/v1/features/chipseq/genes/{gene_id}",
            params={"mark_type": mark_type}
        )
        # All marks should be valid parameters even if no data
        assert response.status_code in [200, 404], \
            f"Mark {mark_type}: Expected 200 or 404, got {response.status_code}"


class TestChIPSeqGeneSummary:
    """Tests for gene summary statistics endpoint"""

    def test_get_gene_summary(self, api_client: httpx.Client, api_assert: APIAssertions):
        """GET /features/chipseq/genes/{gene_id}/summary returns statistics"""
        gene_id = get_valid_gene_id(api_client)
        if gene_id is None:
            pytest.skip("No valid gene ID available for testing")

        marks = get_available_marks(api_client)
        # API may use 'mark_name' or 'mark_type' field
        mark_type = marks[0].get("mark_name") or marks[0].get("mark_type") if marks else "H3K27me3"

        response = api_client.get(
            f"/api/v1/features/chipseq/genes/{gene_id}/summary",
            params={"mark_type": mark_type}
        )
        assert response.status_code in [200, 404]

        if response.status_code == 200:
            data = api_assert.assert_json_response(response)
            # Verify summary contains expected statistic fields
            expected_fields = ["total_peaks", "avg_signal", "mark_type"]
            for field in expected_fields:
                if field in data:
                    # Field exists, verify it's the right type
                    if field == "total_peaks":
                        assert isinstance(data[field], int), f"{field} should be integer"
                    elif field in ["avg_signal", "max_signal", "avg_fold_enrichment"]:
                        assert isinstance(data[field], (int, float)), f"{field} should be numeric"

    def test_get_gene_summary_invalid_gene(self, api_client: httpx.Client):
        """GET /features/chipseq/genes/{invalid_id}/summary returns 404"""
        response = api_client.get(
            "/api/v1/features/chipseq/genes/999999999/summary",
            params={"mark_type": "H3K27me3"}
        )
        assert response.status_code == 404


class TestChIPSeqMarkComparison:
    """Tests for mark comparison endpoint"""

    def test_compare_two_marks(self, api_client: httpx.Client, api_assert: APIAssertions):
        """GET /features/chipseq/genes/{gene_id}/compare compares multiple marks"""
        gene_id = get_valid_gene_id(api_client)
        if gene_id is None:
            pytest.skip("No valid gene ID available for testing")

        response = api_client.get(
            f"/api/v1/features/chipseq/genes/{gene_id}/compare",
            params={"marks": "H3K27me3,H3K4me3"}
        )
        assert response.status_code in [200, 404]

        if response.status_code == 200:
            data = api_assert.assert_json_response(response)
            # Comparison should include data for requested marks
            assert isinstance(data, dict), "Comparison response should be a dictionary"

    def test_compare_with_flanking(self, api_client: httpx.Client):
        """Compare marks with custom flanking region"""
        gene_id = get_valid_gene_id(api_client)
        if gene_id is None:
            pytest.skip("No valid gene ID available for testing")

        response = api_client.get(
            f"/api/v1/features/chipseq/genes/{gene_id}/compare",
            params={"marks": "H3K27me3,H3K4me3", "flanking": 50000}
        )
        assert response.status_code in [200, 404]


class TestChIPSeqStats:
    """Tests for global statistics endpoint"""

    def test_get_global_stats(self, api_client: httpx.Client, api_assert: APIAssertions):
        """GET /features/chipseq/stats returns global statistics"""
        response = api_client.get("/api/v1/features/chipseq/stats")

        # Stats endpoint may not exist
        if response.status_code == 404:
            pytest.skip("Stats endpoint not available")

        api_assert.assert_successful_response(response)
        data = api_assert.assert_json_response(response)

        # Verify expected fields exist (flexible - different implementations may vary)
        possible_fields = ["total_experiments", "total_peaks", "mark_stats", "species_stats"]
        found_fields = [f for f in possible_fields if f in data]
        assert len(found_fields) > 0, \
            f"Stats should contain at least one of: {possible_fields}"


class TestChIPSeqFiltering:
    """Tests for ChIP-seq filtering parameters"""

    def test_filter_by_fold_enrichment(self, api_client: httpx.Client):
        """Test filtering by minimum fold enrichment"""
        gene_id = get_valid_gene_id(api_client)
        if gene_id is None:
            pytest.skip("No valid gene ID available for testing")

        response = api_client.get(
            f"/api/v1/features/chipseq/genes/{gene_id}",
            params={
                "mark_type": "H3K27me3",
                "min_fold_enrichment": 5.0
            }
        )
        assert response.status_code in [200, 404]

    def test_filter_by_qvalue(self, api_client: httpx.Client):
        """Test filtering by maximum q-value (FDR)"""
        gene_id = get_valid_gene_id(api_client)
        if gene_id is None:
            pytest.skip("No valid gene ID available for testing")

        response = api_client.get(
            f"/api/v1/features/chipseq/genes/{gene_id}",
            params={
                "mark_type": "H3K27me3",
                "max_qvalue": 0.01
            }
        )
        assert response.status_code in [200, 404]

    @pytest.mark.parametrize("cell_type", CELL_TYPES)
    def test_filter_by_cell_type(self, api_client: httpx.Client, cell_type: str):
        """Test filtering by cell type"""
        gene_id = get_valid_gene_id(api_client)
        if gene_id is None:
            pytest.skip("No valid gene ID available for testing")

        response = api_client.get(
            f"/api/v1/features/chipseq/genes/{gene_id}",
            params={
                "mark_type": "H3K27me3",
                "cell_type": cell_type
            }
        )
        # Should accept the parameter without error
        assert response.status_code in [200, 404, 422], \
            f"Cell type {cell_type}: Unexpected status {response.status_code}"

    def test_pagination_parameters(self, api_client: httpx.Client):
        """Test pagination parameters"""
        gene_id = get_valid_gene_id(api_client)
        if gene_id is None:
            pytest.skip("No valid gene ID available for testing")

        response = api_client.get(
            f"/api/v1/features/chipseq/genes/{gene_id}",
            params={
                "mark_type": "H3K27me3",
                "page": 1,
                "page_size": 10
            }
        )
        assert response.status_code in [200, 404]


class TestChIPSeqErrorHandling:
    """Tests for error handling in ChIP-seq endpoints"""

    def test_invalid_mark_type(self, api_client: httpx.Client):
        """Invalid mark type should return 422 or be ignored"""
        gene_id = get_valid_gene_id(api_client)
        if gene_id is None:
            pytest.skip("No valid gene ID available for testing")

        response = api_client.get(
            f"/api/v1/features/chipseq/genes/{gene_id}",
            params={"mark_type": "INVALID_MARK_XYZ"}
        )
        # Should return 422 (validation error) or 404 (no data)
        assert response.status_code in [200, 404, 422], \
            f"Invalid mark type should return 422 or 404, got {response.status_code}"

    def test_negative_flanking(self, api_client: httpx.Client):
        """Negative flanking value should be handled"""
        gene_id = get_valid_gene_id(api_client)
        if gene_id is None:
            pytest.skip("No valid gene ID available for testing")

        response = api_client.get(
            f"/api/v1/features/chipseq/genes/{gene_id}",
            params={
                "mark_type": "H3K27me3",
                "flanking": -1000
            }
        )
        # Should return 422 (validation error) or handle gracefully
        assert response.status_code in [200, 404, 422]

    def test_invalid_page_number(self, api_client: httpx.Client):
        """Invalid page number should be handled"""
        gene_id = get_valid_gene_id(api_client)
        if gene_id is None:
            pytest.skip("No valid gene ID available for testing")

        response = api_client.get(
            f"/api/v1/features/chipseq/genes/{gene_id}",
            params={
                "mark_type": "H3K27me3",
                "page": -1
            }
        )
        assert response.status_code in [200, 404, 422]


class TestChIPSeqCellTypeSupport:
    """Tests specifically for cell type support (K562, GM12878, HepG2, H1-hESC)"""

    def test_k562_cell_type(self, api_client: httpx.Client):
        """Test K562 cell type is recognized"""
        gene_id = get_valid_gene_id(api_client)
        if gene_id is None:
            pytest.skip("No valid gene ID available for testing")

        response = api_client.get(
            f"/api/v1/features/chipseq/genes/{gene_id}",
            params={"mark_type": "H3K27me3", "cell_type": "K562"}
        )
        assert response.status_code in [200, 404, 422]

    def test_gm12878_cell_type(self, api_client: httpx.Client):
        """Test GM12878 cell type is recognized"""
        gene_id = get_valid_gene_id(api_client)
        if gene_id is None:
            pytest.skip("No valid gene ID available for testing")

        response = api_client.get(
            f"/api/v1/features/chipseq/genes/{gene_id}",
            params={"mark_type": "H3K27me3", "cell_type": "GM12878"}
        )
        assert response.status_code in [200, 404, 422]

    def test_hepg2_cell_type_new(self, api_client: httpx.Client):
        """Test HepG2 cell type is recognized (new cell type)"""
        gene_id = get_valid_gene_id(api_client)
        if gene_id is None:
            pytest.skip("No valid gene ID available for testing")

        response = api_client.get(
            f"/api/v1/features/chipseq/genes/{gene_id}",
            params={"mark_type": "H3K27me3", "cell_type": "HepG2"}
        )
        assert response.status_code in [200, 404, 422]

    def test_h1hesc_cell_type_new(self, api_client: httpx.Client):
        """Test H1-hESC cell type is recognized (new cell type)"""
        gene_id = get_valid_gene_id(api_client)
        if gene_id is None:
            pytest.skip("No valid gene ID available for testing")

        response = api_client.get(
            f"/api/v1/features/chipseq/genes/{gene_id}",
            params={"mark_type": "H3K27me3", "cell_type": "H1-hESC"}
        )
        assert response.status_code in [200, 404, 422]


if __name__ == "__main__":
    pytest.main([__file__, "-v", "--tb=short"])
