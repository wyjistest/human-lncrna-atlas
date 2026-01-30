#!/usr/bin/env bash
set -euo pipefail

# 目的：
# - 验证 `scripts/check_docs_status_markers.py` 在任意子目录执行时也能正常工作（不会因相对路径而崩溃）。
# - 验证失败输出包含 `file:line` 与触发指示（便于定位与回滚）。
#
# 说明：
# - 测试会在临时目录里创建一个最小 git 仓库，并只提交两份 markdown（CURRENT_STATUS + bad doc）。
# - 通过在 bad doc 中引入 TODO/marker 来覆盖 fail/pass 两种路径。

REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"

tmp_root="$(mktemp -d)"
cleanup() {
  if [ -n "${tmp_root:-}" ] && [ -d "${tmp_root:-}" ] && [ "${tmp_root:-}" != "/" ]; then
    rm -rf "$tmp_root"
  fi
}
trap cleanup EXIT

if [ -z "${tmp_root:-}" ] || [ ! -d "$tmp_root" ]; then
  echo "failed to create tmp dir via mktemp" >&2
  exit 1
fi

case "$tmp_root" in
  "$REPO_ROOT" | "$REPO_ROOT"/*)
    echo "refusing to run tests with tmp_root inside repo: $tmp_root" >&2
    exit 1
    ;;
esac

mkdir -p "$tmp_root/scripts" "$tmp_root/docs"

cp "$REPO_ROOT/scripts/check_docs_status_markers.py" "$tmp_root/scripts/check_docs_status_markers.py"

cat > "$tmp_root/docs/CURRENT_STATUS.md" <<'EOF'
# Current Status

TODO: this is intentionally present and should be exempt.
EOF

cat > "$tmp_root/docs/bad.md" <<'EOF'
# Bad Doc
Some intro
TODO: missing marker should fail
EOF

git -C "$tmp_root" init -q
git -C "$tmp_root" config user.email "test@example.com"
git -C "$tmp_root" config user.name "Test"
git -C "$tmp_root" add scripts/check_docs_status_markers.py docs/CURRENT_STATUS.md docs/bad.md
git -C "$tmp_root" commit -qm "init"

set +e
out="$(cd "$tmp_root" && python3 scripts/check_docs_status_markers.py 2>&1)"
status=$?
set -e

if [ "$status" -eq 0 ]; then
  echo "expected docs status marker check to fail when marker is missing" >&2
  exit 1
fi

echo "$out" | grep -F "docs/bad.md:3:" >/dev/null || {
  echo "expected failure output to include file:line for offender" >&2
  echo "$out" >&2
  exit 1
}

echo "$out" | grep -F "indicator: TODO" >/dev/null || {
  echo "expected failure output to include indicator label" >&2
  echo "$out" >&2
  exit 1
}

# Fix the doc by adding the required marker.
cat > "$tmp_root/docs/bad.md" <<'EOF'
# Bad Doc
Some intro
TODO: now has marker
See docs/CURRENT_STATUS.md for up-to-date status.
EOF

(cd "$tmp_root" && python3 scripts/check_docs_status_markers.py >/dev/null)

# Regression check: running from a subdirectory should work (historically would crash).
subdir_out="$(cd "$tmp_root/scripts" && python3 check_docs_status_markers.py 2>&1)"
echo "$subdir_out" | grep -F "markdown files scanned" >/dev/null || {
  echo "expected script to scan markdown files even when executed from a subdirectory" >&2
  echo "$subdir_out" >&2
  exit 1
}

echo "OK: docs status marker check works from repo root and subdirectories"
