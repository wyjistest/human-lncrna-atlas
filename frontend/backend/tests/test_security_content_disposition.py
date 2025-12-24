import re

import pytest

from app.utils.http_headers import sanitize_filename, content_disposition_attachment
from app.utils.streaming_export import (
    stream_csv_response,
    stream_excel_response,
    stream_jsonl_response,
)


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


def test_streaming_export_responses_use_safe_content_disposition():
    raw = 'evil"\r\nSet-Cookie: pwn=1.csv'

    csv_resp = stream_csv_response(iter([{"a": "1"}]), fieldnames=["a"], filename=raw)
    csv_cd = csv_resp.headers.get("content-disposition", "")
    assert "\r" not in csv_cd
    assert "\n" not in csv_cd
    assert "filename*=" in csv_cd

    jsonl_resp = stream_jsonl_response(iter([{"a": "1"}]), filename=raw)
    jsonl_cd = jsonl_resp.headers.get("content-disposition", "")
    assert "\r" not in jsonl_cd
    assert "\n" not in jsonl_cd
    assert "filename*=" in jsonl_cd

    # Excel export uses openpyxl; keep the payload tiny to avoid test overhead.
    xlsx_resp = stream_excel_response(iter([{"a": "1"}]), fieldnames=["a"], filename=raw)
    xlsx_cd = xlsx_resp.headers.get("content-disposition", "")
    assert "\r" not in xlsx_cd
    assert "\n" not in xlsx_cd
    assert "filename*=" in xlsx_cd
