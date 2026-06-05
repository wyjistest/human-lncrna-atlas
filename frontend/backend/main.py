# -*- coding: utf-8 -*-
"""
Human LncRNA Atlas - FastAPI Backend
跨物种lncRNA调控网络数据库 API

Phase 9.16: 模块化重构
- 安全中间件提取到 app/middleware/security/
- 基因组文件服务提取到 app/mounts/genomes.py
"""
from fastapi import FastAPI, Request, HTTPException
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from starlette.exceptions import HTTPException as StarletteHTTPException
from starlette.middleware.trustedhost import TrustedHostMiddleware
from contextlib import asynccontextmanager
from sqlalchemy.exc import SQLAlchemyError
import os
import time
import mimetypes

from app.core.config import settings
from app.core.database import init_db, close_db
from app.core.logging_config import setup_logging
from app.core.exceptions import (
    build_validation_error_detail,
    normalize_http_error_detail,
    sanitize_db_error,
    sanitize_internal_error,
)
from app.core.utils import sanitize_for_log
from app.middleware import (
    AdminMetricsMiddleware,
    LoggingMiddleware,
    RequestLimitsMiddleware,
    add_security_headers,
    is_prometheus_metrics_enabled,
    metrics_auth_middleware,
)
from app.mounts import mount_genomes_app
from app.routers import genes, regulations, diseases, stats, network, admin, igv, features, chipseq, lncrna_chipseq_overlap, conservation, export, analysis, visualization
from app.routers.chipseq_rate_limit import rate_limit
from app.schemas.common import HealthResponse

# ============================================================================
# slowapi Rate Limiting Setup (for per-endpoint rate limiting)
# ============================================================================
try:
    from slowapi.errors import RateLimitExceeded
    from slowapi.middleware import SlowAPIMiddleware
    from app.routers.chipseq_rate_limit import chipseq_limiter, rate_limit_exceeded_handler
    SLOWAPI_AVAILABLE = True
except ImportError:
    SLOWAPI_AVAILABLE = False
    chipseq_limiter = None

# ============================================================================
# Prometheus Metrics Setup (prometheus-fastapi-instrumentator)
# ============================================================================
try:
    from prometheus_fastapi_instrumentator import Instrumentator
    PROMETHEUS_AVAILABLE = True
except ImportError:
    PROMETHEUS_AVAILABLE = False
    Instrumentator = None

# 注册基因组文件的 MIME 类型，避免被当作 text/plain 处理
mimetypes.add_type("application/octet-stream", ".2bit")
mimetypes.add_type("application/octet-stream", ".bb")
mimetypes.add_type("application/octet-stream", ".bigbed")
mimetypes.add_type("application/octet-stream", ".bw")
mimetypes.add_type("application/octet-stream", ".bigwig")

# 初始化日志
logger = setup_logging(settings.LOG_LEVEL)

def _get_weak_admin_api_key_reason(admin_key: str) -> str | None:
    """
    检测 Admin API Key 是否过弱/疑似占位符（防止误把示例值用于生产环境）。

    说明：
    - 这里只做“明显危险”的最小集合判断，避免误伤真实 key。
    - 不返回/不记录 key 本身，防止日志泄露。
    """
    key = str(admin_key or "").strip()
    if not key:
        return None

    # 典型占位符（CHANGE_ME / change-me / change_me / "default" 等）
    import re

    canonical = re.sub(r"[-_\s]+", "", key.lower())
    if canonical in {"changeme", "default", "password", "admin", "secret"}:
        return (
            "ADMIN_API_KEY appears to be a placeholder/weak value (e.g., CHANGE_ME/default/password). "
            "Generate a strong random key: openssl rand -hex 32"
        )

    # 最低强度要求：避免过短 key（生产环境至少 16 字符）
    if len(key) < 16:
        return (
            "ADMIN_API_KEY is too short (<16 chars). "
            "Generate a strong random key: openssl rand -hex 32"
        )

    return None


