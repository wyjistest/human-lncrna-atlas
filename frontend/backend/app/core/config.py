"""
应用配置模块
"""
import json
from pathlib import Path
from typing import Optional, List, Any
from urllib.parse import quote
from pydantic_settings import BaseSettings, SettingsConfigDict
from pydantic import BaseModel, Field, SecretStr, field_validator
from sqlalchemy.engine import URL

# 计算 .env 文件的绝对路径（相对于 backend 目录）
# 这样无论从哪个目录启动应用，都能正确加载 .env
_BACKEND_DIR = Path(__file__).resolve().parent.parent.parent
_ENV_FILE = _BACKEND_DIR / ".env"


class AlertThresholds(BaseModel):
    """告警阈值配置"""

    error_rate: float = Field(default=0.05, description="错误率阈值 > 5%")
    response_time_ms: float = Field(default=500.0, description="平均响应时间阈值 > 500ms")
    cpu_percent: float = Field(default=80.0, description="CPU使用率阈值 > 80%")
    memory_percent: float = Field(default=85.0, description="内存使用率阈值 > 85%")


class Settings(BaseSettings):
    """应用配置"""

    # 应用信息
    APP_NAME: str = "Human LncRNA Atlas API"
    APP_VERSION: str = "0.1.0"
    API_V1_PREFIX: str = "/api/v1"

    # 环境模式配置（Phase 9.18 - Codex审查修复）
    # production: 严格模式，DB连接失败时拒绝启动
    # development: 宽松模式，DB连接失败时仍启动（方便开发调试）
    ENV: str = Field(
        default="development",
        validation_alias="ENV",
        description="运行环境: production | development (默认 development)"
    )

    @property
    def is_production(self) -> bool:
        """判断是否为生产环境"""
        return self.ENV.lower() in ("production", "prod")

    # 数据库配置
    DATABASE_HOST: str = Field(default="localhost", validation_alias="DB_HOST")
    DATABASE_PORT: int = Field(default=5432, validation_alias="DB_PORT")
    DATABASE_USER: str = Field(default="amax", validation_alias="DB_USER")
    # SECURITY: 使用 SecretStr 保护密码，避免在日志/异常中泄露
    DATABASE_PASSWORD: SecretStr = Field(default=SecretStr(""), validation_alias="DB_PASSWORD")
    DATABASE_NAME: str = Field(default="lncrna_production", validation_alias="DB_NAME")

    # 数据库连接池配置
    # P1-004 优化: 增加默认连接池大小以支持生产环境并发
    DB_POOL_SIZE: int = Field(
        default=10,
        validation_alias="DB_POOL_SIZE",
        description="连接池大小 (默认 10，生产环境建议 20)"
    )
    DB_POOL_MAX_OVERFLOW: int = Field(
        default=20,
        validation_alias="DB_POOL_MAX_OVERFLOW",
        description="超出 pool_size 后最多创建的连接数 (默认 20，生产环境建议 30)"
    )
    DB_POOL_TIMEOUT: int = Field(
        default=30,
        validation_alias="DB_POOL_TIMEOUT",
        description="获取连接超时秒数 (默认 30)"
    )
    DB_POOL_RECYCLE: int = Field(
        default=1800,
        validation_alias="DB_POOL_RECYCLE",
        description="连接回收时间秒数 (默认 1800 = 30分钟)"
    )

    # Redis配置
    REDIS_HOST: str = Field(default="localhost", validation_alias="REDIS_HOST")
    REDIS_PORT: int = Field(default=6379, validation_alias="REDIS_PORT")
    REDIS_DB: int = Field(default=0, validation_alias="REDIS_DB")
    # SECURITY: 使用 SecretStr 保护 Redis 密码
    REDIS_PASSWORD: Optional[SecretStr] = Field(default=None, validation_alias="REDIS_PASSWORD")

    # CORS配置（支持环境变量 CORS_ORIGINS，JSON 数组格式）
    # 默认值仅包含 localhost，生产环境请通过 CORS_ORIGINS 环境变量配置实际域名
    # 安全提示：不要在默认值中硬编码具体 IP 地址
    CORS_ORIGINS: List[str] = Field(
        default=[
            "http://localhost:5173",  # Vite开发服务器
            "http://localhost:5174",  # Vite备用端口
            "http://localhost:3000",  # 备用端口
            "http://127.0.0.1:5173",
            "http://127.0.0.1:5174",
            "http://127.0.0.1:3000",
        ],
        validation_alias="CORS_ORIGINS",
        description="允许的 CORS 来源列表，环境变量需使用 JSON 数组格式"
    )

    @field_validator("CORS_ORIGINS", mode="before")
    @classmethod
    def parse_cors_origins(cls, v: Any) -> List[str]:
        """
        解析并验证 CORS_ORIGINS 配置

        支持两种格式：
        1. JSON 数组字符串: '["http://localhost:5173", "http://example.com"]'
        2. 已解析的列表（来自代码默认值）

        安全校验（Phase 9.18 - Codex审查修复）：
        - 禁止通配符 '*'（与 allow_credentials=true 不兼容且不安全）
        - 强制要求 http:// 或 https:// scheme
        - 拒绝空 scheme 或格式错误的 URL
        """
        from urllib.parse import urlparse

        def validate_origin(origin: str) -> str:
            """
            验证单个 origin URL 的安全性

            Phase 9.19 增强校验（Codex审查修复）：
            - 禁止通配符 '*'
            - 强制 http/https scheme
            - 禁止 path/query/fragment（浏览器 Origin 头不包含这些）
            - 禁止 userinfo（user:pass@host 可能泄露凭据到日志）
            """
            origin = str(origin).strip()

            # 禁止通配符
            if origin == "*":
                raise ValueError(
                    "CORS_ORIGINS: Wildcard '*' is not allowed with allow_credentials=true. "
                    "Please specify explicit origins."
                )

            # 解析 URL
            parsed = urlparse(origin)

            # 强制要求 scheme
            if not parsed.scheme:
                raise ValueError(
                    f"CORS_ORIGINS: Origin '{origin}' is missing scheme. "
                    "Must be http:// or https://"
                )

            # 仅允许 http/https scheme
            if parsed.scheme not in ("http", "https"):
                raise ValueError(
                    f"CORS_ORIGINS: Origin '{origin}' has invalid scheme '{parsed.scheme}'. "
                    "Only http:// and https:// are allowed."
                )

            # 强制要求 host
            if not parsed.netloc:
                raise ValueError(
                    f"CORS_ORIGINS: Origin '{origin}' is missing host."
                )

            # Phase 9.19: 禁止 userinfo（user:pass@host 格式）
            # 安全风险：凭据可能泄露到日志中
            if parsed.username or parsed.password:
                raise ValueError(
                    f"CORS_ORIGINS: Origin '{origin}' contains userinfo (username/password). "
                    "This is not allowed for security reasons."
                )

            # Phase 9.19: 禁止 path/query/fragment
            # 浏览器发送的 Origin 头只包含 scheme + host + port，不包含 path
            # 配置带 path 的 origin 永远不会匹配，属于误配置
            if parsed.path and parsed.path != "/":
                raise ValueError(
                    f"CORS_ORIGINS: Origin '{origin}' contains a path '{parsed.path}'. "
                    "Browser Origin headers never include paths. Remove the path."
                )
            if parsed.query:
                raise ValueError(
                    f"CORS_ORIGINS: Origin '{origin}' contains a query string. "
                    "Browser Origin headers never include query strings. Remove it."
                )
            if parsed.fragment:
                raise ValueError(
                    f"CORS_ORIGINS: Origin '{origin}' contains a fragment. "
                    "Browser Origin headers never include fragments. Remove it."
                )

            # 返回规范化的 origin（去除尾部斜杠）
            normalized = f"{parsed.scheme}://{parsed.netloc}"
            return normalized

        # 解析输入
        origins: List[str]
        if isinstance(v, str):
            try:
                parsed = json.loads(v)
                if not isinstance(parsed, list):
                    raise ValueError("CORS_ORIGINS must be a JSON array")
                origins = [str(item) for item in parsed]
            except json.JSONDecodeError as e:
                raise ValueError(f"Invalid JSON in CORS_ORIGINS: {e}")
        elif isinstance(v, list):
            origins = v
        else:
            raise ValueError(f"CORS_ORIGINS must be a list or JSON string, got {type(v)}")

        # 验证每个 origin
        validated_origins = [validate_origin(o) for o in origins]

        return validated_origins

    # TrustedHost 配置（Phase 9.18 - Codex审查修复）
    # 防止 HTTP Host Header 攻击
    # 默认允许 localhost 和通配符（开发环境），生产环境应配置实际域名
    TRUSTED_HOSTS: List[str] = Field(
        default=["localhost", "127.0.0.1", "*.localhost"],
        validation_alias="TRUSTED_HOSTS",
        description="允许的 Host 头列表，支持通配符如 '*.example.com'"
    )

    @field_validator("TRUSTED_HOSTS", mode="before")
    @classmethod
    def parse_trusted_hosts(cls, v: Any) -> List[str]:
        """
        解析并验证 TRUSTED_HOSTS 配置

        Phase 9.19 增强校验（Codex审查修复）：
        - 禁止 http:// 或 https:// 前缀（应为纯主机名）
        - 禁止单独的 '*' 通配符（允许所有主机，危险）
        - 验证主机名格式
        """
        import re

        def validate_host(host: str) -> str:
            """验证单个 host 条目"""
            host = str(host).strip()

            if not host:
                raise ValueError("TRUSTED_HOSTS: Empty host entry is not allowed.")

            # 禁止 URL 格式（应为纯主机名，不含 scheme）
            if host.startswith(("http://", "https://", "//")):
                raise ValueError(
                    f"TRUSTED_HOSTS: '{host}' should be a hostname, not a URL. "
                    "Remove the scheme (http:// or https://). Example: 'example.com'"
                )

            # 禁止单独的 '*' 通配符（允许所有主机，安全风险）
            if host == "*":
                raise ValueError(
                    "TRUSTED_HOSTS: Wildcard '*' alone is not allowed as it accepts all hosts. "
                    "Use specific domains like '*.example.com' or 'api.example.com'."
                )

            # 验证通配符格式（只允许 *.domain.com 形式）
            if "*" in host:
                # 通配符只能在开头，且必须是 *.something 格式
                if not re.match(r"^\*\.[a-zA-Z0-9]", host):
                    raise ValueError(
                        f"TRUSTED_HOSTS: Invalid wildcard pattern '{host}'. "
                        "Wildcards must be at the start: '*.example.com'"
                    )

            # 基本主机名格式验证（允许通配符、字母、数字、点、连字符）
            # 移除开头的 *. 后验证剩余部分
            check_host = host[2:] if host.startswith("*.") else host
            if check_host and not re.match(r"^[a-zA-Z0-9]([a-zA-Z0-9\-\.]*[a-zA-Z0-9])?$", check_host):
                # 允许单字符主机名如 "localhost"
                if len(check_host) > 1 or not check_host.isalnum():
                    raise ValueError(
                        f"TRUSTED_HOSTS: '{host}' contains invalid characters. "
                        "Use only letters, numbers, dots, and hyphens."
                    )

            return host

        # 解析输入
        hosts: List[str]
        if isinstance(v, str):
            try:
                parsed = json.loads(v)
                if isinstance(parsed, list):
                    hosts = [str(item).strip() for item in parsed if item]
                else:
                    raise ValueError("TRUSTED_HOSTS must be a JSON array")
            except json.JSONDecodeError as e:
                raise ValueError(f"Invalid JSON in TRUSTED_HOSTS: {e}")
        elif isinstance(v, list):
            hosts = [str(item).strip() for item in v if item]
        else:
            raise ValueError(f"TRUSTED_HOSTS must be a list or JSON string, got {type(v)}")

        # 验证每个 host
        return [validate_host(h) for h in hosts]

    # 缓存配置
    CACHE_TTL: int = Field(default=3600, validation_alias="CACHE_TTL")  # 缓存时间（秒）
    ENABLE_CACHE: bool = Field(default=True, validation_alias="ENABLE_CACHE")

    # 分页配置
    DEFAULT_PAGE_SIZE: int = 100
    MAX_PAGE_SIZE: int = 1000

    # 日志配置
    LOG_LEVEL: str = Field(default="INFO", validation_alias="LOG_LEVEL")

    # 请求日志配置
    REQUEST_LOG_ENABLED: bool = Field(
        default=True,
        validation_alias="REQUEST_LOG_ENABLED",
        description="是否启用请求日志 (默认 true)"
    )
    REQUEST_LOG_SLOW_THRESHOLD_MS: int = Field(
        default=0,
        validation_alias="REQUEST_LOG_SLOW_THRESHOLD_MS",
        description="仅记录慢请求阈值（毫秒），0 表示记录全部 (默认 0)"
    )
    REQUEST_LOG_SAMPLE_RATE: float = Field(
        default=1.0,
        validation_alias="REQUEST_LOG_SAMPLE_RATE",
        description="请求日志采样率 0.0-1.0 (默认 1.0 = 100%)"
    )
    REQUEST_LOG_MAX_URL_LENGTH: int = Field(
        default=2048,
        validation_alias="REQUEST_LOG_MAX_URL_LENGTH",
        description=(
            "请求日志中记录的 URL 最大长度（防止超长查询字符串导致日志膨胀/DoS）。"
            "0 表示不限制。"
        ),
        ge=0,
    )

    # 性能配置
    QUERY_TIMEOUT: int = Field(default=30, validation_alias="QUERY_TIMEOUT")  # 查询超时（秒）

    # 告警阈值配置
    ALERT_THRESHOLDS: AlertThresholds = AlertThresholds()

    # Admin API 安全配置
    # SECURITY: 使用 SecretStr 保护 Admin API Key
    ADMIN_API_KEY: Optional[SecretStr] = Field(default=None, validation_alias="ADMIN_API_KEY")
    ADMIN_ALLOWED_IPS: list = Field(
        default=["127.0.0.1", "localhost", "::1"],
        description="允许访问 Admin API 的 IP 地址白名单"
    )
    # 严格模式：启用后无条件要求 API Key，不再信任私网 IP 自动放行
    # ⚠️ 生产安全：默认 true，要求配置 ADMIN_API_KEY
    # 开发环境可设为 false 或使用 SECURITY_ALLOW_INSECURE=true 绕过检查
    ADMIN_REQUIRE_API_KEY: bool = Field(
        default=True,
        validation_alias="ADMIN_REQUIRE_API_KEY",
        description="⚠️ SECURITY: Defaults to true. Requires ADMIN_API_KEY to be configured. "
                    "Set to false ONLY for local development with SECURITY_ALLOW_INSECURE=true."
    )

    # Trusted Proxies for X-Forwarded-For header validation
    # Only trust X-Forwarded-For headers from these IP addresses/ranges
    # SECURITY NOTE: Default values are conservative (localhost only).
    # In production with a reverse proxy (nginx, traefik, etc.), add the proxy's IP.
    # Avoid trusting entire private ranges (10.0.0.0/8, 172.16.0.0/12, 192.168.0.0/16)
    # unless you fully control that network segment.
    TRUSTED_PROXIES: list = Field(
        default=[
            "127.0.0.1",        # localhost IPv4
            "::1",              # localhost IPv6
        ],
        description="IP addresses/ranges trusted as reverse proxies for X-Forwarded-For parsing. "
                    "Add your reverse proxy IP here (e.g., '10.0.0.1' or '192.168.1.100')."
    )

    # Rate Limiting - Private IP Bypass
    # When False (default), rate limiting applies to all requests including private IPs
    # When True, requests from private/internal IPs bypass rate limiting (dev convenience)
    # SECURITY NOTE: Keep False in production to prevent bypass via internal network
    RATE_LIMIT_BYPASS_PRIVATE: bool = Field(
        default=False,
        validation_alias="RATE_LIMIT_BYPASS_PRIVATE",
        description="Allow private IPs to bypass rate limiting (dev only, keep False in production)"
    )

    RATELIMIT_STORAGE_URL: Optional[SecretStr] = Field(
        default=None,
        validation_alias="RATELIMIT_STORAGE_URL",
        description="SlowAPI storage backend URI (recommended: Redis) for distributed rate limiting"
    )
    RATELIMIT_KEY_PREFIX: str = Field(
        default="lncrna_atlas",
        validation_alias="RATELIMIT_KEY_PREFIX",
        description="Prefix for SlowAPI rate limit keys (helps avoid collisions)"
    )

    # HSTS (HTTP Strict Transport Security)
    # Only enable when HTTPS is fully configured - this tells browsers to ONLY use HTTPS
    # SECURITY NOTE: Once enabled with preload, it's very difficult to disable
    ENABLE_HSTS: bool = Field(
        default=False,
        validation_alias="ENABLE_HSTS",
        description="Enable HSTS header (only enable when HTTPS is fully configured)"
    )
    HSTS_MAX_AGE: int = Field(
        default=31536000,  # 1 year
        validation_alias="HSTS_MAX_AGE",
        description="HSTS max-age in seconds (default: 1 year)"
    )
    HSTS_INCLUDE_SUBDOMAINS: bool = Field(
        default=True,
        validation_alias="HSTS_INCLUDE_SUBDOMAINS",
        description="Include subdomains in HSTS policy"
    )
    HSTS_PRELOAD: bool = Field(
        default=False,
        validation_alias="HSTS_PRELOAD",
        description="Add preload directive (only after testing, hard to undo)"
    )

    # IGV Genome Files Directory
    # Path to directory containing genome reference files for IGV.js browser
    # If not set or directory doesn't exist, IGV static file service will be disabled
    GENOMES_DIR: Optional[str] = Field(
        default=None,
        validation_alias="GENOMES_DIR",
        description="Directory containing genome files for IGV.js (e.g., /data/genomes)"
    )

    @property
    def database_url(self) -> str:
        """构建数据库连接URL

        Phase 9.17: 使用 SQLAlchemy URL.create() 构建 URL
        解决密码中包含 @:/#% 等特殊字符导致连接失败的问题
        """
        # SECURITY: 使用 get_secret_value() 获取真实密码
        password = self.DATABASE_PASSWORD.get_secret_value() if self.DATABASE_PASSWORD else None

        # 使用 SQLAlchemy URL.create() 自动处理特殊字符编码
        url_obj = URL.create(
            drivername="postgresql",
            username=self.DATABASE_USER,
            password=password if password else None,
            host=self.DATABASE_HOST,
            port=self.DATABASE_PORT,
            database=self.DATABASE_NAME,
        )
        return str(url_obj)

    @property
    def safe_database_url(self) -> str:
        """构建脱敏的数据库连接URL（用于日志）"""
        password = self.DATABASE_PASSWORD.get_secret_value() if self.DATABASE_PASSWORD else ""
        if password:
            return f"postgresql://{self.DATABASE_USER}:***@{self.DATABASE_HOST}:{self.DATABASE_PORT}/{self.DATABASE_NAME}"
        else:
            return f"postgresql://{self.DATABASE_USER}@{self.DATABASE_HOST}:{self.DATABASE_PORT}/{self.DATABASE_NAME}"

    # Note: async_database_url removed - asyncpg not in dependencies and not used
    # If async DB support is needed, add asyncpg to requirements.txt first

    @property
    def redis_url(self) -> str:
        """构建Redis连接URL

        Phase 9.17: 使用 quote(safe='') 编码密码中的特殊字符
        """
        # SECURITY: 使用 get_secret_value() 获取真实密码
        password = self.REDIS_PASSWORD.get_secret_value() if self.REDIS_PASSWORD else None
        if password:
            # URL 编码密码中的特殊字符 (@:/#%)
            # 使用 quote(safe='') 而非 quote_plus，因为 quote_plus 把空格编码为 +
            # 但在 URL userinfo 部分，+ 不会被还原为空格 (RFC 3986)
            encoded_password = quote(password, safe='')
            return f"redis://:{encoded_password}@{self.REDIS_HOST}:{self.REDIS_PORT}/{self.REDIS_DB}"
        else:
            return f"redis://{self.REDIS_HOST}:{self.REDIS_PORT}/{self.REDIS_DB}"

    @property
    def ratelimit_storage_url(self) -> Optional[str]:
        """
        获取 SlowAPI 限流存储 URL（解密 SecretStr）。

        Returns:
            storage uri 字符串或 None（未配置）
        """
        return self.RATELIMIT_STORAGE_URL.get_secret_value() if self.RATELIMIT_STORAGE_URL else None

    model_config = SettingsConfigDict(
        env_file=str(_ENV_FILE),  # 使用绝对路径，支持从任意目录启动
        case_sensitive=True,
    )


# 全局配置实例
settings = Settings()
