"""
Admin API 路由

提供系统监控和管理功能端点
Phase 2 增强：响应时间分布、错误趋势、端点统计
Phase 3 增强：系统资源监控、告警、响应时间百分位

安全机制：
- IP 白名单：只允许本地和内网 IP 访问
- API Key 认证：可选的 X-Admin-API-Key 头验证
- 严格模式：ADMIN_REQUIRE_API_KEY=true 时无条件要求 API Key
"""
import os
import re
import secrets
import time
import logging
import shutil
import threading
from datetime import datetime
from typing import Literal, Optional, Sequence
from collections import defaultdict
from urllib.parse import urlsplit

try:
    import psutil  # type: ignore
except ImportError:  # pragma: no cover
    psutil = None  # type: ignore[assignment]
from fastapi import APIRouter, Request, Depends, HTTPException, Header
from pydantic import BaseModel, Field
from sqlalchemy import text

from app.core.database import engine
from app.core.cache import cache
from app.core.config import settings, AlertThresholds
from app.core.ip_utils import get_client_ip, is_private_ip
from app.core.utils import sanitize_for_log
from app.routers.chipseq_rate_limit import rate_limit
from app.schemas.monitoring import (
    MetricsResponse,
    RequestMetrics,
    ErrorMetrics,
    ResponseTimeMetrics,
    HealthMetrics,
    CacheStats,
    CacheBreakdown,
    CacheGetLatencyPercentiles,
    CacheNamespacesBreakdown,
    CacheNamespaceBreakdownItem,
    CacheKeysBreakdown,
    CacheKeyBreakdownItem,
    ResponseTimeDistribution,
    ErrorTrend,
    EndpointStats,
    # Phase 3 新增
    SystemMetrics,
    SystemMemory,
    SystemDisk,
    ProcessInfo,
    Alert,
    PercentileMetrics,
)

logger = logging.getLogger(__name__)
_LOCK_TYPE = type(threading.Lock())


_SAFE_METHODS = {"GET", "HEAD", "OPTIONS"}

def _origin_from_referer(referer: str) -> Optional[str]:
    """
    Best-effort derive an Origin-like value from a Referer header.

    SECURITY:
    - We only use this as defense-in-depth when Origin is missing.
    - We intentionally drop userinfo/path/query/fragment by reconstructing from hostname/port.
    """
    if not referer:
        return None

    try:
        parsed = urlsplit(referer)
    except Exception:
        return None

    scheme = (parsed.scheme or "").lower()
    if scheme not in {"http", "https"}:
        return None

    hostname = parsed.hostname
    if not hostname:
        return None

    try:
        port = parsed.port
    except ValueError:
        return None

    if port:
        return f"{scheme}://{hostname}:{port}"
    return f"{scheme}://{hostname}"


def _enforce_admin_unsafe_origin(request: Request) -> None:
    """
    Best-effort CSRF mitigation for Admin endpoints when IP-based access is enabled.

    Context (FastAPI docs/security):
    - CSRF attacks do not require CORS. A malicious site can trigger cross-site requests from a user's browser.
    - Our Admin API is normally protected by API Key (ADMIN_REQUIRE_API_KEY=true by default).
    - When admins intentionally disable strict mode for local development, we may allow IP-based access.

    Mitigation:
    - For unsafe methods (POST/PUT/PATCH/DELETE), if the browser sends an Origin header, require it to be:
      1) Same-origin as the API server, or
      2) In configured CORS_ORIGINS (frontend origins).
    - Non-browser clients (curl) typically don't send Origin and will not be blocked.
    """
    if request.method.upper() in _SAFE_METHODS:
        return

    origin = (request.headers.get("origin") or "").strip()
    if not origin:
        # Some clients (or privacy settings) omit Origin but still include Referer.
        referer = (request.headers.get("referer") or "").strip()
        origin = _origin_from_referer(referer) or ""
    if not origin:
        return

    backend_origin = str(request.base_url).rstrip("/")
    allowed = {o.lower() for o in settings.CORS_ORIGINS} | {backend_origin.lower()}
    if origin.rstrip("/").lower() not in allowed:
        raise HTTPException(
            status_code=403,
            detail={
                "error": "CSRF_BLOCKED",
                "message": "Origin not allowed for state-changing Admin request",
                "origin": origin,
            },
        )


