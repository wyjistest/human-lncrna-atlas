"""
Unit tests for Admin materialized view operations.

These tests avoid real database connections by using a lightweight fake Connection.
"""

from __future__ import annotations

import types
from datetime import datetime, timedelta, timezone

import pytest


_DEFAULT_TIMESTAMP = object()


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
    def __init__(
        self,
        *,
        lock_available: bool = True,
        populated: bool = True,
        mv_exists: bool = True,
        last_analyze=_DEFAULT_TIMESTAMP,
        last_autoanalyze=_DEFAULT_TIMESTAMP,
    ):
        self.dialect = types.SimpleNamespace(name="postgresql")
        self.executed: list[tuple[str, dict | None]] = []
        self._lock_available = lock_available
        self._populated = populated
        self._mv_exists = mv_exists
        self._last_analyze = (
            datetime.now(timezone.utc) - timedelta(minutes=5)
            if last_analyze is _DEFAULT_TIMESTAMP
            else last_analyze
        )
        self._last_autoanalyze = (
            datetime.now(timezone.utc) - timedelta(minutes=3)
            if last_autoanalyze is _DEFAULT_TIMESTAMP
            else last_autoanalyze
        )

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
                last_analyze=self._last_analyze,
                last_autoanalyze=self._last_autoanalyze,
            )
            return _FetchResult(row)
        if sql.startswith("REFRESH MATERIALIZED VIEW"):
            return _ScalarResult(True)
        if sql.startswith("ANALYZE"):
            return _ScalarResult(True)

        raise AssertionError(f"Unexpected SQL executed in unit test: {sql!r}")


def _mv_status_item(
    name: str,
    *,
    health_status: str = "healthy",
    severity: str = "info",
    recommended_action: str | None = None,
):
    return {
        "name": name,
        "health_status": health_status,
        "severity": severity,
        "recommended_action": recommended_action,
        "affects_features": [],
    }


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
    assert status["health_status"] == "healthy"
    assert status["severity"] == "info"
    assert status["recommended_action"] is None
    assert "Overlap compare" in status["affects_features"]


@pytest.mark.unit
def test_get_mv_status_marks_missing_overlap_mv_as_critical():
    from app.core import materialized_views as mv_ops

    conn = _FakeConnection(mv_exists=False)
    status = mv_ops.get_mv_status(conn, "mv_lncrna_chipseq_overlaps")

    assert status["exists"] is False
    assert status["health_status"] == "missing"
    assert status["severity"] == "critical"
    assert "05_mv_lncrna_chipseq_overlaps.sql" in (status["recommended_action"] or "")
    assert "Overlap compare" in status["affects_features"]


@pytest.mark.unit
def test_get_mv_status_marks_stale_stats_as_warning():
    from app.core import materialized_views as mv_ops

    stale = datetime.now(timezone.utc) - timedelta(days=2)
    conn = _FakeConnection(last_analyze=stale, last_autoanalyze=stale)
    status = mv_ops.get_mv_status(conn, "mv_lncrna_chipseq_overlaps")

    assert status["health_status"] == "stale_stats"
    assert status["severity"] == "warning"
    assert "Run ANALYZE or refresh this MV" in (status["recommended_action"] or "")


@pytest.mark.unit
def test_build_attention_summary_reports_all_healthy():
    from app.core import materialized_views as mv_ops

    summary = mv_ops.build_attention_summary(
        [
            _mv_status_item("mv_analysis_high_affinity_stats_ba100"),
            _mv_status_item("mv_lncrna_chipseq_overlaps"),
        ],
        supported=True,
        database_backend="postgresql",
    )

    assert summary["status"] == "healthy"
    assert summary["severity"] == "info"
    assert summary["attention_count"] == 0
    assert summary["total_count"] == 2
    assert summary["attention_view_names"] == []
    assert "healthy" in summary["message"].lower()
    assert summary["recommended_action"] is None


@pytest.mark.unit
def test_build_attention_summary_reports_warning_attention():
    from app.core import materialized_views as mv_ops

    summary = mv_ops.build_attention_summary(
        [
            _mv_status_item("mv_analysis_high_affinity_stats_ba100"),
            _mv_status_item(
                "mv_analysis_top_lncrnas_ba100",
                health_status="stale_stats",
                severity="warning",
                recommended_action="Run ANALYZE for top-lncRNA stats.",
            ),
        ],
        supported=True,
        database_backend="postgresql",
    )

    assert summary["status"] == "degraded"
    assert summary["severity"] == "warning"
    assert summary["attention_count"] == 1
    assert summary["total_count"] == 2
    assert summary["attention_view_names"] == ["mv_analysis_top_lncrnas_ba100"]
    assert "1/2" in summary["message"]
    assert summary["recommended_action"] == "Run ANALYZE for top-lncRNA stats."


@pytest.mark.unit
def test_build_attention_summary_reports_critical_attention():
    from app.core import materialized_views as mv_ops

    summary = mv_ops.build_attention_summary(
        [
            _mv_status_item("mv_analysis_high_affinity_stats_ba100"),
            _mv_status_item(
                "mv_lncrna_chipseq_overlaps",
                health_status="missing",
                severity="critical",
                recommended_action="Recreate overlap MV before serving compare traffic.",
            ),
        ],
        supported=True,
        database_backend="postgresql",
    )

    assert summary["status"] == "critical"
    assert summary["severity"] == "critical"
    assert summary["attention_count"] == 1
    assert summary["attention_view_names"] == ["mv_lncrna_chipseq_overlaps"]
    assert "critical" in summary["message"].lower()
    assert summary["recommended_action"] == "Recreate overlap MV before serving compare traffic."


@pytest.mark.unit
def test_build_attention_summary_reports_unsupported_backend_as_degraded():
    from app.core import materialized_views as mv_ops

    summary = mv_ops.build_attention_summary(
        [_mv_status_item(name) for name in mv_ops.DEFAULT_MATERIALIZED_VIEWS],
        supported=False,
        database_backend="sqlite",
    )

    assert summary["status"] == "degraded"
    assert summary["severity"] == "warning"
    assert summary["attention_count"] == len(mv_ops.DEFAULT_MATERIALIZED_VIEWS)
    assert summary["attention_view_names"] == list(mv_ops.DEFAULT_MATERIALIZED_VIEWS)
    assert "sqlite" in summary["message"]
    assert "PostgreSQL" in (summary["recommended_action"] or "")
