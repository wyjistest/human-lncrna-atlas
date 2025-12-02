#!/bin/bash
# ==============================================================================
# PostgreSQL 安装脚本 (Ubuntu/Debian)
# ==============================================================================
# 版本: v2.1
# 支持: PostgreSQL 15/16/17/18
# 默认: PostgreSQL 17 (推荐稳定版)
# 兼容: Ubuntu 20.04+, Debian 11+
# ==============================================================================

set -e

# 可配置版本（默认17）
PG_VERSION="${PG_VERSION:-17}"
GRANT_SUPERUSER="${GRANT_SUPERUSER:-no}"  # 默认不授予超级权限

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

echo "========================================="
echo " PostgreSQL $PG_VERSION 安装向导"
echo "========================================="
echo ""
echo "📋 版本说明:"
echo "  • PostgreSQL 18 (最新): 2025-11-13发布，最新特性"
echo "  • PostgreSQL 17 (推荐): 稳定版，适合生产环境"
echo "  • PostgreSQL 15/16: 旧版本，也很稳定"
echo ""
echo "💡 切换版本: export PG_VERSION=18 && ./install_postgresql.sh"
echo ""

# ==============================================================================
# 前置检查
# ==============================================================================

log_step 0 "系统环境检查"

# 检测发行版
if [ -f /etc/os-release ]; then
    . /etc/os-release
    OS_NAME=$ID
    OS_VERSION=$VERSION_ID
    OS_CODENAME=$VERSION_CODENAME

    # 如果没有VERSION_CODENAME，尝试用lsb_release
    if [ -z "$OS_CODENAME" ]; then
        OS_CODENAME=$(lsb_release -cs 2>/dev/null || echo "")
    fi
else
    log_error "无法检测操作系统"
    exit 1
fi

echo "检测到系统: $OS_NAME $OS_VERSION ($OS_CODENAME)"

# 验证支持的发行版
case "$OS_NAME" in
    ubuntu|debian)
        log_success "支持的操作系统"
        ;;
    *)
        log_warning "未测试的操作系统: $OS_NAME"
        echo "脚本仅在Ubuntu/Debian测试过，继续安装可能失败"
        read -p "是否继续？(y/N) " -n 1 -r
        echo
        if [[ ! $REPLY =~ ^[Yy]$ ]]; then
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

# 安装必要的工具
sudo apt-get update
sudo apt-get install -y wget ca-certificates gnupg

# 【修复1】：使用新的GPG key方法，不使用弃用的apt-key
KEYRING_DIR="/usr/share/keyrings"
sudo mkdir -p "$KEYRING_DIR"

if [ ! -f "$KEYRING_DIR/postgresql-archive-keyring.gpg" ]; then
    echo "下载PostgreSQL GPG key..."
    wget --quiet -O - https://www.postgresql.org/media/keys/ACCC4CF8.asc | \
        gpg --dearmor | \
        sudo tee "$KEYRING_DIR/postgresql-archive-keyring.gpg" > /dev/null
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
    sudo tee "$REPO_FILE"

log_success "PostgreSQL仓库已添加 (使用 $OS_CODENAME-pgdg)"
echo ""

# ==============================================================================
# Step 2: 安装PostgreSQL
# ==============================================================================

log_step 2 "安装PostgreSQL $PG_VERSION"

sudo apt-get update
sudo apt-get install -y postgresql-$PG_VERSION postgresql-contrib-$PG_VERSION

log_success "PostgreSQL $PG_VERSION 安装完成"
echo ""

# ==============================================================================
# Step 3: 启动PostgreSQL服务
# ==============================================================================

log_step 3 "启动PostgreSQL服务"

if [ "$HAS_SYSTEMD" = "yes" ]; then
    sudo systemctl start postgresql
    sudo systemctl enable postgresql

    # 检查状态
    if sudo systemctl is-active --quiet postgresql; then
        log_success "PostgreSQL服务已启动"
    else
        log_error "PostgreSQL服务启动失败"
        echo "查看日志: sudo journalctl -u postgresql -n 50"
        exit 1
    fi
else
    log_warning "无systemd，尝试使用pg_ctlcluster..."
    sudo pg_ctlcluster $PG_VERSION main start || {
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
sudo -u postgres psql -c "SELECT version();" 2>/dev/null || {
    log_error "无法连接到PostgreSQL"
    exit 1
}

echo ""

# ==============================================================================
# Step 5: 创建应用数据库用户（修复：可选超级权限）
# ==============================================================================

log_step 5 "创建应用数据库用户"

# 检查用户是否已存在
if sudo -u postgres psql -tAc "SELECT 1 FROM pg_roles WHERE rolname='$USER'" | grep -q 1; then
    echo "用户 $USER 已存在"
else
    echo "创建PostgreSQL用户: $USER"

    # 【修复3】：根据GRANT_SUPERUSER变量决定是否授予超级权限
    if [ "$GRANT_SUPERUSER" = "yes" ]; then
        sudo -u postgres createuser -s "$USER"
        log_success "用户 $USER 创建成功（拥有超级用户权限）"
        log_warning "生产环境不建议授予超级权限！"
    else
        sudo -u postgres createuser -d "$USER"  # 只授予创建数据库权限
        log_success "用户 $USER 创建成功（可创建数据库）"
        echo "提示：如需超级权限，运行:"
        echo "  sudo -u postgres psql -c \"ALTER USER $USER WITH SUPERUSER;\""
        echo "  或: export GRANT_SUPERUSER=yes && ./install_postgresql.sh"
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
    sudo grep "^local" "$PG_HBA" | head -3

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
echo "  用户: $USER (已创建)"
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
echo "     或: psql -U $USER postgres  # 如果peer认证配置正确"
echo ""
echo "  3. 创建测试数据库:"
echo "     sudo -u postgres createdb test_db -O $USER"
echo ""
echo "  4. 运行端到端测试:"
echo "     cd /data/wenyujianData/humanLncAtlas"
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
echo ""
