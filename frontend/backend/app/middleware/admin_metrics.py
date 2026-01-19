"""
Admin Monitoring 指标采集（in-memory）

目标：
- 为前端 `Admin/Monitoring` 页面提供轻量、无需外部依赖的请求级指标
- 不替代 Prometheus：Prometheus `/metrics` 仍是更完整的观测出口

设计约束：
- 纯 ASGI 中间件，避免 BaseHTTPMiddleware 与 StreamingResponse 的已知问题
- 线程安全：写入时加锁；读取端（/api/v1/admin/metrics）应尽量做快照避免长时间持锁
- 低开销：固定窗口、固定 bucket、限制 endpoint 维度，避免高基数导致内存增长
"""

from __future__ import annotations

import logging
import threading
import time
from collections import deque
from typing import Any

from starlette.types import ASGIApp, Receive, Scope, Send

from app.core.config import settings
from app.core.utils import sanitize_for_log

logger = logging.getLogger("api")
_LOCK_TYPE = type(threading.Lock())


def create_metrics_data(
    *,
    response_times_maxlen: int = 2000,
    time_series_maxlen: int = 600,
    max_endpoints: int = 200,
    endpoint_response_times_maxlen: int = 200,
) -> dict[str, Any]:
    """
    创建 Admin metrics 的内部存储结构（挂载到 app.state.metrics_data）。

    说明：
    - total_time：单位秒（与 admin.py 中 avg_ms 的计算逻辑对齐）
    - endpoints[*].total_time：单位毫秒（与 build_endpoints_stats 的 avg_ms 对齐）
    """
    return {
        "_lock": threading.Lock(),
        "total_requests": 0,
        "total_errors": 0,
        "total_time": 0.0,  # seconds
        "response_times": deque(maxlen=max(1, int(response_times_maxlen))),  # milliseconds
        "response_time_buckets": {
            "0-50": 0,
            "50-100": 0,
            "100-200": 0,
            "200-500": 0,
            "500+": 0,
        },
        "time_series": deque(maxlen=max(1, int(time_series_maxlen))),  # per-second entries
        "current_second": {"timestamp": 0, "requests": 0, "errors": 0},
        "endpoints": {},  # path -> {requests, errors, total_time(ms)}
        "_max_endpoints": max(1, int(max_endpoints)),
        "_endpoint_response_times_maxlen": max(1, int(endpoint_response_times_maxlen)),
    }


def ensure_metrics_data(app) -> dict[str, Any]:
    """
    确保 app.state.metrics_data 存在且结构完整（兼容历史版本的 {}）。
    """
    data = getattr(getattr(app, "state", None), "metrics_data", None)
    if not isinstance(data, dict) or "_lock" not in data:
        data = create_metrics_data()
        app.state.metrics_data = data
        return data

    # 补齐缺失字段（best-effort，避免历史残留导致 KeyError）
    data.setdefault("_lock", threading.Lock())
    data.setdefault("total_requests", 0)
    data.setdefault("total_errors", 0)
    data.setdefault("total_time", 0.0)
    data.setdefault("response_times", deque(maxlen=2000))
    data.setdefault(
        "response_time_buckets",
        {"0-50": 0, "50-100": 0, "100-200": 0, "200-500": 0, "500+": 0},
    )
    data.setdefault("time_series", deque(maxlen=600))
    data.setdefault("current_second", {"timestamp": 0, "requests": 0, "errors": 0})
    data.setdefault("endpoints", {})
    data.setdefault("_max_endpoints", 200)
    data.setdefault("_endpoint_response_times_maxlen", 200)
    return data


def _bucket_key(duration_ms: float) -> str:
    if duration_ms < 50:
        return "0-50"
    if duration_ms < 100:
        return "50-100"
    if duration_ms < 200:
        return "100-200"
    if duration_ms < 500:
        return "200-500"
    return "500+"


def _route_template_from_scope(scope: Scope) -> str | None:
    """
    Best-effort 获取路由模板路径（降低 endpoint 维度的高基数风险）。
    """
    route = scope.get("route")
    template = getattr(route, "path", None)
    if isinstance(template, str) and template:
        return template
    return None


