# Phase 6.0：科研数据深度分析规划

**项目**: Human LncRNA Atlas
**阶段**: Phase 6.0 (Research Data Analysis)
**前置条件**: Phase 5.2 完成（全站性能优化）
**预计工作量**: 3-4 天
**优先级**: P0（高优先级，科研核心价值）

---

## 项目背景

### 数据资产

经过 Phase 1-5 的建设，项目已拥有丰富的科研数据资产：

| 数据类型 | 数量 | 数据源 | 质量 |
|---------|------|--------|------|
| **调控关系** | 804,630 | LongTarget 预测 | 高质量 |
| **跨物种数据** | 4 个物种 | Human, Chimp, Macaque, Marmoset | 完整 |
| **表观遗传** | 462 万+ ChIP-seq 峰 | ENCODE | 权威 |
| **开放染色质** | 122 万 DNase-seq 峰 | ENCODE | 权威 |
| **重复元件** | 548 万注释 | UCSC RepeatMasker | 完整 |
| **疾病关联** | 67,763 关联 | GWAS | 临床相关 |
| **保守性数据** | 1,969 保守 lncRNA | 自有分析 | 独特 |

### 技术优势

- ✅ API 响应时间：毫秒级（42.7x 平均加速）
- ✅ 数据库查询：优化完善（物化视图 + 索引）
- ✅ 可视化工具：ECharts, Cytoscape, IGV.js
- ✅ 计算环境：Python + Jupyter + Pandas/NumPy

---

## 分析方向详细规划

### 📊 方向 1：高亲和力调控网络分析

**研究目标**: 识别具有强调控能力的核心 lncRNA 及其生物学特征

#### 1.1 数据查询与统计

**SQL 查询**:
```sql
-- 高亲和力调控关系（BA > 100）
SELECT
    lncrna_gene_id,
    COUNT(*) as target_count,
    AVG(binding_affinity) as avg_ba,
    MAX(binding_affinity) as max_ba,
    COUNT(DISTINCT species_id) as species_count
FROM regulations
WHERE binding_affinity > 100
GROUP BY lncrna_gene_id
ORDER BY target_count DESC
LIMIT 100;

-- 物种分布
SELECT
    species_id,
    COUNT(*) as high_ba_count,
    AVG(binding_affinity) as avg_ba
FROM regulations
WHERE binding_affinity > 100
GROUP BY species_id;
```

**Python 分析**:
```python
import pandas as pd
import matplotlib.pyplot as plt
import seaborn as sns

# 加载数据
df = pd.read_sql(query, engine)

# 统计分析
ba_distribution = df['binding_affinity'].describe()
top_lncrnas = df.nlargest(100, 'target_count')

# 可视化
plt.figure(figsize=(12, 6))
sns.histplot(df['binding_affinity'], bins=50)
plt.title('Binding Affinity Distribution (BA > 100)')
plt.savefig('ba_distribution_high_affinity.png', dpi=300)
```

#### 1.2 Top lncRNA 排行榜

✅ **最小可复现产出（已落地）**：可直接生成 BA>=阈值 的 Top lncRNA 榜单（CSV + Markdown）。

```bash
# 默认输出到 docs/reports/
python3 scripts/research/top_lncrna_by_binding_affinity.py --species-id 1 --min-ba 100 --limit 50

# 多物种（一次性生成多个物种榜单 + 汇总索引）
python3 scripts/research/top_lncrna_by_binding_affinity.py --species-ids all --min-ba 100 --limit 50

# 可选：覆盖 Markdown 的 Generated(UTC)，便于稳定对比/提交（默认会写入当前时间）
python3 scripts/research/top_lncrna_by_binding_affinity.py --species-id 1 --min-ba 100 --limit 50 --generated-at 2026-01-27T00-00-00Z

# 可选：本地 sample DB 烟测（v2.3 sample_data 的 BA 约 55–82，MIN_BA 默认 50）
bash scripts/research/generate_top_lncrna_sample_baseline_local.sh
```

