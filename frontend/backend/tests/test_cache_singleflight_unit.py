"""
Unit tests for cache stampede protection (singleflight).

Phase 9.48+: Third-round deep review - verify concurrent calls to cached endpoints
do not trigger duplicated expensive computations within the same process.
"""

import threading

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
    compute_gate = threading.Barrier(2)  # main thread + the single compute thread
    all_calls_started = threading.Event()
    call_started = 0
    call_started_lock = threading.Lock()
    results: list[dict] = [{} for _ in range(10)]
    errors: list[Exception] = []

    @cache_module.cached("unit:singleflight", ttl=1)
    def expensive(x: int) -> dict:
        nonlocal compute_calls
        with compute_calls_lock:
            compute_calls += 1
        # Avoid time.sleep(): block deterministically until all workers started calling
        # the function, then let main thread release the compute path.
        compute_gate.wait(timeout=5)
        return {"x": x}

    def worker(i: int):
        nonlocal call_started
        try:
            barrier.wait(timeout=5)
            with call_started_lock:
                call_started += 1
                if call_started == 10:
                    all_calls_started.set()
            results[i] = expensive(1)
        except Exception as e:
            errors.append(e)

    threads = [threading.Thread(target=worker, args=(i,)) for i in range(10)]
    for t in threads:
        t.start()

    assert all_calls_started.wait(timeout=5)
    compute_gate.wait(timeout=5)

    for t in threads:
        t.join(timeout=10)

    assert not any(t.is_alive() for t in threads)
    assert errors == []
    assert all(r == {"x": 1} for r in results)
    assert compute_calls == 1
