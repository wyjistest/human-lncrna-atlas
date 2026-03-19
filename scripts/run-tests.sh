#!/bin/bash
# Human LncRNA Atlas - 测试运行脚本
# 统一测试入口（支持 CI 对齐检查 + 可选 E2E）

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(dirname "$SCRIPT_DIR")"
BACKEND_DIR="$PROJECT_ROOT/frontend/backend"
FRONTEND_DIR="$PROJECT_ROOT/frontend/web"

# 可选：覆盖服务地址（默认本地开发端口）
API_BASE_URL="${API_BASE_URL:-http://localhost:8000}"
BASE_URL="${BASE_URL:-http://localhost:5173}"

normalize_backend_origin_url() {
    local raw="${1:-}"
    raw="${raw%/}"
    if [[ "$raw" == */api/v1 ]]; then
        raw="${raw%/api/v1}"
    fi
    echo "$raw"
}

# 兼容本地代理环境：默认绕过 localhost/127.0.0.1，避免 curl 走 http_proxy 导致卡住。
DEFAULT_NO_PROXY="127.0.0.1,localhost,::1"
export NO_PROXY="${NO_PROXY:-$DEFAULT_NO_PROXY}"
export no_proxy="${no_proxy:-$DEFAULT_NO_PROXY}"

# 颜色定义
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

RUN_TESTS_SUMMARY_PATH="${RUN_TESTS_SUMMARY_PATH:-}"
RUN_TESTS_SUMMARY_JSON_PATH="${RUN_TESTS_SUMMARY_JSON_PATH:-}"
RUN_TESTS_ARTIFACT_DIR="${RUN_TESTS_ARTIFACT_DIR:-}"
RUN_TESTS_STAGE_LOGS_DIR="${RUN_TESTS_STAGE_LOGS_DIR:-}"
RUN_TESTS_SUMMARY_ENABLED=0
RUN_TESTS_SUMMARY_ROWS_FILE=""
RUN_TESTS_SUMMARY_JSON_ROWS_FILE=""
RUN_TESTS_SUMMARY_TOTAL=0
RUN_TESTS_SUMMARY_FAILED=0
RUN_TESTS_SUMMARY_MODE=""
RUN_TESTS_SUMMARY_STARTED_AT=""
RUN_TESTS_SUMMARY_FIRST_FAILED_STAGE=""
RUN_TESTS_SUMMARY_ACTIVE="${RUN_TESTS_SUMMARY_ACTIVE:-0}"

echo "=========================================="
echo "  Human LncRNA Atlas - 测试套件"
echo "=========================================="
echo ""

escape_summary_cell() {
    local value="${1:-}"
    value="${value//$'\n'/<br>}"
    value="${value//|/\\|}"
    printf '%s' "$value"
}

escape_json_string() {
    local value="${1:-}"
    value="${value//\\/\\\\}"
    value="${value//\"/\\\"}"
    value="${value//$'\n'/\\n}"
    value="${value//$'\r'/\\r}"
    value="${value//$'\t'/\\t}"
    printf '%s' "$value"
}

json_string_or_null() {
    local value="${1:-}"
    if [ -z "$value" ]; then
        printf 'null'
        return 0
    fi
    printf '"%s"' "$(escape_json_string "$value")"
}

normalize_stage_id() {
    local raw="${1:-stage}"
    local normalized
    normalized="$(printf '%s' "$raw" | tr '[:upper:]' '[:lower:]' | sed -E 's/[^a-z0-9]+/-/g; s/^-+//; s/-+$//')"
    if [ -z "$normalized" ]; then
        normalized="stage"
    fi
    printf '%s' "$normalized"
}

is_github_actions() {
    [ "${GITHUB_ACTIONS:-}" = "true" ]
}

announce_github_stage_start() {
    local stage="$1"
    local stage_id="$2"
    local hint="${3:-}"
    if ! is_github_actions; then
        return 0
    fi
    echo "::notice::[run-tests][${stage_id}] Starting ${stage} (${hint})"
    echo "::group::run-tests [${stage_id}] ${stage}"
}

announce_github_stage_end() {
    if ! is_github_actions; then
        return 0
    fi
    echo "::endgroup::"
}

announce_github_stage_failure() {
    local stage="$1"
    local stage_id="$2"
    local hint="${3:-}"
    local log_relpath="${4:-}"
    if ! is_github_actions; then
        return 0
    fi

    local message="[run-tests][${stage_id}] Failed ${stage}"
    if [ -n "$hint" ]; then
        message="${message} (${hint})"
    fi
    if [ -n "$log_relpath" ]; then
        message="${message}; log=${log_relpath}"
    fi
    echo "::error::${message}"
}

resolve_stage_log_relpath() {
    local log_path="${1:-}"
    if [ -z "$log_path" ]; then
        return 0
    fi

    if [ -n "$RUN_TESTS_ARTIFACT_DIR" ] && [[ "$log_path" == "$RUN_TESTS_ARTIFACT_DIR/"* ]]; then
        printf '%s' "${log_path#"$RUN_TESTS_ARTIFACT_DIR"/}"
        return 0
    fi

    printf '%s/%s' "$(basename "$(dirname "$log_path")")" "$(basename "$log_path")"
}

init_run_tests_summary() {
    local mode="${1:-unknown}"
    if [ -n "$RUN_TESTS_ARTIFACT_DIR" ]; then
        mkdir -p "$RUN_TESTS_ARTIFACT_DIR"
        if [ -z "$RUN_TESTS_SUMMARY_JSON_PATH" ]; then
            RUN_TESTS_SUMMARY_JSON_PATH="$RUN_TESTS_ARTIFACT_DIR/run-tests-summary.json"
        fi
        if [ -z "$RUN_TESTS_STAGE_LOGS_DIR" ]; then
            RUN_TESTS_STAGE_LOGS_DIR="$RUN_TESTS_ARTIFACT_DIR/run-tests-stage-logs"
        fi
    fi

    if [ -z "$RUN_TESTS_SUMMARY_PATH" ] && [ -z "$RUN_TESTS_SUMMARY_JSON_PATH" ] && [ -z "$RUN_TESTS_STAGE_LOGS_DIR" ]; then
        return 0
    fi
    if [ "$RUN_TESTS_SUMMARY_ACTIVE" = "1" ]; then
        return 0
    fi

    if [ -n "$RUN_TESTS_SUMMARY_PATH" ]; then
        mkdir -p "$(dirname "$RUN_TESTS_SUMMARY_PATH")"
        RUN_TESTS_SUMMARY_ROWS_FILE="$(mktemp "${TMPDIR:-/tmp}/run-tests-summary.XXXXXX")"
    fi
    if [ -n "$RUN_TESTS_SUMMARY_JSON_PATH" ]; then
        mkdir -p "$(dirname "$RUN_TESTS_SUMMARY_JSON_PATH")"
        RUN_TESTS_SUMMARY_JSON_ROWS_FILE="$(mktemp "${TMPDIR:-/tmp}/run-tests-summary-json.XXXXXX")"
    fi
    if [ -n "$RUN_TESTS_STAGE_LOGS_DIR" ]; then
        mkdir -p "$RUN_TESTS_STAGE_LOGS_DIR"
    fi

    RUN_TESTS_SUMMARY_ENABLED=1
    RUN_TESTS_SUMMARY_TOTAL=0
    RUN_TESTS_SUMMARY_FAILED=0
    RUN_TESTS_SUMMARY_MODE="$mode"
    RUN_TESTS_SUMMARY_STARTED_AT="$(date -u +"%Y-%m-%dT%H:%M:%SZ")"
    RUN_TESTS_SUMMARY_FIRST_FAILED_STAGE=""
    RUN_TESTS_SUMMARY_ACTIVE=1
    export RUN_TESTS_SUMMARY_ACTIVE

    if [ -n "$RUN_TESTS_SUMMARY_PATH" ]; then
        {
            echo "# run-tests summary"
            echo
            echo "- Mode: \`$(escape_summary_cell "$mode")\`"
            echo "- Started at (UTC): \`$RUN_TESTS_SUMMARY_STARTED_AT\`"
            case "$mode" in
                ci)
                    echo "- Coverage: \`core checks only\`"
                    ;;
                ci-postgres)
                    echo "- Coverage: \`core checks + API snapshot baseline\`"
                    ;;
                ci-plus)
                    echo "- Coverage: \`core checks + mocked Playwright e2e-smoke\`"
                    ;;
                ci-full)
                    echo "- Coverage: \`ci-plus + dependency security audit\`"
                    ;;
            esac
            echo
            echo "| Stage | Status | Duration (s) | Hint |"
            echo "| --- | --- | ---: | --- |"
        } > "$RUN_TESTS_SUMMARY_PATH"
    fi
}

