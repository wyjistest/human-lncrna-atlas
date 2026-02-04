#!/usr/bin/env bash
# ==============================================================================
# git 代理包装器（单次命令生效）
# ==============================================================================
# 用途：
# - 当直连 github.com 超时/不可达，但本机有 HTTP 代理（如 mihomo/clash）可用时，
#   通过环境变量让 git 的 HTTP(S) 请求走代理。
#
# 设计原则：
# - 不修改全局 git config（避免影响 Actions runner）
# - 仅影响当前进程（可审计、可回滚）
#
# 用法：
#   bash scripts/ci/git_with_proxy.sh fetch --prune
#   bash scripts/ci/git_with_proxy.sh push
#
# 可配置：
#   PROXY_URL=http://127.0.0.1:7890
#   NO_PROXY_LIST=127.0.0.1,localhost,::1
# ==============================================================================

set -euo pipefail

if [ $# -lt 1 ]; then
  echo "Usage: $0 <git-args...>" >&2
  exit 2
fi

PROXY_URL="${PROXY_URL:-http://127.0.0.1:7890}"
NO_PROXY_LIST="${NO_PROXY_LIST:-127.0.0.1,localhost,::1}"

export http_proxy="${http_proxy:-$PROXY_URL}"
export https_proxy="${https_proxy:-$PROXY_URL}"
export HTTP_PROXY="${HTTP_PROXY:-$http_proxy}"
export HTTPS_PROXY="${HTTPS_PROXY:-$https_proxy}"

# 避免把本机服务（backend/health check 等）也走代理，导致卡住
export NO_PROXY="${NO_PROXY:-$NO_PROXY_LIST}"
export no_proxy="${no_proxy:-$NO_PROXY_LIST}"

exec git "$@"

