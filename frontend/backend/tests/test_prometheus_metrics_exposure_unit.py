import os
import subprocess
import sys
from pathlib import Path

import pytest


BACKEND_DIR = Path(__file__).resolve().parents[1]


def _run_route_probe(enable_metrics: str | None) -> subprocess.CompletedProcess[str]:
    env = os.environ.copy()
    env["ENV"] = "test"
    env["SECURITY_ALLOW_INSECURE"] = "true"
    if enable_metrics is None:
        env.pop("ENABLE_METRICS", None)
    else:
        env["ENABLE_METRICS"] = enable_metrics

    code = """
from main import PROMETHEUS_AVAILABLE, app

paths = {getattr(route, "path", None) for route in app.routes}
if PROMETHEUS_AVAILABLE:
    print("/metrics" in paths)
else:
    print("prometheus-unavailable")
"""
    return subprocess.run(
        [sys.executable, "-c", code],
        cwd=BACKEND_DIR,
        env=env,
        text=True,
        capture_output=True,
        timeout=20,
        check=False,
    )


def _probe_value(result: subprocess.CompletedProcess[str]) -> str:
    lines = [line.strip() for line in result.stdout.splitlines() if line.strip()]
    return lines[-1] if lines else ""


@pytest.mark.unit
def test_prometheus_metrics_route_is_not_registered_when_disabled():
    result = _run_route_probe(enable_metrics=None)

    assert result.returncode == 0, result.stderr or result.stdout
    assert _probe_value(result) in {"False", "prometheus-unavailable"}


@pytest.mark.unit
def test_prometheus_metrics_route_is_registered_when_enabled():
    result = _run_route_probe(enable_metrics="true")

    assert result.returncode == 0, result.stderr or result.stdout
    assert _probe_value(result) in {"True", "prometheus-unavailable"}
