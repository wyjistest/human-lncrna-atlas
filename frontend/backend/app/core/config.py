"""
应用配置模块
"""
from typing import Optional
from pydantic_settings import BaseSettings, SettingsConfigDict
from pydantic import BaseModel, Field


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
    DATABASE_HOST: str = Field(default="localhost", env="DB_HOST")
    DATABASE_PORT: int = Field(default=5432, env="DB_PORT")
    DATABASE_USER: str = Field(default="amax", env="DB_USER")
    DATABASE_PASSWORD: str = Field(default="", env="DB_PASSWORD")
    DATABASE_NAME: str = Field(default="lncrna_production", env="DB_NAME")

    # Redis配置
    REDIS_HOST: str = Field(default="localhost", env="REDIS_HOST")
    REDIS_PORT: int = Field(default=6379, env="REDIS_PORT")
    REDIS_DB: int = Field(default=0, env="REDIS_DB")
    REDIS_PASSWORD: Optional[str] = Field(default=None, env="REDIS_PASSWORD")

    # CORS配置（移除通配符以提高安全性）
    CORS_ORIGINS: list = [
        "http://localhost:5173",  # Vite开发服务器
        "http://localhost:5174",  # Vite备用端口
        "http://localhost:3000",  # 备用端口
        "http://127.0.0.1:5173",
        "http://127.0.0.1:5174",
        "http://127.0.0.1:3000",
        "http://192.168.6.135:5173",  # 内网访问
        "http://192.168.6.135:5174",
        "http://45.62.117.191:6003",  # 公网前端
        "http://45.62.117.191:5173",
        "http://45.62.117.191:5174",
        # 如需添加更多来源，请在此处明确指定
    ]

    # 缓存配置
    CACHE_TTL: int = Field(default=3600, env="CACHE_TTL")  # 缓存时间（秒）
    ENABLE_CACHE: bool = Field(default=True, env="ENABLE_CACHE")

    # 分页配置
    DEFAULT_PAGE_SIZE: int = 100
    MAX_PAGE_SIZE: int = 1000

    # 日志配置
    LOG_LEVEL: str = Field(default="INFO", env="LOG_LEVEL")

    # 性能配置
    QUERY_TIMEOUT: int = Field(default=30, env="QUERY_TIMEOUT")  # 查询超时（秒）

    # 告警阈值配置
    ALERT_THRESHOLDS: AlertThresholds = AlertThresholds()

    @property
    def database_url(self) -> str:
        """构建数据库连接URL"""
        if self.DATABASE_PASSWORD:
            return f"postgresql://{self.DATABASE_USER}:{self.DATABASE_PASSWORD}@{self.DATABASE_HOST}:{self.DATABASE_PORT}/{self.DATABASE_NAME}"
        else:
            return f"postgresql://{self.DATABASE_USER}@{self.DATABASE_HOST}:{self.DATABASE_PORT}/{self.DATABASE_NAME}"

    @property
    def async_database_url(self) -> str:
        """构建异步数据库连接URL"""
        if self.DATABASE_PASSWORD:
            return f"postgresql+asyncpg://{self.DATABASE_USER}:{self.DATABASE_PASSWORD}@{self.DATABASE_HOST}:{self.DATABASE_PORT}/{self.DATABASE_NAME}"
        else:
            return f"postgresql+asyncpg://{self.DATABASE_USER}@{self.DATABASE_HOST}:{self.DATABASE_PORT}/{self.DATABASE_NAME}"

    @property
    def redis_url(self) -> str:
        """构建Redis连接URL"""
        if self.REDIS_PASSWORD:
            return f"redis://:{self.REDIS_PASSWORD}@{self.REDIS_HOST}:{self.REDIS_PORT}/{self.REDIS_DB}"
        else:
            return f"redis://{self.REDIS_HOST}:{self.REDIS_PORT}/{self.REDIS_DB}"

    model_config = SettingsConfigDict(
        env_file=".env",
        case_sensitive=True,
    )


# 全局配置实例
settings = Settings()
