#!/usr/bin/env python3
"""
Docs 标题伪影检查：

- 仅扫描 git 跟踪的 Markdown 文件（避免把本地生成/忽略文件当作仓库内容）。
- 防止把带“行号前缀”的标题误提交，例如：
  - "# 1:# 标题"
  - "## 12:## 子标题"

这类内容通常来自把带行号的输出（如 `nl -ba`）误粘贴进文档。
"""

from __future__ import annotations

import argparse
import re
import subprocess
import sys
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[1]
HEADING_ARTIFACT_RE = re.compile(r"^#+\\s+\\d+:\\s*#+\\s")


def _git_ls_files(paths: list[str]) -> list[Path]:
    cmd = ["git", "ls-files", "--"] + paths
    result = subprocess.run(cmd, check=False, capture_output=True, text=True, cwd=str(REPO_ROOT))
    if result.returncode != 0:
        message = "Failed to list tracked files via git."
        if result.stderr:
            message = f"{message}\\n{result.stderr.strip()}"
        raise RuntimeError(message)
    return [REPO_ROOT / line for line in result.stdout.splitlines() if line.endswith(".md")]


def main() -> int:
    parser = argparse.ArgumentParser(description="Check docs for heading artifacts like '# 1:# ...'.")
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
        print("Docs heading artifact check: no tracked markdown files found (skipped).")
        return 0

    offenders: list[str] = []
    scanned = 0

    for path in files:
        try:
            text = path.read_text(encoding="utf-8")
        except FileNotFoundError:
            continue
        except UnicodeDecodeError:
            text = path.read_text(encoding="utf-8", errors="ignore")
        scanned += 1

        for line_no, line in enumerate(text.splitlines(), start=1):
            if HEADING_ARTIFACT_RE.match(line):
                try:
                    rel = path.relative_to(REPO_ROOT)
                except ValueError:
                    rel = path
                offenders.append(f"{rel}:{line_no}: {line.strip()}")
                break

    if offenders:
        print("Docs heading artifact check FAILED.")
        print("Detected headings with line-number artifacts (e.g. '# 1:# ...').")
        print("")
        print("Files:")
        for entry in sorted(offenders):
            print(f"- {entry}")
        return 1

    print(f"Docs heading artifact check passed ({scanned} markdown files scanned).")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

