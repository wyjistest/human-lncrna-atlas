#!/usr/bin/env python3
"""
将仓库 backlog manifest 同步到 GitHub Issues。

设计目标：
- manifest 为唯一事实源；
- 使用稳定 `backlog-id` marker 做幂等同步；
- 自动补齐 labels / milestone；
- 标题、正文、labels、milestone、state 由同步脚本管理；
- comments 与历史关闭记录保持在 GitHub 上，不做额外改动。
"""

from __future__ import annotations

import argparse
import json
import os
import subprocess
import sys
import urllib.error
import urllib.parse
import urllib.request
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Iterable


REPO_ROOT = Path(__file__).resolve().parents[2]
DEFAULT_MANIFEST = REPO_ROOT / ".github/governance/backlog.yml"
BACKLOG_ID_PREFIX = "<!-- backlog-id: "
BACKLOG_ID_SUFFIX = " -->"

DEFAULT_LABEL_META: dict[str, dict[str, str]] = {
    "kind:governance": {"color": "5319E7", "description": "Repository governance automation"},
    "kind:backlog": {"color": "0052CC", "description": "Managed backlog item"},
    "track:docs-governance": {"color": "0E8A16", "description": "Docs and backlog governance"},
    "track:analysis": {"color": "1D76DB", "description": "Analysis workbench follow-up"},
    "track:research": {"color": "5319E7", "description": "Research evidence-chain follow-up"},
    "priority:p1": {"color": "B60205", "description": "Highest roadmap priority"},
    "priority:p2": {"color": "D93F0B", "description": "Secondary roadmap priority"},
}


@dataclass
class SyncStats:
    created: int = 0
    updated: int = 0
    closed: int = 0
    reopened: int = 0
    unchanged: int = 0


def _load_manifest(path: Path) -> dict[str, Any]:
    raw = path.read_text(encoding="utf-8").strip()
    if not raw:
        raise ValueError(f"manifest is empty: {path}")
    try:
        data = json.loads(raw)
    except json.JSONDecodeError:
        try:
            import yaml  # type: ignore
        except Exception as exc:
            raise ValueError(
                "manifest is not JSON-compatible YAML, and PyYAML is unavailable"
            ) from exc
        data = yaml.safe_load(raw)
    if not isinstance(data, dict):
        raise ValueError("manifest must decode to an object")
    return data


def _resolve_token() -> str:
    for env_name in ("GH_TOKEN", "GITHUB_TOKEN"):
        token = os.environ.get(env_name)
        if token:
            return token

    try:
        output = subprocess.check_output(["gh", "auth", "token"], text=True)
    except Exception as exc:  # pragma: no cover - exercised in integration only
        raise RuntimeError("missing GH_TOKEN/GITHUB_TOKEN and failed to read `gh auth token`") from exc

    token = output.strip()
    if not token:
        raise RuntimeError("received empty token from `gh auth token`")
    return token


class GitHubClient:
    def __init__(self, repo: str, token: str):
        self.repo = repo
        self.token = token
        self.base_url = f"https://api.github.com/repos/{repo}"

    def _request(
        self,
        method: str,
        path: str,
        *,
        query: dict[str, Any] | None = None,
        body: dict[str, Any] | None = None,
    ) -> Any:
        url = f"{self.base_url}{path}"
        if query:
            encoded = urllib.parse.urlencode(query, doseq=True)
            url = f"{url}?{encoded}"

        payload = None
        headers = {
            "Accept": "application/vnd.github+json",
            "Authorization": f"Bearer {self.token}",
            "User-Agent": "human-lncrna-atlas-governance-sync",
        }
        if body is not None:
            payload = json.dumps(body).encode("utf-8")
            headers["Content-Type"] = "application/json"

        request = urllib.request.Request(url, data=payload, method=method, headers=headers)
        try:
            with urllib.request.urlopen(request, timeout=30) as response:
                raw = response.read().decode("utf-8")
                if not raw:
                    return None
                return json.loads(raw)
        except urllib.error.HTTPError as exc:  # pragma: no cover - exercised in real API usage
            detail = exc.read().decode("utf-8", errors="ignore")
            raise RuntimeError(f"GitHub API {method} {path} failed: {exc.code} {detail}") from exc

    def paginate(self, path: str, *, query: dict[str, Any] | None = None) -> list[dict[str, Any]]:
        results: list[dict[str, Any]] = []
        page = 1
        while True:
            next_query = dict(query or {})
            next_query.setdefault("per_page", 100)
            next_query["page"] = page
            chunk = self._request("GET", path, query=next_query)
            if not isinstance(chunk, list):
                raise RuntimeError(f"Expected list response for {path}, got {type(chunk).__name__}")
            if not chunk:
                return results
            results.extend(chunk)
            if len(chunk) < int(next_query["per_page"]):
                return results
            page += 1

    def list_labels(self) -> list[dict[str, Any]]:
        return self.paginate("/labels")

    def create_label(self, *, name: str, color: str, description: str) -> dict[str, Any]:
        return self._request("POST", "/labels", body={"name": name, "color": color, "description": description})

    def list_milestones(self) -> list[dict[str, Any]]:
        return self.paginate("/milestones", query={"state": "all"})

    def create_milestone(self, title: str) -> dict[str, Any]:
        return self._request("POST", "/milestones", body={"title": title})

    def list_issues(self) -> list[dict[str, Any]]:
        issues = self.paginate("/issues", query={"state": "all"})
        return [issue for issue in issues if "pull_request" not in issue]

    def create_issue(self, payload: dict[str, Any]) -> dict[str, Any]:
        return self._request("POST", "/issues", body=payload)

    def update_issue(self, number: int, payload: dict[str, Any]) -> dict[str, Any]:
        return self._request("PATCH", f"/issues/{number}", body=payload)


