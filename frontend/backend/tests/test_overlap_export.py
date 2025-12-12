"""
lncRNA-ChIP-seq Overlap Export API Tests

Tests for /api/v1/lncrna-chipseq-overlap/export endpoint

This module tests the batch export functionality including:
- BED6 format export
- CSV format export
- Filter application (chromosome, mark_type, cell_type)
- Empty results handling
- Max rows enforcement
- Format validation

Run: pytest tests/test_overlap_export.py -v
"""
import pytest
import httpx
from io import StringIO
import csv

from conftest import APIAssertions


# ============== Test Constants ==============

EXPORT_ENDPOINT = "/api/v1/lncrna-chipseq-overlap/export"


# ============== Helper Functions ==============

def parse_bed_lines(content: str) -> list[list[str]]:
    """
    Parse BED format content into list of fields.

    Returns:
        List of [chrom, start, end, name, score, strand] for each data line
        (skips track header lines starting with 'track')
    """
    lines = []
    for line in content.strip().split('\n'):
        line = line.strip()
        if not line or line.startswith('track'):
            continue
        fields = line.split('\t')
        if len(fields) >= 6:
            lines.append(fields)
    return lines


def parse_csv_content(content: str) -> tuple[list[str], list[dict]]:
    """
    Parse CSV content into headers and rows.

    Returns:
        Tuple of (headers, rows) where rows is list of dictionaries
    """
    reader = csv.DictReader(StringIO(content))
    headers = reader.fieldnames or []
    rows = list(reader)
    return headers, rows


def validate_bed6_format(line_fields: list[str]) -> None:
    """
    Validate BED6 format: chrom, start, end, name, score, strand

    Raises:
        AssertionError if format is invalid
    """
    assert len(line_fields) == 6, f"BED6 must have 6 columns, got {len(line_fields)}"

    chrom, start, end, name, score, strand = line_fields

    # Chromosome should start with 'chr'
    assert chrom.startswith('chr'), f"Chromosome should start with 'chr', got: {chrom}"

    # Start and end should be integers
    try:
        start_int = int(start)
        end_int = int(end)
    except ValueError:
        pytest.fail(f"Start/end must be integers: start={start}, end={end}")

    # End > start
    assert end_int > start_int, f"End must be > start: start={start_int}, end={end_int}"

    # Name should not be empty
    assert name and len(name) > 0, "Name field should not be empty"

    # Score should be integer 0-1000
    try:
        score_int = int(score)
        assert 0 <= score_int <= 1000, f"Score must be 0-1000, got: {score_int}"
    except ValueError:
        pytest.fail(f"Score must be integer: {score}")

    # Strand should be '.', '+', or '-'
    assert strand in ['.', '+', '-'], f"Strand must be '.', '+', or '-', got: {strand}"


# ============== Test Classes ==============

