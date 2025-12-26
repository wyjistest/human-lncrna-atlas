import pytest

from app.core.utils import sanitize_for_log


@pytest.mark.unit
def test_sanitize_for_log_strips_control_chars():
    raw = "abc\nDEF\r\x00\t\x1b[31mGHI"
    sanitized = sanitize_for_log(raw, max_length=0)

    assert "\n" not in sanitized
    assert "\r" not in sanitized
    assert "\x00" not in sanitized
    assert "\t" not in sanitized
    assert "\x1b" not in sanitized


@pytest.mark.unit
def test_sanitize_for_log_truncates_with_suffix():
    raw = "a" * 100
    sanitized = sanitize_for_log(raw, max_length=12)
    assert sanitized.endswith("...[TRUNC]")
    assert len(sanitized) == 12

