import asyncio

import pytest
from pydantic import SecretStr
from starlette.requests import Request
from starlette.responses import JSONResponse

from app.core.config import settings
from app.middleware.security.metrics_auth import metrics_auth_middleware


def _make_request(
    *,
    path: str = "/metrics",
    root_path: str = "",
    client_ip: str = "127.0.0.1",
    headers: list[tuple[bytes, bytes]] | None = None,
) -> Request:
    scope = {
        "type": "http",
        "http_version": "1.1",
        "method": "GET",
        "scheme": "http",
        "path": path,
        "raw_path": path.encode("utf-8"),
        "query_string": b"",
        "headers": headers or [],
        "client": (client_ip, 12345),
        "server": ("testserver", 80),
        "root_path": root_path,
    }
    return Request(scope)


async def _call_next(_request: Request) -> JSONResponse:
    return JSONResponse(status_code=200, content={"ok": True})


@pytest.mark.unit
def test_metrics_auth_strict_mode_requires_valid_key(monkeypatch):
    monkeypatch.setattr(settings, "ADMIN_REQUIRE_API_KEY", True)
    monkeypatch.setattr(settings, "ADMIN_API_KEY", SecretStr("secret"))

    # Missing key -> 403
    resp = asyncio.run(metrics_auth_middleware(_make_request(), _call_next))
    assert resp.status_code == 403

    # Wrong key -> 403
    wrong = _make_request(headers=[(b"x-admin-api-key", b"wrong")])
    resp = asyncio.run(metrics_auth_middleware(wrong, _call_next))
    assert resp.status_code == 403

    # Correct key -> 200
    ok = _make_request(headers=[(b"x-admin-api-key", b"secret")])
    resp = asyncio.run(metrics_auth_middleware(ok, _call_next))
    assert resp.status_code == 200


@pytest.mark.unit
def test_metrics_auth_non_strict_private_ip_allows_no_key_but_denies_wrong_key(monkeypatch):
    monkeypatch.setattr(settings, "ADMIN_REQUIRE_API_KEY", False)
    monkeypatch.setattr(settings, "ADMIN_API_KEY", SecretStr("secret"))

    # Private IP with no key -> 200
    resp = asyncio.run(metrics_auth_middleware(_make_request(), _call_next))
    assert resp.status_code == 200

    # Private IP with wrong key -> 403 (do not fall back to private IP allow)
    wrong = _make_request(headers=[(b"x-admin-api-key", b"wrong")])
    resp = asyncio.run(metrics_auth_middleware(wrong, _call_next))
    assert resp.status_code == 403

    # Private IP with correct key -> 200
    ok = _make_request(headers=[(b"x-admin-api-key", b"secret")])
    resp = asyncio.run(metrics_auth_middleware(ok, _call_next))
    assert resp.status_code == 200


@pytest.mark.unit
def test_metrics_auth_only_applies_to_prometheus_metrics_path(monkeypatch):
    monkeypatch.setattr(settings, "ADMIN_REQUIRE_API_KEY", True)
    monkeypatch.setattr(settings, "ADMIN_API_KEY", SecretStr("secret"))

    # Should not block non-Prometheus endpoints that happen to end with "/metrics"
    non_prom = _make_request(path="/api/v1/admin/metrics")
    resp = asyncio.run(metrics_auth_middleware(non_prom, _call_next))
    assert resp.status_code == 200

    # Still blocks Prometheus metrics even when served behind a reverse-proxy root_path
    with_root_path = _make_request(path="/metrics", root_path="/api")
    resp = asyncio.run(metrics_auth_middleware(with_root_path, _call_next))
    assert resp.status_code == 403
