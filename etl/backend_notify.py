"""
ETL 结束后通知后端刷新缓存（可选）
================================

设计目标：
- ETL/脚本导入完成后，可选触发后端 Admin API：
  1) 重置 MV 可用性缓存（避免继续走 fallback）
  2) 按命名空间失效业务缓存（避免 TTL 窗口内读到旧数据）
- 默认关闭；失败不影响主流程（best-effort）。

启用方式（环境变量）：
- HLA_NOTIFY_BACKEND=true
- HLA_BACKEND_URL=http://localhost:8000               # 可选
- HLA_ADMIN_API_KEY=... 或 ADMIN_API_KEY=...          # 必需
- HLA_INVALIDATE_CACHE=true|false                     # 默认 true
- HLA_INVALIDATE_NAMESPACES=regulations,genes,stats   # 可选（默认所有白名单）
- HLA_RESET_MV_CACHE=true|false                       # 默认 true
- HLA_NOTIFY_TIMEOUT_SECONDS=10                       # 可选
"""

from __future__ import annotations

import json
import logging
import os
from dataclasses import dataclass
from typing import Iterable, Optional
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen

logger = logging.getLogger(__name__)


def _env_bool(name: str, default: bool) -> bool:
    raw = os.getenv(name)
    if raw is None:
        return default
    value = raw.strip().lower()
    return value in {"1", "true", "yes", "y", "on"}


def _env_int(name: str, default: int) -> int:
    raw = os.getenv(name)
    if raw is None:
        return default
    try:
        return int(raw.strip())
    except ValueError:
        return default


def _split_csv(value: str) -> list[str]:
    return [part.strip() for part in value.split(",") if part.strip()]


@dataclass(frozen=True)
class BackendNotifyConfig:
    enabled: bool
    backend_url: str
    admin_api_key: str
    invalidate_cache: bool
    invalidate_namespaces: list[str]
    reset_mv_cache: bool
    timeout_seconds: int


DEFAULT_INVALIDATE_NAMESPACES: list[str] = [
    # Must match backend allowlist in frontend/backend/app/routers/admin.py
    "regulations",
    "genes",
    "stats",
    "export",
    "conservation",
    "chipseq",
    "network",
    "diseases",
    "features",
    "igv",
    "analysis",
    "visualization",
]


def load_config_from_env(*, enabled_default: bool = False) -> BackendNotifyConfig:
    enabled = _env_bool("HLA_NOTIFY_BACKEND", enabled_default)
    backend_url = (os.getenv("HLA_BACKEND_URL") or os.getenv("BACKEND_URL") or "http://localhost:8000").rstrip("/")
    admin_api_key = os.getenv("HLA_ADMIN_API_KEY") or os.getenv("ADMIN_API_KEY") or ""

    invalidate_cache = _env_bool("HLA_INVALIDATE_CACHE", True)
    reset_mv_cache = _env_bool("HLA_RESET_MV_CACHE", True)
    timeout_seconds = max(1, _env_int("HLA_NOTIFY_TIMEOUT_SECONDS", 10))

    namespaces_raw = os.getenv("HLA_INVALIDATE_NAMESPACES")
    invalidate_namespaces = _split_csv(namespaces_raw) if namespaces_raw else list(DEFAULT_INVALIDATE_NAMESPACES)

    return BackendNotifyConfig(
        enabled=enabled,
        backend_url=backend_url,
        admin_api_key=admin_api_key,
        invalidate_cache=invalidate_cache,
        invalidate_namespaces=invalidate_namespaces,
        reset_mv_cache=reset_mv_cache,
        timeout_seconds=timeout_seconds,
    )


def _post_json(*, url: str, admin_api_key: str, payload: Optional[dict], timeout_seconds: int) -> None:
    data = b""
    headers = {"X-Admin-API-Key": admin_api_key}
    if payload is not None:
        data = json.dumps(payload).encode("utf-8")
        headers["Content-Type"] = "application/json"

    req = Request(url, data=data, headers=headers, method="POST")
    with urlopen(req, timeout=timeout_seconds) as resp:  # nosec B310 - controlled target URL, best-effort
        # Consume response to ensure request completes; keep logs minimal.
        resp.read()


def notify_backend_best_effort(
    *,
    reason: str,
    config: Optional[BackendNotifyConfig] = None,
    invalidate_namespaces: Optional[Iterable[str]] = None,
) -> None:
    """
    Best-effort 后端通知：失败不抛出异常。

    Args:
        reason: 日志用标识（例如导入脚本名）
        config: 可显式传入配置；默认从环境变量读取
        invalidate_namespaces: 覆盖失效命名空间（不传则用 config）
    """
    cfg = config or load_config_from_env(enabled_default=False)
    if not cfg.enabled:
        return

    if not cfg.admin_api_key:
        logger.warning("[%s] HLA_NOTIFY_BACKEND=true but ADMIN_API_KEY/HLA_ADMIN_API_KEY is empty; skip notify", reason)
        return

    base = cfg.backend_url.rstrip("/")

    try:
        if cfg.reset_mv_cache:
            _post_json(
                url=f"{base}/api/v1/admin/mv-cache/reset",
                admin_api_key=cfg.admin_api_key,
                payload={},
                timeout_seconds=cfg.timeout_seconds,
            )
            logger.info("[%s] Admin notified: mv-cache/reset", reason)
    except (HTTPError, URLError, TimeoutError, ValueError) as e:
        logger.warning("[%s] Admin notify failed (mv-cache/reset): %s", reason, str(e)[:200])

    if not cfg.invalidate_cache:
        return

    namespaces = list(invalidate_namespaces) if invalidate_namespaces is not None else list(cfg.invalidate_namespaces)
    for ns in namespaces:
        if not ns:
            continue
        try:
            _post_json(
                url=f"{base}/api/v1/admin/cache/invalidate/{ns}",
                admin_api_key=cfg.admin_api_key,
                payload=None,
                timeout_seconds=cfg.timeout_seconds,
            )
            logger.info("[%s] Cache invalidated: %s", reason, ns)
        except (HTTPError, URLError, TimeoutError, ValueError) as e:
            logger.warning("[%s] Cache invalidate failed (%s): %s", reason, ns, str(e)[:200])
