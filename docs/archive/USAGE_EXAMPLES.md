> [!IMPORTANT]
> 本文档为历史记录/会话纪要（可能包含 TODO、checkbox、Mock 等信号，不代表当前实现/待办）。
> 当前真实状态与下一步请以 `docs/CURRENT_STATUS.md` 为准。

# Human lncRNA Analysis - 使用示例

## 快速开始

### 1. 基本用法（不使用配置文件）

```bash
# 分析单个lncRNA目录
python3 analyze_peaks_binding_affinity.py \
    resultAllLongTarget/CATG00000000034.1 \
    60 \
    output.txt \
    --target-dna-dir allMergedTranscriptSeq
```

### 2. 使用YAML配置文件

```bash
# 使用配置文件（自动读取target_dna_dirs）
python3 analyze_peaks_binding_affinity.py \
    resultAllLongTarget/CATG00000000034.1 \
    60 \
    output.txt \
    --config human_lncrna_config.yaml
```

### 3. 使用Tree-Pickle加速（推荐用于大规模数据）

```bash
# 先生成目录树索引（一次性操作）
cd marmoset/inputForShenzhen
python3 generate_directory_tree.py scan \
    <data-root>/humanLncAtlas \
    <data-root>/humanLncAtlas_tree.pkl

# 使用pickle文件运行分析（快100-1000倍）
python3 analyze_peaks_binding_affinity.py \
    resultAllLongTarget/CATG00000000034.1 \
    60 \
    output_with_pickle.txt \
    --tree-pickle <data-root>/humanLncAtlas_tree.pkl \
    --target-dna-dir allMergedTranscriptSeq
```

### 4. 使用Overlap模式（更宽松的peak-site匹配）

```bash
# Strict模式（默认）：结合位点必须完全在peak内
python3 analyze_peaks_binding_affinity.py \
    resultAllLongTarget/CATG00000000034.1 \
    60 \
    strict_output.txt \
    --overlap-mode strict \
    --tree-pickle <data-root>/humanLncAtlas_tree.pkl

# Overlap模式：任何重叠都算（通常能找到更多结果）
python3 analyze_peaks_binding_affinity.py \
    resultAllLongTarget/CATG00000000034.1 \
    60 \
    overlap_output.txt \
    --overlap-mode overlap \
    --tree-pickle <data-root>/humanLncAtlas_tree.pkl
```

### 5. Strand-Based目录路由（Human lncRNA特有）

```bash
# 同时使用minus和all目录，自动根据链方向路由
python3 analyze_peaks_binding_affinity.py \
    resultMinusLongTarget \
    60 \
    strand_based_output.txt \
    --extra-result-dirs resultAllLongTarget \
    --tree-pickle <data-root>/humanLncAtlas_tree.pkl \
    --target-dna-dir allMergedTranscriptSeq

# 注意：
# - 负链（-）的pair会使用resultMinusLongTarget
# - 正链（+）的pair会使用resultAllLongTarget
# - 必须同时提供两个目录才能启用自动路由
```

## 完整示例（所有选项）

```bash
# 生产环境推荐配置
python3 analyze_peaks_binding_affinity.py \
    resultMinusLongTarget \
    60 \
    human_lncrna_BA60_complete.txt \
    --extra-result-dirs resultAllLongTarget \
    --tree-pickle <data-root>/humanLncAtlas_tree.pkl \
    --overlap-mode overlap \
    --target-dna-dir allMergedTranscriptSeq \
    --config human_lncrna_config.yaml
```

## 性能对比

### 不使用Tree-Pickle

```bash
# 第一次运行
$ time python3 analyze_peaks_binding_affinity.py resultAllLongTarget/CATG00000000034.1 60 out.txt

正在构建 DNA 文件索引缓存...
DNA 文件索引完成，共索引 88704 个文件    # ← 耗时约30-60秒

处理完成，共处理 376 个文件对
real    1m45s
```

### 使用Tree-Pickle

```bash
# 使用pickle后
$ time python3 analyze_peaks_binding_affinity.py resultAllLongTarget/CATG00000000034.1 60 out.txt \
    --tree-pickle <data-root>/humanLncAtlas_tree.pkl

正在加载目录树索引: <data-root>/humanLncAtlas_tree.pkl
✓ 目录树索引加载成功，耗时: 56.04 秒    # ← 一次性加载
DNA 文件索引完成，共索引 88704 个文件    # ← 从内存查找，<1秒

处理完成，共处理 376 个文件对
real    1m5s    # 加载pickle后，后续查找几乎不花时间
```

