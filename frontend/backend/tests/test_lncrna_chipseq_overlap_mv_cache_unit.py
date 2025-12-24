"""
lncRNA-ChIP-seq overlap MV 可用性缓存单元测试

覆盖点（P0）：
- 路由层 reset_mv_cache 应正确重置集中式 MV 缓存状态（Phase 9.24）
- check_materialized_view_exists 在非 PostgreSQL 环境应优雅降级（不访问 pg_class）
- TTL 缓存命中时不重复访问数据库

运行：
    pytest tests/test_lncrna_chipseq_overlap_mv_cache_unit.py -v -m unit
"""

import importlib
from types import SimpleNamespace

import pytest

pytestmark = pytest.mark.unit


class _DummyResult:
    def __init__(self, row):
        self._row = row

    def fetchone(self):
        return self._row


class _CountingSession:
    """最小 Session stub：仅覆盖 MV 检测所需方法，并统计 execute 调用次数。"""

    def __init__(self, *, dialect_name: str, mv_populated: bool):
        self._dialect_name = dialect_name
        self._mv_populated = mv_populated
        self.execute_calls = 0

    def get_bind(self):
        return SimpleNamespace(dialect=SimpleNamespace(name=self._dialect_name))

    def execute(self, sql, params=None):
        self.execute_calls += 1
        sql_text = getattr(sql, "text", str(sql))
        assert "pg_class" in sql_text, "此单元测试仅覆盖 MV 可用性检查查询"
        return _DummyResult(SimpleNamespace(relname="mv_lncrna_chipseq_overlaps", relispopulated=self._mv_populated))


def _install_test_cache(monkeypatch, *, ttl_seconds: int = 300):
    """
    在路由模块内注入独立的 MaterializedViewCache，避免污染全局 singleton。
    """
    from app.core.mv_cache import MaterializedViewCache
    from app.routers import lncrna_chipseq_overlap as mod

    cache = MaterializedViewCache(mv_name="mv_lncrna_chipseq_overlaps", ttl_seconds=ttl_seconds)
    monkeypatch.setattr(mod, "mv_cache", cache, raising=True)
    mod.reset_mv_cache()
    return mod, cache


def test_reset_mv_cache_resets_core_cache(monkeypatch):
    mod, cache = _install_test_cache(monkeypatch)

    db = _CountingSession(dialect_name="postgresql", mv_populated=True)
    assert mod.check_materialized_view_exists(db) is True
    assert cache.get_status()["checked"] is True

    mod.reset_mv_cache()

    status = cache.get_status()
    assert status["checked"] is False
    assert status["available"] is False
    assert status["checked_at"] == 0.0


def test_check_mv_non_postgresql_graceful(monkeypatch):
    mod, cache = _install_test_cache(monkeypatch)

    # 固定时间，避免测试依赖真实时钟
    # Phase 9.24: 使用 monotonic 替代 time（更稳定，不受系统时钟影响）
    mv_cache_mod = importlib.import_module("app.core.mv_cache")
    monkeypatch.setattr(mv_cache_mod, "time", SimpleNamespace(monotonic=lambda: 1000.0))
    db = _CountingSession(dialect_name="sqlite", mv_populated=False)

    assert mod.check_materialized_view_exists(db) is False
    assert db.execute_calls == 0, "非 PostgreSQL 不应查询 pg_class"
    status = cache.get_status()
    assert status["checked"] is True
    assert status["available"] is False
    assert status["checked_at"] == 1000.0


def test_check_mv_cache_ttl_hit_skips_db(monkeypatch):
    mod, _cache = _install_test_cache(monkeypatch)

    # 第一次检查：1000s；第二次检查：1001s（仍在 TTL=300s 内）
    # Phase 9.24: 使用 monotonic 替代 time
    times = iter([1000.0, 1001.0])
    mv_cache_mod = importlib.import_module("app.core.mv_cache")
    monkeypatch.setattr(mv_cache_mod, "time", SimpleNamespace(monotonic=lambda: next(times)))
    db = _CountingSession(dialect_name="postgresql", mv_populated=True)

    assert mod.check_materialized_view_exists(db) is True
    assert db.execute_calls == 1

    # TTL 命中：不应再次执行 SQL
    assert mod.check_materialized_view_exists(db) is True
    assert db.execute_calls == 1


def test_reset_forces_recheck(monkeypatch):
    mod, _cache = _install_test_cache(monkeypatch)

    # Phase 9.24: 使用 monotonic 替代 time
    times = iter([1000.0, 1001.0, 1002.0])
    mv_cache_mod = importlib.import_module("app.core.mv_cache")
    monkeypatch.setattr(mv_cache_mod, "time", SimpleNamespace(monotonic=lambda: next(times)))
    db = _CountingSession(dialect_name="postgresql", mv_populated=False)

    assert mod.check_materialized_view_exists(db) is False
    assert db.execute_calls == 1

    # reset 后应再次访问数据库
    mod.reset_mv_cache()
    assert mod.check_materialized_view_exists(db) is False
    assert db.execute_calls == 2
