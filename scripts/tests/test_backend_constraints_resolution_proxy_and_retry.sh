#!/usr/bin/env bash
set -euo pipefail

# 目的：
# - PyPI 约束解析测试在代理环境下应显式把 PIP_PROXY 传给 pip。
# - 遇到一次性 pip 网络失败时应重试，避免代理/TLS 抖动导致 CI 误报红。

REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"

tmp_root="$(mktemp -d)"
cleanup() {
  rm -rf "$tmp_root"
}
trap cleanup EXIT

mkdir -p "$tmp_root/bin" "$tmp_root/scripts/tests" "$tmp_root/frontend/backend"
cp "$REPO_ROOT/scripts/tests/test_backend_constraints_resolution.sh" \
  "$tmp_root/scripts/tests/test_backend_constraints_resolution.sh"
chmod +x "$tmp_root/scripts/tests/test_backend_constraints_resolution.sh"

cat > "$tmp_root/frontend/backend/requirements-dev.txt" <<'EOF'
fastapi>=0.118.0,<1.0.0
EOF
cat > "$tmp_root/frontend/backend/constraints.txt" <<'EOF'
fastapi==0.135.1
EOF

cat > "$tmp_root/bin/python3" <<'EOF'
#!/usr/bin/env bash
set -euo pipefail

if [[ "${1:-}" == "-m" && "${2:-}" == "venv" ]]; then
  venv_dir="${3:?}"
  mkdir -p "$venv_dir/bin"
  cat > "$venv_dir/bin/activate" <<'ACTIVATE'
VIRTUAL_ENV="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
PATH="$VIRTUAL_ENV/bin:$PATH"
export VIRTUAL_ENV PATH
ACTIVATE
  cat > "$venv_dir/bin/python" <<'PYTHON'
#!/usr/bin/env bash
set -euo pipefail
if [[ "${1:-}" == "-m" && "${2:-}" == "pip" ]]; then
  shift 2
  printf 'python -m pip %s\n' "$*" >> "${PIP_LOG:?}"
  exit 0
fi
exit 0
PYTHON
  chmod +x "$venv_dir/bin/python"
  cat > "$venv_dir/bin/pip" <<'PIP'
#!/usr/bin/env bash
set -euo pipefail
printf 'pip %s\n' "$*" >> "${PIP_LOG:?}"
if [[ "$*" == *"--dry-run"* ]]; then
  count_file="${PIP_DRY_RUN_COUNT:?}"
  count=0
  if [ -f "$count_file" ]; then
    count="$(cat "$count_file")"
  fi
  count=$((count + 1))
  printf '%s\n' "$count" > "$count_file"
  if [ "$count" -eq 1 ]; then
    echo "simulated transient pip failure" >&2
    exit 1
  fi
fi
exit 0
PIP
  chmod +x "$venv_dir/bin/pip"
  exit 0
fi

echo "unexpected python3 invocation: $*" >&2
exit 1
EOF
chmod +x "$tmp_root/bin/python3"

pip_log="$tmp_root/pip.log"
dry_run_count="$tmp_root/dry-run-count"
(
  cd "$tmp_root"
  PATH="$tmp_root/bin:$PATH" \
  PIP_LOG="$pip_log" \
  PIP_DRY_RUN_COUNT="$dry_run_count" \
  PIP_PROXY="http://127.0.0.1:7890" \
    bash scripts/tests/test_backend_constraints_resolution.sh >/dev/null
)

grep -F -- "--proxy http://127.0.0.1:7890" "$pip_log" >/dev/null || {
  echo "expected pip invocations to include --proxy from PIP_PROXY" >&2
  cat "$pip_log" >&2
  exit 1
}

grep -F -- "--retries 0" "$pip_log" >/dev/null || {
  echo "expected pip invocations to disable nested pip retries" >&2
  cat "$pip_log" >&2
  exit 1
}

grep -F -- "--timeout 15" "$pip_log" >/dev/null || {
  echo "expected pip invocations to use an explicit socket timeout" >&2
  cat "$pip_log" >&2
  exit 1
}

if grep -F -- "install --upgrade pip" "$pip_log" >/dev/null; then
  echo "expected resolver dry-run test to avoid network-heavy pip self-upgrade" >&2
  cat "$pip_log" >&2
  exit 1
