"""
Unit tests for Redis reconnect backoff (CacheService resilience).

Phase 9.50: Sixth-round deep review - performance/observability.
"""

import pytest

pytestmark = pytest.mark.unit


def test_redis_cache_reconnect_backoff(monkeypatch):
    from app.core import cache as cache_module

    # Avoid real network connections.
    connect_attempts = 0

    def _fake_connect(self):
        nonlocal connect_attempts
        connect_attempts += 1
        self._client = None

    monkeypatch.setattr(cache_module.RedisCache, "_connect", _fake_connect)
    monkeypatch.setattr(cache_module.settings, "ENABLE_CACHE", True, raising=False)
    monkeypatch.setattr(cache_module.settings, "REDIS_CONNECT_BACKOFF_SECONDS", 30, raising=False)

    # Deterministic monotonic time:
    # - init: 0s (records last attempt)
    # - get@0s: no reconnect
    # - get@29s: still within backoff
    # - get@31s: reconnect attempt allowed (needs 2 monotonic calls in _maybe_reconnect)
    times = iter([0.0, 0.0, 29.0, 31.0, 31.0])
    monkeypatch.setattr(cache_module.time, "monotonic", lambda: next(times))

    cache = cache_module.RedisCache()
    assert connect_attempts == 1

    cache.get("k")
    assert connect_attempts == 1

    cache.get("k")
    assert connect_attempts == 1

    cache.get("k")
    assert connect_attempts == 2

