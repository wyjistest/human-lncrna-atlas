import re

import pytest

from app.utils.http_headers import sanitize_filename, content_disposition_attachment


pytestmark = pytest.mark.unit


def test_sanitize_filename_whitelist_and_crlf_stripping():
    raw = 'evil"\r\nSet-Cookie: pwn=1; path=/\n../a b🚨.csv'
    safe = sanitize_filename(raw)

    # No CR/LF
    assert "\r" not in safe
    assert "\n" not in safe

    # Only whitelist chars
    assert re.fullmatch(r"[A-Za-z0-9._-]+", safe), f"Unexpected sanitized filename: {safe!r}"


def test_content_disposition_attachment_is_safe_and_rfc5987():
    raw = "report\r\nX-Injected: 1.txt"
    header_value = content_disposition_attachment(raw)

    # No response splitting
    assert "\r" not in header_value
    assert "\n" not in header_value

    # Has both legacy and RFC 5987 parts
    assert "attachment;" in header_value
    assert "filename=" in header_value
    assert "filename*=" in header_value

