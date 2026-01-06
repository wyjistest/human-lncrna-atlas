#!/bin/bash
# ==============================================================================
# Human LncRNA Atlas - 一键启动脚本
# ==============================================================================
# 版本: v1.0
# 日期: 2025-12-02
# 用途: 启动前后端服务，支持开发和生产模式
# ==============================================================================

set -euo pipefail  # 遇到错误立即退出（含未定义变量与管道失败）

# ==============================================================================
# 配置区域（可通过环境变量覆盖）
# ==============================================================================

# 项目路径（默认使用脚本所在目录的父目录）
SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
PROJECT_ROOT="${PROJECT_ROOT:-$(dirname "$SCRIPT_DIR")}"
BACKEND_DIR="${BACKEND_DIR:-$PROJECT_ROOT/frontend/backend}"
FRONTEND_DIR="${FRONTEND_DIR:-$PROJECT_ROOT/frontend/web}"

# 服务配置
BACKEND_HOST="${BACKEND_HOST:-0.0.0.0}"
BACKEND_PORT="${BACKEND_PORT:-8000}"
FRONTEND_HOST="${FRONTEND_HOST:-0.0.0.0}"
FRONTEND_PORT="${FRONTEND_PORT:-5173}"

# 数据库配置
DB_HOST="${DB_HOST:-localhost}"
DB_PORT="${DB_PORT:-5432}"
DB_USER="${DB_USER:-amax}"
DB_NAME="${DB_NAME:-lncrna_production}"

# 日志目录
LOG_DIR="${LOG_DIR:-/tmp/lncrna-atlas}"

# 运行模式: dev(开发) 或 prod(生产)
MODE="${MODE:-dev}"

# dev 模式增强：自动注入 LAN 访问所需配置
# - TRUSTED_HOSTS: 允许通过本机局域网 IP 访问（避免 Invalid host header）
# - CORS_ORIGINS: 允许局域网访问前端时跨域调用后端
# - ADMIN_API_KEY: 自动生成（避免后端 fail-fast 因未配置而拒绝启动）
# 如需关闭自动注入：AUTO_LAN=false
AUTO_LAN="${AUTO_LAN:-true}"

# 后端 Python 解释器（可选）：默认自动探测 backend/.venv 或 backend/venv
BACKEND_PYTHON="${BACKEND_PYTHON:-}"

# 颜色输出
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
CYAN='\033[0;36m'
NC='\033[0m' # No Color

# ==============================================================================
# 工具函数
# ==============================================================================

log_info() {
    echo -e "${BLUE}[INFO]${NC} $1"
}

log_success() {
    echo -e "${GREEN}[SUCCESS]${NC} $1"
}

log_warning() {
    echo -e "${YELLOW}[WARNING]${NC} $1"
}

log_error() {
    echo -e "${RED}[ERROR]${NC} $1"
}

log_step() {
    echo -e "${CYAN}[STEP]${NC} $1"
}

check_command() {
    if ! command -v "$1" &> /dev/null; then
        log_error "$1 未安装，请先安装"
        return 1
    fi
    return 0
}

detect_lan_ip() {
    # 尽量选择“默认路由出口”的 IPv4（通常就是局域网 IP）
    # 失败则回退到 hostname -I 的第一个地址
    local ip_addr=""

    if command -v ip > /dev/null 2>&1; then
        ip_addr="$(ip -4 route get 1.1.1.1 2>/dev/null | awk '{for(i=1;i<=NF;i++) if($i=="src"){print $(i+1); exit}}' || true)"
    fi

    if [ -z "$ip_addr" ] && command -v hostname > /dev/null 2>&1; then
        ip_addr="$(hostname -I 2>/dev/null | awk '{print $1}' || true)"
    fi

    if [ -z "$ip_addr" ]; then
        ip_addr="127.0.0.1"
    fi

    echo "$ip_addr"
}

resolve_backend_python() {
    if [ -n "$BACKEND_PYTHON" ]; then
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

    echo "python3"
}

generate_admin_api_key() {
    # 生成 32 bytes 的 hex key（64 字符）
    if command -v openssl > /dev/null 2>&1; then
        openssl rand -hex 32
        return 0
    fi
    python3 -c "import secrets; print(secrets.token_hex(32))"
}

