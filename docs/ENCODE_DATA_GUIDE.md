# ENCODE 真实数据下载和导入指南

> **用途**: 使用真实 ENCODE 数据替换测试数据
> **数据源**: UCSC ENCODE Broad Histone (hg19)

---

## 为什么需要真实数据？

**测试数据的局限**:
- ✅ 快速验证架构（5 分钟）
- ✅ 完全可控，适合开发
- ❌ 坐标随机，与真实基因位置不完全匹配
- ❌ 无法用于科研发表

**ENCODE 真实数据的优势**:
- ✅ Peaks 位置与真实基因准确匹配
- ✅ 高质量的实验数据（Broad Institute）
- ✅ 可用于科研分析和发表
- ✅ 包含完整的质量控制指标

---

## 快速下载（推荐）

### 常见坑

- **HepG2 的 H3K4me1 文件名**：UCSC 上写作 `H3k04me1`（注意 `04`），不是 `H3k4me1`。
- **HepG2 的 H3K9me3 文件名**：UCSC 上写作 `H3k09me3Pk`（注意 `09`，且是 `Pk` 不是 `StdPk`）。
- **H1-hESC 的 H3K9me3 文件名**：UCSC 上写作 `H3k09me3`（注意 `09`），不是 `H3k9me3`。
- **A549 没有 StdPk**：UCSC hg19 BroadHistone 的 A549 多为处理组（例如 `Etoh02Pk` / `Dex100nmPk`），且常见 `H3k04me1/2/3`、`H3k09ac/H3k09me3`（带前导 0）。

### 方案 A：使用我们的下载脚本（自动化）

```bash
cd <repo-root>/frontend/backend

# 预览要下载的文件（dry-run）
python3 scripts/download_encode_chipseq.py \
    --all \
    --cell-line GM12878 \
    --dry-run

# 输出示例：
# Total files to download: 8
# Estimated total size: ~22.1 MB

# 实际下载
python3 scripts/download_encode_chipseq.py \
    --all \
    --cell-line GM12878 \
    --output encode_chipseq_data

# 等待下载完成（约 2-5 分钟，取决于网速）
```

**下载内容**:
- H3K27me3: wgEncodeBroadHistoneGm12878H3k27me3StdPk.broadPeak.gz (2.1 MB)
- H3K4me1: wgEncodeBroadHistoneGm12878H3k4me1StdPk.broadPeak.gz (5.1 MB)
- H3K4me2: wgEncodeBroadHistoneGm12878H3k4me2StdPk.broadPeak.gz (4.0 MB)
- H3K4me3: wgEncodeBroadHistoneGm12878H3k4me3StdPk.broadPeak.gz (1.8 MB)
- H3K27ac: wgEncodeBroadHistoneGm12878H3k27acStdPk.broadPeak.gz (4.5 MB)
- H3K36me3: wgEncodeBroadHistoneGm12878H3k36me3StdPk.broadPeak.gz (0.5 MB)
- H3K9ac: wgEncodeBroadHistoneGm12878H3k9acStdPk.broadPeak.gz (3.0 MB)
- H3K9me3: wgEncodeBroadHistoneGm12878H3k9me3StdPk.broadPeak.gz (1.1 MB)

---

### 方案 B：手动下载（更灵活）

