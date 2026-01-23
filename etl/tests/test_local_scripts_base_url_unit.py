import os
import subprocess
import sys
import threading
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

import pytest


@pytest.mark.skipif(sys.platform.startswith("win"), reason="Bash scripts are not supported on Windows")
def test_run_tests_status_respects_base_url_env(tmp_path: Path) -> None:
    repo_root = Path(__file__).resolve().parents[2]

    class OkHandler(BaseHTTPRequestHandler):
        def do_GET(self) -> None:  # noqa: N802
            self.send_response(200)
            self.end_headers()
            self.wfile.write(b"ok\n")

        def log_message(self, format: str, *args: object) -> None:  # noqa: A002
            return

    def start_server() -> ThreadingHTTPServer:
        server = ThreadingHTTPServer(("127.0.0.1", 0), OkHandler)
        thread = threading.Thread(target=server.serve_forever, daemon=True)
        thread.start()
        return server

    backend = start_server()
    frontend = start_server()

    try:
        backend_port = backend.server_address[1]
        frontend_port = frontend.server_address[1]

        env = os.environ.copy()
        env["API_BASE_URL"] = f"http://127.0.0.1:{backend_port}"
        env["BASE_URL"] = f"http://127.0.0.1:{frontend_port}"

        result = subprocess.run(
            ["bash", "scripts/run-tests.sh", "status"],
            cwd=repo_root,
            env=env,
            capture_output=True,
            text=True,
            timeout=20,
            check=False,
        )

        output = f"{result.stdout}\n{result.stderr}"
        assert result.returncode == 0, f"stdout/stderr:\n{output}"
        assert str(backend_port) in output, f"Expected backend port {backend_port} in output:\n{output}"
        assert str(frontend_port) in output, f"Expected frontend port {frontend_port} in output:\n{output}"
    finally:
        frontend.shutdown()
        backend.shutdown()
