"""
安全测试: /export/chipseq-overlaps mark_names 参数验证（单元测试）

覆盖修复点:
- 防止通过重复 query 参数放大 mark_names 列表导致解析/数据库负载上升（DoS）
- 限制最大 marks 数量与单项长度（与 app.core.validators 常量保持一致）
- 去除空白项并做 strip 规范化

运行方式:
    pytest tests/test_security_export_chipseq_overlaps_mark_names_unit.py -v
"""

import pytest
from fastapi import HTTPException

from app.core.validators import MAX_EXPORT_MARKS, MAX_ITEM_LENGTH
from app.routers.export import _validate_mark_names_list


pytestmark = pytest.mark.unit


def test_empty_list_raises_400():
    with pytest.raises(HTTPException) as exc_info:
        _validate_mark_names_list([])
    assert exc_info.value.status_code == 400


def test_whitespace_only_items_raises_400():
    with pytest.raises(HTTPException) as exc_info:
        _validate_mark_names_list([" ", "\t", "\n"])
    assert exc_info.value.status_code == 400


def test_too_many_items_raises_400():
    too_many = [f"m{i}" for i in range(MAX_EXPORT_MARKS + 1)]
    with pytest.raises(HTTPException) as exc_info:
        _validate_mark_names_list(too_many)
    assert exc_info.value.status_code == 400
    assert "Maximum" in str(exc_info.value.detail)


def test_item_too_long_raises_400():
    long_item = "a" * (MAX_ITEM_LENGTH + 1)
    with pytest.raises(HTTPException) as exc_info:
        _validate_mark_names_list([long_item])
    assert exc_info.value.status_code == 400
    assert "too long" in str(exc_info.value.detail).lower()


def test_normalizes_items():
    assert _validate_mark_names_list([" H3K4me3 ", "H3K27me3"]) == ["H3K4me3", "H3K27me3"]

