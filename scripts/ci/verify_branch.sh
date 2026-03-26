#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(cd "$SCRIPT_DIR/../.." && pwd)"

DEFAULT_LOCAL_TARGET="ci"
DEFAULT_SECURITY_AUDIT="auto"
DEFAULT_BASE_REF="origin/main"
RUN_DISCOVERY_ATTEMPTS="${VERIFY_BRANCH_RUN_DISCOVERY_ATTEMPTS:-12}"
RUN_DISCOVERY_SLEEP_SECONDS="${VERIFY_BRANCH_RUN_DISCOVERY_SLEEP_SECONDS:-5}"

usage() {
  cat <<'EOF'
用法：bash scripts/ci/verify_branch.sh [options]

选项：
  --branch <branch>            指定要验证的本地分支（默认：当前分支）
  --pr <number>                从同仓库 PR 解析 head branch（不支持 fork PR）
  --skip-local                 跳过本地 `bash scripts/run-tests.sh <target>`
  --skip-push                  跳过 `git push origin <branch>`
  --local-target <target>      本地门禁目标（默认：ci）
  --security-audit <mode>      auto|always|never（默认：auto）
  --runs-on <label>            workflow_dispatch 时覆盖 runs_on 输入
  --base <ref>                 auto 判定 security-audit 时对比的 base ref（默认：origin/main）
  -h, --help                   显示帮助
EOF
}

log() {
  echo "[verify-branch] $*"
}

die() {
  echo "[verify-branch] ERROR: $*" >&2
  exit 1
}

require_cmd() {
  command -v "$1" >/dev/null 2>&1 || die "missing required command: $1"
}

require_clean_worktree() {
  if ! git -C "$REPO_ROOT" diff --quiet --ignore-submodules --; then
    die "工作区存在未提交的 tracked changes；请先提交或暂存后再执行。"
  fi
  if ! git -C "$REPO_ROOT" diff --cached --quiet --ignore-submodules --; then
    die "暂存区存在未提交的 tracked changes；请先提交后再执行。"
  fi
}

current_branch() {
  local branch
  branch="$(git -C "$REPO_ROOT" symbolic-ref --quiet --short HEAD 2>/dev/null || true)"
  [ -n "$branch" ] || die "当前处于 detached HEAD；请显式传入 --branch。"
  printf '%s\n' "$branch"
}

ensure_local_branch_exists() {
  local branch="$1"
  git -C "$REPO_ROOT" show-ref --verify --quiet "refs/heads/$branch" || {
    die "未找到本地分支：$branch。若来自 PR，请先执行 gh pr checkout 或 git fetch/checkout。"
  }
}

resolve_branch_from_pr() {
  local pr_number="$1"
  local pr_info
  pr_info="$(
    gh pr view "$pr_number" \
      --json headRefName,isCrossRepository \
      --jq '[.headRefName, (.isCrossRepository | tostring)] | @tsv'
  )"

  [ -n "$pr_info" ] || die "无法解析 PR #$pr_number 的 head branch。"

  local branch
  local is_cross_repo
  IFS=$'\t' read -r branch is_cross_repo <<<"$pr_info"

  [ -n "$branch" ] || die "PR #$pr_number 未返回有效的 head branch。"
  [ "$is_cross_repo" = "false" ] || die "PR #$pr_number 来自 fork；为避免在本地/自托管环境执行不受信任代码，本脚本不支持 fork PR。"

  printf '%s\n' "$branch"
}

