"""
Human LncRNA Atlas - FastAPI Backend
跨物种lncRNA调控网络数据库 API
"""
from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from fastapi.responses import JSONResponse
from contextlib import asynccontextmanager
import os
import time
import mimetypes

# 注册基因组文件的 MIME 类型，避免被当作 text/plain 处理
mimetypes.add_type("application/octet-stream", ".2bit")
mimetypes.add_type("application/octet-stream", ".bb")
mimetypes.add_type("application/octet-stream", ".bigbed")
mimetypes.add_type("application/octet-stream", ".bw")
mimetypes.add_type("application/octet-stream", ".bigwig")

from app.core.config import settings  # noqa: E402
from app.core.database import init_db, close_db  # noqa: E402
from app.core.logging_config import setup_logging  # noqa: E402
from app.core.exceptions import sanitize_internal_error  # noqa: E402
from app.middleware.logging import LoggingMiddleware  # noqa: E402
from app.routers import genes, regulations, diseases, stats, network, admin, igv, features, chipseq, lncrna_chipseq_overlap, conservation, export, analysis, visualization  # noqa: E402
from app.schemas.common import HealthResponse  # noqa: E402

# ============================================================================
# slowapi Rate Limiting Setup (for per-endpoint rate limiting)
# ============================================================================
try:
    from slowapi import _rate_limit_exceeded_handler
    from slowapi.errors import RateLimitExceeded
    from slowapi.middleware import SlowAPIMiddleware
    from app.routers.chipseq_rate_limit import chipseq_limiter
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

# 初始化日志
logger = setup_logging(settings.LOG_LEVEL)


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
    allow_insecure = os.environ.get("SECURITY_ALLOW_INSECURE", "").lower() == "true"

    fatal_errors = []
    warnings = []

    # 1. Admin API Key 配置检查
    if settings.ADMIN_REQUIRE_API_KEY:
        if not settings.ADMIN_API_KEY:
            fatal_errors.append(
                "ADMIN_REQUIRE_API_KEY=true but ADMIN_API_KEY is not set. "
                "Generate a key: openssl rand -hex 32"
            )
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

    # 3. 连接池配置检查（仅警告）
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
    # 注意：详细请求指标请使用 Prometheus /metrics 端点
    app.state.metrics_data = {}

    # 初始化数据库连接
    if init_db():
        logger.info("✅ 应用启动成功")
    else:
        logger.error("❌ 数据库连接失败，但应用仍会启动")

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
    docs_url="/docs",
    redoc_url="/redoc",
    lifespan=lifespan,
)

# 配置中间件
# 注意：RateLimitMiddleware 已移除，统一使用 slowapi 进行端点级别限流
# MetricsMiddleware 已移除，统一使用 Prometheus Metrics (prometheus-fastapi-instrumentator)
app.add_middleware(LoggingMiddleware)
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.CORS_ORIGINS,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# ============================================================================
# Security Headers Middleware
# ============================================================================
@app.middleware("http")
async def add_security_headers(request: Request, call_next):
    """
    添加安全响应头，防御常见 Web 攻击

    Headers:
    - X-Content-Type-Options: 防止 MIME 类型嗅探
    - X-Frame-Options: 防止点击劫持（Clickjacking）
    - X-XSS-Protection: 启用浏览器 XSS 过滤（旧版浏览器）
    - Referrer-Policy: 控制 Referer 头发送策略
    - Permissions-Policy: 限制浏览器功能（如地理位置、摄像头）
    - Strict-Transport-Security: 强制 HTTPS（需配置 ENABLE_HSTS=true）
    - Content-Security-Policy: 限制资源加载来源（API 严格模式）
    """
    response = await call_next(request)

    # 防止 MIME 类型嗅探
    response.headers["X-Content-Type-Options"] = "nosniff"

    # 防止点击劫持（API 不需要在 iframe 中嵌入）
    response.headers["X-Frame-Options"] = "DENY"

    # XSS 保护（主要针对旧版浏览器）
    response.headers["X-XSS-Protection"] = "1; mode=block"

    # 控制 Referer 发送策略
    response.headers["Referrer-Policy"] = "strict-origin-when-cross-origin"

    # 限制浏览器功能（API 不需要这些功能）
    response.headers["Permissions-Policy"] = "geolocation=(), microphone=(), camera=()"

    # HSTS - 仅在配置启用时添加（需要 HTTPS 已完全配置）
    if settings.ENABLE_HSTS:
        hsts_value = f"max-age={settings.HSTS_MAX_AGE}"
        if settings.HSTS_INCLUDE_SUBDOMAINS:
            hsts_value += "; includeSubDomains"
        if settings.HSTS_PRELOAD:
            hsts_value += "; preload"
        response.headers["Strict-Transport-Security"] = hsts_value

    # CSP - API 严格策略（禁止内联脚本、eval、外部资源）
    # API 返回 JSON 数据，不需要加载任何外部资源
    response.headers["Content-Security-Policy"] = (
        "default-src 'none'; "
        "frame-ancestors 'none'; "
        "base-uri 'none'; "
        "form-action 'none'"
    )

    return response

