"""
日志配置

Phase 9.16: 添加日志轮转支持
参考: Codex 代码审查 - FileHandler 无 rotation 可能导致磁盘占满
"""
import logging
import os
import sys
from logging.handlers import TimedRotatingFileHandler
from pathlib import Path

# 日志目录
# 默认写入 backend 目录下的 logs/，避免使用 /tmp 这类公共临时目录引入的潜在覆盖/劫持风险
# Phase 9.17: 延迟目录创建到 setup_logging()，在只读环境优雅降级为 stdout
_BACKEND_DIR = Path(__file__).resolve().parent.parent.parent
LOG_DIR = Path(os.getenv("LOG_DIR", str(_BACKEND_DIR / "logs")))

# 日志轮转配置（可通过环境变量覆盖）
# LOG_ROTATION_WHEN: 轮转时间单位 (S=秒, M=分钟, H=小时, D=天, midnight=午夜)
# LOG_ROTATION_INTERVAL: 轮转间隔
# LOG_ROTATION_BACKUP_COUNT: 保留的备份文件数量
LOG_ROTATION_WHEN = os.getenv("LOG_ROTATION_WHEN", "midnight")
LOG_ROTATION_INTERVAL = int(os.getenv("LOG_ROTATION_INTERVAL", "1"))
LOG_ROTATION_BACKUP_COUNT = int(os.getenv("LOG_ROTATION_BACKUP_COUNT", "30"))

# 是否输出到文件（生产环境可能使用 stdout + 平台收集）
LOG_TO_FILE = os.getenv("LOG_TO_FILE", "true").lower() == "true"


def setup_logging(log_level: str = "INFO"):
    """
    配置日志系统

    日志策略:
    - 始终输出到 stdout（便于容器/平台收集）
    - 可选输出到文件（带轮转），通过 LOG_TO_FILE=true 启用

    环境变量:
    - LOG_DIR: 日志目录（默认 backend/logs/）
    - LOG_TO_FILE: 是否输出到文件（默认 true）
    - LOG_ROTATION_WHEN: 轮转时间单位（默认 midnight）
    - LOG_ROTATION_INTERVAL: 轮转间隔（默认 1）
    - LOG_ROTATION_BACKUP_COUNT: 保留备份数（默认 30 天）

    Phase 9.17: 优雅降级 - 如果无法创建日志目录，自动降级为仅 stdout 输出
    """

    # 日志格式
    log_format = "%(asctime)s - %(name)s - %(levelname)s - %(message)s"
    date_format = "%Y-%m-%d %H:%M:%S"

    handlers = [
        # 控制台输出（始终启用）
        logging.StreamHandler(sys.stdout),
    ]

    # Phase 9.17: 延迟创建日志目录，优雅处理只读文件系统
    file_logging_enabled = LOG_TO_FILE
    if file_logging_enabled:
        try:
            LOG_DIR.mkdir(parents=True, exist_ok=True)
        except (PermissionError, OSError) as e:
            # 只读文件系统或权限受限 - 降级为仅 stdout
            file_logging_enabled = False
            print(
                f"WARNING: Cannot create log directory {LOG_DIR}: {e}. "
                "Falling back to stdout-only logging.",
                file=sys.stderr
            )

    # 文件输出（可选，带轮转）
    # Phase 9.17: 也捕获 handler 初始化失败（目录存在但文件不可写等情况）
    if file_logging_enabled:
        try:
            file_handler = TimedRotatingFileHandler(
                filename=LOG_DIR / "api.log",
                when=LOG_ROTATION_WHEN,
                interval=LOG_ROTATION_INTERVAL,
                backupCount=LOG_ROTATION_BACKUP_COUNT,
                encoding="utf-8",
            )
            file_handler.setFormatter(logging.Formatter(log_format, date_format))
            # 轮转后的文件名格式: api.log.2025-12-22
            file_handler.suffix = "%Y-%m-%d"
            handlers.append(file_handler)
        except (PermissionError, OSError) as e:
            # 文件不可写或其他 I/O 错误 - 降级为仅 stdout
            file_logging_enabled = False
            print(
                f"WARNING: Cannot create log file in {LOG_DIR}: {e}. "
                "Falling back to stdout-only logging.",
                file=sys.stderr
            )

    # 配置根日志
    logging.basicConfig(
        level=getattr(logging, log_level.upper()),
        format=log_format,
        datefmt=date_format,
        handlers=handlers,
    )

    # 配置API日志
    api_logger = logging.getLogger("api")
    api_logger.setLevel(logging.INFO)

    # 配置数据库日志（只记录警告和错误）
    logging.getLogger("sqlalchemy.engine").setLevel(logging.WARNING)

    # 日志启动信息
    if file_logging_enabled:
        api_logger.info(
            f"Log rotation enabled: when={LOG_ROTATION_WHEN}, "
            f"interval={LOG_ROTATION_INTERVAL}, backupCount={LOG_ROTATION_BACKUP_COUNT}"
        )

    return api_logger
