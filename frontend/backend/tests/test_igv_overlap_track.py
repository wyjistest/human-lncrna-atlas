"""
IGV Overlap Track API Tests - chr/chromosome Parameter Alias Support

Tests the /api/v1/igv/overlap-track endpoint for:
1. chr parameter (IGV.js standard)
2. chromosome parameter (alternative)
3. Missing parameter error handling

Run: pytest tests/test_igv_overlap_track.py -v
"""
import pytest
import httpx


BASE_URL = "http://localhost:8000"
API_PREFIX = "/api/v1"
OVERLAP_TRACK_URL = f"{API_PREFIX}/igv/overlap-track"


class TestOverlapTrackChrParameter:
    """Test chr parameter support (IGV.js standard format)"""

    def test_chr_parameter_valid(self, client: httpx.Client):
        """Test that 'chr' parameter works correctly"""
        response = client.get(
            OVERLAP_TRACK_URL,
            params={
                "chr": "chr1",
                "start": 1000000,
                "end": 2000000
            }
        )
        assert response.status_code == 200
        assert response.headers.get("content-type", "").startswith("text/plain")

        # BED format should have tab-separated lines
        content = response.text
        if content.strip():  # If there's data
            lines = content.strip().split("\n")
            for line in lines:
                fields = line.split("\t")
                # BED6 format: chr, start, end, name, score, strand
                assert len(fields) == 6, f"BED6 should have 6 fields, got {len(fields)}"
                assert fields[0].startswith("chr"), f"First field should be chromosome, got {fields[0]}"

    def test_chr_parameter_without_prefix(self, client: httpx.Client):
        """Test that chr value without 'chr' prefix is normalized"""
        response = client.get(
            OVERLAP_TRACK_URL,
            params={
                "chr": "1",  # Without 'chr' prefix
                "start": 1000000,
                "end": 2000000
            }
        )
        assert response.status_code == 200

        # Should normalize to 'chr1' in output
        content = response.text
        if content.strip():
            lines = content.strip().split("\n")
            for line in lines:
                fields = line.split("\t")
                assert fields[0] == "chr1", f"Chromosome should be normalized to 'chr1', got {fields[0]}"


class TestOverlapTrackChromosomeParameter:
    """Test chromosome parameter support (alternative parameter name)"""

    def test_chromosome_parameter_valid(self, client: httpx.Client):
        """Test that 'chromosome' parameter works as an alias for 'chr'"""
        response = client.get(
            OVERLAP_TRACK_URL,
            params={
                "chromosome": "chr1",  # Using 'chromosome' instead of 'chr'
                "start": 1000000,
                "end": 2000000
            }
        )
        assert response.status_code == 200
        assert response.headers.get("content-type", "").startswith("text/plain")

    def test_chromosome_parameter_without_prefix(self, client: httpx.Client):
        """Test that chromosome value without 'chr' prefix is normalized"""
        response = client.get(
            OVERLAP_TRACK_URL,
            params={
                "chromosome": "22",  # Without 'chr' prefix
                "start": 1000000,
                "end": 2000000
            }
        )
        assert response.status_code == 200

        # Should normalize to 'chr22' in output
        content = response.text
        if content.strip():
            lines = content.strip().split("\n")
            for line in lines:
                fields = line.split("\t")
                assert fields[0] == "chr22", f"Chromosome should be normalized to 'chr22', got {fields[0]}"


class TestOverlapTrackMissingParameter:
    """Test error handling when both chr and chromosome are missing"""

    def test_missing_chr_and_chromosome_error(self, client: httpx.Client):
        """Test that missing both chr and chromosome returns 400 error"""
        response = client.get(
            OVERLAP_TRACK_URL,
            params={
                # Neither 'chr' nor 'chromosome' provided
                "start": 1000000,
                "end": 2000000
            }
        )
        assert response.status_code == 400

        data = response.json()
        assert "detail" in data
        assert "chr" in data["detail"].lower() or "chromosome" in data["detail"].lower()


