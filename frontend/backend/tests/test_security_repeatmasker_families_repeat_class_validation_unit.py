import pytest
from types import SimpleNamespace

from fastapi import FastAPI
from fastapi.testclient import TestClient

from app.core.cache import cache
from app.core.database import get_db
from app.models import Species
from app.routers.features import router as features_router


pytestmark = pytest.mark.unit


class _FakeQuery:
    def __init__(self, *, first_row=None):
        self._first_row = first_row

    def filter(self, *args, **kwargs):  # noqa: ARG002
        return self

    def first(self):
        return self._first_row


class _DummySession:
    """最小 Session stub：用于覆盖 repeat_class 无效时的提前返回分支。"""

    def query(self, *args, **kwargs):  # noqa: ARG002
        if len(args) == 1 and args[0] is Species:
            return _FakeQuery(first_row=SimpleNamespace(species_id=1, display_name="Human"))
        raise AssertionError("Unexpected DB query in this test")


@pytest.fixture()
def client() -> TestClient:
    app = FastAPI(docs_url=None, redoc_url=None, openapi_url=None)
    app.include_router(features_router, prefix="/api/v1")

    def _override_get_db():
        yield _DummySession()

    app.dependency_overrides[get_db] = _override_get_db
    return TestClient(app)


def test_repeat_families_invalid_repeat_class_returns_empty_list_without_db_scan(client: TestClient) -> None:
    classes_key = cache.make_key("repeatmasker:classes", species_id=1)
    cache.set(classes_key, ["LINE", "SINE"], cache.TTL_STATS)
    try:
        resp = client.get(
            "/api/v1/features/repeats/1/families",
            params={"repeat_class": "NOT_A_REAL_CLASS"},
        )
        assert resp.status_code == 200
        assert resp.json() == []
    finally:
        cache.delete(classes_key)

