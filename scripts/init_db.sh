#!/bin/bash
# ==============================================================================
# 多物种lncRNA调控网络数据库 - 一键建库脚本
# ==============================================================================
# 版本: v2.3
# 日期: 2025-11-20
# 用途: 自动化创建数据库、安装扩展、执行DDL、验证完整性
# ==============================================================================

# 遇到错误立即退出（含未定义变量与管道失败）
# -e: 任意命令失败即退出
# -u: 使用未定义变量即退出
# -o pipefail: 管道中任意环节失败即退出（避免 psql | grep 静默失败）
set -euo pipefail

# ==============================================================================
# 配置区域（可通过环境变量覆盖）
# ==============================================================================

DB_HOST="${DB_HOST:-localhost}"
DB_PORT="${DB_PORT:-5432}"
DB_USER="${DB_USER:-postgres}"
DB_NAME="${DB_NAME:-lncrna_production}"
DB_PASSWORD="${DB_PASSWORD:-}"  # 若需要密码，请设置 DB_PASSWORD 或 ~/.pgpass（脚本不会在非交互模式下等待密码输入）

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
        PGPASSWORD="$DB_PASSWORD" psql -w -v ON_ERROR_STOP=1 -h "$DB_HOST" -p "$DB_PORT" -U "$DB_USER" -d "$db" "$@"
    else
        # -w: 禁止交互式密码提示，避免在 CI/非交互 shell 中卡住
        psql -w -v ON_ERROR_STOP=1 -h "$DB_HOST" -p "$DB_PORT" -U "$DB_USER" -d "$db" "$@"
    fi
}

# 执行psql命令（连接postgres数据库）
run_psql_postgres() {
    if [ -n "$DB_PASSWORD" ]; then
        PGPASSWORD="$DB_PASSWORD" psql -w -v ON_ERROR_STOP=1 -h "$DB_HOST" -p "$DB_PORT" -U "$DB_USER" -d postgres "$@"
    else
        # -w: 禁止交互式密码提示，避免在 CI/非交互 shell 中卡住
        psql -w -v ON_ERROR_STOP=1 -h "$DB_HOST" -p "$DB_PORT" -U "$DB_USER" -d postgres "$@"
    fi
}

# SECURITY: 限制用于 SQL 标识符/字符串拼接的输入，避免脚本被异常值破坏
validate_identifier() {
    local name="$1"
    local value="$2"
    if [[ -z "$value" ]]; then
        log_error "$name 不能为空"
        exit 1
    fi
    # 当前脚本会将 DB_NAME/DB_USER 直接拼接进 SQL（未加引号），因此仅允许安全字符。
    # 如需使用特殊字符，请改为 psql 变量方式并使用 :\"var\" 引用。
    if [[ ! "$value" =~ ^[a-zA-Z0-9_]+$ ]]; then
        log_error "$name 包含非法字符: '$value'（仅允许字母/数字/下划线）"
        exit 1
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

    # 基本输入校验（避免 SQL/命令拼接异常）
    validate_identifier "DB_NAME" "$DB_NAME"
    validate_identifier "DB_USER" "$DB_USER"

    # 尽早测试数据库连接，避免后续流程在中途才失败
    log_info "测试 PostgreSQL 连接..."
    if ! run_psql_postgres -tAc "SELECT 1" > /dev/null 2>&1; then
        log_error "无法连接 PostgreSQL：$DB_HOST:$DB_PORT (user=$DB_USER, db=postgres)"
        log_error "请检查：PostgreSQL 是否运行、连接参数、认证方式（必要时设置 DB_PASSWORD 或 ~/.pgpass）"
        exit 1
    fi
    log_success "PostgreSQL 连接正常"

    # 检查schema文件存在性
    if [ ! -f "$SCHEMA_DIR/01_core.sql" ]; then
        log_error "找不到核心Schema文件: $SCHEMA_DIR/01_core.sql"
        exit 1
    fi

    # Phase 9.20: 02_extension.sql 已弃用，使用 04_extension_phase2.sql
    if [ "$INSTALL_EXTENSION_LAYER" = "yes" ] && [ ! -f "$SCHEMA_DIR/04_extension_phase2.sql" ]; then
        log_error "找不到扩展层Schema文件: $SCHEMA_DIR/04_extension_phase2.sql"
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
    # P1 兼容性：某些环境（例如非 en_US locale 的系统）可能不存在 en_US.UTF-8，导致 CREATE DATABASE 失败。
    # 先尝试显式指定 locale（便于在多数 Linux 环境获得一致排序/比较行为），失败则回退到集群默认 locale。
    if run_psql_postgres -c "CREATE DATABASE $DB_NAME ENCODING 'UTF8' LC_COLLATE='en_US.UTF-8' LC_CTYPE='en_US.UTF-8' TEMPLATE=template0"; then
        log_success "数据库创建成功"
        return
    fi

    log_warning "创建数据库失败：系统可能不支持 en_US.UTF-8 locale，回退使用 PostgreSQL 默认 locale"
    run_psql_postgres -c "CREATE DATABASE $DB_NAME ENCODING 'UTF8' TEMPLATE=template0"
    log_success "数据库创建成功（默认 locale）"
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

    # 可选性能优化：/analysis/summary (High Affinity, BA>=100) 预聚合物化视图
    # 依赖仅为核心表（regulations/genes），无需 ChIP-seq 扩展。
    if [ -f "$SCHEMA_DIR/07_mv_analysis_summary_high_affinity_ba100.sql" ]; then
        log_info "（可选）加速 /analysis/summary (High Affinity, BA>=100)："
        log_info "  psql -h $DB_HOST -p $DB_PORT -U $DB_USER -d $DB_NAME -f $SCHEMA_DIR/07_mv_analysis_summary_high_affinity_ba100.sql"
    fi
}