输出：
- `docs/reports/top-lncrna-ba100-species1.csv`
- `docs/reports/top-lncrna-ba100-species1.md`
（多物种模式会额外生成索引，例如：`docs/reports/top-lncrna-ba100-species-all.md`）

sample baseline（可提交小文件，便于 review）：
- `docs/baselines/research/top-lncrna-ba50-species1.csv`
- `docs/baselines/research/top-lncrna-ba50-species1.md`

**生成榜单**:
```python
top_100_lncrnas = pd.DataFrame({
    'rank': range(1, 101),
    'lncrna_name': ...,
    'ensembl_id': ...,
    'target_count': ...,
    'avg_ba': ...,
    'max_ba': ...,
    'species': ...,
    'conserved_species_count': ...
})

# 导出
top_100_lncrnas.to_csv('top_100_high_affinity_lncrnas.csv', index=False)
top_100_lncrnas.to_excel('top_100_high_affinity_lncrnas.xlsx', index=False)
```

**可视化**:
- Top 20 lncRNA 柱状图（调控数量）
- BA 分布箱线图（按物种）
- 散点图（调控数量 vs 平均 BA）

#### 1.3 靶基因功能富集分析

**分析步骤**:
1. 提取高亲和力 lncRNA 的所有靶基因
2. 进行 GO enrichment analysis（使用 g:Profiler 或 DAVID）
3. KEGG pathway enrichment
4. 疾病关联富集（基于现有 trait_gene_associations）

**可复现产出（导出靶基因列表）**：
```bash
# 真实数据库（需后端 Python 依赖可用，环境变量同 backend：DB_HOST/DB_PORT/DB_NAME/DB_USER/DB_PASSWORD）
python3 scripts/research/top_lncrna_target_genes_for_enrichment.py \
  --species-id 1 \
  --min-ba 100 \
  --top-n 50 \
  --target-protein-coding-only \
  --out-dir docs/reports

# 本地 sample DB 烟测（不依赖真实大库）
bash scripts/research/generate_top_lncrna_target_genes_sample_baseline_local.sh
```

**输出文件**（默认 `--out-dir docs/reports`）：
- `top-lncrna-target-genes-ba<MIN_BA>-top<TOP_N>-species<SPECIES_ID>.tsv`（带统计字段，可追溯）
- `top-lncrna-target-genes-ba<MIN_BA>-top<TOP_N>-species<SPECIES_ID>.txt`（富集输入：一行一个 gene）
- `top-lncrna-target-genes-ba<MIN_BA>-top<TOP_N>-species<SPECIES_ID>.md`（参数与 Top lncRNA 列表摘要）

**工具**:
```python
from gprofiler import GProfiler

gp = GProfiler(return_dataframe=True)
enrichment = gp.profile(organism='hsapiens', query=target_genes)
```

#### 1.4 调控网络拓扑分析

**网络构建**:
```python
import networkx as nx
import community  # Louvain 社区检测

# 构建网络
G = nx.DiGraph()
for reg in regulations:
    G.add_edge(reg['lncrna'], reg['target'], weight=reg['ba'])

# 网络指标
degree_centrality = nx.degree_centrality(G)
betweenness = nx.betweenness_centrality(G)
communities = community.best_partition(G.to_undirected())

# 可视化
pos = nx.spring_layout(G)
nx.draw_networkx(G, pos, node_color=communities.values())
```

**交付成果**:
- 网络拓扑 PDF
- 中心性分析报告
- 社区检测结果
- 关键调控节点列表

---

### 🧬 方向 2：跨物种保守性模式分析

**研究目标**: 揭示 lncRNA 调控在进化中的保守性规律

#### 2.1 保守性分类统计

**查询保守 lncRNA**:
```sql
-- 4 物种保守的 lncRNA
SELECT
    core_id,
    COUNT(DISTINCT species_id) as species_count,
    SUM(regulation_count) as total_regulations
FROM (
    SELECT
        g.core_id,
        r.species_id,
        COUNT(r.regulation_id) as regulation_count
    FROM genes g
    JOIN regulations r ON g.gene_id = r.lncrna_gene_id
    GROUP BY g.core_id, r.species_id
) subq
GROUP BY core_id
HAVING COUNT(DISTINCT species_id) = 4
ORDER BY total_regulations DESC;
```

