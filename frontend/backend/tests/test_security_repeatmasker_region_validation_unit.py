import pytest

from fastapi import FastAPI
from fastapi.testclient import TestClient

from app.core.database import get_db
from app.routers.features import router as features_router


pytestmark = pytest.mark.unit


class _DummySession:
    """最小 Session stub：本组测试仅覆盖参数校验分支，不会触达 DB。"""


@pytest.fixture()
def client() -> TestClient:
    app = FastAPI(docs_url=None, redoc_url=None, openapi_url=None)
    app.include_router(features_router, prefix="/api/v1")

    def _override_get_db():
        yield _DummySession()

    app.dependency_overrides[get_db] = _override_get_db
    return TestClient(app)


def test_repeatmasker_end_le_start_returns_400(client: TestClient) -> None:
    resp = client.get(
        "/api/v1/features/repeats/1",
        params={"chromosome": "chr1", "start": 10, "end": 10},
    )
    assert resp.status_code == 400


def test_repeatmasker_region_too_large_returns_400(client: TestClient) -> None:
    resp = client.get(
        "/api/v1/features/repeats/1",
        params={"chromosome": "chr1", "start": 0, "end": 10_000_001},
    )
    assert resp.status_code == 400


def test_repeatmasker_blank_chromosome_returns_400(client: TestClient) -> None:
    resp = client.get(
        "/api/v1/features/repeats/1",
        params={"chromosome": "   ", "start": 0, "end": 1},
    )
    assert resp.status_code == 400

