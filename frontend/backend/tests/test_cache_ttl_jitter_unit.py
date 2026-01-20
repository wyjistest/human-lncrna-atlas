"""
Unit tests for cache TTL jitter.

Goal:
- Add small per-key TTL jitter to reduce cache avalanche risk (many hot keys expiring together).
"""

import hashlib

import pytest


class _DummyRedis:
    def __init__(self):
        self.ttls: list[int] = []

    @property
    def connected(self) -> bool:  # noqa: D401 - match RedisCache API
        return True

    def set(self, key: str, value, ttl: int) -> bool:  # noqa: ANN001 - test double
        self.ttls.append(int(ttl))
        return True


@pytest.mark.unit
def test_cache_set_applies_deterministic_ttl_jitter(monkeypatch):
    """
    When TTL jitter is enabled, CacheService.set() should adjust ttl by a deterministic
    delta in [-ttl*pct, +ttl*pct] based on the cache key hash.
    """
    from app.core import cache as cache_module

    # Avoid real Redis connection attempts during unit tests.
    monkeypatch.setattr(cache_module.RedisCache, "_connect", lambda self: None)
    monkeypatch.setattr(cache_module.settings, "ENABLE_CACHE", True, raising=False)

    # Enable jitter (10%).
    monkeypatch.setattr(cache_module.settings, "CACHE_TTL_JITTER_PCT", 0.1, raising=False)

    cache = cache_module.CacheService()
    dummy = _DummyRedis()
    cache._redis = dummy  # type: ignore[attr-defined]

    key = "lncrna:unit:key:abc"
    ttl = 100

    # Avoid serialization noise: value is already JSON-like.
    cache.set(key, {"ok": 1}, ttl=ttl, pre_serialized=True)

    assert len(dummy.ttls) == 1

    max_delta = int(ttl * 0.1)
    h = int(hashlib.sha256(key.encode()).hexdigest()[:8], 16)
    delta = (h % (2 * max_delta + 1)) - max_delta
    expected = max(1, ttl + delta)

    assert dummy.ttls[0] == expected


@pytest.mark.unit
def test_cache_set_no_jitter_when_disabled(monkeypatch):
    from app.core import cache as cache_module

    monkeypatch.setattr(cache_module.RedisCache, "_connect", lambda self: None)
    monkeypatch.setattr(cache_module.settings, "ENABLE_CACHE", True, raising=False)
    monkeypatch.setattr(cache_module.settings, "CACHE_TTL_JITTER_PCT", 0.0, raising=False)

    cache = cache_module.CacheService()
    dummy = _DummyRedis()
    cache._redis = dummy  # type: ignore[attr-defined]

    cache.set("lncrna:unit:key:no-jitter", {"ok": 1}, ttl=100, pre_serialized=True)

    assert dummy.ttls == [100]

