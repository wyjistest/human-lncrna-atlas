"""
日志配置
"""
import logging
import os
import sys
from pathlib import Path

# 日志目录
# 默认写入 backend 目录下的 logs/，避免使用 /tmp 这类公共临时目录引入的潜在覆盖/劫持风险
_BACKEND_DIR = Path(__file__).resolve().parent.parent.parent
LOG_DIR = Path(os.getenv("LOG_DIR", str(_BACKEND_DIR / "logs")))
LOG_DIR.mkdir(parents=True, exist_ok=True)


def setup_logging(log_level: str = "INFO"):
    """配置日志系统"""

    # 日志格式
    log_format = "%(asctime)s - %(name)s - %(levelname)s - %(message)s"
    date_format = "%Y-%m-%d %H:%M:%S"

    # 配置根日志
    logging.basicConfig(
        level=getattr(logging, log_level.upper()),
        format=log_format,
        datefmt=date_format,
        handlers=[
            # 控制台输出
            logging.StreamHandler(sys.stdout),
            # 文件输出
            logging.FileHandler(LOG_DIR / "api.log"),
        ],
    )

    # 配置API日志
    api_logger = logging.getLogger("api")
    api_logger.setLevel(logging.INFO)

    # 配置数据库日志（只记录警告和错误）
    logging.getLogger("sqlalchemy.engine").setLevel(logging.WARNING)

    return api_logger
