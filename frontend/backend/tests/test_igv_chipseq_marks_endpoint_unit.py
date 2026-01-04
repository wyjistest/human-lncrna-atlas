from types import SimpleNamespace

from fastapi import FastAPI
from fastapi.testclient import TestClient
import pytest

from app.core.cache import cache
from app.core.database import get_db
from app.models import Species
import app.routers.igv_chipseq as igv_chipseq


pytestmark = pytest.mark.unit


class _FakeQuery:
    def __init__(self, *, first_row=None):
        self._first_row = first_row

    def filter(self, *args, **kwargs):  # noqa: ARG002
        return self

    def first(self):
        return self._first_row


class _DummySession:
    def __init__(self, *, mv_rows=None, fallback_rows=None):
        self._mv_rows = mv_rows or []
        self._fallback_rows = fallback_rows or []

    def query(self, model, *args, **kwargs):  # noqa: ARG002
        if model is Species:
            return _FakeQuery(first_row=SimpleNamespace(species_id=1, species_code="HS", display_name="Human"))
        return _FakeQuery(first_row=None)

    def execute(self, stmt, params=None):  # noqa: ARG002
        sql = str(stmt)
        if "mv_chipseq_mark_stats" in sql:
            return SimpleNamespace(fetchall=lambda: self._mv_rows)
        return SimpleNamespace(fetchall=lambda: self._fallback_rows)


def test_igv_chipseq_marks_endpoint_returns_wrapper(monkeypatch: pytest.MonkeyPatch):
    # Avoid cross-test cache pollution
    monkeypatch.setattr(cache, "get", lambda *args, **kwargs: None)
    monkeypatch.setattr(cache, "set", lambda *args, **kwargs: True)

    mv_rows = [
        (
            "H3K27me3",
            "Histone H3 lysine 27 trimethylation",
            "repressive",
            "#DC143C",
            None,
            6,
            295044,
        ),
    ]

    app = FastAPI()
    app.include_router(igv_chipseq.router, prefix="/api/v1/igv")

    def _override_get_db():
        yield _DummySession(mv_rows=mv_rows)

    app.dependency_overrides[get_db] = _override_get_db
    client = TestClient(app)

    resp = client.get("/api/v1/igv/chipseq/marks/1")
    assert resp.status_code == 200
    payload = resp.json()

    assert payload["success"] is True
    assert payload["data"]["species_id"] == 1
    assert payload["data"]["marks"][0]["mark_name"] == "H3K27me3"