```bash
cd <repo-root>/chipseq_data
mkdir -p encode_gm12878

# 下载 H3K27me3
wget https://hgdownload.soe.ucsc.edu/goldenPath/hg19/encodeDCC/wgEncodeBroadHistone/wgEncodeBroadHistoneGm12878H3k27me3StdPk.broadPeak.gz

# 下载 H3K4me1
wget https://hgdownload.soe.ucsc.edu/goldenPath/hg19/encodeDCC/wgEncodeBroadHistone/wgEncodeBroadHistoneGm12878H3k4me1StdPk.broadPeak.gz

# 下载 H3K4me2
wget https://hgdownload.soe.ucsc.edu/goldenPath/hg19/encodeDCC/wgEncodeBroadHistone/wgEncodeBroadHistoneGm12878H3k4me2StdPk.broadPeak.gz

# 下载 H3K4me3
wget https://hgdownload.soe.ucsc.edu/goldenPath/hg19/encodeDCC/wgEncodeBroadHistone/wgEncodeBroadHistoneGm12878H3k4me3StdPk.broadPeak.gz

# 下载 H3K27ac
wget https://hgdownload.soe.ucsc.edu/goldenPath/hg19/encodeDCC/wgEncodeBroadHistone/wgEncodeBroadHistoneGm12878H3k27acStdPk.broadPeak.gz

# 下载 H3K36me3
wget https://hgdownload.soe.ucsc.edu/goldenPath/hg19/encodeDCC/wgEncodeBroadHistone/wgEncodeBroadHistoneGm12878H3k36me3StdPk.broadPeak.gz

# 下载 H3K9ac
wget https://hgdownload.soe.ucsc.edu/goldenPath/hg19/encodeDCC/wgEncodeBroadHistone/wgEncodeBroadHistoneGm12878H3k9acStdPk.broadPeak.gz

# 下载 H3K9me3
wget https://hgdownload.soe.ucsc.edu/goldenPath/hg19/encodeDCC/wgEncodeBroadHistone/wgEncodeBroadHistoneGm12878H3k9me3StdPk.broadPeak.gz

# 解压所有文件
gunzip *.gz
```

---

## 数据导入

### 步骤 0：组装审计（推荐）

在导入前建议先做一次 hg19 组装一致性审计（尤其是你手工下载/搬运过 peaks 文件时），可以快速发现 hg38/GRCh38 混入、下载损坏、未知染色体等问题：

```bash
cd <repo-root>
HUMAN_LNC_ATLAS_DATA_DIR="/data/wenyujianData/humanLncAtlas" \
  bash scripts/genomes/audit_external_data_assemblies.sh
```

### 步骤 1：准备元数据文件

为每个下载的文件创建元数据 JSON：

**H3K27me3 元数据** (`encode_gm12878/H3K27me3_metadata.json`):
```json
{
  "mark_type": "H3K27me3",
  "encode_accession": "ENCSR000AKP",
  "tissue_type": "blood",
  "cell_type": "B-lymphocyte",
  "cell_line": "GM12878",
  "antibody_target": "H3K27me3",
  "source_database": "ENCODE",
  "peak_type": "broad",
  "genome_assembly": "hg19"
}
```

**H3K4me1 元数据** (`encode_gm12878/H3K4me1_metadata.json`):
```json
{
  "mark_type": "H3K4me1",
  "encode_accession": "ENCSR000AKX",
  "tissue_type": "blood",
  "cell_type": "B-lymphocyte",
  "cell_line": "GM12878",
  "antibody_target": "H3K4me1",
  "source_database": "ENCODE",
  "peak_type": "broad",
  "genome_assembly": "hg19"
}
```

**H3K4me3 元数据** (`encode_gm12878/H3K4me3_metadata.json`):
```json
{
  "mark_type": "H3K4me3",
  "encode_accession": "ENCSR000AKY",
  "tissue_type": "blood",
  "cell_type": "B-lymphocyte",
  "cell_line": "GM12878",
  "antibody_target": "H3K4me3",
  "source_database": "ENCODE",
  "peak_type": "broad",
  "genome_assembly": "hg19"
}
```

**H3K27ac 元数据** (`encode_gm12878/H3K27ac_metadata.json`):
```json
{
  "mark_type": "H3K27ac",
  "encode_accession": "ENCSR000AKL",
  "tissue_type": "blood",
  "cell_type": "B-lymphocyte",
  "cell_line": "GM12878",
  "antibody_target": "H3K27ac",
  "source_database": "ENCODE",
  "peak_type": "broad",
  "genome_assembly": "hg19"
}
```

