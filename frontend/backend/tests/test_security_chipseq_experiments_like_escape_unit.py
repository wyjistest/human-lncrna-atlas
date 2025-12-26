"""
Unit tests: ChIP-seq experiments filtering should use a single-character ESCAPE clause.

Rationale:
- PostgreSQL requires the ESCAPE string length to be exactly 1 character.
- We use backslash (\\) as the escape character together with escape_like_pattern().
"""

from datetime import datetime

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from app.core.database import get_db
from app.routers.chipseq_experiments import router as experiments_router


pytestmark = pytest.mark.unit


class _DummyResult:
    def __init__(self, rows):
        self._rows = list(rows)

    def fetchall(self):
        return self._rows


class _CaptureSession:
    def __init__(self):
        self.last_sql = None
        self.last_params = None

    def execute(self, sql, params=None):
        self.last_sql = getattr(sql, "text", str(sql))
        self.last_params = dict(params or {})

        # Return one row matching list_experiments() expected shape (22 columns).
        row = (
            1,  # experiment_id
            "exp1",  # experiment_name
            1,  # species_id
            "hs",  # species_code
            "H3K27me3",  # mark_name
            "repressive",  # mark_category
            "#666666",  # display_color
            "K562",  # cell_type
            None,  # tissue_type
            None,  # cell_line
            None,  # treatment
            "ENCODE",  # source_database
            None,  # source_accession
            None,  # peak_caller
            None,  # reference_genome
            None,  # total_reads
            None,  # mapped_reads
            None,  # frip_score
            True,  # is_active
            datetime(2025, 1, 1),  # created_at
            0,  # peak_count
            1,  # total_count
        )
        return _DummyResult([row])


@pytest.fixture()
def captured_db() -> _CaptureSession:
    return _CaptureSession()


@pytest.fixture()
def client(captured_db: _CaptureSession) -> TestClient:
    app = FastAPI()
    app.include_router(experiments_router, prefix="/api/v1/features/chipseq")

    def _override_get_db():
        yield captured_db

    app.dependency_overrides[get_db] = _override_get_db
    return TestClient(app)


def test_list_experiments_cell_type_uses_single_char_escape_clause(client: TestClient, captured_db: _CaptureSession):
    # Test that the ESCAPE clause uses a single backslash character.
    # We use a cell_type that contains the LIKE wildcard `_` to verify escaping.
    # Note: We use `_` instead of `%` to avoid URL encoding issues across different environments.
    resp = client.get(
        "/api/v1/features/chipseq/experiments",
        params={"cell_type": "K_562"},
    )
    assert resp.status_code == 200

    assert captured_db.last_sql is not None, "Expected the endpoint to execute a SQL query"
    assert "ESCAPE '\\'" in captured_db.last_sql, "ESCAPE clause should use a single backslash character"
    assert "ESCAPE '\\\\'" not in captured_db.last_sql, "ESCAPE clause must not contain a two-character string"

    assert captured_db.last_params is not None
    # The escape_like_pattern function should escape `_` with backslash
    assert captured_db.last_params.get("cell_type") == r"K\_562"
