"""
Unit tests for CacheService get() latency observability stats.

Roadmap: add lightweight cache get latency percentiles (p50/p95/p99) for hits/misses,
without doing expensive sorting in the hot path.
"""

import pytest


@pytest.mark.unit
def test_cache_stats_includes_get_latency_percentiles(monkeypatch):
    from app.core import cache as cache_module

    # Avoid real Redis connection attempts during unit tests.
    monkeypatch.setattr(cache_module.RedisCache, "_connect", lambda self: None)
    monkeypatch.setattr(cache_module.settings, "ENABLE_CACHE", True, raising=False)

    cache = cache_module.CacheService()
    key = cache.make_key("genes:options")

    # Collect enough samples to compute percentiles (>= 10 samples).
    for _ in range(12):
        assert cache.get(key) is None

    cache.set(key, {"traits": []}, ttl=60)
    for _ in range(12):
        assert cache.get(key) == {"traits": []}

    stats = cache.get_stats()
    latency = stats.get("get_latency_ms")
    assert isinstance(latency, dict)

    assert int(latency.get("hits_samples", 0) or 0) >= 12
    assert int(latency.get("misses_samples", 0) or 0) >= 12
    assert int(latency.get("max_samples", 0) or 0) > 0

    hits = latency.get("hits")
    misses = latency.get("misses")
    assert isinstance(hits, dict)
    assert isinstance(misses, dict)

    for metric in ("p50_ms", "p95_ms", "p99_ms"):
        assert float(hits[metric]) >= 0.0
        assert float(misses[metric]) >= 0.0

    assert float(hits["p50_ms"]) <= float(hits["p95_ms"]) <= float(hits["p99_ms"])
    assert float(misses["p50_ms"]) <= float(misses["p95_ms"]) <= float(misses["p99_ms"])

