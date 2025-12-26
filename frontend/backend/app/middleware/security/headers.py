"""
Security Headers Middleware

Phase 9.16: 从 main.py 提取
添加安全响应头，防御常见 Web 攻击
"""
from fastapi import Request

from app.core.config import settings


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

    # 关闭 DNS 预解析（减少隐私泄露面）
    response.headers["X-DNS-Prefetch-Control"] = "off"

    # 禁止旧式跨域策略文件（Flash/Adobe Reader 等遗留机制）
    response.headers["X-Permitted-Cross-Domain-Policies"] = "none"

    # HSTS - 仅在配置启用时添加（需要 HTTPS 已完全配置）
    if settings.ENABLE_HSTS:
        hsts_value = f"max-age={settings.HSTS_MAX_AGE}"
        if settings.HSTS_INCLUDE_SUBDOMAINS:
            hsts_value += "; includeSubDomains"
        if settings.HSTS_PRELOAD:
            hsts_value += "; preload"
        response.headers["Strict-Transport-Security"] = hsts_value

    # CSP - API 严格策略（禁止内联脚本、eval、外部资源）
    # API 返回 JSON/文本数据，不需要加载任何外部资源。
    #
    # ⚠️ 注意：FastAPI 的 Swagger UI (/docs) 与 ReDoc (/redoc) 需要加载 JS/CSS。
    # 若对文档页面也设置 `default-src 'none'`，浏览器会阻止资源加载，导致交互式文档不可用。
    path = request.url.path or ""
    if not (path.startswith("/docs") or path.startswith("/redoc")):
        response.headers["Content-Security-Policy"] = (
            "default-src 'none'; "
            "frame-ancestors 'none'; "
            "base-uri 'none'; "
            "form-action 'none'"
        )

    # 对敏感端点显式禁用缓存（避免浏览器/中间代理缓存 Admin/metrics 输出）
    normalized_path = path.rstrip("/")
    admin_prefix = f"{settings.API_V1_PREFIX}/admin"
    if normalized_path.endswith("/metrics") or normalized_path.startswith(admin_prefix):
        response.headers["Cache-Control"] = "no-store"
        response.headers["Pragma"] = "no-cache"

    return response