fi

if [ "$(cat "$dry_run_count")" -ne 2 ]; then
  echo "expected dry-run resolver to retry once after transient failure" >&2
  cat "$pip_log" >&2
  exit 1
fi

echo "OK: backend constraints resolver uses PIP_PROXY and retries transient pip failures"

invalid_log="$tmp_root/invalid-attempts.log"
set +e
(
  cd "$tmp_root"
  PATH="$tmp_root/bin:$PATH" \
  PIP_LOG="$invalid_log" \
  PIP_DRY_RUN_COUNT="$tmp_root/invalid-dry-run-count" \
  PIP_RESOLVE_ATTEMPTS=0 \
    bash scripts/tests/test_backend_constraints_resolution.sh >/dev/null 2>&1
)
invalid_status=$?
set -e

if [ "$invalid_status" -eq 0 ]; then
  echo "expected invalid PIP_RESOLVE_ATTEMPTS=0 to fail instead of skipping pip commands" >&2
  cat "$invalid_log" >&2 || true
  exit 1
fi

echo "OK: backend constraints resolver rejects invalid retry attempts"

invalid_pip_retries_log="$tmp_root/invalid-pip-retries.log"
set +e
(
  cd "$tmp_root"
  PATH="$tmp_root/bin:$PATH" \
  PIP_LOG="$invalid_pip_retries_log" \
  PIP_DRY_RUN_COUNT="$tmp_root/invalid-pip-retries-count" \
  PIP_RESOLVE_PIP_RETRIES=-1 \
    bash scripts/tests/test_backend_constraints_resolution.sh >"$tmp_root/invalid-pip-retries.out" 2>&1
)
invalid_pip_retries_status=$?
set -e

if [ "$invalid_pip_retries_status" -eq 0 ]; then
  echo "expected invalid PIP_RESOLVE_PIP_RETRIES=-1 to fail before pip commands" >&2
  cat "$invalid_pip_retries_log" >&2 || true
  exit 1
fi

grep -F "PIP_RESOLVE_PIP_RETRIES must be a non-negative integer" \
  "$tmp_root/invalid-pip-retries.out" >/dev/null || {
    echo "expected invalid PIP_RESOLVE_PIP_RETRIES failure to explain the valid format" >&2
    cat "$tmp_root/invalid-pip-retries.out" >&2
    exit 1
  }

if [ -s "$invalid_pip_retries_log" ]; then
  echo "expected invalid PIP_RESOLVE_PIP_RETRIES to fail before invoking pip" >&2
  cat "$invalid_pip_retries_log" >&2
  exit 1
fi

echo "OK: backend constraints resolver rejects invalid pip retry values"

invalid_timeout_log="$tmp_root/invalid-timeout.log"
set +e
(
  cd "$tmp_root"
  PATH="$tmp_root/bin:$PATH" \
  PIP_LOG="$invalid_timeout_log" \
  PIP_DRY_RUN_COUNT="$tmp_root/invalid-timeout-count" \
  PIP_RESOLVE_TIMEOUT=0 \
    bash scripts/tests/test_backend_constraints_resolution.sh >"$tmp_root/invalid-timeout.out" 2>&1
)
invalid_timeout_status=$?
set -e

if [ "$invalid_timeout_status" -eq 0 ]; then
  echo "expected invalid PIP_RESOLVE_TIMEOUT=0 to fail before pip commands" >&2
  cat "$invalid_timeout_log" >&2 || true
  exit 1
fi

grep -F "PIP_RESOLVE_TIMEOUT must be a positive integer" \
  "$tmp_root/invalid-timeout.out" >/dev/null || {
    echo "expected invalid PIP_RESOLVE_TIMEOUT failure to explain the valid format" >&2
    cat "$tmp_root/invalid-timeout.out" >&2
    exit 1
  }

if [ -s "$invalid_timeout_log" ]; then
  echo "expected invalid PIP_RESOLVE_TIMEOUT to fail before invoking pip" >&2
  cat "$invalid_timeout_log" >&2
  exit 1
fi

echo "OK: backend constraints resolver rejects invalid pip timeout values"