def _extract_backlog_id(body: str | None) -> str | None:
    if not body:
        return None
    for line in body.splitlines():
        line = line.strip()
        if line.startswith(BACKLOG_ID_PREFIX) and line.endswith(BACKLOG_ID_SUFFIX):
            return line[len(BACKLOG_ID_PREFIX) : -len(BACKLOG_ID_SUFFIX)].strip()
    return None


def _render_issue_body(item: dict[str, Any], manifest_path: Path) -> str:
    summary = str(item.get("summary", "")).strip()
    priority = str(item.get("priority", "")).strip()
    state = str(item.get("state", "open")).strip() or "open"
    body_sections = item.get("body_sections")
    if not isinstance(body_sections, list):
        body_sections = []

    lines = [
        f"{BACKLOG_ID_PREFIX}{item['id']}{BACKLOG_ID_SUFFIX}",
        "<!-- managed-by: scripts/governance/sync_backlog_issues.py -->",
        "",
        f"来源：`{manifest_path.relative_to(REPO_ROOT).as_posix()}`",
    ]
    if summary:
        lines.extend(["", summary])

    lines.append("")
    if priority:
        lines.append(f"- Priority: `{priority}`")
    lines.append(f"- State: `{state}`")
    lines.append("")

    for section in body_sections:
        heading = str(section.get("heading", "")).strip()
        body = str(section.get("body", "")).strip()
        if not heading or not body:
            continue
        lines.extend([f"## {heading}", "", body, ""])

    lines.extend(["## Acceptance Criteria", ""])
    for criterion in item["acceptance_criteria"]:
        lines.append(f"- [ ] {criterion}")
    lines.append("")
    lines.append("> 注意：本 issue 由 backlog manifest 自动维护；标题、正文、labels、milestone、state 的手工修改可能会被后续同步覆盖。")
    lines.append("")
    return "\n".join(lines)


def _label_meta(name: str) -> dict[str, str]:
    if name in DEFAULT_LABEL_META:
        return DEFAULT_LABEL_META[name]
    return {"color": "C2E0C6", "description": "Managed backlog label"}


def _ensure_labels(client: Any, labels: Iterable[str], dry_run: bool) -> None:
    existing = {label["name"] for label in client.list_labels()}
    for name in sorted(set(labels)):
        if name in existing:
            continue
        meta = _label_meta(name)
        if dry_run:
            print(f"[dry-run] create label: {name}")
            existing.add(name)
            continue
        client.create_label(name=name, color=meta["color"], description=meta["description"])
        print(f"created label: {name}")
        existing.add(name)


def _ensure_milestone(client: Any, title: str, dry_run: bool) -> int:
    for milestone in client.list_milestones():
        if milestone.get("title") == title:
            return int(milestone["number"])

    if dry_run:
        print(f"[dry-run] create milestone: {title}")
        return -1

    milestone = client.create_milestone(title)
    print(f"created milestone: {title}")
    return int(milestone["number"])


def _normalize_labels(issue: dict[str, Any]) -> list[str]:
    names = [label["name"] for label in issue.get("labels", []) if isinstance(label, dict) and "name" in label]
    return sorted(set(names))


