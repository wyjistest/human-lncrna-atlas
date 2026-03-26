#!/usr/bin/env bash
set -euo pipefail

# 目的：
# - 回归测试 `scripts/ci/verify_branch.sh` 的主流程：
#   1) tracked 脏工作区必须直接失败；
#   2) 同仓库 PR 验证成功时，必须跑本地 `scripts/run-tests.sh ci`、push 目标分支，
#      并手动触发 `test.yml` 后等待对应 run 完成。
#
# 说明：
# - 使用真实本地 git 仓库 + bare remote，避免伪造 git 状态。
# - 通过 fake `gh` / `sleep` 与 git 包装器记录命令，不访问真实 GitHub。

REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
REAL_GIT="$(command -v git)"

tmp_root="$(mktemp -d)"
cleanup() {
  rm -rf "$tmp_root"
}
trap cleanup EXIT

repo="$tmp_root/repo"
remote="$tmp_root/remote.git"
log_path="$tmp_root/command.log"
state_dir="$tmp_root/state"

mkdir -p \
  "$repo/scripts/ci" \
  "$repo/scripts" \
  "$tmp_root/bin" \
  "$state_dir"

cp "$REPO_ROOT/scripts/ci/verify_branch.sh" "$repo/scripts/ci/verify_branch.sh"
chmod +x "$repo/scripts/ci/verify_branch.sh"

cat > "$repo/scripts/run-tests.sh" <<'EOF'
#!/usr/bin/env bash
set -euo pipefail

log_path="${VERIFY_BRANCH_TEST_LOG:?}"
printf 'run-tests' >> "$log_path"
for arg in "$@"; do
  printf ' [%s]' "$arg" >> "$log_path"
done
printf '\n' >> "$log_path"
exit 0
EOF
chmod +x "$repo/scripts/run-tests.sh"

cat > "$tmp_root/bin/git" <<'EOF'
#!/usr/bin/env bash
set -euo pipefail

log_path="${VERIFY_BRANCH_TEST_LOG:?}"
real_git="${VERIFY_BRANCH_REAL_GIT:?}"

printf 'git' >> "$log_path"
for arg in "$@"; do
  printf ' [%s]' "$arg" >> "$log_path"
done
printf '\n' >> "$log_path"

exec "$real_git" "$@"
EOF
chmod +x "$tmp_root/bin/git"

cat > "$tmp_root/bin/gh" <<'EOF'
#!/usr/bin/env bash
set -euo pipefail

log_path="${VERIFY_BRANCH_TEST_LOG:?}"
state_dir="${VERIFY_BRANCH_TEST_STATE_DIR:?}"

printf 'gh' >> "$log_path"
for arg in "$@"; do
  printf ' [%s]' "$arg" >> "$log_path"
done
printf '\n' >> "$log_path"

sub1="${1:-}"
sub2="${2:-}"

if [[ "$sub1" == "pr" && "$sub2" == "view" ]]; then
  printf 'feature/verify\tfalse\n'
  exit 0
fi

if [[ "$sub1" == "workflow" && "$sub2" == "run" ]]; then
  exit 0
fi

if [[ "$sub1" == "run" && "$sub2" == "list" ]]; then
  count_file="$state_dir/test-run-list.count"
  count=0
  if [ -f "$count_file" ]; then
    count="$(cat "$count_file")"
  fi
  count=$((count + 1))
  printf '%s' "$count" > "$count_file"
  if [ "$count" -ge 2 ]; then
    printf '101\thttps://example.invalid/runs/101\n'
  fi
  exit 0
fi

if [[ "$sub1" == "run" && "$sub2" == "watch" ]]; then
  exit 0
fi

echo "unexpected gh invocation: $*" >&2
exit 1
EOF
chmod +x "$tmp_root/bin/gh"

cat > "$tmp_root/bin/sleep" <<'EOF'
#!/usr/bin/env bash
set -euo pipefail

log_path="${VERIFY_BRANCH_TEST_LOG:?}"
printf 'sleep' >> "$log_path"
for arg in "$@"; do
  printf ' [%s]' "$arg" >> "$log_path"
done
printf '\n' >> "$log_path"
exit 0
EOF
chmod +x "$tmp_root/bin/sleep"

git init -q --bare "$remote"
git --git-dir="$remote" symbolic-ref HEAD refs/heads/main

(
  cd "$repo"
  git init -q
  git symbolic-ref HEAD refs/heads/main
  git config user.name "ci"
  git config user.email "ci@example.invalid"
  git remote add origin "$remote"

  echo "# verify-branch" > README.md
  git add README.md scripts/run-tests.sh
  git commit -q -m "test: initial"
  git push -q -u origin main

  git checkout -q -b feature/verify
  echo "dirty change" >> README.md
)

export VERIFY_BRANCH_TEST_LOG="$log_path"
export VERIFY_BRANCH_REAL_GIT="$REAL_GIT"
export VERIFY_BRANCH_TEST_STATE_DIR="$state_dir"

set +e
dirty_output="$(
  cd "$repo" &&
    PATH="$tmp_root/bin:$PATH" \
      VERIFY_BRANCH_RUN_DISCOVERY_ATTEMPTS=2 \
      VERIFY_BRANCH_RUN_DISCOVERY_SLEEP_SECONDS=0 \
      bash scripts/ci/verify_branch.sh --pr 123 --runs-on self-hosted --security-audit never 2>&1
)"
dirty_status=$?
set -e

echo "$dirty_output"

if [ "$dirty_status" -eq 0 ]; then
  echo "expected dirty tracked workspace to fail" >&2
  exit 1
fi

echo "$dirty_output" | grep -E "tracked changes|工作区.*tracked" >/dev/null || {
  echo "expected dirty workspace error message" >&2
  exit 1
}

(
  cd "$repo"
  git add README.md
  git commit -q -m "test: clean feature branch"
)

: > "$log_path"
rm -f "$state_dir/test-run-list.count"

output="$(
  cd "$repo" &&
    PATH="$tmp_root/bin:$PATH" \
      VERIFY_BRANCH_RUN_DISCOVERY_ATTEMPTS=2 \
      VERIFY_BRANCH_RUN_DISCOVERY_SLEEP_SECONDS=0 \
      bash scripts/ci/verify_branch.sh --pr 123 --runs-on self-hosted --security-audit never 2>&1
)"

echo "$output"

grep -F "run-tests [ci]" "$log_path" >/dev/null || {
  echo "expected local ci target to run" >&2
  exit 1
}

grep -E "git .*\\[push\\] \\[origin\\] \\[feature/verify\\]" "$log_path" >/dev/null || {
  echo "expected target branch to be pushed to origin" >&2
  exit 1
}

grep -F "gh [pr] [view] [123]" "$log_path" >/dev/null || {
  echo "expected PR metadata lookup" >&2
  exit 1
}

grep -F "gh [workflow] [run] [test.yml] [--ref] [feature/verify] [-f] [runs_on=self-hosted]" "$log_path" >/dev/null || {
  echo "expected test workflow dispatch with runs_on override" >&2
  exit 1
}

grep -F "gh [run] [watch] [101] [--exit-status]" "$log_path" >/dev/null || {
  echo "expected workflow watch on discovered run id" >&2
  exit 1
}

echo "$output" | grep -F "https://example.invalid/runs/101" >/dev/null || {
  echo "expected run URL in output summary" >&2
  exit 1
}

echo "OK"