**可复现产出（保守性分层统计 + Top 列表）**：
```bash
# 真实数据库（需后端 Python 依赖可用，环境变量同 backend：DB_HOST/DB_PORT/DB_NAME/DB_USER/DB_PASSWORD）
python3 scripts/research/conserved_lncrna_by_binding_affinity.py \
  --species-ids all \
  --min-ba 100 \
  --limit 50 \
  --out-dir docs/reports

# 本地 sample DB 烟测（不依赖真实大库）
bash scripts/research/generate_conserved_lncrna_sample_baseline_local.sh
```

**输出文件**（默认 `--out-dir docs/reports`）：
- `conserved-lncrna-ba<MIN_BA>-top<LIMIT>-species-<group>.csv`（Top 列表，可追溯）
- `conserved-lncrna-ba<MIN_BA>-top<LIMIT>-species-<group>.md`（分层统计 + Top 列表摘要）

**分层统计**:
| 保守等级 | lncRNA 数量 | 调控关系 | 占比 |
|---------|-----------|----------|------|
| 4 物种 | 1,001 | 437,478 | 50.84% |
| 3 物种 | 653 | 246,860 | 33.16% |
| 2 物种 | 276 | 109,861 | 14.02% |
| 1 物种 | 39 | 10,431 | 1.98% |

#### 2.2 保守性矩阵与热力图

✅ **可复现产出（保守性矩阵 + 热力图）**：基于 BA 阈值，按 lncRNA `core_id` 聚合，输出“物种两两共享数量矩阵 + 行归一化共享率矩阵”（CSV + Markdown），并在本机安装 `matplotlib` 时额外输出 PNG 热力图（缺失依赖则跳过，不报错）。

```bash
# 真实数据库（需后端 Python 依赖可用，环境变量同 backend：DB_HOST/DB_PORT/DB_NAME/DB_USER/DB_PASSWORD）
python3 scripts/research/conservation_matrix_by_binding_affinity.py \
  --species-ids all \
  --min-ba 100 \
  --out-dir docs/reports

# 本地 sample DB 烟测（不依赖真实大库；样例数据 lncRNA 仅在 human，其他物种矩阵可能为 0）
bash scripts/research/generate_conservation_matrix_sample_baseline_local.sh
```

输出文件（默认 `--out-dir docs/reports`）：
- `conservation-matrix-ba<MIN_BA>-species-<group>-counts.csv`（共享数量矩阵）
- `conservation-matrix-ba<MIN_BA>-species-<group>-row-share.csv`（行归一化共享率矩阵）
- `conservation-matrix-ba<MIN_BA>-species-<group>.md`（口径说明 + 表格摘要）
- `conservation-matrix-ba<MIN_BA>-species-<group>-counts.png`（可选：counts 热力图）
- `conservation-matrix-ba<MIN_BA>-species-<group>-row-share.png`（可选：row-share 热力图）

**计算物种间共享矩阵**:
```python
import numpy as np
import seaborn as sns

# 计算物种间共享的 lncRNA 数量
species_pairs = [
    ('Human', 'Chimp'),
    ('Human', 'Macaque'),
    ('Human', 'Marmoset'),
    ('Chimp', 'Macaque'),
    ('Chimp', 'Marmoset'),
    ('Macaque', 'Marmoset'),
]

shared_matrix = np.array([...])  # 4x4 对称矩阵

# 热力图
plt.figure(figsize=(8, 6))
sns.heatmap(shared_matrix,
            annot=True,
            fmt='d',
            cmap='YlOrRd',
            xticklabels=['Human', 'Chimp', 'Macaque', 'Marmoset'],
            yticklabels=['Human', 'Chimp', 'Macaque', 'Marmoset'])
plt.title('Shared lncRNAs Between Species')
plt.savefig('conservation_heatmap.png', dpi=300)
```

#### 2.3 进化距离与保守性相关性

**分析思路**:
1. 定义进化距离（基于系统发育树）
2. 计算物种对间的 lncRNA 共享率
3. 相关性分析（Pearson/Spearman）
4. 线性回归建模

