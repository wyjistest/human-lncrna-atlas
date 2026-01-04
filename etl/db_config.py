"""
ETL 数据库连接配置辅助
====================

设计目标：
- 统一从环境变量读取数据库连接参数（DB_HOST/DB_PORT/DB_NAME/DB_USER/DB_PASSWORD）
- 允许脚本用命令行参数覆盖
- 当未提供密码时，移除 password 字段以便 psycopg2 使用 .pgpass / trust 认证
"""

from __future__ import annotations

import os
from typing import Any, Dict


def get_db_config_from_env() -> Dict[str, Any]:
    """
    从环境变量读取数据库配置（带安全默认值）。

    Returns:
        psycopg2.connect(**db_config) 可用的 dict
    """
    return {
        "host": os.environ.get("DB_HOST", "localhost"),
        "port": os.environ.get("DB_PORT", "5432"),
        "dbname": os.environ.get("DB_NAME", "lncrna_production"),
        "user": os.environ.get("DB_USER", ""),
        "password": os.environ.get("DB_PASSWORD", ""),
    }


def finalize_db_config(db_config: Dict[str, Any]) -> Dict[str, Any]:
    """
    规范化 db_config：
    - 当 password 为空时移除该键，允许 .pgpass 或 trust 认证生效
    """
    cfg = dict(db_config)
    if not cfg.get("password"):
        cfg.pop("password", None)
    return cfg

