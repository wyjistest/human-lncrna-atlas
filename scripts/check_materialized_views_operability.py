#!/usr/bin/env python3
"""
Materialized Views operability gate.

用途：
- 读取 Admin `/api/v1/admin/materialized-views/status`
- 或直接消费保存好的 status JSON
- 根据 `attention_summary.severity` 返回稳定退出码

退出码：
- 0: healthy / info
- 1: degraded / warning / unsupported
- 2: critical
- 3: I/O 或网络错误
"""

from __future__ import annotations

import argparse
import json
import os
import sys
from pathlib import Path
from typing import Any
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen


STATUS_ENDPOINT_PATH = "/api/v1/admin/materialized-views/status"


def _parse_args() -> argparse.Namespace:
    env_admin_api_key = (os.environ.get("ADMIN_API_KEY") or "").strip() or None
    parser = argparse.ArgumentParser(description="Check materialized views operability from Admin status JSON.")
    source_group = parser.add_mutually_exclusive_group(required=True)
    source_group.add_argument(
        "--backend-url",
        help="Backend base url (default endpoint appended: /api/v1/admin/materialized-views/status).",
    )
    source_group.add_argument(
        "--status-json",
        help="Path to a saved materialized-views status JSON payload.",
    )
    parser.add_argument(
        "--admin-api-key",
        default=env_admin_api_key,
        help="Admin API Key for backend requests (sent as X-Admin-API-Key; default: $ADMIN_API_KEY).",
    )
    parser.add_argument(
        "--timeout-seconds",
        type=float,
        default=10.0,
        help="HTTP timeout seconds for --backend-url (default: 10).",
    )
    return parser.parse_args()


def _normalize_backend_url(raw: str) -> str:
    base_url = (raw or "").strip().rstrip("/")
    if base_url.endswith(STATUS_ENDPOINT_PATH):
        return base_url[: -len(STATUS_ENDPOINT_PATH)]
    if base_url.endswith("/api/v1"):
        return base_url[: -len("/api/v1")]
    return base_url


def _load_status_json(path_str: str) -> dict[str, Any]:
    path = Path(path_str).expanduser()
    if not path.is_absolute():
        path = (Path.cwd() / path).resolve()
    with path.open("r", encoding="utf-8") as fh:
        return json.load(fh)


def _fetch_status_json(base_url: str, admin_api_key: str | None, timeout_seconds: float) -> dict[str, Any]:
    endpoint = f"{_normalize_backend_url(base_url)}{STATUS_ENDPOINT_PATH}"
    headers = {"Accept": "application/json"}
    if admin_api_key:
        headers["X-Admin-API-Key"] = admin_api_key
    request = Request(endpoint, headers=headers, method="GET")
    with urlopen(request, timeout=timeout_seconds) as response:  # noqa: S310
        return json.loads(response.read().decode("utf-8"))


def _derive_attention_summary(payload: dict[str, Any]) -> dict[str, Any]:
    summary = payload.get("attention_summary")
    if isinstance(summary, dict):
        return summary

    supported = payload.get("supported", True) is not False
    backend = str(payload.get("database_backend") or "unknown").strip() or "unknown"
    views = payload.get("views")
    if not isinstance(views, list):
        views = []

    if not supported:
        names = [str(view.get("name")) for view in views if isinstance(view, dict) and view.get("name")]
        return {
            "status": "degraded",
            "severity": "warning",
            "message": f"Materialized view operations are unavailable on {backend}.",
            "recommended_action": "Switch the admin backend to PostgreSQL to refresh or inspect materialized views.",
            "attention_count": len(names),
            "total_count": len(views),
            "attention_view_names": names,
        }

    attention_views = [
        view
        for view in views
        if isinstance(view, dict) and str(view.get("health_status") or "") != "healthy"
    ]
    severity = "info"
    if any(str(view.get("severity")) == "critical" for view in attention_views):
        severity = "critical"
    elif attention_views:
        severity = "warning"

    return {
        "status": "critical" if severity == "critical" else ("degraded" if attention_views else "healthy"),
        "severity": severity,
        "message": (
            f"{len(attention_views)}/{len(views)} materialized view(s) need attention."
            if attention_views
            else "All materialized views are healthy."
        ),
        "recommended_action": next(
            (
                str(view.get("recommended_action")).strip()
                for view in attention_views
                if isinstance(view.get("recommended_action"), str) and str(view.get("recommended_action")).strip()
            ),
            None,
        ),
        "attention_count": len(attention_views),
        "total_count": len(views),
        "attention_view_names": [
            str(view.get("name"))
            for view in attention_views
            if isinstance(view, dict) and view.get("name")
        ],
    }


def _exit_code_for_summary(summary: dict[str, Any]) -> int:
    severity = str(summary.get("severity") or "").strip().lower()
    if severity == "critical":
        return 2
    if severity == "warning":
        return 1
    return 0


def main() -> int:
    args = _parse_args()
    try:
        if args.status_json:
            payload = _load_status_json(args.status_json)
        else:
            payload = _fetch_status_json(str(args.backend_url or ""), args.admin_api_key, float(args.timeout_seconds))
    except FileNotFoundError as exc:
        print(f"[ERROR] status json not found: {exc.filename}", file=sys.stderr)
        return 3
    except json.JSONDecodeError as exc:
        print(f"[ERROR] invalid json: {exc}", file=sys.stderr)
        return 3
    except HTTPError as exc:
        print(f"[ERROR] backend returned HTTP {exc.code}: {exc.reason}", file=sys.stderr)
        return 3
    except URLError as exc:
        print(f"[ERROR] backend request failed: {exc.reason}", file=sys.stderr)
        return 3

    summary = _derive_attention_summary(payload)
    attention_count = int(summary.get("attention_count") or 0)
    total_count = int(summary.get("total_count") or 0)
    status = str(summary.get("status") or "unknown")
    severity = str(summary.get("severity") or "unknown")
    message = str(summary.get("message") or "").strip()
    recommended_action = str(summary.get("recommended_action") or "").strip()
    attention_names = summary.get("attention_view_names")
    if not isinstance(attention_names, list):
        attention_names = []

    print(f"status={status} severity={severity} attention={attention_count}/{total_count}")
    if message:
        print(message)
    if recommended_action:
        print(f"recommended_action={recommended_action}")
    if attention_names:
        print(f"attention_views={','.join(str(name) for name in attention_names)}")

    return _exit_code_for_summary(summary)


if __name__ == "__main__":
    raise SystemExit(main())