✅ **可复现产出（进化距离 vs 保守性相关性）**：基于 BA 阈值，按 lncRNA `core_id` 聚合，输出“物种对 pairwise 指标”（CSV + Markdown），并计算 `distance_mya` 与 `jaccard/avg_row_share` 的 Pearson/Spearman 相关系数；本机安装 `matplotlib` 时额外输出散点图 PNG（缺失依赖则跳过，不报错）。

```bash
# 真实数据库（需后端 Python 依赖可用，环境变量同 backend：DB_HOST/DB_PORT/DB_NAME/DB_USER/DB_PASSWORD）
python3 scripts/research/conservation_distance_correlation_by_binding_affinity.py \
  --species-ids all \
  --min-ba 100 \
  --out-dir docs/reports

# 可选：用 JSON 覆盖/补齐进化距离（Mya），用于不同物种集合或更精细的系统发育距离
# JSON 格式示例：{"human-chimp": 6, "human-macaque": 25, "human-marmoset": 40, "chimp-macaque": 25, ...}
python3 scripts/research/conservation_distance_correlation_by_binding_affinity.py \
  --species-ids all \
  --min-ba 100 \
  --distances-json docs/reports/distance_mya_overrides.json \
  --out-dir docs/reports

# 本地 sample DB 烟测（不依赖真实大库；样例数据 lncRNA 仅在 human，相关性可能为 N/A）
bash scripts/research/generate_conservation_distance_correlation_sample_baseline_local.sh
```

输出文件（默认 `--out-dir docs/reports`）：
- `conservation-distance-ba<MIN_BA>-species-<group>.csv`（pairwise 指标）
- `conservation-distance-ba<MIN_BA>-species-<group>.md`（指标表 + 相关系数汇总）
- `conservation-distance-ba<MIN_BA>-species-<group>-jaccard.png`（可选：Jaccard vs distance 散点图）
- `conservation-distance-ba<MIN_BA>-species-<group>-avg-row-share.png`（可选：avg row-share vs distance 散点图）

**预期发现**:
- 进化距离越近，共享 lncRNA 越多
- 人-黑猩猩共享最多（进化距离最近）
- 量化进化保守性的衰减速率

#### 2.4 功能富集分析

**研究问题**: 保守的 lncRNA 调控哪些功能？

✅ **可复现产出（导出靶基因列表，用于富集输入）**：基于 BA 阈值与指定保守等级（`species_count`），按 lncRNA `core_id` 聚合选出 lncRNA 集合，并汇总其靶基因列表（TSV/TXT/MD）。默认支持在同一次运行中额外导出 `species_count==1`（物种特异）用于对比。

```bash
# 真实数据库（需后端 Python 依赖可用，环境变量同 backend：DB_HOST/DB_PORT/DB_NAME/DB_USER/DB_PASSWORD）
# 说明：--species-count 0 表示“使用最大保守等级”（= len(species_ids)）
python3 scripts/research/conserved_lncrna_target_genes_for_enrichment.py \
  --species-ids all \
  --min-ba 100 \
  --species-count 0 \
  --include-specific \
  --target-protein-coding-only \
  --out-dir docs/reports

# 本地 sample DB 烟测（不依赖真实大库；样例数据 lncRNA 仅在 human，因此全保守（species_count==4）会为空；脚本默认同时导出 species_count==1）
bash scripts/research/generate_conserved_lncrna_target_genes_sample_baseline_local.sh
```

输出文件（默认 `--out-dir docs/reports`）：
- `conserved-lncrna-target-genes-ba<MIN_BA>-sc<SPECIES_COUNT>-species-<group>.tsv`（带统计字段，可追溯）
- `conserved-lncrna-target-genes-ba<MIN_BA>-sc<SPECIES_COUNT>-species-<group>.txt`（富集输入：一行一个 gene）
- `conserved-lncrna-target-genes-ba<MIN_BA>-sc<SPECIES_COUNT>-species-<group>.md`（参数与 lncRNA 预览摘要）
- `conserved-lncrna-target-genes-ba<MIN_BA>-species-<group>.md`（可选：当同时导出多个 `species_count` 时生成索引）

