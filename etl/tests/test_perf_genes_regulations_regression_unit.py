import json
import os
import subprocess
import sys
import threading
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from typing import Any
from urllib.parse import parse_qs, urlparse


def _start_mock_server(state: dict[str, Any]) -> ThreadingHTTPServer:
    class Handler(BaseHTTPRequestHandler):
        def do_GET(self) -> None:  # noqa: N802
            parsed = urlparse(self.path)

            if parsed.path == "/api/v1/genes":
                qs = parse_qs(parsed.query)
                if "page" not in qs or "page_size" not in qs:
                    self.send_response(400)
                    self.end_headers()
                    self.wfile.write(b"missing paging\n")
                    return
                self.send_response(200)
                self.send_header("Content-Type", "application/json")
                self.end_headers()
                self.wfile.write(b'{"ok":true}\n')
                return

            if parsed.path == "/api/v1/regulations":
                qs = parse_qs(parsed.query)
                if "page" not in qs or "page_size" not in qs:
                    self.send_response(400)
                    self.end_headers()
                    self.wfile.write(b"missing paging\n")
                    return
                self.send_response(200)
                self.send_header("Content-Type", "application/json")
                self.end_headers()
                self.wfile.write(b'{"ok":true}\n')
                return

            if parsed.path == "/api/v1/admin/metrics":
                payload = state.get("metrics_payload")
                if not isinstance(payload, dict):
                    self.send_response(500)
                    self.end_headers()
                    self.wfile.write(b"missing metrics_payload\n")
                    return
                self.send_response(200)
                self.send_header("Content-Type", "application/json")
                self.end_headers()
                self.wfile.write((json.dumps(payload) + "\n").encode("utf-8"))
                return

            self.send_response(404)
            self.end_headers()
            self.wfile.write(b"not found\n")

        def log_message(self, fmt: str, *args: Any) -> None:  # noqa: A003
            return

    server = ThreadingHTTPServer(("127.0.0.1", 0), Handler)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    return server


def _run_script(repo_root: Path, env: dict[str, str], *args: str) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        [sys.executable, "scripts/perf_genes_regulations_regression.py", *args],
        cwd=repo_root,
        env=env,
        capture_output=True,
        text=True,
        timeout=30,
        check=False,
    )


def _base_metrics_payload(*, response_p95: float, response_p99: float, db_p95: float, db_p99: float) -> dict[str, Any]:
    return {
        "request": {"total": 100},
        "errors": {"total": 0},
        "endpoints": [
            {
                "path": "/api/v1/genes",
                "requests": 20,
                "percentiles": {"p95_ms": response_p95, "p99_ms": response_p99},
                "db_percentiles": {"p95_ms": db_p95, "p99_ms": db_p99},
            },
            {
                "path": "/api/v1/regulations",
                "requests": 20,
                "percentiles": {"p95_ms": response_p95, "p99_ms": response_p99},
                "db_percentiles": {"p95_ms": db_p95, "p99_ms": db_p99},
            },
        ],
    }


def test_perf_genes_regulations_generate_baseline_and_check_passes(tmp_path: Path) -> None:
    repo_root = Path(__file__).resolve().parents[2]

    state: dict[str, Any] = {
        "metrics_payload": _base_metrics_payload(response_p95=1000.0, response_p99=1200.0, db_p95=200.0, db_p99=250.0),
    }
    server = _start_mock_server(state)
    try:
        port = server.server_address[1]
        base_url = f"http://127.0.0.1:{port}"

        env = os.environ.copy()

        # Simulate global proxy enabled but no explicit bypass configured.
        env["http_proxy"] = "http://127.0.0.1:1"
        env["https_proxy"] = "http://127.0.0.1:1"
        env.pop("NO_PROXY", None)
        env.pop("no_proxy", None)

        baseline_file = tmp_path / "baseline.json"
        out_dir = tmp_path / "out"

        gen = _run_script(
            repo_root,
            env,
            "generate-baseline",
            "--base-url",
            base_url,
            "--baseline-file",
            str(baseline_file),
            "--out-dir",
            str(out_dir),
            "--warmup-rounds",
            "2",
            "--timeout-seconds",
            "1",
        )
        output = f"{gen.stdout}\n{gen.stderr}"
        assert gen.returncode == 0, f"generate-baseline failed:\n{output}"
        assert baseline_file.exists(), f"baseline file not created. Output:\n{output}"
        assert list(out_dir.glob("perf-genes-regulations-*.md")), f"missing markdown report. Output:\n{output}"

        chk = _run_script(
            repo_root,
            env,
            "check",
            "--base-url",
            base_url,
            "--baseline-file",
            str(baseline_file),
            "--out-dir",
            str(out_dir),
            "--warmup-rounds",
            "2",
            "--timeout-seconds",
            "1",
        )
        output = f"{chk.stdout}\n{chk.stderr}"
        assert chk.returncode == 0, f"check should pass:\n{output}"
    finally:
        server.shutdown()


def test_perf_genes_regulations_check_fails_on_large_regression(tmp_path: Path) -> None:
    repo_root = Path(__file__).resolve().parents[2]

    state: dict[str, Any] = {
        "metrics_payload": _base_metrics_payload(response_p95=1000.0, response_p99=1200.0, db_p95=200.0, db_p99=250.0),
    }
    server = _start_mock_server(state)
    try:
        port = server.server_address[1]
        base_url = f"http://127.0.0.1:{port}"

        env = os.environ.copy()
        env.pop("NO_PROXY", None)
        env.pop("no_proxy", None)

        baseline_file = tmp_path / "baseline.json"
        out_dir = tmp_path / "out"

        gen = _run_script(
            repo_root,
            env,
            "generate-baseline",
            "--base-url",
            base_url,
            "--baseline-file",
            str(baseline_file),
            "--out-dir",
            str(out_dir),
            "--warmup-rounds",
            "1",
            "--timeout-seconds",
            "1",
        )
        output = f"{gen.stdout}\n{gen.stderr}"
        assert gen.returncode == 0, f"generate-baseline failed:\n{output}"

        # Simulate a clear regression that exceeds both pct and abs thresholds.
        state["metrics_payload"] = _base_metrics_payload(response_p95=2000.0, response_p99=2400.0, db_p95=500.0, db_p99=650.0)

        chk = _run_script(
            repo_root,
            env,
            "check",
            "--base-url",
            base_url,
            "--baseline-file",
            str(baseline_file),
            "--out-dir",
            str(out_dir),
            "--warmup-rounds",
            "1",
            "--timeout-seconds",
            "1",
        )
        output = f"{chk.stdout}\n{chk.stderr}"
        assert chk.returncode != 0, f"check should fail on regression:\n{output}"
        assert "REGRESSION" in output
    finally:
        server.shutdown()

