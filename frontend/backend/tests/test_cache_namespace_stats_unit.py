"""
Unit tests for CacheService namespace-level observability stats.

Phase 9.50 (roadmap): add lightweight cache namespace breakdown to help diagnose:
- hit/miss rates per logical namespace
- compute (cache-miss) durations
"""

import pytest


@pytest.mark.unit
def test_cache_stats_includes_namespace_breakdown(monkeypatch):
    from app.core import cache as cache_module

    # Avoid real Redis connection attempts during unit tests.
    monkeypatch.setattr(cache_module.RedisCache, "_connect", lambda self: None)
    monkeypatch.setattr(cache_module.settings, "ENABLE_CACHE", True, raising=False)

    cache = cache_module.CacheService()

    key = cache.make_key("genes:options")
    assert cache.get(key) is None  # miss

    cache.set(key, {"traits": []}, ttl=60)
    assert cache.get(key) == {"traits": []}  # hit

    # Also exercise get_or_compute() compute timing stats.
    cache.get_or_compute(
        "stats:overview",
        lambda: {"ok": 1},
        ttl=60,
        species_id=1,
    )
    cache.get_or_compute(
        "stats:overview",
        lambda: {"ok": 2},
        ttl=60,
        species_id=1,
    )

    stats = cache.get_stats()
    assert stats["backend"] in {"redis", "memory"}
    assert stats["enabled"] is True
    assert stats["hits"] >= 1
    assert stats["misses"] >= 1

    namespaces = stats.get("namespaces")
    assert isinstance(namespaces, dict)
    assert isinstance(namespaces.get("top"), list)

    top = {item["namespace"]: item for item in namespaces["top"]}
    assert "genes:options" in top
    assert top["genes:options"]["requests"] >= 2
    assert top["genes:options"]["hits"] >= 1
    assert top["genes:options"]["misses"] >= 1

    assert "stats:overview" in top
    assert top["stats:overview"]["compute_count"] >= 1
    assert top["stats:overview"]["compute_avg_ms"] >= 0
    # Max compute time should be present once we record timing stats.
    assert top["stats:overview"]["compute_max_ms"] >= 0

    keys = stats.get("keys")
    assert isinstance(keys, dict)
    assert isinstance(keys.get("top"), list)
    top_keys = {item["key"]: item for item in keys["top"]}
    assert key in top_keys
    assert top_keys[key]["requests"] >= 2
    assert top_keys[key]["hits"] >= 1
    assert top_keys[key]["misses"] >= 1
