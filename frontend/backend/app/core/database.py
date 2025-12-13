"""
数据库连接管理

Performance and Security Features:
- Connection pooling with QueuePool (PostgreSQL) or NullPool (SQLite)
- Query timeout protection (30s default, PostgreSQL only)
- Connection health checks (pool_pre_ping)
- Automatic connection recycling
- Multi-dialect support (PostgreSQL, SQLite)
"""
from sqlalchemy import create_engine, text, event
from sqlalchemy.orm import sessionmaker, declarative_base
from sqlalchemy.pool import QueuePool, StaticPool
from contextlib import contextmanager
import logging

from .config import settings

logger = logging.getLogger(__name__)

# Query timeout in milliseconds (default: 30 seconds)
QUERY_TIMEOUT_MS = settings.QUERY_TIMEOUT * 1000

# Detect database dialect from URL
_db_url = settings.database_url
_is_postgresql = _db_url.startswith("postgresql")
_is_sqlite = _db_url.startswith("sqlite")

# Build engine kwargs based on dialect
_engine_kwargs = {
    "echo": False,  # 生产环境关闭SQL日志
}

if _is_postgresql:
    # PostgreSQL: Use QueuePool with connection pooling
    # Note: statement_timeout is set via connect event listener (below) for consistency
    _engine_kwargs.update({
        "poolclass": QueuePool,
        "pool_size": 5,  # 连接池大小
        "max_overflow": 10,  # 超出 pool_size 后最多创建的连接数
        "pool_timeout": 30,  # 获取连接超时（秒）
        "pool_recycle": 1800,  # 连接回收时间（秒）
        "pool_pre_ping": True,  # 连接前检查，避免使用已断开的连接
    })
    logger.info("Using PostgreSQL database engine with connection pooling")
elif _is_sqlite:
    # SQLite: Use StaticPool for thread safety in multi-threaded environments
    _engine_kwargs.update({
        "poolclass": StaticPool,
        "connect_args": {
            "check_same_thread": False,  # Allow SQLite to be used across threads
        },
    })
    logger.info("Using SQLite database engine (demo mode)")
else:
    # Generic fallback for other databases
    _engine_kwargs.update({
        "poolclass": QueuePool,
        "pool_size": 5,
        "max_overflow": 10,
        "pool_timeout": 30,
        "pool_recycle": 1800,
        "pool_pre_ping": True,
    })
    logger.info(f"Using generic database engine for: {_db_url.split(':')[0]}")

# 创建数据库引擎
engine = create_engine(settings.database_url, **_engine_kwargs)


# Event listener to set statement_timeout on each connection checkout (PostgreSQL only)
if _is_postgresql:
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
        if _is_sqlite:
            logger.info(f"Database connection successful: SQLite ({_db_url})")
        else:
            logger.info(f"Database connection successful: {settings.DATABASE_NAME}@{settings.DATABASE_HOST}")
        return True
    except Exception as e:
        logger.error(f"Database connection failed: {e}")
        return False


def close_db():
    """
    关闭数据库连接
    在应用关闭时调用
    """
    engine.dispose()
    logger.info("Database connections closed")


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
        For non-PostgreSQL databases, this is a no-op (timeout not supported).
        Uses session-level SET (not SET LOCAL) to ensure timeout applies
        across the entire context, not just within a single transaction.
    """
    if _is_postgresql:
        timeout_ms = timeout_seconds * 1000
        try:
            db.execute(text(f"SET statement_timeout = {timeout_ms}"))
            yield db
        finally:
            # Reset to default timeout
            db.execute(text(f"SET statement_timeout = {QUERY_TIMEOUT_MS}"))
    else:
        # Non-PostgreSQL: timeout not supported, just yield the session
        yield db
