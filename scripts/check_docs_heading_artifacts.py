#!/usr/bin/env python3
"""
文档标题伪影检查（fast fail）。

目的：
- 防止 Markdown 标题中混入不可见/难排查字符（如 NBSP、BOM、零宽字符），导致目录锚点、
  搜索或复制粘贴行为异常。
- 作为 CI 门禁的一部分：发现问题立即失败，并输出 file:line 便于定位与可回滚修复。

说明：
- 仅扫描 git 跟踪的 Markdown 文件（避免把本地生成/忽略文件当作仓库内容）。
- 排除规划类文档（docs/plans/**、plan/**），避免计划文件包含“坏例子/对比”导致误报。
- 只检查 fenced code block 之外的 ATX headings（`#` 到 `######` 且后跟空格）。
"""

from __future__ import annotations

import re
import subprocess
import sys
from dataclasses import dataclass
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[1]

HEADING_RE = re.compile(r"^#{1,6}\s+")
FENCE_RE = re.compile(r"^\s*([`~]{3,})")


@dataclass(frozen=True)
class Artifact:
    pattern: re.Pattern[str]
    name: str


ARTIFACTS: tuple[Artifact, ...] = (
    Artifact(re.compile("\uFEFF"), "BOM (U+FEFF)"),
    Artifact(re.compile("\u00A0"), "NBSP (U+00A0)"),
    Artifact(re.compile("[\u200B\u200C\u200D\u2060]"), "zero-width char"),
    Artifact(re.compile("\t"), "tab"),
)


def _git_ls_files(pattern: str) -> list[Path]:
    try:
        out = subprocess.check_output(
            ["git", "ls-files", pattern],
            cwd=str(REPO_ROOT),
            text=True,
            stderr=subprocess.DEVNULL,
        )
    except Exception:
        return []
    return [REPO_ROOT / line for line in out.splitlines() if line.strip()]


def iter_markdown_files() -> list[Path]:
    files = _git_ls_files("*.md")
    filtered: list[Path] = []
    for p in files:
        try:
            rel = p.relative_to(REPO_ROOT)
        except ValueError:
            continue

        rel_posix = rel.as_posix()
        if rel_posix.startswith("docs/plans/") or rel_posix.startswith("plan/"):
            continue

        if not p.is_file():
            continue

        filtered.append(p)

    return filtered


def _iter_heading_issues(path: Path) -> list[tuple[int, str]]:
    try:
        text = path.read_text(encoding="utf-8")
    except UnicodeDecodeError:
        text = path.read_text(encoding="utf-8", errors="ignore")

    issues: list[tuple[int, str]] = []

    in_fence = False
    fence_char = ""
    fence_len = 0

    for line_no, line in enumerate(text.splitlines(), start=1):
        fence_match = FENCE_RE.match(line)
        if fence_match:
            marker = fence_match.group(1)
            if not in_fence:
                in_fence = True
                fence_char = marker[0]
                fence_len = len(marker)
            elif marker[0] == fence_char and len(marker) >= fence_len:
                in_fence = False
                fence_char = ""
                fence_len = 0
            continue

        if in_fence:
            continue

        if not HEADING_RE.match(line):
            continue

        if line != line.rstrip(" "):
            issues.append((line_no, "heading has trailing spaces"))

        for artifact in ARTIFACTS:
            if artifact.pattern.search(line):
                issues.append((line_no, f"heading contains {artifact.name}"))
                break

    return issues


def main() -> int:
    bad: list[str] = []
    files = iter_markdown_files()
    if not files:
        print("No markdown files found via git ls-files; skip docs heading artifacts check.", file=sys.stderr)
        return 0

    for path in files:
        issues = _iter_heading_issues(path)
        if not issues:
            continue

        rel = path.relative_to(REPO_ROOT)
        for line_no, msg in issues:
            bad.append(f"{rel}:{line_no}: {msg}")

    if bad:
        print("Docs heading artifacts check failed:", file=sys.stderr)
        for item in bad:
            print(item, file=sys.stderr)
        return 1

    print(f"Docs heading artifacts check passed ({len(files)} markdown files).")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

