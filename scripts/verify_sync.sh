#!/bin/bash
# v2.3 同步验证脚本
set -e

echo "========================================="
echo "文件完整性校验 v2.3"
echo "========================================="
echo ""

# 检查MD5
echo "1️⃣  MD5校验..."
EXPECTED_SCHEMA="1b3ab40c3d82a15386e010ea4a1d4af4"
EXPECTED_DOC="eb17f899a7a423bfb06e63826106e6f5"

ACTUAL_SCHEMA=$(md5sum schema_mvp_core.sql | awk '{print $1}')
ACTUAL_DOC=$(md5sum DATABASE_DESIGN_FINAL.md | awk '{print $1}')

if [ "$ACTUAL_SCHEMA" == "$EXPECTED_SCHEMA" ]; then
    echo "✅ schema_mvp_core.sql 校验通过"
else
    echo "❌ schema_mvp_core.sql 校验失败"
    echo "   预期: $EXPECTED_SCHEMA"
    echo "   实际: $ACTUAL_SCHEMA"
    exit 1
fi

if [ "$ACTUAL_DOC" == "$EXPECTED_DOC" ]; then
    echo "✅ DATABASE_DESIGN_FINAL.md 校验通过"
else
    echo "❌ DATABASE_DESIGN_FINAL.md 校验失败"
    echo "   预期: $EXPECTED_DOC"
    echo "   实际: $ACTUAL_DOC"
    exit 1
fi

echo ""
echo "2️⃣  版本号验证..."
SCHEMA_VERSION=$(head -4 schema_mvp_core.sql | grep "版本:" | grep -oP 'v\d+\.\d+')
DOC_VERSION=$(head -5 DATABASE_DESIGN_FINAL.md | grep "**版本**" | grep -oP 'v\d+\.\d+')

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
SCHEMA_GENES_IDX=$(grep "CREATE INDEX idx_genes" schema_mvp_core.sql | wc -l)
DOC_GENES_IDX=$(sed -n '/-- genes表/,/-- regulations表/p' DATABASE_DESIGN_FINAL.md | grep "CREATE INDEX idx_genes" | wc -l)

if [ "$SCHEMA_GENES_IDX" == "5" ] && [ "$DOC_GENES_IDX" == "5" ]; then
    echo "✅ genes表索引: 5个 (一致)"
else
    echo "❌ genes表索引不一致: Schema=$SCHEMA_GENES_IDX, Doc=$DOC_GENES_IDX"
    exit 1
fi

SCHEMA_REG_IDX=$(grep "CREATE INDEX idx_reg_" schema_mvp_core.sql | wc -l)
DOC_REG_IDX=$(sed -n '/-- regulations表/,/-- trait_gene/p' DATABASE_DESIGN_FINAL.md | grep "CREATE INDEX idx_reg_" | wc -l)

if [ "$SCHEMA_REG_IDX" == "8" ] && [ "$DOC_REG_IDX" == "8" ]; then
    echo "✅ regulations表索引: 8个 (一致)"
else
    echo "❌ regulations表索引不一致: Schema=$SCHEMA_REG_IDX, Doc=$DOC_REG_IDX"
    exit 1
fi

echo ""
echo "4️⃣  关键索引存在性验证..."
if grep -q "idx_genes_ensembl" schema_mvp_core.sql && grep -q "idx_genes_ensembl" DATABASE_DESIGN_FINAL.md; then
    echo "✅ idx_genes_ensembl 存在"
else
    echo "❌ idx_genes_ensembl 缺失"
    exit 1
fi

if grep -q "idx_reg_batch" schema_mvp_core.sql && grep -q "idx_reg_batch" DATABASE_DESIGN_FINAL.md; then
    echo "✅ idx_reg_batch 存在"
else
    echo "❌ idx_reg_batch 缺失"
    exit 1
fi

echo ""
echo "5️⃣  查询示例验证（不应使用gene_region）..."
if grep "gene_region" DATABASE_DESIGN_FINAL.md | grep -v "Phase 2" | grep -v "添加generated列" | grep -v "注意" | grep -q "JOIN"; then
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
echo "  schema_mvp_core.sql:      $ACTUAL_SCHEMA"
echo "  DATABASE_DESIGN_FINAL.md: $ACTUAL_DOC"
echo ""
echo "版本: $SCHEMA_VERSION"
echo "验证时间: $(date '+%Y-%m-%d %H:%M:%S')"
