import asyncio

import pytest
from starlette.requests import Request


def _make_request(
    *,
    path: str = "/api/v1/admin/cache/reset-stats",
    method: str = "POST",
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
def test_admin_reset_cache_stats_resets_counters_but_keeps_cache_data(monkeypatch):
    from app.core import cache as cache_module

    # Avoid real Redis connection attempts during unit tests.
    monkeypatch.setattr(cache_module.RedisCache, "_connect", lambda self: None)
    monkeypatch.setattr(cache_module.settings, "ENABLE_CACHE", True, raising=False)

    test_cache = cache_module.CacheService()

    key = test_cache.make_key("genes:options")
    assert test_cache.get(key) is None  # miss
    test_cache.set(key, {"ok": 1}, ttl=60)
    assert test_cache.get(key) == {"ok": 1}  # hit
    assert test_cache.get_stats()["total_requests"] >= 2

    import app.routers.admin as admin_router

    # Use a dedicated CacheService instance to keep this test isolated.
    monkeypatch.setattr(admin_router, "cache", test_cache)

    handler = getattr(admin_router.reset_cache_stats, "__wrapped__", admin_router.reset_cache_stats)
    result = asyncio.run(handler(_make_request()))
    assert result["status"] == "success"

    stats = result["stats"]
    assert stats["hits"] == 0
    assert stats["misses"] == 0
    assert stats["total_requests"] == 0

    # Resetting stats must NOT clear cached values.
    assert test_cache._get_backend_value(key) == {"ok": 1}
    assert test_cache._memory.get_stats()["size"] == 1

