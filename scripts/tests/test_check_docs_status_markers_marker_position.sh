#!/usr/bin/env bash
set -euo pipefail

# 目的：
# - 验证“入口/用户向”文档（如 docs/api/**）在出现 TODO/checkbox/mock/stub 等信号时，
#   `docs/CURRENT_STATUS.md` marker 必须出现在文档前 N 行（默认 30），否则应失败。
#
# 说明：
# - 测试会在临时目录里创建一个最小 git 仓库，并提交 CURRENT_STATUS + entry doc。
# - 先构造“marker 太靠后”的失败用例，再修复为“marker 靠前”的通过用例。

unset GIT_DIR GIT_WORK_TREE

REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"

tmp_root="$(mktemp -d)"
cleanup() {
  if [ -n "${tmp_root:-}" ] && [ -d "${tmp_root:-}" ] && [ "${tmp_root:-}" != "/" ]; then
    rm -rf "$tmp_root"
  fi
}
trap cleanup EXIT

mkdir -p "$tmp_root/scripts" "$tmp_root/docs/api" "$tmp_root/docs"
cp "$REPO_ROOT/scripts/check_docs_status_markers.py" "$tmp_root/scripts/check_docs_status_markers.py"

cat > "$tmp_root/docs/CURRENT_STATUS.md" <<'EOF'
# Current Status
EOF

# marker 放在第 35 行（>30），且包含 TODO 信号，应失败。
{
  echo "# Entry Doc"
  echo ""
  echo "TODO: should require marker near top"
  for i in $(seq 1 30); do
    echo "filler line $i"
  done
  echo "See docs/CURRENT_STATUS.md for up-to-date status."
} > "$tmp_root/docs/api/entry.md"

git -C "$tmp_root" init -q
git -C "$tmp_root" config user.email "test@example.com"
git -C "$tmp_root" config user.name "Test"
git -C "$tmp_root" add scripts/check_docs_status_markers.py docs/CURRENT_STATUS.md docs/api/entry.md
git -C "$tmp_root" commit -qm "init"

set +e
out="$(cd "$tmp_root" && python3 scripts/check_docs_status_markers.py 2>&1)"
status=$?
set -e

if [ "$status" -eq 0 ]; then
  echo "expected docs status marker check to fail when marker is too late" >&2
  exit 1
fi

echo "$out" | grep -F "docs/api/entry.md:34:" >/dev/null || {
  echo "expected failure output to include file:line for marker position" >&2
  echo "$out" >&2
  exit 1
}

echo "$out" | grep -F "marker too late" >/dev/null || {
  echo "expected failure output to include 'marker too late' hint" >&2
  echo "$out" >&2
  exit 1
}

# Fix: move marker near top (<=30 lines).
cat > "$tmp_root/docs/api/entry.md" <<'EOF'
# Entry Doc

TODO: should require marker near top
See docs/CURRENT_STATUS.md for up-to-date status.

More content...
EOF

(cd "$tmp_root" && python3 scripts/check_docs_status_markers.py >/dev/null)

echo "OK: docs status marker check enforces marker position for entry docs"