execute_extension_schema() {
    if [ "$INSTALL_EXTENSION_LAYER" = "yes" ]; then
        # Phase 9.20: 使用 04_extension_phase2.sql 替代已弃用的 02_extension.sql
        log_info "执行扩展层Schema (04_extension_phase2.sql)..."
        run_psql "$DB_NAME" -f "$SCHEMA_DIR/04_extension_phase2.sql"
        log_success "扩展层Schema执行完成"

        # Phase 9.20 Codex 审查修复: MV 依赖 ChIP-seq schema，不应自动执行
        # 物化视图需要在 chipseq_schema.sql 执行后单独运行
        if [ -f "$SCHEMA_DIR/05_mv_lncrna_chipseq_overlaps.sql" ]; then
            log_warning "物化视图 (05_mv_lncrna_chipseq_overlaps.sql) 需在 ChIP-seq schema 后手动执行"
            log_info "  执行顺序: chipseq_schema.sql → 05_mv_lncrna_chipseq_overlaps.sql"
            if [ -f "$SCHEMA_DIR/06_mv_lncrna_chipseq_overlaps_epigenetic_summary_ba100.sql" ]; then
                log_info "  （可选）加速 /analysis/summary: 06_mv_lncrna_chipseq_overlaps_epigenetic_summary_ba100.sql"
                log_info "  执行顺序: chipseq_schema.sql → 05_mv_lncrna_chipseq_overlaps.sql → 06_mv_lncrna_chipseq_overlaps_epigenetic_summary_ba100.sql"
            fi
        fi
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
    # Phase 9.20 Codex 审查修复: 04_extension_phase2.sql 只创建 feature_tracks 和 genomic_features
    if [ "$INSTALL_EXTENSION_LAYER" = "yes" ]; then
        local expected_ext_tables=2
        local ext_table_count=$(run_psql "$DB_NAME" -tAc "
            SELECT COUNT(*) FROM information_schema.tables
            WHERE table_schema = 'public'
              AND table_name IN ('feature_tracks', 'genomic_features')
        ")

        if [ "$ext_table_count" -ne "$expected_ext_tables" ]; then
            log_error "扩展层表数量不正确: 预期 $expected_ext_tables, 实际 $ext_table_count"
            exit 1
        fi
        log_success "扩展层验证通过: $ext_table_count 张表 (feature_tracks, genomic_features)"
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
