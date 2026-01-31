#!/usr/bin/env bash
set -euo pipefail

# 目的：
# - 为 scripts/gh_push_commit.py 新增的 `--range` + `--dry-run` 能力提供脚本级单元测试。
# - 该测试不依赖网络与 GitHub API：只验证本地 git commit 解析与输出契约。
#
# 验收：
# 1) 对线性历史：`--range <A..B> --dry-run` 输出按顺序列出 commits，并 exit 0。
# 2) 对 merge commit：dry-run 也应拒绝，并给出明确提示（保持与单 commit 模式一致）。

# 兼容 git hooks 环境：避免 GIT_DIR/GIT_WORK_TREE 污染影响临时仓库。
unset GIT_DIR GIT_WORK_TREE

REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"

tmp_root="$(mktemp -d)"
cleanup() {
  rm -rf "$tmp_root"
}
trap cleanup EXIT

repo="$tmp_root/repo"
mkdir -p "$repo"

cd "$repo"
git init -q
git config user.name "ci"
git config user.email "ci@example.invalid"
default_branch="$(git symbolic-ref --short HEAD)"

echo "one" > file.txt
git add file.txt
git commit -q -m "test: one"

echo "two" >> file.txt
git add file.txt
git commit -q -m "test: two"

echo "three" >> file.txt
git add file.txt
git commit -q -m "test: three"

echo "== dry-run linear range =="
out="$(
  python3 "$REPO_ROOT/scripts/gh_push_commit.py" \
    --repo-dir "$repo" \
    --branch main \
    --range "HEAD~2..HEAD" \
    --dry-run \
    2>&1
)"
echo "$out"

echo "$out" | grep -F "[dry-run] commits (2)" >/dev/null || {
  echo "expected dry-run header with commit count" >&2
  exit 1
}
echo "$out" | grep -F "test: two" >/dev/null || {
  echo "expected commit subject 'test: two' in output" >&2
  exit 1
}
echo "$out" | grep -F "test: three" >/dev/null || {
  echo "expected commit subject 'test: three' in output" >&2
  exit 1
}
echo "$out" | grep -F "file.txt" >/dev/null || {
  echo "expected changed file list in dry-run output" >&2
  exit 1
}

echo "== dry-run rejects merge commits =="

# Create a merge commit.
git checkout -q -b feature
echo "feature" > feature.txt
git add feature.txt
git commit -q -m "test: feature"

git checkout -q "$default_branch"
echo "main" > main.txt
git add main.txt
git commit -q -m "test: main"

git merge -q --no-ff feature -m "test: merge feature"

set +e
out_merge="$(
  python3 "$REPO_ROOT/scripts/gh_push_commit.py" \
    --repo-dir "$repo" \
    --branch main \
    --range "HEAD~1..HEAD" \
    --dry-run \
    2>&1
)"
code=$?
set -e

echo "$out_merge"

if [ "$code" -eq 0 ]; then
  echo "expected merge commit dry-run to fail" >&2
  exit 1
fi
echo "$out_merge" | grep -E "不支持 merge commit|rebase/squash" >/dev/null || {
  echo "expected merge commit error message" >&2
  exit 1
}

echo "OK"
