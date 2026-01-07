#!/usr/bin/env bash
# v2.3 同步验证脚本（增强版）
#
# 目标：
# - 验证 schema 与设计文档的一致性（版本号/关键索引/示例查询）
# - 提供可复现的“文件指纹”校验（MD5）
#
# 兼容性：
# - 支持从任意工作目录运行（自动定位仓库根目录）
# - 同时兼容旧路径（schema_mvp_core.sql / DATABASE_DESIGN_FINAL.md）
#   与当前路径（schema/v2.3/01_core.sql / docs/DATABASE_DESIGN_FINAL.md）
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(cd "${SCRIPT_DIR}/.." && pwd)"

relpath() {
    local path="$1"
    if [[ "$path" == "${REPO_ROOT}/"* ]]; then
        echo "${path#${REPO_ROOT}/}"
        return 0
    fi
    echo "$path"
}

md5_file() {
    local file="$1"
    if command -v md5sum >/dev/null 2>&1; then
        md5sum "$file" | awk '{print $1}'
        return 0
    fi
    # macOS fallback
    if command -v md5 >/dev/null 2>&1; then
        md5 -q "$file"
        return 0
    fi
    echo "❌ 缺少 md5 工具：请安装 md5sum(coreutils) 或使用 macOS 自带 md5" >&2
    return 1
}

pick_first_existing() {
    local picked=""
    for candidate in "$@"; do
        if [ -f "$candidate" ]; then
            picked="$candidate"
            break
        fi
    done
    echo "$picked"
}

extract_version() {
    local file="$1"
    head -20 "$file" | awk 'match($0, /v[0-9]+\.[0-9]+/) {print substr($0, RSTART, RLENGTH); exit}'
}

echo "========================================="
echo "文件完整性校验 v2.3"
echo "========================================="
echo ""

# 检查MD5
echo "1️⃣  MD5校验..."

# 自动定位目标文件（支持新旧路径）
SCHEMA_FILE="$(pick_first_existing \
    "${REPO_ROOT}/schema/v2.3/01_core.sql" \
    "${REPO_ROOT}/schema_mvp_core.sql" \
)"
DOC_FILE="$(pick_first_existing \
    "${REPO_ROOT}/docs/DATABASE_DESIGN_FINAL.md" \
    "${REPO_ROOT}/DATABASE_DESIGN_FINAL.md" \
)"

if [ -z "${SCHEMA_FILE}" ]; then
    echo "❌ 找不到 schema 文件"
    echo "   期望路径之一：schema/v2.3/01_core.sql 或 schema_mvp_core.sql"
    exit 1
fi
if [ -z "${DOC_FILE}" ]; then
    echo "❌ 找不到设计文档"
    echo "   期望路径之一：docs/DATABASE_DESIGN_FINAL.md 或 DATABASE_DESIGN_FINAL.md"
    exit 1
fi

# 文件指纹（固定值用于验证“是否为已声明的官方版本”）
#
# 注意：这不是“schema/文档一致性”的唯一判断依据（后续还有版本/索引/示例校验），
# 但可用于快速识别是否在检查预期版本的文件。
if [[ "$(relpath "$DOC_FILE")" == "docs/DATABASE_DESIGN_FINAL.md" ]]; then
    EXPECTED_DOC="d8209f2f7cd7bf6d14410c440f84e658"
else
    # 旧路径（历史文件名）
    EXPECTED_DOC="eb17f899a7a423bfb06e63826106e6f5"
fi
if [[ "$(relpath "$SCHEMA_FILE")" == "schema/v2.3/01_core.sql" ]]; then
    EXPECTED_SCHEMA="540c38797a68b72655a9390128ddf64e"
else
    # 旧文件名（历史路径）
    EXPECTED_SCHEMA="1b3ab40c3d82a15386e010ea4a1d4af4"
fi

SCHEMA_DISPLAY="$(relpath "$SCHEMA_FILE")"
DOC_DISPLAY="$(relpath "$DOC_FILE")"

ACTUAL_SCHEMA="$(md5_file "$SCHEMA_FILE")"
ACTUAL_DOC="$(md5_file "$DOC_FILE")"

if [ "$ACTUAL_SCHEMA" == "$EXPECTED_SCHEMA" ]; then
    echo "✅ ${SCHEMA_DISPLAY} 校验通过"
