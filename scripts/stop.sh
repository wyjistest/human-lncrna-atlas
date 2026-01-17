#!/bin/bash
# ==============================================================================
# Human LncRNA Atlas - 一键停止脚本
# ==============================================================================
# 版本: v1.0
# 日期: 2025-12-02
# 用途: 停止前后端服务
# ==============================================================================

# 遇到错误立即退出（含未定义变量与管道失败）
set -euo pipefail

has_command() {
    command -v "$1" >/dev/null 2>&1
}

# ==============================================================================
# 配置区域
# ==============================================================================

LOG_DIR="${LOG_DIR:-/tmp/lncrna-atlas}"
BACKEND_PORT="${BACKEND_PORT:-8000}"
FRONTEND_PORT="${FRONTEND_PORT:-5173}"

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

# ==============================================================================
# 服务停止
# ==============================================================================

stop_backend() {
    log_step "停止后端服务..."

    local stopped=0

    # 方法1: 使用 PID 文件
    if [ -f "$LOG_DIR/backend.pid" ]; then
        local pid=$(cat "$LOG_DIR/backend.pid")
        if kill -0 "$pid" 2>/dev/null; then
            kill "$pid" 2>/dev/null || true
            log_info "已发送停止信号到后端进程 (PID: $pid)"
            stopped=1
        fi
        rm -f "$LOG_DIR/backend.pid"
    fi

    # 方法2: 按端口查找
    local pids=""
    if has_command pgrep; then
        pids="$(pgrep -f "uvicorn.*main:app.*$BACKEND_PORT" 2>/dev/null || true)"
    fi
    if [ -n "$pids" ]; then
        while IFS= read -r pid; do
            if [ -n "${pid:-}" ]; then
                kill "$pid" 2>/dev/null || true
                log_info "停止后端进程 (PID: $pid)"
            fi
        done <<< "$pids"
        stopped=1
    fi

    # 方法3: 使用 lsof 按端口查找
    local port_pid=""
    if has_command lsof; then
        port_pid="$(lsof -ti:$BACKEND_PORT 2>/dev/null || true)"
    fi
    if [ -n "$port_pid" ]; then
        # port_pid 可能包含多个 PID（按空白分隔），此处故意不加引号
        kill $port_pid 2>/dev/null || true
        log_info "停止端口 $BACKEND_PORT 上的进程"
        stopped=1
    fi

    if [ $stopped -eq 1 ]; then
        sleep 1
        # 验证是否停止
        if has_command pgrep && pgrep -f "uvicorn.*main:app.*$BACKEND_PORT" > /dev/null 2>&1; then
            log_warning "后端服务仍在运行，尝试强制停止..."
            if has_command pkill; then
                pkill -9 -f "uvicorn.*main:app.*$BACKEND_PORT" 2>/dev/null || true
            fi
        fi
        log_success "后端服务已停止"
    else
        log_info "后端服务未在运行"
    fi
}

stop_frontend() {
    log_step "停止前端服务..."

    local stopped=0

    # 方法1: 使用 PID 文件
    if [ -f "$LOG_DIR/frontend.pid" ]; then
        local pid=$(cat "$LOG_DIR/frontend.pid")
        if kill -0 "$pid" 2>/dev/null; then
            kill "$pid" 2>/dev/null || true
            log_info "已发送停止信号到前端进程 (PID: $pid)"
            stopped=1
        fi
        rm -f "$LOG_DIR/frontend.pid"
    fi

    # 方法2: 按进程名查找 (vite)
    local pids=""
    if has_command pgrep; then
        pids="$(pgrep -f "vite.*$FRONTEND_PORT" 2>/dev/null || true)"
    fi
    if [ -n "$pids" ]; then
        while IFS= read -r pid; do
            if [ -n "${pid:-}" ]; then
                kill "$pid" 2>/dev/null || true
                log_info "停止前端进程 (PID: $pid)"
            fi
        done <<< "$pids"
        stopped=1
    fi

    # 方法3: 查找 node 进程 (npm run dev)
    pids=""
    if has_command pgrep; then
        pids="$(pgrep -f "node.*vite" 2>/dev/null || true)"
    fi
    if [ -n "$pids" ]; then
        while IFS= read -r pid; do
            if [ -n "${pid:-}" ]; then
                kill "$pid" 2>/dev/null || true
                log_info "停止 Node 进程 (PID: $pid)"
            fi
        done <<< "$pids"
        stopped=1
    fi

    # 方法4: 使用 lsof 按端口查找
    local port_pid=""
    if has_command lsof; then
        port_pid="$(lsof -ti:$FRONTEND_PORT 2>/dev/null || true)"
    fi
    if [ -n "$port_pid" ]; then
        # port_pid 可能包含多个 PID（按空白分隔），此处故意不加引号
        kill $port_pid 2>/dev/null || true
        log_info "停止端口 $FRONTEND_PORT 上的进程"
        stopped=1
    fi

    if [ $stopped -eq 1 ]; then
        sleep 1
        log_success "前端服务已停止"
    else
        log_info "前端服务未在运行"
    fi
}

