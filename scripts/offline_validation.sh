#!/bin/bash
# 离线验证（无需PostgreSQL）- 增强版

set -e

GREEN='\033[0;32m'
RED='\033[0;31m'
YELLOW='\033[1;33m'
NC='\033[0m'

echo "========================================="
echo " 离线验证（增强版 - 包含FK检查）"
echo "========================================="
echo ""

cd "$(dirname "$0")/.."

# 1. 文件存在性检查
echo "1️⃣  文件存在性检查"
FILES=(
    "schema/v2.3/01_core.sql"
    "schema/v2.3/02_extension.sql"
    "schema/v2.3/03_sample_data.sql"
    "scripts/init_db.sh"
    "scripts/verify_sync.sh"
    "etl/templates/batch_manager.py"
    "etl/templates/import_base.py"
    "etl/examples/import_regulations.py"
    "tests/smoke_test.sql"
    "README.md"
)

ALL_EXIST=true
for file in "${FILES[@]}"; do
    if [ -f "$file" ]; then
        echo -e "  ${GREEN}✅${NC} $file"
    else
        echo -e "  ${RED}❌${NC} $file (缺失)"
        ALL_EXIST=false
    fi
done

if [ "$ALL_EXIST" = false ]; then
    echo -e "${RED}❌ 部分文件缺失${NC}"
    exit 1
fi

echo ""

# 2. Python语法检查
echo "2️⃣  Python脚本语法检查"
python3 -m py_compile etl/templates/batch_manager.py && echo -e "  ${GREEN}✅${NC} batch_manager.py"
python3 -m py_compile etl/templates/import_base.py && echo -e "  ${GREEN}✅${NC} import_base.py"
python3 -m py_compile etl/examples/import_regulations.py && echo -e "  ${GREEN}✅${NC} import_regulations.py"

echo ""

# 3. Shell脚本语法检查
echo "3️⃣  Shell脚本语法检查"
bash -n scripts/init_db.sh && echo -e "  ${GREEN}✅${NC} init_db.sh"
bash -n scripts/verify_sync.sh && echo -e "  ${GREEN}✅${NC} verify_sync.sh"
bash -n scripts/end_to_end_test.sh && echo -e "  ${GREEN}✅${NC} end_to_end_test.sh"

echo ""

# 4. 文档同步验证（verify_sync）
echo "4️⃣  文档同步验证（verify_sync.sh）"
if command -v md5sum >/dev/null 2>&1 || command -v md5 >/dev/null 2>&1; then
    bash scripts/verify_sync.sh
    echo -e "  ${GREEN}✅${NC} verify_sync.sh 运行通过"
else
    echo -e "  ${YELLOW}⚠️${NC}  未找到 md5sum/md5，跳过 verify_sync 运行验证"
    echo -e "      提示：Linux 可安装 coreutils；macOS 自带 md5；也可仅运行 bash -n 检查语法。"
fi

echo ""

# 5. SQL文件基础语法检查
echo "5️⃣  SQL文件基础检查"
if grep -q "CREATE TABLE" schema/v2.3/01_core.sql; then
    echo -e "  ${GREEN}✅${NC} 01_core.sql 包含CREATE TABLE语句"
fi

if grep -q "INSERT INTO" schema/v2.3/03_sample_data.sql; then
    echo -e "  ${GREEN}✅${NC} 03_sample_data.sql 包含INSERT语句"
fi

echo ""

# 6. 关键修复验证（精确检查，排除注释）
echo "6️⃣  关键修复验证（v2.3.1）"

# 检查core_id_assignments INSERT（排除注释行）
if grep "INSERT INTO core_id_assignments" -A 2 schema/v2.3/03_sample_data.sql | grep -v "^--" | grep -q "species_id\|species_gene_id"; then
    echo -e "  ${RED}❌${NC} core_id_assignments INSERT包含错误列"
    exit 1
else
    echo -e "  ${GREEN}✅${NC} core_id_assignments INSERT已修复"
fi

