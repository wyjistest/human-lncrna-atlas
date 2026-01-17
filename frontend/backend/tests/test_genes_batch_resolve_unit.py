"""
Unit tests: Genes batch resolve endpoint should validate input before hitting DB.

Rationale:
- The /api/v1/genes/batch endpoint is designed for batch query input from frontend.
- It must enforce size limits to avoid DoS and should reject invalid payloads
  without touching the database layer.
"""

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from app.core.database import get_db
from app.routers.genes import router as genes_router

pytestmark = pytest.mark.unit


class _FailSession:
    def query(self, *args, **kwargs):  # pragma: no cover
        raise AssertionError("DB should not be queried for invalid input")


@pytest.fixture()
def client() -> TestClient:
    app = FastAPI()
    app.include_router(genes_router, prefix="/api/v1")

    def _override_get_db():
        yield _FailSession()

    app.dependency_overrides[get_db] = _override_get_db
    return TestClient(app)


def test_batch_resolve_empty_identifiers_returns_400(client: TestClient) -> None:
    resp = client.post("/api/v1/genes/batch", json={"identifiers": []})
    assert resp.status_code == 400


def test_batch_resolve_too_many_identifiers_returns_400(client: TestClient) -> None:
    identifiers = ["A"] * 201
    resp = client.post("/api/v1/genes/batch", json={"identifiers": identifiers})
    assert resp.status_code == 400


def test_batch_resolve_identifier_too_long_returns_400(client: TestClient) -> None:
    resp = client.post("/api/v1/genes/batch", json={"identifiers": ["X" * 51]})
    assert resp.status_code == 400


def test_batch_resolve_total_chars_too_large_returns_400(client: TestClient) -> None:
    identifiers = ["X" * 50] * 101
    resp = client.post("/api/v1/genes/batch", json={"identifiers": identifiers})
    assert resp.status_code == 400


def test_batch_resolve_invalid_gene_type_returns_400(client: TestClient) -> None:
    resp = client.post("/api/v1/genes/batch", json={"identifiers": ["1"], "gene_type": "invalid"})
    assert resp.status_code == 400

