"""
Unit tests: validators (comma-separated lists / int lists)

目的：
- 固化输入限制（max items / max length / range），防止无意放宽导致 DoS 风险回归
"""

import pytest
from fastapi import HTTPException

from app.core.validators import (
    MAX_COMMA_SEPARATED_ITEMS,
    MAX_FIELD_LENGTH,
    MAX_ITEM_LENGTH,
    parse_comma_list,
    parse_int_list,
    validate_comma_list,
)

pytestmark = pytest.mark.unit


def test_parse_comma_list_basic_parsing_and_normalization() -> None:
    assert parse_comma_list(None) is None
    assert parse_comma_list("") is None
    assert parse_comma_list("a, b, , c") == ["a", "b", "c"]


def test_parse_comma_list_rejects_too_many_items() -> None:
    value = ",".join(str(i) for i in range(MAX_COMMA_SEPARATED_ITEMS + 1))
    with pytest.raises(HTTPException) as exc:
        parse_comma_list(value, param_name="items")

    assert exc.value.status_code == 400


def test_parse_comma_list_rejects_item_too_long() -> None:
    value = "x" * (MAX_ITEM_LENGTH + 1)
    with pytest.raises(HTTPException) as exc:
        parse_comma_list(value, param_name="items")

    assert exc.value.status_code == 400


def test_parse_comma_list_rejects_field_too_long() -> None:
    value = "x" * (MAX_FIELD_LENGTH + 1)
    with pytest.raises(HTTPException) as exc:
        parse_comma_list(value, param_name="items")

    assert exc.value.status_code == 400


def test_validate_comma_list_raises_value_error_on_invalid() -> None:
    ok = "a,b,c"
    assert validate_comma_list(ok) == ok

    too_many = ",".join(str(i) for i in range(MAX_COMMA_SEPARATED_ITEMS + 1))
    with pytest.raises(ValueError):
        validate_comma_list(too_many)

    too_long = "x" * (MAX_FIELD_LENGTH + 1)
    with pytest.raises(ValueError):
        validate_comma_list(too_long)


def test_parse_int_list_parses_and_validates_range() -> None:
    assert parse_int_list("1,2,3", param_name="ids") == [1, 2, 3]

    with pytest.raises(HTTPException) as exc:
        parse_int_list("a", param_name="ids")
    assert exc.value.status_code == 400

    with pytest.raises(HTTPException) as exc:
        parse_int_list("0", min_value=1, param_name="ids")
    assert exc.value.status_code == 400

    with pytest.raises(HTTPException) as exc:
        parse_int_list("5", max_value=4, param_name="ids")
    assert exc.value.status_code == 400

