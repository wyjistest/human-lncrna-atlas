"""
请求大小/查询字符串长度限制中间件（纯 ASGI）

目标：
- 抵御 DoS：通过超大请求体（JSON/Form）或超长查询字符串消耗内存/CPU。

实现说明：
- 采用纯 ASGI 中间件，避免 BaseHTTPMiddleware 在 StreamingResponse 场景下的已知限制。
- 优先检查 Content-Length（若存在且可解析），可在不读取 body 的情况下快速拒绝。
- 对缺失 Content-Length 的请求，包装 receive() 统计累计 body 字节数，超限即返回 413。

注意：
- 这是应用层兜底；生产环境建议同时在反向代理层配置更严格的限制（例如 client_max_body_size）。
"""

from __future__ import annotations

import logging
from typing import Optional

from fastapi.responses import JSONResponse
from starlette.types import ASGIApp, Receive, Scope, Send

from app.core.config import settings

logger = logging.getLogger("api")


class _RequestBodyTooLarge(Exception):
    """内部异常：用于中断读取请求体并返回 413。"""


class RequestLimitsMiddleware:
    """
    统一的请求大小/查询字符串长度限制中间件。

    Args:
        max_body_size: 最大请求体大小（字节）。None 表示使用 settings.MAX_REQUEST_BODY_SIZE
        max_query_string_length: 最大查询字符串长度（字节）。None 表示使用 settings.MAX_QUERY_STRING_LENGTH
    """

    def __init__(
        self,
        app: ASGIApp,
        *,
        max_body_size: Optional[int] = None,
        max_query_string_length: Optional[int] = None,
    ) -> None:
        self.app = app
        self._max_body_size = int(
            settings.MAX_REQUEST_BODY_SIZE if max_body_size is None else max_body_size
        )
        self._max_query_string_length = int(
            settings.MAX_QUERY_STRING_LENGTH
            if max_query_string_length is None
            else max_query_string_length
        )

    @staticmethod
    def _json_error(status_code: int, error: str, message: str, **extra):
        return JSONResponse(
            status_code=status_code,
            content={
                "detail": {
                    "error": error,
                    "message": message,
                    **extra,
                }
            },
        )

    @staticmethod
    def _get_header(scope: Scope, name: bytes) -> Optional[bytes]:
        for k, v in scope.get("headers", []) or []:
            if k.lower() == name:
                return v
        return None

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        if scope["type"] != "http":
            await self.app(scope, receive, send)
            return

        # 1) Query string length (bytes) – reject early to avoid heavy parsing.
        if self._max_query_string_length > 0:
            query_string = scope.get("query_string") or b""
            if len(query_string) > self._max_query_string_length:
                logger.warning(
                    "Query string too long: %s bytes (max=%s) path=%s",
                    len(query_string),
                    self._max_query_string_length,
                    scope.get("path", ""),
                )
                resp = self._json_error(
                    status_code=414,
                    error="QUERY_STRING_TOO_LONG",
                    message="Query string too long",
                    max_bytes=self._max_query_string_length,
                    actual_bytes=len(query_string),
                )
                await resp(scope, receive, send)
                return

        # 2) Request body size (bytes)
        if self._max_body_size <= 0:
            await self.app(scope, receive, send)
            return

        content_length: Optional[int] = None
        raw = self._get_header(scope, b"content-length")
        if raw:
            try:
                content_length = int(raw.decode("ascii", errors="ignore").strip())
            except Exception:
                content_length = None

        # Fast-fail when client declares an oversized body.
        if content_length is not None and content_length > self._max_body_size:
            logger.warning(
                "Request body too large (Content-Length): %s bytes (max=%s) path=%s",
                content_length,
                self._max_body_size,
                scope.get("path", ""),
            )
            resp = self._json_error(
                status_code=413,
                error="REQUEST_BODY_TOO_LARGE",
                message="Request body too large",
                max_bytes=self._max_body_size,
                actual_bytes=content_length,
            )
            await resp(scope, receive, send)
            return

        received = 0

        async def limited_receive() -> dict:
            nonlocal received
            message = await receive()
            if message.get("type") == "http.request":
                body = message.get("body", b"") or b""
                received += len(body)
                if received > self._max_body_size:
                    raise _RequestBodyTooLarge
            return message

        try:
            await self.app(scope, limited_receive, send)
        except _RequestBodyTooLarge:
            logger.warning(
                "Request body too large (streamed): %s bytes (max=%s) path=%s",
                received,
                self._max_body_size,
                scope.get("path", ""),
            )
            resp = self._json_error(
                status_code=413,
                error="REQUEST_BODY_TOO_LARGE",
                message="Request body too large",
                max_bytes=self._max_body_size,
                actual_bytes=received,
            )
            await resp(scope, receive, send)

