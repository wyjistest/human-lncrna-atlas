#!/usr/bin/env bash
# ==============================================================================
# Human LncRNA Atlas - 开发环境一键启动（LAN 友好）
# ==============================================================================
# 用途：
# - 调用 scripts/start.sh 启动前后端（dev 模式）
# - 自动注入 LAN 访问所需的 TRUSTED_HOSTS / CORS_ORIGINS / VITE_API_BASE_URL / ADMIN_API_KEY
#
# 常用：
#   ./scripts/dev.sh          # 启动前后端（可通过 192.168.x.x 访问）
#   ./scripts/stop.sh -s      # 查看状态
#   ./scripts/stop.sh         # 停止服务
# ==============================================================================

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"

# 强制使用 dev 模式（start.sh 也支持 MODE=dev，但这里显式声明更直观）
export MODE="dev"

exec "$SCRIPT_DIR/start.sh" "$@"