async def verify_admin_access(
    request: Request,
    x_admin_api_key: Optional[str] = Header(None, alias="X-Admin-API-Key"),
) -> None:
    """
    验证 Admin API 访问权限

    安全检查策略：
    1. 严格模式 (ADMIN_REQUIRE_API_KEY=true): 必须提供正确的 API Key
    2. 普通模式:
       a. 如果提供了正确的 API Key，立即授权访问
       b. 如果提供了错误的 API Key，直接拒绝（避免绕过 Key 验证回退到 IP 放行）
       c. 如果未提供 API Key，且客户端 IP 在白名单或为私有/内网地址，授权访问
       d. 所有检查都失败则拒绝访问

    生产环境强烈建议启用 ADMIN_REQUIRE_API_KEY，防止反向代理场景下
    因 TRUSTED_PROXIES 配置不当导致私网 IP 自动放行被绕过。

    Args:
        request: FastAPI Request 对象
        x_admin_api_key: 可选的 API Key 头

    Raises:
        HTTPException: 403 如果访问被拒绝
    """
    client_ip = get_client_ip(request)

    # 严格模式：必须提供正确的 API Key
    if settings.ADMIN_REQUIRE_API_KEY:
        # SECURITY: 使用 get_secret_value() 获取真实 API Key
        admin_key = settings.ADMIN_API_KEY.get_secret_value() if settings.ADMIN_API_KEY else None
        if not admin_key:
            logger.error("ADMIN_REQUIRE_API_KEY is True but ADMIN_API_KEY is not configured")
            raise HTTPException(
                status_code=500,
                detail={"error": "SERVER_CONFIG_ERROR", "message": "Admin API key not configured"}
            )
        # SECURITY: 使用 secrets.compare_digest 防止时序攻击
        if x_admin_api_key and secrets.compare_digest(x_admin_api_key, admin_key):
            logger.debug(f"Admin API access granted via API Key (strict mode) from {client_ip}")
            return
        logger.warning(f"Admin API access denied (strict mode): invalid or missing API Key from {client_ip}")
        raise HTTPException(
            status_code=403,
            detail={
                "error": "ACCESS_DENIED",
                "message": "Valid API Key required (strict mode enabled)",
            }
        )

    # 普通模式：检查 API Key（如果配置了且提供了）
    # SECURITY: 使用 get_secret_value() 获取真实 API Key
    admin_key = settings.ADMIN_API_KEY.get_secret_value() if settings.ADMIN_API_KEY else None
    if admin_key:
        # SECURITY: 使用 secrets.compare_digest 防止时序攻击
        if x_admin_api_key and secrets.compare_digest(x_admin_api_key, admin_key):
            logger.debug(f"Admin API access granted via API Key from {client_ip}")
            return
        # SECURITY: 提供了错误的 API Key 时直接拒绝，不继续 IP 检查
        # 这避免了攻击者通过提供错误 Key 绕过 Key 验证走 IP 放行
        if x_admin_api_key:
            logger.warning(f"Invalid Admin API Key from {client_ip}, rejecting request")
            raise HTTPException(
                status_code=403,
                detail={
                    "error": "ACCESS_DENIED",
                    "message": "Invalid API Key provided",
                }
            )

    # 检查 IP 白名单
    allowed_ips = settings.ADMIN_ALLOWED_IPS

    # 检查是否在显式白名单中
    if client_ip in allowed_ips or "localhost" in allowed_ips and client_ip == "127.0.0.1":
        # CSRF defense-in-depth: only relevant when strict mode is disabled.
        if not settings.ADMIN_REQUIRE_API_KEY:
            _enforce_admin_unsafe_origin(request)
        logger.debug(f"Admin API access granted via IP whitelist: {client_ip}")
        return

    # 检查是否为私有/内网 IP（仅在非严格模式下）
    if is_private_ip(client_ip):
        # CSRF defense-in-depth: only relevant when strict mode is disabled.
        if not settings.ADMIN_REQUIRE_API_KEY:
            _enforce_admin_unsafe_origin(request)
        logger.warning(
            f"⚠️ SECURITY: Admin API accessed from private IP {client_ip} without API Key. "
            f"This is allowed in development mode (ADMIN_REQUIRE_API_KEY=false) but is a security risk in production. "
            f"Set ADMIN_REQUIRE_API_KEY=true to enforce API Key for all requests."
        )
        return

    # 所有检查都失败，拒绝访问
    logger.warning(f"Admin API access denied for IP: {client_ip}")
    raise HTTPException(
        status_code=403,
        detail={
            "error": "ACCESS_DENIED",
            "message": "Admin API access is restricted to local/internal networks or requires valid API Key",
        }
    )

router = APIRouter(
    prefix="/admin",
    tags=["admin"],
    dependencies=[Depends(verify_admin_access)],  # 所有 Admin 端点需要鉴权
    responses={
        403: {"description": "Access denied - invalid API key or IP not allowed"},
        500: {"description": "Internal server error"},
    },
)


def check_database_status() -> Literal["ok", "error"]:
    """
    检查数据库连接状态

    Returns:
        "ok" 如果连接正常，否则 "error"
    """
    try:
        with engine.connect() as conn:
            conn.execute(text("SELECT 1"))
        return "ok"
    except Exception as e:
        logger.error("Database health check failed: %s", sanitize_for_log(e, max_length=2000), exc_info=True)
        return "error"


def check_cache_status() -> Literal["ok", "error", "not_configured"]:
    """
    检查缓存（Redis）连接状态

    Returns:
        "ok" 如果连接正常
        "error" 如果连接失败
        "not_configured" 如果未配置
    """
    if not cache.enabled:
        return "not_configured"

    if cache.backend == "redis":
        # Redis 已连接
        return "ok"
    else:
        # 回退到内存缓存，表示 Redis 不可用
        return "error"


def determine_health_status(
    db_status: Literal["ok", "error"],
    cache_status: Literal["ok", "error", "not_configured"],
) -> Literal["healthy", "degraded", "down"]:
    """
    根据各组件状态确定整体健康状态

    Args:
        db_status: 数据库状态
        cache_status: 缓存状态

    Returns:
        整体健康状态
    """
    if db_status == "error":
        return "down"
    if cache_status == "error":
        return "degraded"
    return "healthy"


def build_response_time_distribution(metrics_data: dict) -> ResponseTimeDistribution:
    """
    构建响应时间分布数据

    Args:
        metrics_data: 原始指标数据

    Returns:
        ResponseTimeDistribution 模型实例
    """
    buckets_data = metrics_data.get("response_time_buckets", {})
    bucket_labels = ["0-50ms", "50-100ms", "100-200ms", "200-500ms", "500ms+"]
    bucket_keys = ["0-50", "50-100", "100-200", "200-500", "500+"]
    counts = [buckets_data.get(key, 0) for key in bucket_keys]

    return ResponseTimeDistribution(buckets=bucket_labels, counts=counts)


