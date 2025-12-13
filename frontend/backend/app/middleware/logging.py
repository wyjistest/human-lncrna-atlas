"""
日志中间件
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
        # 跳过静态文件路径（避免 BaseHTTPMiddleware 与流式响应的兼容性问题）
        if request.url.path.startswith("/genomes"):
            return await call_next(request)

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
