"""
单元测试：/genes/options 在传入 limit 时不应触发 SQLAlchemy Query 顺序异常

背景：
- 真实环境里（SQLAlchemy 2.x + Postgres）如果先调用 `.limit()` 再 `.order_by()`，
  会触发运行时错误：`Query.order_by() being called on a Query which already has LIMIT...`
- 该错误会导致 /api/v1/genes/options 在前端 typeahead/下拉场景直接 500

本测试通过最小 Query stub 复现该行为，确保实现保持正确调用顺序。
"""

import pytest

pytestmark = pytest.mark.unit


class _DummyQuery:
    def __init__(self) -> None:
        self._limit_applied = False

    def join(self, *args, **kwargs):  # noqa: ANN002, D401
        return self

    def filter(self, *args, **kwargs):  # noqa: ANN002, D401
        return self

    def limit(self, *args, **kwargs):  # noqa: ANN002, D401
        self._limit_applied = True
        return self

    def order_by(self, *args, **kwargs):  # noqa: ANN002, D401
        if self._limit_applied:
            raise RuntimeError(
                "Query.order_by() being called on a Query which already has LIMIT or OFFSET applied.  "
                "Call order_by() before limit() or offset() are applied."
            )
        return self

    def all(self):  # noqa: ANN001, D401
        return []


class _DummySession:
    def query(self, *args, **kwargs):  # noqa: ANN002, D401
        return _DummyQuery()


def test_genes_options_limit_does_not_raise() -> None:
    from app.routers import genes as genes_router

    result = genes_router.get_gene_options.__wrapped__(  # type: ignore[attr-defined]
        request=None,
        species_id=1,
        gene_type="lncRNA",
        q=None,
        limit=5,
        db=_DummySession(),
    )

    assert result == {"genes": []}

