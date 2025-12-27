import asyncio

import pytest
from pydantic import SecretStr
from starlette.requests import Request
from fastapi import HTTPException

from app.core.config import settings
from app.routers.admin import verify_admin_access


def _make_request(
    *,
    path: str = "/api/v1/admin/metrics",
    method: str = "GET",
    client_ip: str = "203.0.113.10",
    headers: list[tuple[bytes, bytes]] | None = None,
) -> Request:
    scope = {
        "type": "http",
        "http_version": "1.1",
        "method": method,
        "scheme": "http",
        "path": path,
        "raw_path": path.encode("utf-8"),
        "query_string": b"",
        "headers": headers or [(b"host", b"testserver")],
        "client": (client_ip, 12345),
        "server": ("testserver", 80),
        "root_path": "",
    }
    return Request(scope)


@pytest.mark.unit
def test_verify_admin_access_never_leaks_client_ip_in_403_details(monkeypatch):
    monkeypatch.setattr(settings, "ADMIN_API_KEY", SecretStr("secret"))

    # Strict mode: missing/wrong key -> 403 without client_ip in detail
    monkeypatch.setattr(settings, "ADMIN_REQUIRE_API_KEY", True)
    with pytest.raises(HTTPException) as exc:
        asyncio.run(verify_admin_access(_make_request(), x_admin_api_key=None))
    assert exc.value.status_code == 403
    assert isinstance(exc.value.detail, dict)
    assert "client_ip" not in exc.value.detail

    with pytest.raises(HTTPException) as exc:
        asyncio.run(verify_admin_access(_make_request(), x_admin_api_key="wrong"))
    assert exc.value.status_code == 403
    assert isinstance(exc.value.detail, dict)
    assert "client_ip" not in exc.value.detail

    # Non-strict mode: wrong key -> 403 without client_ip in detail
    monkeypatch.setattr(settings, "ADMIN_REQUIRE_API_KEY", False)
    with pytest.raises(HTTPException) as exc:
        asyncio.run(verify_admin_access(_make_request(), x_admin_api_key="wrong"))
    assert exc.value.status_code == 403
    assert isinstance(exc.value.detail, dict)
    assert "client_ip" not in exc.value.detail

    # Non-strict mode: no key + public IP (not whitelisted/private) -> 403 without client_ip in detail
    with pytest.raises(HTTPException) as exc:
        asyncio.run(verify_admin_access(_make_request(), x_admin_api_key=None))
    assert exc.value.status_code == 403
    assert isinstance(exc.value.detail, dict)
    assert "client_ip" not in exc.value.detail

