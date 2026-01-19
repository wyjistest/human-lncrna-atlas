"""
数据库连接管理

Performance and Security Features:
- Connection pooling with QueuePool (PostgreSQL) or StaticPool (SQLite)
- Query timeout protection (30s default, PostgreSQL only)
- Connection health checks (pool_pre_ping, configurable)
- Automatic connection recycling
- Multi-dialect support (PostgreSQL, SQLite)
"""
from contextlib import contextmanager
from contextvars import ContextVar, Token
from dataclasses import dataclass, field
import hashlib
import logging
import re
import time
from typing import Optional

from sqlalchemy import create_engine, text, event
from sqlalchemy.orm import sessionmaker, declarative_base
from sqlalchemy.pool import QueuePool, StaticPool

from .config import settings
from .utils import sanitize_for_log

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
    # Pool parameters configurable via environment variables (see config.py)
    # Note: statement_timeout is set via connect event listener (below) for consistency
    _engine_kwargs.update({
        "poolclass": QueuePool,
        "pool_size": settings.DB_POOL_SIZE,
        "max_overflow": settings.DB_POOL_MAX_OVERFLOW,
        "pool_timeout": settings.DB_POOL_TIMEOUT,
        "pool_recycle": settings.DB_POOL_RECYCLE,
        # pool_pre_ping: 取连接时做一次轻量校验，避免使用已断开的连接（可配置）
        "pool_pre_ping": settings.DB_POOL_PRE_PING,
    })
    logger.info(
        f"Using PostgreSQL database engine with connection pooling "
        f"(pool_size={settings.DB_POOL_SIZE}, max_overflow={settings.DB_POOL_MAX_OVERFLOW}, "
        f"pool_pre_ping={settings.DB_POOL_PRE_PING})"
    )
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
        "pool_size": settings.DB_POOL_SIZE,
        "max_overflow": settings.DB_POOL_MAX_OVERFLOW,
        "pool_timeout": settings.DB_POOL_TIMEOUT,
        "pool_recycle": settings.DB_POOL_RECYCLE,
        "pool_pre_ping": settings.DB_POOL_PRE_PING,
    })
    logger.info(f"Using generic database engine for: {_db_url.split(':')[0]}")

# 创建数据库引擎
engine = create_engine(settings.database_url, **_engine_kwargs)


# Event listener to set statement_timeout on each new DBAPI connection (PostgreSQL only)
if _is_postgresql:
    @event.listens_for(engine, "connect")
    def set_statement_timeout(dbapi_connection, connection_record):
        """
        Set PostgreSQL statement_timeout on each new connection.
        This prevents any single query from running longer than QUERY_TIMEOUT seconds.
        """
        cursor = dbapi_connection.cursor()
        # 使用参数化查询防止 SQL 注入（即使 timeout 来自配置）
        cursor.execute("SET statement_timeout = %s", (QUERY_TIMEOUT_MS,))
        cursor.close()
        logger.debug(f"Set statement_timeout to {QUERY_TIMEOUT_MS}ms on new connection")


_DB_QUERY_DURATIONS_PER_REQUEST_MAXLEN = 200
DB_SLOW_QUERY_THRESHOLD_MS = 200.0
_DB_STATEMENT_MAX_CHARS = 400
_DB_SQL_WHITESPACE_RE = re.compile(r"\s+")


@dataclass
class DbSlowQuerySample:
    fingerprint: str
    statement: str
    duration_ms: float
    timestamp: float


@dataclass
class DbRequestMetrics:
    db_total_time_ms: float = 0.0
    db_query_count: int = 0
    query_durations_ms: list[float] = field(default_factory=list)
    slow_queries: list[DbSlowQuerySample] = field(default_factory=list)


_DB_REQUEST_METRICS: ContextVar[Optional[DbRequestMetrics]] = ContextVar(
    "db_request_metrics",
    default=None,
)


def start_db_request_metrics() -> Token[Optional[DbRequestMetrics]]:
    """
    为单个请求启动 DB metrics 收集。

    说明：
    - 通过 ContextVar 将“当前请求”信息传递给 SQLAlchemy engine event listener。
    - 若没有调用该函数（例如后台任务/脚本），DB 查询计时仍可工作，但不会计入 Admin metrics。
    """

    return _DB_REQUEST_METRICS.set(DbRequestMetrics())


