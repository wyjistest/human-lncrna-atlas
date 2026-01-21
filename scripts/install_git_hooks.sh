#!/usr/bin/env bash
set -euo pipefail

# 安装本仓库的 git hooks（目前只包含 pre-push 本地 CI 门禁）。
#
# 用法：
#   bash scripts/install_git_hooks.sh
#
# 说明：
# - 如果目标 hook 已存在，会先备份为 *.bak.<timestamp>
# - hooks 不会随 git 提交同步到其他机器，因此需要每个开发环境执行一次

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(dirname "$SCRIPT_DIR")"

hook_src="${REPO_ROOT}/githooks/pre-push"
if [ ! -f "$hook_src" ]; then
  echo "[ERROR] Hook template not found: ${hook_src}" >&2
  exit 1
fi

git_dir="$(git -C "$REPO_ROOT" rev-parse --git-dir 2>/dev/null || true)"
if [ -z "$git_dir" ]; then
  echo "[ERROR] Not a git repository: ${REPO_ROOT}" >&2
  exit 1
fi

if [[ "$git_dir" = /* ]]; then
  hooks_dir="${git_dir}/hooks"
else
  hooks_dir="${REPO_ROOT}/${git_dir}/hooks"
fi

mkdir -p "$hooks_dir"

hook_dst="${hooks_dir}/pre-push"
if [ -e "$hook_dst" ]; then
  ts="$(date +"%Y%m%d%H%M%S")"
  backup="${hook_dst}.bak.${ts}"
  cp "$hook_dst" "$backup"
  echo "[INFO] Backed up existing pre-push hook to: ${backup}"
fi

cp "$hook_src" "$hook_dst"
chmod +x "$hook_dst"

echo "[OK] Installed pre-push hook: ${hook_dst}"
echo ""
echo "Tips:"
echo "- Skip once: git push --no-verify"
echo "- Skip via env: SKIP_LOCAL_CI=1 git push"
echo "- Change target: LOCAL_CI_TARGET=smoke git push"