append_run_tests_summary_row() {
    local stage="${1:-}"
    local stage_id="${2:-}"
    local status="${3:-}"
    local duration_seconds="${4:-0}"
    local hint="${5:-}"
    local started_at="${6:-}"
    local finished_at="${7:-}"
    local log_relpath="${8:-}"

    if [ "$RUN_TESTS_SUMMARY_ENABLED" != "1" ]; then
        return 0
    fi

    RUN_TESTS_SUMMARY_TOTAL=$((RUN_TESTS_SUMMARY_TOTAL + 1))
    if [ "$status" != "PASS" ]; then
        RUN_TESTS_SUMMARY_FAILED=$((RUN_TESTS_SUMMARY_FAILED + 1))
        if [ -z "$RUN_TESTS_SUMMARY_FIRST_FAILED_STAGE" ]; then
            RUN_TESTS_SUMMARY_FIRST_FAILED_STAGE="$stage_id"
        fi
    fi

    if [ -n "$RUN_TESTS_SUMMARY_ROWS_FILE" ]; then
        printf '| %s | %s | %s | %s |\n' \
            "$(escape_summary_cell "$stage")" \
            "$(escape_summary_cell "$status")" \
            "$(escape_summary_cell "$duration_seconds")" \
            "$(escape_summary_cell "$hint")" \
            >> "$RUN_TESTS_SUMMARY_ROWS_FILE"
    fi

    if [ -n "$RUN_TESTS_SUMMARY_JSON_ROWS_FILE" ]; then
        printf '{ "stage_id": "%s", "name": "%s", "status": "%s", "duration_seconds": %s, "hint": %s, "started_at": %s, "finished_at": %s, "log_relpath": %s }\n' \
            "$(escape_json_string "$stage_id")" \
            "$(escape_json_string "$stage")" \
            "$(escape_json_string "$status")" \
            "$duration_seconds" \
            "$(json_string_or_null "$hint")" \
            "$(json_string_or_null "$started_at")" \
            "$(json_string_or_null "$finished_at")" \
            "$(json_string_or_null "$log_relpath")" \
            >> "$RUN_TESTS_SUMMARY_JSON_ROWS_FILE"
    fi
}

finalize_run_tests_summary() {
    local exit_code="${1:-0}"
    if [ "$RUN_TESTS_SUMMARY_ENABLED" != "1" ]; then
        return 0
    fi

    local passed=0
    local finished_at result
    passed=$((RUN_TESTS_SUMMARY_TOTAL - RUN_TESTS_SUMMARY_FAILED))
    finished_at="$(date -u +"%Y-%m-%dT%H:%M:%SZ")"
    result="failed"
    if [ "$exit_code" -eq 0 ]; then
        result="passed"
    fi

    if [ -n "$RUN_TESTS_SUMMARY_PATH" ] && [ -n "$RUN_TESTS_SUMMARY_ROWS_FILE" ]; then
        cat "$RUN_TESTS_SUMMARY_ROWS_FILE" >> "$RUN_TESTS_SUMMARY_PATH"
        {
            echo
            echo "- Result: **${result}**"
            echo "- Finished at (UTC): \`${finished_at}\`"
            echo "- Passed stages: ${passed}/${RUN_TESTS_SUMMARY_TOTAL}"
            echo "- Failed stages: ${RUN_TESTS_SUMMARY_FAILED}"
            if [ -n "$RUN_TESTS_SUMMARY_FIRST_FAILED_STAGE" ]; then
                echo "- First failed stage: \`${RUN_TESTS_SUMMARY_FIRST_FAILED_STAGE}\`"
            fi
        } >> "$RUN_TESTS_SUMMARY_PATH"
    fi

    if [ -n "$RUN_TESTS_SUMMARY_JSON_PATH" ] && [ -n "$RUN_TESTS_SUMMARY_JSON_ROWS_FILE" ]; then
        {
            echo "{"
            echo "  \"mode\": $(json_string_or_null "$RUN_TESTS_SUMMARY_MODE"),"
            echo "  \"result\": $(json_string_or_null "$result"),"
            echo "  \"started_at\": $(json_string_or_null "$RUN_TESTS_SUMMARY_STARTED_AT"),"
            echo "  \"finished_at\": $(json_string_or_null "$finished_at"),"
            echo "  \"passed_stages\": ${passed},"
            echo "  \"failed_stages\": ${RUN_TESTS_SUMMARY_FAILED},"
            echo "  \"first_failed_stage\": $(json_string_or_null "$RUN_TESTS_SUMMARY_FIRST_FAILED_STAGE"),"
            echo "  \"stages\": ["
            if [ -s "$RUN_TESTS_SUMMARY_JSON_ROWS_FILE" ]; then
                awk 'BEGIN { first = 1 } { if (!first) printf(",\n"); printf("    %s", $0); first = 0 } END { if (!first) printf("\n") }' "$RUN_TESTS_SUMMARY_JSON_ROWS_FILE"
            fi
            echo "  ]"
            echo "}"
        } > "$RUN_TESTS_SUMMARY_JSON_PATH"
    fi

    rm -f "$RUN_TESTS_SUMMARY_ROWS_FILE" "$RUN_TESTS_SUMMARY_JSON_ROWS_FILE"
    RUN_TESTS_SUMMARY_ROWS_FILE=""
    RUN_TESTS_SUMMARY_JSON_ROWS_FILE=""
}

