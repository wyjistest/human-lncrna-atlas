#!/bin/bash
# ==============================================================================
# Human LncRNA Atlas - 一键启动脚本
# ==============================================================================
# 版本: v1.0
# 日期: 2025-12-02
# 用途: 启动前后端服务，支持开发和生产模式
# ==============================================================================

set -e  # 遇到错误立即退出

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
    if pg_isready -h "$DB_HOST" -p "$DB_PORT" -U "$DB_USER" -d "$DB_NAME" &> /dev/null; then
        log_info "数据库连接: OK"
    else
        log_warning "数据库连接失败，后端可能无法正常工作"
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
        if curl -s --max-time 5 "$url" > /dev/null 2>&1; then
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

    # 启动服务
    if [ "$MODE" = "prod" ]; then
        log_info "生产模式启动..."
        nohup python3 -m uvicorn main:app \
            --host "$BACKEND_HOST" \
            --port "$BACKEND_PORT" \
            --workers 4 \
            > "$LOG_DIR/backend.log" 2>&1 &
    else
        log_info "开发模式启动 (热重载)..."
        nohup python3 -m uvicorn main:app \
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
        npm install
    fi

    # 启动服务
    if [ "$MODE" = "prod" ]; then
        log_info "生产模式: 构建并预览..."
        npm run build
        nohup npm run preview -- --host "$FRONTEND_HOST" --port "$FRONTEND_PORT" \
            > "$LOG_DIR/frontend.log" 2>&1 &
    else
        log_info "开发模式启动..."
        nohup npm run dev -- --host "$FRONTEND_HOST" --port "$FRONTEND_PORT" \
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