def _validate_security_config() -> None:
    """
    启动时安全配置验证 (Fail-Fast)

    检查项：
    1. ADMIN_REQUIRE_API_KEY=true 但 ADMIN_API_KEY 未设置 → FATAL
    2. ADMIN_REQUIRE_API_KEY=false → FATAL (生产风险)
    3. slowapi 不可用 → FATAL (限流禁用)
    4. 连接池配置过小 → WARNING

    开发模式绕过：
    设置 SECURITY_ALLOW_INSECURE=true 可跳过 fail-fast（仅限开发环境）

    Raises:
        RuntimeError: 当存在致命安全配置错误且未启用开发模式时
    """
    # 检查是否允许不安全配置（仅限开发环境）
    # Phase 9.19: 生产环境硬拒绝 SECURITY_ALLOW_INSECURE
    allow_insecure_env = os.environ.get("SECURITY_ALLOW_INSECURE", "").lower() == "true"
    if settings.is_production and allow_insecure_env:
        logger.error(
            "❌ FATAL: SECURITY_ALLOW_INSECURE=true is FORBIDDEN in production (ENV=production). "
            "Remove this environment variable or set ENV=development."
        )
        raise RuntimeError(
            "SECURITY_ALLOW_INSECURE=true is not allowed in production environment. "
            "Remove SECURITY_ALLOW_INSECURE or set ENV=development."
        )
    allow_insecure = allow_insecure_env and not settings.is_production

    fatal_errors = []
    warnings = []

    # 1. Admin API Key 配置检查
    if settings.ADMIN_REQUIRE_API_KEY:
        # SECURITY: 使用 get_secret_value() 检查 API Key 是否真正配置
        admin_key = settings.ADMIN_API_KEY.get_secret_value() if settings.ADMIN_API_KEY else None
        if not admin_key:
            fatal_errors.append(
                "ADMIN_REQUIRE_API_KEY=true but ADMIN_API_KEY is not set. "
                "Generate a key: openssl rand -hex 32"
            )
        else:
            weak_reason = _get_weak_admin_api_key_reason(admin_key)
            if weak_reason:
                # 生产环境：视为致命错误（避免把示例值/弱口令带到线上）
                # 非生产环境：仅告警，不改变行为，保持向后兼容
                if settings.is_production:
                    fatal_errors.append(weak_reason)
                else:
                    warnings.append(weak_reason)
    else:
        # 非严格模式视为致命错误（生产环境必须启用 API Key）
        fatal_errors.append(
            "ADMIN_REQUIRE_API_KEY=false - Admin API allows unauthenticated access from private IPs. "
            "Set ADMIN_REQUIRE_API_KEY=true and ADMIN_API_KEY for production."
        )

    # 2. slowapi 可用性检查（硬依赖）
    if not SLOWAPI_AVAILABLE:
        fatal_errors.append(
            "slowapi is not available - rate limiting is DISABLED for all endpoints. "
            "Install slowapi: pip install slowapi"
        )

    if settings.is_production:
        # 2.1 生产环境禁止私网 bypass（否则可能被代理误配 + XFF 伪造绕过）
        if getattr(settings, "RATE_LIMIT_BYPASS_PRIVATE", False):
            fatal_errors.append(
                "RATE_LIMIT_BYPASS_PRIVATE=true is not allowed in production. "
                "Keep it false to prevent rate-limit bypass via internal IP spoofing."
            )

        storage_url = settings.ratelimit_storage_url or ""
        if not storage_url:
            fatal_errors.append(
                "RATELIMIT_STORAGE_URL is not set in production. "
                "SlowAPI defaults to memory:// which is NOT shared across workers. "
                "Configure Redis, e.g. RATELIMIT_STORAGE_URL=redis://:password@redis:6379/1"
            )
        else:
            normalized = storage_url.strip().lower()
            if normalized.startswith("memory://"):
                fatal_errors.append(
                    "RATELIMIT_STORAGE_URL=memory:// is not allowed in production. "
                    "Use Redis for distributed rate limiting."
                )
            elif not normalized.startswith(("redis://", "rediss://", "redis+unix://", "redis+cluster://")):
                fatal_errors.append(
                    f"RATELIMIT_STORAGE_URL uses unsupported scheme in production: {storage_url!r}. "
                    "Use Redis storage, e.g. redis://:password@redis:6379/1"
                )

    # 3. TRUSTED_HOSTS 生产环境检查（Phase 9.19）
    # 生产环境不应仅使用 localhost 默认值，否则所有外部请求返回 400
    # Phase 9.19 补强：空列表也 fail-fast（会绕过 TrustedHostMiddleware）
    if settings.is_production:
        if not settings.TRUSTED_HOSTS:
            # 空列表会完全禁用 TrustedHostMiddleware，失去 Host Header 防护
            fatal_errors.append(
                "TRUSTED_HOSTS is empty in production. "
                "This disables TrustedHostMiddleware and Host Header attack protection. "
                "Configure TRUSTED_HOSTS with your actual domain(s), e.g., ['example.com', '*.example.com']"
            )
        else:
            localhost_only_hosts = {"localhost", "127.0.0.1", "::1", "*.localhost"}
            configured_hosts = set(settings.TRUSTED_HOSTS)
            if configured_hosts.issubset(localhost_only_hosts):
                fatal_errors.append(
                    f"TRUSTED_HOSTS only contains localhost values {list(configured_hosts)} in production. "
                    "This will reject ALL external requests with HTTP 400. "
                    "Add your actual domain(s) to TRUSTED_HOSTS, e.g., ['example.com', '*.example.com']"
                )

        # 3.1 TRUSTED_PROXIES 生产环境检查（防止 X-Forwarded-For 伪造导致鉴权/限流绕过）
        # 默认配置是 localhost-only，安全但可能导致所有客户端共享同一个限流 key（若实际运行在反代后）。
        try:
            import ipaddress

            for entry in settings.TRUSTED_PROXIES or []:
                proxy = str(entry).strip()
                if not proxy:
                    continue
                # 极高风险：信任全网，任何客户端都可伪造 XFF
                if proxy in {"0.0.0.0/0", "::/0"}:
                    fatal_errors.append(
                        f"TRUSTED_PROXIES contains an unsafe catch-all network {proxy!r} in production. "
                        "This allows anyone to spoof X-Forwarded-For and bypass IP-based protections."
                    )
                    continue

                if "/" in proxy:
                    net = ipaddress.ip_network(proxy, strict=False)
                    # 过宽的网段通常意味着“信任整段内网”，风险较高，给出警告即可（由部署方决定）。
                    if (net.version == 4 and net.prefixlen < 24) or (net.version == 6 and net.prefixlen < 64):
                        warnings.append(
                            f"TRUSTED_PROXIES contains a broad network {proxy!r} in production. "
                            "Prefer trusting only the exact reverse-proxy IP(s) to reduce XFF spoofing risk."
                        )
                else:
                    # Validate single IP format
                    ipaddress.ip_address(proxy)
        except Exception as e:  # pragma: no cover
            warnings.append(f"Failed to validate TRUSTED_PROXIES entries: {e}")

        # 3.2 API Docs exposure notice
        if getattr(settings, "ENABLE_API_DOCS", True):
            warnings.append(
                "ENABLE_API_DOCS=true in production. Consider disabling /docs, /redoc and /openapi.json "
                "to reduce attack surface."
            )

        # 3.3 DoS guardrails sanity checks (request size / query string length)
        # These are app-level backstops; production should ideally also enforce limits at the reverse proxy layer.
        max_body = int(getattr(settings, "MAX_REQUEST_BODY_SIZE", 0) or 0)
        if max_body <= 0:
            warnings.append(
                "MAX_REQUEST_BODY_SIZE is 0 (unlimited). This disables request body size protection and may allow DoS."
            )
        elif max_body > 20 * 1024 * 1024:
            warnings.append(
                f"MAX_REQUEST_BODY_SIZE is very large ({max_body} bytes). Consider lowering it to reduce DoS risk."
            )

        max_qs = int(getattr(settings, "MAX_QUERY_STRING_LENGTH", 0) or 0)
        if max_qs <= 0:
            warnings.append(
                "MAX_QUERY_STRING_LENGTH is 0 (unlimited). This disables query string length protection and may allow DoS."
            )
        elif max_qs > 64 * 1024:
            warnings.append(
                f"MAX_QUERY_STRING_LENGTH is very large ({max_qs} bytes). Consider lowering it to reduce DoS risk."
            )

        # 3.4 Request logging sanity checks (operational cost)
        # Default config logs all requests; this can be very expensive on high QPS production systems.
        # We only warn here (no behavior changes) to preserve backward compatibility.
        try:
            if settings.REQUEST_LOG_ENABLED:
                if settings.REQUEST_LOG_SLOW_THRESHOLD_MS <= 0 and settings.REQUEST_LOG_SAMPLE_RATE >= 1.0:
                    warnings.append(
                        "Request logging is configured to log ALL requests "
                        "(REQUEST_LOG_SLOW_THRESHOLD_MS=0 and REQUEST_LOG_SAMPLE_RATE=1.0). "
                        "This may cause high I/O in production. Consider setting "
                        "REQUEST_LOG_SLOW_THRESHOLD_MS (e.g., 200) and/or REQUEST_LOG_SAMPLE_RATE (e.g., 0.1)."
                    )
                if settings.REQUEST_LOG_MAX_URL_LENGTH <= 0:
                    warnings.append(
                        "REQUEST_LOG_MAX_URL_LENGTH is 0 (unlimited). This may cause log bloat in production. "
                        "Consider setting REQUEST_LOG_MAX_URL_LENGTH=2048."
                    )
        except Exception as e:  # pragma: no cover
            warnings.append(f"Failed to validate request logging settings: {e}")

    # 4. 连接池配置检查（仅警告）
    pool_total = settings.DB_POOL_SIZE + settings.DB_POOL_MAX_OVERFLOW
    if pool_total < 20:
        warnings.append(
            f"Database pool size ({settings.DB_POOL_SIZE}+{settings.DB_POOL_MAX_OVERFLOW}={pool_total}) "
            f"may be insufficient for high concurrency. Consider increasing to 20+."
        )

    # 输出警告
    for warning in warnings:
        logger.warning(f"⚠️  Security Warning: {warning}")

    # 输出致命错误
    for error in fatal_errors:
        logger.error(f"❌ FATAL Security Error: {error}")

    # 汇总日志
    if fatal_errors or warnings:
        logger.info(
            f"🔒 Security validation: {len(fatal_errors)} fatal errors, {len(warnings)} warnings"
        )
    else:
        logger.info("🔒 Security validation: All checks passed")

    # Fail-Fast: 存在致命错误时拒绝启动
    if fatal_errors:
        if allow_insecure:
            # 极醒目警告：生产环境误配置此变量将导致严重安全漏洞
            insecure_warning = """
╔══════════════════════════════════════════════════════════════════════════════╗
║  🚨🚨🚨 SECURITY_ALLOW_INSECURE=true 已启用 🚨🚨🚨
║
║  ⚠️  所有安全检查已被绕过！当前风险：
║      - Admin API 可能无需认证即可访问
║      - 限流功能可能被完全禁用
║      - 系统对 DoS 攻击和未授权访问毫无防护
║
║  🔴 如果这是生产环境，请立即停止服务并移除此环境变量！
║
║  ✅ 仅在本地开发/测试环境使用此配置。
╚══════════════════════════════════════════════════════════════════════════════╝
"""
            logger.warning(insecure_warning)
            # 额外记录到 ERROR 级别确保被监控系统捕获
            logger.error(
                "INSECURE_MODE_ACTIVE: Security checks bypassed via SECURITY_ALLOW_INSECURE=true"
            )
        else:
            error_summary = "; ".join(fatal_errors)
            raise RuntimeError(
                f"Security validation failed - refusing to start. "
                f"Errors: {error_summary}. "
                f"Set SECURITY_ALLOW_INSECURE=true to bypass (development only)."
            )


