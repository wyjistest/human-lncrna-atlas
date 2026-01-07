#!/bin/bash
# ==============================================================================
# PostgreSQL 安装脚本 (Ubuntu/Debian)
# ==============================================================================
# 版本: v2.2
# 支持: PostgreSQL 15/16/17/18
# 默认: PostgreSQL 17 (推荐稳定版)
# 兼容: Ubuntu 20.04+, Debian 11+
# ==============================================================================

set -euo pipefail

# 可配置版本（默认17）
PG_VERSION="${PG_VERSION:-17}"
GRANT_SUPERUSER="${GRANT_SUPERUSER:-no}"  # 默认不授予超级权限
ASSUME_YES="${ASSUME_YES:-no}"            # 非交互模式下默认继续（慎用）

# 指定要创建的应用数据库用户（默认取 SUDO_USER/USER）
APP_DB_USER="${APP_DB_USER:-${SUDO_USER:-${USER:-}}}"
if [ -z "$APP_DB_USER" ]; then
    APP_DB_USER="$(id -un 2>/dev/null || true)"
fi

# 运行时路径（用于输出提示）
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(cd "${SCRIPT_DIR}/.." && pwd)"

# 颜色输出
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m'

log_step() {
    echo -e "${BLUE}[STEP $1]${NC} $2"
}

log_success() {
    echo -e "${GREEN}✅ $1${NC}"
}

log_error() {
    echo -e "${RED}❌ $1${NC}"
}

log_warning() {
    echo -e "${YELLOW}⚠️  $1${NC}"
}

is_interactive() {
    [ -t 0 ]
}

confirm_continue() {
    local prompt="${1:-是否继续？(y/N) }"
    if [ "$ASSUME_YES" = "yes" ]; then
        return 0
    fi
    if ! is_interactive; then
        return 1
    fi
    read -p "$prompt" -n 1 -r
    echo
    [[ $REPLY =~ ^[Yy]$ ]]
}

validate_role_name() {
    local role_name="$1"
    if [[ ! "$role_name" =~ ^[a-zA-Z_][a-zA-Z0-9_]*$ ]]; then
        log_error "应用数据库用户 '$role_name' 不是安全的 PostgreSQL role 标识符"
        echo "请设置一个安全值（字母/数字/_，且不能以数字开头），例如："
        echo "  export APP_DB_USER=amax"
        exit 1
    fi
}

# sudo/权限处理：root 下不强制依赖 sudo；非交互环境避免 sudo 等待密码卡死
SUDO=""
if [ "$(id -u)" -ne 0 ]; then
    if ! command -v sudo >/dev/null 2>&1; then
        log_error "需要 sudo，但系统未安装 sudo。请安装 sudo 或以 root 身份运行。"
        exit 1
    fi
    SUDO="sudo"
fi

ensure_privileges() {
    if [ -z "$SUDO" ]; then
        return 0
    fi
    if sudo -n true >/dev/null 2>&1; then
        return 0
    fi
    if ! is_interactive; then
        log_error "需要 sudo 权限，但当前为非交互环境且 sudo 可能需要密码，已停止以避免卡死"
        echo "解决方案："
        echo "  1) 以可交互终端运行该脚本；或"
        echo "  2) 配置免密 sudo；或"
        echo "  3) 以 root 身份运行"
        exit 1
    fi
    echo "需要 sudo 权限以安装/配置 PostgreSQL，请输入密码（如提示）..."
    sudo -v
}

run_as_postgres() {
    if [ -n "$SUDO" ]; then
        $SUDO -u postgres "$@"
        return
    fi
    if command -v runuser >/dev/null 2>&1; then
        runuser -u postgres -- "$@"
        return
    fi
    if command -v su >/dev/null 2>&1; then
        su - postgres -c "$(printf '%q ' "$@")"
        return
    fi
    log_error "无法切换到 postgres 用户执行命令（缺少 sudo/runuser/su）"
    exit 1
}

echo "========================================="
echo " PostgreSQL $PG_VERSION 安装向导"
echo "========================================="
echo ""
echo "📋 版本说明:"
echo "  • PostgreSQL 18 (最新): 2025-11-13发布，最新特性"
echo "  • PostgreSQL 17 (推荐): 稳定版，适合生产环境"
echo "  • PostgreSQL 15/16: 旧版本，也很稳定"
echo ""
echo "💡 切换版本（项目根目录执行）: export PG_VERSION=18 && ./scripts/install_postgresql.sh"
echo ""

# ==============================================================================
# 前置检查
# ==============================================================================

log_step 0 "系统环境检查"

# 检测发行版
if [ -f /etc/os-release ]; then
    . /etc/os-release
    OS_NAME="${ID:-unknown}"
    OS_VERSION="${VERSION_ID:-unknown}"
    OS_CODENAME="${VERSION_CODENAME:-}"

    # 如果没有VERSION_CODENAME，尝试用lsb_release
    if [ -z "$OS_CODENAME" ]; then
        OS_CODENAME=$(lsb_release -cs 2>/dev/null || echo "")
    fi