discover_run() {
  local workflow="$1"
  local branch="$2"
  local sha="$3"
  local attempt
  local jq_expr
  local run_info

  jq_expr=".[] | select(.headSha == \"$sha\") | [.databaseId, .url] | @tsv"

  for ((attempt = 1; attempt <= RUN_DISCOVERY_ATTEMPTS; attempt++)); do
    run_info="$(
      gh run list \
        --workflow "$workflow" \
        --branch "$branch" \
        --event workflow_dispatch \
        --limit 20 \
        --json databaseId,url,headSha \
        --jq "$jq_expr" | head -n 1
    )"
    run_info="${run_info//$'\r'/}"

    if [ -n "$run_info" ] && [ "$run_info" != "null" ]; then
      printf '%s\n' "$run_info"
      return 0
    fi

    if [ "$attempt" -lt "$RUN_DISCOVERY_ATTEMPTS" ]; then
      sleep "$RUN_DISCOVERY_SLEEP_SECONDS"
    fi
  done

  die "已触发 $workflow，但在 branch=$branch sha=$sha 上未找到对应 workflow_dispatch run。"
}

dispatch_workflow_and_watch() {
  local workflow="$1"
  local label="$2"
  local branch="$3"
  local sha="$4"
  local run_info
  local run_id
  local run_url
  local args=(workflow run "$workflow" --ref "$branch")

  if [ -n "$RUNS_ON_LABEL" ]; then
    args+=(-f "runs_on=$RUNS_ON_LABEL")
  fi

  gh "${args[@]}"

  run_info="$(discover_run "$workflow" "$branch" "$sha")"
  IFS=$'\t' read -r run_id run_url <<<"$run_info"

  [ -n "$run_id" ] || die "$label run 缺少 databaseId。"
  [ -n "$run_url" ] || die "$label run 缺少 URL。"

  echo "[verify-branch] $label run: $run_url" >&2
  if ! gh run watch "$run_id" --exit-status; then
    die "$label 失败：$run_url"
  fi

  printf '%s\n' "$run_url"
}

security_audit_needed_auto() {
  local branch="$1"
  local changed

  git -C "$REPO_ROOT" rev-parse --verify "$BASE_REF" >/dev/null 2>&1 || {
    die "未找到 base ref：$BASE_REF"
  }

  changed="$(git -C "$REPO_ROOT" diff --name-only "$BASE_REF...$branch")"
  if [ -z "$changed" ]; then
    return 1
  fi

  while IFS= read -r path; do
    case "$path" in
      .github/workflows/security-audit.yml|frontend/backend/requirements*.txt|frontend/backend/constraints.txt|frontend/web/package.json|frontend/web/package-lock.json)
        return 0
        ;;
    esac
  done <<<"$changed"

  return 1
}

run_local_gate() {
  local target="$1"
  log "运行本地门禁：bash scripts/run-tests.sh $target"
  (
    cd "$REPO_ROOT"
    env -u GIT_DIR -u GIT_WORK_TREE bash "scripts/run-tests.sh" "$target"
  )
}

push_branch() {
  local branch="$1"
  log "推送分支到 origin/$branch"
  # verify_branch 已在 push 前显式跑过本地门禁；这里透传 SKIP_LOCAL_CI=1，
  # 避免 pre-push hook 再重复执行一次 scripts/run-tests.sh。
  if ! env SKIP_LOCAL_CI=1 git -C "$REPO_ROOT" push origin "$branch"; then
    echo "[verify-branch] git push 失败：origin/$branch" >&2
    echo "[verify-branch] 可重试：bash scripts/ci/git_with_proxy.sh push origin \"$branch\"" >&2
    echo "[verify-branch] 若仍失败，可按需使用 scripts/gh_push_commit.py 作为 GitHub API 止损路径（本脚本不会自动切换）。" >&2
    exit 1
  fi
}

