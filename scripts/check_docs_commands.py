#!/usr/bin/env python3
"""
文档命令漂移检查（fast fail）。

目的：
- 防止文档里出现容易导致新同学踩坑的启动命令漂移（例如 app.main:app / python -m uvicorn / poetry run uvicorn）。
- 作为 CI 门禁的一部分：发现问题立即失败，并输出 file:line 便于定位。
"""

from __future__ import annotations

import subprocess
import sys
from dataclasses import dataclass
from pathlib import Path
import re


REPO_ROOT = Path(__file__).resolve().parents[1]


@dataclass(frozen=True)
class Rule:
    pattern: re.Pattern[str]
    message: str


RULES: tuple[Rule, ...] = (
    Rule(
        pattern=re.compile(r"\bpoetry\s+run\s+uvicorn\b", re.IGNORECASE),
        message="文档中不建议使用 poetry 启动；请统一为 `python3 -m uvicorn main:app ...`。",
    ),
    Rule(
        pattern=re.compile(r"\bapp\.main:app\b"),
        message="后端入口为 `main:app`（repo: frontend/backend/main.py），不要写 `app.main:app`。",
    ),
    Rule(
        pattern=re.compile(r"\bpython\s+-m\s+uvicorn\b"),
        message="文档统一使用 `python3 -m uvicorn main:app ...`（避免 python 指向不确定）。",
    ),
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
    # 仅检查仓库内文件，避免把 git 子模块/外部路径带进来
    filtered: list[Path] = []
    for p in files:
        try:
            rel = p.relative_to(REPO_ROOT)
        except ValueError:
            continue

        # 规划类文档允许包含“坏例子/对比”，避免误报导致 CI 卡死在计划文件上。
        rel_posix = rel.as_posix()
        if rel_posix.startswith("docs/plans/") or rel_posix.startswith("plan/"):
            continue

        if not p.is_file():
            continue

        try:
            resolved = p.resolve()
        except Exception:
            continue

        if REPO_ROOT not in resolved.parents:
            continue

        filtered.append(p)

    return filtered


def main() -> int:
    bad: list[str] = []
    files = iter_markdown_files()
    if not files:
        print("No markdown files found via git ls-files; skip docs drift check.", file=sys.stderr)
        return 0

    for path in files:
        try:
            text = path.read_text(encoding="utf-8")
        except Exception as e:  # pragma: no cover
            bad.append(f"{path.relative_to(REPO_ROOT)}:0: 无法读取文件: {e}")
            continue

        rel = path.relative_to(REPO_ROOT)
        for line_no, line in enumerate(text.splitlines(), start=1):
            for rule in RULES:
                if rule.pattern.search(line):
                    bad.append(f"{rel}:{line_no}: {rule.message}")

    if bad:
        print("Docs command drift check failed:", file=sys.stderr)
        for item in bad:
            print(item, file=sys.stderr)
        return 1

    print(f"Docs command drift check passed ({len(files)} markdown files).")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
