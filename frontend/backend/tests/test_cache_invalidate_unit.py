"""
Unit tests for CacheService.invalidate().

Phase 9.49: Third-round deep review - ensure cache invalidation deletes both:
- the namespace root key (no hashed suffix)
- the namespace hashed keys (namespace:* pattern)
"""

import pytest


class _DummyRedis:
    def __init__(self, *, pattern_deleted: int = 0):
        self.deleted_keys: list[str] = []
        self.deleted_patterns: list[str] = []
        self._pattern_deleted = pattern_deleted

    @property
    def connected(self) -> bool:  # noqa: D401 - keep consistent with RedisCache API
        return True

    def delete(self, key: str) -> bool:
        self.deleted_keys.append(key)
        return True

    def delete_pattern(self, pattern: str) -> int:
        self.deleted_patterns.append(pattern)
        return self._pattern_deleted


@pytest.mark.unit
@pytest.mark.parametrize("namespace", ["stats", "stats:overview"])
def test_invalidate_deletes_root_and_pattern_on_redis(monkeypatch, namespace: str):
    from app.core import cache as cache_module

    # Avoid real Redis connection attempts during unit tests.
    monkeypatch.setattr(cache_module.RedisCache, "_connect", lambda self: None)
    monkeypatch.setattr(cache_module.settings, "ENABLE_CACHE", True, raising=False)

    cache = cache_module.CacheService()
    dummy = _DummyRedis(pattern_deleted=3)
    cache._redis = dummy  # type: ignore[attr-defined]

    deleted = cache.invalidate(namespace)

    assert dummy.deleted_keys == [f"lncrna:{namespace}"]
    assert dummy.deleted_patterns == [f"lncrna:{namespace}:*"]
    assert deleted == 4


@pytest.mark.unit
def test_invalidate_deletes_root_and_prefix_on_memory(monkeypatch):
    from app.core import cache as cache_module

    # Force memory backend by preventing Redis connection.
    monkeypatch.setattr(cache_module.RedisCache, "_connect", lambda self: None)
    monkeypatch.setattr(cache_module.settings, "ENABLE_CACHE", True, raising=False)

    cache = cache_module.CacheService()

    root_key = "lncrna:stats:overview"
    hashed_key = "lncrna:stats:overview:abc123"
    cache._memory.set(root_key, {"ok": 1}, ttl=60)
    cache._memory.set(hashed_key, {"ok": 2}, ttl=60)

    deleted = cache.invalidate("stats:overview")

    assert deleted == 2
    assert cache._memory.get(root_key) is None
    assert cache._memory.get(hashed_key) is None

