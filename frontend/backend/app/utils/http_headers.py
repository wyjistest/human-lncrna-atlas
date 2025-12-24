"""
HTTP header utilities (security-focused).

This module centralizes safe header construction for download responses.

Security goals:
- Prevent response splitting / header injection via CRLF in user-controlled filenames
- Keep filenames ASCII-only using a strict whitelist
- Provide a safe Content-Disposition value for attachments

Whitelist charset: [A-Za-z0-9._-]
"""

from __future__ import annotations

import re
from urllib.parse import quote


_FILENAME_ALLOWED_RE = re.compile(r"[^A-Za-z0-9._-]+")
_MULTI_UNDERSCORE_RE = re.compile(r"_+")


def sanitize_filename(filename: str, *, default: str = "download", max_length: int = 200) -> str:
    """
    Sanitize a filename for use in HTTP headers.

    Rules:
    - Explicitly strip CR/LF and quotes to prevent header injection.
    - Replace any non-whitelisted characters with underscore.
    - Collapse repeated underscores.
    - Ensure a non-empty fallback.

    Args:
        filename: Input filename (may be user-controlled).
        default: Fallback when sanitized result is empty.
        max_length: Max length to avoid overly large headers (best-effort).

    Returns:
        A safe ASCII filename containing only [A-Za-z0-9._-].
    """
    if not filename:
        return default

    # Remove CR/LF first to prevent response splitting.
    sanitized = filename.replace("\r", "").replace("\n", "")

    # Remove quotes (can break header formatting).
    sanitized = sanitized.replace('"', "").replace("'", "")

    # Replace path separators to avoid confusing filenames.
    sanitized = sanitized.replace("/", "_").replace("\\", "_")

    # Whitelist replacement: anything else becomes underscore.
    sanitized = _FILENAME_ALLOWED_RE.sub("_", sanitized.strip())
    sanitized = _MULTI_UNDERSCORE_RE.sub("_", sanitized).strip("._-")

    if not sanitized:
        sanitized = default

    # Best-effort length cap while preserving a short extension.
    if max_length and len(sanitized) > max_length:
        stem, dot, ext = sanitized.rpartition(".")
        if dot and 1 <= len(ext) <= 10:
            max_stem = max(1, max_length - len(ext) - 1)
            sanitized = f"{stem[:max_stem]}.{ext}"
        else:
            sanitized = sanitized[:max_length]

    # Avoid special path-like names.
    if sanitized in {".", ".."}:
        sanitized = default

    return sanitized


def content_disposition_attachment(filename: str) -> str:
    """
    Build a safe Content-Disposition header value for an attachment.

    Uses both:
    - filename="<ascii>" (legacy, widely supported)
    - filename*=UTF-8''<pct-encoded> (RFC 5987)

    Note: The input is sanitized first, so both parts are safe.
    """
    safe = sanitize_filename(filename)
    encoded = quote(safe, safe="")
    return f"attachment; filename=\"{safe}\"; filename*=UTF-8''{encoded}"


__all__ = ["sanitize_filename", "content_disposition_attachment"]

