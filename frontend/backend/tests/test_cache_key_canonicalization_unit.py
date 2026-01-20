"""
Unit tests for cache key canonicalization.

Goal:
- Reduce cache key fragmentation caused by semantically equivalent inputs
  (e.g. whitespace differences, comma-separated list spacing).
"""

import pytest


@pytest.mark.unit
def test_make_key_strips_string_values_in_key_params(monkeypatch):
    """
    Cache keys should not differ only because a string value has leading/trailing whitespace.
    """
    from app.core import cache as cache_module

    # Avoid real Redis connection attempts during unit tests.
    monkeypatch.setattr(cache_module.RedisCache, "_connect", lambda self: None)
    monkeypatch.setattr(cache_module.settings, "ENABLE_CACHE", True, raising=False)

    cache = cache_module.CacheService()

    key1 = cache.make_key("unit:key", mark_type="H3K27me3")
    key2 = cache.make_key("unit:key", mark_type="  H3K27me3  ")

    assert key1 == key2


@pytest.mark.unit
def test_make_key_normalizes_comma_list_strings_for_known_param_names(monkeypatch):
    """
    For known comma-separated list parameters, normalize spacing so that:
    - "A,B" and "A, B" map to the same cache key
    - Order is preserved (no sorting) to avoid changing semantics.
    """
    from app.core import cache as cache_module

    # Avoid real Redis connection attempts during unit tests.
    monkeypatch.setattr(cache_module.RedisCache, "_connect", lambda self: None)
    monkeypatch.setattr(cache_module.settings, "ENABLE_CACHE", True, raising=False)

    cache = cache_module.CacheService()

    key1 = cache.make_key("unit:key", marks="H3K27me3,H3K4me3")
    key2 = cache.make_key("unit:key", marks="H3K27me3, H3K4me3")
    key3 = cache.make_key("unit:key", cell_types="K562,GM12878")
    key4 = cache.make_key("unit:key", cell_types="K562, GM12878")

    assert key1 == key2
    assert key3 == key4


@pytest.mark.unit
def test_make_key_does_not_normalize_commas_for_free_text_params(monkeypatch):
    """
    Free-text parameters may legitimately contain commas/spaces; do not rewrite them.
    """
    from app.core import cache as cache_module

    # Avoid real Redis connection attempts during unit tests.
    monkeypatch.setattr(cache_module.RedisCache, "_connect", lambda self: None)
    monkeypatch.setattr(cache_module.settings, "ENABLE_CACHE", True, raising=False)

    cache = cache_module.CacheService()

    key1 = cache.make_key("unit:key", trait_name="a,b")
    key2 = cache.make_key("unit:key", trait_name="a, b")

    assert key1 != key2

