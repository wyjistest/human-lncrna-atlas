"""
Unit tests: BED/track output sanitization helpers.

These helpers are used to prevent control characters from breaking BED/TSV structure,
and to avoid quote injection in BED track header attributes.
"""

import pytest

from app.utils.bed import sanitize_bed_field, sanitize_bed_track_attr


pytestmark = pytest.mark.unit


def test_sanitize_bed_field_removes_control_chars_and_strips():
    raw = "A\tB\r\nC\x00D  "
    out = sanitize_bed_field(raw)
    assert "\t" not in out
    assert "\r" not in out
    assert "\n" not in out
    assert "\x00" not in out
    assert out == out.strip()
    assert out, "Output should not be empty"


def test_sanitize_bed_field_truncates():
    out = sanitize_bed_field("a" * 1000, max_len=10)
    assert len(out) == 10


def test_sanitize_bed_field_empty_becomes_unknown():
    out = sanitize_bed_field("\t\r\n\x00")
    assert out == "unknown"


def test_sanitize_bed_track_attr_replaces_quotes():
    raw = 'gene"bad\r\nname'
    out = sanitize_bed_track_attr(raw)
    assert '"' not in out
    assert "\r" not in out
    assert "\n" not in out
    assert out, "Output should not be empty"

