#!/usr/bin/env bash
set -euo pipefail

# 目的：
# - 验证治理入口检查脚本会阻止 docs 入口继续硬编码日期路线图/漂移式 backlog。
# - 验证在修正入口文档与 backlog manifest 后，脚本从 repo root 和子目录执行都能通过。

unset GIT_DIR GIT_WORK_TREE

REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"

tmp_root="$(mktemp -d)"
cleanup() {
  if [ -n "${tmp_root:-}" ] && [ -d "${tmp_root:-}" ] && [ "${tmp_root:-}" != "/" ]; then
    rm -rf "$tmp_root"
  fi
}
trap cleanup EXIT

mkdir -p "$tmp_root/docs/roadmaps" "$tmp_root/.github/governance" "$tmp_root/scripts/governance"
cp "$REPO_ROOT/scripts/governance/check_governance_entrypoints.py" "$tmp_root/scripts/governance/check_governance_entrypoints.py"

cat > "$tmp_root/docs/README.md" <<'EOF'
# Docs

1. 当前状态：`docs/CURRENT_STATUS.md`
2. 1–2 周路线图：`docs/ROADMAP_2026-02-03.md`
EOF

cat > "$tmp_root/docs/CURRENT_STATUS.md" <<'EOF'
# Current Status

## 🎯 建议的下一步开发
- [x] 已完成但仍留在此处
EOF

cat > "$tmp_root/docs/project.md" <<'EOF'
# Project Index
EOF

cat > "$tmp_root/docs/roadmaps/ROADMAP_CURRENT.md" <<'EOF'
# Pointer
EOF

cat > "$tmp_root/.github/governance/backlog.yml" <<'EOF'
{"version":1,"default_milestone":"Current Roadmap","items":[{"id":"bad-only"}]}
EOF

(
  cd "$tmp_root"
  git init -q
  git config user.name "ci"
  git config user.email "ci@example.invalid"
  git add .
  git commit -q -m "test: init"
)

set +e
bad_out="$(cd "$tmp_root" && python3 scripts/governance/check_governance_entrypoints.py 2>&1)"
bad_code=$?
set -e

if [ "$bad_code" -eq 0 ]; then
  echo "expected governance check to fail for bad entrypoints" >&2
  exit 1
fi

echo "$bad_out" | grep -F "docs/README.md" >/dev/null || {
  echo "expected docs/README.md offender in governance check output" >&2
  echo "$bad_out" >&2
  exit 1
}
echo "$bad_out" | grep -F "docs/CURRENT_STATUS.md" >/dev/null || {
  echo "expected CURRENT_STATUS offender in governance check output" >&2
  echo "$bad_out" >&2
  exit 1
}
echo "$bad_out" | grep -F ".github/governance/backlog.yml" >/dev/null || {
  echo "expected backlog manifest offender in governance check output" >&2
  echo "$bad_out" >&2
  exit 1
}

cat > "$tmp_root/docs/README.md" <<'EOF'
# 文档导航

1. 当前状态：`docs/CURRENT_STATUS.md`
2. 当前路线图：`docs/roadmaps/ROADMAP_CURRENT.md`
EOF

cat > "$tmp_root/docs/CURRENT_STATUS.md" <<'EOF'
# Current Status

当前事实以本页为准。

- 当前路线图：`docs/roadmaps/ROADMAP_CURRENT.md`
- backlog 源：`.github/governance/backlog.yml`
EOF

cat > "$tmp_root/docs/project.md" <<'EOF'
# Human LncRNA Atlas 文档索引

> 说明：本页为历史索引快照。当前入口请看 `docs/README.md`。
EOF

cat > "$tmp_root/.github/governance/backlog.yml" <<'EOF'
{
  "version": 1,
  "default_milestone": "Current Roadmap",
  "items": [
    {
      "id": "docs-roadmap-current-pointer",
      "title": "docs: stabilize current roadmap pointer",
      "summary": "summary",
      "labels": ["documentation", "kind:governance"],
      "milestone": "Current Roadmap",
      "priority": "p1",
      "state": "open",
      "body_sections": [{"heading": "Background", "body": "body"}],
      "acceptance_criteria": ["one", "two"]
    }
  ]
}
EOF

set +e
missing_doc_out="$(cd "$tmp_root" && python3 scripts/governance/check_governance_entrypoints.py 2>&1)"
missing_doc_code=$?
set -e

if [ "$missing_doc_code" -eq 0 ]; then
  echo "expected governance check to fail when CURRENT_STATUS misses automation doc pointer" >&2
  exit 1
fi

echo "$missing_doc_out" | grep -F "docs/CURRENT_STATUS.md" >/dev/null || {
  echo "expected CURRENT_STATUS offender when automation doc pointer is missing" >&2
  echo "$missing_doc_out" >&2
  exit 1
}

cat > "$tmp_root/docs/CURRENT_STATUS.md" <<'EOF'
# Current Status

当前事实以本页为准。

- 当前路线图：`docs/roadmaps/ROADMAP_CURRENT.md`
- backlog 源：`.github/governance/backlog.yml`
- backlog 自动化说明：`docs/governance/BACKLOG_AUTOMATION.md`
EOF

(cd "$tmp_root" && git add . && git commit -q -m "test: fix")
(cd "$tmp_root" && python3 scripts/governance/check_governance_entrypoints.py >/dev/null)

subdir_out="$(cd "$tmp_root/scripts" && python3 governance/check_governance_entrypoints.py 2>&1)"
echo "$subdir_out" | grep -F "Governance entrypoint check passed." >/dev/null || {
  echo "expected governance check to pass from subdirectory" >&2
  echo "$subdir_out" >&2
  exit 1
}

echo "OK: governance entrypoint check fails on drift and passes after fixes"