else
    log_error "无法检测操作系统"
    exit 1
fi

echo "检测到系统: $OS_NAME $OS_VERSION ($OS_CODENAME)"

# 基本输入校验：避免 role 名导致 SQL/命令异常
if [ -z "$APP_DB_USER" ]; then
    log_error "无法确定要创建的应用数据库用户（APP_DB_USER/SUDO_USER/USER 均为空）"
    exit 1
fi
validate_role_name "$APP_DB_USER"

# 无法检测发行版代号时，无法配置 pgdg 仓库
if [ -z "$OS_CODENAME" ]; then
    log_error "无法检测发行版代号（VERSION_CODENAME 或 lsb_release -cs）"
    exit 1
fi

# 验证支持的发行版
case "$OS_NAME" in
    ubuntu|debian)
        log_success "支持的操作系统"
        ;;
    *)
        log_warning "未测试的操作系统: $OS_NAME"
        echo "脚本仅在Ubuntu/Debian测试过，继续安装可能失败"
        if ! confirm_continue "是否继续？(y/N) "; then
            exit 1
        fi
        ;;
esac

# 检查systemd
if ! command -v systemctl &> /dev/null; then
    log_warning "未检测到systemd，服务管理可能不可用"
    HAS_SYSTEMD=no
else
    HAS_SYSTEMD=yes
fi

echo ""

# ==============================================================================
# Step 1: 添加PostgreSQL官方仓库（修复：动态检测代号）
# ==============================================================================

log_step 1 "添加PostgreSQL官方APT仓库"

# 需要 sudo/root 权限，提前检查避免在 apt/tee 时卡死
ensure_privileges

# 安装必要的工具
$SUDO apt-get update
$SUDO apt-get install -y wget ca-certificates gnupg

# 【修复1】：使用新的GPG key方法，不使用弃用的apt-key
KEYRING_DIR="/usr/share/keyrings"
$SUDO mkdir -p "$KEYRING_DIR"

if [ ! -f "$KEYRING_DIR/postgresql-archive-keyring.gpg" ]; then
    echo "下载PostgreSQL GPG key..."
    wget --quiet -O - https://www.postgresql.org/media/keys/ACCC4CF8.asc | \
        gpg --dearmor | \
        $SUDO tee "$KEYRING_DIR/postgresql-archive-keyring.gpg" > /dev/null
    log_success "GPG key已添加"
else
    echo "GPG key已存在"
fi

# 【修复2】：动态使用检测到的发行版代号，而非硬编码focal
# 【修复3】：Ubuntu 20.04 (focal) 已于2025年7月从主仓库移除，使用归档仓库
REPO_FILE="/etc/apt/sources.list.d/pgdg.list"

# 检查是否是已停止支持的发行版（需要使用归档仓库）
ARCHIVED_CODENAMES="focal"  # Ubuntu 20.04
if echo "$ARCHIVED_CODENAMES" | grep -qw "$OS_CODENAME"; then
    REPO_URL="https://apt-archive.postgresql.org/pub/repos/apt/"
    log_warning "检测到已归档的发行版: $OS_CODENAME"
    echo "使用归档仓库: apt-archive.postgresql.org"
    echo "建议: 升级到Ubuntu 22.04+以获得持续更新"
else
    REPO_URL="https://apt.postgresql.org/pub/repos/apt/"
fi

echo "deb [signed-by=$KEYRING_DIR/postgresql-archive-keyring.gpg] $REPO_URL $OS_CODENAME-pgdg main" | \
    $SUDO tee "$REPO_FILE"

log_success "PostgreSQL仓库已添加 (使用 $OS_CODENAME-pgdg)"
echo ""

# ==============================================================================
# Step 2: 安装PostgreSQL
# ==============================================================================

log_step 2 "安装PostgreSQL $PG_VERSION"

$SUDO apt-get update
$SUDO apt-get install -y postgresql-$PG_VERSION postgresql-contrib-$PG_VERSION

log_success "PostgreSQL $PG_VERSION 安装完成"
echo ""

# ==============================================================================
# Step 3: 启动PostgreSQL服务
# ==============================================================================

log_step 3 "启动PostgreSQL服务"

if [ "$HAS_SYSTEMD" = "yes" ]; then
    $SUDO systemctl start postgresql
    $SUDO systemctl enable postgresql

    # 检查状态
    if $SUDO systemctl is-active --quiet postgresql; then
        log_success "PostgreSQL服务已启动"
    else
        log_error "PostgreSQL服务启动失败"
        echo "查看日志: sudo journalctl -u postgresql -n 50"
        exit 1
    fi
else
    log_warning "无systemd，尝试使用pg_ctlcluster..."
    $SUDO pg_ctlcluster $PG_VERSION main start || {
        log_error "PostgreSQL启动失败"
        exit 1
    }
    log_success "PostgreSQL服务已启动"
fi

echo ""

# ==============================================================================
# Step 4: 配置PostgreSQL用户
# ==============================================================================

log_step 4 "配置PostgreSQL用户"