def build_error_trend(metrics_data: dict) -> ErrorTrend:
    """
    构建错误率趋势数据（从 time_series 按分钟聚合，取最近10分钟）

    Args:
        metrics_data: 原始指标数据

    Returns:
        ErrorTrend 模型实例
    """
    time_series = metrics_data.get("time_series", [])
    current_second = metrics_data.get("current_second", {})

    # 将 time_series 转换为列表以便处理
    series_list = list(time_series)

    # 添加当前秒数据（如果存在）
    if current_second.get("timestamp", 0) > 0:
        series_list.append({
            "timestamp": current_second["timestamp"],
            "requests": current_second["requests"],
            "errors": current_second["errors"],
        })

    # 按分钟聚合
    minute_data = defaultdict(lambda: {"requests": 0, "errors": 0})
    for entry in series_list:
        ts = entry.get("timestamp", 0)
        if ts > 0:
            # 将时间戳截断到分钟
            minute_ts = (ts // 60) * 60
            minute_data[minute_ts]["requests"] += entry.get("requests", 0)
            minute_data[minute_ts]["errors"] += entry.get("errors", 0)

    # 获取最近10分钟的数据
    current_time = int(time.time())
    current_minute = (current_time // 60) * 60

    timestamps = []
    error_rates = []

    for i in range(9, -1, -1):  # 从9分钟前到当前分钟
        minute_ts = current_minute - (i * 60)
        time_label = datetime.fromtimestamp(minute_ts).strftime("%H:%M")
        timestamps.append(time_label)

        data = minute_data.get(minute_ts, {"requests": 0, "errors": 0})
        if data["requests"] > 0:
            rate = data["errors"] / data["requests"]
        else:
            rate = 0.0
        error_rates.append(round(rate, 4))

    return ErrorTrend(timestamps=timestamps, error_rates=error_rates)


def build_endpoints_stats(metrics_data: dict, top_n: int = 20) -> list[EndpointStats]:
    """
    构建端点统计数据（按请求数降序排列，Top N）

    Args:
        metrics_data: 原始指标数据
        top_n: 返回的端点数量

    Returns:
        EndpointStats 列表
    """
    endpoints_data = metrics_data.get("endpoints", {})

    stats_list = []
    for path, data in endpoints_data.items():
        requests = data.get("requests", 0)
        errors = data.get("errors", 0)
        total_time = data.get("total_time", 0.0)

        avg_ms = (total_time / requests) if requests > 0 else 0.0
        error_rate = (errors / requests) if requests > 0 else 0.0

        stats_list.append(
            EndpointStats(
                path=path,
                requests=requests,
                avg_ms=round(avg_ms, 2),
                errors=errors,
                error_rate=round(error_rate, 4),
            )
        )

    # 按请求数降序排列，取 Top N
    stats_list.sort(key=lambda x: x.requests, reverse=True)
    return stats_list[:top_n]


def calculate_last_minute_requests(metrics_data: dict) -> int:
    """
    从 time_series 统计最近60秒的请求数

    Args:
        metrics_data: 原始指标数据

    Returns:
        最近一分钟的请求数
    """
    time_series = metrics_data.get("time_series", [])
    current_second = metrics_data.get("current_second", {})

    current_time = int(time.time())
    cutoff_time = current_time - 60

    total = 0

    # 统计 time_series 中最近60秒的数据
    for entry in time_series:
        ts = entry.get("timestamp", 0)
        if ts >= cutoff_time:
            total += entry.get("requests", 0)

    # 添加当前秒数据（如果在范围内）
    if current_second.get("timestamp", 0) >= cutoff_time:
        total += current_second.get("requests", 0)

    return total


# Phase 3 - 系统资源监控函数
def get_system_metrics() -> SystemMetrics:
    """
    获取系统资源指标

    使用 psutil 库获取 CPU、内存、磁盘和当前进程的资源使用情况。
    所有调用都包含异常处理以确保服务稳定性。

    Returns:
        SystemMetrics: 系统资源指标对象
    """
    # psutil 非必需依赖：缺失时返回降级的系统指标，避免 Admin 路由导入失败导致应用无法启动
    if psutil is None:  # pragma: no cover
        logger.warning("psutil is not installed; returning degraded system metrics (zeros)")

        try:
            disk = shutil.disk_usage("/")
            total_gb = disk.total / 1024 / 1024 / 1024
            used_gb = disk.used / 1024 / 1024 / 1024
            disk_info = SystemDisk(
                used_gb=round(used_gb, 2),
                total_gb=round(total_gb, 2),
                percent=round((used_gb / total_gb * 100) if total_gb > 0 else 0.0, 2),
            )
        except Exception:
            disk_info = SystemDisk(used_gb=0, total_gb=0, percent=0)

        return SystemMetrics(
            cpu_percent=0.0,
            memory=SystemMemory(used_mb=0, total_mb=0, percent=0),
            disk=disk_info,
            process=ProcessInfo(cpu_percent=0, memory_mb=0),
        )

    # CPU 使用率（非阻塞模式）
    try:
        cpu_percent = psutil.cpu_percent(interval=None)
    except Exception as e:
        logger.warning("Failed to get CPU percent: %s", sanitize_for_log(e, max_length=2000))
        cpu_percent = 0.0

    # 内存使用情况
    try:
        memory = psutil.virtual_memory()
        memory_info = SystemMemory(
            used_mb=round(memory.used / 1024 / 1024, 2),
            total_mb=round(memory.total / 1024 / 1024, 2),
            percent=round(memory.percent, 2),
        )
    except Exception as e:
        logger.warning("Failed to get memory info: %s", sanitize_for_log(e, max_length=2000))
        memory_info = SystemMemory(used_mb=0, total_mb=0, percent=0)

    # 磁盘使用情况（根目录）
    try:
        disk = psutil.disk_usage("/")
        disk_info = SystemDisk(
            used_gb=round(disk.used / 1024 / 1024 / 1024, 2),
            total_gb=round(disk.total / 1024 / 1024 / 1024, 2),
            percent=round(disk.percent, 2),
        )
    except Exception as e:
        logger.warning("Failed to get disk info: %s", sanitize_for_log(e, max_length=2000))
        disk_info = SystemDisk(used_gb=0, total_gb=0, percent=0)

    # 当前进程信息
    try:
        process = psutil.Process(os.getpid())
        process_info = ProcessInfo(
            cpu_percent=round(process.cpu_percent(), 2),
            memory_mb=round(process.memory_info().rss / 1024 / 1024, 2),
        )
    except Exception as e:
        logger.warning("Failed to get process info: %s", sanitize_for_log(e, max_length=2000))
        process_info = ProcessInfo(cpu_percent=0, memory_mb=0)

    return SystemMetrics(
        cpu_percent=round(cpu_percent, 2),
        memory=memory_info,
        disk=disk_info,
        process=process_info,
    )


def generate_alerts(
    metrics_data: dict,
    system: SystemMetrics,
    avg_response_time_ms: float,
    thresholds: AlertThresholds,
) -> list[Alert]:
    """
    生成告警列表

    根据配置的阈值检查各项指标，生成相应的告警。
    告警分为 warning（接近阈值）和 critical（超过阈值）两个级别。

    Args:
        metrics_data: 原始指标数据
        system: 系统资源指标
        avg_response_time_ms: 平均响应时间（毫秒）
        thresholds: 告警阈值配置

    Returns:
        Alert 列表
    """
    alerts = []

    # 错误率告警
    total_requests = metrics_data.get("total_requests", 0)
    total_errors = metrics_data.get("total_errors", 0)
    error_rate = total_errors / total_requests if total_requests > 0 else 0.0

    if error_rate > thresholds.error_rate:
        alerts.append(
            Alert(
                type="critical",
                metric="error_rate",
                value=round(error_rate, 4),
                threshold=thresholds.error_rate,
                message=f"Error rate {error_rate:.1%} exceeds threshold {thresholds.error_rate:.1%}",
            )
        )
    elif error_rate > thresholds.error_rate * 0.8:
        alerts.append(
            Alert(
                type="warning",
                metric="error_rate",
                value=round(error_rate, 4),
                threshold=thresholds.error_rate,
                message=f"Error rate {error_rate:.1%} approaching threshold {thresholds.error_rate:.1%}",
            )
        )

    # 响应时间告警
    if avg_response_time_ms > thresholds.response_time_ms:
        alerts.append(
            Alert(
                type="critical",
                metric="response_time_ms",
                value=round(avg_response_time_ms, 2),
                threshold=thresholds.response_time_ms,
                message=f"Avg response time {avg_response_time_ms:.0f}ms exceeds threshold {thresholds.response_time_ms:.0f}ms",
            )
        )
    elif avg_response_time_ms > thresholds.response_time_ms * 0.8:
        alerts.append(
            Alert(
                type="warning",
                metric="response_time_ms",
                value=round(avg_response_time_ms, 2),
                threshold=thresholds.response_time_ms,
                message=f"Avg response time {avg_response_time_ms:.0f}ms approaching threshold {thresholds.response_time_ms:.0f}ms",
            )
        )

    # CPU 告警
    if system.cpu_percent > thresholds.cpu_percent:
        alerts.append(
            Alert(
                type="critical",
                metric="cpu_percent",
                value=system.cpu_percent,
                threshold=thresholds.cpu_percent,
                message=f"CPU usage {system.cpu_percent:.1f}% exceeds threshold {thresholds.cpu_percent:.1f}%",
            )
        )
    elif system.cpu_percent > thresholds.cpu_percent * 0.9:
        alerts.append(
            Alert(
                type="warning",
                metric="cpu_percent",
                value=system.cpu_percent,
                threshold=thresholds.cpu_percent,
                message=f"CPU usage {system.cpu_percent:.1f}% approaching threshold {thresholds.cpu_percent:.1f}%",
            )
        )

    # 内存告警
    if system.memory.percent > thresholds.memory_percent:
        alerts.append(
            Alert(
                type="critical",
                metric="memory_percent",
                value=system.memory.percent,
                threshold=thresholds.memory_percent,
                message=f"Memory usage {system.memory.percent:.1f}% exceeds threshold {thresholds.memory_percent:.1f}%",
            )
        )
    elif system.memory.percent > thresholds.memory_percent * 0.9:
        alerts.append(
            Alert(
                type="warning",
                metric="memory_percent",
                value=system.memory.percent,
                threshold=thresholds.memory_percent,
                message=f"Memory usage {system.memory.percent:.1f}% approaching threshold {thresholds.memory_percent:.1f}%",
            )
        )

    return alerts


def calculate_percentiles(response_times: Sequence[float]) -> Optional[PercentileMetrics]:
    """
    计算响应时间百分位

    至少需要10个数据点才能计算有意义的百分位数。

    Args:
        response_times: 响应时间数据队列（毫秒）

    Returns:
        PercentileMetrics 对象，如果数据不足则返回 None
    """
    if len(response_times) < 10:
        return None

    sorted_times = sorted(response_times)
    n = len(sorted_times)

    # 计算百分位索引（使用最近邻法）
    p50_idx = min(int(n * 0.50), n - 1)
    p95_idx = min(int(n * 0.95), n - 1)
    p99_idx = min(int(n * 0.99), n - 1)

    return PercentileMetrics(
        p50_ms=round(sorted_times[p50_idx], 2),
        p95_ms=round(sorted_times[p95_idx], 2),
        p99_ms=round(sorted_times[p99_idx], 2),
    )


@router.get(
    "/metrics",
    response_model=MetricsResponse,
    summary="获取系统监控指标",
    description="""
    返回系统运行状态和性能指标，包括：
    - 健康状态（数据库、缓存、运行时间）
    - 系统资源（CPU、内存）
    - 告警信息

    **说明**：
    - 此端点用于前端 Admin/Monitoring 页面（JSON）
    - 请求级指标为轻量 in-memory 聚合（不依赖 Prometheus 抓取）
    - cache_stats/cache_breakdown 提供缓存命中率与热点分布（namespaces/keys top）
    - 生产环境建议同时接入 Prometheus `/metrics` 获取更完整指标与长期存储
    """,
)
@rate_limit("10/minute")
async def get_metrics(request: Request) -> MetricsResponse:
    """
    获取系统监控指标

    主要用途：
    - 健康检查（数据库、缓存状态）
    - 系统资源监控（CPU、内存）
    - 运行时间和告警

    说明：
    - 该端点用于前端 Admin/Monitoring 页面（JSON）
    - 请求级指标通过 in-memory 方式采集（见 AdminMetricsMiddleware），适合快速排障与轻量监控
    - Prometheus `/metrics` 仍是更完整的观测出口（建议生产环境接入）
    """
    # 获取 metrics_data（优先做快照，避免并发写入导致容器遍历异常）
    metrics_data = getattr(request.app.state, "metrics_data", {}) or {}
    lock = metrics_data.get("_lock")
    if isinstance(lock, _LOCK_TYPE):
        with lock:
            metrics_data = {
                "total_requests": int(metrics_data.get("total_requests", 0) or 0),
                "total_errors": int(metrics_data.get("total_errors", 0) or 0),
                "total_time": float(metrics_data.get("total_time", 0.0) or 0.0),
                "response_time_buckets": dict(metrics_data.get("response_time_buckets", {}) or {}),
                "time_series": list(metrics_data.get("time_series", []) or []),
                "current_second": dict(metrics_data.get("current_second", {}) or {}),
                "endpoints": {
                    k: dict(v) for k, v in (metrics_data.get("endpoints", {}) or {}).items()
                },
                "response_times": list(metrics_data.get("response_times", []) or []),
            }

    total_requests = metrics_data.get("total_requests", 0)
    total_errors = metrics_data.get("total_errors", 0)
    total_time = metrics_data.get("total_time", 0.0)

    # Phase 2 - 从 time_series 计算 last_minute_requests
    last_minute_requests = calculate_last_minute_requests(metrics_data)

    # 计算错误率
    error_rate = total_errors / total_requests if total_requests > 0 else 0.0

    # 计算平均响应时间（毫秒）
    avg_response_time_ms = (
        (total_time / total_requests * 1000) if total_requests > 0 else 0.0
    )

    # 获取运行时间
    start_time = getattr(request.app.state, "start_time", None)
    uptime_seconds = int(time.time() - start_time) if start_time else 0

    # 检查各组件状态
    db_status = check_database_status()
    cache_status = check_cache_status()
    health_status = determine_health_status(db_status, cache_status)

    # 缓存统计摘要（命中率等）。注意：不返回 Redis host 等敏感/环境信息。
    cache_stats: Optional[CacheStats] = None
    cache_breakdown: Optional[CacheBreakdown] = None
    cache_get_latency: Optional[CacheGetLatencyPercentiles] = None
    try:
        stats = cache.get_stats()
        if isinstance(stats, dict):
            hit_rate_pct = float(stats.get("hit_rate_pct", 0.0) or 0.0)
            hit_rate_pct = max(0.0, min(100.0, hit_rate_pct))
            cache_stats = CacheStats(
                backend=str(stats.get("backend") or ""),
                enabled=bool(stats.get("enabled")),
                hits=int(stats.get("hits", 0) or 0),
                misses=int(stats.get("misses", 0) or 0),
                total_requests=int(stats.get("total_requests", 0) or 0),
                hit_rate_pct=hit_rate_pct,
            )

            # 仅返回统计分解信息（namespaces/keys），不返回 Redis host 等敏感信息。
            namespaces = stats.get("namespaces")
            keys = stats.get("keys")
            if isinstance(namespaces, dict) and isinstance(keys, dict):
                ns_top_raw = namespaces.get("top")
                keys_top_raw = keys.get("top")
                if isinstance(ns_top_raw, list) and isinstance(keys_top_raw, list):
                    ns_top: list[CacheNamespaceBreakdownItem] = []
                    for item in ns_top_raw:
                        if not isinstance(item, dict):
                            continue
                        ns_hit_rate_pct = float(item.get("hit_rate_pct", 0.0) or 0.0)
                        ns_hit_rate_pct = max(0.0, min(100.0, ns_hit_rate_pct))
                        ns_top.append(
                            CacheNamespaceBreakdownItem(
                                namespace=str(item.get("namespace") or ""),
                                requests=int(item.get("requests", 0) or 0),
                                hits=int(item.get("hits", 0) or 0),
                                misses=int(item.get("misses", 0) or 0),
                                hit_rate_pct=ns_hit_rate_pct,
                                compute_count=int(item.get("compute_count", 0) or 0),
                                compute_avg_ms=max(0.0, float(item.get("compute_avg_ms", 0.0) or 0.0)),
                                compute_max_ms=max(0.0, float(item.get("compute_max_ms", 0.0) or 0.0)),
                            )
                        )

                    key_top: list[CacheKeyBreakdownItem] = []
                    for item in keys_top_raw:
                        if not isinstance(item, dict):
                            continue
                        key_hit_rate_pct = float(item.get("hit_rate_pct", 0.0) or 0.0)
                        key_hit_rate_pct = max(0.0, min(100.0, key_hit_rate_pct))
                        ns = item.get("namespace")
                        key_top.append(
                            CacheKeyBreakdownItem(
                                key=str(item.get("key") or ""),
                                namespace=str(ns) if ns is not None else None,
                                requests=int(item.get("requests", 0) or 0),
                                hits=int(item.get("hits", 0) or 0),
                                misses=int(item.get("misses", 0) or 0),
                                hit_rate_pct=key_hit_rate_pct,
                            )
                        )

                    cache_breakdown = CacheBreakdown(
                        namespaces=CacheNamespacesBreakdown(
                            tracked=int(namespaces.get("tracked", 0) or 0),
                            limit=int(namespaces.get("limit", 0) or 0),
                            top=ns_top,
                        ),
                        keys=CacheKeysBreakdown(
                            tracked=int(keys.get("tracked", 0) or 0),
                            limit=int(keys.get("limit", 0) or 0),
                            top=key_top,
                        ),
                    )

            # Cache get() latency percentiles (best-effort; may be null if samples are insufficient).
            get_latency = stats.get("get_latency_ms")
            if isinstance(get_latency, dict):
                hits_samples = max(0, int(get_latency.get("hits_samples", 0) or 0))
                misses_samples = max(0, int(get_latency.get("misses_samples", 0) or 0))
                max_samples = max(0, int(get_latency.get("max_samples", 0) or 0))

                hits_pct_raw = get_latency.get("hits")
                misses_pct_raw = get_latency.get("misses")
                hits_pct = None
                misses_pct = None
                if isinstance(hits_pct_raw, dict):
                    hits_pct = PercentileMetrics(
                        p50_ms=max(0.0, float(hits_pct_raw.get("p50_ms", 0.0) or 0.0)),
                        p95_ms=max(0.0, float(hits_pct_raw.get("p95_ms", 0.0) or 0.0)),
                        p99_ms=max(0.0, float(hits_pct_raw.get("p99_ms", 0.0) or 0.0)),
                    )
                if isinstance(misses_pct_raw, dict):
                    misses_pct = PercentileMetrics(
                        p50_ms=max(0.0, float(misses_pct_raw.get("p50_ms", 0.0) or 0.0)),
                        p95_ms=max(0.0, float(misses_pct_raw.get("p95_ms", 0.0) or 0.0)),
                        p99_ms=max(0.0, float(misses_pct_raw.get("p99_ms", 0.0) or 0.0)),
                    )

                cache_get_latency = CacheGetLatencyPercentiles(
                    hits_samples=hits_samples,
                    misses_samples=misses_samples,
                    max_samples=max_samples,
                    hits=hits_pct,
                    misses=misses_pct,
                )
    except Exception as e:  # pragma: no cover
        logger.debug("Failed to build cache stats summary: %s", sanitize_for_log(e, max_length=2000))

    # Phase 2 - 构建新增指标
    response_time_distribution = build_response_time_distribution(metrics_data)
    error_trend = build_error_trend(metrics_data)
    endpoints = build_endpoints_stats(metrics_data, top_n=20)

    # Phase 3 - 系统资源监控
    system_metrics = get_system_metrics()

    # Phase 3 - 生成告警
    alerts = generate_alerts(
        metrics_data=metrics_data,
        system=system_metrics,
        avg_response_time_ms=avg_response_time_ms,
        thresholds=settings.ALERT_THRESHOLDS,
    )

    # Phase 3 - 计算响应时间百分位
    response_times = metrics_data.get("response_times", [])
    percentiles = calculate_percentiles(response_times)

    return MetricsResponse(
        # Phase 1 - 基础指标
        request=RequestMetrics(
            total=total_requests,
            last_minute=last_minute_requests,
        ),
        errors=ErrorMetrics(
            total=total_errors,
            rate=round(error_rate, 4),
        ),
        response_time=ResponseTimeMetrics(
            avg_ms=round(avg_response_time_ms, 2),
        ),
        health=HealthMetrics(
            status=health_status,
            database=db_status,
            cache=cache_status,
            uptime_seconds=uptime_seconds,
        ),
        cache_stats=cache_stats,
        cache_breakdown=cache_breakdown,
        cache_get_latency=cache_get_latency,
        # Phase 2 - 新增指标
        response_time_distribution=response_time_distribution,
        error_trend=error_trend,
        endpoints=endpoints,
        # Phase 3 - 系统监控指标
        system=system_metrics,
        alerts=alerts,
        percentiles=percentiles,
    )


@router.post(
    "/metrics/reset-stats",
    summary="重置监控指标统计",
    description="仅重置 /api/v1/admin/metrics 的 in-memory 统计计数，不影响 Prometheus /metrics。",
)
@rate_limit("5/minute")
async def reset_metrics_stats(request: Request) -> dict:
    """
    重置 Admin Monitoring 指标统计（in-memory）

    说明：
    - 仅影响 `/api/v1/admin/metrics` 使用的 in-memory 聚合数据
    - 不影响 Prometheus `/metrics`（如已接入，仍建议用于长期观测）
    """
    metrics_data = getattr(request.app.state, "metrics_data", None)
    if not isinstance(metrics_data, dict):
        from app.middleware.admin_metrics import create_metrics_data

        request.app.state.metrics_data = create_metrics_data()
        logger.info("Admin metrics stats reset by admin (recreated metrics_data)")
        return {"status": "success", "message": "Admin monitoring metrics reset"}

    lock = metrics_data.get("_lock")
    if isinstance(lock, _LOCK_TYPE):
        with lock:
            metrics_data["total_requests"] = 0
            metrics_data["total_errors"] = 0
            metrics_data["total_time"] = 0.0

            # 清空样本与时间序列（保留 maxlen）
            response_times = metrics_data.get("response_times")
            if hasattr(response_times, "clear"):
                response_times.clear()
            else:
                metrics_data["response_times"] = []

            time_series = metrics_data.get("time_series")
            if hasattr(time_series, "clear"):
                time_series.clear()
            else:
                metrics_data["time_series"] = []

            metrics_data["current_second"] = {"timestamp": 0, "requests": 0, "errors": 0}

            endpoints = metrics_data.get("endpoints")
            if isinstance(endpoints, dict):
                endpoints.clear()
            else:
                metrics_data["endpoints"] = {}

            # 重置 bucket（保留标签集合）
            buckets = metrics_data.get("response_time_buckets")
            if isinstance(buckets, dict):
                for k in list(buckets.keys()):
                    buckets[k] = 0
            else:
                metrics_data["response_time_buckets"] = {"0-50": 0, "50-100": 0, "100-200": 0, "200-500": 0, "500+": 0}

    else:
        # 历史/异常场景：无锁结构直接重建（best-effort）
        from app.middleware.admin_metrics import create_metrics_data

        request.app.state.metrics_data = create_metrics_data()

    logger.info("Admin metrics stats reset by admin")
    return {"status": "success", "message": "Admin monitoring metrics reset"}


# ============================================================================
# Cache Management Endpoints
# ============================================================================


@router.get(
    "/cache/stats",
    summary="获取缓存统计",
    description="返回缓存命中率、后端类型和使用情况",
)
@rate_limit("10/minute")
async def get_cache_stats(request: Request) -> dict:
    """
    获取缓存统计信息

    Returns:
        缓存统计数据，包括命中率、后端类型、请求计数等
    """
    stats = cache.get_stats()
    if isinstance(stats, dict):
        # Provide allowlist for admin UI to avoid frontend/backend drift.
        # SECURITY: This list is informational; the server still enforces allowlist checks.
        stats = dict(stats)
        stats["allowed_namespaces"] = sorted(ALLOWED_CACHE_NAMESPACES)
    return stats


@router.post(
    "/cache/reset-stats",
    summary="重置缓存统计计数器",
    description="仅重置 cache 命中/未命中与 namespace/key 统计，不会清空缓存内容。",
)
@rate_limit("5/minute")
async def reset_cache_stats(request: Request) -> dict:
    """
    重置缓存统计计数器（不影响缓存内容）

    Returns:
        重置后的缓存统计快照（hits/misses 归零）
    """
    cache.reset_stats()
    logger.info("Cache stats reset by admin")
    return {
        "status": "success",
        "message": "Cache stats reset",
        "stats": cache.get_stats(),
    }


@router.post(
    "/cache/clear",
    summary="清空全部缓存",
    description="清空所有 lncrna: 前缀的缓存。操作不可撤销。",
)
@rate_limit("2/minute")
async def clear_cache(request: Request) -> dict:
    """
    清空全部缓存

    Returns:
        删除的缓存条目数量
    """
    deleted = cache.clear_all()
    cache.reset_stats()  # 重置统计计数器
    logger.info(f"Cache cleared by admin: {deleted} entries deleted")
    return {
        "status": "success",
        "deleted": deleted,
        "message": f"Cleared {deleted} cache entries",
    }


# SECURITY: 允许的缓存命名空间白名单
ALLOWED_CACHE_NAMESPACES = {
    "regulations",
    "genes",
    "stats",
    "export",
    "conservation",
    "chipseq",
    "network",
    "diseases",
    "features",
    "igv",
    "analysis",
    "visualization",
}

# SECURITY: 命名空间格式验证（仅允许字母数字和下划线/连字符）
NAMESPACE_PATTERN = re.compile(r'^[a-z0-9_-]{1,32}$')


@router.post(
    "/cache/invalidate/{namespace}",
    summary="按命名空间失效缓存",
    description="""
    使指定命名空间的缓存失效。允许的命名空间：
    - regulations - 调控关系相关缓存
    - genes - 基因相关缓存
    - stats - 统计数据缓存
    - export - 导出相关缓存
    - conservation - 保守性分析缓存
    - chipseq - ChIP-seq 数据缓存
    - network - 网络可视化缓存
    - diseases - 疾病关联缓存
    - features - 基因组特征缓存
    - igv - IGV 浏览器缓存
    - analysis - 分析结果缓存
    - visualization - 可视化数据缓存
    """,
)
@rate_limit("5/minute")
async def invalidate_cache_namespace(request: Request, namespace: str) -> dict:
    """
    按命名空间失效缓存

    Args:
        namespace: 缓存命名空间（必须在白名单中）

    Returns:
        删除的缓存条目数量

    Raises:
        HTTPException: 400 如果命名空间无效或不在白名单中
    """
    # SECURITY: 验证 namespace 格式（防止通配符和特殊字符注入）
    if not NAMESPACE_PATTERN.match(namespace):
        raise HTTPException(
            status_code=400,
            detail={
                "error": "INVALID_NAMESPACE",
                "message": "Namespace must be 1-32 lowercase alphanumeric characters, underscores, or hyphens",
            }
        )

    # SECURITY: 验证 namespace 在白名单中
    if namespace not in ALLOWED_CACHE_NAMESPACES:
        raise HTTPException(
            status_code=400,
            detail={
                "error": "INVALID_NAMESPACE",
                "message": f"Namespace '{namespace}' is not allowed. Allowed: {sorted(ALLOWED_CACHE_NAMESPACES)}",
            }
        )

    deleted = cache.invalidate(namespace)
    logger.info(f"Cache namespace '{namespace}' invalidated by admin: {deleted} entries deleted")
    return {
        "status": "success",
        "namespace": namespace,
        "deleted": deleted,
        "message": f"Invalidated {deleted} entries in namespace '{namespace}'",
    }


# ============================================================================
# Materialized View Cache Management (Phase 9.12)
# ============================================================================


@router.post(
    "/mv-cache/reset",
    summary="重置物化视图可用性缓存",
    description="""
    重置 MV 可用性检测的进程级缓存。

    在以下场景后调用：
    - 创建新的物化视图
    - 刷新物化视图
    - 物化视图结构变更

    这会强制下次查询重新检测 MV 可用性，而不是等待 TTL（5分钟）过期。
    """,
)
@rate_limit("10/minute")
async def reset_mv_cache(request: Request) -> dict:
    """
    重置物化视图可用性缓存

    Returns:
        重置状态信息
    """
    from app.routers.lncrna_chipseq_overlap import reset_mv_cache as reset_overlap_mv_cache
    from app.routers.igv_overlap_track import reset_mv_cache as reset_igv_mv_cache

    reset_overlap_mv_cache()
    reset_igv_mv_cache()

    logger.info("Materialized view caches reset by admin")
    return {
        "status": "success",
        "message": "Materialized view availability caches reset. Next query will re-check MV status.",
        "affected_caches": ["lncrna_chipseq_overlap", "igv_overlap_track"],
    }


# ============================================================================
# Materialized View Refresh / Status (Phase 10.0)
# ============================================================================


class MaterializedViewRefreshRequest(BaseModel):
    """刷新物化视图请求（仅允许白名单内的 MV）。"""

    views: Optional[list[str]] = Field(
        default=None,
        description="要刷新的物化视图列表；null 表示刷新默认列表（按依赖顺序）。",
    )
    concurrently: bool = Field(default=True, description="是否使用 REFRESH MATERIALIZED VIEW CONCURRENTLY（默认 true）")
    analyze: bool = Field(default=True, description="刷新后是否对 MV 执行 ANALYZE（默认 true）")
    timeout_seconds: Optional[int] = Field(
        default=None,
        ge=0,
        description="刷新允许的 statement_timeout（秒）；null 表示使用 MV_REFRESH_TIMEOUT 配置。",
    )


@router.get(
    "/materialized-views/status",
    summary="查询物化视图状态",
    description="返回后端使用的物化视图状态（exists/populated/size/rows_estimate）以及刷新锁是否可用。",
)
@rate_limit("10/minute")
def get_materialized_views_status(request: Request) -> dict:
    from app.core import materialized_views as mv_ops

    autocommit_engine = engine.execution_options(isolation_level="AUTOCOMMIT")
    with autocommit_engine.connect() as conn:
        if conn.dialect.name != "postgresql":
            raise HTTPException(
                status_code=400,
                detail={
                    "error": "UNSUPPORTED_DATABASE",
                    "message": "Materialized view operations require PostgreSQL",
                },
            )

        lock_available = mv_ops.get_refresh_lock_available(conn)
        views = [mv_ops.get_mv_status(conn, name) for name in mv_ops.DEFAULT_MATERIALIZED_VIEWS]

    return {
        "status": "success",
        "refresh_lock_available": bool(lock_available),
        "views": views,
    }


@router.post(
    "/materialized-views/refresh",
    summary="刷新物化视图（Admin）",
    description="""
    触发物化视图刷新（同步执行）。

    安全特性：
    - 复用 Admin 全局鉴权（IP / API Key / 严格模式）
    - 使用 PostgreSQL advisory lock 做跨进程互斥，避免多 worker 并发刷新
    - 临时提升 statement_timeout（MV_REFRESH_TIMEOUT 或请求指定），并在结束后恢复默认 QUERY_TIMEOUT

    定时化建议：生产环境更推荐使用 `scripts/refresh_materialized_views.sh` + cron/systemd 定时运行。
    """,
)
@rate_limit("1/minute")
def refresh_materialized_views_admin(request: Request, body: MaterializedViewRefreshRequest) -> dict:
    from app.core import materialized_views as mv_ops

    autocommit_engine = engine.execution_options(isolation_level="AUTOCOMMIT")
    with autocommit_engine.connect() as conn:
        try:
            result = mv_ops.refresh_materialized_views(
                conn,
                views=body.views,
                concurrently=body.concurrently,
                analyze=body.analyze,
                timeout_seconds=body.timeout_seconds,
            )
        except mv_ops.MaterializedViewRefreshInProgress as e:
            raise HTTPException(
                status_code=409,
                detail={
                    "error": "REFRESH_IN_PROGRESS",
                    "message": str(e),
                },
            )
        except ValueError as e:
            raise HTTPException(
                status_code=400,
                detail={
                    "error": "INVALID_REQUEST",
                    "message": str(e),
                },
            )
        except Exception as e:
            logger.error("Materialized view refresh failed: %s", sanitize_for_log(e, max_length=2000), exc_info=True)
            raise HTTPException(
                status_code=500,
                detail={
                    "error": "REFRESH_FAILED",
                    "message": "Materialized view refresh failed",
                },
            )

    # 刷新完成后，重置进程级 MV 可用性缓存，避免继续走 fallback 逻辑。
    try:
        from app.routers.lncrna_chipseq_overlap import reset_mv_cache as reset_overlap_mv_cache
        from app.routers.igv_overlap_track import reset_mv_cache as reset_igv_mv_cache

        reset_overlap_mv_cache()
        reset_igv_mv_cache()
        result["mv_availability_cache_reset"] = True
    except Exception as e:  # pragma: no cover
        # 不影响刷新结果，但记录告警便于排查。
        logger.warning(
            "Materialized view refreshed but failed to reset MV availability caches: %s",
            sanitize_for_log(e, max_length=2000),
            exc_info=True,
        )
        result["mv_availability_cache_reset"] = False

    logger.info("Materialized views refreshed by admin: status=%s", result.get("status"))
    return result
