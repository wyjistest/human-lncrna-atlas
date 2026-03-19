"""
单元测试：/analysis/summary 的 MV 优先读取 + 缺失时回退

目标：
- 当 analysis summary 的可选物化视图不存在时，不应导致接口失败
- 应自动回退到原始 SQL（保持向后兼容）

说明：
- CI 只跑 -m unit（不依赖真实 PostgreSQL），因此使用最小 Session stub + monkeypatch 覆盖 cache
"""

from types import SimpleNamespace

import pytest
from fastapi import HTTPException

pytestmark = pytest.mark.unit


def _unwrap(func):
    while hasattr(func, "__wrapped__"):
        func = func.__wrapped__  # type: ignore[attr-defined]
    return func


class _DummyResult:
    def __init__(self, rows):
        self._rows = list(rows)

    def fetchone(self):
        return self._rows[0] if self._rows else None

    def fetchall(self):
        return list(self._rows)

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc, tb):
        return False

    def __iter__(self):
        return iter(self._rows)


class _DummySession:
    """
    最小 Session stub：
    - 按 SQL 文本路由不同的返回值/异常
    - 记录调用序列，用于断言回退逻辑确实触发
    """

    def __init__(self):
        self.calls: list[str] = []

    def rollback(self):  # noqa: D401
        return None

    def execute(self, sql, params=None):  # noqa: ARG002 - 与 SQLAlchemy Session.execute 兼容
        sql_text = getattr(sql, "text", str(sql))
        self.calls.append(sql_text)

        # --- High Affinity stats: prefer MV, fallback to CTE query ---
        if "FROM mv_analysis_high_affinity_stats_ba100" in sql_text:
            raise Exception('relation "mv_analysis_high_affinity_stats_ba100" does not exist')

        if "WITH high_affinity_regs AS" in sql_text:
            return _DummyResult(
                [
                    SimpleNamespace(
                        total_regulations=10,
                        unique_lncrnas=2,
                        unique_targets=3,
                        avg_ba=150.0,
                        max_ba=200.0,
                    )
                ]
            )

        # --- Top lncRNAs: prefer MV, fallback to aggregate query ---
        if "FROM mv_analysis_top_lncrnas_ba100" in sql_text:
            raise Exception('relation "mv_analysis_top_lncrnas_ba100" does not exist')

        if "COUNT(DISTINCT r.target_gene_id)" in sql_text and "GROUP BY lnc.gene_name" in sql_text:
            return _DummyResult(
                [
                    SimpleNamespace(lncrna_name="MALAT1", target_count=5, avg_ba=120.0),
                    SimpleNamespace(lncrna_name="NEAT1", target_count=4, avg_ba=110.0),
                ]
            )

        # --- Conservation ---
        if "conservation_counts" in sql_text:
            return _DummyResult([SimpleNamespace(four_species=1, three_species=2, two_species=3)])

        # --- Epigenetic: simulate summary MV missing, fallback query returns empty ---
        if "FROM mv_lncrna_chipseq_overlaps_epigenetic_summary_ba100" in sql_text:
            raise Exception('relation "mv_lncrna_chipseq_overlaps_epigenetic_summary_ba100" does not exist')

        if "FROM mv_lncrna_chipseq_overlaps o" in sql_text and "GROUP BY o.mark_name" in sql_text:
            return _DummyResult([])

        # --- Disease ---
        if "FROM trait_gene_associations tga" in sql_text:
            return _DummyResult([SimpleNamespace(total_diseases=1, total_lncrnas=1, total_genes=2)])

        if "SELECT AVG(connection_count) AS avg_connections" in sql_text:
            return _DummyResult([SimpleNamespace(avg_connections=3.5)])

        raise AssertionError(f"Unexpected SQL executed in unit test:\n{sql_text}")


def test_analysis_summary_mv_missing_falls_back(monkeypatch):
    from app.routers import analysis as analysis_router

    # Ensure deterministic cache behavior in unit test.
    monkeypatch.setattr(analysis_router.cache, "make_key", lambda *a, **k: "analysis:summary:test")
    monkeypatch.setattr(analysis_router.cache, "get", lambda *a, **k: None)
    monkeypatch.setattr(analysis_router.cache, "set", lambda *a, **k: None)

    db = _DummySession()

    # Bypass slowapi limiter wrapper; unit test focuses on SQL fallback logic.
    result = _unwrap(analysis_router.get_analysis_summary)(request=None, db=db)

    # Assert fallback actually happened for the new analysis summary MVs.
    assert any("mv_analysis_high_affinity_stats_ba100" in s for s in db.calls)
    assert any("WITH high_affinity_regs AS" in s for s in db.calls)

    assert any("mv_analysis_top_lncrnas_ba100" in s for s in db.calls)
    assert any("COUNT(DISTINCT r.target_gene_id)" in s for s in db.calls)

    # Basic correctness of assembled response (shape + a few values).
    assert result.high_affinity.total_regulations == 10
    assert result.high_affinity.unique_lncrnas == 2
    assert result.high_affinity.unique_targets == 3
    assert result.high_affinity.top_lncrnas[0].name == "MALAT1"

    assert result.conservation.total_conserved == 6

    assert result.epigenetic.total_overlaps == 0
    assert result.epigenetic.by_mark == {}
    assert result.epigenetic.by_cell_type == {}

    assert result.disease.total_diseases == 1
    assert result.disease.avg_connections == 3.5