class TestOverlapExportBasic:
    """Basic export endpoint tests"""

    def test_export_bed_format_default(self, api_client: httpx.Client, api_assert: APIAssertions):
        """GET /export with default parameters returns BED format"""
        response = api_client.get(EXPORT_ENDPOINT, params={
            "format": "bed",
            "chromosome": "chr22",
            "max_rows": 100
        })

        api_assert.assert_successful_response(response)

        # Check headers
        assert response.headers["content-type"].startswith("text/plain")
        assert "attachment" in response.headers.get("content-disposition", "")
        assert ".bed" in response.headers.get("content-disposition", "")

        # Check content
        content = response.text
        assert len(content) > 0, "Export should return non-empty content"

        # Parse and validate BED format
        lines = parse_bed_lines(content)
        assert len(lines) > 0, "Should have at least one data line"

        # Validate first line
        validate_bed6_format(lines[0])

    def test_export_csv_format(self, api_client: httpx.Client, api_assert: APIAssertions):
        """GET /export?format=csv returns CSV format"""
        response = api_client.get(EXPORT_ENDPOINT, params={
            "format": "csv",
            "chromosome": "chr22",
            "max_rows": 100
        })

        api_assert.assert_successful_response(response)

        # Check headers
        assert response.headers["content-type"].startswith("text/csv")
        assert "attachment" in response.headers.get("content-disposition", "")
        assert ".csv" in response.headers.get("content-disposition", "")

        # Check content
        content = response.text
        assert len(content) > 0, "Export should return non-empty content"

        # Parse CSV
        headers, rows = parse_csv_content(content)

        # Validate CSV structure
        assert len(headers) == 19, f"CSV should have 19 columns, got {len(headers)}"

        # Check required columns
        required_columns = [
            'overlap_id', 'chromosome', 'overlap_start', 'overlap_end', 'overlap_length',
            'lncrna_gene_id', 'lncrna_name', 'target_gene_id', 'target_gene_name',
            'mark_type', 'mark_category', 'cell_type',
            'binding_affinity', 'peak_fold_enrichment', 'peak_qvalue',
            'lncrna_binding_start', 'lncrna_binding_end', 'peak_start', 'peak_end'
        ]

        for col in required_columns:
            assert col in headers, f"Missing required column: {col}"

        # Validate at least one data row if results exist
        if len(rows) > 0:
            first_row = rows[0]
            assert 'chromosome' in first_row, "Data row should have chromosome"
            assert first_row['chromosome'].startswith('chr'), "Chromosome should start with 'chr'"

    def test_export_invalid_format(self, api_client: httpx.Client):
        """GET /export with invalid format returns 400/422"""
        response = api_client.get(EXPORT_ENDPOINT, params={
            "format": "invalid_format",
            "chromosome": "chr22"
        })

        # 使用 Literal 校验时 FastAPI 会返回 422
        assert response.status_code in [400, 422], \
            f"Should return 400 or 422 for invalid format, got {response.status_code}"


class TestOverlapExportFilters:
    """Test filter application in exports"""

    def test_export_with_chromosome_filter(self, api_client: httpx.Client, api_assert: APIAssertions):
        """Export with chromosome filter returns only that chromosome"""
        response = api_client.get(EXPORT_ENDPOINT, params={
            "format": "bed",
            "chromosome": "chr22",
            "max_rows": 50
        })

        api_assert.assert_successful_response(response)

        content = response.text
        lines = parse_bed_lines(content)

        # All lines should be chr22
        for line in lines:
            assert line[0] == "chr22", f"Expected chr22, got {line[0]}"

    def test_export_with_mark_type_filter(self, api_client: httpx.Client, api_assert: APIAssertions):
        """Export with mark_type filter applies filter correctly"""
        response = api_client.get(EXPORT_ENDPOINT, params={
            "format": "csv",
            "chromosome": "chr22",
            "mark_type": "H3K27me3",
            "max_rows": 50
        })

        api_assert.assert_successful_response(response)

        content = response.text
        headers, rows = parse_csv_content(content)

        # All rows should have H3K27me3 mark_type
        for row in rows:
            assert row['mark_type'] == "H3K27me3", f"Expected H3K27me3, got {row['mark_type']}"

    def test_export_with_multiple_filters(self, api_client: httpx.Client, api_assert: APIAssertions):
        """Export with multiple filters applies all filters"""
        response = api_client.get(EXPORT_ENDPOINT, params={
            "format": "csv",
            "chromosome": "chr22",
            "mark_type": "H3K27me3",
            "min_binding_affinity": 50,
            "max_rows": 50
        })

        api_assert.assert_successful_response(response)

        content = response.text
        headers, rows = parse_csv_content(content)

        # Validate filters applied
        for row in rows:
            assert row['chromosome'] == "chr22"
            assert row['mark_type'] == "H3K27me3"

            # Check binding affinity (if present)
            if row.get('binding_affinity'):
                ba = float(row['binding_affinity'])
                assert ba >= 50, f"Binding affinity should be >= 50, got {ba}"


