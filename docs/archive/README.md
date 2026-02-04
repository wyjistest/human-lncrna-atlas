# Human lncRNA-DNA Binding Analysis

人类lncRNA-DNA结合分析工具包，支持超大规模数据集（1000万+文件）的高效处理。

> ⚠️ 本目录为历史归档材料，可能与当前代码不一致，不保证更新。  
> 当前项目现状以 `docs/CURRENT_STATUS.md` 为准；开发/维护入口请优先查看 `docs/README.md`。

## 📁 文件说明

```
humanLncAtlas/
├── analyze_peaks_binding_affinity.py  # 主分析脚本
├── human_lncrna_config.yaml           # YAML配置文件
├── USAGE_EXAMPLES.md                   # 详细使用示例
├── README.md                           # 本文件
├── resultMinusLongTarget/              # 负链lncRNA结果目录
├── resultAllLongTarget/                # 正链lncRNA结果目录
├── allMergedTranscriptSeq/             # DNA序列目录
└── allMinusLongTargetList              # Strand mapping文件
```

## 🚀 快速开始

### 1. 最简单的用法

```bash
python3 analyze_peaks_binding_affinity.py \
    resultAllLongTarget/CATG00000000034.1 \
    60 \
    output.txt \
    --target-dna-dir allMergedTranscriptSeq
```

### 2. 推荐用法（使用tree-pickle加速）

```bash
# 先生成目录树索引（一次性操作，耗时约3分钟）
cd marmoset/inputForShenzhen
python3 generate_directory_tree.py scan \
    <data-root>/humanLncAtlas \
    <data-root>/humanLncAtlas_tree.pkl

# 使用pickle运行分析（快100-1000倍）
cd <data-root>/humanLncAtlas
python3 analyze_peaks_binding_affinity.py \
    resultAllLongTarget/CATG00000000034.1 \
    60 \
    output.txt \
    --tree-pickle <data-root>/humanLncAtlas_tree.pkl \
    --target-dna-dir allMergedTranscriptSeq
```

### 3. 使用YAML配置文件（自动设置DNA目录）

⚠️ **重要**：配置文件目前只支持设置 `target_dna_dirs`，其他参数仍需命令行指定。

```bash
# 配置文件自动提供target_dna_dirs，无需手动指定
python3 analyze_peaks_binding_affinity.py \
    resultAllLongTarget/CATG00000000034.1 \
    60 \
    output.txt \
    --config human_lncrna_config.yaml

# 与tree-pickle结合使用（推荐）
python3 analyze_peaks_binding_affinity.py \
    resultAllLongTarget/CATG00000000034.1 \
    60 \
    output.txt \
    --config human_lncrna_config.yaml \
    --tree-pickle <data-root>/humanLncAtlas_tree.pkl
```

### 4. Strand-Based路由（同时使用minus和all目录）

```bash
python3 analyze_peaks_binding_affinity.py \
    resultMinusLongTarget \
    60 \
    output.txt \
    --extra-result-dirs resultAllLongTarget \
    --tree-pickle <data-root>/humanLncAtlas_tree.pkl \
    --target-dna-dir allMergedTranscriptSeq
```

## ⚙️ 主要参数

| 参数 | 说明 | 示例 |
|------|------|------|
| `result_directory` | 结果目录路径 | `resultAllLongTarget/CATG00000000034.1` |
| `threshold` | Binding Affinity阈值 | `60` |
| `output_file` | 输出文件路径 | `output.txt` |
| `--tree-pickle` | 目录树pickle文件 | `<data-root>/humanLncAtlas_tree.pkl` |
| `--overlap-mode` | 重叠检测模式 | `strict` 或 `overlap` |
| `--target-dna-dir` | DNA序列目录 | `allMergedTranscriptSeq` |
| `--config` | YAML配置文件 | `human_lncrna_config.yaml` |
| `--extra-result-dirs` | 额外结果目录 | `resultAllLongTarget` |

## 🎯 Overlap Mode说明

### Strict模式（默认）
- 结合位点必须**完全包含**在peak内
- 更严格，结果更可靠
- 适合高置信度分析

### Overlap模式
- 结合位点与peak**任何重叠**即可
- 更宽松，能找到更多结果
- 适合初步筛选

**示例**：阈值60时，overlap模式通常能找到2倍于strict模式的结果。

```bash
# Strict模式
python3 analyze_peaks_binding_affinity.py result/ 60 strict.txt --overlap-mode strict
# 结果: 33个

# Overlap模式
python3 analyze_peaks_binding_affinity.py result/ 60 overlap.txt --overlap-mode overlap
# 结果: 67个（+103%）
```

