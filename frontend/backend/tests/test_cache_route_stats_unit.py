import pytest

import app.core.cache as cache_module
from app.core.cache import CacheService
from app.core.request_context import finish_request_scope, start_request_scope


class _DummyRoute:
    path = "/api/v1/test"


@pytest.mark.unit
def test_cache_stats_includes_route_hit_miss_breakdown(monkeypatch):
    # Keep unit tests independent of local Redis availability.
    monkeypatch.setattr(cache_module, "REDIS_AVAILABLE", False)

    cache = CacheService()
    key = cache.make_key("stats:overview")

    token = start_request_scope({"route": _DummyRoute()})
    try:
        # miss
        assert cache.get(key) is None
        # hit
        assert cache.set(key, {"ok": True}, ttl=60) is True
        assert cache.get(key) == {"ok": True}
    finally:
        finish_request_scope(token)

    stats = cache.get_stats()
    routes = stats.get("routes") or {}

    assert routes.get("tracked") == 1
    top = routes.get("top") or []
    assert top and top[0].get("route") == "/api/v1/test"
    assert top[0].get("requests") == 2
    assert top[0].get("hits") == 1
    assert top[0].get("misses") == 1
    assert top[0].get("hit_rate_pct") == 50.0
