import builtins
import importlib
import sys

import pytest


pytestmark = pytest.mark.unit


def test_cache_module_imports_without_redis(monkeypatch):
    """
    Regression test:
    app.core.cache 支持 redis 依赖缺失时的降级路径（避免 NameError / 导入崩溃）。
    """
    real_import = builtins.__import__

    def fake_import(name, *args, **kwargs):  # type: ignore[no-untyped-def]
        if name == "redis" or name.startswith("redis."):
            raise ImportError("Simulated missing redis")
        return real_import(name, *args, **kwargs)

    monkeypatch.setattr(builtins, "__import__", fake_import)

    # 强制重新导入模块以触发 try/except ImportError 分支
    sys.modules.pop("app.core.cache", None)

    try:
        module = importlib.import_module("app.core.cache")
        assert hasattr(module, "CacheService")
    finally:
        # 避免影响其他测试：移除降级导入的模块，让后续用例按正常依赖环境重新导入
        sys.modules.pop("app.core.cache", None)


def test_admin_system_metrics_degrades_without_psutil(monkeypatch):
    """
    Regression test:
    当 psutil 不可用时，Admin 系统指标接口应返回可用的降级数据而不是崩溃。
    """
    from app.routers import admin as admin_router

    monkeypatch.setattr(admin_router, "psutil", None)

    metrics = admin_router.get_system_metrics()
    assert metrics.cpu_percent == 0.0
    assert metrics.memory.total_mb >= 0
    assert metrics.disk.total_gb >= 0
    assert metrics.process.memory_mb >= 0
