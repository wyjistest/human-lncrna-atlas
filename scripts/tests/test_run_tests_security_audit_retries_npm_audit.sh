#!/usr/bin/env bash
set -euo pipefail

# 目的：
# - npm audit 访问 registry.npmjs.org 时可能出现一次性 TLS/网络断连。
# - security-audit 应重试瞬时失败，避免把网络抖动误报为前端依赖漏洞。

REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"

tmp_root="$(mktemp -d)"
cleanup() {
  rm -rf "$tmp_root"
}
trap cleanup EXIT

mkdir -p \
  "$tmp_root/bin" \
  "$tmp_root/scripts" \
  "$tmp_root/scripts/paper" \
  "$tmp_root/frontend/backend/.venv/bin" \
  "$tmp_root/frontend/web"

cp "$REPO_ROOT/scripts/run-tests.sh" "$tmp_root/scripts/run-tests.sh"
chmod +x "$tmp_root/scripts/run-tests.sh"

cat > "$tmp_root/frontend/backend/requirements.txt" <<'EOF'
fastapi==0.0.0
EOF
cat > "$tmp_root/frontend/backend/requirements-dev.txt" <<'EOF'
pip-audit==0.0.0
EOF
cat > "$tmp_root/frontend/backend/constraints.txt" <<'EOF'
starlette==0.0.0
EOF
cat > "$tmp_root/scripts/paper/requirements.txt" <<'EOF'
matplotlib==0.0.0
EOF
cat > "$tmp_root/frontend/web/package-lock.json" <<'EOF'
{"lockfileVersion": 3}
EOF

cat > "$tmp_root/frontend/backend/.venv/bin/python" <<'EOF'
#!/usr/bin/env bash
set -euo pipefail

if [[ "${1:-}" == "-" ]]; then
  echo "fakehash"
  exit 0
fi

if [[ "${1:-}" == "-c" ]]; then
  exit 0
fi

if [[ "${1:-}" == "-m" && "${2:-}" == "pip" && "$*" == *" install "* ]]; then
  exit 0
fi

if [[ "${1:-}" == "-m" && "${2:-}" == "pip_audit" ]]; then
  exit 0
fi

exit 0
EOF
chmod +x "$tmp_root/frontend/backend/.venv/bin/python"

npm_attempts="$tmp_root/npm-audit-attempts"
npm_args_log="$tmp_root/npm-audit-args.log"
cat > "$tmp_root/bin/npm" <<'EOF'
#!/usr/bin/env bash
set -euo pipefail

if [[ "${1:-}" == "ci" ]]; then
  exit 0
fi

if [[ "${1:-}" == "audit" ]]; then
  printf '%s\n' "$*" >> "${NPM_ARGS_LOG:?}"
  count=0
  if [ -f "${NPM_ATTEMPTS:?}" ]; then
    count="$(cat "$NPM_ATTEMPTS")"
  fi
  count=$((count + 1))
  printf '%s\n' "$count" > "$NPM_ATTEMPTS"
  if [ "${NPM_AUDIT_ZERO_EXIT_ERROR:-}" = "1" ]; then
    echo "npm warn audit request to https://registry.npmjs.org/-/npm/v1/security/audits/quick failed" >&2
    echo "npm error audit endpoint returned an error" >&2
    exit 0
  fi
  if [ "$count" -eq 1 ]; then
    echo "npm audit transient TLS disconnect" >&2
    exit 1
  fi
  exit 0
fi

exit 0
EOF
chmod +x "$tmp_root/bin/npm"

(
  cd "$tmp_root"
  env \
    NPM_ATTEMPTS="$npm_attempts" \
    NPM_ARGS_LOG="$npm_args_log" \
    NPM_AUDIT_RETRY_DELAY_SECONDS=0 \
    PATH="$tmp_root/bin:$PATH" \
      bash scripts/run-tests.sh security-audit >/dev/null
)

if [ "$(cat "$npm_attempts")" -ne 2 ]; then
  echo "expected npm audit to retry once after transient failure" >&2
  cat "$npm_args_log" >&2
  exit 1
fi

grep -F -- "--registry=https://registry.npmjs.org" "$npm_args_log" >/dev/null || {
  echo "expected npm audit to keep using npmjs registry" >&2
  cat "$npm_args_log" >&2
  exit 1
}

grep -F -- "--audit-level=high" "$npm_args_log" >/dev/null || {
  echo "expected npm audit strict mode to keep high audit level" >&2
  cat "$npm_args_log" >&2
  exit 1
}

grep -F "run_npm_audit_with_retry npm audit --registry=https://registry.npmjs.org --audit-level=high" \
  "$REPO_ROOT/.github/workflows/security-audit.yml" >/dev/null || {
    echo "expected security-audit workflow strict npm audit to use retry wrapper" >&2
    exit 1
  }

grep -F "NPM_AUDIT_OUTPUT_FILE=npm-audit-report.json run_npm_audit_with_retry npm audit --registry=https://registry.npmjs.org --json" \
  "$REPO_ROOT/.github/workflows/security-audit.yml" >/dev/null || {
    echo "expected security-audit workflow json npm audit report to use retry wrapper output capture" >&2
    exit 1
  }

if grep -F "bash -c 'npm audit --registry=https://registry.npmjs.org --json > npm-audit-report.json 2>&1'" \
  "$REPO_ROOT/.github/workflows/security-audit.yml" >/dev/null; then
  echo "expected retry wrapper to inspect json audit output before writing npm-audit-report.json" >&2
  exit 1
fi

grep -F "run_npm_audit_with_retry npm audit --registry=https://registry.npmjs.org --audit-level=moderate" \
  "$REPO_ROOT/.github/workflows/security-audit.yml" >/dev/null || {
    echo "expected security-audit workflow moderate npm audit output to use retry wrapper" >&2
    exit 1
  }

printf '0\n' > "$npm_attempts"
set +e
(
  cd "$tmp_root"
  env \
    NPM_ATTEMPTS="$npm_attempts" \
    NPM_ARGS_LOG="$npm_args_log" \
    NPM_AUDIT_ATTEMPTS=2 \
    NPM_AUDIT_RETRY_DELAY_SECONDS=0 \
    NPM_AUDIT_ZERO_EXIT_ERROR=1 \
    PATH="$tmp_root/bin:$PATH" \
      bash scripts/run-tests.sh security-audit >/dev/null 2>&1
)
status=$?
set -e

if [ "$status" -eq 0 ]; then
  echo "expected npm audit endpoint errors in output to fail security-audit even when npm exits 0" >&2
  exit 1
fi

if [ "$(cat "$npm_attempts")" -ne 2 ]; then
  echo "expected npm audit endpoint output errors to be retried to the configured limit" >&2
  cat "$npm_args_log" >&2
  exit 1
fi

grep -F "audit endpoint returned an error" "$REPO_ROOT/scripts/run-tests.sh" >/dev/null || {
  echo "expected run-tests npm audit wrapper to detect endpoint error output" >&2
  exit 1
}

grep -F "audit endpoint returned an error" "$REPO_ROOT/.github/workflows/security-audit.yml" >/dev/null || {
  echo "expected workflow npm audit wrapper to detect endpoint error output" >&2
  exit 1
}

echo "OK: run-tests security-audit retries transient npm audit failures"
