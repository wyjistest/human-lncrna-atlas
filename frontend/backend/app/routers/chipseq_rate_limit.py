"""
ChIP-seq 子路由共享的公共能力：限流装饰器与常量。

目标：
- 打破 `app.routers.chipseq` 与各子路由之间的循环依赖
- 让所有 ChIP-seq 子路由复用同一个 slowapi Limiter 实例
"""

import ipaddress
import inspect
import logging
from functools import wraps

from fastapi import Request
from fastapi.responses import JSONResponse

logger = logging.getLogger(__name__)

# Default flanking region for gene queries (10kb)
DEFAULT_FLANKING_REGION = 10000


# ============================================================================
# Rate Limiting Setup (slowapi)
# ============================================================================
try:
    from slowapi import Limiter
    from slowapi.util import get_remote_address

    SLOWAPI_AVAILABLE = True
except ImportError:  # pragma: no cover - 依赖缺失时走降级逻辑
    SLOWAPI_AVAILABLE = False
    Limiter = None


if SLOWAPI_AVAILABLE and Limiter:
    limiter = Limiter(key_func=get_remote_address)
    chipseq_limiter = limiter
else:
    limiter = None
    chipseq_limiter = None


def rate_limit(limit_string: str):
    """
    Rate limiting decorator that gracefully handles missing slowapi.

    Args:
        limit_string: Rate limit string (e.g., "30/minute", "5/minute")
    """

    def decorator(func):
        if not (SLOWAPI_AVAILABLE and limiter):
            return func

        limited_func = limiter.limit(limit_string)(func)

        def _is_private_request(req: Request) -> bool:
            client_ip = req.client.host if req.client else ""
            try:
                ip = ipaddress.ip_address(client_ip)
                return ip.is_private or ip.is_loopback or ip.is_link_local
            except ValueError:
                return False

        if inspect.iscoroutinefunction(func):

            @wraps(func)
            async def async_wrapper(*args, **kwargs):
                request = next((v for v in kwargs.values() if isinstance(v, Request)), None) or next(
                    (a for a in args if isinstance(a, Request)), None
                )
                if request and _is_private_request(request):
                    return await func(*args, **kwargs)
                return await limited_func(*args, **kwargs)

            return async_wrapper

        @wraps(func)
        def sync_wrapper(*args, **kwargs):
            request = next((v for v in kwargs.values() if isinstance(v, Request)), None) or next(
                (a for a in args if isinstance(a, Request)), None
            )
            if request and _is_private_request(request):
                return func(*args, **kwargs)
            return limited_func(*args, **kwargs)

        return sync_wrapper

    return decorator


async def rate_limit_exceeded_handler(request: Request, exc):
    """Custom handler for rate limit exceeded errors"""
    return JSONResponse(
        status_code=429,
        content={
            "success": False,
            "error": {
                "code": "RATE_LIMIT_EXCEEDED",
                "message": "Too many requests. Please try again later.",
                "detail": str(exc.detail) if hasattr(exc, "detail") else "Rate limit exceeded",
                "retry_after": getattr(exc, "retry_after", 60),
            },
        },
    )


__all__ = [
    "DEFAULT_FLANKING_REGION",
    "SLOWAPI_AVAILABLE",
    "limiter",
    "chipseq_limiter",
    "rate_limit",
    "rate_limit_exceeded_handler",
]

