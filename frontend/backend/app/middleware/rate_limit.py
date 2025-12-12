"""
简单的限流中间件（线程安全版本）

注意：为避免本地/内网调试与自动化测试被误伤，
对私有/回环地址默认不做限流。
"""
import time
import asyncio
from collections import defaultdict
import ipaddress
from fastapi import Request, HTTPException
from starlette.middleware.base import BaseHTTPMiddleware
from typing import Callable


class RateLimitMiddleware(BaseHTTPMiddleware):
    """简单的限流中间件（基于IP，线程安全）"""

    def __init__(self, app, requests_per_minute: int = 60):
        super().__init__(app)
        self.requests_per_minute = requests_per_minute
        self.requests: dict[str, list[float]] = defaultdict(list)
        self._lock = asyncio.Lock()
        self._cleanup_counter = 0
        self._cleanup_interval = 100  # 每100个请求清理一次空IP

    @staticmethod
    def _is_private_ip(ip_str: str) -> bool:
        """判断是否为私有/本地 IP（127.0.0.1、10.x、192.168.x 等）"""
        try:
            ip = ipaddress.ip_address(ip_str)
            return ip.is_private or ip.is_loopback or ip.is_link_local
        except ValueError:
            return False

    async def dispatch(self, request: Request, call_next: Callable):
        # 获取客户端IP
        client_ip = request.client.host if request.client else "unknown"

        # 内网/本地访问不限流（避免影响调试与测试）
        if self._is_private_ip(client_ip):
            return await call_next(request)

        # 跳过健康检查、文档和静态文件
        if request.url.path in ["/health", "/docs", "/redoc", "/openapi.json"]:
            return await call_next(request)

        # 跳过静态文件路径（避免 BaseHTTPMiddleware 与流式响应的兼容性问题）
        if request.url.path.startswith("/genomes"):
            return await call_next(request)

        async with self._lock:
            current_time = time.time()

            # 清理过期记录
            self.requests[client_ip] = [
                req_time
                for req_time in self.requests[client_ip]
                if current_time - req_time < 60
            ]

            # 检查限流
            if len(self.requests[client_ip]) >= self.requests_per_minute:
                raise HTTPException(
                    status_code=429,
                    detail=f"Rate limit exceeded. Max {self.requests_per_minute} requests per minute.",
                )

            # 记录请求
            self.requests[client_ip].append(current_time)

            # 定期清理空IP记录（防止内存泄漏）
            self._cleanup_counter += 1
            if self._cleanup_counter >= self._cleanup_interval:
                self._cleanup_counter = 0
                await self._cleanup_empty_ips()

        return await call_next(request)

    async def _cleanup_empty_ips(self):
        """清理没有活跃请求的IP记录"""
        current_time = time.time()
        empty_ips = [
            ip for ip, timestamps in self.requests.items()
            if not timestamps or all(current_time - t >= 60 for t in timestamps)
        ]
        for ip in empty_ips:
            del self.requests[ip]
