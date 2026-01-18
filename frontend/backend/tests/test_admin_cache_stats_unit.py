import asyncio

import pytest
from starlette.requests import Request


def _make_request(
    *,
    path: str = "/api/v1/admin/cache/stats",
    method: str = "GET",
    client_ip: str = "127.0.0.1",
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
def test_admin_cache_stats_includes_allowed_namespaces(monkeypatch):
    from app.core import cache as cache_module

    # Avoid real Redis connection attempts during unit tests.
    monkeypatch.setattr(cache_module.RedisCache, "_connect", lambda self: None)
    monkeypatch.setattr(cache_module.settings, "ENABLE_CACHE", True, raising=False)

    test_cache = cache_module.CacheService()

    import app.routers.admin as admin_router

    # Use a dedicated CacheService instance to keep this test isolated.
    monkeypatch.setattr(admin_router, "cache", test_cache)

    handler = getattr(admin_router.get_cache_stats, "__wrapped__", admin_router.get_cache_stats)
    result = asyncio.run(handler(_make_request()))

    assert isinstance(result, dict)
    assert result["allowed_namespaces"] == sorted(admin_router.ALLOWED_CACHE_NAMESPACES)