**分析步骤**:
```python
# 1. 提取 4 物种保守 lncRNA 的靶基因
conserved_targets = df[df['species_count'] == 4]['target_genes'].tolist()

# 2. GO enrichment
enrichment = gp.profile(organism='hsapiens', query=conserved_targets)

# 3. 对比：保守 vs 物种特异性
specific_targets = df[df['species_count'] == 1]['target_genes'].tolist()
enrichment_specific = gp.profile(organism='hsapiens', query=specific_targets)

# 4. 比较富集结果
compare_enrichment(enrichment, enrichment_specific)
```

**交付成果**:
- 保守 lncRNA 功能富集报告
- 物种特异性功能分析
- 生物学意义解读

---

### 🎨 方向 3：表观遗传标记关联分析

**研究目标**: 揭示 lncRNA 调控位点的染色质状态特征

#### 3.1 ChIP-seq 峰与调控位点重叠

**可复现脚本（推荐）**：
```bash
# 真实数据库（默认 out_dir=docs/reports）
python3 scripts/research/epigenetic_summary_by_binding_affinity.py --min-ba 100

# 本地 sample DB 烟测（不依赖真实大库；样例 BA≈55–82，默认 MIN_BA=50）
bash scripts/research/generate_epigenetic_summary_sample_baseline_local.sh
```

输出文件（默认 `--out-dir docs/reports`）：
- `epigenetic-summary-ba<MIN_BA>.tsv`（mark×category×cell_type 明细）
- `epigenetic-summary-ba<MIN_BA>.md`（Top marks / Top cell types / category 汇总）

**查询重叠数据**:
```sql
-- 使用物化视图（Phase 4.2 优化）
SELECT
    l.lncrna_gene_id,
    l.target_gene_id,
    l.binding_affinity,
    o.mark_name,
    o.peak_score,
    o.cell_type
FROM regulations l
JOIN mv_lncrna_chipseq_overlaps o
  ON l.species_id = o.species_id
  AND l.chr = o.lncrna_chr
  AND l.start_in_genome BETWEEN o.peak_start AND o.peak_end
WHERE l.binding_affinity > 100
  AND o.mark_name IN ('H3K4me3', 'H3K27me3', 'H3K27ac')
LIMIT 10000;
```

**分析指标**:
1. **重叠率**: 有多少高亲和力位点在表观遗传标记峰内？
2. **标记偏好**: H3K4me3（活性启动子）vs H3K27me3（抑制）分布
3. **双价域**: H3K4me3 + H3K27me3 同时存在的位点

#### 3.2 双价域（Bivalent Domain）分析

**查询双价域**:
```sql
SELECT
    lncrna_gene_id,
    target_gene_id,
    COUNT(CASE WHEN mark_name = 'H3K4me3' THEN 1 END) as h3k4me3_count,
    COUNT(CASE WHEN mark_name = 'H3K27me3' THEN 1 END) as h3k27me3_count
FROM mv_lncrna_chipseq_overlaps
GROUP BY lncrna_gene_id, target_gene_id
HAVING h3k4me3_count > 0 AND h3k27me3_count > 0;
```

**生物学意义**:
- 双价域通常标记发育相关基因
- 启动子处于"准备好但未激活"状态
- 与干细胞分化相关

**可视化**:
- Venn 图（H3K4me3, H3K27me3, 调控位点）
- 散点图（BA vs 峰强度）
- 热力图（lncRNA × 组蛋白标记）

#### 3.3 染色质可及性分析

**DNase-seq 数据利用**:
```sql
-- 调控位点在开放染色质区域的比例
SELECT
    species_id,
    COUNT(*) as total_regulations,
    COUNT(CASE WHEN in_dnase_peak THEN 1 END) as in_open_chromatin,
    ROUND(100.0 * COUNT(CASE WHEN in_dnase_peak THEN 1 END) / COUNT(*), 2) as percentage
FROM regulations_with_chromatin_state
GROUP BY species_id;
```

