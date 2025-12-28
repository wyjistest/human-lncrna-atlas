"""
Unit tests: Admin endpoints CSRF defense-in-depth (Origin check for unsafe methods).

Rationale:
- CSRF doesn't require CORS; browsers can send cross-site requests even if responses are blocked.
- In production, Admin API should require an API key (ADMIN_REQUIRE_API_KEY=true).
- When strict mode is intentionally disabled for local development, IP-based access may be allowed.
- For unsafe methods, we block requests with a browser Origin header that is not same-origin and not in CORS_ORIGINS.
"""

import pytest
from fastapi import Depends, FastAPI
from fastapi.testclient import TestClient

from app.core.config import settings
from app.routers.admin import verify_admin_access

pytestmark = pytest.mark.unit


@pytest.fixture()
def app(monkeypatch: pytest.MonkeyPatch) -> FastAPI:
    # Simulate development/insecure mode: allow IP-based admin access.
    monkeypatch.setattr(settings, "ADMIN_REQUIRE_API_KEY", False)
    monkeypatch.setattr(settings, "ADMIN_API_KEY", None)
    monkeypatch.setattr(settings, "CORS_ORIGINS", ["http://localhost:5173"])
    # TestClient uses a synthetic peer host name ("testclient") which is not a real IP.
    # Allow it explicitly so we can exercise the Origin check logic.
    monkeypatch.setattr(settings, "ADMIN_ALLOWED_IPS", ["testclient"])

    fastapi_app = FastAPI()

    @fastapi_app.post("/admin/test", dependencies=[Depends(verify_admin_access)])
    def _admin_test():
        return {"ok": True}

    return fastapi_app


@pytest.fixture()
def client(app: FastAPI) -> TestClient:
    return TestClient(app)


def test_admin_post_blocks_untrusted_origin_in_non_strict_mode(client: TestClient):
    resp = client.post("/admin/test", headers={"Origin": "https://evil.example"})
    assert resp.status_code == 403
    body = resp.json()
    assert body.get("detail", {}).get("error") == "CSRF_BLOCKED"


def test_admin_post_allows_missing_origin_header_in_non_strict_mode(client: TestClient):
    # Non-browser clients typically don't send Origin; should be allowed.
    resp = client.post("/admin/test")
    assert resp.status_code == 200
    assert resp.json() == {"ok": True}


def test_admin_post_blocks_untrusted_referer_in_non_strict_mode(client: TestClient):
    # Defense-in-depth: if Origin is missing but Referer is present and cross-site, block it.
    resp = client.post("/admin/test", headers={"Referer": "https://evil.example/path"})
    assert resp.status_code == 403
    body = resp.json()
    assert body.get("detail", {}).get("error") == "CSRF_BLOCKED"


def test_admin_post_allows_same_origin_referer_in_non_strict_mode(client: TestClient):
    resp = client.post("/admin/test", headers={"Referer": "http://testserver/admin/test"})
    assert resp.status_code == 200


def test_admin_post_allows_configured_cors_referer_in_non_strict_mode(client: TestClient):
    resp = client.post("/admin/test", headers={"Referer": "http://localhost:5173/some/page"})
    assert resp.status_code == 200


def test_admin_post_allows_same_origin_in_non_strict_mode(client: TestClient):
    resp = client.post("/admin/test", headers={"Origin": "http://testserver"})
    assert resp.status_code == 200


def test_admin_post_allows_configured_cors_origin_in_non_strict_mode(client: TestClient):
    resp = client.post("/admin/test", headers={"Origin": "http://localhost:5173"})
    assert resp.status_code == 200
