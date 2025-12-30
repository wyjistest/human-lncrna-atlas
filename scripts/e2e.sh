#!/usr/bin/env bash
# ==============================================================================
# Human LncRNA Atlas - Playwright E2E 一键运行脚本
# ==============================================================================
# 目标：
# - 解决本地/CI 跑 E2E 时常见的 429（后端限流）导致的随机失败
# - 自动以“测试模式”启动前后端，然后运行 `frontend/web` 下的 Playwright 测试
#
# 默认策略（安全优先）：
# - 仅在本脚本启动的后端进程上启用私网 bypass（RATE_LIMIT_BYPASS_PRIVATE=true）
# - 并强制 ENV=test（不会触发 production 的 fail-fast 约束）
#
# 用法：
#   ./scripts/e2e.sh
#   ./scripts/e2e.sh e2e/api/chipseq-compare.spec.ts
#   ./scripts/e2e.sh -- --workers=2
# ==============================================================================

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
PROJECT_ROOT="$(dirname "$SCRIPT_DIR")"

# 统一端口（可通过环境变量覆盖）
export BACKEND_PORT="${BACKEND_PORT:-8000}"
export FRONTEND_PORT="${FRONTEND_PORT:-5173}"

# 以测试模式启动（start.sh 在 dev 模式下会自动注入 TRUSTED_HOSTS/CORS/ADMIN_API_KEY）
export MODE="${MODE:-dev}"
export ENV="${ENV:-test}"

# 关键：避免 Playwright 并发打爆后端限流（仅对私网 IP 生效，生产环境不应开启）
export RATE_LIMIT_BYPASS_PRIVATE="${RATE_LIMIT_BYPASS_PRIVATE:-true}"

# E2E 默认使用 localhost 更可控（避免容器/LAN IP 差异）
export VITE_API_BASE_URL="${VITE_API_BASE_URL:-http://localhost:${BACKEND_PORT}}"
export API_BASE_URL="${API_BASE_URL:-http://localhost:${BACKEND_PORT}}"
export BASE_URL="${BASE_URL:-http://localhost:${FRONTEND_PORT}}"

wait_for_url() {
  local url="$1"
  local name="$2"
  local max_retries="${3:-40}"
  local retry_interval="${4:-1}"

  local attempt=1
  echo "[e2e] 等待 ${name} 就绪: ${url}"
  while [ "$attempt" -le "$max_retries" ]; do
    if curl -fsS --max-time 5 "$url" >/dev/null 2>&1; then
      return 0
    fi
    sleep "$retry_interval"
    attempt=$((attempt + 1))
  done
  echo "[e2e] ${name} 未就绪（超时）。请查看 /tmp/lncrna-atlas/*.log"
  return 1
}

main() {
  echo "[e2e] 停止可能存在的旧进程（避免使用旧环境变量启动的后端）"
  "$SCRIPT_DIR/stop.sh" >/dev/null 2>&1 || true

  echo "[e2e] 启动前后端（MODE=${MODE}, ENV=${ENV}, RATE_LIMIT_BYPASS_PRIVATE=${RATE_LIMIT_BYPASS_PRIVATE}）"
  "$SCRIPT_DIR/start.sh" >/dev/null

  wait_for_url "http://localhost:${BACKEND_PORT}/health" "后端" 40 1
  wait_for_url "http://localhost:${FRONTEND_PORT}" "前端" 60 1

  cd "$PROJECT_ROOT/frontend/web"

  if [ "$#" -eq 0 ]; then
    npm run test:e2e
    return 0
  fi

  # 支持两种调用：
  # 1) ./scripts/e2e.sh e2e/foo.spec.ts
  # 2) ./scripts/e2e.sh -- --workers=2
  if [ "${1:-}" = "--" ]; then
    shift
  fi
  npm run test:e2e -- "$@"
}

main "$@"

