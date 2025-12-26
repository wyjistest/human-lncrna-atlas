"""
Unit tests: lncRNA-ChIP-seq overlap MV fallback plumbing

目标：
- 当 MV 在运行期被删除（TTL 窗口内），MV 查询应抛出原始异常（包含 MV 名），以便路由层识别并回退到 join 查询
- 其他数据库错误仍应被 sanitize_db_error 脱敏为 HTTPException(500)
"""

import pytest
from fastapi import HTTPException

from app.routers.lncrna_chipseq_overlap import get_lncrna_chipseq_overlaps_from_mv
from app.schemas.lncrna_chipseq_overlap import OverlapFilters

pytestmark = pytest.mark.unit


class _MVMissingSession:
    def execute(self, sql, params=None):
        raise Exception('relation "mv_lncrna_chipseq_overlaps" does not exist')


class _GenericDBErrorSession:
    def execute(self, sql, params=None):
        raise Exception("database connection lost")


def test_mv_missing_error_is_reraised_for_router_fallback():
    filters = OverlapFilters(page=1, page_size=10)
    with pytest.raises(Exception) as exc:
        get_lncrna_chipseq_overlaps_from_mv(_MVMissingSession(), filters)

    # 关键：不是 sanitize_db_error 的 HTTPException，而是原始异常，便于上层 is_mv_missing_error 检测
    assert not isinstance(exc.value, HTTPException)
    assert "mv_lncrna_chipseq_overlaps" in str(exc.value)


def test_non_mv_error_is_sanitized():
    filters = OverlapFilters(page=1, page_size=10)
    with pytest.raises(HTTPException) as exc:
        get_lncrna_chipseq_overlaps_from_mv(_GenericDBErrorSession(), filters)

    assert exc.value.status_code == 500
    assert isinstance(exc.value.detail, dict)
    assert exc.value.detail.get("error") == "DATABASE_ERROR"

