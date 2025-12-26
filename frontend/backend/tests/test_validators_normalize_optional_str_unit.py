"""
Unit tests: normalize_optional_str helper.

Rationale:
- Avoid cache key fragmentation caused by whitespace-only query params.
- Prevent accidental broad LIKE filters triggered by blank strings.
"""

import pytest

from app.core.validators import normalize_optional_str

pytestmark = pytest.mark.unit


@pytest.mark.parametrize(
    ("value", "expected"),
    [
        (None, None),
        ("", None),
        ("   ", None),
        ("\n\t", None),
        (" a ", "a"),
        ("MALAT1", "MALAT1"),
    ],
)
def test_normalize_optional_str(value: str | None, expected: str | None):
    assert normalize_optional_str(value) == expected