show_status() {
    echo ""
    echo "=============================================="
    echo "  服务状态"
    echo "=============================================="

    # 检查后端
    if has_command pgrep && pgrep -f "uvicorn.*main:app.*$BACKEND_PORT" > /dev/null 2>&1; then
        local backend_pid
        backend_pid="$(pgrep -f "uvicorn.*main:app.*$BACKEND_PORT" 2>/dev/null | head -1 || true)"
        echo -e "  后端: ${GREEN}运行中${NC} (PID: $backend_pid, 端口: $BACKEND_PORT)"
    else
        echo -e "  后端: ${RED}已停止${NC}"
    fi

    # 检查前端
    local frontend_running=0
    if has_command pgrep && pgrep -f "vite.*$FRONTEND_PORT" > /dev/null 2>&1; then
        frontend_running=1
    fi
    if [ "$frontend_running" -eq 0 ] && has_command lsof && lsof -ti:$FRONTEND_PORT > /dev/null 2>&1; then
        frontend_running=1
    fi
    if [ "$frontend_running" -eq 1 ]; then
        local frontend_pid=""
        if has_command lsof; then
            frontend_pid="$(lsof -ti:$FRONTEND_PORT 2>/dev/null | head -1 || true)"
        fi
        echo -e "  前端: ${GREEN}运行中${NC} (PID: $frontend_pid, 端口: $FRONTEND_PORT)"
    else
        echo -e "  前端: ${RED}已停止${NC}"
    fi

    echo "=============================================="
}

# ==============================================================================
# 主函数
# ==============================================================================

show_usage() {
    echo "用法: $0 [选项]"
    echo ""
    echo "选项:"
    echo "  -b, --backend-only  仅停止后端"
    echo "  -f, --frontend-only 仅停止前端"
    echo "  -s, --status        显示服务状态"
    echo "  -h, --help          显示帮助"
    echo ""
    echo "环境变量:"
    echo "  BACKEND_PORT        后端端口 (默认: 8000)"
    echo "  FRONTEND_PORT       前端端口 (默认: 5173)"
    echo "  LOG_DIR             日志目录 (默认: /tmp/lncrna-atlas)"
    echo ""
    echo "示例:"
    echo "  $0                  # 停止全部服务"
    echo "  $0 -b               # 仅停止后端"
    echo "  $0 -s               # 查看服务状态"
}

main() {
    local backend_only=0
    local frontend_only=0
    local status_only=0

    # 解析参数
    while [[ $# -gt 0 ]]; do
        case $1 in
            -b|--backend-only)
                backend_only=1
                shift
                ;;
            -f|--frontend-only)
                frontend_only=1
                shift
                ;;
            -s|--status)
                status_only=1
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

    if [ $status_only -eq 1 ]; then
        show_status
        exit 0
    fi

    echo ""
    echo "=============================================="
    echo "  Human LncRNA Atlas - 服务停止"
    echo "=============================================="
    echo ""

    if [ $frontend_only -eq 0 ]; then
        stop_backend
    fi

    if [ $backend_only -eq 0 ]; then
        stop_frontend
    fi

    echo ""
    show_status
}

main "$@"
