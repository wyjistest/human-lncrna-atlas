"""
ChIP-seq 子路由共享的公共能力：限流装饰器与常量。

目标：
- 打破 `app.routers.chipseq` 与各子路由之间的循环依赖
- 让所有 ChIP-seq 子路由复用同一个 slowapi Limiter 实例

安全说明：
- 使用 ip_utils.get_rate_limit_key 确保反向代理场景下正确识别真实客户端 IP
- 私网 bypass 由 settings.RATE_LIMIT_BYPASS_PRIVATE 控制（默认关闭）
"""

import inspect
import logging
from functools import wraps

from fastapi import Request
from fastapi.responses import JSONResponse

from app.core.ip_utils import get_rate_limit_key, should_bypass_rate_limit

logger = logging.getLogger(__name__)

# Default flanking region for gene queries (10kb)
DEFAULT_FLANKING_REGION = 10000


# ============================================================================
# Rate Limiting Setup (slowapi)
# ============================================================================
try:
    from slowapi import Limiter

    SLOWAPI_AVAILABLE = True
except ImportError:  # pragma: no cover - 依赖缺失时走降级逻辑
    SLOWAPI_AVAILABLE = False
    Limiter = None


if SLOWAPI_AVAILABLE and Limiter:
    # 使用自定义 key_func 确保反向代理场景下正确识别真实客户端 IP
    limiter = Limiter(key_func=get_rate_limit_key)
    chipseq_limiter = limiter
else:
    limiter = None
    chipseq_limiter = None


def rate_limit(limit_string: str):
    """
    Rate limiting decorator that gracefully handles missing slowapi.

    安全说明：
    - 使用 ip_utils.should_bypass_rate_limit 判断是否跳过限流
    - 默认情况下所有请求都执行限流（包括私网 IP）
    - 设置 RATE_LIMIT_BYPASS_PRIVATE=true 可启用私网 bypass（仅开发环境）

    Args:
        limit_string: Rate limit string (e.g., "30/minute", "5/minute")
    """

    def decorator(func):
        if not (SLOWAPI_AVAILABLE and limiter):
            return func

        limited_func = limiter.limit(limit_string)(func)

        if inspect.iscoroutinefunction(func):

            @wraps(func)
            async def async_wrapper(*args, **kwargs):
                request = next((v for v in kwargs.values() if isinstance(v, Request)), None) or next(
                    (a for a in args if isinstance(a, Request)), None
                )
                if request and should_bypass_rate_limit(request):
                    return await func(*args, **kwargs)
                return await limited_func(*args, **kwargs)

            return async_wrapper

        @wraps(func)
        def sync_wrapper(*args, **kwargs):
            request = next((v for v in kwargs.values() if isinstance(v, Request)), None) or next(
                (a for a in args if isinstance(a, Request)), None
            )
            if request and should_bypass_rate_limit(request):
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

