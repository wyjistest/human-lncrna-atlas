#!/bin/bash
# ==============================================================================
# 多物种lncRNA调控网络数据库 - 一键建库脚本
# ==============================================================================
# 版本: v2.3
# 日期: 2025-11-20
# 用途: 自动化创建数据库、安装扩展、执行DDL、验证完整性
# ==============================================================================

set -e  # 遇到错误立即退出
set -u  # 使用未定义变量时报错

# ==============================================================================
# 配置区域（可通过环境变量覆盖）
# ==============================================================================

DB_HOST="${DB_HOST:-localhost}"
DB_PORT="${DB_PORT:-5432}"
DB_USER="${DB_USER:-postgres}"
DB_NAME="${DB_NAME:-lncrna_network}"
DB_PASSWORD="${DB_PASSWORD:-}"  # 如果为空，将提示输入

SCHEMA_DIR="$(cd "$(dirname "$0")/../schema/v2.3" && pwd)"
INSTALL_EXTENSION_LAYER="${INSTALL_EXTENSION_LAYER:-no}"  # yes/no
FORCE_RECREATE="${FORCE_RECREATE:-no}"  # yes/no - 用于非交互模式

# 颜色输出
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
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

# 执行psql命令（带密码处理）
run_psql() {
    local db="$1"
    shift
    if [ -n "$DB_PASSWORD" ]; then
        PGPASSWORD="$DB_PASSWORD" psql -h "$DB_HOST" -p "$DB_PORT" -U "$DB_USER" -d "$db" "$@"
    else
        psql -h "$DB_HOST" -p "$DB_PORT" -U "$DB_USER" -d "$db" "$@"
    fi
}

# 执行psql命令（连接postgres数据库）
run_psql_postgres() {
    if [ -n "$DB_PASSWORD" ]; then
        PGPASSWORD="$DB_PASSWORD" psql -h "$DB_HOST" -p "$DB_PORT" -U "$DB_USER" -d postgres "$@"
    else
        psql -h "$DB_HOST" -p "$DB_PORT" -U "$DB_USER" -d postgres "$@"
    fi
}

# 检查命令是否存在
check_command() {
    if ! command -v "$1" &> /dev/null; then
        log_error "$1 command not found. Please install PostgreSQL client."
        exit 1
    fi
}

# ==============================================================================
# 主流程
# ==============================================================================

print_banner() {
    echo ""
    echo "========================================="
    echo " lncRNA调控网络数据库 - 一键建库脚本"
    echo " 版本: v2.3"
    echo "========================================="
    echo ""
}

print_config() {
    log_info "配置信息:"
    echo "  数据库主机: $DB_HOST:$DB_PORT"
    echo "  数据库用户: $DB_USER"
    echo "  数据库名称: $DB_NAME"
    echo "  Schema目录: $SCHEMA_DIR"
    echo "  安装扩展层: $INSTALL_EXTENSION_LAYER"
    echo ""
}

check_prerequisites() {
    log_info "检查依赖..."
    check_command psql
    check_command md5sum

    # 检查schema文件存在性
    if [ ! -f "$SCHEMA_DIR/01_core.sql" ]; then
        log_error "找不到核心Schema文件: $SCHEMA_DIR/01_core.sql"
        exit 1
    fi

    if [ "$INSTALL_EXTENSION_LAYER" = "yes" ] && [ ! -f "$SCHEMA_DIR/02_extension.sql" ]; then
        log_error "找不到扩展层Schema文件: $SCHEMA_DIR/02_extension.sql"
        exit 1
    fi

    log_success "依赖检查通过"
}

check_database_exists() {
    log_info "检查数据库是否已存在..."
    if run_psql_postgres -tAc "SELECT 1 FROM pg_database WHERE datname='$DB_NAME'" | grep -q 1; then
        log_warning "数据库 '$DB_NAME' 已存在"

        # 非交互模式支持
        if [ "${FORCE_RECREATE}" = "yes" ]; then
            response="yes"
        elif [ ! -t 0 ]; then
            # Non-interactive mode - default to safe behavior
            log_info "Non-interactive mode detected, keeping existing database"
            response="no"
        else
            read -p "是否删除并重新创建? (yes/no): " response
        fi

        if [ "$response" != "yes" ]; then
            log_info "保留现有数据库，退出"
            exit 0
        fi
        log_info "删除现有数据库..."
        run_psql_postgres -c "DROP DATABASE IF EXISTS $DB_NAME"
        log_success "数据库已删除"
    fi
}

create_database() {
    log_info "创建数据库 '$DB_NAME'..."
    run_psql_postgres -c "CREATE DATABASE $DB_NAME ENCODING 'UTF8' LC_COLLATE='en_US.UTF-8' LC_CTYPE='en_US.UTF-8' TEMPLATE=template0"
    log_success "数据库创建成功"
}

