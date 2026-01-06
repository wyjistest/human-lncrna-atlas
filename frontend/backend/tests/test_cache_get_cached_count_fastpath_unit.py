import pytest
from sqlalchemy import Column, Integer, create_engine
from sqlalchemy.orm import declarative_base, sessionmaker

from app.core.cache import CacheService
from app.core.config import settings


Base = declarative_base()


class _CachedCountRow(Base):
    __tablename__ = "test_cached_count_rows"

    id = Column(Integer, primary_key=True)


@pytest.mark.unit
def test_get_cached_count_preserves_from_for_simple_query(monkeypatch: pytest.MonkeyPatch):
    """
    回归测试：
    - 之前的 fast-path 会对 `session.query(Model.id)` 生成 `SELECT count(*)`（无 FROM），结果恒为 1。
    - 修复后应能正确保留 FROM 并返回真实行数。
    """
    monkeypatch.setattr(settings, "ENABLE_CACHE", False)

    engine = create_engine("sqlite+pysqlite:///:memory:")
    Base.metadata.create_all(engine)
    SessionLocal = sessionmaker(bind=engine)

    db = SessionLocal()
    try:
        db.add_all([_CachedCountRow(), _CachedCountRow(), _CachedCountRow()])
        db.commit()

        cache = CacheService()
        total = cache.get_cached_count(db.query(_CachedCountRow.id), "unit:test:cached_count")
        assert total == 3
    finally:
        db.close()