**预期发现**:
- 高 BA 位点更可能在开放染色质区域
- 细胞类型特异性（K562 vs 其他细胞系）

#### 3.4 重复元件对调控的影响

**分析 RepeatMasker 数据**:
```sql
-- 调控位点与重复元件重叠
SELECT
    rm.repeat_class,
    rm.repeat_family,
    COUNT(DISTINCT r.regulation_id) as regulation_count,
    AVG(r.binding_affinity) as avg_ba
FROM regulations r
JOIN repeat_masker rm
  ON r.species_id = rm.species_id
  AND r.chr = rm.chr
  AND r.start_in_genome BETWEEN rm.start_pos AND rm.end_pos
GROUP BY rm.repeat_class, rm.repeat_family
ORDER BY regulation_count DESC;
```

**研究问题**:
- 转座子（SINE, LINE）是否富集在调控位点？
- 重复元件对调控强度（BA）的影响？

---

### 🏥 方向 4：疾病关联网络分析

**研究目标**: 构建疾病-lncRNA-靶基因三层网络，识别潜在治疗靶点

#### 4.1 三层网络构建

**可复现脚本（最小汇总）**：
```bash
# 真实数据库（默认 out_dir=docs/reports）
python3 scripts/research/disease_network_summary.py --evidence-species-id 1 --top-traits 50 --top-lncrnas 50

# 本地 sample DB 烟测（不依赖真实大库）
bash scripts/research/generate_disease_network_summary_sample_baseline_local.sh
```

输出文件（默认 `--out-dir docs/reports`）：
- `disease-network-traits-evidence-<EVIDENCE_SPECIES_ID|all>.tsv`（Top diseases）
- `disease-network-lncrnas-evidence-<EVIDENCE_SPECIES_ID|all>.tsv`（Top lncRNAs）
- `disease-network-summary-evidence-<EVIDENCE_SPECIES_ID|all>.md`（参数与预览摘要）

**数据整合**:
```python
import networkx as nx

# 构建三层网络
G = nx.Graph()

# 第一层：疾病节点
G.add_nodes_from(diseases, node_type='disease')

# 第二层：靶基因节点
G.add_nodes_from(target_genes, node_type='gene')

# 第三层：lncRNA 节点
G.add_nodes_from(lncrnas, node_type='lncrna')

# 边：疾病-基因（trait_gene_associations）
G.add_edges_from(disease_gene_edges, edge_type='disease_gene')

# 边：基因-lncRNA（regulations）
G.add_edges_from(gene_lncrna_edges, edge_type='regulation')
```

**网络指标**:
- 节点度中心性（哪些 lncRNA/基因最关键）
- 最短路径（疾病 → lncRNA 的间接关联）
- 子图提取（特定疾病的调控子网络）

#### 4.2 重大疾病的 lncRNA 靶点

**关注疾病清单**:
1. Type 2 Diabetes（2 型糖尿病）
2. Alzheimer's Disease（阿尔茨海默病）
3. Coronary Artery Disease（冠状动脉疾病）
4. Breast Cancer（乳腺癌）
5. Schizophrenia（精神分裂症）

**分析模板**（以糖尿病为例）:
```python
# 1. 查询糖尿病关联基因
diabetes_genes = """
SELECT DISTINCT g.gene_id, g.gene_name
FROM trait_gene_associations tga
JOIN genes g ON tga.core_id = g.core_id
WHERE tga.trait_name LIKE '%diabetes%'
"""

# 2. 查询调控这些基因的 lncRNA
regulating_lncrnas = """
SELECT DISTINCT
    lnc.gene_id,
    lnc.gene_name,
    COUNT(DISTINCT r.target_gene_id) as target_count,
    AVG(r.binding_affinity) as avg_ba
FROM genes lnc
JOIN regulations r ON lnc.gene_id = r.lncrna_gene_id
WHERE r.target_gene_id IN (...)  -- diabetes genes
GROUP BY lnc.gene_id, lnc.gene_name
ORDER BY target_count DESC;
```

**可视化**:
- Cytoscape.js 网络图（疾病 → 基因 → lncRNA）
- Sankey 流向图
- 热力图（lncRNA × 疾病关联基因）

