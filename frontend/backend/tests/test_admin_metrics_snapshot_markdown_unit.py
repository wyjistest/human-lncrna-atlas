import importlib.util
from pathlib import Path

import pytest


def _load_admin_metrics_snapshot_module():
    repo_root = Path(__file__).resolve().parents[3]
    script_path = repo_root / "scripts" / "admin_metrics_snapshot.py"

    spec = importlib.util.spec_from_file_location("admin_metrics_snapshot", script_path)
    assert spec is not None
    assert spec.loader is not None

    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


@pytest.mark.unit
def test_admin_metrics_snapshot_uses_hit_rate_pct():
    snapshot = _load_admin_metrics_snapshot_module()

    metrics = {
        "request": {"total": 123, "last_minute": 5},
        "errors": {"total": 0, "rate": 0.0},
        "response_time": {"avg_ms": 12.3},
        "percentiles": {"p50_ms": 10.0, "p95_ms": 20.0, "p99_ms": 30.0},
        "cache_stats": {"hit_rate_pct": 12.34, "hits": 1, "misses": 2},
        "endpoints": [],
        "database": {},
    }

    md = snapshot.build_markdown(
        metrics,
        base_url="http://localhost:8000",
        fetched_at="2026-01-22T00-00-00Z",
    )

    assert "- **hit rate**：12.34%" in md
