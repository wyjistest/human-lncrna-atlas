#!/usr/bin/env python3
from __future__ import annotations

import importlib.util
import sys
import tempfile
import unittest
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[2]
MODULE_PATH = REPO_ROOT / "scripts/governance/sync_backlog_issues.py"

spec = importlib.util.spec_from_file_location("sync_backlog_issues", MODULE_PATH)
module = importlib.util.module_from_spec(spec)
assert spec is not None and spec.loader is not None
sys.modules[spec.name] = module
spec.loader.exec_module(module)


class FakeGitHubClient:
    def __init__(self) -> None:
        self.labels: list[dict[str, object]] = [{"name": "documentation"}]
        self.milestones: list[dict[str, object]] = []
        self.issues: list[dict[str, object]] = []
        self.next_issue_number = 1
        self.next_milestone_number = 1

    def list_labels(self):
        return list(self.labels)

    def create_label(self, *, name: str, color: str, description: str):
        created = {"name": name, "color": color, "description": description}
        self.labels.append(created)
        return created

    def list_milestones(self):
        return list(self.milestones)

    def create_milestone(self, title: str):
        created = {"number": self.next_milestone_number, "title": title, "state": "open"}
        self.next_milestone_number += 1
        self.milestones.append(created)
        return created

    def list_issues(self):
        return list(self.issues)

    def create_issue(self, payload):
        created = {
            "number": self.next_issue_number,
            "state": "open",
            "title": payload["title"],
            "body": payload["body"],
            "labels": [{"name": name} for name in payload.get("labels", [])],
            "milestone": (
                next((m for m in self.milestones if m["number"] == payload["milestone"]), None)
                if "milestone" in payload
                else None
            ),
        }
        self.next_issue_number += 1
        self.issues.append(created)
        return created

    def update_issue(self, number: int, payload):
        issue = next(issue for issue in self.issues if issue["number"] == number)
        if "title" in payload:
            issue["title"] = payload["title"]
        if "body" in payload:
            issue["body"] = payload["body"]
        if "state" in payload:
            issue["state"] = payload["state"]
        if "labels" in payload:
            issue["labels"] = [{"name": name} for name in payload["labels"]]
        if "milestone" in payload:
            issue["milestone"] = next((m for m in self.milestones if m["number"] == payload["milestone"]), None)
        return issue


def sample_manifest(*, state: str = "open", title: str = "docs: stabilize roadmap pointer"):
    return {
        "version": 1,
        "default_milestone": "Current Roadmap",
        "items": [
            {
                "id": "docs-roadmap-current-pointer",
                "title": title,
                "summary": "summary",
                "labels": ["documentation", "kind:governance", "priority:p1"],
                "milestone": "Current Roadmap",
                "priority": "p1",
                "state": state,
                "body_sections": [{"heading": "Background", "body": "body"}],
                "acceptance_criteria": ["one", "two"],
            }
        ],
    }


class SyncBacklogIssuesTests(unittest.TestCase):
    def test_load_manifest_accepts_json_compatible_yaml_file(self):
        with tempfile.TemporaryDirectory() as tmp_dir:
            manifest_path = Path(tmp_dir) / "backlog.yml"
            manifest_path.write_text('{"version":1,"items":[]}', encoding="utf-8")
            data = module._load_manifest(manifest_path)
        self.assertEqual(data["version"], 1)

    def test_sync_creates_issue_label_and_milestone(self):
        client = FakeGitHubClient()
        stats = module.sync_manifest(
            client,
            manifest=sample_manifest(),
            manifest_path=REPO_ROOT / ".github/governance/backlog.yml",
            dry_run=False,
        )

        self.assertEqual(stats.created, 1)
        self.assertIn("kind:governance", {label["name"] for label in client.labels})
        self.assertEqual(client.milestones[0]["title"], "Current Roadmap")
        self.assertEqual(client.issues[0]["title"], "docs: stabilize roadmap pointer")
        self.assertIn("backlog-id: docs-roadmap-current-pointer", client.issues[0]["body"])

    def test_sync_updates_existing_issue(self):
        client = FakeGitHubClient()
        client.create_milestone("Current Roadmap")
        client.issues.append(
            {
                "number": 1,
                "state": "open",
                "title": "old title",
                "body": "<!-- backlog-id: docs-roadmap-current-pointer -->\nold",
                "labels": [{"name": "documentation"}],
                "milestone": {"number": 1, "title": "Current Roadmap"},
            }
        )

        stats = module.sync_manifest(
            client,
            manifest=sample_manifest(title="new title"),
            manifest_path=REPO_ROOT / ".github/governance/backlog.yml",
            dry_run=False,
        )

        self.assertEqual(stats.updated, 1)
        self.assertEqual(client.issues[0]["title"], "new title")
        self.assertIn("Acceptance Criteria", client.issues[0]["body"])

    def test_sync_closes_stale_issue_not_in_manifest(self):
        client = FakeGitHubClient()
        client.issues.append(
            {
                "number": 1,
                "state": "open",
                "title": "stale",
                "body": "<!-- backlog-id: stale-item -->\nbody",
                "labels": [],
                "milestone": None,
            }
        )

        stats = module.sync_manifest(
            client,
            manifest={"version": 1, "default_milestone": "Current Roadmap", "items": []},
            manifest_path=REPO_ROOT / ".github/governance/backlog.yml",
            dry_run=False,
        )

        self.assertEqual(stats.closed, 1)
        self.assertEqual(client.issues[0]["state"], "closed")

    def test_sync_reopens_issue_when_manifest_state_is_open(self):
        client = FakeGitHubClient()
        client.create_milestone("Current Roadmap")
        client.issues.append(
            {
                "number": 1,
                "state": "closed",
                "title": "old title",
                "body": "<!-- backlog-id: docs-roadmap-current-pointer -->\nold",
                "labels": [{"name": "documentation"}],
                "milestone": {"number": 1, "title": "Current Roadmap"},
            }
        )

        stats = module.sync_manifest(
            client,
            manifest=sample_manifest(),
            manifest_path=REPO_ROOT / ".github/governance/backlog.yml",
            dry_run=False,
        )

        self.assertEqual(stats.reopened, 1)
        self.assertEqual(client.issues[0]["state"], "open")

    def test_sync_honors_dry_run_without_mutation(self):
        client = FakeGitHubClient()
        stats = module.sync_manifest(
            client,
            manifest=sample_manifest(),
            manifest_path=REPO_ROOT / ".github/governance/backlog.yml",
            dry_run=True,
        )

        self.assertEqual(stats.created, 1)
        self.assertEqual(client.issues, [])
        self.assertEqual(client.milestones, [])

    def test_sync_allows_manifest_items_without_optional_summary_and_priority(self):
        client = FakeGitHubClient()
        manifest = sample_manifest()
        item = manifest["items"][0]
        item.pop("summary")
        item.pop("priority")

        stats = module.sync_manifest(
            client,
            manifest=manifest,
            manifest_path=REPO_ROOT / ".github/governance/backlog.yml",
            dry_run=False,
        )

        self.assertEqual(stats.created, 1)
        self.assertNotIn("- Priority:", client.issues[0]["body"])
        self.assertIn("Acceptance Criteria", client.issues[0]["body"])


if __name__ == "__main__":
    unittest.main()
