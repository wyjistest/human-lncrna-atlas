# Phase 6.0-B Jupyter Notebooks 使用指南

**项目**: Human LncRNA Atlas
**阶段**: Phase 6.0-B (科研数据深度分析)
**创建日期**: 2025-12-11
**状态**: ✅ 所有 Notebooks 已就绪

---

## 📚 Notebooks 清单

| Notebook | 分析主题 | 预计时间 | 输出成果 |
|----------|---------|---------|---------|
| `01_high_affinity_analysis.ipynb` | 高亲和力调控网络 | 2-3h | Top 100 lncRNA + 网络图 |
| `02_conservation_patterns.ipynb` | 跨物种保守性模式 | 2-3h | 保守性热力图 + 统计 |
| `03_epigenetic_marks.ipynb` | 表观遗传标记关联 | 2-3h | 双价域分析 + 染色质图 |
| `04_disease_networks.ipynb` | 疾病关联网络 | 2-3h | 治疗靶点排行榜 |

---

## 🚀 快速开始

### 1. 安装依赖环境

```bash
cd /data/wenyujianData/human-lncrna-atlas-github/notebooks

# 安装所有必需的库
pip install -r requirements.txt

# 安装额外的可视化库
pip install matplotlib-venn python-louvain
```

**预计安装时间**: 5-10 分钟

### 2. 启动 Jupyter Notebook

```bash
# 启动 Jupyter
jupyter notebook

# 或使用 JupyterLab（推荐）
jupyter lab
```

**访问**: http://localhost:8888

### 3. 确保后端 API 运行

```bash
# 在另一个终端窗口
cd /data/wenyujianData/humanLncAtlas/frontend/backend
source venv/bin/activate
python3 -m uvicorn main:app --reload --port 8000

# 测试 API
curl http://localhost:8000/health
```

---

## 📖 使用每个 Notebook 的步骤

### Notebook 01: 高亲和力调控网络分析

**目标**: 识别核心 lncRNA 并分析其调控网络

**运行步骤**:
1. 打开 `01_high_affinity_analysis.ipynb`
2. 按顺序执行所有 cell（点击 Cell → Run All）
3. 根据需要调整参数：
   - `MIN_BA`: 最小结合亲和力（默认 100）
   - `LIMIT`: 数据量（默认 10000）
   - `SPECIES_ID`: 物种筛选（默认 None = 所有物种）

**预期输出**:
- ✅ `results/top_100_high_affinity_lncrnas.xlsx` - Top 100 排行榜
- ✅ `results/network_nodes.csv` - 网络节点数据
- ✅ `results/network_edges.csv` - 网络边数据
- ✅ `figures/01_ba_distribution_analysis.png` - BA 分布图
- ✅ `figures/02_top_lncrnas_visualization.png` - Top 20 可视化
- ✅ `figures/03_centrality_analysis.png` - 中心性分析
- ✅ `figures/04_regulatory_network_visualization.png` - 网络拓扑图

**分析亮点**:
- 📊 4 种统计图表（直方图、箱线图、密度图、CDF）
- 🌐 NetworkX 网络拓扑分析（度中心性、介数中心性）
- 🔍 社区检测（Louvain 算法）
- 📈 多维度可视化

---

### Notebook 02: 跨物种保守性模式分析

**目标**: 揭示 lncRNA 在进化中的保守性规律

**运行步骤**:
1. 打开 `02_conservation_patterns.ipynb`
2. 执行所有 cell
3. 可调整参数：
   - `min_species_count`: 最少保守物种数（2/3/4）

**预期输出**:
- ✅ `results/conservation_summary.xlsx` - 保守性统计
- ✅ `results/highly_conserved_lncrnas_4species.xlsx` - 4 物种保守排行榜
- ✅ `results/conservation_statistical_tests.csv` - 统计检验结果
- ✅ `figures/05_conservation_distribution.png` - 保守性分布
- ✅ `figures/06_conservation_heatmap.png` - 物种共享热力图
- ✅ `figures/07_conservation_characteristics.png` - 保守性特征图
- ✅ `figures/08_conservation_venn_diagrams.png` - Venn 图

