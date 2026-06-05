#!/usr/bin/env bash
set -euo pipefail

# 目的：
# - pip-audit 通过 requests 访问 OSV，在代理环境下可能出现一次性 TLS/EOF 抖动。
# - security-audit 应重试瞬时失败，避免把网络抖动误报为依赖漏洞。

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

audit_attempts="$tmp_root/pip-audit-attempts"
audit_args_log="$tmp_root/pip-audit-args.log"
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
  printf '%s\n' "$*" >> "${AUDIT_ARGS_LOG:?}"
  count=0
  if [ -f "${AUDIT_ATTEMPTS:?}" ]; then
    count="$(cat "$AUDIT_ATTEMPTS")"
  fi
  count=$((count + 1))
  printf '%s\n' "$count" > "$AUDIT_ATTEMPTS"
  if [ "$count" -eq 1 ]; then
    echo "transient osv proxy EOF" >&2
    exit 28
  fi
  exit 0
fi

exit 0
EOF
chmod +x "$tmp_root/frontend/backend/.venv/bin/python"

cat > "$tmp_root/bin/npm" <<'EOF'
#!/usr/bin/env bash
set -euo pipefail
exit 0
EOF
chmod +x "$tmp_root/bin/npm"

(
  cd "$tmp_root"
  env \
    AUDIT_ATTEMPTS="$audit_attempts" \
    AUDIT_ARGS_LOG="$audit_args_log" \
    PIP_PROXY="http://localhost:7890" \
    PIP_AUDIT_RETRY_DELAY_SECONDS=0 \
    PATH="$tmp_root/bin:$PATH" \
      bash scripts/run-tests.sh security-audit >/dev/null
)

attempt_count="$(cat "$audit_attempts")"
if [ "$attempt_count" -lt 3 ]; then
  echo "expected backend pip-audit to be retried before paper audit; attempts=$attempt_count" >&2
  exit 1
fi

grep -F -- "--timeout 8" "$audit_args_log" >/dev/null || {
  echo "expected pip-audit invocations to use explicit default socket timeout" >&2
  cat "$audit_args_log" >&2
  exit 1
}

echo "OK: run-tests security-audit retries transient pip-audit failures"
