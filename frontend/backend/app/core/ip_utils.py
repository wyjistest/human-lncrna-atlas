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

from fastapi import Request

from app.core.config import settings

logger = logging.getLogger(__name__)


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
            # 取第一个 IP（客户端原始 IP）
            client_ip = forwarded_for.split(",")[0].strip()
            logger.debug(f"Trusted proxy {direct_ip}, using X-Forwarded-For: {client_ip}")
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

    根据 settings.RATE_LIMIT_BYPASS_PRIVATE 配置决定是否对私网 IP 放行。
    生产环境建议关闭此选项。

    Args:
        request: FastAPI Request 对象

    Returns:
        True 如果应跳过限流，否则 False
    """
    # 如果配置禁用私网 bypass，总是执行限流
    if not getattr(settings, 'RATE_LIMIT_BYPASS_PRIVATE', False):
        return False

    client_ip = get_client_ip(request)
    return is_private_ip(client_ip)


__all__ = [
    "is_private_ip",
    "is_trusted_proxy",
    "get_client_ip",
    "get_rate_limit_key",
    "should_bypass_rate_limit",
]
