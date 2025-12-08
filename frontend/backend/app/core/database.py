"""
数据库连接管理

Performance and Security Features:
- Connection pooling with QueuePool
- Query timeout protection (30s default)
- Connection health checks (pool_pre_ping)
- Automatic connection recycling
"""
from sqlalchemy import create_engine, text, event
from sqlalchemy.orm import sessionmaker, declarative_base
from sqlalchemy.pool import QueuePool
from contextlib import contextmanager
import logging

from .config import settings

logger = logging.getLogger(__name__)

# Query timeout in milliseconds (default: 30 seconds)
QUERY_TIMEOUT_MS = settings.QUERY_TIMEOUT * 1000

# 创建数据库引擎（使用连接池）
engine = create_engine(
    settings.database_url,
    poolclass=QueuePool,
    pool_size=5,  # 连接池大小
    max_overflow=10,  # 超出 pool_size 后最多创建的连接数
    pool_timeout=30,  # 获取连接超时（秒）
    pool_recycle=1800,  # 连接回收时间（秒）
    pool_pre_ping=True,  # 连接前检查，避免使用已断开的连接
    echo=False,  # 生产环境关闭SQL日志
    # PostgreSQL-specific: Set statement timeout to prevent long-running queries
    connect_args={
        "options": f"-c statement_timeout={QUERY_TIMEOUT_MS}"
    },
)


# Event listener to set statement_timeout on each connection checkout
@event.listens_for(engine, "connect")
def set_statement_timeout(dbapi_connection, connection_record):
    """
    Set PostgreSQL statement_timeout on each new connection.
    This prevents any single query from running longer than QUERY_TIMEOUT seconds.
    """
    cursor = dbapi_connection.cursor()
    cursor.execute(f"SET statement_timeout = {QUERY_TIMEOUT_MS}")
    cursor.close()
    logger.debug(f"Set statement_timeout to {QUERY_TIMEOUT_MS}ms on new connection")

# 创建Session工厂
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

# ORM基类
Base = declarative_base()


def get_db():
    """
    数据库会话依赖注入
    用于FastAPI路由
    """
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


def init_db():
    """
    初始化数据库连接
    在应用启动时调用
    """
    try:
        # 测试连接
        with engine.connect() as conn:
            conn.execute(text("SELECT 1"))
        print(f"✅ 数据库连接成功: {settings.DATABASE_NAME}@{settings.DATABASE_HOST}")
        return True
    except Exception as e:
        print(f"❌ 数据库连接失败: {e}")
        return False


def close_db():
    """
    关闭数据库连接
    在应用关闭时调用
    """
    engine.dispose()
    print("Database connections closed")


@contextmanager
def with_timeout(db, timeout_seconds: int):
    """
    Context manager for executing queries with a custom timeout.

    Usage:
        with with_timeout(db, 60) as session:
            # This query will timeout after 60 seconds
            result = session.execute(text("SELECT ..."))

    Args:
        db: SQLAlchemy Session
        timeout_seconds: Custom timeout in seconds

    Note:
        The timeout is reset to default after the context exits.
    """
    timeout_ms = timeout_seconds * 1000
    try:
        db.execute(text(f"SET LOCAL statement_timeout = {timeout_ms}"))
        yield db
    finally:
        # Reset to default timeout
        db.execute(text(f"SET LOCAL statement_timeout = {QUERY_TIMEOUT_MS}"))