**分析亮点**:
- 🔬 物种间共享矩阵分析
- 📊 保守性分层统计（2/3/4 物种）
- 🧬 进化距离与保守性关系
- 📈 Kruskal-Wallis H 检验 + Spearman 相关性

---

### Notebook 03: 表观遗传标记关联分析

**目标**: 分析 lncRNA 调控位点的染色质状态

**运行步骤**:
1. 打开 `03_epigenetic_marks.ipynb`
2. 执行所有 cell
3. 可选：修改分析的组蛋白标记列表

**预期输出**:
- ✅ `results/bivalent_domains.xlsx` - 双价域列表
- ✅ `figures/09_chipseq_mark_distribution.png` - 标记分布
- ✅ `figures/10_bivalent_domain_analysis.png` - 双价域分析
- ✅ `figures/11_ba_vs_peak_score.png` - BA vs 峰强度相关性
- ✅ `figures/12_cell_type_mark_heatmap.png` - 细胞类型热力图
- ✅ `figures/13_chromatin_state_classification.png` - 染色质状态分类

**分析亮点**:
- 🧬 双价域（Bivalent Domain）自动检测
- 📊 6 种组蛋白标记全覆盖分析
- 🔬 细胞类型特异性分析
- 📈 BA 与峰强度 Spearman 相关性检验

**生物学意义**:
- 双价域通常标记发育相关基因
- 活性启动子（H3K4me3）vs 抑制性标记（H3K27me3）

---

### Notebook 04: 疾病关联网络分析

**目标**: 构建疾病-基因-lncRNA 三层网络，识别治疗靶点

**运行步骤**:
1. 打开 `04_disease_networks.ipynb`
2. 执行所有 cell
3. 可修改分析的疾病列表（默认：diabetes, alzheimer, cancer, cardiovascular, autism）

**预期输出**:
- ✅ `results/diabetes_lncrna_targets.xlsx` - 糖尿病 lncRNA 靶点
- ✅ `results/therapeutic_targets_ranking.xlsx` - 治疗靶点排行榜
- ✅ `figures/14_diabetes_therapeutic_targets.png` - 靶点排行图
- ✅ `figures/15_disease_shared_lncrnas.png` - 疾病共享热力图
- ✅ `figures/16_diabetes_network_visualization.png` - 三层网络图

**分析亮点**:
- 🏥 5 种重大疾病网络构建
- 🎯 基于中心性的靶点排序
- 🔗 三层网络（疾病-基因-lncRNA）可视化
- 📊 疾病间共享 lncRNA 分析

**临床转化价值**:
- 识别高优先级治疗靶点
- 揭示疾病间共同调控机制

---

## ⚙️ 高级配置

### 调整数据量

如果内存有限或需要快速测试，可以调整 `LIMIT` 参数：

```python
# 在每个 Notebook 的第二个 cell 中修改
LIMIT = 1000  # 小规模测试
LIMIT = 10000  # 默认（推荐）
LIMIT = 50000  # 大规模分析（需要更多内存）
```

### 修改物种筛选

```python
# 只分析人类数据
SPECIES_ID = 1

# 只分析黑猩猩
SPECIES_ID = 2

# 分析所有物种
SPECIES_ID = None  # 默认
```

### 调整可视化参数

```python
# 修改图表 DPI（发表质量）
plt.savefig('output.png', dpi=300)  # 默认
plt.savefig('output.png', dpi=600)  # 超高清（文件大）

# 修改图表尺寸
plt.figure(figsize=(12, 8))  # 默认
plt.figure(figsize=(20, 16))  # 大图
```

---

## 🔧 故障排除

### 问题 1: 模块导入错误

**错误**: `ModuleNotFoundError: No module named 'xxx'`

**解决**:
```bash
pip install xxx
# 或重新安装所有依赖
pip install -r requirements.txt
```