#### 4.3 潜在治疗靶点识别

**排序标准**:
1. **调控数量** (targets 越多越关键)
2. **结合亲和力** (BA 越高越稳定)
3. **保守性** (跨物种保守优先)
4. **疾病关联强度** (GWAS p-value)
5. **可成药性** (文献支持)

**生成报告**:
```python
therapeutic_targets = pd.DataFrame({
    'rank': ...,
    'lncrna_name': ...,
    'disease': ...,
    'target_count': ...,
    'avg_ba': ...,
    'conservation': ...,
    'gwas_pvalue': ...,
    'druggability_score': ...,
    'literature_support': ...
})
```

---

## 技术实现方案

### 环境配置

**所需工具**:
```bash
# Python 数据分析栈
pip install pandas numpy scipy matplotlib seaborn
pip install networkx python-louvain
pip install gprofiler-official  # GO enrichment
pip install jupyter notebook
pip install scikit-learn  # 机器学习（可选）
pip install statsmodels  # 统计分析
```

**Jupyter Notebook 结构**:
```
notebooks/
├── 01_high_affinity_analysis.ipynb
├── 02_conservation_patterns.ipynb
├── 03_epigenetic_marks.ipynb
├── 04_disease_networks.ipynb
└── utils/
    ├── db_connection.py
    ├── plotting_utils.py
    └── network_analysis.py
```

### 数据导出 API

**新建端点**（可选）:
```python
# app/routers/export.py
@router.get("/export/high-affinity-regulations")
def export_high_affinity(min_ba: float = 100):
    """导出高亲和力调控关系（用于科研分析）"""
    # 查询 + 格式化
    # 返回 CSV/JSON
```

### 可视化集成

**前端新页面**（可选）:
```
/research-insights
├── /high-affinity-network
├── /conservation-evolution
├── /epigenetic-landscape
└── /disease-associations
```

---

## 交付成果清单

### 数据分析成果

1. **Jupyter Notebooks** (4-6 个)
   - 完整的分析流程
   - 可重现的代码
   - 统计检验结果

2. **数据集** (CSV/Excel)
   - Top 100 高亲和力 lncRNA
   - 保守 lncRNA 列表
   - 疾病关联 lncRNA 靶点

3. **可视化图表** (发表质量，300 DPI)
   - BA 分布图
   - 保守性热力图
   - 网络拓扑图
   - 富集分析气泡图

4. **统计分析报告** (Markdown)
   - 描述性统计
   - 假设检验结果
   - 生物学解读

### 科研产出（潜在）

5. **研究论文草稿**
   - Introduction（背景介绍）
   - Methods（方法描述）
   - Results（结果呈现）
   - Discussion（讨论）

6. **补充材料**
   - 完整基因列表
   - 原始数据表
   - 分析代码

---

## 工作量估算

### Day 1: 高亲和力分析（6-8 小时）

**上午**（4 小时）:
- 数据查询和清洗
- 描述性统计
- BA 分布分析

**下午**（3-4 小时）:
- Top lncRNA 排行榜
- 靶基因功能富集
- 可视化图表生成

---

### Day 2: 保守性模式分析（6-8 小时）

**上午**（4 小时）:
- 保守性分类统计
- 物种间共享矩阵
- 热力图生成

**下午**（3-4 小时）:
- 进化距离相关性
- 功能富集对比
- 生物学解读

---

### Day 3: 表观遗传关联（6-8 小时）

**上午**（4 小时）:
- ChIP-seq 峰重叠分析
- 双价域检测
- 染色质状态分类

**下午**（3-4 小时）:
- DNase-seq 开放染色质
- RepeatMasker 重复元件
- 综合分析报告

---

### Day 4: 疾病网络与整合（4-6 小时）

**上午**（3 小时）:
- 三层网络构建
- 中心性分析
- 子网络提取

**下午**（2-3 小时）:
- 潜在靶点识别
- 整合所有分析结果
- 生成最终报告

---

## 成功验收标准

### 科研质量

