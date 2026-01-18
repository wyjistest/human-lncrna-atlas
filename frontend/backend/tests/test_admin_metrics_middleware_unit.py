import asyncio
import time

import pytest
from fastapi import FastAPI, HTTPException
from fastapi.testclient import TestClient
from starlette.requests import Request

import app.routers.admin as admin_module
from app.middleware.admin_metrics import AdminMetricsMiddleware, create_metrics_data
from app.schemas.monitoring import ProcessInfo, SystemDisk, SystemMemory, SystemMetrics


def _make_request(app: FastAPI, path: str = "/api/v1/admin/metrics") -> Request:
    scope = {
        "type": "http",
        "http_version": "1.1",
        "method": "GET",
        "scheme": "http",
        "path": path,
        "raw_path": path.encode("utf-8"),
        "query_string": b"",
        "headers": [(b"host", b"testserver")],
        "client": ("127.0.0.1", 12345),
        "server": ("testserver", 80),
        "root_path": "",
        "app": app,
    }
    return Request(scope)


@pytest.mark.unit
def test_admin_metrics_middleware_collects_stats_and_skips_admin_prefix():
    app = FastAPI()
    app.state.metrics_data = create_metrics_data(
        response_times_maxlen=100,
        time_series_maxlen=100,
        max_endpoints=10,
    )

    @app.get("/api/v1/test")
    def ok():
        return {"ok": True}

    @app.get("/api/v1/fail")
    def fail():
        raise HTTPException(status_code=500, detail="boom")

    app.add_middleware(AdminMetricsMiddleware)

    with TestClient(app) as client:
        for _ in range(3):
            resp = client.get("/api/v1/test")
            assert resp.status_code == 200

        for _ in range(2):
            resp = client.get("/api/v1/fail")
            assert resp.status_code == 500

        # /api/v1/admin* 默认跳过，避免监控自刷屏
        resp = client.get("/api/v1/admin/skip")
        assert resp.status_code == 404

    data = app.state.metrics_data
    with data["_lock"]:
        assert data["total_requests"] == 5
        assert data["total_errors"] == 2
        assert sum(data["response_time_buckets"].values()) == 5

        endpoints = data["endpoints"]
        assert isinstance(endpoints, dict)
        assert sum(v.get("requests", 0) for v in endpoints.values()) == 5


@pytest.mark.unit
def test_admin_metrics_get_metrics_computes_percentiles(monkeypatch):
    app = FastAPI()
    app.state.start_time = time.time() - 10
    app.state.metrics_data = create_metrics_data()

    @app.get("/api/v1/test")
    def ok():
        return {"ok": True}

    app.add_middleware(AdminMetricsMiddleware)

    with TestClient(app) as client:
        for _ in range(12):
            resp = client.get("/api/v1/test")
            assert resp.status_code == 200

    monkeypatch.setattr(admin_module, "check_database_status", lambda: "ok")
    monkeypatch.setattr(admin_module, "check_cache_status", lambda: "not_configured")
    monkeypatch.setattr(
        admin_module.cache,
        "get_stats",
        lambda: {
            "backend": "memory",
            "enabled": True,
            "hits": 7,
            "misses": 3,
            "total_requests": 10,
            "hit_rate_pct": 70.0,
            "namespaces": {
                "tracked": 2,
                "limit": 10,
                "top": [
                    {
                        "namespace": "genes",
                        "requests": 8,
                        "hits": 6,
                        "misses": 2,
                        "hit_rate_pct": 75.0,
                        "compute_count": 2,
                        "compute_avg_ms": 10.0,
                        "compute_max_ms": 20.0,
                    }
                ],
            },
            "keys": {
                "tracked": 2,
                "limit": 10,
                "top": [
                    {
                        "key": "lncrna:genes:abcdef0123",
                        "namespace": "genes",
                        "requests": 8,
                        "hits": 6,
                        "misses": 2,
                        "hit_rate_pct": 75.0,
                    }
                ],
            },
        },
    )
    monkeypatch.setattr(
        admin_module,
        "get_system_metrics",
        lambda: SystemMetrics(
            cpu_percent=0.0,
            memory=SystemMemory(used_mb=0, total_mb=0, percent=0),
            disk=SystemDisk(used_gb=0, total_gb=0, percent=0),
            process=ProcessInfo(cpu_percent=0, memory_mb=0),
        ),
    )
    monkeypatch.setattr(admin_module, "generate_alerts", lambda **kwargs: [])

    request = _make_request(app)

    # 绕过 slowapi 限流装饰器（只测试业务逻辑）
    get_metrics = admin_module.get_metrics
    if hasattr(get_metrics, "__wrapped__"):
        get_metrics = get_metrics.__wrapped__

    metrics = asyncio.run(get_metrics(request))
    assert metrics.request.total == 12
    assert metrics.errors.total == 0
    assert metrics.response_time_distribution.counts and sum(metrics.response_time_distribution.counts) == 12
    assert metrics.endpoints and sum(e.requests for e in metrics.endpoints) == 12
    assert metrics.percentiles is not None
    assert metrics.cache_stats is not None
    assert metrics.cache_stats.backend == "memory"
    assert metrics.cache_stats.hit_rate_pct == 70.0
    assert metrics.cache_breakdown is not None
    assert metrics.cache_breakdown.namespaces.top[0].namespace == "genes"
    assert metrics.cache_breakdown.keys.top[0].namespace == "genes"


@pytest.mark.unit
def test_admin_metrics_reset_stats_clears_in_memory_counters():
    app = FastAPI()
    app.state.start_time = time.time() - 10
    app.state.metrics_data = create_metrics_data()

    @app.get("/api/v1/test")
    def ok():
        return {"ok": True}

    app.add_middleware(AdminMetricsMiddleware)

    with TestClient(app) as client:
        for _ in range(3):
            resp = client.get("/api/v1/test")
            assert resp.status_code == 200

    data = app.state.metrics_data
    with data["_lock"]:
        assert data["total_requests"] == 3
        assert len(data["response_times"]) == 3

    request = _make_request(app, path="/api/v1/admin/metrics/reset-stats")

    reset_metrics_stats = admin_module.reset_metrics_stats
    if hasattr(reset_metrics_stats, "__wrapped__"):
        reset_metrics_stats = reset_metrics_stats.__wrapped__

    result = asyncio.run(reset_metrics_stats(request))
    assert result["status"] == "success"

    with data["_lock"]:
        assert data["total_requests"] == 0
        assert data["total_errors"] == 0
        assert data["total_time"] == 0.0
        assert len(data["response_times"]) == 0
        assert sum(data["response_time_buckets"].values()) == 0
        assert len(data["time_series"]) == 0
        assert data["current_second"]["timestamp"] == 0
        assert data["current_second"]["requests"] == 0
        assert data["current_second"]["errors"] == 0
        assert data["endpoints"] == {}