echo "当前PostgreSQL版本："
run_as_postgres psql -c "SELECT version();" 2>/dev/null || {
    log_error "无法连接到PostgreSQL"
    exit 1
}

echo ""

# ==============================================================================
# Step 5: 创建应用数据库用户（修复：可选超级权限）
# ==============================================================================

log_step 5 "创建应用数据库用户"

# 检查用户是否已存在
if run_as_postgres psql -tAc "SELECT 1 FROM pg_roles WHERE rolname='$APP_DB_USER'" | grep -q 1; then
    echo "用户 $APP_DB_USER 已存在"
else
    echo "创建PostgreSQL用户: $APP_DB_USER"

    # 【修复3】：根据GRANT_SUPERUSER变量决定是否授予超级权限
    if [ "$GRANT_SUPERUSER" = "yes" ]; then
        run_as_postgres createuser -s "$APP_DB_USER"
        log_success "用户 $APP_DB_USER 创建成功（拥有超级用户权限）"
        log_warning "生产环境不建议授予超级权限！"
    else
        run_as_postgres createuser -d "$APP_DB_USER"  # 只授予创建数据库权限
        log_success "用户 $APP_DB_USER 创建成功（可创建数据库）"
        echo "提示：如需超级权限，运行:"
        echo "  sudo -u postgres psql -c \"ALTER USER $APP_DB_USER WITH SUPERUSER;\""
        echo "  或: export GRANT_SUPERUSER=yes && ./scripts/install_postgresql.sh"
    fi
fi

echo ""

# ==============================================================================
# Step 6: 配置认证方式
# ==============================================================================

log_step 6 "配置本地连接权限"

PG_HBA="/etc/postgresql/$PG_VERSION/main/pg_hba.conf"

if [ -f "$PG_HBA" ]; then
    echo "当前认证配置（仅显示local连接）："
    $SUDO grep "^local" "$PG_HBA" | head -3

    echo ""
    log_warning "默认认证方式为 'peer'（本地用户名匹配）"
    echo ""
    echo "如需无密码连接，可修改 $PG_HBA："
    echo "  将 'peer' 改为 'trust'（开发环境）"
    echo "  或设置密码并使用 'md5'（生产环境）"
    echo ""
    echo "修改后重启服务:"
    if [ "$HAS_SYSTEMD" = "yes" ]; then
        echo "  sudo systemctl restart postgresql"
    else
        echo "  sudo pg_ctlcluster $PG_VERSION main restart"
    fi
else
    log_warning "未找到pg_hba.conf: $PG_HBA"
fi

echo ""

# ==============================================================================
# 安装完成
# ==============================================================================

echo "========================================="
echo -e "${GREEN}✅ PostgreSQL $PG_VERSION 安装完成！${NC}"
echo "========================================="
echo ""
echo "📦 安装信息:"
echo "  版本: PostgreSQL $PG_VERSION"
echo "  系统: $OS_NAME $OS_VERSION ($OS_CODENAME)"
echo "  用户: $APP_DB_USER (已创建)"
if [ "$GRANT_SUPERUSER" = "yes" ]; then
    echo "  权限: SUPERUSER ⚠️"
else
    echo "  权限: CREATEDB (安全模式)"
fi
echo "  认证: peer (默认)"
echo ""
echo "🚀 下一步操作："
echo "  1. 验证安装:"
echo "     psql --version"
echo ""
echo "  2. 连接数据库:"
echo "     sudo -u postgres psql"
echo "     或: psql -U $APP_DB_USER postgres  # 如果peer认证配置正确"
echo ""
echo "  3. 创建测试数据库:"
echo "     sudo -u postgres createdb test_db -O $APP_DB_USER"
echo ""
echo "  4. 运行端到端测试:"
echo "     cd ${PROJECT_ROOT}"
echo "     ./scripts/end_to_end_test.sh"
echo ""
echo "📁 配置文件位置:"
echo "  主配置: /etc/postgresql/$PG_VERSION/main/postgresql.conf"
echo "  认证配置: /etc/postgresql/$PG_VERSION/main/pg_hba.conf"
echo ""
if [ "$HAS_SYSTEMD" = "yes" ]; then
    echo "🔧 常用命令:"
    echo "  启动服务: sudo systemctl start postgresql"
    echo "  停止服务: sudo systemctl stop postgresql"
    echo "  查看状态: sudo systemctl status postgresql"
    echo "  查看日志: sudo journalctl -u postgresql -f"
else
    echo "🔧 常用命令:"
    echo "  启动服务: sudo pg_ctlcluster $PG_VERSION main start"
    echo "  停止服务: sudo pg_ctlcluster $PG_VERSION main stop"
    echo "  查看状态: sudo pg_ctlcluster $PG_VERSION main status"
fi
echo ""
echo "⚙️  环境变量:"
echo "  PG_VERSION=18          # 安装指定版本"
echo "  GRANT_SUPERUSER=yes    # 授予超级权限（慎用）"
echo "  APP_DB_USER=amax       # 指定要创建的数据库用户"
echo "  ASSUME_YES=yes         # 非交互模式默认继续（慎用）"
echo ""
