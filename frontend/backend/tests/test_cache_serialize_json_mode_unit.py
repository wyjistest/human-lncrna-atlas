"""
Unit tests for CacheService._serialize().

Verify Pydantic v2 JSON mode is used, so non-JSON types (e.g. tuple, datetime)
are normalized into JSON-compatible types.
"""

import json
from datetime import datetime, timezone

import pytest
from pydantic import BaseModel


class _DemoModel(BaseModel):
    """A minimal model containing non-JSON Python types."""

    numbers: tuple[int, int]
    created_at: datetime


@pytest.mark.unit
def test_serialize_uses_pydantic_json_mode(monkeypatch):
    from app.core import cache as cache_module

    # Avoid real Redis connection attempts during unit tests.
    monkeypatch.setattr(cache_module.RedisCache, "_connect", lambda self: None)
    monkeypatch.setattr(cache_module.settings, "ENABLE_CACHE", True, raising=False)

    cache = cache_module.CacheService()
    model = _DemoModel(numbers=(1, 2), created_at=datetime(2032, 6, 1, 12, 13, 14, tzinfo=timezone.utc))

    dumped = cache._serialize(model)

    assert dumped["numbers"] == [1, 2]
    assert isinstance(dumped["created_at"], str)
    json.dumps(dumped)

    # CacheService.set() should apply the same normalization by default.
    key = cache.make_key("unit:cache_serialize_json_mode")
    assert cache.set(key, model, ttl=60)
    cached = cache.get(key)
    assert cached is not None
    assert cached["numbers"] == [1, 2]
    assert isinstance(cached["created_at"], str)
    json.dumps(cached)