### 问题 2: API 连接失败

**错误**: `requests.exceptions.ConnectionError`

**解决**:
```bash
# 检查后端是否运行
curl http://localhost:8000/health

# 如果未运行，启动后端
cd /data/wenyujianData/humanLncAtlas/frontend/backend
source venv/bin/activate
python3 -m uvicorn main:app --reload --port 8000
```

### 问题 3: 内存不足

**错误**: `MemoryError` 或系统卡死

**解决**:
```python
# 减少 LIMIT 参数
LIMIT = 1000  # 从 10000 降低到 1000

# 分批处理数据
for i in range(0, total, batch_size):
    batch = df.iloc[i:i+batch_size]
    # 处理 batch...
```

### 问题 4: 中文字体显示问题

**错误**: 图表中中文显示为方框

**解决**:
```python
# 在 Notebook 开头添加
import matplotlib.pyplot as plt
plt.rcParams['font.sans-serif'] = ['Arial Unicode MS', 'SimHei', 'DejaVu Sans']
plt.rcParams['axes.unicode_minus'] = False
```

---

## 📊 预期分析成果

### 数据集（Excel/CSV）

1. **Top 100 高亲和力 lncRNA** - 可发表的补充材料
2. **保守 lncRNA 列表** - 独特的跨物种数据
3. **双价域位点** - 表观遗传调控热点
4. **疾病治疗靶点** - 临床转化价值
5. **网络节点/边数据** - 可导入 Cytoscape

### 图表（300 DPI 发表质量）

- ✅ 12+ 张统计分析图
- ✅ 4+ 张网络拓扑图
- ✅ 6+ 张热力图/Venn 图
- ✅ 所有图表符合发表标准

### 统计分析报告

- ✅ 描述性统计（均值、中位数、标准差）
- ✅ 假设检验（Kruskal-Wallis, Mann-Whitney, Spearman）
- ✅ 相关性分析
- ✅ 生物学意义解读

---

## 🎯 执行建议

### Day 1: 高亲和力 + 保守性分析

```bash
# 上午（3小时）
jupyter notebook 01_high_affinity_analysis.ipynb
# 预期产出：Top 100 lncRNA + 网络分析

# 下午（3小时）
jupyter notebook 02_conservation_patterns.ipynb
# 预期产出：保守性热力图 + 统计检验
```

### Day 2: 表观遗传 + 疾病网络分析

```bash
# 上午（3小时）
jupyter notebook 03_epigenetic_marks.ipynb
# 预期产出：双价域分析 + 染色质状态

# 下午（3小时）
jupyter notebook 04_disease_networks.ipynb
# 预期产出：治疗靶点排行榜 + 三层网络
```

### Day 3: 结果整合与论文准备

- 汇总所有分析发现
- 撰写分析报告
- 准备论文图表和补充材料

---

## 📝 使用技巧

### 1. 批量运行所有 Cell

```python
# 在 Jupyter 菜单栏
Cell → Run All
```

### 2. 导出 HTML 报告

```bash
# 在命令行
jupyter nbconvert --to html 01_high_affinity_analysis.ipynb
```

### 3. 导出 PDF（需要 LaTeX）

```bash
jupyter nbconvert --to pdf 01_high_affinity_analysis.ipynb
```

### 4. 清除所有输出

```python
# 在 Jupyter 菜单栏
Cell → All Output → Clear
```

---

## 🔍 代码复用建议

### 复用数据获取代码

所有 Notebooks 都使用相同的 API 调用模式：

```python
import requests
import pandas as pd

API_BASE_URL = "http://localhost:8000/api/v1"

# 模板
response = requests.get(
    f"{API_BASE_URL}/export/{endpoint}",
    params={...}
)

if response.status_code == 200:
    data = response.json()
    df = pd.DataFrame(data['data'])
else:
    print(f"错误: {response.status_code}")
```

### 复用可视化代码

标准图表模板：