## 📊 输出格式

TSV格式，包含21列：

```
Species  LncRNA_ID  File  Target_Gene_ID  Target_Region_Start  Target_Region_End
Total_Sites  Kept_Sites  Num_Peaks  Best_Peak_Num  Best_Avg_BA  Best_Num_Sites
Best_Peak_Chr  Best_Peak_Start  Best_Peak_End  Best_Site_BA
LncRNA_Start  LncRNA_End  DNA_Start  DNA_End  LncRNA_Sequence  DNA_Sequence
```

### 查看结果

```bash
# 格式化显示
head -10 output.txt | column -t -s $'\t'

# 检查DNA序列提取成功率
awk -F'\t' 'BEGIN{none=0; found=0} NR>1 {
    if ($20 == "None" || $20 == "NA" || length($20) == 0) none++;
    else found++
} END {
    print "DNA序列找到:", found;
    print "DNA序列缺失:", none;
    if (found+none > 0) printf "成功率: %.1f%%\n", (found/(found+none)*100)
}' output.txt
```

## ⚡ 性能优化

### Tree-Pickle的巨大优势

| 数据规模 | 不使用pickle | 使用pickle | 加速比 |
|---------|-------------|-----------|--------|
| 文件数：10,591,285 | 每次查找30-60秒 | 加载一次56秒，后续<0.1秒 | **300-1000x** |
| 总索引时间 | 每次运行都扫描 | 一次性扫描199秒 | 重复运行时无限大 |

**结论**：对于humanLncAtlas这样的超大数据集，tree-pickle是**必需的**，不是可选的！

## 🔍 Strand-Based路由机制

### 工作原理

1. **读取** `allMinusLongTargetList` 获取每个(lncRNA, target gene)的链方向
2. **路由规则**：
   - 负链（-）→ `resultMinusLongTarget`
   - 正链（+）→ `resultAllLongTarget`
3. **自动切换**：即使在resultAllLongTarget目录中处理，遇到负链pair也会自动到resultMinusLongTarget查找

### 启用条件

必须同时满足：
1. ✅ 提供两个目录：`resultMinusLongTarget` 和 `resultAllLongTarget`
2. ✅ `allMinusLongTargetList` 文件存在
3. ✅ 目录名包含 `resultMinusLongTarget` 或 `resultAllLongTarget`

```bash
# ✅ 正确：启用strand-based路由
python3 analyze_peaks_binding_affinity.py \
    resultMinusLongTarget \
    60 \
    out.txt \
    --extra-result-dirs resultAllLongTarget

# ❌ 错误：只提供一个目录，不会路由
python3 analyze_peaks_binding_affinity.py \
    resultMinusLongTarget \
    60 \
    out.txt
```

## 📚 更多信息

- **详细使用示例**: 查看 [USAGE_EXAMPLES.md](USAGE_EXAMPLES.md)
- **Tree-Pickle使用指南**: `marmoset/inputForShenzhen/TREE_PICKLE_USAGE.md`
- **目录树生成工具**: `marmoset/inputForShenzhen/DIRECTORY_TREE_GUIDE.md`

## 🐛 常见问题

### Q: 为什么要用tree-pickle？

A: humanLncAtlas有1059万个文件，每次用glob.glob查找要30-60秒。Tree-pickle把整个目录树加载到内存，后续查找<0.1秒。

### Q: overlap和strict模式怎么选？

A:
- 初步分析用overlap（全面）
- 高质量结果用strict（严格）
- 可以两个都跑，然后比较

### Q: 内存不够怎么办？

A:
- Tree-pickle需要约6-9GB内存
- 如果内存不足，不使用`--tree-pickle`参数即可
- 速度会慢，但能正常工作

### Q: 如何处理多个lncRNA？

A: 直接指定包含多个lncRNA的父目录：

```bash
python3 analyze_peaks_binding_affinity.py \
    resultAllLongTarget \
    60 \
    all_lncrnas.txt \
    --tree-pickle <data-root>/humanLncAtlas_tree.pkl
```

## 📝 版本历史

- **v2.0** (2025-11): 添加tree-pickle支持，overlap-mode，bug修复
- **v1.0** (2025-早期): 初始版本，基本功能

## 👥 贡献者

- 温玉坚团队 - 数据生成和分析
- AI辅助开发 - 代码优化和文档

## 📄 许可证

研究使用。
