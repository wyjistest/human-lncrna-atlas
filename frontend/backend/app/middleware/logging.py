"""
日志和监控中间件
"""
import time
import logging
from fastapi import Request, Response
from starlette.middleware.base import BaseHTTPMiddleware
from typing import Callable

logger = logging.getLogger("api")


class LoggingMiddleware(BaseHTTPMiddleware):
    """请求日志中间件"""

    async def dispatch(self, request: Request, call_next: Callable) -> Response:
        # 记录请求开始
        start_time = time.time()

        # 获取请求信息
        method = request.method
        url = str(request.url)
        client_ip = request.client.host if request.client else "unknown"

        # 处理请求
        try:
            response = await call_next(request)

            # 计算耗时
            process_time = time.time() - start_time

            # 记录日志
            logger.info(
                f"{method} {url} - {response.status_code} - "
                f"{process_time:.3f}s - {client_ip}"
            )

            # 添加响应头
            response.headers["X-Process-Time"] = f"{process_time:.3f}"

            return response

        except Exception as e:
            # 记录错误
            process_time = time.time() - start_time
            logger.error(
                f"{method} {url} - ERROR - {process_time:.3f}s - "
                f"{client_ip} - {str(e)}"
            )
            raise


class MetricsMiddleware(BaseHTTPMiddleware):
    """性能指标中间件"""

    async def dispatch(self, request: Request, call_next: Callable) -> Response:
        start_time = time.time()

        # 获取app.state中的指标数据
        if not hasattr(request.app.state, "metrics_data"):
            request.app.state.metrics_data = {
                "total_requests": 0,
                "total_errors": 0,
                "total_time": 0.0,
            }

        try:
            response = await call_next(request)

            # 更新指标
            request.app.state.metrics_data["total_requests"] += 1
            process_time = time.time() - start_time
            request.app.state.metrics_data["total_time"] += process_time

            # 记录慢请求
            if process_time > 2.0:
                logger.warning(
                    f"Slow request: {request.method} {request.url} - {process_time:.3f}s"
                )

            if response.status_code >= 500:
                request.app.state.metrics_data["total_errors"] += 1

            return response

        except Exception as e:
            request.app.state.metrics_data["total_errors"] += 1
            raise
