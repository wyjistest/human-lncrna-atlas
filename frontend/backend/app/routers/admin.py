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
from datetime import datetime
from typing import Literal, Optional
from collections import defaultdict, deque

try:
    import psutil  # type: ignore
except ImportError:  # pragma: no cover
    psutil = None  # type: ignore[assignment]
from fastapi import APIRouter, Request, Depends, HTTPException, Header
from sqlalchemy import text

from app.core.database import engine
from app.core.cache import cache
from app.core.config import settings, AlertThresholds
from app.core.ip_utils import get_client_ip, is_private_ip
from app.routers.chipseq_rate_limit import rate_limit
from app.schemas.monitoring import (
    MetricsResponse,
    RequestMetrics,
    ErrorMetrics,
    ResponseTimeMetrics,
    HealthMetrics,
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


_SAFE_METHODS = {"GET", "HEAD", "OPTIONS"}


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
        return

    backend_origin = str(request.base_url).rstrip("/")
    allowed = set(settings.CORS_ORIGINS) | {backend_origin}
    if origin not in allowed:
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
        if x_admin_api_key and secrets.compare_digest(
            x_admin_api_key.encode('utf-8'),
            admin_key.encode('utf-8')
        ):
            logger.debug(f"Admin API access granted via API Key (strict mode) from {client_ip}")
            return
        logger.warning(f"Admin API access denied (strict mode): invalid or missing API Key from {client_ip}")
        raise HTTPException(
            status_code=403,
            detail={
                "error": "ACCESS_DENIED",
                "message": "Valid API Key required (strict mode enabled)",
                "client_ip": client_ip,
            }
        )

    # 普通模式：检查 API Key（如果配置了且提供了）
    # SECURITY: 使用 get_secret_value() 获取真实 API Key
    admin_key = settings.ADMIN_API_KEY.get_secret_value() if settings.ADMIN_API_KEY else None
    if admin_key:
        # SECURITY: 使用 secrets.compare_digest 防止时序攻击
        if x_admin_api_key and secrets.compare_digest(
            x_admin_api_key.encode('utf-8'),
            admin_key.encode('utf-8')
        ):
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
                    "client_ip": client_ip,
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
            "client_ip": client_ip,
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
        logger.error(f"Database health check failed: {e}")
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
        logger.warning(f"Failed to get CPU percent: {e}")
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
        logger.warning(f"Failed to get memory info: {e}")
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
        logger.warning(f"Failed to get disk info: {e}")
        disk_info = SystemDisk(used_gb=0, total_gb=0, percent=0)

    # 当前进程信息
    try:
        process = psutil.Process(os.getpid())
        process_info = ProcessInfo(
            cpu_percent=round(process.cpu_percent(), 2),
            memory_mb=round(process.memory_info().rss / 1024 / 1024, 2),
        )
    except Exception as e:
        logger.warning(f"Failed to get process info: {e}")
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


def calculate_percentiles(response_times: deque) -> Optional[PercentileMetrics]:
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

    **注意**：详细请求指标（QPS、响应时间分布等）请使用 Prometheus `/metrics` 端点。
    此端点主要提供健康检查和系统资源监控。
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

    注意：请求级别的详细指标（QPS、响应时间百分位等）
    已迁移到 Prometheus /metrics 端点。此端点返回的
    request/error 计数为 0（历史兼容）。
    """
    # 获取 metrics_data
    metrics_data = getattr(request.app.state, "metrics_data", {})
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
    response_times = metrics_data.get("response_times", deque())
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
        # Phase 2 - 新增指标
        response_time_distribution=response_time_distribution,
        error_trend=error_trend,
        endpoints=endpoints,
        # Phase 3 - 系统监控指标
        system=system_metrics,
        alerts=alerts,
        percentiles=percentiles,
    )


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
    return cache.get_stats()


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