@asynccontextmanager
async def lifespan(app: FastAPI):
    """应用生命周期管理"""
    # 启动时执行
    logger.info("=" * 60)
    logger.info(f"🚀 {settings.APP_NAME} v{settings.APP_VERSION}")
    logger.info("=" * 60)

    # 安全配置验证
    _validate_security_config()

    # 初始化应用启动时间（用于 admin metrics uptime 计算）
    app.state.start_time = time.time()

    # 初始化空的 metrics_data（兼容 admin metrics 端点）
    # 注意：
    # - Prometheus /metrics 提供更完整的观测出口
    # - Admin /api/v1/admin/metrics 需要轻量 in-memory 指标支持（用于前端 Monitoring 页）
    from app.middleware.admin_metrics import create_metrics_data

    app.state.metrics_data = create_metrics_data()

    # 初始化数据库连接（Phase 9.18 - Codex审查修复：生产环境fail-fast）
    db_connected = init_db()
    if db_connected:
        logger.info("✅ 数据库连接成功")
    else:
        if settings.is_production:
            # 生产环境：数据库连接失败时拒绝启动
            raise RuntimeError(
                "Database connection failed in production environment. "
                "Set ENV=development to allow startup without database."
            )
        else:
            # 开发环境：警告但继续启动
            logger.warning("⚠️ 数据库连接失败，开发模式下应用仍会启动")

    logger.info(f"✅ 应用启动成功 (ENV={settings.ENV})")

    yield

    # 关闭时执行
    close_db()
    logger.info("👋 应用已关闭")


