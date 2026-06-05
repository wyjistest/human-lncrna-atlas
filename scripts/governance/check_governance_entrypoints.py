#!/usr/bin/env python3
"""
治理入口检查：

- docs/README.md 必须通过稳定指针引用 `docs/roadmaps/ROADMAP_CURRENT.md`，
  不能把“当前路线图”硬编码为某个日期快照文件。
- docs/CURRENT_STATUS.md 必须只承担当前事实与治理入口，不再承载漂移式 backlog checklist。
- docs/project.md 必须显式标记为历史索引快照，并把当前入口指向 docs/README.md。
- `.github/governance/backlog.yml` 必须满足最小 manifest 结构要求。

实现上尽量使用标准库，backlog 文件支持：
1) JSON（JSON 是 YAML 1.2 子集，可直接存成 `.yml`）；
2) 若本机装有 PyYAML，则也兼容普通 YAML。
"""

from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Any


REPO_ROOT = Path(__file__).resolve().parents[2]
DOCS_README = REPO_ROOT / "docs/README.md"
CURRENT_STATUS = REPO_ROOT / "docs/CURRENT_STATUS.md"
DOCS_PROJECT = REPO_ROOT / "docs/project.md"
ROADMAP_CURRENT = REPO_ROOT / "docs/roadmaps/ROADMAP_CURRENT.md"
BACKLOG_MANIFEST = REPO_ROOT / ".github/governance/backlog.yml"

ROADMAP_POINTER = "docs/roadmaps/ROADMAP_CURRENT.md"
BACKLOG_POINTER = ".github/governance/backlog.yml"
BACKLOG_AUTOMATION_POINTER = "docs/governance/BACKLOG_AUTOMATION.md"
PROJECT_HISTORY_MARKER = "历史索引快照"

DATED_ROADMAP_RE = re.compile(r"docs/ROADMAP_\d{4}-\d{2}-\d{2}\.md")


def _load_text(path: Path) -> str:
    try:
        return path.read_text(encoding="utf-8")
    except UnicodeDecodeError:
        return path.read_text(encoding="utf-8", errors="ignore")


def _find_line(text: str, needle: str) -> int | None:
    for idx, line in enumerate(text.splitlines(), start=1):
        if needle in line:
            return idx
    return None


def _append(offenders: list[str], path: Path, line_no: int | None, message: str) -> None:
    rel = path.relative_to(REPO_ROOT).as_posix()
    offenders.append(f"{rel}:{line_no or 1}: {message}")


def _parse_backlog_manifest(path: Path) -> dict[str, Any]:
    raw = _load_text(path).strip()
    if not raw:
        raise ValueError("backlog manifest is empty")

    try:
        data = json.loads(raw)
    except json.JSONDecodeError:
        try:
            import yaml  # type: ignore
        except Exception as exc:  # pragma: no cover - exercised via shell test
            raise ValueError(
                "backlog manifest is not JSON-compatible YAML, and PyYAML is unavailable"
            ) from exc
        data = yaml.safe_load(raw)

    if not isinstance(data, dict):
        raise ValueError("backlog manifest must decode to an object")
    return data


def _check_docs_readme(offenders: list[str]) -> None:
    text = _load_text(DOCS_README)
    if ROADMAP_POINTER not in text:
        _append(offenders, DOCS_README, 1, f"missing stable roadmap pointer `{ROADMAP_POINTER}`")
    for idx, line in enumerate(text.splitlines(), start=1):
        if DATED_ROADMAP_RE.search(line):
            _append(
                offenders,
                DOCS_README,
                idx,
                "dated roadmap link found in docs entrypoint; use ROADMAP_CURRENT pointer instead",
            )