apply_dev_env_overrides() {
    if [ "$MODE" != "dev" ] || [ "$AUTO_LAN" != "true" ]; then
        return 0
    fi

    local lan_ip="${LAN_IP:-$(detect_lan_ip)}"

    # 仅在用户未显式设置时注入，避免覆盖用户配置
    if [ -z "${ENV:-}" ]; then
        export ENV="development"
    fi

    if [ -z "${TRUSTED_HOSTS:-}" ]; then
        export TRUSTED_HOSTS="[\"localhost\",\"127.0.0.1\",\"*.localhost\",\"${lan_ip}\"]"
        log_info "dev: 自动注入 TRUSTED_HOSTS=$TRUSTED_HOSTS"
    fi

    if [ -z "${CORS_ORIGINS:-}" ]; then
        export CORS_ORIGINS="[\"http://localhost:${FRONTEND_PORT}\",\"http://127.0.0.1:${FRONTEND_PORT}\",\"http://${lan_ip}:${FRONTEND_PORT}\"]"
        log_info "dev: 自动注入 CORS_ORIGINS=$CORS_ORIGINS"
    fi

    # LAN 友好开发模式下，前端默认会通过 LAN IP 访问后端（VITE_API_BASE_URL=http://<lan_ip>:8000）。
    # 这会导致限流 key 变为 LAN IP（非 127.0.0.1），并在 Playwright 并发测试或频繁交互时触发 429。
    # 仅在用户未显式配置时，开启私网 IP 限流 bypass（生产环境请保持 false）。
    if [ -z "${RATE_LIMIT_BYPASS_PRIVATE:-}" ]; then
        export RATE_LIMIT_BYPASS_PRIVATE="true"
        log_info "dev: 自动注入 RATE_LIMIT_BYPASS_PRIVATE=$RATE_LIMIT_BYPASS_PRIVATE"
    fi

    if [ -z "${ADMIN_API_KEY:-}" ]; then
        export ADMIN_API_KEY="$(generate_admin_api_key)"
        export ADMIN_REQUIRE_API_KEY="true"

        # SECURITY: 仅写入本机临时目录，避免误提交到仓库
        local key_file="$LOG_DIR/admin_api_key.txt"
        printf '%s' "$ADMIN_API_KEY" > "$key_file"
        chmod 600 "$key_file" 2>/dev/null || true
        log_info "dev: 自动生成 ADMIN_API_KEY（已写入 $key_file）"
    fi

    if [ -z "${VITE_API_BASE_URL:-}" ]; then
        export VITE_API_BASE_URL="http://${lan_ip}:${BACKEND_PORT}"
        log_info "dev: 自动注入 VITE_API_BASE_URL=$VITE_API_BASE_URL"
    fi
}

# ==============================================================================
# 环境检查
# ==============================================================================

check_environment() {
    log_step "检查运行环境..."

    local has_error=0

    # 检查 Python
    if check_command python3; then
        local py_version=$(python3 --version 2>&1 | cut -d' ' -f2)
        log_info "Python: $py_version"
    else
        has_error=1
    fi

    # 检查 Node.js
    if check_command node; then
        local node_version=$(node --version)
        log_info "Node.js: $node_version"
    else
        has_error=1
    fi

    # 检查 npm
    if check_command npm; then
        local npm_version=$(npm --version)
        log_info "npm: $npm_version"
    else
        has_error=1
    fi

    # curl 是健康检查与启动确认的硬依赖
    if ! check_command curl; then
        has_error=1
    fi

    # 检查目录
    if [ ! -d "$BACKEND_DIR" ]; then
        log_error "后端目录不存在: $BACKEND_DIR"
        has_error=1
    fi

    if [ ! -d "$FRONTEND_DIR" ]; then
        log_error "前端目录不存在: $FRONTEND_DIR"
        has_error=1
    fi

    # 检查数据库连接
    log_info "检查数据库连接..."
    if command -v pg_isready > /dev/null 2>&1; then
        if pg_isready -h "$DB_HOST" -p "$DB_PORT" -U "$DB_USER" -d "$DB_NAME" &> /dev/null; then
            log_info "数据库连接: OK"
        else
            log_warning "数据库连接失败，后端可能无法正常工作"
        fi
    else
        log_warning "pg_isready 未安装，跳过数据库就绪检查（仅影响提示，不影响启动）"
    fi

    if [ $has_error -eq 1 ]; then
        log_error "环境检查失败，请解决上述问题后重试"
        exit 1
    fi

    log_success "环境检查通过"
}

# ==============================================================================
# 服务管理
# ==============================================================================

