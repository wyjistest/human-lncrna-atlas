"""
Genome Static File Service Mount

Phase 9.16: 从 main.py 提取
提供 IGV.js 基因组文件访问服务
"""
import logging
import os
from pathlib import PurePosixPath

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from starlette.responses import Response as StarletteResponse
from starlette.types import ASGIApp as StarletteASGIApp

from app.core.config import settings

logger = logging.getLogger("api")

# Phase 9.16: 文件扩展名白名单 - 防止暴露非基因组文件
# 参考: Codex 代码审查 - /genomes 安全加固
# Phase 9.23: 添加 .bb/.bigbed (BigBed 格式) - 修复 IGV.js bigBed 资源 403 问题
ALLOWED_GENOME_EXTENSIONS = {
    '.fa', '.fasta', '.fna',  # 基因组序列
    '.fai',                    # FASTA 索引
    '.gz', '.bgz',             # 压缩文件
    '.tbi', '.csi',            # Tabix 索引
    '.cytoband', '.cytoband.txt',  # 染色体带型（避免泛 .txt 放行）
    '.sizes', '.chrom.sizes',  # 染色体大小
    '.2bit',                   # 2bit 格式
    '.bed', '.bedgraph',       # BED 格式
    '.bb', '.bigbed',          # BigBed 格式 (Phase 9.23)
    '.gff', '.gff3', '.gtf',   # 注释文件
    '.bw', '.bigwig',          # BigWig
}


class GenomeFileWhitelistMiddleware:
    """只允许访问白名单内的文件扩展名"""

    def __init__(self, app: StarletteASGIApp):
        self.app = app

    @staticmethod
    def _is_safe_static_path(path: str) -> bool:
        """
        Best-effort path safety checks (defense-in-depth).

        Notes:
        - Starlette StaticFiles already prevents directory traversal outside the mount directory.
        - These checks further reduce the chance of accidental sensitive file exposure (e.g., dotfiles)
          and block suspicious paths early.
        """
        # Null byte / backslash are never expected in URL paths for this service.
        if "\x00" in path or "\\" in path:
            return False

        parts = PurePosixPath(path).parts
        for part in parts:
            # PurePosixPath('/a').parts -> ('/', 'a')
            if part in ("", "/"):
                continue

            # Explicit traversal segments (even though StaticFiles should handle these).
            if part in (".", ".."):
                return False

            # Dotfiles / hidden directories (avoid accidental exposure like ".env.gz").
            if part.startswith("."):
                return False

        return True

    async def __call__(self, scope, receive, send):
        if scope["type"] == "http":
            path = scope.get("path", "")

            if path and path != "/" and not self._is_safe_static_path(path):
                response = StarletteResponse(
                    content=b"Forbidden: Invalid path",
                    status_code=403,
                    media_type="text/plain",
                )
                await response(scope, receive, send)
                return

            # 获取文件扩展名（支持 .chrom.sizes 等复合扩展名）
            path_lower = path.lower()
            allowed = False
            for ext in ALLOWED_GENOME_EXTENSIONS:
                if path_lower.endswith(ext):
                    allowed = True
                    break

            if not allowed and path != "/" and not path.endswith("/"):
                # 返回 403 Forbidden
                response = StarletteResponse(
                    content=b"Forbidden: File type not allowed",
                    status_code=403,
                    media_type="text/plain"
                )
                await response(scope, receive, send)
                return

        await self.app(scope, receive, send)


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


def create_genomes_app() -> FastAPI:
    """
    创建基因组文件服务子应用

    Returns:
        配置好 CORS 和安全头的 FastAPI 子应用
    """
    genomes_app = FastAPI()

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

    # Phase 9.16: 文件扩展名白名单中间件（最后添加 = 最先执行）
    # 在 CORS 和安全头之前检查文件类型，拒绝非白名单文件
    genomes_app.add_middleware(GenomeFileWhitelistMiddleware)

    return genomes_app


def mount_genomes_app(app: FastAPI) -> bool:
    """
    挂载基因组文件服务到主应用

    挂载静态文件服务（用于 IGV.js 基因组文件）
    使用独立的 FastAPI 子应用，绕过主应用的 LoggingMiddleware（解决 BaseHTTPMiddleware 兼容性问题）
    注意：子应用有自己的安全头中间件 (StaticSecurityHeadersMiddleware)，与主应用安全头独立
    GENOMES_DIR 通过 Settings 加载，支持 .env 文件配置

    ⚠️ SECURITY WARNING:
    /genomes 端点会暴露 GENOMES_DIR 下的所有文件（递归）。
    请确保该目录仅包含公开的基因组数据文件（.fa, .fai, .cytoband 等）。
    不要在 GENOMES_DIR 中放置：
    - 配置文件（.env, .yaml, credentials）
    - 私有数据或敏感信息
    - 可执行文件或脚本
    建议使用专用目录，如 /data/genomes/，不与其他数据混放。

    Args:
        app: 主 FastAPI 应用实例

    Returns:
        True 如果成功挂载，False 如果目录不存在或未配置
    """
    genomes_dir = settings.GENOMES_DIR

    if not genomes_dir or not os.path.exists(genomes_dir):
        logger.warning("GENOMES_DIR not set or does not exist, genome file service disabled")
        return False

    # 创建并配置子应用
    genomes_app = create_genomes_app()

    # 挂载静态文件到子应用根路径
    genomes_app.mount("/", StaticFiles(directory=genomes_dir), name="genomes_static")

    # 将子应用挂载到主应用
    app.mount("/genomes", genomes_app)

    logger.info(f"Genome file service enabled: /genomes -> {genomes_dir}")
    return True
