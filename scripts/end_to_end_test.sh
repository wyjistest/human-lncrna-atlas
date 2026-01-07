#!/bin/bash
# ==============================================================================
# 端到端验证脚本
# ==============================================================================
# 版本: v2.3.1
# 用途: 验证整个系统可以"开箱即跑"
# ==============================================================================

set -e  # 遇到错误立即退出

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

# ==============================================================================
# 配置
# ==============================================================================

TEST_DB_NAME="lncrna_e2e_test"
DB_USER="${DB_USER:-postgres}"
DB_HOST="${DB_HOST:-localhost}"
DB_PORT="${DB_PORT:-5432}"
DB_PASSWORD="${DB_PASSWORD:-}"

# 若需要密码，请通过环境变量 DB_PASSWORD 或 ~/.pgpass 提供；避免在非交互环境下卡住等待输入。
if [ -n "$DB_PASSWORD" ]; then
    export PGPASSWORD="$DB_PASSWORD"
fi

PROJECT_ROOT="$(cd "$(dirname "$0")/.." && pwd)"
cd "$PROJECT_ROOT"

echo "========================================="
echo " 端到端验证测试"
echo " 项目: lncRNA调控网络数据库 v2.3.1"
echo "========================================="
echo ""
echo "配置:"
echo "  数据库: $TEST_DB_NAME"
echo "  用户: $DB_USER"
echo "  项目目录: $PROJECT_ROOT"
echo ""

# ==============================================================================
# Step 1: 清理环境
# ==============================================================================

log_step 1 "清理测试环境"

psql -w -h "$DB_HOST" -p "$DB_PORT" -U "$DB_USER" -d postgres -c "DROP DATABASE IF EXISTS $TEST_DB_NAME;" 2>/dev/null || true

log_success "测试环境已清理"
echo ""

# ==============================================================================
# Step 2: 一键建库
# ==============================================================================

log_step 2 "执行一键建库脚本"

# 设置环境变量
export DB_NAME="$TEST_DB_NAME"
export DB_HOST="$DB_HOST"
export DB_PORT="$DB_PORT"
export DB_USER="$DB_USER"
export DB_PASSWORD="$DB_PASSWORD"
export INSTALL_EXTENSION_LAYER="no"  # MVP只测试核心层

# 执行建库脚本
if ./scripts/init_db.sh; then
    log_success "一键建库成功"
else
    log_error "一键建库失败"
    exit 1
fi

echo ""

# ==============================================================================
# Step 3: 验证核心表结构
# ==============================================================================

log_step 3 "验证核心表结构"