install_extensions() {
    log_info "安装PostgreSQL扩展..."
    run_psql "$DB_NAME" -c "CREATE EXTENSION IF NOT EXISTS pgcrypto"
    log_success "扩展安装完成 (pgcrypto)"
}

execute_core_schema() {
    log_info "执行核心层Schema (01_core.sql)..."
    run_psql "$DB_NAME" -f "$SCHEMA_DIR/01_core.sql" -q
    log_success "核心层Schema执行完成"
}

execute_extension_schema() {
    if [ "$INSTALL_EXTENSION_LAYER" = "yes" ]; then
        log_info "执行扩展层Schema (02_extension.sql)..."
        run_psql "$DB_NAME" -f "$SCHEMA_DIR/02_extension.sql"
        log_success "扩展层Schema执行完成"
    else
        log_info "跳过扩展层Schema（设置 INSTALL_EXTENSION_LAYER=yes 以安装）"
    fi
}

verify_installation() {
    log_info "验证安装..."

    # 检查表数量
    local expected_core_tables=12
    local core_table_count=$(run_psql "$DB_NAME" -tAc "
        SELECT COUNT(*) FROM information_schema.tables
        WHERE table_schema = 'public'
          AND table_name IN ('species', 'core_id_assignments', 'core_genes', 'genes',
                              'traits', 'ontologies', 'trait_gene_associations',
                              'import_batches', 'regulations', 'sequences',
                              'network_jobs', 'network_snapshots')
    ")

    if [ "$core_table_count" -ne "$expected_core_tables" ]; then
        log_error "核心层表数量不正确: 预期 $expected_core_tables, 实际 $core_table_count"
        exit 1
    fi
    log_success "核心层验证通过: $core_table_count 张表"

    # 检查扩展层（如果安装了）
    if [ "$INSTALL_EXTENSION_LAYER" = "yes" ]; then
        local expected_ext_tables=5
        local ext_table_count=$(run_psql "$DB_NAME" -tAc "
            SELECT COUNT(*) FROM information_schema.tables
            WHERE table_schema = 'public'
              AND table_name IN ('feature_tracks', 'genomic_features', 'feature_gene_links',
                                  'experiments', 'experiment_features')
        ")

        if [ "$ext_table_count" -ne "$expected_ext_tables" ]; then
            log_error "扩展层表数量不正确: 预期 $expected_ext_tables, 实际 $ext_table_count"
            exit 1
        fi
        log_success "扩展层验证通过: $ext_table_count 张表"
    fi

    # 检查species表是否有4行数据
    local species_count=$(run_psql "$DB_NAME" -tAc "SELECT COUNT(*) FROM species")
    if [ "$species_count" -ne 4 ]; then
        log_warning "species表行数异常: 预期 4, 实际 $species_count"
    else
        log_success "物种数据验证通过: $species_count 个物种"
    fi

    # 检查feature_tracks是否有5行数据（如果安装了扩展层）
    if [ "$INSTALL_EXTENSION_LAYER" = "yes" ]; then
        local tracks_count=$(run_psql "$DB_NAME" -tAc "SELECT COUNT(*) FROM feature_tracks")
        if [ "$tracks_count" -ne 5 ]; then
            log_warning "feature_tracks表行数异常: 预期 5, 实际 $tracks_count"
        else
            log_success "Feature tracks验证通过: $tracks_count 个tracks"
        fi
    fi
}

print_summary() {
    echo ""
    echo "========================================="
    echo " 数据库初始化完成!"
    echo "========================================="
    echo ""
    echo "连接信息:"
    echo "  psql -h $DB_HOST -p $DB_PORT -U $DB_USER -d $DB_NAME"
    echo ""
    echo "数据库结构:"
    run_psql "$DB_NAME" -c "\dt"
    echo ""
    echo "下一步操作:"
    echo "  1. 导入核心数据: etl/examples/import_regulations.py"
    echo "  2. 运行测试查询: psql -d $DB_NAME -f tests/smoke_test.sql"
    if [ "$INSTALL_EXTENSION_LAYER" != "yes" ]; then
        echo "  3. 安装扩展层: INSTALL_EXTENSION_LAYER=yes ./scripts/init_db.sh"
    fi
    echo ""
    echo "========================================="
}

# ==============================================================================
# 入口点
# ==============================================================================

main() {
    print_banner
    print_config
    check_prerequisites
    check_database_exists
    create_database
    install_extensions
    execute_core_schema
    execute_extension_schema
    verify_installation
    print_summary
}

# 执行主流程
main "$@"
