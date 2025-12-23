"""
lncRNA-ChIP-seq overlap MV 可用性缓存单元测试

覆盖点（P0）：
- reset_mv_cache 不应出现重复定义覆盖导致的缓存键缺失
- check_materialized_view_exists 在非 PostgreSQL 环境应优雅降级
- TTL 缓存命中时不重复访问数据库

运行：
    pytest tests/test_lncrna_chipseq_overlap_mv_cache_unit.py -v -m unit
"""

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


def test_reset_mv_cache_has_checked_at_key():
    from app.routers import lncrna_chipseq_overlap as mod

    mod.reset_mv_cache()

    assert mod._mv_available_cache["checked"] is False
    assert mod._mv_available_cache["available"] is False
    assert "checked_at" in mod._mv_available_cache


def test_check_mv_non_postgresql_graceful(monkeypatch):
    from app.routers import lncrna_chipseq_overlap as mod

    # 固定时间，避免测试依赖真实时钟
    monkeypatch.setattr(mod, "time", SimpleNamespace(time=lambda: 1000.0))

    mod.reset_mv_cache()
    db = _CountingSession(dialect_name="sqlite", mv_populated=False)

    assert mod.check_materialized_view_exists(db) is False
    assert db.execute_calls == 0, "非 PostgreSQL 不应查询 pg_class"
    assert mod._mv_available_cache == {"checked": True, "available": False, "checked_at": 1000.0}


def test_check_mv_cache_ttl_hit_skips_db(monkeypatch):
    from app.routers import lncrna_chipseq_overlap as mod

    # 第一次检查：1000s；第二次检查：1001s（仍在 TTL=300s 内）
    times = iter([1000.0, 1001.0])
    monkeypatch.setattr(mod, "time", SimpleNamespace(time=lambda: next(times)))

    mod.reset_mv_cache()
    db = _CountingSession(dialect_name="postgresql", mv_populated=True)

    assert mod.check_materialized_view_exists(db) is True
    assert db.execute_calls == 1

    # TTL 命中：不应再次执行 SQL
    assert mod.check_materialized_view_exists(db) is True
    assert db.execute_calls == 1


def test_reset_forces_recheck(monkeypatch):
    from app.routers import lncrna_chipseq_overlap as mod

    times = iter([1000.0, 1001.0, 1002.0])
    monkeypatch.setattr(mod, "time", SimpleNamespace(time=lambda: next(times)))

    mod.reset_mv_cache()
    db = _CountingSession(dialect_name="postgresql", mv_populated=False)

    assert mod.check_materialized_view_exists(db) is False
    assert db.execute_calls == 1

    # reset 后应再次访问数据库
    mod.reset_mv_cache()
    assert mod.check_materialized_view_exists(db) is False
    assert db.execute_calls == 2