```python
# 保存高质量图表的标准格式
plt.savefig('figures/output.png',
            dpi=300,                    # 发表质量
            bbox_inches='tight',        # 去除空白边距
            facecolor='white')          # 白色背景
```

---

## 📚 扩展分析方向

### 可选分析 1: GO 功能富集

```python
from gprofiler import GProfiler

# 提取 Top 100 lncRNA 的靶基因
target_genes = df[df['lncrna_name'].isin(top_100_names)]['target_name'].unique()

# GO enrichment
gp = GProfiler(return_dataframe=True)
enrichment = gp.profile(organism='hsapiens', query=target_genes.tolist())

print(enrichment.head(20))
```

### 可选分析 2: 序列保守性

```python
from Bio import pairwise2
from Bio.Seq import Seq

# 提取保守 lncRNA 的序列
# 进行多序列比对
# 计算序列相似度
```

### 可选分析 3: 机器学习建模

```python
from sklearn.ensemble import RandomForestClassifier
from sklearn.model_selection import train_test_split

# 预测调控强度（BA）
# 特征：lncRNA 特性、染色质状态、保守性等
```

---

## ✅ 检查清单

运行 Notebooks 前确认：

- [ ] 已安装所有依赖（`pip install -r requirements.txt`）
- [ ] 后端 API 正常运行（http://localhost:8000/health 返回 200）
- [ ] 创建了输出目录（data/, figures/, results/）
- [ ] 有足够的磁盘空间（建议 >2GB）
- [ ] 有足够的内存（建议 >4GB）

运行 Notebooks 后验证：

- [ ] 所有 cell 成功执行（无红色错误）
- [ ] 生成了所有预期的图表文件
- [ ] 生成了所有预期的数据文件
- [ ] 图表质量符合预期（300 DPI）
- [ ] 统计检验结果合理（p < 0.05）

---

## 🎓 学习资源

### pandas 文档
- 官方文档: https://pandas.pydata.org/docs/
- 10 Minutes to pandas: https://pandas.pydata.org/docs/user_guide/10min.html

### NetworkX 文档
- 官方文档: https://networkx.org/documentation/stable/
- Tutorial: https://networkx.org/documentation/stable/tutorial.html

### Seaborn 文档
- 官方文档: https://seaborn.pydata.org/
- Gallery: https://seaborn.pydata.org/examples/index.html

### 统计分析
- SciPy Stats: https://docs.scipy.org/doc/scipy/reference/stats.html
- Statsmodels: https://www.statsmodels.org/

---

## 💡 最佳实践

### 1. 版本控制

```bash
# 保存 Notebook 到 Git（去除输出）
jupyter nbconvert --clear-output --inplace *.ipynb
git add notebooks/
git commit -m "feat: add Phase 6.0-B analysis notebooks"
```

### 2. 可重现性

```python
# 在每个 Notebook 开头设置随机种子
import random
import numpy as np

random.seed(42)
np.random.seed(42)
```

### 3. 代码注释

- 为每个分析步骤添加清晰的 Markdown 说明
- 关键代码添加行内注释
- 解释生物学意义

### 4. 结果验证

- 检查数据质量（缺失值、异常值）
- 验证统计检验的前提条件
- 与文献结果对比验证

---

## 📧 获取帮助

如果遇到问题：

1. **检查文档**: 阅读本指南的故障排除部分
2. **查看日志**: 检查 Jupyter 输出和后端日志
3. **测试 API**: 使用 curl 命令独立测试 API
4. **简化分析**: 减少数据量，逐步调试

---

## 🎯 下一步：Phase 6.0-C（可选）

完成所有分析后，可以考虑：

1. **创建前端展示页面** - 将分析结果集成到 Web 界面
2. **撰写科研论文** - 使用生成的图表和数据
3. **深度分析** - 基于初步发现，进行更深入的探索

---

**文档创建**: 2025-12-11
**版本**: Phase 6.0-B
**AI 协助**: Claude Sonnet 4.5 (1M context)