def sync_manifest(
    client: Any,
    *,
    manifest: dict[str, Any],
    manifest_path: Path,
    dry_run: bool,
) -> SyncStats:
    items = manifest.get("items", [])
    if not isinstance(items, list):
        raise ValueError("manifest `items` must be a list")

    all_labels = [label for item in items if isinstance(item, dict) for label in item.get("labels", [])]
    _ensure_labels(client, all_labels, dry_run)

    default_milestone = str(manifest.get("default_milestone", "Current Roadmap")).strip() or "Current Roadmap"
    milestone_cache: dict[str, int] = {}

    managed_issues: dict[str, dict[str, Any]] = {}
    duplicates: list[str] = []
    for issue in client.list_issues():
        backlog_id = _extract_backlog_id(issue.get("body"))
        if backlog_id is None:
            continue
        if backlog_id in managed_issues:
            duplicates.append(backlog_id)
            continue
        managed_issues[backlog_id] = issue
    if duplicates:
        raise RuntimeError(f"duplicate managed issues detected for backlog ids: {', '.join(sorted(set(duplicates)))}")

    stats = SyncStats()
    declared_ids: set[str] = set()

    for item in items:
        if not isinstance(item, dict):
            raise ValueError("each backlog item must be an object")
        backlog_id = str(item["id"])
        declared_ids.add(backlog_id)
        milestone_title = str(item.get("milestone") or default_milestone)
        milestone_number = milestone_cache.get(milestone_title)
        if milestone_number is None:
            milestone_number = _ensure_milestone(client, milestone_title, dry_run)
            milestone_cache[milestone_title] = milestone_number

        desired_body = _render_issue_body(item, manifest_path)
        desired_labels = sorted(set(str(label) for label in item.get("labels", [])))
        desired_state = str(item.get("state", "open"))
        existing = managed_issues.get(backlog_id)

        payload: dict[str, Any] = {
            "title": str(item["title"]),
            "body": desired_body,
            "labels": desired_labels,
        }
        if milestone_number > 0:
            payload["milestone"] = milestone_number

        if existing is None:
            if desired_state == "closed":
                print(f"skip closed-only manifest item without issue: {backlog_id}")
                stats.unchanged += 1
                continue
            if dry_run:
                print(f"[dry-run] create issue: {payload['title']}")
            else:
                client.create_issue(payload)
                print(f"created issue: {payload['title']}")
            stats.created += 1
            continue

        changed_payload: dict[str, Any] = {}
        if existing.get("title") != payload["title"]:
            changed_payload["title"] = payload["title"]
        if existing.get("body") != payload["body"]:
            changed_payload["body"] = payload["body"]
        if _normalize_labels(existing) != desired_labels:
            changed_payload["labels"] = desired_labels
        current_milestone = existing.get("milestone", {}) or {}
        current_milestone_number = current_milestone.get("number")
        if milestone_number > 0 and current_milestone_number != milestone_number:
            changed_payload["milestone"] = milestone_number
        if desired_state != existing.get("state"):
            changed_payload["state"] = desired_state

        if not changed_payload:
            print(f"unchanged: #{existing['number']} {payload['title']}")
            stats.unchanged += 1
            continue

        previous_state = existing.get("state")
        action = "reopen" if desired_state == "open" and existing.get("state") == "closed" else "update"
        if dry_run:
            print(f"[dry-run] {action} issue #{existing['number']}: {payload['title']}")
        else:
            client.update_issue(int(existing["number"]), changed_payload)
            past_tense = "reopened" if action == "reopen" else "updated"
            print(f"{past_tense} issue #{existing['number']}: {payload['title']}")

        if desired_state == "open" and previous_state == "closed":
            stats.reopened += 1
        elif desired_state == "closed" and previous_state == "open":
            stats.closed += 1
        else:
            stats.updated += 1

    stale_ids = sorted(set(managed_issues) - declared_ids)
    for backlog_id in stale_ids:
        issue = managed_issues[backlog_id]
        if issue.get("state") == "closed":
            print(f"stale issue already closed: #{issue['number']} {backlog_id}")
            stats.unchanged += 1
            continue
        if dry_run:
            print(f"[dry-run] close stale issue #{issue['number']}: {backlog_id}")
        else:
            client.update_issue(int(issue["number"]), {"state": "closed"})
            print(f"closed stale issue #{issue['number']}: {backlog_id}")
        stats.closed += 1

    return stats


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Sync backlog manifest to GitHub issues.")
    parser.add_argument("--repo", required=True, help="GitHub repository in owner/name format")
    parser.add_argument(
        "--manifest",
        default=str(DEFAULT_MANIFEST),
        help="Path to backlog manifest (default: .github/governance/backlog.yml)",
    )
    parser.add_argument("--dry-run", action="store_true", help="Show intended changes without calling write APIs")
    return parser.parse_args()


def main() -> int:
    args = _parse_args()
    manifest_path = Path(args.manifest)
    if not manifest_path.is_absolute():
        manifest_path = (REPO_ROOT / manifest_path).resolve()
    if not manifest_path.exists():
        print(f"manifest not found: {manifest_path}", file=sys.stderr)
        return 2

    try:
        manifest = _load_manifest(manifest_path)
        token = _resolve_token()
        client = GitHubClient(repo=args.repo, token=token)
        stats = sync_manifest(client, manifest=manifest, manifest_path=manifest_path, dry_run=args.dry_run)
    except Exception as exc:
        print(str(exc), file=sys.stderr)
        return 1

    summary = {
        "created": stats.created,
        "updated": stats.updated,
        "closed": stats.closed,
        "reopened": stats.reopened,
        "unchanged": stats.unchanged,
    }
    print(json.dumps(summary, ensure_ascii=True, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