def _check_current_status(offenders: list[str]) -> None:
    text = _load_text(CURRENT_STATUS)
    banned_heading = "## 🎯 建议的下一步开发"
    line_no = _find_line(text, banned_heading)
    if line_no is not None:
        _append(
            offenders,
            CURRENT_STATUS,
            line_no,
            "drift-prone next-development checklist heading still present",
        )
    if ROADMAP_POINTER not in text:
        _append(offenders, CURRENT_STATUS, 1, f"missing roadmap pointer `{ROADMAP_POINTER}`")
    if BACKLOG_POINTER not in text:
        _append(offenders, CURRENT_STATUS, 1, f"missing backlog pointer `{BACKLOG_POINTER}`")
    if BACKLOG_AUTOMATION_POINTER not in text:
        _append(
            offenders,
            CURRENT_STATUS,
            1,
            f"missing backlog automation pointer `{BACKLOG_AUTOMATION_POINTER}`",
        )


def _check_docs_project(offenders: list[str]) -> None:
    text = _load_text(DOCS_PROJECT)
    history_line = _find_line(text, PROJECT_HISTORY_MARKER)
    if history_line is None:
        _append(
            offenders,
            DOCS_PROJECT,
            1,
            f"missing historical marker `{PROJECT_HISTORY_MARKER}`",
        )
    if "docs/README.md" not in text:
        _append(offenders, DOCS_PROJECT, 1, "missing pointer to `docs/README.md`")


def _check_roadmap_pointer_exists(offenders: list[str]) -> None:
    if not ROADMAP_CURRENT.exists():
        _append(offenders, ROADMAP_CURRENT, 1, "missing roadmap pointer document")


def _check_backlog_manifest(offenders: list[str]) -> None:
    if not BACKLOG_MANIFEST.exists():
        _append(offenders, BACKLOG_MANIFEST, 1, "missing backlog manifest")
        return

    try:
        data = _parse_backlog_manifest(BACKLOG_MANIFEST)
    except ValueError as exc:
        _append(offenders, BACKLOG_MANIFEST, 1, str(exc))
        return

    items = data.get("items")
    if not isinstance(items, list) or not items:
        _append(offenders, BACKLOG_MANIFEST, 1, "manifest must contain a non-empty `items` list")
        return

    seen_ids: set[str] = set()
    for idx, item in enumerate(items, start=1):
        base_line = 1 + idx
        if not isinstance(item, dict):
            _append(offenders, BACKLOG_MANIFEST, base_line, "each backlog item must be an object")
            continue

        for field in ("id", "title", "labels", "acceptance_criteria"):
            if field not in item:
                _append(offenders, BACKLOG_MANIFEST, base_line, f"item missing required field `{field}`")

        item_id = item.get("id")
        if isinstance(item_id, str) and item_id:
            if item_id in seen_ids:
                _append(offenders, BACKLOG_MANIFEST, base_line, f"duplicate backlog id `{item_id}`")
            seen_ids.add(item_id)
        else:
            _append(offenders, BACKLOG_MANIFEST, base_line, "item `id` must be a non-empty string")

        labels = item.get("labels")
        if not isinstance(labels, list) or not labels or any(not isinstance(label, str) or not label for label in labels):
            _append(offenders, BACKLOG_MANIFEST, base_line, "`labels` must be a non-empty string list")

        criteria = item.get("acceptance_criteria")
        if (
            not isinstance(criteria, list)
            or not criteria
            or any(not isinstance(entry, str) or not entry for entry in criteria)
        ):
            _append(
                offenders,
                BACKLOG_MANIFEST,
                base_line,
                "`acceptance_criteria` must be a non-empty string list",
            )

        state = item.get("state")
        if state not in {"open", "closed"}:
            _append(offenders, BACKLOG_MANIFEST, base_line, "`state` must be `open` or `closed`")


def main() -> int:
    offenders: list[str] = []
    _check_docs_readme(offenders)
    _check_current_status(offenders)
    _check_docs_project(offenders)
    _check_roadmap_pointer_exists(offenders)
    _check_backlog_manifest(offenders)

    if offenders:
        print("Governance entrypoint check FAILED.")
        print("Files:")
        for offender in offenders:
            print(f"- {offender}")
        return 1

    print("Governance entrypoint check passed.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
