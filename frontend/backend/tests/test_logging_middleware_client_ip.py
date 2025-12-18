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