# ============================================================================
# slowapi Rate Limiting Integration (per-endpoint limits for ChIP-seq API)
# ============================================================================
if SLOWAPI_AVAILABLE and chipseq_limiter:
    app.state.limiter = chipseq_limiter
    app.add_exception_handler(RateLimitExceeded, _rate_limit_exceeded_handler)
    app.add_middleware(SlowAPIMiddleware)
    logger.info("slowapi rate limiting enabled for ChIP-seq endpoints")

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
    instrumentator.expose(app, endpoint="/metrics", include_in_schema=True, tags=["monitoring"])

    logger.info("Prometheus metrics enabled at /metrics endpoint")
else:
    logger.warning("prometheus-fastapi-instrumentator not available, /metrics endpoint disabled")


# 全局异常处理
@app.exception_handler(Exception)
async def global_exception_handler(request: Request, exc: Exception):
    """
    全局异常处理器 - 使用 sanitize_internal_error 进行错误脱敏

    安全改进：
    - 不再在 DEBUG 模式下暴露完整错误信息
    - 使用 error_id 关联服务器日志和客户端报告
    - 返回通用错误消息，防止信息泄露
    """
    # 使用 sanitize_internal_error 生成脱敏的 HTTPException
    sanitized_exc = sanitize_internal_error(
        e=exc,
        logger=logger,
        error_type="INTERNAL_ERROR",
        message="An internal server error occurred. Please try again later."
    )

    return JSONResponse(
        status_code=sanitized_exc.status_code,
        content={"detail": sanitized_exc.detail},
    )


# 根路径
@app.get("/", tags=["root"])
def read_root():
    """API根路径"""
    return {
        "name": settings.APP_NAME,
        "version": settings.APP_VERSION,
        "status": "running",
        "docs": "/docs",
        "redoc": "/redoc",
        "health": "/health",
        "api_prefix": settings.API_V1_PREFIX,
    }


# 健康检查
@app.get("/health", response_model=HealthResponse, tags=["root"])
def health_check():
    """健康检查接口"""
    from app.core.database import engine
    from app.core.cache import cache
    from sqlalchemy import text

    # 检查数据库状态
    try:
        with engine.connect() as conn:
            conn.execute(text("SELECT 1"))
        db_status = "healthy"
    except Exception as e:
        # 安全改进：不暴露底层异常详情，只记录日志
        logger.error(f"Health check database error: {e}")
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

# 挂载静态文件服务（用于 IGV.js 基因组文件）
# 使用独立的 FastAPI 子应用，完全绕过主应用的中间件（解决 BaseHTTPMiddleware 兼容性问题）
# GENOMES_DIR 通过 Settings 加载，支持 .env 文件配置
GENOMES_DIR = settings.GENOMES_DIR

if GENOMES_DIR and os.path.exists(GENOMES_DIR):
    # 创建独立的 FastAPI 子应用用于静态文件服务
    # 使用 Starlette CORSMiddleware 包装，代替自定义 CORSStaticFiles 实现
    from fastapi import FastAPI as SubFastAPI
    from starlette.types import ASGIApp as StarletteASGIApp

    # 创建静态文件子应用
    genomes_app = SubFastAPI()

    # 安全头中间件（静态文件版）- 添加基本安全保护
    class StaticSecurityHeadersMiddleware:
        """为静态文件服务添加安全响应头"""

        def __init__(self, app: StarletteASGIApp):
            self.app = app

        async def __call__(self, scope, receive, send):
            if scope["type"] != "http":
                await self.app(scope, receive, send)
                return

            async def send_wrapper(message):
                if message["type"] == "http.response.start":
                    headers = list(message.get("headers", []))
                    # 添加基本安全头
                    headers.extend([
                        (b"x-content-type-options", b"nosniff"),
                        (b"x-frame-options", b"DENY"),
                        (b"referrer-policy", b"strict-origin-when-cross-origin"),
                        # 静态文件的 CSP：仅允许自身
                        (b"content-security-policy", b"default-src 'none'; frame-ancestors 'none'"),
                        # 缓存控制：基因组文件不常变化，允许缓存
                        (b"cache-control", b"public, max-age=86400"),
                    ])
                    message = {**message, "headers": headers}
                await send(message)

            await self.app(scope, receive, send_wrapper)

    # 添加安全头中间件（先添加的后执行，所以安全头在 CORS 之后添加）
    genomes_app.add_middleware(StaticSecurityHeadersMiddleware)

    # 为子应用添加 CORS 中间件（使用标准 Starlette 实现）
    genomes_app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.CORS_ORIGINS,
        allow_credentials=True,
        allow_methods=["GET", "HEAD", "OPTIONS"],
        allow_headers=["Range", "Content-Type"],
        expose_headers=["Content-Length", "Content-Range", "Accept-Ranges"],
    )

    # 挂载静态文件到子应用根路径
    genomes_app.mount("/", StaticFiles(directory=GENOMES_DIR), name="genomes_static")

    # 将子应用挂载到主应用
    app.mount("/genomes", genomes_app)

    logger.info(f"Genome file service enabled: /genomes -> {GENOMES_DIR}")
else:
    logger.warning("GENOMES_DIR not set or does not exist, genome file service disabled")


if __name__ == "__main__":
    import uvicorn

    uvicorn.run(
        "main:app",
        host="0.0.0.0",
        port=8000,
        reload=True,
        log_level="info",
    )