run_stage_with_summary() {
    local stage="$1"
    local hint="$2"
    local fn="$3"
    shift 3 || true

    local stage_id started_at_epoch ended_at_epoch duration_seconds rc status
    local started_at finished_at log_path log_relpath
    stage_id="$(normalize_stage_id "$stage")"
    started_at="$(date -u +"%Y-%m-%dT%H:%M:%SZ")"
    started_at_epoch="$(date +%s)"
    status="PASS"
    log_path=""
    log_relpath=""
    if [ -n "$RUN_TESTS_STAGE_LOGS_DIR" ]; then
        log_path="$RUN_TESTS_STAGE_LOGS_DIR/${stage_id}.log"
        : > "$log_path"
        log_relpath="$(resolve_stage_log_relpath "$log_path")"
    fi

    announce_github_stage_start "$stage" "$stage_id" "$hint"
    if [ -n "$log_path" ]; then
        if "$fn" "$@" > >(tee -a "$log_path") 2> >(tee -a "$log_path" >&2); then
            rc=0
        else
            rc=$?
            status="FAIL"
        fi
    elif "$fn" "$@"; then
        rc=0
    else
        rc=$?
        status="FAIL"
    fi

    announce_github_stage_end
    ended_at_epoch="$(date +%s)"
    finished_at="$(date -u +"%Y-%m-%dT%H:%M:%SZ")"
    duration_seconds=$((ended_at_epoch - started_at_epoch))
    append_run_tests_summary_row "$stage" "$stage_id" "$status" "$duration_seconds" "$hint" "$started_at" "$finished_at" "$log_relpath"
    if [ "$status" != "PASS" ]; then
        announce_github_stage_failure "$stage" "$stage_id" "$hint" "$log_relpath"
    fi
    return "$rc"
}

require_cmd() {
    local cmd="$1"
    if ! command -v "$cmd" > /dev/null 2>&1; then
        echo -e "${RED}缺少依赖命令: ${cmd}${NC}"
        return 1
    fi
    return 0
}

ensure_frontend_deps() {
    require_cmd npm || return 1
    if [ ! -f "$FRONTEND_DIR/package-lock.json" ]; then
        echo -e "${RED}未找到前端锁文件: ${FRONTEND_DIR}/package-lock.json${NC}"
        return 1
    fi

    # 仅在 node_modules 缺失或检测到锁文件漂移时自动安装，避免每次都重装依赖导致本地过慢。
    if [ ! -d "$FRONTEND_DIR/node_modules" ]; then
        echo -e "${YELLOW}前端依赖未安装，执行 npm ci...${NC}"
        (cd "$FRONTEND_DIR" && npm ci)
        return 0
    fi

    # npm 会在 node_modules 下生成 `.package-lock.json`，代表“上次安装时的锁文件快照”。
    # 若 package-lock.json 比该快照更新，说明依赖已漂移（例如 git pull 更新了 lockfile 但未重装依赖）。
    local installed_lock="$FRONTEND_DIR/node_modules/.package-lock.json"
    if [ ! -f "$installed_lock" ]; then
        echo -e "${YELLOW}未找到 ${installed_lock}，执行 npm ci...${NC}"
        (cd "$FRONTEND_DIR" && npm ci)
        return 0
    fi

    if [ "$FRONTEND_DIR/package-lock.json" -nt "$installed_lock" ]; then
        echo -e "${YELLOW}检测到前端依赖可能已漂移（package-lock.json 更新），执行 npm ci...${NC}"
        (cd "$FRONTEND_DIR" && npm ci)
        return 0
    fi

    return 0
}

resolve_backend_python() {
    # 优先使用后端虚拟环境，避免依赖全局 Python（CI/本地更稳定）
    if [ -n "${BACKEND_PYTHON:-}" ]; then
        echo "$BACKEND_PYTHON"
        return 0
    fi

    if [ -x "$BACKEND_DIR/.venv/bin/python" ]; then
        echo "$BACKEND_DIR/.venv/bin/python"
        return 0
    fi
    if [ -x "$BACKEND_DIR/venv/bin/python" ]; then
        echo "$BACKEND_DIR/venv/bin/python"
        return 0
    fi

    # 本地自举：若开发机未创建后端 venv，且全局 Python 依赖不全（常见：缺 psycopg2/pytest），
    # 则自动创建 `frontend/backend/.venv`，降低本地 CI 使用门槛。
    #
    # 说明：
    # - CI 环境通常已由 workflow 显式 `pip install -r ...`，此处不应重复创建 venv。
    # - 如你使用 Conda/pyenv 等外部环境管理，可设置 `SKIP_BACKEND_VENV_BOOTSTRAP=1` 禁用自举，
    #   并通过 `BACKEND_PYTHON` 指向你的 Python 解释器。
    if [ "${SKIP_BACKEND_VENV_BOOTSTRAP:-}" != "1" ] && [ "${CI:-}" != "true" ] && [ "${CI:-}" != "1" ]; then
        local venv_dir="$BACKEND_DIR/.venv"
        local venv_python="$venv_dir/bin/python"
        if [ ! -x "$venv_python" ] && command -v python3 >/dev/null 2>&1; then
            echo -e "${YELLOW}[run-tests] 未检测到后端 venv，正在创建: ${venv_dir}${NC}" >&2
            if python3 -m venv "$venv_dir"; then
                echo -e "${GREEN}[run-tests] 已创建后端 venv: ${venv_dir}${NC}" >&2
            else
                echo -e "${RED}[run-tests] 后端 venv 创建失败；将回退到系统 python3（可能导致缺依赖失败）${NC}" >&2
            fi
        fi
        if [ -x "$venv_python" ]; then
            echo "$venv_python"
            return 0
        fi
    fi

    echo "python3"
}

