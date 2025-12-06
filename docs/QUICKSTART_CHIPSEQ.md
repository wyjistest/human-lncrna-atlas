# ChIP-seq Epigenetic Marks 快速开始指南

> **目标读者**: 开发者、数据分析师
> **预计时间**: 30 分钟（不含数据下载）

---

## 🎯 目标

本指南将帮助您快速：
1. 了解 ChIP-seq 功能的核心价值
2. 在本地环境运行完整示例
3. 导入第一个 H3K27me3 数据集
4. 在前端查看组蛋白修饰数据

---

## 📦 前置条件

- PostgreSQL 15+ 运行中
- Python 3.11+ 环境
- Node.js 20+
- 约 2GB 磁盘空间

---

## ⚡ 5 分钟快速部署

### Step 1: 创建数据库表（2 分钟）

```bash
cd /data/wenyujianData/human-lncrna-atlas-github/frontend/backend

# 执行建表脚本
psql -U amax -d lncrna_production -f sql/chipseq_schema.sql

# 验证
psql -U amax -d lncrna_production -c "SELECT COUNT(*) FROM epigenetic_mark_types;"
# 应该输出 15
```

### Step 2: 启动后端（1 分钟）

```bash
cd /data/wenyujianData/humanLncAtlas/frontend/backend

# 确保 chipseq router 已注册到 main.py
# （如果还没有，参考实施检查清单）

# 启动
python3 -m uvicorn main:app --host 0.0.0.0 --port 8000 --reload
```

访问 http://localhost:8000/docs，确认能看到 `chipseq` 标签。

### Step 3: 下载示例数据（取决于网速）

```bash
cd /data/wenyujianData/humanLncAtlas

# 创建数据目录
mkdir -p chipseq_data/demo

# 下载一个小的示例文件（示例，请替换为实际 URL）
# 选项 A: 从 ENCODE 下载
wget -O chipseq_data/demo/H3K27me3_peaks.bed.gz \
  "https://www.encodeproject.org/files/ENCFF001XYZ/@@download/ENCFF001XYZ.bed.gz"

gunzip chipseq_data/demo/H3K27me3_peaks.bed.gz

# 选项 B: 使用测试数据生成器（如果 ENCODE 访问困难）
# python3 scripts/generate_test_chipseq.py --mark H3K27me3 --peaks 1000
```

### Step 4: 导入数据（1-2 分钟）

```bash
cd /data/wenyujianData/humanLncAtlas/frontend/backend

# 创建元数据文件
cat > /tmp/demo_metadata.json << 'EOF'
{
  "mark_type": "H3K27me3",
  "encode_accession": "DEMO001",
  "tissue_type": "brain",
  "cell_type": "neuron",
  "peak_type": "broad"
}
EOF

# 执行导入（小数据集，约 1-2 分钟）
python3 scripts/import_chipseq.py \
    --input /data/wenyujianData/humanLncAtlas/chipseq_data/demo/H3K27me3_peaks.bed \
    --mark-type H3K27me3 \
    --species human \
    --experiment-name "Demo_H3K27me3" \
    --metadata /tmp/demo_metadata.json \
    --batch-size 5000 \
    --compute-associations

# 刷新统计视图
psql -U amax -d lncrna_production << 'SQL'
REFRESH MATERIALIZED VIEW mv_chipseq_mark_stats;
REFRESH MATERIALIZED VIEW mv_gene_mark_summary;
SQL
```

### Step 5: 启动前端（1 分钟）

```bash
cd /data/wenyujianData/humanLncAtlas/frontend/web

# 启动
npm run dev -- --host 0.0.0.0
```

访问 http://localhost:5173

### Step 6: 查看数据（1 分钟）

1. 导航到任意基因详情页（例如 `HOTAIR` 或 `MALAT1`）
2. 点击 **"Genomic Features"** Tab
3. 点击 **"ChIP-seq Peaks"** 子 Tab
4. 在 Mark 选择器中选择 **"H3K27me3 (Repressive)"**
5. 查看统计卡片、数据表格和过滤器

---

## 🔍 核心功能演示

### 功能 1: 查看单个 Mark 的 Peaks

**操作**:
1. 选择 Mark: H3K27me3
2. 查看统计卡片（Total Peaks, Avg Signal, Avg Fold Enrichment）
3. 浏览数据表格（染色体、位置、信号强度、Q-value）
4. 应用过滤器（Q-value < 0.01, Fold Enrichment > 5）

**预期结果**:
- 看到基因区域的所有 H3K27me3 peaks
- 信号强度颜色编码（高信号 = 红色，低信号 = 绿色）
- 位置类型标注（Promoter, Gene Body, Downstream）

