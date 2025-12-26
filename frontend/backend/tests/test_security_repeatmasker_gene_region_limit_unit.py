from types import SimpleNamespace

import pytest

from fastapi import FastAPI
from fastapi.testclient import TestClient

from app.core.database import get_db
from app.routers.features import router as features_router


pytestmark = pytest.mark.unit


class _DummyQuery:
    def __init__(self, result):
        self._result = result

    def filter(self, *args, **kwargs):
        return self

    def first(self):
        return self._result


class _DummySession:
    def __init__(self, gene):
        self._gene = gene

    def query(self, *args, **kwargs):
        return _DummyQuery(self._gene)


@pytest.fixture()
def client() -> TestClient:
    # Build a dummy gene with a huge span to trigger region-size guard.
    gene = SimpleNamespace(
        gene_id=1,
        gene_start=0,
        gene_end=20_000_000,
        species_id=1,
        chromosome="chr1",
    )
    db = _DummySession(gene)

    app = FastAPI(docs_url=None, redoc_url=None, openapi_url=None)
    app.include_router(features_router, prefix="/api/v1")

    def _override_get_db():
        yield db

    app.dependency_overrides[get_db] = _override_get_db
    return TestClient(app)


def test_repeatmasker_gene_repeats_region_too_large_returns_400(client: TestClient) -> None:
    resp = client.get("/api/v1/features/genes/1/repeats")
    assert resp.status_code == 400


def test_repeatmasker_gene_repeat_stats_region_too_large_returns_400(client: TestClient) -> None:
    resp = client.get("/api/v1/features/genes/1/repeats/stats")
    assert resp.status_code == 400

