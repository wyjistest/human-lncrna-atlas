import json
import subprocess
import sys
import threading
from contextlib import contextmanager
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from typing import Iterator
from urllib.parse import urlparse


@contextmanager
def _mock_backend_server() -> Iterator[tuple[str, dict[str, int]]]:
    counters: dict[str, int] = {"__total__": 0}

    def bump(path: str) -> None:
        counters["__total__"] = counters.get("__total__", 0) + 1
        counters[path] = counters.get(path, 0) + 1

    class Handler(BaseHTTPRequestHandler):
        def do_GET(self) -> None:  # noqa: N802 (BaseHTTPRequestHandler naming)
            parsed = urlparse(self.path)
            path = parsed.path
            bump(path)

            if path in {"/health", "/api/v1/stats/overview", "/api/v1/genes", "/api/v1/regulations"}:
                payload = {"ok": True}
            elif path == "/api/v1/admin/metrics":
                payload = {
                    "request": {"total": counters.get("__total__", 0), "last_minute": 0},
                    "errors": {"total": 0, "rate": 0.0},
                    "response_time": {"avg_ms": 1.0},
                    "percentiles": {},
                    "endpoints": [],
                    "cache_stats": {"hit_rate": "0%", "hits": 0, "misses": 0},
                    "cache_breakdown": {
                        "namespaces": {"top": []},
                        "keys": {
                            "top": [
                                {
                                    "key": "genes:list:species_id=1:page=1",
                                    "namespace": "genes:list",
                                    "requests": 10,
                                    "hits": 8,
                                    "misses": 2,
                                    "hit_rate_pct": 80.0,
                                }
                            ]
                        },
                    },
                    "cache_get_latency": {},
                    "database": {"slow_queries": []},
                }
            else:
                self.send_response(404)
                self.end_headers()
                return

            data = json.dumps(payload, ensure_ascii=False).encode("utf-8")
            self.send_response(200)
            self.send_header("Content-Type", "application/json; charset=utf-8")
            self.send_header("Content-Length", str(len(data)))
            self.end_headers()
            self.wfile.write(data)

        def log_message(self, format: str, *args) -> None:  # noqa: A002
            return

    server = ThreadingHTTPServer(("127.0.0.1", 0), Handler)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    try:
        host, port = server.server_address
        yield (f"http://{host}:{port}", counters)
    finally:
        server.shutdown()
        thread.join(timeout=5)


def test_admin_metrics_snapshot_warmup_rounds(tmp_path: Path) -> None:
    repo_root = Path(__file__).resolve().parents[2]

    with _mock_backend_server() as (base_url, counters):
        proc = subprocess.run(
            [
                sys.executable,
                str(repo_root / "scripts/admin_metrics_snapshot.py"),
                "--base-url",
                base_url,
                "--out-dir",
                str(tmp_path),
                "--prefix",
                "test-admin-metrics",
                "--warmup-rounds",
                "2",
            ],
            cwd=str(repo_root),
            capture_output=True,
            text=True,
            check=False,
        )

        assert proc.returncode == 0, proc.stderr
        assert counters.get("/health", 0) >= 1
        assert counters.get("/api/v1/stats/overview", 0) >= 1

        json_files = sorted(tmp_path.glob("test-admin-metrics-*.json"))
        md_files = sorted(tmp_path.glob("test-admin-metrics-*.md"))
        assert json_files, "expected JSON output file"
        assert md_files, "expected Markdown output file"

        exported = json.loads(json_files[0].read_text(encoding="utf-8"))
        assert (exported.get("request") or {}).get("total", 0) >= 1

        md = md_files[0].read_text(encoding="utf-8")
        assert "Cache keys（Top）" in md
        assert "genes:list:species_id=1:page=1" in md
