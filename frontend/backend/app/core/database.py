"""
数据库连接管理
"""
from sqlalchemy import create_engine, text
from sqlalchemy.orm import sessionmaker, declarative_base
from sqlalchemy.pool import QueuePool

from .config import settings

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
)

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
    print("✅ 数据库连接已关闭")