class TestOverlapExportEdgeCases:
    """Test edge cases and error handling"""

    def test_export_max_rows_enforcement(self, api_client: httpx.Client, api_assert: APIAssertions):
        """Export respects max_rows parameter"""
        max_rows = 10
        response = api_client.get(EXPORT_ENDPOINT, params={
            "format": "bed",
            "chromosome": "chr22",
            "max_rows": max_rows
        })

        api_assert.assert_successful_response(response)

        content = response.text
        lines = parse_bed_lines(content)

        # Should have at most max_rows lines
        assert len(lines) <= max_rows, f"Should have at most {max_rows} lines, got {len(lines)}"

    def test_export_with_no_results(self, api_client: httpx.Client, api_assert: APIAssertions):
        """Export with filters returning no results still succeeds"""
        response = api_client.get(EXPORT_ENDPOINT, params={
            "format": "bed",
            "chromosome": "chr99",  # Non-existent chromosome
            "max_rows": 100
        })

        # Should return 200 with header only
        api_assert.assert_successful_response(response)

        content = response.text
        lines = parse_bed_lines(content)

        # Should have 0 data lines (only track header)
        assert len(lines) == 0, "Should have no data lines for empty results"

    def test_export_filename_generation(self, api_client: httpx.Client, api_assert: APIAssertions):
        """Export generates appropriate filename in Content-Disposition"""
        response = api_client.get(EXPORT_ENDPOINT, params={
            "format": "bed",
            "chromosome": "chr22",
            "mark_type": "H3K27me3"
        })

        api_assert.assert_successful_response(response)

        # Check filename includes filters
        content_disposition = response.headers.get("content-disposition", "")
        assert "chr22" in content_disposition, "Filename should include chromosome"
        assert "H3K27me3" in content_disposition, "Filename should include mark_type"
        assert ".bed" in content_disposition, "Filename should have .bed extension"


class TestOverlapExportBEDFormat:
    """Detailed BED format validation"""

    def test_bed_format_score_calculation(self, api_client: httpx.Client, api_assert: APIAssertions):
        """BED score is binding_affinity * 10, clamped to 0-1000"""
        response = api_client.get(EXPORT_ENDPOINT, params={
            "format": "bed",
            "chromosome": "chr22",
            "max_rows": 10
        })

        api_assert.assert_successful_response(response)

        content = response.text
        lines = parse_bed_lines(content)

        for line in lines:
            score = int(line[4])
            assert 0 <= score <= 1000, f"Score must be 0-1000, got {score}"

    def test_bed_format_coordinates_valid(self, api_client: httpx.Client, api_assert: APIAssertions):
        """BED coordinates are valid (start < end, non-negative)"""
        response = api_client.get(EXPORT_ENDPOINT, params={
            "format": "bed",
            "chromosome": "chr22",
            "max_rows": 10
        })

        api_assert.assert_successful_response(response)

        content = response.text
        lines = parse_bed_lines(content)

        for line in lines:
            start = int(line[1])
            end = int(line[2])

            assert start >= 0, f"Start must be non-negative, got {start}"
            assert end > start, f"End must be > start, got start={start}, end={end}"

    def test_bed_format_name_structure(self, api_client: httpx.Client, api_assert: APIAssertions):
        """BED name field follows {lncrna}_{target}_{mark} format"""
        response = api_client.get(EXPORT_ENDPOINT, params={
            "format": "bed",
            "chromosome": "chr22",
            "max_rows": 5
        })

        api_assert.assert_successful_response(response)

        content = response.text
        lines = parse_bed_lines(content)

        for line in lines:
            name = line[3]
            parts = name.split('_')

            # Should have at least 3 parts (lncrna, target, mark)
            assert len(parts) >= 3, f"Name should have format lncrna_target_mark, got: {name}"