---

### 步骤 2：导入 ENCODE 数据

#### 选项 A：逐个导入（推荐新手）

```bash
cd <repo-root>/frontend/backend

# 导入 H3K27me3
python3 scripts/import_chipseq.py \
    --input encode_gm12878/wgEncodeBroadHistoneGm12878H3k27me3StdPk.broadPeak \
    --mark-type H3K27me3 \
    --species human \
    --experiment-name "ENCODE_GM12878_H3K27me3" \
    --cell-line "GM12878" \
    --cell-type "B-lymphocyte" \
    --tissue-type "blood" \
    --accession "ENCSR000AKP" \
    --source "ENCODE" \
    --format broadPeak \
    --db-name lncrna_production \
    --db-user amax \
    --compute-associations  # 可选：生成 gene_peak_associations（可能较慢）

# 导入 H3K4me1
python3 scripts/import_chipseq.py \
    --input encode_gm12878/wgEncodeBroadHistoneGm12878H3k4me1StdPk.broadPeak \
    --mark-type H3K4me1 \
    --species human \
    --experiment-name "ENCODE_GM12878_H3K4me1" \
    --cell-line "GM12878" \
    --cell-type "B-lymphocyte" \
    --tissue-type "blood" \
    --db-name lncrna_production \
    --db-user amax \
    --compute-associations  # 可选：生成 gene_peak_associations（可能较慢）

# 类似地导入 H3K4me3 和 H3K27ac
```

#### 选项 B：批量导入（推荐高级用户）

创建配置文件 `encode_batch_config.json`:
```json
{
  "species": "human",
  "experiments": [
    {
      "mark_type": "H3K27me3",
      "cell_line": "GM12878",
      "peaks_file": "encode_gm12878/wgEncodeBroadHistoneGm12878H3k27me3StdPk.broadPeak",
      "metadata_file": "encode_gm12878/H3K27me3_metadata.json"
    },
    {
      "mark_type": "H3K4me1",
      "cell_line": "GM12878",
      "peaks_file": "encode_gm12878/wgEncodeBroadHistoneGm12878H3k4me1StdPk.broadPeak",
      "metadata_file": "encode_gm12878/H3K4me1_metadata.json"
    },
    {
      "mark_type": "H3K4me3",
      "cell_line": "GM12878",
      "peaks_file": "encode_gm12878/wgEncodeBroadHistoneGm12878H3k4me3StdPk.broadPeak",
      "metadata_file": "encode_gm12878/H3K4me3_metadata.json"
    },
    {
      "mark_type": "H3K27ac",
      "cell_line": "GM12878",
      "peaks_file": "encode_gm12878/wgEncodeBroadHistoneGm12878H3k27acStdPk.broadPeak",
      "metadata_file": "encode_gm12878/H3K27ac_metadata.json"
    }
  ],
  "options": {
    "batch_size": 10000,
    "compute_associations": true
  }
}
```

然后批量导入：
```bash
python3 scripts/batch_import_chipseq.py encode_batch_config.json
```

---

### 步骤 3：刷新物化视图

如果你在导入时没有启用 `--compute-associations` / `compute_associations=true`（或你想对历史数据统一补齐 `gene_peak_associations`），建议先运行批量脚本（默认仅处理 `is_active=TRUE` 的 experiments，并在末尾刷新物化视图）：

```bash
cd <repo-root>/frontend/backend

# 先查看将要处理哪些 experiments
python3 scripts/compute_gene_peak_associations.py --dry-run

# 如果你本机 Postgres 使用 Unix socket / peer auth（常见现象：`psql` 可直连，但 `localhost:5432` 需要密码），建议显式指定：
python3 scripts/compute_gene_peak_associations.py --db-host /var/run/postgresql --db-user <os-user> --dry-run

# 真正执行（默认跳过“已存在 associations”的 experiments）
python3 scripts/compute_gene_peak_associations.py

# 同上（peer auth 场景）
python3 scripts/compute_gene_peak_associations.py --db-host /var/run/postgresql --db-user <os-user>
```

