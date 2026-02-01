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


REPO_ROOT = Path(__file__).resolve().parents[1]
REQUIRED_MARKER = "docs/CURRENT_STATUS.md"
EXEMPT_FILES: set[Path] = {REPO_ROOT / REQUIRED_MARKER}

DEFAULT_MAX_MARKER_LINE = 30

# 仅对“入口/用户向”文档强制 marker 必须在文档前 N 行出现（更容易被读到，减少误读为 backlog）。
# 其他目录仍只要求“出现即可”，避免对历史/内部规划文档造成不必要的侵入。
POSITION_REQUIRED_PREFIXES: tuple[str, ...] = (
    "docs/api/",
    "docs/backend/",
    "docs/frontend/",
    "docs/performance/",
    "docs/reports/",
    "docs/roadmaps/",
    "docs/sessions/",
)

POSITION_REQUIRED_FILES: set[Path] = {
    Path("docs/project.md"),
    Path("docs/PITFALLS.md"),
    Path("docs/LOCAL_CI_BOOTSTRAP.md"),
}

INDICATORS: tuple[tuple[re.Pattern[str], str], ...] = (
    (re.compile(r"\bTODO\b", re.IGNORECASE), "TODO"),
    (re.compile(r"\[ \]"), "checkbox"),
    (re.compile(r"\bmock\b", re.IGNORECASE), "mock"),
    (re.compile(r"\bstub\b", re.IGNORECASE), "stub"),
    (re.compile("未实现"), "未实现"),
    (re.compile("待实现"), "待实现"),
)


def _git_ls_files(paths: list[str]) -> list[Path]:
    cmd = ["git", "ls-files", "--"] + paths
    result = subprocess.run(cmd, check=False, capture_output=True, text=True, cwd=str(REPO_ROOT))
    if result.returncode != 0:
        message = "Failed to list tracked files via git."
        if result.stderr:
            message = f"{message}\n{result.stderr.strip()}"
        raise RuntimeError(message)
    return [REPO_ROOT / line for line in result.stdout.splitlines() if line.endswith(".md")]


def _needs_marker(text: str) -> bool:
    return _find_first_indicator(text) is not None


def _find_first_indicator(text: str) -> tuple[int, str] | None:
    for line_no, line in enumerate(text.splitlines(), start=1):
        for pattern, label in INDICATORS:
            if pattern.search(line):
                return line_no, label
    return None


def _find_marker_line(text: str) -> int | None:
    for line_no, line in enumerate(text.splitlines(), start=1):
        if REQUIRED_MARKER in line:
            return line_no
    return None


def _requires_marker_near_top(rel: Path) -> bool:
    rel_posix = rel.as_posix()
    if rel in POSITION_REQUIRED_FILES:
        return True
    return any(rel_posix.startswith(prefix) for prefix in POSITION_REQUIRED_PREFIXES)


def main() -> int:
    parser = argparse.ArgumentParser(description="Check docs have CURRENT_STATUS marker when needed.")
    parser.add_argument(
        "--paths",
        nargs="*",
        default=["docs"],
        help="Directories to scan (git-tracked markdown files only).",
    )
    parser.add_argument(
        "--max-marker-line",
        type=int,
        default=DEFAULT_MAX_MARKER_LINE,
        help="Require CURRENT_STATUS marker to appear within first N lines for entry docs (default: 30).",
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
        except FileNotFoundError:
            # 当你在工作区里删除了文件但尚未 staged/commit 时，`git ls-files` 可能仍会列出它。
            # 为了让该检查在重构期间依然可用，这里对“磁盘不存在”的文件做跳过处理。
            continue
        except UnicodeDecodeError:
            text = path.read_text(encoding="utf-8", errors="ignore")
        scanned += 1

        indicator = _find_first_indicator(text)
        if indicator is None:
            continue

        if REQUIRED_MARKER not in text:
            try:
                rel = path.relative_to(REPO_ROOT)
            except ValueError:
                rel = path
            line_no, label = indicator
            offenders.append(f"{rel}:{line_no}: missing marker: `{REQUIRED_MARKER}` (indicator: {label})")
            continue

        # Marker exists: for entry docs, require it to be within the first N lines for visibility.
        try:
            rel = path.relative_to(REPO_ROOT)
        except ValueError:
            rel = path
        if _requires_marker_near_top(rel):
            marker_line = _find_marker_line(text) or 0
            if marker_line > int(args.max_marker_line):
                _, label = indicator
                offenders.append(
                    f"{rel}:{marker_line}: marker too late: `{REQUIRED_MARKER}` "
                    f"(>{args.max_marker_line}; indicator: {label})"
                )

    if offenders:
        print("Docs status marker check FAILED.")
        print(f"Marker required when doc contains indicators: `{REQUIRED_MARKER}`")
        print(f"Entry docs must place the marker within first {int(args.max_marker_line)} line(s).")
        print("")
        print("Files:")
        for path in sorted(offenders):
            print(f"- {path}")
        return 1

    print(f"Docs status marker check passed ({scanned} markdown files scanned).")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