- ✅ 统计检验 p < 0.05
- ✅ 可视化符合发表标准（300 DPI）
- ✅ 分析逻辑清晰可重现
- ✅ 生物学解读合理

### 技术质量

- ✅ Jupyter Notebook 可运行
- ✅ 代码注释完整
- ✅ 数据导出格式规范
- ✅ 图表标注清晰

### 产出丰富度

- ✅ 至少 4 个分析维度
- ✅ 至少 10 张发表质量图表
- ✅ 至少 2-3 个新发现或假说
- ✅ 完整的方法和结果文档

---

## 风险评估

| 风险 | 概率 | 影响 | 缓解措施 |
|------|------|------|----------|
| **数据质量问题** | 中 | 高 | 数据清洗 + 异常值检测 |
| **统计显著性不足** | 中 | 中 | 增加样本量 + 非参数检验 |
| **生物学解读错误** | 低 | 高 | 文献验证 + 专家审核 |
| **计算资源不足** | 低 | 中 | 优化查询 + 分批处理 |
| **可重现性问题** | 低 | 中 | 固定随机种子 + 版本锁定 |

---

## 参考文献与资源

### 数据库与工具

1. **g:Profiler** - GO enrichment analysis
   - URL: https://biit.cs.ut.ee/gprofiler/
   - API: Python package `gprofiler-official`

2. **DAVID** - Functional annotation
   - URL: https://david.ncifcrf.gov/

3. **STRING** - 蛋白质相互作用网络
   - URL: https://string-db.org/

4. **NCBI Gene** - 基因功能注释
   - URL: https://www.ncbi.nlm.nih.gov/gene

### 相关文献

1. lncRNA 调控机制综述
2. 跨物种保守性研究
3. 表观遗传与基因调控
4. lncRNA 与疾病关联

---

## 后续扩展方向

### 短期扩展（1-2 周）

1. **时间序列分析**（如有时间维度数据）
2. **亚细胞定位分析**（lncRNA 在细胞内的位置）
3. **RNA 结构预测**（二级结构与功能关系）

### 中期扩展（1-2 月）

4. **机器学习建模**
   - 预测 lncRNA-靶基因相互作用
   - 调控强度（BA）预测模型
   - 疾病关联预测

5. **比较基因组学**
   - 序列保守性分析
   - 同源性建模
   - 进化选择压力

6. **单细胞数据整合**（如有）
   - lncRNA 细胞类型特异性表达
   - 发育轨迹分析

---

## 总结

**Phase 6.0 科研数据分析**将：

1. **最大化数据价值** - 80 万+调控关系的深度挖掘
2. **产出科研成果** - 可发表的图表和发现
3. **提升学术影响** - 独特的跨物种 lncRNA 数据集
4. **支撑假说生成** - 为实验验证提供方向

**预期产出**:
- 4-6 个 Jupyter Notebooks
- 10+ 发表质量图表
- 2-3 个新发现或假说
- 完整的分析报告

**已落地（最小可复现）**：
- `scripts/research/` 下已提供方向 1/2/3/4 的导出脚本入口（Top lncRNA、保守性分层/矩阵/相关性、靶基因富集输入、表观遗传汇总、疾病网络汇总）。
- `notebooks/` 已存在 Phase 6.0-B 的 Notebook 模板（01–04），可作为“深化分析 + 发表图表”的载体。

**下一步（建议）**：
1. 在真实数据库上运行上述脚本，生成 `docs/reports/` 的可追溯产物（TSV/CSV/MD/TXT/可选 PNG）。
2. 富集分析：将导出的 `*.txt` 靶基因列表输入 g:Profiler / DAVID（或按需引入 `gprofiler-official`）。
3. 将关键结论与图表沉淀到 `notebooks/`（或补充 `docs/reports/` 的结果解读文档），形成可复用的“方法 + 结果”闭环。

---

**规划创建**: 2025-12-10
**规划版本**: Phase 6.0
**状态**: 🚧 已完成最小可复现脚本产出；后续为深化分析与图表/解读整理（现状以 `docs/CURRENT_STATUS.md` 为准）

**AI 协助**: GPT-5.2 (Codex) + 人工复核
