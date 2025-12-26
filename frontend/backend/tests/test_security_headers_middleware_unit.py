from fastapi import FastAPI
from fastapi.testclient import TestClient

from app.core.config import settings
from app.middleware.security.headers import add_security_headers


def _make_app() -> FastAPI:
    # Disable built-in docs to avoid route conflicts in unit tests.
    app = FastAPI(docs_url=None, redoc_url=None, openapi_url=None)

    app.middleware("http")(add_security_headers)

    @app.get("/test")
    def test_endpoint():
        return {"ok": True}

    @app.get("/docs")
    def docs_endpoint():
        return {"docs": True}

    @app.get(f"{settings.API_V1_PREFIX}/admin/ping")
    def admin_endpoint():
        return {"admin": True}

    @app.get("/metrics")
    def metrics_endpoint():
        return "ok"

    return app


def test_security_headers_present_on_normal_routes():
    client = TestClient(_make_app())
    response = client.get("/test")

    assert response.headers["X-Content-Type-Options"] == "nosniff"
    assert response.headers["X-Frame-Options"] == "DENY"
    assert response.headers["X-XSS-Protection"] == "1; mode=block"
    assert response.headers["Referrer-Policy"] == "strict-origin-when-cross-origin"
    assert response.headers["Permissions-Policy"] == "geolocation=(), microphone=(), camera=()"
    assert response.headers["X-DNS-Prefetch-Control"] == "off"
    assert response.headers["X-Permitted-Cross-Domain-Policies"] == "none"

    assert "Content-Security-Policy" in response.headers


def test_csp_not_set_on_docs_route():
    client = TestClient(_make_app())
    response = client.get("/docs")
    assert "Content-Security-Policy" not in response.headers


def test_sensitive_endpoints_disable_caching():
    client = TestClient(_make_app())

    response = client.get(f"{settings.API_V1_PREFIX}/admin/ping")
    assert response.headers["Cache-Control"] == "no-store"
    assert response.headers["Pragma"] == "no-cache"

    metrics_response = client.get("/metrics")
    assert metrics_response.headers["Cache-Control"] == "no-store"
    assert metrics_response.headers["Pragma"] == "no-cache"