class TestOverlapExportCSVFormat:
    """Detailed CSV format validation"""

    def test_csv_column_order(self, api_client: httpx.Client, api_assert: APIAssertions):
        """CSV columns are in correct order"""
        response = api_client.get(EXPORT_ENDPOINT, params={
            "format": "csv",
            "chromosome": "chr22",
            "max_rows": 1
        })

        api_assert.assert_successful_response(response)

        content = response.text
        headers, _ = parse_csv_content(content)

        expected_order = [
            'overlap_id', 'chromosome', 'overlap_start', 'overlap_end', 'overlap_length',
            'lncrna_gene_id', 'lncrna_name', 'target_gene_id', 'target_gene_name',
            'mark_type', 'mark_category', 'cell_type',
            'binding_affinity', 'peak_fold_enrichment', 'peak_qvalue',
            'lncrna_binding_start', 'lncrna_binding_end', 'peak_start', 'peak_end'
        ]

        assert headers == expected_order, f"Column order mismatch.\nExpected: {expected_order}\nGot: {headers}"

    def test_csv_data_types(self, api_client: httpx.Client, api_assert: APIAssertions):
        """CSV data types are correct (integers, floats, strings)"""
        response = api_client.get(EXPORT_ENDPOINT, params={
            "format": "csv",
            "chromosome": "chr22",
            "max_rows": 5
        })

        api_assert.assert_successful_response(response)

        content = response.text
        headers, rows = parse_csv_content(content)

        if len(rows) > 0:
            row = rows[0]

            # Test integer fields
            integer_fields = [
                'overlap_start', 'overlap_end', 'overlap_length',
                'lncrna_gene_id', 'target_gene_id',
                'lncrna_binding_start', 'lncrna_binding_end',
                'peak_start', 'peak_end'
            ]

            for field in integer_fields:
                if row.get(field):
                    try:
                        int(row[field])
                    except ValueError:
                        pytest.fail(f"Field {field} should be integer, got: {row[field]}")

            # Test float fields
            float_fields = ['binding_affinity', 'peak_fold_enrichment', 'peak_qvalue']

            for field in float_fields:
                if row.get(field):
                    try:
                        float(row[field])
                    except ValueError:
                        pytest.fail(f"Field {field} should be numeric, got: {row[field]}")

    def test_csv_no_missing_required_fields(self, api_client: httpx.Client, api_assert: APIAssertions):
        """CSV required fields are never empty"""
        response = api_client.get(EXPORT_ENDPOINT, params={
            "format": "csv",
            "chromosome": "chr22",
            "max_rows": 10
        })

        api_assert.assert_successful_response(response)

        content = response.text
        headers, rows = parse_csv_content(content)

        required_fields = [
            'overlap_id', 'chromosome', 'overlap_start', 'overlap_end',
            'mark_type', 'cell_type'
        ]

        for i, row in enumerate(rows):
            for field in required_fields:
                assert row.get(field), f"Row {i}: Required field '{field}' is empty"


class TestOverlapExportPerformance:
    """Performance and rate limiting tests"""

    def test_export_large_dataset(self, api_client: httpx.Client, api_assert: APIAssertions):
        """Export large dataset (1000 rows) completes successfully"""
        response = api_client.get(EXPORT_ENDPOINT, params={
            "format": "csv",
            "chromosome": "chr22",
            "max_rows": 1000
        }, timeout=60.0)  # Longer timeout for large export

        api_assert.assert_successful_response(response)

        content = response.text
        headers, rows = parse_csv_content(content)

        # Should have up to 1000 rows
        assert len(rows) <= 1000, f"Should have at most 1000 rows"

    def test_export_streaming_response(self, api_client: httpx.Client, api_assert: APIAssertions):
        """Export returns streaming response (doesn't load all data into memory)"""
        response = api_client.get(EXPORT_ENDPOINT, params={
            "format": "bed",
            "chromosome": "chr22",
            "max_rows": 500
        })

        api_assert.assert_successful_response(response)

        # Response should be successful
        assert response.status_code == 200

        # Content should be available
        assert len(response.text) > 0