class TestOverlapTrackParameterPriority:
    """Test parameter priority when both chr and chromosome are provided"""

    def test_chr_takes_priority_over_chromosome(self, client: httpx.Client):
        """Test that 'chr' takes priority when both parameters are provided"""
        response = client.get(
            OVERLAP_TRACK_URL,
            params={
                "chr": "chr1",
                "chromosome": "chr22",  # This should be ignored
                "start": 1000000,
                "end": 2000000
            }
        )
        assert response.status_code == 200

        # Should use chr1, not chr22
        content = response.text
        if content.strip():
            lines = content.strip().split("\n")
            for line in lines:
                fields = line.split("\t")
                assert fields[0] == "chr1", f"Should use 'chr' parameter value, got {fields[0]}"


class TestOverlapTrackWithFilters:
    """Test overlap track with optional filter parameters"""

    def test_chr_with_mark_type_filter(self, client: httpx.Client):
        """Test chr parameter combined with mark_type filter"""
        response = client.get(
            OVERLAP_TRACK_URL,
            params={
                "chr": "chr1",
                "start": 1000000,
                "end": 5000000,
                "mark_type": "H3K27me3"
            }
        )
        assert response.status_code == 200

        # Verify mark type appears in feature names
        content = response.text
        if content.strip():
            lines = content.strip().split("\n")
            for line in lines:
                fields = line.split("\t")
                name = fields[3]  # name field
                assert "H3K27me3" in name, f"Feature name should contain mark type, got {name}"

    def test_chromosome_with_min_ba_filter(self, client: httpx.Client):
        """Test chromosome parameter combined with min_ba filter"""
        response = client.get(
            OVERLAP_TRACK_URL,
            params={
                "chromosome": "chr1",
                "start": 1000000,
                "end": 5000000,
                "min_ba": 50.0
            }
        )
        assert response.status_code == 200


class TestOverlapTrackValidation:
    """Test validation of start/end parameters"""

    def test_invalid_region_start_greater_than_end(self, client: httpx.Client):
        """Test that start > end returns 400 error"""
        response = client.get(
            OVERLAP_TRACK_URL,
            params={
                "chr": "chr1",
                "start": 2000000,
                "end": 1000000  # start > end
            }
        )
        assert response.status_code == 400

    def test_region_too_large(self, client: httpx.Client):
        """Test that region > 10Mb returns 400 error"""
        response = client.get(
            OVERLAP_TRACK_URL,
            params={
                "chr": "chr1",
                "start": 0,
                "end": 20000000  # 20Mb > 10Mb limit
            }
        )
        assert response.status_code == 400


class TestOverlapTrackBED6Format:
    """Test BED6 format output compliance"""

    def test_bed6_format_structure(self, client: httpx.Client):
        """Test that output follows BED6 format specification"""
        response = client.get(
            OVERLAP_TRACK_URL,
            params={
                "chr": "chr1",
                "start": 1000000,
                "end": 5000000
            }
        )
        assert response.status_code == 200

        content = response.text
        if content.strip():
            lines = content.strip().split("\n")
            for line in lines:
                fields = line.split("\t")

                # BED6 format validation
                assert len(fields) == 6, "BED6 should have 6 fields"

                # Field 1: chromosome (string)
                assert fields[0].startswith("chr"), f"Invalid chromosome: {fields[0]}"

                # Field 2: chromStart (integer, 0-based)
                assert fields[1].isdigit(), f"chromStart should be integer: {fields[1]}"

                # Field 3: chromEnd (integer)
                assert fields[2].isdigit(), f"chromEnd should be integer: {fields[2]}"

                # Field 4: name (string)
                assert len(fields[3]) > 0, "name should not be empty"

                # Field 5: score (integer 0-1000)
                assert fields[4].isdigit(), f"score should be integer: {fields[4]}"
                score = int(fields[4])
                assert 0 <= score <= 1000, f"score should be 0-1000: {score}"

                # Field 6: strand (+/-/.)
                assert fields[5] in ["+", "-", "."], f"Invalid strand: {fields[5]}"


# Pytest fixtures
@pytest.fixture(scope="session")
def client() -> httpx.Client:
    """Create httpx client for testing"""
    with httpx.Client(base_url=BASE_URL, timeout=30.0) as client:
        yield client


if __name__ == "__main__":
    pytest.main([__file__, "-v", "--tb=short"])