create_log_dir() {
    mkdir -p "$LOG_DIR"
    # SECURITY: 尽量避免日志目录被其他用户读取（尤其在共享机器/多用户环境）
    chmod 700 "$LOG_DIR" 2>/dev/null || true
    log_info "日志目录: $LOG_DIR"
}

wait_for_health() {
    # 带重试的健康检查
    # 参数: $1=URL $2=服务名 $3=最大重试次数 $4=重试间隔秒数
    local url="$1"
    local service_name="$2"
    local max_retries="${3:-10}"
    local retry_interval="${4:-2}"
    local attempt=1

    log_info "等待 $service_name 健康检查..."
    while [ $attempt -le $max_retries ]; do
        # -f: HTTP 4xx/5xx 视为失败；避免把错误页当作“健康”
        # -sS: 静默但保留错误信息（这里重定向到 /dev/null，仅靠退出码判断）
        if curl -fsS --max-time 5 "$url" > /dev/null 2>&1; then
            return 0
        fi
        log_info "健康检查 [$attempt/$max_retries]... (等待 ${retry_interval}s)"
        sleep $retry_interval
        attempt=$((attempt + 1))
    done
    return 1
}

start_backend() {
    log_step "启动后端服务..."

    cd "$BACKEND_DIR"

    # 检查是否已经在运行
    if pgrep -f "uvicorn.*main:app.*$BACKEND_PORT" > /dev/null; then
        log_warning "后端服务已在运行 (端口 $BACKEND_PORT)"
        return 0
    fi

    local python_bin
    python_bin="$(resolve_backend_python)"
    if ! command -v "$python_bin" > /dev/null 2>&1; then
        log_error "未找到后端 Python 解释器: $python_bin"
        log_error "可选：设置 BACKEND_PYTHON=/path/to/python 或创建 $BACKEND_DIR/.venv"
        return 1
    fi
    if ! "$python_bin" -c "import uvicorn" > /dev/null 2>&1; then
        log_error "后端依赖未安装（uvicorn 不可用）。"
        log_error "请先在 $BACKEND_DIR 安装依赖，例如：$python_bin -m pip install -r requirements.txt"
        log_error "（如需运行测试/ruff）再执行：$python_bin -m pip install -r requirements-dev.txt"
        return 1
    fi

    # 启动服务
    # SECURITY: 预创建日志文件并收紧权限，避免默认 umask 导致日志可被其他用户读取
    touch "$LOG_DIR/backend.log"
    chmod 600 "$LOG_DIR/backend.log" 2>/dev/null || true
    if [ "$MODE" = "prod" ]; then
        log_info "生产模式启动..."
        nohup "$python_bin" -m uvicorn main:app \
            --host "$BACKEND_HOST" \
            --port "$BACKEND_PORT" \
            --workers 4 \
            > "$LOG_DIR/backend.log" 2>&1 &
    else
        log_info "开发模式启动 (热重载)..."
        nohup "$python_bin" -m uvicorn main:app \
            --host "$BACKEND_HOST" \
            --port "$BACKEND_PORT" \
            --reload \
            > "$LOG_DIR/backend.log" 2>&1 &
    fi

    local backend_pid=$!
    echo $backend_pid > "$LOG_DIR/backend.pid"

    # 带重试的健康检查（最多 10 次，每次间隔 2 秒，共 20 秒超时）
    if wait_for_health "http://localhost:$BACKEND_PORT/health" "后端" 10 2; then
        log_success "后端服务启动成功 (PID: $backend_pid)"
        log_info "API 文档: http://localhost:$BACKEND_PORT/docs"
    else
        log_error "后端服务健康检查失败！"
        log_error "可能原因: 数据库连接失败、端口被占用、配置错误"
        log_error "查看日志: tail -f $LOG_DIR/backend.log"
        log_error "最后 20 行日志:"
        tail -20 "$LOG_DIR/backend.log" 2>/dev/null || true
        return 1
    fi
}

