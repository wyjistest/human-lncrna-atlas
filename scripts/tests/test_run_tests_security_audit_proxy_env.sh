#!/usr/bin/env bash
set -euo pipefail

# 目的：
# - pip-audit 没有 --proxy 参数；当只配置 PIP_PROXY 时，security-audit
#   入口必须把它转成 HTTP_PROXY/HTTPS_PROXY，保证 pip-audit 的解析请求也能走代理。

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

audit_env_log="$tmp_root/pip-audit-env.log"
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
  {
    printf 'HTTP_PROXY=%s\n' "${HTTP_PROXY:-}"
    printf 'HTTPS_PROXY=%s\n' "${HTTPS_PROXY:-}"
    printf 'http_proxy=%s\n' "${http_proxy:-}"
    printf 'https_proxy=%s\n' "${https_proxy:-}"
  } >> "${AUDIT_ENV_LOG:?}"
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
    -u HTTP_PROXY \
    -u HTTPS_PROXY \
    -u http_proxy \
    -u https_proxy \
    AUDIT_ENV_LOG="$audit_env_log" \
    PIP_PROXY="http://localhost:7890" \
    PATH="$tmp_root/bin:$PATH" \
      bash scripts/run-tests.sh security-audit >/dev/null
)

if [ ! -f "$audit_env_log" ]; then
  echo "expected security-audit to invoke backend pip-audit" >&2
  exit 1
fi

grep -F "HTTP_PROXY=http://localhost:7890" "$audit_env_log" >/dev/null || {
  echo "expected pip-audit to receive HTTP_PROXY derived from PIP_PROXY" >&2
  cat "$audit_env_log" >&2
  exit 1
}

grep -F "HTTPS_PROXY=http://localhost:7890" "$audit_env_log" >/dev/null || {
  echo "expected pip-audit to receive HTTPS_PROXY derived from PIP_PROXY" >&2
  cat "$audit_env_log" >&2
  exit 1
}

grep -F "http_proxy=http://localhost:7890" "$audit_env_log" >/dev/null || {
  echo "expected pip-audit to receive lowercase http_proxy derived from PIP_PROXY" >&2
  cat "$audit_env_log" >&2
  exit 1
}

grep -F "https_proxy=http://localhost:7890" "$audit_env_log" >/dev/null || {
  echo "expected pip-audit to receive lowercase https_proxy derived from PIP_PROXY" >&2
  cat "$audit_env_log" >&2
  exit 1
}

echo "OK: run-tests security-audit maps PIP_PROXY to pip-audit proxy env"