说明：
- 默认只处理 `reference_genome` 匹配 `hg19/GRCh37` 的 experiments（防止 hg38 混入）；如需要严格要求可加 `--require-reference-genome`。
- 若需要强制重跑（即使已存在部分 associations），可用 `--force`（依赖 `ON CONFLICT DO NOTHING` 防重复写入）。
- 如果你只想补齐表而暂不刷新物化视图，可用 `--no-refresh-mvs`。
- 如需长跑审计/断点续跑，可用 `--report-jsonl <path>` 输出 JSONL 报告；重新运行时配合 `--resume-from <path>` 跳过已处理 experiments（可与 `--report-jsonl` 指向同一文件）；如希望单个 experiment 失败不影响整体，可加 `--continue-on-error`。

备用：你也可以手动刷新物化视图：

```bash
psql -U amax -d lncrna_production << 'SQL'
REFRESH MATERIALIZED VIEW mv_chipseq_mark_stats;
REFRESH MATERIALIZED VIEW mv_gene_mark_summary;
SELECT 'Refreshed' AS status;
SQL
```

可选：如果你是通过本仓库的 ETL/导入脚本批量更新数据，可以启用 `HLA_NOTIFY_BACKEND=true`，让脚本在结束时 best-effort 调用后端 Admin API 来失效缓存/刷新物化视图（默认关闭、失败不影响导入流程）。参考：`etl/backend_notify.py` 与 `README.md` 的 “Materialized Views” 小节。

---

### 步骤 4：验证导入结果

```sql
-- 检查导入的实验
SELECT e.experiment_id, m.mark_name, e.cell_line, COUNT(p.peak_id) as peak_count
FROM chipseq_experiments e
JOIN epigenetic_mark_types m ON e.mark_type_id = m.mark_type_id
LEFT JOIN chipseq_peaks p ON e.experiment_id = p.experiment_id
WHERE e.source_database = 'ENCODE'
GROUP BY e.experiment_id, m.mark_name, e.cell_line;
```

**预期结果**（ENCODE 真实数据）:
```
 mark_name | cell_line | peak_count
-----------+-----------+------------
 H3K27me3  | GM12878   |   40,000-60,000
 H3K4me1   | GM12878   |   80,000-120,000
 H3K4me3   | GM12878   |   30,000-50,000
 H3K27ac   | GM12878   |   70,000-100,000
```

**注意**: ENCODE 真实数据的 peaks 数量远大于测试数据（10-40 倍）

---

### 步骤 5：组装一致性审计（hg19，推荐）

为避免 hg19/GRCh37 环境中混入 hg38/GRCh38 的 peaks/轨道文件，建议在导入或更新外部数据后运行审计脚本（**只读**、输出落盘、可回溯）：

```bash
cd <repo-root>

# 外部文件审计：bigWig/bigBed header 与 chrom.sizes 一致性 + peaks 坐标边界校验
bash "scripts/genomes/audit_external_data_assemblies.sh"

# DB 审计：检查 active experiments 的 reference_genome 回填需求（默认只生成可回滚 SQL，不写 DB）
DB_USER=amax DB_NAME=lncrna_production bash "scripts/genomes/audit_chipseq_reference_genome_db.sh"
```

输出默认写入：`/data/wenyujianData/humanLncAtlas/audits/<timestamp>_*_audit/`，包含 `meta.env`、逐步 log，以及（DB 审计场景）可回滚 SQL。

---

## 预期的 Peak 数量（参考：本仓库当前 human/hg19 active experiments）

> 说明：peaks 数量会随 ENCODE 版本、过滤策略、是否合并 replicate 而变化；以下数字用于校验“导入后量级是否合理”。更完整统计以 `docs/CURRENT_STATUS.md` 为准。

