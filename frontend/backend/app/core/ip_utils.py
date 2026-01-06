"""
统一的 IP 地址处理工具

提供反向代理场景下的真实客户端 IP 识别、私网 IP 判断等功能。
Admin 鉴权和限流模块共用此实现，避免策略分叉。

安全说明:
- 仅当直接连接 IP 在 TRUSTED_PROXIES 列表中时，才信任 X-Forwarded-For 头
- 这可以防止攻击者伪造 X-Forwarded-For 绕过 IP 白名单或限流
- 生产环境中必须正确配置 TRUSTED_PROXIES（只添加代理 IP，不要信任整段私网网段）
"""

import ipaddress
import logging
import re
from typing import Optional

from fastapi import Request

from app.core.config import settings

logger = logging.getLogger(__name__)


_XFF_CONTROL_CHARS_RE = re.compile(r"[\x00-\x1f\x7f]+")


def parse_x_forwarded_for(forwarded_for: str) -> Optional[str]:
    """
    Parse and validate the first IP from an X-Forwarded-For header value.

    Security goals:
    - Prevent log injection / header smuggling via control characters.
    - Ensure downstream auth / rate limiting uses a real IP address.

    Notes:
    - Only the first entry is considered (original client IP): "client, proxy1, proxy2".
    - Best-effort support for common non-standard formats like:
      - "1.2.3.4:1234" (IPv4 with port)
      - "[2001:db8::1]:1234" (IPv6 with port)
    """
    if not forwarded_for:
        return None

    # Avoid spending time on extremely large headers.
    raw = forwarded_for[:512]

    first = raw.split(",")[0]
    first = _XFF_CONTROL_CHARS_RE.sub(" ", first).strip()
    if not first:
        return None

    # Some proxies accidentally forward "Forwarded: for=..." into XFF.
    if first.lower().startswith("for="):
        first = first[4:].strip()

    # Trim surrounding quotes.
    first = first.strip().strip('"').strip("'").strip()
    if not first:
        return None

    # If there is trailing junk after the IP (e.g. after control chars), keep the first token.
    parts = first.split()
    if parts:
        first = parts[0]

    # IPv6 with port: [2001:db8::1]:1234
    if first.startswith("[") and "]" in first:
        first = first[1:first.index("]")]
    else:
        # IPv4 with port: 1.2.3.4:1234
        if first.count(":") == 1 and "." in first:
            host, port = first.split(":", 1)
            if port.isdigit():
                first = host

    try:
        ip = ipaddress.ip_address(first)
    except ValueError:
        return None

    return str(ip)


def is_private_ip(ip_str: str) -> bool:
    """
    检查 IP 地址是否为私有/内网地址

    包括:
    - 私有地址: 10.0.0.0/8, 172.16.0.0/12, 192.168.0.0/16
    - 回环地址: 127.0.0.0/8, ::1
    - 链路本地: 169.254.0.0/16, fe80::/10

    Args:
        ip_str: IP 地址字符串

    Returns:
        True 如果是私有/内网地址，否则 False
    """
    try:
        ip = ipaddress.ip_address(ip_str)
        return ip.is_private or ip.is_loopback or ip.is_link_local
    except ValueError:
        return False


def is_trusted_proxy(ip_str: str) -> bool:
    """
    检查 IP 地址是否为受信任的代理服务器

    仅当请求来自受信任的代理时，才应信任 X-Forwarded-For 头。
    这可以防止 IP 欺骗攻击。

    Args:
        ip_str: 连接客户端的 IP 地址字符串

    Returns:
        True 如果 IP 在 settings.TRUSTED_PROXIES 列表中，否则 False
    """
    try:
        ip = ipaddress.ip_address(ip_str)
        for proxy in settings.TRUSTED_PROXIES:
            try:
                # 检查是否为 CIDR 网段（如 10.0.0.0/8）
                if "/" in proxy:
                    network = ipaddress.ip_network(proxy, strict=False)
                    if ip in network:
                        return True
                else:
                    # 单个 IP 地址
                    if ip == ipaddress.ip_address(proxy):
                        return True
            except ValueError:
                # 无效的代理配置，跳过
                continue
        return False
    except ValueError:
        return False


def get_client_ip(request: Request) -> str:
    """
    获取客户端真实 IP 地址

    安全策略：仅当请求来自受信任的代理时，才信任 X-Forwarded-For 头。
    这可以防止攻击者伪造 X-Forwarded-For 头来绕过 IP 白名单限制。

    X-Forwarded-For 格式: "client, proxy1, proxy2"
    - 取第一个 IP 作为原始客户端 IP

    Args:
        request: FastAPI Request 对象

    Returns:
        客户端 IP 地址字符串
    """
    # 获取直接连接的客户端 IP
    direct_ip = request.client.host if request.client else "unknown"

    # 仅当直接连接来自受信任的代理时，才检查 X-Forwarded-For
    if is_trusted_proxy(direct_ip):
        forwarded_for = request.headers.get("X-Forwarded-For")
        if forwarded_for:
            client_ip = parse_x_forwarded_for(forwarded_for)
            if client_ip:
                logger.debug("Trusted proxy %s, using X-Forwarded-For: %s", direct_ip, client_ip)
                return client_ip

    # 直接连接场景或不信任的代理
    return direct_ip


def get_rate_limit_key(request: Request) -> str:
    """
    获取限流使用的 key

    与 get_client_ip 相同，确保限流基于真实客户端 IP 而非代理 IP。
    这可以避免反向代理场景下所有请求共享同一个限流 key。

    Args:
        request: FastAPI Request 对象

    Returns:
        用于限流的 IP 地址字符串
    """
    return get_client_ip(request)


def should_bypass_rate_limit(request: Request) -> bool:
    """
    判断是否应跳过限流

    规则：
    - 非 production 环境：回环地址（127.0.0.0/8, ::1）默认跳过限流，避免本机开发/端到端测试因并发触发 429。
    - 任意环境：当 settings.RATE_LIMIT_BYPASS_PRIVATE=true 时，私网 IP 可跳过限流（生产环境建议关闭）。

    Args:
        request: FastAPI Request 对象

    Returns:
        True 如果应跳过限流，否则 False
    """
    client_ip = get_client_ip(request)

    # 开发/测试环境：本机请求默认不受限流影响，避免 UI / Playwright E2E 在高并发下触发 429。
    if getattr(settings, "ENV", "development") != "production":
        try:
            ip = ipaddress.ip_address(client_ip)
            if ip.is_loopback:
                return True
        except ValueError:
            pass

    # 可选：私网 bypass（仅当显式开启时）
    if getattr(settings, "RATE_LIMIT_BYPASS_PRIVATE", False):
        return is_private_ip(client_ip)

    return False


__all__ = [
    "is_private_ip",
    "is_trusted_proxy",
    "get_client_ip",
    "get_rate_limit_key",
    "should_bypass_rate_limit",
    "parse_x_forwarded_for",
]
