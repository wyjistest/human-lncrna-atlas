"""
Prometheus /metrics Endpoint Authentication Middleware

Phase 9.16: 从 main.py 提取
保护 Prometheus /metrics 端点，要求 API Key 认证
"""
import logging
import os
import secrets

from fastapi import Request
from fastapi.responses import JSONResponse

from app.core.config import settings
from app.core.ip_utils import get_client_ip, is_private_ip
from app.core.utils import sanitize_for_log

logger = logging.getLogger(__name__)


def is_prometheus_metrics_enabled() -> bool:
    return os.getenv("ENABLE_METRICS", "False").lower() in {"true", "1"}


async def metrics_auth_middleware(request: Request, call_next):
    """
    保护 Prometheus /metrics 端点，要求 API Key 认证

    此中间件在 prometheus-fastapi-instrumentator 的 /metrics 端点之前执行，
    确保只有经过认证的请求才能访问指标数据。

    认证方式：
    - 严格模式 (ADMIN_REQUIRE_API_KEY=true): 必须提供 X-Admin-API-Key
    - 普通模式: 私有 IP 可跳过认证

    安全原因：
    - Prometheus /metrics 端点可暴露敏感运行时指标（请求量、延迟、错误率等）
    - 攻击者可利用这些信息进行针对性攻击（如在高负载时发起 DDoS）
    """
    def _error(status_code: int, error: str, message: str):
        return JSONResponse(
            status_code=status_code,
            content={"detail": {"error": error, "message": message}},
        )

    # 只拦截 Prometheus /metrics 路径
    #
    # 注意：
    # - 使用 ASGI scope["path"]（不包含 root_path），避免误拦截如 /api/v1/admin/metrics 这类端点
    # - 兼容反向代理 root_path 与尾随斜杠（如 root_path=/api 且 path=/metrics，或 /metrics/）
    scope_path = (request.scope.get("path") or "").rstrip("/")
    if scope_path == "/metrics":
        if not is_prometheus_metrics_enabled():
            return await call_next(request)

        client_ip = get_client_ip(request)
        safe_ip = sanitize_for_log(client_ip, max_length=100)
        api_key = request.headers.get("X-Admin-API-Key")

        # 获取配置的 Admin API Key
        admin_key = None
        if settings.ADMIN_API_KEY:
            admin_key = settings.ADMIN_API_KEY.get_secret_value()

        # 严格模式：必须提供正确的 API Key
        if settings.ADMIN_REQUIRE_API_KEY:
            if not admin_key:
                return _error(500, "SERVER_CONFIG_ERROR", "Admin API key not configured")
            if api_key and secrets.compare_digest(api_key, admin_key):
                return await call_next(request)

            if api_key:
                logger.warning("Invalid Admin API Key for /metrics from %s (strict mode)", safe_ip)
            return _error(403, "ACCESS_DENIED", "Valid X-Admin-API-Key required for /metrics")

        # 普通模式：有效 API Key 或私有 IP 可访问
        # SECURITY: 若配置了 admin_key 且客户端提供了错误的 API Key，则直接拒绝（不回退到私网放行）
        if admin_key and api_key:
            if secrets.compare_digest(api_key, admin_key):
                return await call_next(request)
            logger.warning("Invalid Admin API Key for /metrics from %s", safe_ip)
            return _error(403, "ACCESS_DENIED", "Invalid API Key provided")
        if is_private_ip(client_ip):
            return await call_next(request)

        return _error(403, "ACCESS_DENIED", "Admin access required for /metrics")

    return await call_next(request)
