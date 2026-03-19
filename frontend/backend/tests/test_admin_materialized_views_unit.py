"""
Unit tests for Admin materialized view operations.

These tests avoid real database connections by using a lightweight fake Connection.
"""

from __future__ import annotations

import types
from datetime import datetime, timedelta, timezone

import pytest


class _ScalarResult:
    def __init__(self, value):
        self._value = value

    def scalar_one(self):
        return self._value


class _FetchResult:
    def __init__(self, row):
        self._row = row

    def fetchone(self):
        return self._row


class _FakeConnection:
    def __init__(self, *, lock_available: bool = True, populated: bool = True, mv_exists: bool = True):
        self.dialect = types.SimpleNamespace(name="postgresql")
        self.executed: list[tuple[str, dict | None]] = []
        self._lock_available = lock_available
        self._populated = populated
        self._mv_exists = mv_exists

    def execute(self, statement, params=None):
        sql = (getattr(statement, "text", str(statement)) or "").strip()
        self.executed.append((sql, params))

        if "pg_try_advisory_lock" in sql:
            return _ScalarResult(self._lock_available)
        if "pg_advisory_unlock" in sql:
            return _ScalarResult(True)
        if sql.startswith("SET statement_timeout"):
            return _ScalarResult(True)
        if "FROM pg_class c" in sql:
            if not self._mv_exists:
                return _FetchResult(None)
            row = types.SimpleNamespace(
                populated=self._populated,
                total_size="1 MB",
                total_size_bytes=1048576,
                heap_size="768 kB",
                heap_size_bytes=786432,
                index_size="256 kB",
                index_size_bytes=262144,
                rows_estimate=123,
                last_analyze=datetime.now(timezone.utc) - timedelta(minutes=5),
                last_autoanalyze=datetime.now(timezone.utc) - timedelta(minutes=3),
            )
            return _FetchResult(row)
        if sql.startswith("REFRESH MATERIALIZED VIEW"):
            return _ScalarResult(True)
        if sql.startswith("ANALYZE"):
            return _ScalarResult(True)

        raise AssertionError(f"Unexpected SQL executed in unit test: {sql!r}")


@pytest.mark.unit
def test_refresh_raises_when_lock_unavailable():
    from app.core import materialized_views as mv_ops

    conn = _FakeConnection(lock_available=False)
    with pytest.raises(mv_ops.MaterializedViewRefreshInProgress):
        mv_ops.refresh_materialized_views(conn, views=["mv_lncrna_chipseq_overlaps"], timeout_seconds=1)


@pytest.mark.unit
def test_refresh_restores_statement_timeout_and_unlocks():
    from app.core import materialized_views as mv_ops
    from app.core.config import settings

    conn = _FakeConnection(lock_available=True, populated=True, mv_exists=True)
    result = mv_ops.refresh_materialized_views(
        conn,
        views=["mv_lncrna_chipseq_overlaps"],
        concurrently=True,
        analyze=True,
        timeout_seconds=10,
    )

    assert result["status"] in {"success", "partial"}
    assert result["views"][0]["ok"] is True
    assert result["views"][0]["concurrently"] is True

    statements = [sql for sql, _ in conn.executed]
    assert any("SET statement_timeout" in sql and ":ms" in sql for sql in statements)
    assert any("REFRESH MATERIALIZED VIEW CONCURRENTLY mv_lncrna_chipseq_overlaps" in sql for sql in statements)
    assert any("SELECT pg_advisory_unlock" in sql for sql in statements)

    # Ensure we restore to QUERY_TIMEOUT_MS at the end (second SET call).
    set_calls = [(sql, params) for sql, params in conn.executed if sql.startswith("SET statement_timeout")]
    assert len(set_calls) >= 2
    assert set_calls[-1][1] == {"ms": int(settings.QUERY_TIMEOUT) * 1000}


@pytest.mark.unit
def test_refresh_falls_back_to_full_when_not_populated():
    from app.core import materialized_views as mv_ops

    conn = _FakeConnection(lock_available=True, populated=False, mv_exists=True)
    result = mv_ops.refresh_materialized_views(
        conn,
        views=["mv_lncrna_chipseq_overlaps"],
        concurrently=True,
        analyze=False,
        timeout_seconds=10,
    )

    assert result["views"][0]["ok"] is True
    assert result["views"][0]["concurrently"] is False
    assert result["views"][0]["note"]

    statements = [sql for sql, _ in conn.executed]
    assert any(sql == "REFRESH MATERIALIZED VIEW mv_lncrna_chipseq_overlaps" for sql in statements)


@pytest.mark.unit
def test_normalize_mv_list_preserves_dependency_order():
    from app.core import materialized_views as mv_ops

    normalized = mv_ops.normalize_mv_list(
        [
            "mv_lncrna_chipseq_overlaps_epigenetic_summary_ba100",
            "mv_lncrna_chipseq_overlaps",
        ]
    )
    assert normalized == [
        "mv_lncrna_chipseq_overlaps",
        "mv_lncrna_chipseq_overlaps_epigenetic_summary_ba100",
    ]


@pytest.mark.unit
def test_get_mv_status_includes_operational_metadata():
    from app.core import materialized_views as mv_ops

    conn = _FakeConnection(lock_available=True, populated=True, mv_exists=True)
    status = mv_ops.get_mv_status(conn, "mv_lncrna_chipseq_overlaps")

    assert status["exists"] is True
    assert status["total_size"] == "1 MB"
    assert status["total_size_bytes"] == 1048576
    assert status["heap_size"] == "768 kB"
    assert status["heap_size_bytes"] == 786432
    assert status["index_size"] == "256 kB"
    assert status["index_size_bytes"] == 262144
    assert status["last_analyze_at"] is not None
    assert status["last_autoanalyze_at"] is not None
    assert status["last_stats_at"] is not None
    assert status["last_stats_source"] == "autoanalyze"
    assert isinstance(status["stats_age_seconds"], float)
    assert status["stats_age_seconds"] >= 0