class AdminMetricsMiddleware:
    """
    采集请求级指标，写入 app.state.metrics_data。

    - 统计口径：仅统计“非 Admin/非健康检查/非 /metrics/非静态文件”请求，避免监控自刷屏造成噪音。
    - error 口径：仅统计 5xx（更贴近系统错误率告警语义）。
    """

    def __init__(self, app: ASGIApp):
        self.app = app
        api_prefix = (settings.API_V1_PREFIX or "").rstrip("/")
        self._skip_prefixes = (
            "/health",
            "/metrics",
            "/docs",
            "/redoc",
            "/openapi.json",
            "/genomes",
            f"{api_prefix}/admin" if api_prefix else "/api/v1/admin",
        )

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        if scope["type"] != "http":
            await self.app(scope, receive, send)
            return

        path = scope.get("path", "") or ""
        if any(path.startswith(prefix) for prefix in self._skip_prefixes):
            await self.app(scope, receive, send)
            return

        start = time.monotonic()
        status_code: int = 0

        async def send_wrapper(message: dict) -> None:
            nonlocal status_code
            if message.get("type") == "http.response.start":
                status_code = int(message.get("status", 0) or 0)
            await send(message)

        try:
            await self.app(scope, receive, send_wrapper)
        finally:
            duration_sec = max(0.0, time.monotonic() - start)
            duration_ms = duration_sec * 1000.0

            # Best-effort：异常情况下可能未写入 status，按 500 处理更符合“错误率”语义。
            code = status_code or 500
            is_error = 500 <= code <= 599

            app = scope.get("app")
            if app is None:
                return

            try:
                metrics_data = ensure_metrics_data(app)
                lock = metrics_data.get("_lock")
                if not isinstance(lock, _LOCK_TYPE):
                    lock = None

                if lock is None:
                    # 极端降级：无锁写入（尽量不影响主链路）
                    lock_ctx = _NoopLock()
                else:
                    lock_ctx = lock

                with lock_ctx:
                    metrics_data["total_requests"] = int(metrics_data.get("total_requests", 0)) + 1
                    metrics_data["total_time"] = float(metrics_data.get("total_time", 0.0)) + duration_sec
                    if is_error:
                        metrics_data["total_errors"] = int(metrics_data.get("total_errors", 0)) + 1

                    # 响应时间 bucket
                    buckets = metrics_data.get("response_time_buckets") or {}
                    bkey = _bucket_key(duration_ms)
                    buckets[bkey] = int(buckets.get(bkey, 0)) + 1
                    metrics_data["response_time_buckets"] = buckets

                    # 响应时间样本（用于百分位）
                    response_times = metrics_data.get("response_times")
                    if isinstance(response_times, deque):
                        response_times.append(float(duration_ms))
                    else:
                        metrics_data["response_times"] = deque([float(duration_ms)], maxlen=2000)

                    # per-second time series
                    now_ts = int(time.time())
                    current = metrics_data.get("current_second") or {"timestamp": 0, "requests": 0, "errors": 0}
                    if int(current.get("timestamp", 0) or 0) != now_ts:
                        # flush previous second into time_series
                        prev_ts = int(current.get("timestamp", 0) or 0)
                        if prev_ts > 0:
                            series = metrics_data.get("time_series")
                            if not isinstance(series, deque):
                                series = deque(maxlen=600)
                            series.append(
                                {
                                    "timestamp": prev_ts,
                                    "requests": int(current.get("requests", 0) or 0),
                                    "errors": int(current.get("errors", 0) or 0),
                                }
                            )
                            metrics_data["time_series"] = series

                        current = {"timestamp": now_ts, "requests": 0, "errors": 0}
                        metrics_data["current_second"] = current

                    current["requests"] = int(current.get("requests", 0) or 0) + 1
                    if is_error:
                        current["errors"] = int(current.get("errors", 0) or 0) + 1

                    # Endpoint-level stats（尽量使用 route template）
                    template = _route_template_from_scope(scope) or "other"
                    endpoints = metrics_data.get("endpoints")
                    if not isinstance(endpoints, dict):
                        endpoints = {}
                        metrics_data["endpoints"] = endpoints

                    max_endpoints = int(metrics_data.get("_max_endpoints", 200) or 200)
                    endpoint_times_maxlen = max(
                        1,
                        int(metrics_data.get("_endpoint_response_times_maxlen", 200) or 200),
                    )
                    endpoint_key = template
                    if endpoint_key not in endpoints and len(endpoints) >= max_endpoints:
                        endpoint_key = "other"

                    ep = endpoints.get(endpoint_key)
                    if not isinstance(ep, dict):
                        ep = {
                            "requests": 0,
                            "errors": 0,
                            "total_time": 0.0,
                            "response_times": deque(maxlen=endpoint_times_maxlen),
                        }
                        endpoints[endpoint_key] = ep

                    ep["requests"] = int(ep.get("requests", 0) or 0) + 1
                    if is_error:
                        ep["errors"] = int(ep.get("errors", 0) or 0) + 1
                    # NOTE: endpoint total_time 口径为毫秒（与 EndpointStats.avg_ms 对齐）
                    ep["total_time"] = float(ep.get("total_time", 0.0) or 0.0) + float(duration_ms)
                    # Endpoint 响应时间样本（用于百分位；固定窗口，避免高开销与高基数）
                    ep_times = ep.get("response_times")
                    if isinstance(ep_times, deque):
                        ep_times.append(float(duration_ms))
                    else:
                        ep_times = deque(maxlen=endpoint_times_maxlen)
                        ep_times.append(float(duration_ms))
                        ep["response_times"] = ep_times

            except Exception as e:  # pragma: no cover
                # 指标采集必须“绝不影响主请求链路”
                logger.debug("Admin metrics collection failed: %s", sanitize_for_log(e, max_length=2000))


class _NoopLock:
    def __enter__(self) -> None:
        return None

    def __exit__(self, exc_type, exc, tb) -> bool:
        return False
