import pytest
from starlette.requests import Request

pytestmark = pytest.mark.unit


def _make_request(*, client_ip: str) -> Request:
    # should_bypass_rate_limit 只依赖 request.client.host 与 request.headers，
    # 构造最小 ASGI scope 即可（不需要 receive）。
    scope = {
        "type": "http",
        "method": "GET",
        "path": "/",
        "headers": [],
        "client": (client_ip, 12345),
        "server": ("testserver", 80),
        "scheme": "http",
        "query_string": b"",
    }
    return Request(scope)


def test_should_bypass_rate_limit_allows_loopback_in_development(monkeypatch: pytest.MonkeyPatch):
    from app.core import ip_utils

    monkeypatch.setattr(ip_utils.settings, "ENV", "development", raising=False)
    monkeypatch.setattr(ip_utils.settings, "RATE_LIMIT_BYPASS_PRIVATE", False, raising=False)

    assert ip_utils.should_bypass_rate_limit(_make_request(client_ip="127.0.0.1")) is True


def test_should_bypass_rate_limit_does_not_bypass_loopback_in_production(monkeypatch: pytest.MonkeyPatch):
    from app.core import ip_utils

    monkeypatch.setattr(ip_utils.settings, "ENV", "production", raising=False)
    monkeypatch.setattr(ip_utils.settings, "RATE_LIMIT_BYPASS_PRIVATE", False, raising=False)

    assert ip_utils.should_bypass_rate_limit(_make_request(client_ip="127.0.0.1")) is False


def test_should_bypass_rate_limit_private_ip_requires_explicit_flag(monkeypatch: pytest.MonkeyPatch):
    from app.core import ip_utils

    monkeypatch.setattr(ip_utils.settings, "ENV", "development", raising=False)

    monkeypatch.setattr(ip_utils.settings, "RATE_LIMIT_BYPASS_PRIVATE", False, raising=False)
    assert ip_utils.should_bypass_rate_limit(_make_request(client_ip="192.168.1.10")) is False

    monkeypatch.setattr(ip_utils.settings, "RATE_LIMIT_BYPASS_PRIVATE", True, raising=False)
    assert ip_utils.should_bypass_rate_limit(_make_request(client_ip="192.168.1.10")) is True