else
    echo "❌ ${SCHEMA_DISPLAY} 校验失败"
    echo "   预期: $EXPECTED_SCHEMA"
    echo "   实际: $ACTUAL_SCHEMA"
    exit 1
fi

if [ "$ACTUAL_DOC" == "$EXPECTED_DOC" ]; then
    echo "✅ ${DOC_DISPLAY} 校验通过"
else
    echo "❌ ${DOC_DISPLAY} 校验失败"
    echo "   预期: $EXPECTED_DOC"
    echo "   实际: $ACTUAL_DOC"
    exit 1
fi

echo ""
echo "2️⃣  版本号验证..."
SCHEMA_VERSION="$(extract_version "$SCHEMA_FILE")"
DOC_VERSION="$(extract_version "$DOC_FILE")"

if [ -z "${SCHEMA_VERSION}" ] || [ -z "${DOC_VERSION}" ]; then
    echo "❌ 无法解析版本号（请检查文件头部是否包含版本标记）"
    echo "   Schema: ${SCHEMA_DISPLAY}"
    echo "   文档:  ${DOC_DISPLAY}"
    exit 1
fi

if [ "$SCHEMA_VERSION" == "$DOC_VERSION" ]; then
    echo "✅ 版本号一致: $SCHEMA_VERSION"
else
    echo "❌ 版本号不一致"
    echo "   Schema: $SCHEMA_VERSION"
    echo "   文档: $DOC_VERSION"
    exit 1
fi

echo ""
echo "3️⃣  索引数量验证..."
SCHEMA_GENES_IDX="$(awk '/CREATE INDEX idx_genes/ {c++} END {print c+0}' "$SCHEMA_FILE")"
DOC_GENES_IDX="$(sed -n '/-- genes表/,/-- regulations表/p' "$DOC_FILE" | awk '/CREATE INDEX idx_genes/ {c++} END {print c+0}')"

if [ "$SCHEMA_GENES_IDX" == "5" ] && [ "$DOC_GENES_IDX" == "5" ]; then
    echo "✅ genes表索引: 5个 (一致)"
else
    echo "❌ genes表索引不一致: Schema=$SCHEMA_GENES_IDX, Doc=$DOC_GENES_IDX"
    exit 1
fi

SCHEMA_REG_IDX="$(awk '/CREATE INDEX idx_reg_/ {c++} END {print c+0}' "$SCHEMA_FILE")"
DOC_REG_IDX="$(sed -n '/-- regulations表/,/-- trait_gene/p' "$DOC_FILE" | awk '/CREATE INDEX idx_reg_/ {c++} END {print c+0}')"

if [ "$SCHEMA_REG_IDX" == "8" ] && [ "$DOC_REG_IDX" == "8" ]; then
    echo "✅ regulations表索引: 8个 (一致)"
else
    echo "❌ regulations表索引不一致: Schema=$SCHEMA_REG_IDX, Doc=$DOC_REG_IDX"
    exit 1
fi

echo ""
echo "4️⃣  关键索引存在性验证..."
if grep -q "idx_genes_ensembl" "$SCHEMA_FILE" && grep -q "idx_genes_ensembl" "$DOC_FILE"; then
    echo "✅ idx_genes_ensembl 存在"
else
    echo "❌ idx_genes_ensembl 缺失"
    exit 1
fi

if grep -q "idx_reg_batch" "$SCHEMA_FILE" && grep -q "idx_reg_batch" "$DOC_FILE"; then
    echo "✅ idx_reg_batch 存在"
else
    echo "❌ idx_reg_batch 缺失"
    exit 1
fi

echo ""
echo "5️⃣  查询示例验证（不应使用gene_region）..."
if grep "gene_region" "$DOC_FILE" | grep -v "Phase 2" | grep -v "添加generated列" | grep -v "注意" | grep -q "JOIN"; then
    echo "❌ 查询示例仍使用gene_region"
    exit 1
else
    echo "✅ 查询示例不使用gene_region（或仅在Phase 2说明中）"
fi

echo ""
echo "========================================="
echo "✅ 所有验证通过！文件已完全同步。"
echo "========================================="
echo ""
echo "MD5签名:"
echo "  ${SCHEMA_DISPLAY}: $ACTUAL_SCHEMA"
echo "  ${DOC_DISPLAY}: $ACTUAL_DOC"
echo ""
echo "版本: $SCHEMA_VERSION"
echo "验证时间: $(date '+%Y-%m-%d %H:%M:%S')"
