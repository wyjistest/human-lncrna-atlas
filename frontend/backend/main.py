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
import mimetypes
import logging

# 注册基因组文件的 MIME 类型，避免被当作 text/plain 处理
mimetypes.add_type("application/octet-stream", ".2bit")
mimetypes.add_type("application/octet-stream", ".bb")
mimetypes.add_type("application/octet-stream", ".bigbed")
mimetypes.add_type("application/octet-stream", ".bw")
mimetypes.add_type("application/octet-stream", ".bigwig")

from app.core.config import settings
from app.core.database import init_db, close_db
from app.core.logging_config import setup_logging
from app.core.exceptions import sanitize_internal_error
from app.middleware.logging import LoggingMiddleware
from app.routers import genes, regulations, diseases, stats, network, admin, igv, features, chipseq, lncrna_chipseq_overlap, conservation, export, analysis, visualization
from app.schemas.common import HealthResponse

# ============================================================================
# slowapi Rate Limiting Setup (for per-endpoint rate limiting)
# ============================================================================
try:
    from slowapi import _rate_limit_exceeded_handler
    from slowapi.errors import RateLimitExceeded
    from app.routers.chipseq import limiter as chipseq_limiter
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


@asynccontextmanager
async def lifespan(app: FastAPI):
    """应用生命周期管理"""
    # 启动时执行
    logger.info("=" * 60)
    logger.info(f"🚀 {settings.APP_NAME} v{settings.APP_VERSION}")
    logger.info("=" * 60)

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
# slowapi Rate Limiting Integration (per-endpoint limits for ChIP-seq API)
# ============================================================================
if SLOWAPI_AVAILABLE and chipseq_limiter:
    app.state.limiter = chipseq_limiter
    app.add_exception_handler(RateLimitExceeded, _rate_limit_exceeded_handler)
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
        content=sanitized_exc.detail,
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
    from sqlalchemy import text

    try:
        # 测试数据库连接
        with engine.connect() as conn:
            conn.execute(text("SELECT 1"))
        db_status = "healthy"
    except Exception as e:
        # 安全改进：不暴露底层异常详情，只记录日志
        logger.error(f"Health check database error: {e}")
        db_status = "unhealthy"

    return HealthResponse(
        status="healthy" if db_status == "healthy" else "degraded",
        database=db_status,
        redis="not configured",
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
GENOMES_DIR = os.environ.get("GENOMES_DIR")

if GENOMES_DIR and os.path.exists(GENOMES_DIR):
    # 包装 StaticFiles 以添加 CORS 头（自定义实现，避免 BaseHTTPMiddleware 兼容性问题）
    from starlette.types import ASGIApp, Receive, Scope, Send

    # 创建独立的静态文件子应用，带 CORS 支持
    static_app = StaticFiles(directory=GENOMES_DIR)

    class CORSStaticFiles:
        """带 CORS 支持的静态文件服务（严格 Origin 验证）"""
        def __init__(self, app: ASGIApp, allow_origins: list):
            self.app = app
            self.allow_origins = set(allow_origins)  # Convert to set for O(1) lookup

        def _is_origin_allowed(self, origin: str) -> bool:
            """Check if the origin is in the allowed list"""
            return origin in self.allow_origins

        async def __call__(self, scope: Scope, receive: Receive, send: Send):
            if scope["type"] == "http":
                # 获取 Origin 头
                headers = dict(scope.get("headers", []))
                origin = headers.get(b"origin", b"").decode()

                # Validate origin against allowed list (no wildcard fallback)
                allowed_origin = origin if self._is_origin_allowed(origin) else ""

                # 检查是否是预检请求
                if scope["method"] == "OPTIONS":
                    # Only respond to preflight if origin is allowed
                    if allowed_origin:
                        response_headers = [
                            (b"access-control-allow-origin", allowed_origin.encode()),
                            (b"access-control-allow-methods", b"GET, HEAD, OPTIONS"),
                            (b"access-control-allow-headers", b"Range, Content-Type"),
                            (b"access-control-max-age", b"86400"),
                            (b"content-length", b"0"),
                        ]
                        await send({"type": "http.response.start", "status": 204, "headers": response_headers})
                        await send({"type": "http.response.body", "body": b""})
                    else:
                        # Origin not allowed - return 403
                        response_headers = [
                            (b"content-type", b"text/plain"),
                            (b"content-length", b"16"),
                        ]
                        await send({"type": "http.response.start", "status": 403, "headers": response_headers})
                        await send({"type": "http.response.body", "body": b"Origin forbidden"})
                    return

                # 包装 send 函数以添加 CORS 头
                async def send_with_cors(message):
                    if message["type"] == "http.response.start":
                        headers = list(message.get("headers", []))
                        # Only add CORS headers if origin is allowed
                        if allowed_origin:
                            headers.append((b"access-control-allow-origin", allowed_origin.encode()))
                            headers.append((b"access-control-allow-methods", b"GET, HEAD, OPTIONS"))
                            headers.append((b"access-control-allow-headers", b"Range, Content-Type"))
                            headers.append((b"access-control-expose-headers", b"Content-Length, Content-Range, Accept-Ranges"))
                        message = {**message, "headers": headers}
                    await send(message)

                await self.app(scope, receive, send_with_cors)
            else:
                await self.app(scope, receive, send)

    # 挂载带 CORS 的静态文件服务
    cors_static_app = CORSStaticFiles(static_app, settings.CORS_ORIGINS)
    app.mount("/genomes", cors_static_app)

    logger.info(f"📁 基因组文件服务已启用: /genomes -> {GENOMES_DIR}")
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
