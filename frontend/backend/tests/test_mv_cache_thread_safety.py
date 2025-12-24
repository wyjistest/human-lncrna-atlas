"""
Unit tests for thread-safe MaterializedViewCache

Phase 9.24: Tests for the centralized thread-safe MV cache module.
These tests verify:
1. Thread-safety of cache operations
2. TTL-based expiration
3. Reset functionality
4. Cache status reporting
"""
import threading
import time
from types import SimpleNamespace
from typing import Optional
from unittest.mock import MagicMock, patch

import pytest


class MockSession:
    """Mock database session for testing."""

    def __init__(self, dialect_name: str = "postgresql", mv_populated: bool = True):
        self._dialect_name = dialect_name
        self._mv_populated = mv_populated
        self.execute_count = 0

    def get_bind(self):
        return SimpleNamespace(dialect=SimpleNamespace(name=self._dialect_name))

    def execute(self, sql, params=None):
        self.execute_count += 1
        if self._mv_populated:
            return MockResult(SimpleNamespace(relname="mv_lncrna_chipseq_overlaps", relispopulated=True))
        else:
            return MockResult(None)


class MockResult:
    """Mock query result."""

    def __init__(self, row):
        self._row = row

    def fetchone(self):
        return self._row


@pytest.fixture
def fresh_cache():
    """Create a fresh cache instance for each test."""
    from app.core.mv_cache import MaterializedViewCache
    return MaterializedViewCache(mv_name="test_mv", ttl_seconds=1)


@pytest.mark.unit
class TestMaterializedViewCacheBasic:
    """Basic functionality tests."""

    def test_cache_initialization(self, fresh_cache):
        """Test cache initializes with correct defaults."""
        status = fresh_cache.get_status()
        assert status["mv_name"] == "test_mv"
        assert status["ttl_seconds"] == 1
        assert status["checked"] is False
        assert status["available"] is False

    def test_reset_clears_cache(self, fresh_cache):
        """Test reset() clears all cache state."""
        # Populate cache first
        db = MockSession()
        fresh_cache.is_available(db)
        assert fresh_cache.get_status()["checked"] is True

        # Reset
        fresh_cache.reset()
        status = fresh_cache.get_status()
        assert status["checked"] is False
        assert status["available"] is False

    def test_is_available_postgresql(self, fresh_cache):
        """Test MV detection on PostgreSQL."""
        db = MockSession(dialect_name="postgresql", mv_populated=True)
        assert fresh_cache.is_available(db) is True
        assert db.execute_count == 1

    def test_is_available_non_postgresql(self, fresh_cache):
        """Test MV not available on non-PostgreSQL."""
        db = MockSession(dialect_name="sqlite")
        assert fresh_cache.is_available(db) is False
        assert db.execute_count == 0  # Should not query pg_class

    def test_is_available_mv_not_populated(self, fresh_cache):
        """Test when MV exists but not populated."""
        db = MockSession(dialect_name="postgresql", mv_populated=False)
        assert fresh_cache.is_available(db) is False


@pytest.mark.unit
class TestMaterializedViewCacheTTL:
    """TTL-related tests."""

    def test_cache_hit_within_ttl(self, fresh_cache):
        """Test cached result is returned within TTL."""
        db = MockSession()

        # First call - hits DB
        fresh_cache.is_available(db)
        assert db.execute_count == 1

        # Second call within TTL - should use cache
        fresh_cache.is_available(db)
        assert db.execute_count == 1  # No additional DB call

    def test_cache_expires_after_ttl(self, fresh_cache):
        """Test cache expires and re-checks after TTL."""
        db = MockSession()

        # First call
        fresh_cache.is_available(db)
        assert db.execute_count == 1

        # Wait for TTL to expire (cache TTL is 1 second)
        time.sleep(1.1)

        # Should re-check
        fresh_cache.is_available(db)
        assert db.execute_count == 2

    def test_get_status_includes_age(self, fresh_cache):
        """Test status includes cache age."""
        db = MockSession()
        fresh_cache.is_available(db)

        time.sleep(0.1)
        status = fresh_cache.get_status()

        assert status["checked"] is True
        assert status["age_seconds"] is not None
        assert status["age_seconds"] >= 0.1


@pytest.mark.unit
class TestMaterializedViewCacheThreadSafety:
    """Thread-safety tests."""

    def test_concurrent_reads(self, fresh_cache):
        """Test multiple threads can read concurrently without errors."""
        db = MockSession()
        results = []
        errors = []

        def reader():
            try:
                result = fresh_cache.is_available(db)
                results.append(result)
            except Exception as e:
                errors.append(e)

        threads = [threading.Thread(target=reader) for _ in range(10)]
        for t in threads:
            t.start()
        for t in threads:
            t.join()

        assert len(errors) == 0
        assert len(results) == 10
        assert all(r is True for r in results)

    def test_concurrent_resets(self, fresh_cache):
        """Test multiple threads can reset concurrently without errors."""
        errors = []

        def resetter():
            try:
                for _ in range(100):
                    fresh_cache.reset()
            except Exception as e:
                errors.append(e)

        threads = [threading.Thread(target=resetter) for _ in range(5)]
        for t in threads:
            t.start()
        for t in threads:
            t.join()

        assert len(errors) == 0

    def test_concurrent_read_and_reset(self, fresh_cache):
        """Test reading and resetting concurrently is safe."""
        db = MockSession()
        errors = []
        stop_flag = threading.Event()

        def reader():
            while not stop_flag.is_set():
                try:
                    fresh_cache.is_available(db)
                except Exception as e:
                    errors.append(e)

        def resetter():
            for _ in range(50):
                try:
                    fresh_cache.reset()
                    time.sleep(0.01)
                except Exception as e:
                    errors.append(e)

        readers = [threading.Thread(target=reader) for _ in range(3)]
        resetters = [threading.Thread(target=resetter) for _ in range(2)]

        for t in readers + resetters:
            t.start()

        # Let resetters finish
        for t in resetters:
            t.join()

        # Signal readers to stop
        stop_flag.set()
        for t in readers:
            t.join()

        assert len(errors) == 0


@pytest.mark.unit
class TestMaterializedViewCacheSingleton:
    """Tests for the singleton instance."""

    def test_singleton_exists(self):
        """Test mv_cache singleton is available."""
        from app.core.mv_cache import mv_cache
        assert mv_cache is not None
        assert mv_cache.mv_name == "mv_lncrna_chipseq_overlaps"
        assert mv_cache.ttl_seconds == 300

    def test_routers_use_same_cache(self):
        """Test both routers use the same cache instance."""
        from app.core.mv_cache import mv_cache as core_cache
        from app.routers.lncrna_chipseq_overlap import reset_mv_cache as overlap_reset
        from app.routers.igv_overlap_track import reset_mv_cache as igv_reset

        # Both reset functions should affect the same cache
        # We verify by checking that after reset, cache state is reset
        db = MockSession()
        core_cache.is_available(db)
        assert core_cache.get_status()["checked"] is True

        # Reset via overlap module
        overlap_reset()
        assert core_cache.get_status()["checked"] is False

        # Repopulate
        core_cache.is_available(db)
        assert core_cache.get_status()["checked"] is True

        # Reset via igv module
        igv_reset()
        assert core_cache.get_status()["checked"] is False