class _TxDummySession(_DummySession):
    """
    更接近 PostgreSQL 行为的 Session stub：
    - 当一次 execute 发生异常时，将会进入“事务失败”状态
    - 在调用 rollback() 之前，后续 execute 会抛出 InFailedSqlTransaction 类错误

    目的：确保 /analysis/summary 的 MV 缺失回退逻辑在真实数据库下不会因为缺少 rollback 而 500。
    """

    def __init__(self):
        super().__init__()
        self.failed_transaction = False
        self.rollback_calls = 0

    def rollback(self):  # noqa: D401
        self.rollback_calls += 1
        self.failed_transaction = False

    def execute(self, sql, params=None):  # noqa: ARG002 - 与 SQLAlchemy Session.execute 兼容
        sql_text = getattr(sql, "text", str(sql))
        self.calls.append(sql_text)

        if self.failed_transaction:
            raise Exception(
                "current transaction is aborted, commands ignored until end of transaction block"
            )

        # --- High Affinity stats: prefer MV, fallback to CTE query ---
        if "FROM mv_analysis_high_affinity_stats_ba100" in sql_text:
            self.failed_transaction = True
            raise Exception('relation "mv_analysis_high_affinity_stats_ba100" does not exist')

        if "WITH high_affinity_regs AS" in sql_text:
            return _DummyResult(
                [
                    SimpleNamespace(
                        total_regulations=10,
                        unique_lncrnas=2,
                        unique_targets=3,
                        avg_ba=150.0,
                        max_ba=200.0,
                    )
                ]
            )

        # --- Top lncRNAs: prefer MV, fallback to aggregate query ---
        if "FROM mv_analysis_top_lncrnas_ba100" in sql_text:
            self.failed_transaction = True
            raise Exception('relation "mv_analysis_top_lncrnas_ba100" does not exist')

        if "COUNT(DISTINCT r.target_gene_id)" in sql_text and "GROUP BY lnc.gene_name" in sql_text:
            return _DummyResult(
                [
                    SimpleNamespace(lncrna_name="MALAT1", target_count=5, avg_ba=120.0),
                    SimpleNamespace(lncrna_name="NEAT1", target_count=4, avg_ba=110.0),
                ]
            )

        # --- Conservation ---
        if "conservation_counts" in sql_text:
            return _DummyResult([SimpleNamespace(four_species=1, three_species=2, two_species=3)])

        # --- Epigenetic: simulate summary MV missing, fallback query returns empty ---
        if "FROM mv_lncrna_chipseq_overlaps_epigenetic_summary_ba100" in sql_text:
            self.failed_transaction = True
            raise Exception('relation "mv_lncrna_chipseq_overlaps_epigenetic_summary_ba100" does not exist')

        if "FROM mv_lncrna_chipseq_overlaps o" in sql_text and "GROUP BY o.mark_name" in sql_text:
            return _DummyResult([])

        # --- Disease ---
        if "FROM trait_gene_associations tga" in sql_text:
            return _DummyResult([SimpleNamespace(total_diseases=1, total_lncrnas=1, total_genes=2)])

        if "SELECT AVG(connection_count) AS avg_connections" in sql_text:
            return _DummyResult([SimpleNamespace(avg_connections=3.5)])

        raise AssertionError(f"Unexpected SQL executed in unit test:\n{sql_text}")


def test_analysis_summary_mv_missing_rolls_back_transaction(monkeypatch):
    from app.routers import analysis as analysis_router

    monkeypatch.setattr(analysis_router.cache, "make_key", lambda *a, **k: "analysis:summary:test")
    monkeypatch.setattr(analysis_router.cache, "get", lambda *a, **k: None)
    monkeypatch.setattr(analysis_router.cache, "set", lambda *a, **k: None)

    db = _TxDummySession()

    result = _unwrap(analysis_router.get_analysis_summary)(request=None, db=db)

    # Must rollback after MV-missing errors, otherwise later queries would fail under PostgreSQL semantics.
    assert db.rollback_calls >= 1

    assert result.high_affinity.total_regulations == 10
    assert result.disease.total_diseases == 1


class _BrokenEpigeneticSession(_DummySession):
    def execute(self, sql, params=None):  # noqa: ARG002 - 与 SQLAlchemy Session.execute 兼容
        sql_text = getattr(sql, "text", str(sql))
        if "FROM mv_lncrna_chipseq_overlaps_epigenetic_summary_ba100" in sql_text:
            raise Exception('permission denied for relation "mv_lncrna_chipseq_overlaps_epigenetic_summary_ba100"')
        return super().execute(sql, params)


def test_analysis_summary_non_missing_epigenetic_error_raises_500(monkeypatch):
    from app.routers import analysis as analysis_router

    monkeypatch.setattr(analysis_router.cache, "make_key", lambda *a, **k: "analysis:summary:test")
    monkeypatch.setattr(analysis_router.cache, "get", lambda *a, **k: None)
    monkeypatch.setattr(analysis_router.cache, "set", lambda *a, **k: None)

    db = _BrokenEpigeneticSession()

    with pytest.raises(HTTPException) as exc_info:
        _unwrap(analysis_router.get_analysis_summary)(request=None, db=db)

    assert exc_info.value.status_code == 500
    assert exc_info.value.detail["error"] == "DATABASE_ERROR"