main() {
  local branch=""
  local pr_number=""
  local skip_local="false"
  local skip_push="false"
  local local_target="$DEFAULT_LOCAL_TARGET"
  local security_audit_mode="$DEFAULT_SECURITY_AUDIT"
  RUNS_ON_LABEL=""
  BASE_REF="$DEFAULT_BASE_REF"

  while [ "$#" -gt 0 ]; do
    case "$1" in
      --branch)
        [ "$#" -ge 2 ] || die "--branch 缺少参数"
        branch="$2"
        shift 2
        ;;
      --pr)
        [ "$#" -ge 2 ] || die "--pr 缺少参数"
        pr_number="$2"
        shift 2
        ;;
      --skip-local)
        skip_local="true"
        shift
        ;;
      --skip-push)
        skip_push="true"
        shift
        ;;
      --local-target)
        [ "$#" -ge 2 ] || die "--local-target 缺少参数"
        local_target="$2"
        shift 2
        ;;
      --security-audit)
        [ "$#" -ge 2 ] || die "--security-audit 缺少参数"
        security_audit_mode="$2"
        shift 2
        ;;
      --runs-on)
        [ "$#" -ge 2 ] || die "--runs-on 缺少参数"
        RUNS_ON_LABEL="$2"
        shift 2
        ;;
      --base)
        [ "$#" -ge 2 ] || die "--base 缺少参数"
        BASE_REF="$2"
        shift 2
        ;;
      -h|--help)
        usage
        exit 0
        ;;
      *)
        usage >&2
        die "未知参数：$1"
        ;;
    esac
  done

  [ -d "$REPO_ROOT/.git" ] || git -C "$REPO_ROOT" rev-parse --is-inside-work-tree >/dev/null 2>&1 || die "当前目录不是 git 仓库：$REPO_ROOT"
  require_cmd git
  require_cmd gh

  if [ -n "$branch" ] && [ -n "$pr_number" ]; then
    die "--branch 与 --pr 不能同时使用"
  fi

  case "$security_audit_mode" in
    auto|always|never)
      ;;
    *)
      die "--security-audit 仅支持 auto|always|never（当前：$security_audit_mode）"
      ;;
  esac

  if [ -n "$pr_number" ]; then
    branch="$(resolve_branch_from_pr "$pr_number")"
  elif [ -z "$branch" ]; then
    branch="$(current_branch)"
  fi

  [ -n "$branch" ] || die "无法确定要验证的分支"
  ensure_local_branch_exists "$branch"
  require_clean_worktree

  local checked_out_branch
  checked_out_branch="$(current_branch)"
  if [ "$skip_local" != "true" ] && [ "$checked_out_branch" != "$branch" ]; then
    die "当前检出分支为 $checked_out_branch，但目标分支为 $branch；请先 checkout 目标分支，或使用 --skip-local。"
  fi

  local target_sha
  target_sha="$(git -C "$REPO_ROOT" rev-parse "$branch^{commit}")"

  local should_run_security_audit="false"
  case "$security_audit_mode" in
    always)
      should_run_security_audit="true"
      ;;
    never)
      should_run_security_audit="false"
      ;;
    auto)
      if security_audit_needed_auto "$branch"; then
        should_run_security_audit="true"
      fi
      ;;
  esac

  log "目标分支：$branch"
  [ -n "$pr_number" ] && log "来自 PR：#$pr_number"
  log "目标提交：$target_sha"

  if [ "$skip_local" = "true" ]; then
    log "跳过本地门禁（--skip-local）"
  else
    run_local_gate "$local_target"
  fi

  if [ "$skip_push" = "true" ]; then
    log "跳过 git push（--skip-push）"
  else
    push_branch "$branch"
  fi

  local test_url
  local security_url=""

  test_url="$(dispatch_workflow_and_watch "test.yml" "Tests" "$branch" "$target_sha")"

  if [ "$should_run_security_audit" = "true" ]; then
    security_url="$(dispatch_workflow_and_watch "security-audit.yml" "Security Audit" "$branch" "$target_sha")"
  else
    log "Skip security audit（mode=$security_audit_mode；对比 $BASE_REF 未检测到依赖清单变更）"
  fi

  echo
  log "Summary"
  echo "  branch: $branch"
  echo "  tests: $test_url"
  if [ -n "$security_url" ]; then
    echo "  security-audit: $security_url"
  else
    echo "  security-audit: skipped"
  fi
}

main "$@"
