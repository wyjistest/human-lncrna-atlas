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
from collections import deque
import time
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
from app.middleware.logging import LoggingMiddleware, MetricsMiddleware
from app.middleware.rate_limit import RateLimitMiddleware
from app.routers import genes, regulations, diseases, stats, network, admin, igv, features, conservation, chipseq, lncrna_chipseq_overlap
from app.schemas.common import HealthResponse

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
app.add_middleware(RateLimitMiddleware, requests_per_minute=100)  # 限流：100请求/分钟
app.add_middleware(LoggingMiddleware)
app.add_middleware(MetricsMiddleware)
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.CORS_ORIGINS,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# 保存MetricsMiddleware实例到app.state（用于/metrics端点）
# 注意：需要在第一个请求后才能获取实例
app.state.metrics_data = {
    # Phase 1 - 基础指标（保留向后兼容）
    "total_requests": 0,
    "total_errors": 0,
    "total_time": 0.0,
    "last_minute_requests": 0,

    # Phase 2 - 响应时间分布
    "response_time_buckets": {
        "0-50": 0,
        "50-100": 0,
        "100-200": 0,
        "200-500": 0,
        "500+": 0,
    },

    # Phase 2 - 时间序列数据（最近10分钟，每秒一条）
    "time_series": deque(maxlen=600),

    # Phase 2 - 端点统计 {"/api/v1/genes": {"requests": 0, "errors": 0, "total_time": 0.0}}
    "endpoints": {},

    # Phase 2 - 当前秒数据聚合
    "current_second": {"timestamp": 0, "requests": 0, "errors": 0},

    # Phase 3 - 响应时间原始数据（用于百分位计算）
    "response_times": deque(maxlen=1000),
}

# 记录应用启动时间（用于计算运行时间）
app.state.start_time = time.time()


# 全局异常处理
@app.exception_handler(Exception)
async def global_exception_handler(request: Request, exc: Exception):
    logger.error(f"Unhandled exception: {str(exc)}", exc_info=True)
    return JSONResponse(
        status_code=500,
        content={
            "message": "Internal server error",
            "detail": str(exc) if settings.LOG_LEVEL == "DEBUG" else "An error occurred",
        },
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
        db_status = f"unhealthy: {str(e)}"

    return HealthResponse(
        status="healthy" if db_status == "healthy" else "degraded",
        database=db_status,
        redis="not configured",
        version=settings.APP_VERSION,
    )


# 监控指标端点（原始格式，保留用于内部监控）
@app.get("/internal/metrics", tags=["monitoring"])
def get_internal_metrics():
    """
    获取原始性能指标（内部使用）

    注意：前端请使用 /api/v1/admin/metrics 端点
    """
    if hasattr(app.state, "metrics_data"):
        data = app.state.metrics_data
        total = data["total_requests"]
        errors = data["total_errors"]
        total_time = data["total_time"]

        avg_time = total_time / total if total > 0 else 0
        error_rate = errors / total if total > 0 else 0

        return {
            "total_requests": total,
            "total_errors": errors,
            "error_rate": f"{error_rate:.2%}",
            "avg_response_time": f"{avg_time:.3f}s",
        }
    return {"message": "Metrics not available"}


# 注册路由
app.include_router(genes.router, prefix=settings.API_V1_PREFIX)
app.include_router(regulations.router, prefix=settings.API_V1_PREFIX)
app.include_router(diseases.router, prefix=settings.API_V1_PREFIX)
app.include_router(stats.router, prefix=settings.API_V1_PREFIX)
app.include_router(network.router, prefix=settings.API_V1_PREFIX)
app.include_router(admin.router, prefix=settings.API_V1_PREFIX)
app.include_router(igv.router, prefix=settings.API_V1_PREFIX)
app.include_router(features.router, prefix=settings.API_V1_PREFIX)
app.include_router(conservation.router, prefix=settings.API_V1_PREFIX)
app.include_router(chipseq.router, prefix=settings.API_V1_PREFIX)
app.include_router(lncrna_chipseq_overlap.router, prefix=settings.API_V1_PREFIX)

# 挂载静态文件服务（用于 IGV.js 基因组文件）
# 使用独立的 FastAPI 子应用，完全绕过主应用的中间件（解决 BaseHTTPMiddleware 兼容性问题）
GENOMES_DIR = os.environ.get("GENOMES_DIR", "/data/wenyujianData/humanLncAtlas/genomes")

if os.path.exists(GENOMES_DIR):
    from starlette.applications import Starlette
    from starlette.routing import Mount
    from starlette.middleware import Middleware
    from starlette.middleware.cors import CORSMiddleware as StarletteCORS

    # 创建独立的静态文件子应用，带 CORS 支持
    static_app = StaticFiles(directory=GENOMES_DIR)

    # 包装 StaticFiles 以添加 CORS 头
    from starlette.types import ASGIApp, Receive, Scope, Send

    class CORSStaticFiles:
        """带 CORS 支持的静态文件服务"""
        def __init__(self, app: ASGIApp, allow_origins: list):
            self.app = app
            self.allow_origins = allow_origins

        async def __call__(self, scope: Scope, receive: Receive, send: Send):
            if scope["type"] == "http":
                # 获取 Origin 头
                headers = dict(scope.get("headers", []))
                origin = headers.get(b"origin", b"").decode()

                # 检查是否是预检请求
                if scope["method"] == "OPTIONS":
                    response_headers = [
                        (b"access-control-allow-origin", origin.encode() if origin else b"*"),
                        (b"access-control-allow-methods", b"GET, HEAD, OPTIONS"),
                        (b"access-control-allow-headers", b"Range, Content-Type"),
                        (b"access-control-max-age", b"86400"),
                        (b"content-length", b"0"),
                    ]
                    await send({"type": "http.response.start", "status": 204, "headers": response_headers})
                    await send({"type": "http.response.body", "body": b""})
                    return

                # 包装 send 函数以添加 CORS 头
                async def send_with_cors(message):
                    if message["type"] == "http.response.start":
                        headers = list(message.get("headers", []))
                        # 添加 CORS 头
                        headers.append((b"access-control-allow-origin", origin.encode() if origin else b"*"))
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


if __name__ == "__main__":
    import uvicorn

    uvicorn.run(
        "main:app",
        host="0.0.0.0",
        port=8000,
        reload=True,
        log_level="info",
    )
