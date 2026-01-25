"""
请求上下文（ContextVars）

目标：
- 在“无侵入”的前提下，把请求级上下文（例如 route template）传递给底层组件。
- 典型用途：可观测性归因（DB 慢查询、cache 回源 compute 等），不影响主业务链路。

设计说明：
- 使用 ContextVar 保存当前请求的 ASGI scope 引用。
- route template 由 Starlette Router 在匹配后写入 scope["route"]；
  因此只要在最外层 ASGI middleware 里把 scope 放进 ContextVar，
  业务代码（例如 cache.get_or_compute）在 endpoint 内即可拿到 route template。
"""

from __future__ import annotations

from contextvars import ContextVar, Token
from typing import Any, Optional, MutableMapping


_REQUEST_SCOPE: ContextVar[Optional[MutableMapping[str, Any]]] = ContextVar(
    "request_scope",
    default=None,
)


def start_request_scope(scope: MutableMapping[str, Any]) -> Token[Optional[MutableMapping[str, Any]]]:
    """
    绑定当前请求的 ASGI scope 到 ContextVar。

    必须在请求结束时调用 finish_request_scope(token) 进行 reset，
    以避免上下文泄漏到后续请求（尤其是复用 event loop 的场景）。
    """

    return _REQUEST_SCOPE.set(scope)


def finish_request_scope(token: Token[Optional[MutableMapping[str, Any]]]) -> None:
    """重置当前请求的 scope 绑定。"""

    _REQUEST_SCOPE.reset(token)


def get_route_template() -> Optional[str]:
    """
    Best-effort 获取当前请求的 route template。

    返回示例：/api/v1/genes/{gene_id}
    若无法获取（例如未处于请求上下文或非路由请求），返回 None。
    """

    scope = _REQUEST_SCOPE.get()
    if scope is None:
        return None
    route = scope.get("route")
    template = getattr(route, "path", None)
    if isinstance(template, str) and template:
        return template
    return None
