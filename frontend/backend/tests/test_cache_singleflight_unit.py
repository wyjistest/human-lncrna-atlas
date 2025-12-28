"""
Unit tests for cache stampede protection (singleflight).

Phase 9.48+: Third-round deep review - verify concurrent calls to cached endpoints
do not trigger duplicated expensive computations within the same process.
"""

import threading
import time

import pytest


@pytest.mark.unit
def test_cached_decorator_singleflight(monkeypatch):
    """
    When multiple threads call the same @cached function concurrently,
    compute should run only once (per-process best-effort singleflight).
    """
    from app.core import cache as cache_module

    # Avoid Redis connection attempts during unit tests (and keep behavior deterministic).
    monkeypatch.setattr(cache_module.RedisCache, "_connect", lambda self: None)

    # Enable cache explicitly for this test.
    monkeypatch.setattr(cache_module.settings, "ENABLE_CACHE", True, raising=False)

    # Use a fresh cache instance to avoid cross-test contamination.
    fresh_cache = cache_module.CacheService()
    monkeypatch.setattr(cache_module, "cache", fresh_cache)

    compute_calls = 0
    compute_calls_lock = threading.Lock()
    barrier = threading.Barrier(10)
    results: list[dict] = [{} for _ in range(10)]
    errors: list[Exception] = []

    @cache_module.cached("unit:singleflight", ttl=1)
    def expensive(x: int) -> dict:
        nonlocal compute_calls
        with compute_calls_lock:
            compute_calls += 1
        # Ensure other threads have time to contend on the lock
        time.sleep(0.05)
        return {"x": x}

    def worker(i: int):
        try:
            barrier.wait(timeout=2)
            results[i] = expensive(1)
        except Exception as e:
            errors.append(e)

    threads = [threading.Thread(target=worker, args=(i,)) for i in range(10)]
    for t in threads:
        t.start()
    for t in threads:
        t.join(timeout=3)

    assert errors == []
    assert all(r == {"x": 1} for r in results)
    assert compute_calls == 1

