#!/usr/bin/env python3
"""
Docs 状态标注检查：

- 仅扫描 git 跟踪的 Markdown 文件（避免把本地生成/忽略文件当作仓库内容）。
- 若文档包含“Mock/未实现/待实现/TODO/checkbox”等容易被误读为当前待办的信号，
  则必须包含 `docs/CURRENT_STATUS.md` 引用，用于指向真实现状。
"""

from __future__ import annotations

import argparse
import re
import subprocess
import sys
from pathlib import Path


REQUIRED_MARKER = "docs/CURRENT_STATUS.md"
EXEMPT_FILES: set[Path] = {Path(REQUIRED_MARKER)}

INDICATOR_PATTERNS: tuple[re.Pattern[str], ...] = (
    re.compile(r"\bTODO\b", re.IGNORECASE),
    re.compile(r"\[ \]"),
    re.compile(r"\bmock\b", re.IGNORECASE),
    re.compile(r"\bstub\b", re.IGNORECASE),
    re.compile("未实现"),
    re.compile("待实现"),
)


def _git_ls_files(paths: list[str]) -> list[Path]:
    cmd = ["git", "ls-files", "--"] + paths
    result = subprocess.run(cmd, check=False, capture_output=True, text=True)
    if result.returncode != 0:
        message = "Failed to list tracked files via git."
        if result.stderr:
            message = f"{message}\n{result.stderr.strip()}"
        raise RuntimeError(message)
    return [Path(line) for line in result.stdout.splitlines() if line.endswith(".md")]


def _needs_marker(text: str) -> bool:
    return any(pattern.search(text) for pattern in INDICATOR_PATTERNS)


def main() -> int:
    parser = argparse.ArgumentParser(description="Check docs have CURRENT_STATUS marker when needed.")
    parser.add_argument(
        "--paths",
        nargs="*",
        default=["docs"],
        help="Directories to scan (git-tracked markdown files only).",
    )
    args = parser.parse_args()

    try:
        files = _git_ls_files(args.paths)
    except RuntimeError as exc:
        print(str(exc), file=sys.stderr)
        return 2
    if not files:
        print("Docs status marker check: no tracked markdown files found (skipped).")
        return 0

    offenders: list[str] = []
    scanned = 0

    for path in files:
        if path in EXEMPT_FILES:
            continue
        try:
            text = path.read_text(encoding="utf-8")
        except UnicodeDecodeError:
            text = path.read_text(encoding="utf-8", errors="ignore")
        scanned += 1

        if not _needs_marker(text):
            continue
        if REQUIRED_MARKER not in text:
            offenders.append(str(path))

    if offenders:
        print("Docs status marker check FAILED.")
        print(f"Marker required when doc contains indicators, but missing: `{REQUIRED_MARKER}`")
        print("")
        print("Files:")
        for path in sorted(offenders):
            print(f"- {path}")
        return 1

    print(f"Docs status marker check passed ({scanned} markdown files scanned).")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