# 创建FastAPI应用实例
app = FastAPI(
    title=settings.APP_NAME,
    version=settings.APP_VERSION,
    description="""
    ## 跨物种lncRNA调控网络数据库API

    提供以下功能：
    - 🧬 **基因查询** - 查询基因信息、直系同源基因
    - 🔗 **调控关系** - 查询lncRNA-target调控网络
    - 🏥 **疾病关联** - 查询基因-疾病关联
    - 📊 **统计分析** - 全局统计、Top基因/疾病
    - 🌐 **网络可视化** - 生成可视化网络数据
    - 🔬 **跨物种对比** - 保守调控关系分析

    ### 数据库统计
    - 5,484 个核心基因
    - 17,248 个物种特异性基因
    - 804,630 条调控关系
    - 67,763 个疾病关联
    - 涵盖4个物种（人、黑猩猩、猕猴、狨猴）
    """,
    # SECURITY: 可通过 ENABLE_API_DOCS=false 在生产环境禁用 API 文档与 OpenAPI schema 暴露
    docs_url="/docs" if settings.ENABLE_API_DOCS else None,
    redoc_url="/redoc" if settings.ENABLE_API_DOCS else None,
    openapi_url="/openapi.json" if settings.ENABLE_API_DOCS else None,
    lifespan=lifespan,
)

