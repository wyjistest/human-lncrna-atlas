from app.middleware.logging import LoggingMiddleware


def _make_scope(*, client_ip: str | None, headers: list[tuple[bytes, bytes]] | None = None) -> dict:
    # LoggingMiddleware._get_client_ip 只依赖 scope["client"] 与 scope["headers"]，
    # 这里提供最小 ASGI scope 即可。
    return {
        "type": "http",
        "client": (client_ip, 12345) if client_ip is not None else None,
        "headers": headers or [],
    }


def test_get_client_ip_trusted_proxy_uses_x_forwarded_for():
    scope = _make_scope(
        client_ip="127.0.0.1",
        headers=[(b"x-forwarded-for", b"8.8.8.8, 1.1.1.1")],
    )
    assert LoggingMiddleware._get_client_ip(scope) == "8.8.8.8"


def test_get_client_ip_untrusted_proxy_ignores_x_forwarded_for():
    scope = _make_scope(
        client_ip="203.0.113.5",
        headers=[(b"x-forwarded-for", b"8.8.8.8")],
    )
    assert LoggingMiddleware._get_client_ip(scope) == "203.0.113.5"


def test_get_client_ip_missing_forwarded_for_returns_direct_ip():
    scope = _make_scope(client_ip="127.0.0.1")
    assert LoggingMiddleware._get_client_ip(scope) == "127.0.0.1"


def test_get_client_ip_missing_client_returns_unknown():
    scope = _make_scope(client_ip=None)
    assert LoggingMiddleware._get_client_ip(scope) == "unknown"


def test_truncate_for_log_keeps_short_text():
    text = "/api/v1/genes?species_id=1"
    assert LoggingMiddleware._truncate_for_log(text, 2048) == text


def test_truncate_for_log_respects_max_length_and_suffix():
    long_text = "/api/v1/genes?" + ("q=" + "x" * 5000)
    truncated = LoggingMiddleware._truncate_for_log(long_text, 80)
    assert len(truncated) == 80
    assert truncated.startswith("/api/v1/genes?")
    assert truncated.endswith("...[TRUNC]")


def test_truncate_for_log_small_max_length_does_not_append_suffix():
    long_text = "x" * 100
    truncated = LoggingMiddleware._truncate_for_log(long_text, 5)
    assert len(truncated) == 5
    assert truncated == "x" * 5