| Mark | 细胞系 | Peaks（当前） | 文件大小（UCSC broadPeak.gz） |
|------|--------|--------------|------------------------------|
| H3K27me3 | GM12878 | 29,588 | 2.1 MB |
| H3K4me1 | GM12878 | 109,612 | 5.1 MB |
| H3K4me2 | GM12878 | 79,675 | 4.0 MB |
| H3K4me3 | GM12878 | 57,476 | 1.8 MB |
| H3K27ac | GM12878 | 56,069 | 4.5 MB |
| H3K36me3 | GM12878 | 33,710 | 0.5 MB |
| H3K9ac | GM12878 | 41,266 | 3.0 MB |
| H3K9me3 | GM12878 | 74,515 | 1.1 MB |
| **总计** | | **481,911** | **~22.1 MB** |

---

## 多细胞系数据（可选）

### 下载其他细胞系

```bash
# A549（肺癌细胞系；注意：UCSC hg19 BroadHistone 的 A549 多为处理组，无 StdPk；脚本默认选择 Etoh02 版本）
python3 scripts/download_encode_chipseq.py \
    --all \
    --cell-line A549 \
    --output encode_a549

# H1-hESC（胚胎干细胞）
python3 scripts/download_encode_chipseq.py \
    --all \
    --cell-line H1-hESC \
    --output encode_h1hesc

# K562（红白血病细胞）
python3 scripts/download_encode_chipseq.py \
    --all \
    --cell-line K562 \
    --output encode_k562
```

### 数据规模预估（3 个细胞系 × 8 marks；参考当前数据量）

| 细胞系 | Marks | Peaks（当前） | 文件大小（估算） |
|--------|-------|--------------|------------------|
| GM12878 | 8 | 481,911 | ~22.1 MB |
| H1-hESC | 8 | 508,144 | ~18.6 MB |
| K562 | 8 | 544,849 | ~16.3 MB |
| **总计** | **24** | **1,534,904** | **~57.0 MB** |

---

## 数据质量对比

### 测试数据 vs ENCODE 数据

| 维度 | 测试数据 | ENCODE 数据 |
|------|---------|------------|
| **Peaks 数量** | 300/mark | 40,000-100,000/mark |
| **与基因重叠** | 随机（~5%基因） | 准确（~80%基因） |
| **生物学意义** | 合成，无意义 | 真实，有意义 |
| **可发表性** | ❌ 否 | ✅ 是 |
| **导入时间** | ~1 秒/mark | ~30-60 秒/mark |
| **存储需求** | ~100 KB | ~50-200 MB |
| **适用场景** | 开发测试 | 科研分析 |

---

## 切换到真实数据的流程

### 选项 A：清空测试数据，重新导入（推荐）

```bash
# 1. 备份当前数据库（可选）
pg_dump -U amax -d lncrna_production -t chipseq_* > chipseq_test_backup.sql

# 2. 清空测试数据
psql -U amax -d lncrna_production << 'SQL'
TRUNCATE TABLE chipseq_peaks CASCADE;
TRUNCATE TABLE chipseq_experiments CASCADE;
TRUNCATE TABLE gene_peak_associations CASCADE;
SQL

# 3. 下载 ENCODE 数据
python3 scripts/download_encode_chipseq.py --all --cell-line GM12878

# 4. 导入 ENCODE 数据
python3 scripts/batch_import_chipseq.py encode_chipseq_data/encode_batch_import_config.json

# 5. 刷新物化视图
psql -U amax -d lncrna_production << 'SQL'
REFRESH MATERIALIZED VIEW mv_chipseq_mark_stats;
REFRESH MATERIALIZED VIEW mv_gene_mark_summary;
SQL
```

---

### 选项 B：保留测试数据，增量添加（开发环境）

