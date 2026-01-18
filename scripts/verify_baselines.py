#!/usr/bin/env python3
"""
verify_baselines.py

目的：
- 为仓库内“可提交的回归锚点（baselines）”提供一个统一的校验入口。

当前支持：
- API Snapshot Baseline：`docs/baselines/api-snapshot.sample.json`

用法：
  # 1) 校验一个已运行的后端（需要服务已启动）
  python3 scripts/verify_baselines.py --mode running --base-url http://localhost:8000

  # 2) 使用本地 PostgreSQL + 本地后端 venv 生成临时快照，再与 baseline 比对
  python3 scripts/verify_baselines.py --mode local

  # 3) 使用 Docker Compose 生成临时快照，再与 baseline 比对
  python3 scripts/verify_baselines.py --mode docker
"""

from __future__ import annotations

import argparse
import difflib
import json
import os
import subprocess
import sys
import tempfile
from pathlib import Path
from typing import Any


def _repo_root() -> Path:
    return Path(__file__).resolve().parents[1]


def _stable_json_text(obj: Any) -> str:
    return json.dumps(obj, ensure_ascii=False, indent=2, sort_keys=True) + "\n"


def _compare_json_files(expected: Path, actual: Path) -> int:
    expected_obj = json.loads(expected.read_text(encoding="utf-8"))
    actual_obj = json.loads(actual.read_text(encoding="utf-8"))
    if expected_obj == actual_obj:
        return 0

    diff = "".join(
        difflib.unified_diff(
            _stable_json_text(expected_obj).splitlines(True),
            _stable_json_text(actual_obj).splitlines(True),
            fromfile=str(expected),
            tofile=str(actual),
        )
    )
    print("ERROR: baseline mismatch", file=sys.stderr)
    if diff:
        sys.stderr.write(diff)
    return 3


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Verify repo baselines (API snapshot, etc.)")
    parser.add_argument(
        "--mode",
        choices=["running", "local", "docker"],
        default="running",
        help="Verify mode: running (backend already running) | local (local Postgres + venv) | docker (docker compose)",
    )
    parser.add_argument(
        "--base-url",
        default="http://localhost:8000",
        help="Backend base URL (running mode only)",
    )
    parser.add_argument(
        "--baseline-file",
        default="docs/baselines/api-snapshot.sample.json",
        help="Baseline JSON file path (default: docs/baselines/api-snapshot.sample.json)",
    )
    parser.add_argument(
        "--timeout",
        type=float,
        default=10.0,
        help="Per-request timeout seconds (running mode only; forwarded to api_snapshot.py)",
    )
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    repo_root = _repo_root()

    baseline_file = Path(args.baseline_file)
    if not baseline_file.is_absolute():
        baseline_file = repo_root / baseline_file

    if args.mode == "running":
        cmd = [
            sys.executable,
            str(repo_root / "scripts/api_snapshot.py"),
            "--base-url",
            args.base_url,
            "--timeout",
            str(args.timeout),
            "--check-baseline",
            str(baseline_file),
        ]
        return subprocess.run(cmd, cwd=str(repo_root), check=False).returncode

    if args.mode in {"local", "docker"}:
        generator = (
            repo_root / "scripts/baselines/generate_api_snapshot_baseline_local.sh"
            if args.mode == "local"
            else repo_root / "scripts/baselines/generate_api_snapshot_baseline.sh"
        )

        with tempfile.TemporaryDirectory(prefix="hla-baseline-verify-") as tmp:
            candidate = Path(tmp) / "api-snapshot.candidate.json"
            env = os.environ.copy()
            env["OUT_FILE"] = str(candidate)

            proc = subprocess.run(["bash", str(generator)], cwd=str(repo_root), env=env, check=False)
            if proc.returncode != 0:
                return proc.returncode

            return _compare_json_files(baseline_file, candidate)

    print(f"ERROR: unsupported mode: {args.mode}", file=sys.stderr)
    return 2


if __name__ == "__main__":
    raise SystemExit(main())

