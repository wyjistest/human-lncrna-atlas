"""
Unit tests: pagination offset guard

目的：
- 防止超大 OFFSET 深分页导致慢查询/DoS
- 保证 compute_pagination_offset 在边界条件下行为可预期
"""

import pytest
from fastapi import HTTPException

from app.core.validators import MAX_PAGINATION_OFFSET, compute_pagination_offset

pytestmark = pytest.mark.unit


def test_compute_pagination_offset_normal_cases():
    assert compute_pagination_offset(1, 100) == 0
    assert compute_pagination_offset(2, 100) == 100
    assert compute_pagination_offset(10, 50) == 450


def test_compute_pagination_offset_allows_exact_max_offset():
    page_size = 1000
    page = (MAX_PAGINATION_OFFSET // page_size) + 1  # offset == MAX_PAGINATION_OFFSET
    assert compute_pagination_offset(page, page_size) == MAX_PAGINATION_OFFSET


def test_compute_pagination_offset_rejects_too_large_offset():
    page_size = 1000
    page = (MAX_PAGINATION_OFFSET // page_size) + 2  # offset > MAX_PAGINATION_OFFSET
    with pytest.raises(HTTPException) as exc:
        compute_pagination_offset(page, page_size)

    assert exc.value.status_code == 400