```bash
# 不删除现有数据，直接导入 ENCODE 数据
# 系统会自动处理重复的实验名称
python3 scripts/download_encode_chipseq.py --all --cell-line GM12878
python3 scripts/batch_import_chipseq.py encode_chipseq_data/encode_batch_import_config.json
```

**优势**: 保留测试数据供调试，同时有真实数据供分析

**注意**: 数据库会同时包含测试数据和真实数据，查询时需要区分（通过 `source_database` 字段）

---

## 验证真实数据

### 查询著名基因的 ChIP-seq 数据

```bash
# HOTAIR (lncRNA，已知受 H3K27me3 调控)
curl "http://localhost:8000/api/v1/features/chipseq/genes/18917/summary" | jq

# TP53 (肿瘤抑制基因)
# 查找 TP53 的 gene_id
psql -U amax -d lncrna_production -c "SELECT gene_id FROM genes WHERE gene_name = 'TP53' LIMIT 1;"

curl "http://localhost:8000/api/v1/features/chipseq/genes/{gene_id}/summary" | jq

# 预期：看到多个 marks 的数据，可能包含 bivalent domains
```

---

## ENCODE 数据使用注意事项

### 1. 数据使用限制

ENCODE 数据有发布限制期：
- **已发布数据**: 可自由使用和发表
- **限制期数据**: 仅限 ENCODE 联盟内部使用

**检查方式**: 访问 https://www.encodeproject.org/ 查看具体实验的状态

### 2. 引用要求

使用 ENCODE 数据发表时，需引用：
```
ENCODE Project Consortium. An integrated encyclopedia of DNA elements
in the human genome. Nature. 2012 Sep 6;489(7414):57-74.
```

### 3. 数据版本

- **hg19 (GRCh37)**: 较旧，但数据丰富
- **hg38 (GRCh38)**: 最新，但部分数据仍在处理中

**建议**: Phase 2.4 使用 hg19，与现有基因组版本一致

---

## 故障排除

### 问题 1：下载失败

**症状**: wget 报错或超时

**解决**:
```bash
# 使用 rsync（更可靠）
rsync -a -P rsync://hgdownload.gi.ucsc.edu/goldenPath/hg19/encodeDCC/wgEncodeBroadHistone/wgEncodeBroadHistoneGm12878H3k27me3StdPk.broadPeak.gz ./

# 或使用 curl
curl -O http://hgdownload.gi.ucsc.edu/goldenPath/hg19/encodeDCC/wgEncodeBroadHistone/wgEncodeBroadHistoneGm12878H3k27me3StdPk.broadPeak.gz
```

---

### 问题 2：导入速度慢

**症状**: 10 万 peaks 导入超过 10 分钟

**优化**:
```bash
# 增大 batch_size
python3 scripts/import_chipseq.py \
    --batch-size 20000 \  # 默认 10000
    ...

# 或关闭关联计算（后续再计算）
# 不使用 --compute-associations
```

---

### 问题 3：磁盘空间不足

**检查**:
```bash
df -h <data-root>/
```

**解决**:
- ENCODE 数据压缩后约 40 MB（3 个细胞系）
- 解压后约 200 MB
- 数据库存储约 500 MB - 1 GB
- 建议至少保留 2-3 GB 可用空间

---

## 下一步选项

### 选项 1：下载真实 ENCODE 数据（推荐）

```bash
python3 scripts/download_encode_chipseq.py --all --cell-line GM12878
```

**预计时间**: 5-10 分钟（下载 + 导入）

---

### 选项 2：继续使用测试数据，开始前端测试

```bash
cd <repo-root>/frontend/web
npm run dev -- --host 0.0.0.0
```

访问 http://localhost:5173，测试 ChIPSeqPeaksTable 组件

---

### 选项 3：开始 Phase 2.5（对比功能）

实现多 marks 对比 API 和可视化

---

**建议**: 根据您的需求选择。如果是科研用途，建议下载真实数据；如果是架构验证，测试数据已经足够。

---

**文档生成时间**: 2025-12-06
