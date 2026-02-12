from __future__ import annotations

from contextlib import contextmanager

import pytest
from starlette.requests import Request

import app.core.cache as cache_module
import app.core.database as database_module

import main as main_module


def _make_request(path: str = "/health") -> Request:
    scope = {
        "type": "http",
        "http_version": "1.1",
        "method": "GET",
        "scheme": "http",
        "path": path,
        "raw_path": path.encode("utf-8"),
        "query_string": b"",
        "headers": [(b"host", b"localhost")],
        "client": ("127.0.0.1", 12345),
        "server": ("localhost", 8000),
        "root_path": "",
        "app": None,
    }
    return Request(scope)


class _DummyConn:
    def execute(self, *_args, **_kwargs):
        return None


@contextmanager
def _dummy_connect():
    yield _DummyConn()


class _DummyEngine:
    def connect(self):
        return _dummy_connect()


@pytest.mark.unit
@pytest.mark.parametrize(
    ("db_name", "expected_mode"),
    [
        ("lncrna_production", "production"),
        ("lncrna_baseline", "baseline"),
        ("custom_db", "custom"),
    ],
)
def test_root_includes_db_meta(monkeypatch, db_name: str, expected_mode: str):
    monkeypatch.setattr(main_module.settings, "DATABASE_NAME", db_name, raising=False)

    data = main_module.read_root()

    assert data["db_name"] == db_name
    assert data["db_mode"] == expected_mode


@pytest.mark.unit
@pytest.mark.parametrize(
    ("db_name", "expected_mode"),
    [
        ("lncrna_production", "production"),
        ("lncrna_baseline", "baseline"),
        ("custom_db", "custom"),
    ],
)
def test_health_includes_db_meta(monkeypatch, db_name: str, expected_mode: str):
    monkeypatch.setattr(main_module.settings, "DATABASE_NAME", db_name, raising=False)
    monkeypatch.setattr(cache_module.settings, "ENABLE_CACHE", False, raising=False)
    monkeypatch.setattr(database_module, "engine", _DummyEngine())

    target = getattr(main_module.health_check, "__wrapped__", main_module.health_check)
    resp = target(_make_request())

    assert resp.db_name == db_name
    assert resp.db_mode == expected_mode
