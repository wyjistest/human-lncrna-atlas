"""
日志中间件 - 纯 ASGI 实现

使用纯 ASGI 中间件代替 BaseHTTPMiddleware，解决与 StreamingResponse 的兼容性问题。
Starlette 文档警告 BaseHTTPMiddleware 在处理 StreamingResponse 时有局限性。
"""
import time
import logging
from typing import List, Tuple
from starlette.types import ASGIApp, Receive, Scope, Send

logger = logging.getLogger("api")


class LoggingMiddleware:
    """
    请求日志中间件（纯 ASGI 实现）

    优势：
    - 完全兼容 StreamingResponse
    - 不缓冲响应体
    - 更低的内存开销
    """

    # 跳过日志记录的路径前缀
    SKIP_PATHS: List[str] = ["/genomes", "/metrics", "/health"]

    def __init__(self, app: ASGIApp):
        self.app = app

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        if scope["type"] != "http":
            await self.app(scope, receive, send)
            return

        # 获取请求路径
        path = scope.get("path", "")

        # 跳过指定路径（静态文件、metrics 等）
        if any(path.startswith(prefix) for prefix in self.SKIP_PATHS):
            await self.app(scope, receive, send)
            return

        # 记录请求开始时间
        start_time = time.time()

        # 获取请求信息
        method = scope.get("method", "UNKNOWN")
        query_string = scope.get("query_string", b"").decode(errors="replace")
        url = f"{path}?{query_string}" if query_string else path

        # 获取客户端 IP
        client = scope.get("client")
        client_ip = client[0] if client else "unknown"

        # 状态码存储
        status_code: int = 0
        response_started = False

        async def send_wrapper(message: dict) -> None:
            nonlocal status_code, response_started

            if message["type"] == "http.response.start":
                status_code = message.get("status", 0)
                response_started = True

                # 计算处理时间并添加到响应头
                process_time = time.time() - start_time
                headers: List[Tuple[bytes, bytes]] = list(message.get("headers", []))
                headers.append((b"x-process-time", f"{process_time:.3f}".encode()))
                message = {**message, "headers": headers}

            await send(message)

        try:
            await self.app(scope, receive, send_wrapper)

            # 记录成功日志
            process_time = time.time() - start_time
            logger.info(
                f"{method} {url} - {status_code} - "
                f"{process_time:.3f}s - {client_ip}"
            )

        except Exception as e:
            # 记录错误日志
            process_time = time.time() - start_time
            logger.error(
                f"{method} {url} - ERROR - {process_time:.3f}s - "
                f"{client_ip} - {str(e)}"
            )
            raise