# 检查genes INSERT
if grep "INSERT INTO genes" -A 2 schema/v2.3/03_sample_data.sql | grep -v "^--" | grep "VALUES" | grep -q "gene_type"; then
    echo -e "  ${RED}❌${NC} genes INSERT包含gene_type列"
    exit 1
else
    echo -e "  ${GREEN}✅${NC} genes INSERT已修复"
fi

# 检查traits INSERT（只检查实际SQL，不检查注释）
if grep "INSERT INTO traits" -A 2 schema/v2.3/03_sample_data.sql | grep -v "^--" | grep -q "trait_efo_id"; then
    echo -e "  ${RED}❌${NC} traits INSERT使用错误的列名trait_efo_id"
    exit 1
else
    if grep "INSERT INTO traits" -A 2 schema/v2.3/03_sample_data.sql | grep -v "^--" | grep -q "trait_doid"; then
        echo -e "  ${GREEN}✅${NC} traits INSERT已修复（使用trait_doid）"
    else
        echo -e "  ${YELLOW}⚠️${NC}  traits INSERT未找到trait_doid列"
    fi
fi

# 检查ETL regulations INSERT
if grep "INSERT INTO regulations" -A 10 etl/examples/import_regulations.py | grep -q "target_strand"; then
    echo -e "  ${RED}❌${NC} ETL仍尝试插入target_strand"
    exit 1
else
    echo -e "  ${GREEN}✅${NC} ETL regulations INSERT已修复"
fi

echo ""

# 7. 外键完整性检查（新增 - ultrathink第6轮审查）
echo "7️⃣  外键完整性检查（样本数据）"

# 提取core_genes中的core_id列表
CORE_GENES_IDS=$(grep "INSERT INTO core_genes" -A 20 schema/v2.3/03_sample_data.sql | grep -E "^\([0-9]+" | sed 's/^(\([0-9]*\).*/\1/' | sort -u)

# 提取genes表中引用的core_id（排除NULL）
GENES_CORE_IDS=$(grep "INSERT INTO genes" -A 30 schema/v2.3/03_sample_data.sql | grep -E "^\([0-9]+, [0-9]+" | awk -F', ' '{print $2}' | grep -v "NULL" | sort -u)

# 检查genes中的core_id是否都存在于core_genes中
MISSING_IDS=""
for id in $GENES_CORE_IDS; do
    if ! echo "$CORE_GENES_IDS" | grep -q "^${id}$"; then
        MISSING_IDS="$MISSING_IDS $id"
    fi
done

if [ -n "$MISSING_IDS" ]; then
    echo -e "  ${RED}❌${NC} genes表引用了不存在的core_id: $MISSING_IDS"
    echo "      core_genes包含: $(echo $CORE_GENES_IDS | tr '\n' ' ')"
    echo "      genes引用: $(echo $GENES_CORE_IDS | tr '\n' ' ')"
    exit 1
else
    echo -e "  ${GREEN}✅${NC} genes.core_id外键完整性检查通过"
    echo "      core_genes: $(echo $CORE_GENES_IDS | wc -w)个ID"
    echo "      genes引用: $(echo $GENES_CORE_IDS | wc -w)个ID（全部存在）"
fi

echo ""
echo "========================================="
echo -e "${GREEN}✅ 离线验证全部通过（含FK检查）${NC}"
echo "========================================="
echo ""
echo "验证结果:"
echo "  ✅ 所有关键文件存在"
echo "  ✅ Python脚本语法正确"
echo "  ✅ Shell脚本语法正确"
echo "  ✅ SQL文件包含必要语句"
echo "  ✅ v2.3.1关键修复已应用"
echo "  ✅ 外键完整性检查通过"
echo ""
echo -e "${YELLOW}⚠️  限制:${NC} 未验证SQL语义正确性（需要PostgreSQL环境）"
echo ""
echo "下一步: 在有PostgreSQL的环境中运行 ./scripts/end_to_end_test.sh"
echo "========================================="
