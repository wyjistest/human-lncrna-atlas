"""
日志中间件 - 纯 ASGI 实现

使用纯 ASGI 中间件代替 BaseHTTPMiddleware，解决与 StreamingResponse 的兼容性问题。
Starlette 文档警告 BaseHTTPMiddleware 在处理 StreamingResponse 时有局限性。

配置选项 (通过环境变量):
- REQUEST_LOG_ENABLED: 是否启用请求日志 (默认 true)
- REQUEST_LOG_SLOW_THRESHOLD_MS: 仅记录慢请求阈值（毫秒），0 表示记录全部
- REQUEST_LOG_SAMPLE_RATE: 请求日志采样率 0.0-1.0 (默认 1.0 = 100%)
"""
import random
import time
import logging
from typing import List, Tuple
from starlette.types import ASGIApp, Receive, Scope, Send

from app.core.config import settings

logger = logging.getLogger("api")


class LoggingMiddleware:
    """
    请求日志中间件（纯 ASGI 实现）

    优势：
    - 完全兼容 StreamingResponse
    - 不缓冲响应体
    - 更低的内存开销
    - 可配置：启用/禁用、慢请求阈值、采样率
    """

    # 跳过日志记录的路径前缀
    SKIP_PATHS: List[str] = ["/genomes", "/metrics", "/health"]

    def __init__(self, app: ASGIApp):
        self.app = app
        self._log_enabled = settings.REQUEST_LOG_ENABLED
        self._slow_threshold_sec = settings.REQUEST_LOG_SLOW_THRESHOLD_MS / 1000.0
        self._sample_rate = max(0.0, min(1.0, settings.REQUEST_LOG_SAMPLE_RATE))

        # 启动时记录配置
        if self._log_enabled:
            config_info = []
            if self._slow_threshold_sec > 0:
                config_info.append(f"slow_threshold={settings.REQUEST_LOG_SLOW_THRESHOLD_MS}ms")
            if self._sample_rate < 1.0:
                config_info.append(f"sample_rate={self._sample_rate:.0%}")
            if config_info:
                logger.info(f"Request logging configured: {', '.join(config_info)}")
            else:
                logger.info("Request logging enabled (all requests)")
        else:
            logger.info("Request logging disabled")

    def _should_log(self, process_time: float) -> bool:
        """根据配置判断是否应该记录日志"""
        if not self._log_enabled:
            return False

        # 慢请求阈值检查（如果设置了阈值）
        if self._slow_threshold_sec > 0 and process_time < self._slow_threshold_sec:
            return False

        # 采样率检查
        if self._sample_rate < 1.0 and random.random() > self._sample_rate:
            return False

        return True

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

            # 根据配置决定是否记录日志
            process_time = time.time() - start_time
            if self._should_log(process_time):
                # 慢请求使用 WARNING 级别
                if self._slow_threshold_sec > 0 and process_time >= self._slow_threshold_sec:
                    logger.warning(
                        f"SLOW {method} {url} - {status_code} - "
                        f"{process_time:.3f}s - {client_ip}"
                    )
                else:
                    logger.info(
                        f"{method} {url} - {status_code} - "
                        f"{process_time:.3f}s - {client_ip}"
                    )

        except Exception as e:
            # 错误日志始终记录（不受采样/阈值限制）
            process_time = time.time() - start_time
            logger.error(
                f"{method} {url} - ERROR - {process_time:.3f}s - "
                f"{client_ip} - {str(e)}"
            )
            raise