### 重复运行时的优势

```bash
# 不使用pickle：每次都要扫描文件系统
运行1: 1m45s
运行2: 1m45s
运行3: 1m45s
总计: 5m15s

# 使用pickle：首次加载后，后续极快
运行1: 1m5s (包含56秒加载)
运行2: 1m5s
运行3: 1m5s
总计: 3m15s

节省: 2分钟 (38%)
```

## Overlap模式效果对比

```bash
# Strict模式（完全包含）
$ python3 analyze_peaks_binding_affinity.py \
    resultAllLongTarget/CATG00000000034.1 60 strict.txt --overlap-mode strict

有效结果数: 33

# Overlap模式（任何重叠）
$ python3 analyze_peaks_binding_affinity.py \
    resultAllLongTarget/CATG00000000034.1 60 overlap.txt --overlap-mode overlap

有效结果数: 67    # 增加了103%

# 建议：
# - 初步分析使用overlap模式（更全面）
# - 高置信度结果使用strict模式（更严格）
```

## 批量处理多个lncRNA

```bash
# 方式1：直接指定包含多个lncRNA的目录
python3 analyze_peaks_binding_affinity.py \
    resultAllLongTarget \
    60 \
    all_lncrna_output.txt \
    --tree-pickle <data-root>/humanLncAtlas_tree.pkl \
    --target-dna-dir allMergedTranscriptSeq

# 方式2：使用strand-based routing处理所有lncRNA
python3 analyze_peaks_binding_affinity.py \
    resultMinusLongTarget \
    60 \
    all_strand_based_output.txt \
    --extra-result-dirs resultAllLongTarget \
    --tree-pickle <data-root>/humanLncAtlas_tree.pkl \
    --target-dna-dir allMergedTranscriptSeq
```

## 输出文件格式

输出是TSV格式，包含以下列：

```
Species  LncRNA_ID  File  Target_Gene_ID  Target_Region_Start  Target_Region_End
Total_Sites  Kept_Sites  Num_Peaks  Best_Peak_Num  Best_Avg_BA  Best_Num_Sites
Best_Peak_Chr  Best_Peak_Start  Best_Peak_End  Best_Site_BA
LncRNA_Start  LncRNA_End  DNA_Start  DNA_End  LncRNA_Sequence  DNA_Sequence
```

### 查看结果示例

```bash
# 查看前10行
head -10 output.txt | column -t -s $'\t'

# 统计有效结果
awk -F'\t' 'NR>1 {sum+=$7} END {print "总结合位点数:", sum}' output.txt

# 查看最佳Binding Affinity
awk -F'\t' 'NR>1 {print $11}' output.txt | sort -rn | head -10
```

## 常见问题

### Q1: DNA序列提取失败怎么办？

```bash
# 检查成功率
awk -F'\t' 'BEGIN{none=0; found=0} NR>1 {
    if ($20 == "None" || $20 == "NA" || length($20) == 0) none++;
    else found++
} END {
    print "DNA序列找到:", found;
    print "DNA序列缺失:", none;
    if (found+none > 0) printf "成功率: %.1f%%\n", (found/(found+none)*100)
}' output.txt
```

### Q2: 如何只处理特定的lncRNA？

```bash
# 创建符号链接到临时目录
mkdir -p temp_analysis
cd temp_analysis
ln -s <data-root>/humanLncAtlas/resultAllLongTarget/CATG00000000034.1 .
ln -s <data-root>/humanLncAtlas/resultAllLongTarget/CATG00000000072.1 .

# 运行分析
python3 analyze_peaks_binding_affinity.py \
    . \
    60 \
    selected_lncrnas.txt \
    --tree-pickle <data-root>/humanLncAtlas_tree.pkl
```

### Q3: 内存不足怎么办？

```bash
# 不使用tree-pickle（会慢但内存占用小）
python3 analyze_peaks_binding_affinity.py \
    resultAllLongTarget/CATG00000000034.1 \
    60 \
    output.txt \
    --target-dna-dir allMergedTranscriptSeq
```

## 下一步

1. 查看生成的输出文件
2. 使用R或Python进行下游分析
3. 可视化最佳binding sites
4. 与实验数据交叉验证