### 功能 2: 过滤 Peaks

**操作**:
1. 调整 "Fold Enrichment" 滑块到 10
2. 选择 "Q-Value" < 0.001
3. 点击 "Apply"

**预期结果**:
- 表格只显示高富集、高显著性的 peaks
- 总数量减少，但质量更高

### 功能 3: 导出 BED 文件

**操作**:
1. 应用想要的过滤器
2. 点击 "Export BED" 按钮

**预期结果**:
- 下载一个 BED 格式文件
- 文件包含过滤后的 peaks
- 可以在 IGV 或 UCSC Genome Browser 中查看

---

## 📊 数据说明

### 支持的组蛋白修饰（15 种）

| Category | Marks | 生物学功能 |
|----------|-------|-----------|
| **Repressive** | H3K27me3, H3K9me3, H4K20me3 | 基因沉默、异染色质 |
| **Activating** | H3K4me3, H3K4me2, H3K9ac | 转录激活、启动子活性 |
| **Enhancer** | H3K4me1, H3K27ac | 增强子活性 |
| **Elongation** | H3K36me3, H3K79me2 | 转录延伸 |
| **Other** | H2A.Z, CTCF | 染色质结构 |

### 数据字段说明

| 字段 | 说明 | 示例值 |
|------|------|--------|
| **Chromosome** | 染色体 | chr1, chr2, chrX |
| **Peak Start** | Peak 起始位置（0-based） | 1234567 |
| **Peak End** | Peak 终止位置 | 1235000 |
| **Signal Value** | 信号强度 | 45.6 |
| **Fold Enrichment** | 相对于背景的富集倍数 | 12.3x |
| **Q-Value** | FDR 校正后的 p-value | 1e-10 |
| **Position Type** | 相对于基因的位置 | Promoter, Gene Body, Downstream |
| **Distance to TSS** | 到转录起始位点的距离 | -500 bp |

---

## 🧪 测试场景

### 场景 1: 查找高信号的 H3K27me3 peaks

**背景**: H3K27me3 是 Polycomb 抑制标记，高信号表示强烈的基因沉默。

**操作**:
```
1. 选择 Mark: H3K27me3
2. 设置 Fold Enrichment >= 10
3. 设置 Q-Value < 0.001
4. 排序：按 Signal Value 降序
```

**预期**: 看到基因区域最强的抑制信号位点。

### 场景 2: 识别启动子区域的修饰

**背景**: 启动子区域的组蛋白修饰影响基因表达。

**操作**:
```
1. 选择 Mark: H3K27me3
2. 设置 Position Type: Promoter
3. 查看 Distance to TSS < 2000 bp 的 peaks
```

**预期**: 看到靠近转录起始位点的 H3K27me3 修饰，提示该基因可能被抑制。

### 场景 3: 对比不同组织的修饰模式（Phase 2.4）

**背景**: 同一基因在不同组织可能有不同的组蛋白修饰模式。

**操作** (需要导入多个组织的数据):
```
1. 选择 Mark: H3K27me3
2. 在统计卡片中查看 "Tissue Distribution"
3. 比较 Brain vs Heart 的 peak 数量和信号强度
```

**预期**: 发现组织特异性的修饰模式。

---

## 🚀 进阶：导入更多数据

### 添加第 2 个 Mark (H3K4me3)

H3K4me3 是活跃启动子标记，与 H3K27me3 形成对比。

```bash
# 下载 H3K4me3 数据
wget -O chipseq_data/demo/H3K4me3_peaks.bed.gz \
  "https://www.encodeproject.org/files/ENCFF002XYZ/@@download/ENCFF002XYZ.bed.gz"

gunzip chipseq_data/demo/H3K4me3_peaks.bed.gz

# 创建元数据
cat > /tmp/h3k4me3_metadata.json << 'EOF'
{
  "mark_type": "H3K4me3",
  "encode_accession": "DEMO002",
  "tissue_type": "brain",
  "cell_type": "neuron",
  "peak_type": "narrow"
}
EOF

# 导入
python3 scripts/import_chipseq.py \
    --input chipseq_data/demo/H3K4me3_peaks.bed \
    --mark-type H3K4me3 \
    --species human \
    --experiment-name "Demo_H3K4me3" \
    --metadata /tmp/h3k4me3_metadata.json \
    --compute-associations

# 刷新统计视图
psql -U amax -d lncrna_production -c "
REFRESH MATERIALIZED VIEW mv_chipseq_mark_stats;
REFRESH MATERIALIZED VIEW mv_gene_mark_summary;
"
```