# 配置中间件
# 注意：RateLimitMiddleware 已移除，统一使用 slowapi 进行端点级别限流
# Prometheus Metrics 统一由 prometheus-fastapi-instrumentator 提供（/metrics）
# Admin Monitoring 页（/api/v1/admin/metrics）使用轻量 in-memory 指标（AdminMetricsMiddleware）
# FastAPI 中间件执行顺序：后添加的中间件在外层（最先执行）。
app.add_middleware(LoggingMiddleware)


# ============================================================================
# TrustedHost Middleware (Phase 9.18 - Codex审查修复)
# 防止 HTTP Host Header 攻击，仅允许配置的 Host 访问
# ============================================================================
if settings.TRUSTED_HOSTS:
    app.add_middleware(
        TrustedHostMiddleware,
        allowed_hosts=settings.TRUSTED_HOSTS,
    )
    logger.info(f"TrustedHostMiddleware enabled with hosts: {settings.TRUSTED_HOSTS}")

# ============================================================================
# slowapi Rate Limiting Integration (per-endpoint limits for ChIP-seq API)
# ============================================================================
if SLOWAPI_AVAILABLE and chipseq_limiter:
    app.state.limiter = chipseq_limiter
    app.add_exception_handler(RateLimitExceeded, rate_limit_exceeded_handler)
    app.add_middleware(SlowAPIMiddleware)
    logger.info("slowapi rate limiting enabled for ChIP-seq endpoints")

# ============================================================================
# Security Middleware Registration
# Phase 9.16: 安全中间件已提取到 app/middleware/security/
# IMPORTANT: 注册在 slowapi 之后，确保 429/异常响应也能附带安全头
# ============================================================================
# ============================================================================
# Request Limits Middleware (DoS hardening)
# IMPORTANT: 放在安全头/CORS 之内，确保 413/414 也能带上安全头与 CORS 头
# ============================================================================
app.add_middleware(RequestLimitsMiddleware)

app.middleware("http")(metrics_auth_middleware)
app.middleware("http")(add_security_headers)