def finish_db_request_metrics(token: Token[Optional[DbRequestMetrics]]) -> Optional[DbRequestMetrics]:
    """
    结束 DB metrics 收集并恢复上层 ContextVar。
    """

    metrics = _DB_REQUEST_METRICS.get()
    _DB_REQUEST_METRICS.reset(token)
    return metrics


def _normalize_sql_statement(statement: str) -> str:
    raw = str(statement or "").strip()
    if not raw:
        return ""

    normalized = _DB_SQL_WHITESPACE_RE.sub(" ", raw)
    if len(normalized) > _DB_STATEMENT_MAX_CHARS:
        return normalized[:_DB_STATEMENT_MAX_CHARS] + "…"
    return normalized


def _fingerprint_sql_statement(statement: str) -> str:
    normalized = _normalize_sql_statement(statement)
    if not normalized:
        return "empty"
    digest = hashlib.sha256(normalized.encode("utf-8", "replace")).hexdigest()
    return digest[:12]


def record_db_query_duration_ms(duration_ms: float, statement: str) -> None:
    """
    记录一次 DB 查询耗时（毫秒），写入当前请求的 DbRequestMetrics。

    说明：
    - 该函数既可被 SQLAlchemy event listener 调用，也可用于单元测试中模拟 DB 查询耗时。
    - 该指标属于“可观测性”，不得影响主查询链路；内部异常会被吞掉。
    """

    try:
        metrics = _DB_REQUEST_METRICS.get()
        if metrics is None:
            return

        ms = max(0.0, float(duration_ms))
        metrics.db_total_time_ms += ms
        metrics.db_query_count += 1

        if len(metrics.query_durations_ms) < _DB_QUERY_DURATIONS_PER_REQUEST_MAXLEN:
            metrics.query_durations_ms.append(ms)

        if DB_SLOW_QUERY_THRESHOLD_MS > 0 and ms >= DB_SLOW_QUERY_THRESHOLD_MS:
            normalized = _normalize_sql_statement(statement)
            fingerprint = _fingerprint_sql_statement(normalized)
            metrics.slow_queries.append(
                DbSlowQuerySample(
                    fingerprint=fingerprint,
                    statement=normalized,
                    duration_ms=ms,
                    timestamp=time.time(),
                )
            )
    except Exception:  # pragma: no cover
        return


@event.listens_for(engine, "before_cursor_execute")
def _db_metrics_before_cursor_execute(conn, cursor, statement, parameters, context, executemany):
    # NOTE: 必须极轻量；不允许抛异常影响查询执行
    try:
        context._db_metrics_start = time.perf_counter()
    except Exception:  # pragma: no cover
        return


@event.listens_for(engine, "after_cursor_execute")
def _db_metrics_after_cursor_execute(conn, cursor, statement, parameters, context, executemany):
    # NOTE: 必须极轻量；不允许抛异常影响查询执行
    try:
        start = getattr(context, "_db_metrics_start", None)
        if start is None:
            return
        duration_ms = (time.perf_counter() - start) * 1000.0
        record_db_query_duration_ms(duration_ms, str(statement))
    except Exception:  # pragma: no cover
        return


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
        safe_error = sanitize_for_log(e, max_length=2000)
        safe_url = settings.safe_database_url if not _is_sqlite else _db_url
        # SECURITY: 避免在生产日志中输出潜在包含凭据的 traceback / DSN
        # 仅在开发环境输出完整堆栈，生产环境输出脱敏后的摘要信息。
        if settings.is_production:
            logger.error(
                "Database connection failed (%s): %s (url=%s)",
                type(e).__name__,
                safe_error,
                safe_url,
            )
        else:
            logger.error(
                "Database connection failed (%s): %s (url=%s)",
                type(e).__name__,
                safe_error,
                safe_url,
                exc_info=True,
            )
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
            # 使用参数化查询防止 SQL 注入
            db.execute(text("SET statement_timeout = :timeout"), {"timeout": timeout_ms})
            yield db
        finally:
            # Reset to default timeout
            db.execute(text("SET statement_timeout = :timeout"), {"timeout": QUERY_TIMEOUT_MS})
    else:
        # Non-PostgreSQL: timeout not supported, just yield the session
        yield db