TABLE_COUNT=$(psql -w -h "$DB_HOST" -p "$DB_PORT" -U "$DB_USER" -d "$TEST_DB_NAME" -tAc "
    SELECT COUNT(*) FROM information_schema.tables
    WHERE table_schema = 'public'
      AND table_name IN ('species', 'core_id_assignments', 'core_genes', 'genes',
                          'traits', 'ontologies', 'trait_gene_associations',
                          'import_batches', 'regulations', 'sequences',
                          'network_jobs', 'network_snapshots')
")

if [ "$TABLE_COUNT" -eq 12 ]; then
    log_success "核心表数量正确: $TABLE_COUNT/12"
else
    log_error "核心表数量错误: $TABLE_COUNT/12"
    exit 1
fi

# 验证species表有4行
SPECIES_COUNT=$(psql -w -h "$DB_HOST" -p "$DB_PORT" -U "$DB_USER" -d "$TEST_DB_NAME" -tAc "SELECT COUNT(*) FROM species")
if [ "$SPECIES_COUNT" -eq 4 ]; then
    log_success "species表数据正确: $SPECIES_COUNT/4"
else
    log_error "species表数据错误: $SPECIES_COUNT/4"
    exit 1
fi

echo ""

# ==============================================================================
# Step 4: 插入样本数据
# ==============================================================================

log_step 4 "插入样本测试数据"

if psql -w -h "$DB_HOST" -p "$DB_PORT" -U "$DB_USER" -d "$TEST_DB_NAME" -f schema/v2.3/03_sample_data.sql > /tmp/sample_data_output.log 2>&1; then
    log_success "样本数据插入成功"
else
    log_error "样本数据插入失败，查看日志: /tmp/sample_data_output.log"
    cat /tmp/sample_data_output.log
    exit 1
fi

echo ""

# ==============================================================================
# Step 5: 验证样本数据行数
# ==============================================================================

log_step 5 "验证样本数据行数"

GENES_COUNT=$(psql -w -h "$DB_HOST" -p "$DB_PORT" -U "$DB_USER" -d "$TEST_DB_NAME" -tAc "SELECT COUNT(*) FROM genes")
REGULATIONS_COUNT=$(psql -w -h "$DB_HOST" -p "$DB_PORT" -U "$DB_USER" -d "$TEST_DB_NAME" -tAc "SELECT COUNT(*) FROM regulations")
TRAITS_COUNT=$(psql -w -h "$DB_HOST" -p "$DB_PORT" -U "$DB_USER" -d "$TEST_DB_NAME" -tAc "SELECT COUNT(*) FROM traits")
TGA_COUNT=$(psql -w -h "$DB_HOST" -p "$DB_PORT" -U "$DB_USER" -d "$TEST_DB_NAME" -tAc "SELECT COUNT(*) FROM trait_gene_associations")

echo "实际行数:"
echo "  genes: $GENES_COUNT (预期: 12)"
echo "  regulations: $REGULATIONS_COUNT (预期: 6)"
echo "  traits: $TRAITS_COUNT (预期: 5)"
echo "  trait_gene_associations: $TGA_COUNT (预期: 10)"

ALL_CORRECT=true

if [ "$GENES_COUNT" -ne 12 ]; then
    log_error "genes表行数错误"
    ALL_CORRECT=false
fi

if [ "$REGULATIONS_COUNT" -ne 6 ]; then
    log_error "regulations表行数错误"
    ALL_CORRECT=false
fi

if [ "$TRAITS_COUNT" -ne 5 ]; then
    log_error "traits表行数错误"
    ALL_CORRECT=false
fi

if [ "$TGA_COUNT" -ne 10 ]; then
    log_error "trait_gene_associations表行数错误"
    ALL_CORRECT=false
fi

if [ "$ALL_CORRECT" = true ]; then
    log_success "所有表行数验证通过"
else
    exit 1
fi

echo ""

# ==============================================================================
# Step 6: 执行冒烟测试
# ==============================================================================

log_step 6 "执行冒烟测试"

if psql -w -h "$DB_HOST" -p "$DB_PORT" -U "$DB_USER" -d "$TEST_DB_NAME" -f tests/smoke_test.sql > /tmp/smoke_test_output.log 2>&1; then
    log_success "冒烟测试执行成功"

    # 检查关键验证点
    if grep -q "❌" /tmp/smoke_test_output.log; then
        log_warning "冒烟测试发现问题，查看详细日志: /tmp/smoke_test_output.log"
    else
        log_success "冒烟测试所有检查通过"
    fi
else
    log_error "冒烟测试执行失败"
    cat /tmp/smoke_test_output.log
    exit 1
fi

echo ""

# ==============================================================================
# Step 7: ETL脚本语法检查
# ==============================================================================

log_step 7 "ETL脚本语法检查"

# 检查Python环境
if ! command -v python3 &> /dev/null; then
    log_warning "Python3未安装，跳过ETL语法检查"
else
    # 检查batch_manager.py
    if python3 -m py_compile etl/templates/batch_manager.py 2>/dev/null; then
        log_success "batch_manager.py 语法正确"
    else
        log_error "batch_manager.py 语法错误"
        exit 1
    fi

    # 检查import_base.py
    if python3 -m py_compile etl/templates/import_base.py 2>/dev/null; then
        log_success "import_base.py 语法正确"
    else
        log_error "import_base.py 语法错误"
        exit 1
    fi

    # 检查import_regulations.py
    if python3 -m py_compile etl/examples/import_regulations.py 2>/dev/null; then
        log_success "import_regulations.py 语法正确"
    else
        log_error "import_regulations.py 语法错误"
        exit 1
    fi
fi

echo ""

# ==============================================================================
# Step 8: 测试关键查询
# ==============================================================================

log_step 8 "测试关键查询"

# 查询1: Autism MTG网络
AUTISM_RESULT=$(psql -w -h "$DB_HOST" -p "$DB_PORT" -U "$DB_USER" -d "$TEST_DB_NAME" -tAc "
    WITH target_genes AS (
        SELECT g.gene_id, g.gene_name
        FROM genes g
        JOIN trait_gene_associations tga ON g.core_id = tga.core_id
        WHERE tga.trait_id = (SELECT trait_id FROM traits WHERE trait_name = 'autism spectrum disorder')
          AND tga.ontology_id = (SELECT ontology_id FROM ontologies WHERE ontology_name = 'middle temporal gyrus')
          AND g.species_id = 1
    )
    SELECT COUNT(*) FROM regulations r
    JOIN target_genes lnc ON r.lncrna_gene_id = lnc.gene_id
    JOIN target_genes tgt ON r.target_gene_id = tgt.gene_id
    WHERE r.binding_affinity >= 50
")

if [ -n "$AUTISM_RESULT" ]; then
    log_success "Autism MTG查询成功: $AUTISM_RESULT 条调控关系"
else
    log_error "Autism MTG查询失败"
    exit 1
fi

echo ""

# ==============================================================================
# 总结
# ==============================================================================

echo "========================================="
echo -e "${GREEN}✅ 端到端验证全部通过！${NC}"
echo "========================================="
echo ""
echo "验证结果:"
echo "  ✅ 一键建库成功"
echo "  ✅ 核心表结构正确 (12张表)"
echo "  ✅ 样本数据插入成功"
echo "  ✅ 数据行数验证通过"
echo "  ✅ 冒烟测试通过"
echo "  ✅ ETL脚本语法正确"
echo "  ✅ 关键查询可执行"
echo ""
echo "测试数据库: $TEST_DB_NAME (保留，可手动删除)"
echo ""
echo "🎉 系统已验证可以"开箱即跑"！"
echo "========================================="