# ============================================================================
# CORS Middleware
# IMPORTANT: 放在最外层，确保所有响应（含 429/5xx）都带 CORS 头，避免前端误判为 CORS Error
# ============================================================================
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.CORS_ORIGINS,
    allow_credentials=True,
    # Phase 9.16: 收敛 CORS 配置，仅允许实际需要的方法和头
    # 参考: Codex 代码审查 - 避免 allow_methods/headers=["*"]
    allow_methods=["GET", "POST", "PUT", "DELETE", "OPTIONS"],
    allow_headers=[
        "Content-Type",
        "Authorization",
        "X-Admin-API-Key",
        "X-Requested-With",
        "Accept",
        "Origin",
    ],
)

# ============================================================================
# Prometheus Metrics Integration (prometheus-fastapi-instrumentator)
# ============================================================================
if PROMETHEUS_AVAILABLE and Instrumentator:
    # 创建 Instrumentator 实例
    instrumentator = Instrumentator(
        should_group_status_codes=True,           # 将状态码分组（2xx, 3xx, 4xx, 5xx）
        should_ignore_untemplated=True,           # 忽略无模板路由
        should_respect_env_var=True,              # 支持环境变量控制
        should_instrument_requests_inprogress=True,  # 追踪进行中的请求
        excluded_handlers=["/health", "/docs", "/redoc", "/openapi.json", "/metrics"],  # 排除的路径
        env_var_name="ENABLE_METRICS",            # 控制开关的环境变量
        inprogress_name="http_requests_inprogress",
        inprogress_labels=True,
    )

    # 对应用进行埋点
    instrumentator.instrument(app)

    # 暴露 /metrics 端点
    # SECURITY: 设置 include_in_schema=False 避免在 OpenAPI 文档中暴露
    # 生产环境应通过网关 ACL 或内网访问控制进一步保护此端点
    instrumentator.expose(app, endpoint="/metrics", include_in_schema=False)

    if is_prometheus_metrics_enabled():
        logger.info("Prometheus metrics enabled at /metrics endpoint")
    else:
        logger.info("Prometheus metrics disabled; set ENABLE_METRICS=true to expose /metrics")
else:
    logger.warning("prometheus-fastapi-instrumentator not available, /metrics endpoint disabled")

# ============================================================================
# Admin In-memory Metrics (for /api/v1/admin/metrics)
# ============================================================================
# 放在最外层：统计口径包含 CORS/安全中间件等完整链路耗时（但默认跳过 /metrics 与 /api/v1/admin 自身）
app.add_middleware(AdminMetricsMiddleware)


# ============================================================================
# Preserve default exception handlers (avoid 404/422 being caught by generic handler)
# Ref: FastAPI docs - handling-errors.md (reuse default handlers)
# ============================================================================
@app.exception_handler(StarletteHTTPException)
async def starlette_http_exception_handler(request: Request, exc: StarletteHTTPException):
    detail = normalize_http_error_detail(exc.detail, status_code=exc.status_code)
    headers = getattr(exc, "headers", None)
    return JSONResponse(status_code=exc.status_code, content={"detail": detail}, headers=headers)


@app.exception_handler(HTTPException)
async def fastapi_http_exception_handler(request: Request, exc: HTTPException):
    detail = normalize_http_error_detail(exc.detail, status_code=exc.status_code)
    headers = getattr(exc, "headers", None)
    return JSONResponse(status_code=exc.status_code, content={"detail": detail}, headers=headers)


@app.exception_handler(RequestValidationError)
async def validation_exception_handler(request: Request, exc: RequestValidationError):
    detail = build_validation_error_detail(exc)
    return JSONResponse(status_code=422, content={"detail": detail})


# ============================================================================
# Global exception handler (sanitized 500s)
# ============================================================================
@app.exception_handler(Exception)
async def global_exception_handler(request: Request, exc: Exception):
    """
    全局异常处理器 - 使用 sanitize_internal_error 进行错误脱敏

    安全改进：
    - 不再在 DEBUG 模式下暴露完整错误信息
    - 使用 error_id 关联服务器日志和客户端报告
    - 返回通用错误消息，防止信息泄露
    """
    # 优先识别数据库异常，返回更明确的错误类型（仍然脱敏）
    if isinstance(exc, SQLAlchemyError):
        sanitized_exc = sanitize_db_error(exc, logger)
    else:
        # 使用 sanitize_internal_error 生成脱敏的 HTTPException
        sanitized_exc = sanitize_internal_error(
            e=exc,
            logger=logger,
            error_type="INTERNAL_ERROR",
            message="An internal server error occurred. Please try again later.",
        )

    return JSONResponse(
        status_code=sanitized_exc.status_code,
        content={"detail": sanitized_exc.detail},
    )

