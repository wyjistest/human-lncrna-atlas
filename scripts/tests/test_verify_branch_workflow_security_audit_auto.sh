#!/usr/bin/env bash
set -euo pipefail

# 目的：
# - 回归测试 `scripts/ci/verify_branch.sh --security-audit auto` 的判定逻辑：
#   1) 当依赖清单 / security-audit workflow 发生改动时，必须额外触发 `security-audit.yml`；
#   2) 普通非依赖改动时，不应额外触发安全审计 workflow。

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

mkdir -p \
  "$repo/scripts/ci" \
  "$repo/scripts" \
  "$repo/frontend/backend" \
  "$repo/frontend/web" \
  "$repo/docs" \
  "$tmp_root/bin"

cp "$REPO_ROOT/scripts/ci/verify_branch.sh" "$repo/scripts/ci/verify_branch.sh"
chmod +x "$repo/scripts/ci/verify_branch.sh"

cat > "$repo/scripts/run-tests.sh" <<'EOF'
#!/usr/bin/env bash
set -euo pipefail
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

printf 'gh' >> "$log_path"
for arg in "$@"; do
  printf ' [%s]' "$arg" >> "$log_path"
done
printf '\n' >> "$log_path"

sub1="${1:-}"
sub2="${2:-}"

if [[ "$sub1" == "workflow" && "$sub2" == "run" ]]; then
  exit 0
fi

if [[ "$sub1" == "run" && "$sub2" == "list" ]]; then
  workflow=""
  while [ "$#" -gt 0 ]; do
    if [ "${1:-}" = "--workflow" ]; then
      workflow="${2:-}"
      break
    fi
    shift
  done

  case "$workflow" in
    test.yml)
      printf '201\thttps://example.invalid/runs/201\n'
      ;;
    security-audit.yml)
      printf '301\thttps://example.invalid/runs/301\n'
      ;;
    *)
      ;;
  esac
  exit 0
fi

if [[ "$sub1" == "run" && "$sub2" == "watch" ]]; then
  exit 0
fi

echo "unexpected gh invocation: $*" >&2
exit 1
EOF
chmod +x "$tmp_root/bin/gh"

git init -q --bare "$remote"
git --git-dir="$remote" symbolic-ref HEAD refs/heads/main

(
  cd "$repo"
  git init -q
  git symbolic-ref HEAD refs/heads/main
  git config user.name "ci"
  git config user.email "ci@example.invalid"
  git remote add origin "$remote"

  echo "requests==1.0.0" > frontend/backend/requirements-dev.txt
  echo "{}" > frontend/web/package-lock.json
  echo "# notes" > docs/notes.md
  git add frontend/backend/requirements-dev.txt frontend/web/package-lock.json docs/notes.md scripts/run-tests.sh
  git commit -q -m "test: initial"
  git push -q -u origin main
  git fetch -q origin

  git checkout -q -b deps/update
  echo "urllib3==2.0.0" >> frontend/backend/requirements-dev.txt
  git add frontend/backend/requirements-dev.txt
  git commit -q -m "test: dependency update"

  git checkout -q main
  git checkout -q -b docs/update
  echo "more docs" >> docs/notes.md
  git add docs/notes.md
  git commit -q -m "test: docs update"
)

export VERIFY_BRANCH_TEST_LOG="$log_path"
export VERIFY_BRANCH_REAL_GIT="$REAL_GIT"

dep_output="$(
  cd "$repo" &&
    PATH="$tmp_root/bin:$PATH" \
      VERIFY_BRANCH_RUN_DISCOVERY_ATTEMPTS=1 \
      VERIFY_BRANCH_RUN_DISCOVERY_SLEEP_SECONDS=0 \
      bash scripts/ci/verify_branch.sh --branch deps/update --skip-local --skip-push --security-audit auto 2>&1
)"

echo "$dep_output"

cp "$log_path" "$tmp_root/deps.log"
: > "$log_path"

docs_output="$(
  cd "$repo" &&
    PATH="$tmp_root/bin:$PATH" \
      VERIFY_BRANCH_RUN_DISCOVERY_ATTEMPTS=1 \
      VERIFY_BRANCH_RUN_DISCOVERY_SLEEP_SECONDS=0 \
      bash scripts/ci/verify_branch.sh --branch docs/update --skip-local --skip-push --security-audit auto 2>&1
)"

echo "$docs_output"

grep -F "gh [workflow] [run] [test.yml] [--ref] [deps/update]" "$tmp_root/deps.log" >/dev/null || {
  echo "expected test workflow for dependency branch" >&2
  exit 1
}

grep -F "gh [workflow] [run] [security-audit.yml] [--ref] [deps/update]" "$tmp_root/deps.log" >/dev/null || {
  echo "expected security audit workflow for dependency branch" >&2
  exit 1
}

grep -F "gh [run] [watch] [301] [--exit-status]" "$tmp_root/deps.log" >/dev/null || {
  echo "expected watch for security audit run" >&2
  exit 1
}

grep -F "gh [workflow] [run] [test.yml] [--ref] [docs/update]" "$log_path" >/dev/null || {
  echo "expected test workflow for docs branch" >&2
  exit 1
}

if grep -Fq "gh [workflow] [run] [security-audit.yml] [--ref] [docs/update]" "$log_path"; then
  echo "did not expect security audit workflow for docs-only branch" >&2
  exit 1
fi

echo "$dep_output" | grep -F "https://example.invalid/runs/301" >/dev/null || {
  echo "expected security audit run URL in dependency branch output" >&2
  exit 1
}

echo "$docs_output" | grep -E "Skip security audit|跳过.*security audit" >/dev/null || {
  echo "expected skip message for docs-only branch" >&2
  exit 1
}

echo "OK"