start_frontend() {
    log_step "启动前端服务..."

    cd "$FRONTEND_DIR"

    # 检查是否已经在运行
    if pgrep -f "vite.*$FRONTEND_PORT" > /dev/null; then
        log_warning "前端服务已在运行 (端口 $FRONTEND_PORT)"
        return 0
    fi

    # 检查依赖
    if [ ! -d "node_modules" ]; then
        log_info "安装前端依赖..."
        # 使用 lockfile 的确定性安装，避免 npm install 产生依赖漂移（供应链/可复现性风险）
        if [ -f "package-lock.json" ]; then
            npm ci
        else
            npm install
        fi
    fi

    # 启动服务
    # SECURITY: 预创建日志文件并收紧权限，避免默认 umask 导致日志可被其他用户读取
    touch "$LOG_DIR/frontend.log"
    chmod 600 "$LOG_DIR/frontend.log" 2>/dev/null || true
    if [ "$MODE" = "prod" ]; then
        log_info "生产模式: 构建并预览..."
        npm run build
        nohup npm run preview -- --host "$FRONTEND_HOST" --port "$FRONTEND_PORT" \
            > "$LOG_DIR/frontend.log" 2>&1 &
    else
        log_info "开发模式启动..."
        nohup npm run dev -- --host "$FRONTEND_HOST" --port "$FRONTEND_PORT" --strictPort \
            > "$LOG_DIR/frontend.log" 2>&1 &
    fi

    local frontend_pid=$!
    echo $frontend_pid > "$LOG_DIR/frontend.pid"

    # 等待启动
    sleep 3

    log_success "前端服务启动成功 (PID: $frontend_pid)"
    log_info "访问地址: http://localhost:$FRONTEND_PORT"
    log_info "查看日志: tail -f $LOG_DIR/frontend.log"
}

# ==============================================================================
# 主函数
# ==============================================================================

show_usage() {
    echo "用法: $0 [选项]"
    echo ""
    echo "选项:"
    echo "  -m, --mode MODE     运行模式: dev(默认) 或 prod"
    echo "  -b, --backend-only  仅启动后端"
    echo "  -f, --frontend-only 仅启动前端"
    echo "  -h, --help          显示帮助"
    echo ""
    echo "环境变量:"
    echo "  PROJECT_ROOT        项目根目录"
    echo "  BACKEND_PORT        后端端口 (默认: 8000)"
    echo "  FRONTEND_PORT       前端端口 (默认: 5173)"
    echo "  DB_HOST             数据库主机 (默认: localhost)"
    echo "  DB_NAME             数据库名 (默认: lncrna_production)"
    echo "  MODE                运行模式 (默认: dev)"
    echo ""
    echo "示例:"
    echo "  $0                  # 开发模式启动全部服务"
    echo "  $0 -m prod          # 生产模式启动"
    echo "  $0 -b               # 仅启动后端"
    echo "  MODE=prod $0        # 通过环境变量设置模式"
}

main() {
    local backend_only=0
    local frontend_only=0

    # 解析参数
    while [[ $# -gt 0 ]]; do
        case $1 in
            -m|--mode)
                if [ $# -lt 2 ]; then
                    log_error "--mode 需要参数: dev 或 prod"
                    show_usage
                    exit 1
                fi
                MODE="$2"
                shift 2
                ;;
            -b|--backend-only)
                backend_only=1
                shift
                ;;
            -f|--frontend-only)
                frontend_only=1
                shift
                ;;
            -h|--help)
                show_usage
                exit 0
                ;;
            *)
                log_error "未知选项: $1"
                show_usage
                exit 1
                ;;
        esac
    done

    echo ""
    echo "=============================================="
    echo "  Human LncRNA Atlas - 服务启动"
    echo "  模式: $MODE"
    echo "=============================================="
    echo ""

    check_environment
    create_log_dir
    apply_dev_env_overrides

    local has_failure=0

    if [ $frontend_only -eq 0 ]; then
        if ! start_backend; then
            has_failure=1
        fi
    fi

    if [ $backend_only -eq 0 ]; then
        start_frontend
    fi

    # 如果有服务启动失败，返回非零退出码
    if [ $has_failure -eq 1 ]; then
        echo ""
        log_error "部分服务启动失败，请检查日志"
        exit 1
    fi

    echo ""
    log_success "服务启动完成！"
    echo ""
    echo "=============================================="
    echo "  服务状态"
    echo "=============================================="
    if [ $frontend_only -eq 0 ]; then
        echo "  后端: http://localhost:$BACKEND_PORT"
        echo "  API:  http://localhost:$BACKEND_PORT/docs"
    fi
    if [ $backend_only -eq 0 ]; then
        echo "  前端: http://localhost:$FRONTEND_PORT"
    fi
    echo ""
    echo "  日志: $LOG_DIR/"
    echo "  停止: $(dirname "$0")/stop.sh"
    echo "=============================================="
}

main "$@"