def _compute_db_mode(db_name: str) -> str:
    """
    生成对外可展示的数据库运行模式（用于排障，避免误连 baseline DB）。

    说明：
    - 不暴露 host/user/password 等敏感信息
    - 仅返回模式 + db_name（你已明确允许暴露最小化元信息）
    """
    name = (db_name or "").strip()
    if name == "lncrna_production":
        return "production"
    if "baseline" in name.lower():
        return "baseline"
    return "custom"


# 根路径
@app.get("/", tags=["root"])
def read_root():
    """API根路径"""
    db_name = settings.DATABASE_NAME
    return {
        "name": settings.APP_NAME,
        "version": settings.APP_VERSION,
        "status": "running",
        "docs": "/docs",
        "redoc": "/redoc",
        "health": "/health",
        "api_prefix": settings.API_V1_PREFIX,
        "db_mode": _compute_db_mode(db_name),
        "db_name": db_name,
    }


# 健康检查
@app.get("/health", response_model=HealthResponse, tags=["root"])
@rate_limit("60/minute")
def health_check(request: Request):
    """健康检查接口"""
    from app.core.database import engine
    from app.core.cache import cache
    from sqlalchemy import text

    db_name = settings.DATABASE_NAME

    # 检查数据库状态
    try:
        with engine.connect() as conn:
            conn.execute(text("SELECT 1"))
        db_status = "healthy"
    except Exception as e:
        # 安全改进：不暴露底层异常详情，只记录日志
        logger.error(
            "Health check database error: %s",
            sanitize_for_log(e, max_length=2000),
            exc_info=not settings.is_production,
        )
        db_status = "unhealthy"

    # 检查 Redis/缓存状态（对齐 CacheService 实际状态）
    if not cache.enabled:
        redis_status = "disabled"
    elif cache.backend == "redis":
        redis_status = "healthy"
    else:
        # 使用内存缓存回退
        redis_status = "fallback (memory)"

    # 综合状态判断
    if db_status == "healthy" and redis_status in ("healthy", "disabled"):
        overall_status = "healthy"
    elif db_status == "healthy":
        overall_status = "degraded"  # Redis 使用回退
    else:
        overall_status = "down"  # 数据库不健康，服务不可用

    return HealthResponse(
        status=overall_status,
        database=db_status,
        redis=redis_status,
        version=settings.APP_VERSION,
        db_mode=_compute_db_mode(db_name),
        db_name=db_name,
    )




# 注册路由
app.include_router(genes.router, prefix=settings.API_V1_PREFIX)
app.include_router(regulations.router, prefix=settings.API_V1_PREFIX)
app.include_router(diseases.router, prefix=settings.API_V1_PREFIX)
app.include_router(stats.router, prefix=settings.API_V1_PREFIX)
app.include_router(network.router, prefix=settings.API_V1_PREFIX)
app.include_router(admin.router, prefix=settings.API_V1_PREFIX)
app.include_router(igv.router, prefix=settings.API_V1_PREFIX)
app.include_router(features.router, prefix=settings.API_V1_PREFIX)
app.include_router(chipseq.router, prefix=settings.API_V1_PREFIX)
app.include_router(lncrna_chipseq_overlap.router, prefix=settings.API_V1_PREFIX)
app.include_router(conservation.router, prefix=settings.API_V1_PREFIX)
app.include_router(export.router, prefix=settings.API_V1_PREFIX)  # Phase 6.0-A: 数据导出 API
app.include_router(analysis.router, prefix=settings.API_V1_PREFIX)  # Phase 6.0-C: 分析结果 API
app.include_router(visualization.router, prefix=settings.API_V1_PREFIX)  # Sankey 流向图可视化 API

# ============================================================================
# Genome Static File Service
# Phase 9.16: 已提取到 app/mounts/genomes.py
# ============================================================================
mount_genomes_app(app)


if __name__ == "__main__":
    import uvicorn

    uvicorn.run(
        "main:app",
        host="0.0.0.0",
        port=8000,
        reload=not settings.is_production,
        log_level="info",
    )