ensure_backend_python() {
    local python_bin="$1"

    # python_bin 可能是绝对路径或命令名
    if [[ "$python_bin" == /* ]]; then
        if [ ! -x "$python_bin" ]; then
            echo -e "${RED}后端 Python 不可执行: ${python_bin}${NC}"
            return 1
        fi
    else
        require_cmd "$python_bin" || return 1
    fi

    return 0
}

backend_venv_dir_from_python() {
    local python_bin="$1"

    # 仅对后端目录内的 venv 做“依赖漂移自动修复”，避免误改全局 Python/Conda 环境。
    if [[ "$python_bin" != /* ]]; then
        return 1
    fi

    local bin_dir
    bin_dir="$(dirname "$python_bin")"
    local venv_dir
    venv_dir="$(dirname "$bin_dir")"

    if [[ "$venv_dir" == "$BACKEND_DIR/.venv" || "$venv_dir" == "$BACKEND_DIR/venv" ]]; then
        echo "$venv_dir"
        return 0
    fi

    return 1
}

compute_backend_deps_hash() {
    local python_bin="$1"

    # 用 Python 计算 sha256，避免依赖 sha256sum/shasum 的平台差异。
    (
        cd "$BACKEND_DIR"
        "$python_bin" - <<'PY'
import hashlib
from pathlib import Path

h = hashlib.sha256()
for name in ("requirements.txt", "requirements-dev.txt", "constraints.txt"):
    p = Path(name)
    if not p.exists():
        continue
    h.update(p.read_bytes())
    h.update(b"\n")

print(h.hexdigest())
PY
    )
}

ensure_backend_deps() {
    local python_bin="$1"
    local venv_dir
    local stamp_file
    local current_hash
    local previous_hash

    ensure_backend_python "$python_bin" || return 1

    if ! venv_dir="$(backend_venv_dir_from_python "$python_bin")"; then
        # 非后端 venv：不自动 pip install（避免意外污染全局环境）
        return 0
    fi

    stamp_file="${venv_dir}/.hla_requirements.sha256"
    current_hash="$(compute_backend_deps_hash "$python_bin")"
    previous_hash=""
    if [ -f "$stamp_file" ]; then
        previous_hash="$(cat "$stamp_file" 2>/dev/null || true)"
    fi

    if [ "$current_hash" = "$previous_hash" ]; then
        return 0
    fi

    echo -e "${YELLOW}检测到后端依赖可能已漂移（requirements/constraints 更新），执行 pip install...${NC}"
    cd "$BACKEND_DIR"

    # 仅在漂移时同步依赖，避免每次 pre-push 都重装导致本地过慢。
    "$python_bin" -m pip install -r requirements-dev.txt -c constraints.txt
    printf "%s\n" "$current_hash" > "$stamp_file"
    return 0
}

ensure_backend_pytest() {
    local python_bin="$1"

    ensure_backend_python "$python_bin" || return 1

    ensure_backend_deps "$python_bin" || return 1

    if ! "$python_bin" -c "import pytest" > /dev/null 2>&1; then
        echo -e "${RED}后端 pytest 不可用（请在后端虚拟环境中安装依赖）${NC}"
        echo -e "${YELLOW}建议：cd ${BACKEND_DIR} && pip install -r requirements-dev.txt -c constraints.txt${NC}"
        return 1
    fi

    return 0
}

ensure_backend_ruff() {
    local ruff_bin="$1"

    # ruff_bin 可能是绝对路径或命令名
    if [[ "$ruff_bin" == /* ]]; then
        if [ ! -x "$ruff_bin" ]; then
            echo -e "${RED}后端 ruff 不可执行: ${ruff_bin}${NC}"
            return 1
        fi
    else
        require_cmd "$ruff_bin" || return 1
    fi

    return 0
}

ensure_backend_pip_audit() {
    local python_bin="$1"

    ensure_backend_python "$python_bin" || return 1

    ensure_backend_deps "$python_bin" || return 1

    if ! "$python_bin" -c "import pip_audit" > /dev/null 2>&1; then
        echo -e "${RED}后端 pip-audit 不可用（请在后端虚拟环境中安装依赖）${NC}"
        echo -e "${YELLOW}建议：cd ${BACKEND_DIR} && pip install pip-audit${NC}"
        return 1
    fi

    return 0
}

# 运行后端 Lint（ruff）
run_backend_lint() {
    echo -e "${YELLOW}运行后端 Lint (ruff check)...${NC}"
    local python_bin
    python_bin="$(resolve_backend_python)"

    ensure_backend_deps "$python_bin" || return 1

    local ruff_bin="ruff"
    if [[ "$python_bin" == /* ]]; then
        ruff_bin="$(dirname "$python_bin")/ruff"
    fi

    ensure_backend_ruff "$ruff_bin" || {
        echo -e "${YELLOW}建议：cd ${BACKEND_DIR} && pip install -r requirements-dev.txt -c constraints.txt${NC}"
        return 1
    }

    cd "$BACKEND_DIR"

    if "$ruff_bin" check .; then
        echo -e "${GREEN}后端 Lint 通过!${NC}"
        return 0
    else
        echo -e "${RED}后端 Lint 失败${NC}"
        return 1
    fi
}

# 检查服务状态
check_services() {
    echo -e "${YELLOW}检查服务状态...${NC}"
    require_cmd curl || return 1

    local backend_health_url="${API_BASE_URL%/}/health"
    local frontend_url="${BASE_URL%/}"

    # 检查后端 (-f: fail on HTTP errors, -sS: silent but show errors)
    if curl -fsS --connect-timeout 2 --max-time 5 "$backend_health_url" > /dev/null 2>&1; then
        echo -e "  后端 (${API_BASE_URL}): ${GREEN}运行中${NC}"
    else
        echo -e "  后端 (${API_BASE_URL}): ${RED}未运行或返回错误${NC}"
        echo -e "  ${YELLOW}请先启动后端: cd frontend/backend && python3 -m uvicorn main:app --port 8000${NC}"
        echo -e "  ${YELLOW}如使用非 8000 端口，请同步设置 API_BASE_URL${NC}"
        return 1
    fi

    # 检查前端 (-f: fail on HTTP errors like 502, -sS: silent but show errors)
    if curl -fsS --connect-timeout 2 --max-time 5 "$frontend_url" > /dev/null 2>&1; then
        echo -e "  前端 (${BASE_URL}): ${GREEN}运行中${NC}"
    else
        echo -e "  前端 (${BASE_URL}): ${RED}未运行或返回错误${NC}"
        echo -e "  ${YELLOW}请先启动前端: cd frontend/web && npm run dev${NC}"
        echo -e "  ${YELLOW}如使用非 5173 端口，请同步设置 BASE_URL${NC}"
        return 1
    fi

    echo ""
    return 0
}

run_backend_security_audit() {
    echo -e "${YELLOW}运行后端依赖安全审计 (pip-audit --strict)...${NC}"
    local python_bin
    python_bin="$(resolve_backend_python)"
    ensure_backend_pip_audit "$python_bin" || return 1

    cd "$BACKEND_DIR"

    if "$python_bin" -m pip_audit -r requirements.txt --strict --progress-spinner off; then
        echo -e "${GREEN}后端依赖安全审计通过!${NC}"
        return 0
    else
        echo -e "${RED}后端依赖安全审计失败（发现漏洞）${NC}"
        return 1
    fi
}

# 运行后端 API 合同测试 (需要服务运行)
run_backend_tests() {
    echo -e "${YELLOW}运行后端 API 合同测试...${NC}"
    local python_bin
    local backend_origin_url
    python_bin="$(resolve_backend_python)"
    backend_origin_url="$(normalize_backend_origin_url "$API_BASE_URL")"
    ensure_backend_pytest "$python_bin" || return 1

    cd "$BACKEND_DIR"

    # integration 测试默认是 opt-in（见 frontend/backend/tests/conftest.py）
    if RUN_INTEGRATION_TESTS=1 TEST_API_URL="$backend_origin_url" "$python_bin" -m pytest tests/test_api_contracts.py -v --tb=short; then
        echo -e "${GREEN}后端 API 测试通过!${NC}"
        return 0
    else
        echo -e "${RED}后端 API 测试失败${NC}"
        return 1
    fi
}

# 运行后端单元测试 (无外部依赖)
run_backend_unit_tests() {
    echo -e "${YELLOW}运行后端单元测试 (pytest -m unit)...${NC}"
    local python_bin
    python_bin="$(resolve_backend_python)"
    ensure_backend_pytest "$python_bin" || return 1

    cd "$BACKEND_DIR"

    if "$python_bin" -m pytest -m unit -v --tb=short; then
        echo -e "${GREEN}后端单元测试通过!${NC}"
        return 0
    else
        echo -e "${RED}后端单元测试失败${NC}"
        return 1
    fi
}

run_backend_checks() {
    echo -e "${YELLOW}运行后端导入与语法检查（对齐 CI）...${NC}"
    local python_bin
    python_bin="$(resolve_backend_python)"
    ensure_backend_python "$python_bin" || return 1
    ensure_backend_deps "$python_bin" || return 1

    cd "$BACKEND_DIR"

    "$python_bin" -c "from app.core.config import settings; print('Config loaded')" || return 1
    "$python_bin" -c "from app.core.database import engine; print('Database module loaded')" || return 1
    "$python_bin" -c "from app.core.cache import cache; print('Cache module loaded')" || return 1
    "$python_bin" -c "from app.core.exceptions import sanitize_db_error; print('Exceptions module loaded')" || return 1
    "$python_bin" -c "import main; print('Main app loaded')" || return 1

    "$python_bin" -m py_compile main.py || return 1
    find app -name "*.py" -exec "$python_bin" -m py_compile {} \; || return 1

    echo -e "${GREEN}后端导入与语法检查通过!${NC}"
    return 0
}

run_etl_checks() {
    echo -e "${YELLOW}运行 ETL 输入校验单元测试 (pytest etl/tests)...${NC}"
    local python_bin
    python_bin="$(resolve_backend_python)"
    ensure_backend_pytest "$python_bin" || return 1

    cd "$PROJECT_ROOT"

    if "$python_bin" -m pytest -q etl/tests; then
        echo -e "${GREEN}ETL 单元测试通过!${NC}"
        return 0
    else
        echo -e "${RED}ETL 单元测试失败${NC}"
        return 1
    fi
}

run_scripts_smoke_tests() {
    cd "$PROJECT_ROOT"

    echo -e "${YELLOW}运行脚本冒烟测试（离线资源下载脚本）...${NC}"
    if ! bash scripts/genomes/tests/test_download_igv_assets.sh; then
        echo -e "${RED}脚本冒烟测试失败（离线资源下载）${NC}"
        return 1
    fi

    echo -e "${YELLOW}运行脚本冒烟测试（Research 导出脚本语法检查）...${NC}"
    require_cmd python3 || return 1

    # 说明：此处只做语法检查（py_compile / bash -n），不执行 DB 查询或生成产物。
    local had_any=false

    local old_nullglob
    old_nullglob="$(shopt -p nullglob || true)"
    shopt -s nullglob

    local py_files=(scripts/research/*.py)
    if [ ${#py_files[@]} -gt 0 ]; then
        had_any=true
        for f in "${py_files[@]}"; do
            if ! python3 -m py_compile "$f"; then
                echo -e "${RED}脚本冒烟测试失败（Research Python 语法检查）：${f}${NC}"
                $old_nullglob || true
                return 1
            fi
        done
    fi

    local sh_files=(scripts/research/generate_*_sample_baseline_local.sh)
    if [ ${#sh_files[@]} -gt 0 ]; then
        had_any=true
        for f in "${sh_files[@]}"; do
            if ! bash -n "$f"; then
                echo -e "${RED}脚本冒烟测试失败（Research Bash 语法检查）：${f}${NC}"
                $old_nullglob || true
                return 1
            fi
        done
    fi

    $old_nullglob || true
    if [ "$had_any" != "true" ]; then
        echo -e "${YELLOW}未找到 scripts/research/*.py 或 generate_*_sample_baseline_local.sh，跳过 Research 语法检查${NC}"
    fi

    echo -e "${GREEN}脚本冒烟测试通过!${NC}"
    return 0
}

run_scripts_unit_tests() {
    cd "$PROJECT_ROOT"

    echo -e "${YELLOW}运行脚本单元测试（scripts/tests）...${NC}"

	    local tests=(
	        "scripts/tests/test_run_tests_frontend_deps.sh"
	        "scripts/tests/test_frontend_entry_bundle_budget.sh"
	        "scripts/tests/test_frontend_bundle_size_report.sh"
	        "scripts/tests/test_frontend_bundle_size_snapshot_json.sh"
	        "scripts/tests/test_frontend_bundle_size_compare_report.sh"
	        "scripts/tests/test_frontend_entry_preloads_regression_gate.sh"
	        "scripts/tests/test_compare_performance_metrics_gate.sh"
	        "scripts/tests/test_aggregate_performance_metrics_median.sh"
	        "scripts/tests/test_perf_report_scenario_drift.sh"
        "scripts/tests/test_run_tests_backend_deps.sh"
        "scripts/tests/test_run_tests_backend_checks_propagates_failures.sh"
        "scripts/tests/test_run_tests_backend_bootstrap_venv.sh"
        "scripts/tests/test_run_tests_ci_summary.sh"
        "scripts/tests/test_run_tests_ci_github_annotations.sh"
        "scripts/tests/test_run_tests_ci_summary_success.sh"
        "scripts/tests/test_checkout_tarball_script.sh"
        "scripts/tests/test_check_docs_status_markers.sh"
        "scripts/tests/test_check_docs_status_markers_marker_position.sh"
        "scripts/tests/test_gh_push_commit_range_dry_run.sh"
        "scripts/tests/test_run_tests_usage_includes_frontend_baselines.sh"
        "scripts/tests/test_run_tests_usage_includes_research_baselines.sh"
        "scripts/tests/test_verify_research_baselines_help.sh"
    )

    local missing=false
    for t in "${tests[@]}"; do
        if [ ! -f "$t" ]; then
            echo -e "${YELLOW}SKIP  未找到: ${t}${NC}"
            missing=true
        fi
    done

    if [ "$missing" = "true" ]; then
        echo -e "${YELLOW}部分 scripts/tests 缺失，跳过脚本单元测试${NC}"
        return 0
    fi

    for t in "${tests[@]}"; do
        # 兼容 git hooks 环境：避免 GIT_DIR/GIT_WORK_TREE 污染导致 tests 误操作主仓库。
        # 说明：脚本单元测试会在临时目录中构造最小仓库结构并验证 run-tests 自举逻辑；
        # 若外部环境设置了 BACKEND_PYTHON，会污染这些测试并导致误判。
        if ! env -u GIT_DIR -u GIT_WORK_TREE -u BACKEND_PYTHON bash "$t"; then
            echo -e "${RED}脚本单元测试失败: ${t}${NC}"
            return 1
        fi
    done

    echo -e "${GREEN}脚本单元测试通过!${NC}"
    return 0
}

run_research_baselines_checks() {
    echo -e "${YELLOW}校验 Research baselines（本地可选；会创建临时 sample DB）...${NC}"
    require_cmd python3 || return 1

    cd "$PROJECT_ROOT"
    if python3 scripts/verify_research_baselines.py --mode local; then
        echo -e "${GREEN}Research baselines 校验通过!${NC}"
        return 0
    else
        echo -e "${RED}Research baselines 校验失败${NC}"
        return 1
    fi
}

run_frontend_baselines_checks() {
    echo -e "${YELLOW}校验 Frontend bundle baselines（本地可选；会执行 npm run build）...${NC}"

    local baseline="${FRONTEND_BUNDLE_BASELINE:-${PROJECT_ROOT}/docs/baselines/frontend/bundle-sizes.baseline.json}"
    if [ ! -f "$baseline" ]; then
        echo -e "${RED}未找到 baseline 文件：${baseline}${NC}"
        echo -e "${YELLOW}提示：可在前端目录生成：cd frontend/web && npm run build && node scripts/report-bundle-sizes.mjs --json \"../../docs/baselines/frontend/bundle-sizes.baseline.json\"${NC}"
        return 1
    fi

    local current="${FRONTEND_BUNDLE_CURRENT:-${PROJECT_ROOT}/test-results/bundle-sizes.current.json}"
    mkdir -p "${PROJECT_ROOT}/test-results"

    run_frontend_build || return 1

    cd "$FRONTEND_DIR"
    if node scripts/report-bundle-sizes.mjs --json "$current" >/dev/null; then
        if node scripts/compare-bundle-sizes.mjs "$baseline" "$current"; then
            echo -e "${GREEN}Frontend bundle baselines 校验通过!${NC}"
            return 0
        fi
    fi

    echo -e "${RED}Frontend bundle baselines 校验失败${NC}"
    echo -e "${YELLOW}current snapshot：${current}${NC}"
    return 1
}

run_api_snapshot_baseline_checks() {
    echo -e "${YELLOW}校验 API snapshot baseline（本地 sample DB）...${NC}"
    require_cmd python3 || return 1

    if (cd "$PROJECT_ROOT" && python3 scripts/verify_baselines.py --mode local); then
        echo -e "${GREEN}API snapshot baseline 校验通过!${NC}"
        return 0
    fi

    echo -e "${RED}API snapshot baseline 校验失败${NC}"
    return 1
}

run_docs_checks() {
    echo -e "${YELLOW}运行文档命令漂移检查...${NC}"
    require_cmd python3 || return 1

    cd "$PROJECT_ROOT"
    if python3 scripts/check_docs_commands.py; then
        echo -e "${GREEN}文档命令漂移检查通过!${NC}"
    else
        echo -e "${RED}文档命令漂移检查失败${NC}"
        return 1
    fi

    echo -e "${YELLOW}运行文档标题伪影检查...${NC}"
    if python3 scripts/check_docs_heading_artifacts.py; then
        echo -e "${GREEN}文档标题伪影检查通过!${NC}"
    else
        echo -e "${RED}文档标题伪影检查失败${NC}"
        return 1
    fi

    echo -e "${YELLOW}运行文档状态标注检查...${NC}"
    if python3 scripts/check_docs_status_markers.py; then
        echo -e "${GREEN}文档状态标注检查通过!${NC}"
        return 0
    else
        echo -e "${RED}文档状态标注检查失败${NC}"
        return 1
    fi
}

run_db_migrations_verify() {
    echo -e "${YELLOW}运行数据库迁移文件校验 (db_migrate.sh verify)...${NC}"
    local script_path="$BACKEND_DIR/scripts/db_migrate.sh"

    if [ ! -f "$script_path" ]; then
        echo -e "${RED}未找到迁移脚本: ${script_path}${NC}"
        return 1
    fi

    if bash "$script_path" verify; then
        echo -e "${GREEN}数据库迁移文件校验通过!${NC}"
        return 0
    else
        echo -e "${RED}数据库迁移文件校验失败${NC}"
        return 1
    fi
}

# 运行前端单元测试
run_frontend_unit_tests() {
    echo -e "${YELLOW}运行前端单元测试...${NC}"
    ensure_frontend_deps || return 1
    cd "$FRONTEND_DIR"

    if npm run test:run; then
        echo -e "${GREEN}前端单元测试通过!${NC}"
        return 0
    else
        echo -e "${RED}前端单元测试失败${NC}"
        return 1
    fi
}

run_frontend_security_audit() {
    echo -e "${YELLOW}运行前端依赖安全审计 (npm audit --audit-level=high)...${NC}"
    ensure_frontend_deps || return 1
    cd "$FRONTEND_DIR"

    if npm audit --registry=https://registry.npmjs.org --audit-level=high; then
        echo -e "${GREEN}前端依赖安全审计通过!${NC}"
        return 0
    else
        echo -e "${RED}前端依赖安全审计失败（发现 high/critical 漏洞）${NC}"
        return 1
    fi
}

run_frontend_lint() {
    echo -e "${YELLOW}运行前端 Lint (ESLint)...${NC}"
    ensure_frontend_deps || return 1
    cd "$FRONTEND_DIR"

    if npm run lint; then
        echo -e "${GREEN}前端 Lint 通过!${NC}"
        return 0
    else
        echo -e "${RED}前端 Lint 失败${NC}"
        return 1
    fi
}

run_frontend_build() {
    echo -e "${YELLOW}运行前端构建 (Vite build)...${NC}"
    ensure_frontend_deps || return 1
    cd "$FRONTEND_DIR"

    if npm run build; then
        echo -e "${GREEN}前端构建通过!${NC}"
        return 0
    else
        echo -e "${RED}前端构建失败${NC}"
        return 1
    fi
}

# 运行 Playwright tests（本地 preview + mocked；不依赖后端/DB）
run_frontend_playwright_preview_tests() {
    local project="${1:-chromium}"
    shift || true
    local specs=("$@")

    if [ "${#specs[@]}" -eq 0 ]; then
        echo -e "${RED}内部错误：未提供 Playwright spec 列表${NC}"
        return 1
    fi

    echo -e "${YELLOW}运行前端 Playwright tests（preview + mocked；browser=${project}）...${NC}"
    ensure_frontend_deps || return 1
    require_cmd curl || return 1

    cd "$FRONTEND_DIR"

    # 确保 dist 存在（CI smoke 依赖 Vite build artifact + preview）
    if [ ! -d "dist" ] || [ ! -f "dist/index.html" ]; then
        echo -e "${YELLOW}未找到 dist/，先执行 npm run build...${NC}"
        npm run build || return 1
    fi

    local default_port=5173
    local port="$default_port"

    # 通过本地 preview server + Playwright 进行验证。
    # 为了保持与 CI 一致，默认使用 5173；但允许通过 BASE_URL 提供自定义端口（仅限 localhost/127.0.0.1）。
    if [ -n "${BASE_URL:-}" ]; then
        if [[ "${BASE_URL}" =~ ^http://(localhost|127\.0\.0\.1)(:([0-9]+))?(/.*)?$ ]]; then
            if [ -n "${BASH_REMATCH[3]:-}" ]; then
                port="${BASH_REMATCH[3]}"
            fi
        else
            echo -e "${YELLOW}仅支持本地 preview server。忽略 BASE_URL=${BASE_URL}${NC}"
            echo -e "${YELLOW}如需自定义端口，请设为 http://127.0.0.1:<port> 或 http://localhost:<port>${NC}"
        fi
    fi

    local base_url="http://127.0.0.1:${port}"

    # 与 CI 一致：使用 strictPort。若端口已被占用，直接 fail-fast。
    if curl -fsS "${base_url}/" > /dev/null 2>&1; then
        echo -e "${RED}端口 ${port} 已被占用（${base_url} 可访问），请先停止占用该端口的服务。${NC}"
        return 1
    fi

    npm run preview -- --host 127.0.0.1 --port "${port}" --strictPort &
    local preview_pid=$!

    local timeout=60
    while ! curl -fsS "${base_url}/" > /dev/null 2>&1; do
        if [ $timeout -le 0 ]; then
            echo -e "${RED}前端 preview server 未在预期时间内就绪${NC}"
            kill "$preview_pid" > /dev/null 2>&1 || true
            return 1
        fi
        sleep 2
        timeout=$((timeout - 2))
    done

    local extra_args=()
    if [ "${PLAYWRIGHT_UPDATE_SNAPSHOTS:-}" = "1" ] || [ "${PLAYWRIGHT_UPDATE_SNAPSHOTS:-}" = "true" ]; then
        extra_args+=(--update-snapshots)
        echo -e "${YELLOW}已启用 --update-snapshots（将更新 Playwright 快照基线）${NC}"
    fi

    local failed=0
    if BASE_URL="$base_url" CI=true npx playwright test "${specs[@]}" --project="$project" --reporter=list "${extra_args[@]}"; then
        echo -e "${GREEN}Playwright tests 通过!${NC}"
    else
        failed=1
        echo -e "${RED}Playwright tests 失败${NC}"
        echo -e "${YELLOW}若提示缺少浏览器，可运行：cd ${FRONTEND_DIR} && npx playwright install ${project}${NC}"
    fi

    kill "$preview_pid" > /dev/null 2>&1 || true
    wait "$preview_pid" > /dev/null 2>&1 || true

    return $failed
}

# 运行 E2E Smoke（完全 mocked，对齐 CI；不依赖后端/DB）
run_frontend_e2e_smoke_tests() {
    local project="${1:-chromium}"
    run_frontend_playwright_preview_tests "$project" \
        e2e/lncrna-chipseq-overlap-query-too-broad.spec.ts \
        e2e/genes-smoke.spec.ts \
        e2e/regulations-smoke.spec.ts \
        e2e/stats-smoke.spec.ts \
        e2e/diseases-smoke.spec.ts \
        e2e/analysis-smoke.spec.ts \
        e2e/conservation-smoke.spec.ts \
        e2e/chipseq-compare-smoke.spec.ts \
        e2e/chipseq-compare-journey-smoke.spec.ts \
        e2e/visualization-hub-smoke.spec.ts \
        e2e/admin-monitoring-smoke.spec.ts \
        e2e/admin-cache-smoke.spec.ts \
        e2e/admin-materialized-views-smoke.spec.ts
}

run_ci_core_checks() {
    local include_e2e_smoke="${1:-false}"
    local include_security_audit="${2:-false}"
    local include_api_snapshot_baseline="${3:-false}"
    local failed=0

    run_stage_with_summary "Backend lint" "ruff check" run_backend_lint || failed=1
    echo ""
    run_stage_with_summary "Backend checks" "import + py_compile checks" run_backend_checks || failed=1
    echo ""
    run_stage_with_summary "ETL checks" "pytest -q etl/tests" run_etl_checks || failed=1
    echo ""
    run_stage_with_summary "Scripts smoke" "offline/download + research syntax smoke" run_scripts_smoke_tests || failed=1
    echo ""
    run_stage_with_summary "Scripts unit" "scripts/tests shell regressions" run_scripts_unit_tests || failed=1
    echo ""
    run_stage_with_summary "Docs checks" "docs drift / heading / status markers" run_docs_checks || failed=1
    echo ""
    run_stage_with_summary "DB migrations verify" "frontend/backend/scripts/db_migrate.sh verify" run_db_migrations_verify || failed=1
    echo ""
    run_stage_with_summary "Backend unit tests" "pytest -m unit" run_backend_unit_tests || failed=1
    if [ "$include_api_snapshot_baseline" = "true" ]; then
        echo ""
        run_stage_with_summary "API snapshot baseline" "python3 scripts/verify_baselines.py --mode local" run_api_snapshot_baseline_checks || failed=1
    fi
    echo ""
    run_stage_with_summary "Frontend unit tests" "npm run test:run" run_frontend_unit_tests || failed=1
    echo ""
    run_stage_with_summary "Frontend lint" "npm run lint" run_frontend_lint || failed=1
    echo ""
    run_stage_with_summary "Frontend build" "npm run build" run_frontend_build || failed=1

    if [ "$include_e2e_smoke" = "true" ]; then
        echo ""
        run_stage_with_summary "Frontend e2e smoke" "Playwright mocked smoke (chromium)" run_frontend_e2e_smoke_tests || failed=1
    fi

    if [ "$include_security_audit" = "true" ]; then
        echo ""
        run_stage_with_summary "Backend security audit" "pip-audit --strict" run_backend_security_audit || failed=1
        echo ""
        run_stage_with_summary "Frontend security audit" "npm audit --audit-level=high" run_frontend_security_audit || failed=1
    fi

    return "$failed"
}

# A11y Smoke（axe-core；完全 mocked，不依赖后端/DB）
run_frontend_e2e_a11y_smoke_tests() {
    local project="${1:-chromium}"
    run_frontend_playwright_preview_tests "$project" e2e/a11y-smoke.spec.ts
}

# Visual regression Smoke（Playwright screenshots；完全 mocked，不依赖后端/DB）
run_frontend_e2e_visual_smoke_tests() {
    local project="${1:-chromium}"
    run_frontend_playwright_preview_tests "$project" e2e/visual-regression-smoke.spec.ts
}

# Performance audit（需要可用后端；仅建议手动/CI workflow_dispatch 运行）
run_frontend_performance_audit() {
    echo -e "${YELLOW}运行前端 Performance audit（Playwright performance suite）...${NC}"
    ensure_frontend_deps || return 1
    require_cmd curl || return 1

    cd "$FRONTEND_DIR"

    # 确保 dist 存在（performance suite 默认依赖 baseURL 指向可访问的前端入口）
    if [ ! -d "dist" ] || [ ! -f "dist/index.html" ]; then
        echo -e "${YELLOW}未找到 dist/，先执行 npm run build...${NC}"
        npm run build || return 1
    fi

    local default_port=5173
    local port="$default_port"

    # 与 e2e-smoke 保持一致：仅支持本地 preview server，且默认 strictPort 5173。
    if [ -n "${BASE_URL:-}" ]; then
        if [[ "${BASE_URL}" =~ ^http://(localhost|127\.0\.0\.1)(:([0-9]+))?(/.*)?$ ]]; then
            if [ -n "${BASH_REMATCH[3]:-}" ]; then
                port="${BASH_REMATCH[3]}"
            fi
        else
            echo -e "${YELLOW}performance-audit 仅支持本地 preview server。忽略 BASE_URL=${BASE_URL}${NC}"
            echo -e "${YELLOW}如需自定义端口，请设为 http://127.0.0.1:<port> 或 http://localhost:<port>${NC}"
        fi
    fi

    local base_url="http://127.0.0.1:${port}"

    if curl -fsS "${base_url}/" > /dev/null 2>&1; then
        echo -e "${RED}端口 ${port} 已被占用（${base_url} 可访问），请先停止占用该端口的服务。${NC}"
        return 1
    fi

    npm run preview -- --host 127.0.0.1 --port "${port}" --strictPort &
    local preview_pid=$!

    local timeout=60
    while ! curl -fsS "${base_url}/" > /dev/null 2>&1; do
        if [ $timeout -le 0 ]; then
            echo -e "${RED}前端 preview server 未在预期时间内就绪${NC}"
            kill "$preview_pid" > /dev/null 2>&1 || true
            return 1
        fi
        sleep 2
        timeout=$((timeout - 2))
    done

    local api_base_url="${API_BASE_URL:-http://127.0.0.1:8000}"
    if ! curl -fsS "${api_base_url}/health" > /dev/null 2>&1; then
        echo -e "${RED}后端健康检查失败：${api_base_url}/health 不可访问${NC}"
        echo -e "${YELLOW}提示：performance-audit 需要可用后端（可通过 API_BASE_URL 覆盖）。${NC}"
        kill "$preview_pid" > /dev/null 2>&1 || true
        wait "$preview_pid" > /dev/null 2>&1 || true
        return 1
    fi

    local failed=0
    local runs="${PERF_AUDIT_RUNS:-3}"
    if ! [[ "$runs" =~ ^[0-9]+$ ]] || [ "$runs" -lt 1 ] || [ "$runs" -gt 10 ]; then
        echo -e "${RED}PERF_AUDIT_RUNS 必须是 1-10 的整数（当前: ${runs}）${NC}"
        kill "$preview_pid" > /dev/null 2>&1 || true
        wait "$preview_pid" > /dev/null 2>&1 || true
        return 1
    fi

    local report_files=()
    local i
    for ((i=1; i<=runs; i++)); do
        local report_path="test-results/performance-run-${i}.json"
        report_files+=("$report_path")
        echo -e "${YELLOW}Performance audit: run ${i}/${runs}（输出: ${report_path}）...${NC}"

        if ! BASE_URL="$base_url" API_BASE_URL="$api_base_url" PERF_REPORT_PATH="$report_path" CI=true npm run test:performance; then
            failed=1
            echo -e "${RED}Performance audit 失败（第 ${i}/${runs} 次 run 未通过）${NC}"
            break
        fi
    done

    if [ "$failed" -eq 0 ]; then
        if ! node scripts/aggregate-performance-metrics.js \
            --out test-results/performance-median-metrics.json \
            --inputs "${report_files[@]}"; then
            failed=1
            echo -e "${RED}Performance audit 失败（聚合 median 报告失败）${NC}"
        elif node scripts/compare-performance-metrics.js \
            --baseline performance-baseline-metrics.json \
            --current test-results/performance-median-metrics.json \
            --fail-on-regression \
            --regression-threshold 2 \
            --out test-results/performance-compare.txt; then
            echo -e "${GREEN}Performance audit 通过!${NC}"
        else
            failed=1
            echo -e "${RED}Performance audit 失败（检测到性能回归 >2%）${NC}"
        fi
    fi

    kill "$preview_pid" > /dev/null 2>&1 || true
    wait "$preview_pid" > /dev/null 2>&1 || true
    return $failed
}

# 运行 E2E 测试
run_e2e_tests() {
    echo -e "${YELLOW}运行 E2E 测试...${NC}"
    ensure_frontend_deps || return 1
    cd "$FRONTEND_DIR"

    if npm run test:e2e; then
        echo -e "${GREEN}E2E 测试通过!${NC}"
        return 0
    else
        echo -e "${RED}E2E 测试失败${NC}"
        return 1
    fi
}

# 主函数
main() {
    local failed=0
    local mode="${1:-smoke}"

    init_run_tests_summary "$mode"

    case "$mode" in
        security-audit)
            run_backend_security_audit || failed=1
            echo ""
            run_frontend_security_audit || failed=1
            ;;
        backend-lint)
            run_backend_lint || failed=1
            ;;
        backend-checks)
            run_backend_checks || failed=1
            ;;
        etl-checks)
            run_etl_checks || failed=1
            ;;
        backend)
            check_services || exit 1
            run_backend_tests || failed=1
            ;;
        status)
            check_services || failed=1
            ;;
        backend-unit)
            run_backend_unit_tests || failed=1
            ;;
        unit)
            run_frontend_unit_tests || failed=1
            ;;
        frontend-lint)
            run_frontend_lint || failed=1
            ;;
        frontend-build)
            run_frontend_build || failed=1
            ;;
        e2e)
            check_services || exit 1
            run_e2e_tests || failed=1
            ;;
        e2e-smoke)
            run_frontend_e2e_smoke_tests || failed=1
            ;;
        e2e-smoke-firefox)
            run_frontend_e2e_smoke_tests firefox || failed=1
            ;;
        e2e-a11y-smoke)
            run_frontend_e2e_a11y_smoke_tests || failed=1
            ;;
        e2e-visual-smoke)
            run_frontend_e2e_visual_smoke_tests || failed=1
            ;;
        performance-audit)
            run_frontend_performance_audit || failed=1
            ;;
        smoke)
            # 默认: 运行所有无外部依赖的单元测试
            run_backend_unit_tests || failed=1
            echo ""
            run_frontend_unit_tests || failed=1
            ;;
        ci)
            # 对齐 GitHub Actions `.github/workflows/test.yml` 的核心质量门禁（不含 secret scan / security-audit）
            run_ci_core_checks false false || failed=1
            ;;
        ci-postgres)
            # self-hosted fast path：在 ci 基础上追加 API snapshot baseline（本地临时 sample DB）。
            run_ci_core_checks false false true || failed=1
            ;;
        ci-plus)
            # 在 ci 基础上追加 Playwright e2e-smoke（完全 mock，不依赖后端/DB）
            # 适合在 GitHub Actions 暂停自动触发时，本地更完整地覆盖回归锚点。
            run_ci_core_checks true false || failed=1
            ;;
        ci-full)
            # 最严格本地门禁：ci-plus + 依赖安全审计（pip-audit + npm audit）
            # 说明：security-audit 可能因环境/网络/依赖漏洞而失败；建议按需使用。
            run_ci_core_checks true true || failed=1
            ;;
        all)
            # 完整测试: 需要后端和前端服务运行
            check_services || exit 1
            echo ""
            run_backend_tests || failed=1
            echo ""
            run_frontend_unit_tests || failed=1
            echo ""
            run_e2e_tests || failed=1
            ;;
        docs-check)
            run_docs_checks || failed=1
            ;;
        frontend-baselines)
            run_frontend_baselines_checks || failed=1
            ;;
        research-baselines)
            run_research_baselines_checks || failed=1
            ;;
        scripts-tests)
            run_scripts_unit_tests || failed=1
            ;;
        *)
            echo "用法: $0 [smoke|security-audit|unit|etl-checks|docs-check|frontend-baselines|research-baselines|scripts-tests|backend-unit|backend-checks|backend-lint|frontend-lint|frontend-build|e2e-smoke|e2e-smoke-firefox|e2e-a11y-smoke|e2e-visual-smoke|performance-audit|ci|ci-postgres|backend|e2e|status|all]"
            echo ""
            echo "  smoke        - 运行所有单元测试（默认，无外部依赖）"
            echo "  security-audit - 运行依赖安全审计（pip-audit + npm audit）"
            echo "  unit         - 运行前端单元测试"
            echo "  etl-checks   - 运行 ETL 输入校验单元测试 (pytest etl/tests)"
            echo "  docs-check   - 检查文档命令漂移（启动命令示例）"
            echo "  frontend-baselines - 校验前端 bundle baselines（本地可选；会执行 npm run build）"
            echo "  research-baselines - 校验 research baselines（本地可选；会创建临时 sample DB）"
            echo "  scripts-tests - 运行 scripts/tests 下的脚本级单元测试（对齐 CI）"
            echo "  backend-unit - 运行后端单元测试 (pytest -m unit)"
            echo "  backend-checks - 运行后端导入与语法检查（对齐 CI）"
            echo "  backend-lint - 运行后端 Lint (ruff check)"
            echo "  frontend-lint  - 运行前端 Lint (ESLint)"
            echo "  frontend-build - 运行前端构建 (Vite build)"
            echo "  e2e-smoke     - 运行 Playwright E2E smoke（完全 mocked，对齐 CI，无需后端/DB）"
            echo "  e2e-smoke-firefox - 运行 Playwright E2E smoke（Firefox，可选 cross-browser）"
            echo "  e2e-a11y-smoke - 运行 Playwright A11y smoke（axe-core；完全 mocked）"
            echo "  e2e-visual-smoke - 运行 Playwright 视觉回归 smoke（screenshots；完全 mocked）"
            echo "  performance-audit - 运行 Playwright performance suite（需要可用后端；建议手动）"
            echo "  ci           - 对齐 GitHub Actions 的核心检查集合"
            echo "  ci-postgres  - ci + API snapshot baseline（本地临时 sample DB；对齐 self-hosted fast path）"
            echo "  ci-plus      - ci + e2e-smoke（更接近原 GH Tests，仍无需后端/DB）"
            echo "  ci-full      - ci-plus + security-audit（最严格门禁）"
            echo "  backend      - 运行后端 API 合同测试（需要服务运行）"
            echo "  e2e          - 运行前端 E2E 测试（需要服务运行）"
            echo "  status       - 检查前后端服务是否可访问（支持 BASE_URL/API_BASE_URL 覆盖）"
            echo "  all          - 运行所有测试（需要服务运行）"
            exit 1
            ;;
    esac

    finalize_run_tests_summary "$failed"

    echo ""
    echo "=========================================="
    if [ $failed -eq 0 ]; then
        echo -e "  ${GREEN}所有测试通过!${NC}"
    else
        echo -e "  ${RED}部分测试失败${NC}"
    fi
    echo "=========================================="

    exit $failed
}

main "$@"
