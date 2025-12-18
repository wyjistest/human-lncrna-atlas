"""
应用配置模块
"""
import json
from pathlib import Path
from typing import Optional, List, Any
from pydantic_settings import BaseSettings, SettingsConfigDict
from pydantic import BaseModel, Field, field_validator

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

    # 数据库配置
    DATABASE_HOST: str = Field(default="localhost", validation_alias="DB_HOST")
    DATABASE_PORT: int = Field(default=5432, validation_alias="DB_PORT")
    DATABASE_USER: str = Field(default="amax", validation_alias="DB_USER")
    DATABASE_PASSWORD: str = Field(default="", validation_alias="DB_PASSWORD")
    DATABASE_NAME: str = Field(default="lncrna_production", validation_alias="DB_NAME")

    # 数据库连接池配置
    DB_POOL_SIZE: int = Field(
        default=5,
        validation_alias="DB_POOL_SIZE",
        description="连接池大小 (默认 5)"
    )
    DB_POOL_MAX_OVERFLOW: int = Field(
        default=10,
        validation_alias="DB_POOL_MAX_OVERFLOW",
        description="超出 pool_size 后最多创建的连接数 (默认 10)"
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
    REDIS_PASSWORD: Optional[str] = Field(default=None, validation_alias="REDIS_PASSWORD")

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
        解析 CORS_ORIGINS 配置

        支持两种格式：
        1. JSON 数组字符串: '["http://localhost:5173", "http://example.com"]'
        2. 已解析的列表（来自代码默认值）
        """
        if isinstance(v, str):
            try:
                parsed = json.loads(v)
                if isinstance(parsed, list):
                    return [str(item) for item in parsed]
                raise ValueError("CORS_ORIGINS must be a JSON array")
            except json.JSONDecodeError as e:
                raise ValueError(f"Invalid JSON in CORS_ORIGINS: {e}")
        if isinstance(v, list):
            return v
        raise ValueError(f"CORS_ORIGINS must be a list or JSON string, got {type(v)}")

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

    # 性能配置
    QUERY_TIMEOUT: int = Field(default=30, validation_alias="QUERY_TIMEOUT")  # 查询超时（秒）

    # 告警阈值配置
    ALERT_THRESHOLDS: AlertThresholds = AlertThresholds()

    # Admin API 安全配置
    ADMIN_API_KEY: Optional[str] = Field(default=None, validation_alias="ADMIN_API_KEY")
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
        """构建数据库连接URL"""
        if self.DATABASE_PASSWORD:
            return f"postgresql://{self.DATABASE_USER}:{self.DATABASE_PASSWORD}@{self.DATABASE_HOST}:{self.DATABASE_PORT}/{self.DATABASE_NAME}"
        else:
            return f"postgresql://{self.DATABASE_USER}@{self.DATABASE_HOST}:{self.DATABASE_PORT}/{self.DATABASE_NAME}"

    # Note: async_database_url removed - asyncpg not in dependencies and not used
    # If async DB support is needed, add asyncpg to requirements.txt first

    @property
    def redis_url(self) -> str:
        """构建Redis连接URL"""
        if self.REDIS_PASSWORD:
            return f"redis://:{self.REDIS_PASSWORD}@{self.REDIS_HOST}:{self.REDIS_PORT}/{self.REDIS_DB}"
        else:
            return f"redis://{self.REDIS_HOST}:{self.REDIS_PORT}/{self.REDIS_DB}"

    model_config = SettingsConfigDict(
        env_file=str(_ENV_FILE),  # 使用绝对路径，支持从任意目录启动
        case_sensitive=True,
    )


# 全局配置实例
settings = Settings()
