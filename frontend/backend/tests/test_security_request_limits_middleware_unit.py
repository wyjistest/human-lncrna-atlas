import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from pydantic import ValidationError

from app.middleware.request_limits import RequestLimitsMiddleware
from app.schemas.chipseq import BatchHeatmapMatrixRequest


def _make_app(*, max_body_size: int, max_query_string_length: int) -> FastAPI:
    app = FastAPI(docs_url=None, redoc_url=None, openapi_url=None)
    app.add_middleware(
        RequestLimitsMiddleware,
        max_body_size=max_body_size,
        max_query_string_length=max_query_string_length,
    )

    @app.get("/ok")
    def ok():
        return {"ok": True}

    @app.post("/echo")
    def echo(payload: dict):
        return payload

    return app


def test_query_string_too_long_returns_414():
    client = TestClient(_make_app(max_body_size=1024, max_query_string_length=10))
    resp = client.get("/ok?x=" + "a" * 100)
    assert resp.status_code == 414
    body = resp.json()
    assert body.get("detail", {}).get("error") == "QUERY_STRING_TOO_LONG"


def test_request_body_too_large_returns_413():
    client = TestClient(_make_app(max_body_size=50, max_query_string_length=2048))
    resp = client.post("/echo", json={"x": "a" * 200})
    assert resp.status_code == 413
    body = resp.json()
    assert body.get("detail", {}).get("error") == "REQUEST_BODY_TOO_LARGE"


def test_request_under_limits_succeeds():
    client = TestClient(_make_app(max_body_size=1024, max_query_string_length=2048))
    resp = client.get("/ok?x=1")
    assert resp.status_code == 200
    assert resp.json() == {"ok": True}

    resp2 = client.post("/echo", json={"x": "ok"})
    assert resp2.status_code == 200
    assert resp2.json() == {"x": "ok"}


def test_batch_heatmap_request_rejects_overlong_items():
    with pytest.raises(ValidationError):
        BatchHeatmapMatrixRequest(
            gene_ids=[1],
            marks=["a" * 200],
            cell_types=["K562"],
        )

    with pytest.raises(ValidationError):
        BatchHeatmapMatrixRequest(
            gene_ids=[1],
            marks=["H3K27me3"],
            cell_types=["a" * 200],
        )

