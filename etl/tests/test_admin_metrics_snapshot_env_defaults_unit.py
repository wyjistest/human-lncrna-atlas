import os
import subprocess
import sys
import threading
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path


def test_admin_metrics_snapshot_uses_env_defaults_and_bypasses_proxy(tmp_path: Path) -> None:
    repo_root = Path(__file__).resolve().parents[2]
    expected_key = "test-admin-key"

    class Handler(BaseHTTPRequestHandler):
        def do_GET(self) -> None:  # noqa: N802
            if self.path != "/api/v1/admin/metrics":
                self.send_response(404)
                self.end_headers()
                return

            if self.headers.get("X-Admin-API-Key") != expected_key:
                self.send_response(403)
                self.end_headers()
                self.wfile.write(b"forbidden\n")
                return

            self.send_response(200)
            self.send_header("Content-Type", "application/json")
            self.end_headers()
            self.wfile.write(
                (
                    '{"request":{"total":0},"errors":{},"response_time":{},"percentiles":{},'
                    '"endpoints":[],"cache_stats":{},"cache_breakdown":{},'
                    '"cache_get_latency":{},"database":{}}\n'
                ).encode("utf-8")
            )

        def log_message(self, format: str, *args: object) -> None:  # noqa: A002
            return

    server = ThreadingHTTPServer(("127.0.0.1", 0), Handler)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()

    try:
        port = server.server_address[1]
        base_url = f"http://127.0.0.1:{port}"

        env = os.environ.copy()
        env["API_BASE_URL"] = base_url
        env["ADMIN_API_KEY"] = expected_key

        # Simulate global proxy enabled but no explicit bypass configured.
        env["http_proxy"] = "http://127.0.0.1:1"
        env["https_proxy"] = "http://127.0.0.1:1"
        env.pop("NO_PROXY", None)
        env.pop("no_proxy", None)

        result = subprocess.run(
            [
                sys.executable,
                "scripts/admin_metrics_snapshot.py",
                "--out-dir",
                str(tmp_path),
                "--prefix",
                "admin-metrics-test",
                "--timeout-seconds",
                "1",
            ],
            cwd=repo_root,
            env=env,
            capture_output=True,
            text=True,
            timeout=20,
            check=False,
        )

        output = f"{result.stdout}\n{result.stderr}"
        assert result.returncode == 0, f"stdout/stderr:\n{output}"
        assert list(tmp_path.glob("admin-metrics-test-*.json")), f"No JSON exported. Output:\n{output}"
        assert list(tmp_path.glob("admin-metrics-test-*.md")), f"No Markdown exported. Output:\n{output}"
    finally:
        server.shutdown()