现在在前端 Mark 选择器中可以看到 H3K4me3 选项！

### 发现 Bivalent Domains（Phase 2.5 功能）

Bivalent domains 是同时存在 H3K27me3（抑制）和 H3K4me3（激活）的区域，通常出现在发育基因上。

```bash
# 查询 bivalent domains
psql -U amax -d lncrna_production << 'SQL'
WITH h3k27me3_peaks AS (
    SELECT p.chromosome, p.peak_start, p.peak_end
    FROM chipseq_peaks p
    JOIN chipseq_experiments e ON p.experiment_id = e.experiment_id
    JOIN epigenetic_mark_types m ON e.mark_type_id = m.mark_type_id
    WHERE m.mark_name = 'H3K27me3'
),
h3k4me3_peaks AS (
    SELECT p.chromosome, p.peak_start, p.peak_end
    FROM chipseq_peaks p
    JOIN chipseq_experiments e ON p.experiment_id = e.experiment_id
    JOIN epigenetic_mark_types m ON e.mark_type_id = m.mark_type_id
    WHERE m.mark_name = 'H3K4me3'
)
SELECT
    a.chromosome,
    GREATEST(a.peak_start, b.peak_start) AS overlap_start,
    LEAST(a.peak_end, b.peak_end) AS overlap_end,
    'bivalent_domain' AS domain_type
FROM h3k27me3_peaks a
JOIN h3k4me3_peaks b
    ON a.chromosome = b.chromosome
    AND a.peak_start < b.peak_end
    AND a.peak_end > b.peak_start
LIMIT 10;
SQL
```

---

## 📚 API 使用示例

### 示例 1: 获取可用 Marks

```bash
curl "http://localhost:8000/api/v1/features/chipseq/marks?species_id=1" | jq
```

响应:
```json
{
  "success": true,
  "data": [
    {
      "mark_type_id": 1,
      "mark_name": "H3K27me3",
      "mark_category": "repressive",
      "display_color": "#9B59B6",
      "experiment_count": 1,
      "peak_count": 12345
    }
  ]
}
```

### 示例 2: 查询基因 Peaks

```bash
curl "http://localhost:8000/api/v1/features/chipseq/genes/12345?mark_type=H3K27me3&min_fold_enrichment=5&max_qvalue=0.01" | jq
```

### 示例 3: 获取基因统计

```bash
curl "http://localhost:8000/api/v1/features/chipseq/genes/12345/summary?mark_type=H3K27me3" | jq
```

---

## 🐛 故障排除

### 问题 1: 前端显示 "No marks available"

**原因**: 数据未导入或物化视图未刷新

**解决**:
```sql
-- 检查是否有实验记录
SELECT COUNT(*) FROM chipseq_experiments;

-- 刷新物化视图
REFRESH MATERIALIZED VIEW mv_chipseq_mark_stats;
```

### 问题 2: API 返回 500 错误

**原因**: 数据库连接问题或表未创建

**解决**:
```bash
# 检查表是否存在
psql -U amax -d lncrna_production -c "\dt chipseq*"

# 检查后端日志
tail -f /tmp/backend.log
```

### 问题 3: 导入脚本报错 "mark_type not found"

**原因**: `epigenetic_mark_types` 表未初始化

**解决**:
```sql
-- 检查 marks 表
SELECT COUNT(*) FROM epigenetic_mark_types;
-- 应该是 15

-- 如果为 0，重新执行建表脚本
\i sql/chipseq_schema.sql
```

---

## 📖 延伸阅读

- **完整架构文档**: `docs/PHASE_2.3_CHIPSEQ_ARCHITECTURE.md`
- **实施检查清单**: `docs/PHASE_2.3_IMPLEMENTATION_CHECKLIST.md`
- **ENCODE 项目**: https://www.encodeproject.org/
- **组蛋白修饰生物学**: https://en.wikipedia.org/wiki/Histone_modification

---

## 🎉 下一步

完成快速开始后，您可以：

1. **Phase 2.4**: 添加更多 marks（H3K4me1, H3K27ac, H3K36me3）
2. **Phase 2.5**: 实现多 marks 对比功能
3. **探索数据**: 在不同基因、不同组织中探索组蛋白修饰模式
4. **集成 IGV**: 在 IGV 浏览器中查看 ChIP-seq 轨道
5. **生物学分析**: 研究组蛋白修饰与基因表达、疾病的关系

---

**享受探索组蛋白修饰的旅程！**

有任何问题，请查阅完整文档或联系开发团队。
