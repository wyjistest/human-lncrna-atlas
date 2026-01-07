# 快速参考卡片

## 一行命令速查

### 基础分析
```bash
# 单个lncRNA，阈值60
python3 analyze_peaks_binding_affinity.py resultAllLongTarget/CATG00000000034.1 60 out.txt --target-dna-dir allMergedTranscriptSeq
```

### 高性能分析（推荐）
```bash
# 使用tree-pickle加速
python3 analyze_peaks_binding_affinity.py resultAllLongTarget/CATG00000000034.1 60 out.txt --tree-pickle <data-root>/humanLncAtlas_tree.pkl --target-dna-dir allMergedTranscriptSeq
```

### Overlap模式
```bash
# 更宽松的匹配，找到更多结果
python3 analyze_peaks_binding_affinity.py resultAllLongTarget/CATG00000000034.1 60 out.txt --overlap-mode overlap --tree-pickle <data-root>/humanLncAtlas_tree.pkl
```

### Strand-Based路由
```bash
# 自动根据链方向选择minus或all目录
python3 analyze_peaks_binding_affinity.py resultMinusLongTarget 60 out.txt --extra-result-dirs resultAllLongTarget --tree-pickle <data-root>/humanLncAtlas_tree.pkl --target-dna-dir allMergedTranscriptSeq
```

### 使用配置文件
```bash
# 所有配置写在YAML里
python3 analyze_peaks_binding_affinity.py resultAllLongTarget/CATG00000000034.1 60 out.txt --config human_lncrna_config.yaml
```

### 生成Tree-Pickle（一次性操作）
```bash
cd marmoset/inputForShenzhen
python3 generate_directory_tree.py scan <data-root>/humanLncAtlas <data-root>/humanLncAtlas_tree.pkl
```

## 常用数据分析命令

### 查看结果
```bash
# 格式化显示前10行
head -10 output.txt | column -t -s $'\t'

# 统计有效结果数
wc -l output.txt

# 查看最高Binding Affinity的10个
awk -F'\t' 'NR>1 {print $11}' output.txt | sort -rn | head -10
```

### 检查质量
```bash
# DNA序列提取成功率
awk -F'\t' 'BEGIN{none=0; found=0} NR>1 {if ($20 == "None" || $20 == "NA" || length($20) == 0) none++; else found++} END {print "成功率:", (found/(found+none)*100)"%"}' output.txt

# 总结合位点数
awk -F'\t' 'NR>1 {sum+=$7} END {print "总位点数:", sum}' output.txt
```

### 过滤结果
```bash
# 只保留Binding Affinity >= 80的
awk -F'\t' 'NR==1 || $11>=80' output.txt > high_ba.txt

# 只保留包含DNA序列的
awk -F'\t' 'NR==1 || ($20!="None" && $20!="NA" && length($20)>0)' output.txt > with_seq.txt
```

## 参数速查表

| 参数 | 简写 | 说明 | 默认值 |
|------|------|------|--------|
| result_directory | - | 结果目录 | 必需 |
| threshold | - | BA阈值 | 0 |
| output_file | - | 输出文件 | batch_results.txt |
| --tree-pickle | - | pickle文件路径 | 无（不使用） |
| --overlap-mode | - | strict/overlap | strict |
| --target-dna-dir | - | DNA序列目录 | 自动检测 |
| --config | - | YAML配置文件 | 无 |
| --extra-result-dirs | - | 额外目录（逗号分隔） | 无 |

## 性能对比

| 场景 | 不用pickle | 用pickle | 提升 |
|------|-----------|---------|------|
| 文件查找 | 30-60秒/次 | <0.1秒/次 | **300-1000x** |
| 单lncRNA分析 | 1分45秒 | 1分5秒 | **38%** |
| 批量分析（10个） | 17分30秒 | 10分50秒 | **38%** |

## Overlap Mode效果

| 阈值 | Strict | Overlap | 增加 |
|------|--------|---------|------|
| BA≥50 | 45个 | 89个 | +98% |
| BA≥60 | 33个 | 67个 | +103% |
| BA≥70 | 22个 | 42个 | +91% |

## 目录结构速查

```
humanLncAtlas/
├── resultMinusLongTarget/          # 负链结果
│   ├── CATG00000000034.1/
│   │   ├── *-TFOsorted             # TFO结果
│   │   └── *-class1                # Class1文件
│   └── ...
├── resultAllLongTarget/            # 正链结果
│   └── ...
├── allMergedTranscriptSeq/         # DNA序列
│   ├── ENSG00000123456.6.fa
│   └── ...
└── allMinusLongTargetList          # Strand mapping
```

## 常见错误速查

| 错误 | 原因 | 解决 |
|------|------|------|
| FileNotFoundError: *.fa | DNA文件找不到 | 检查--target-dna-dir路径 |
| MemoryError | 内存不足 | 不使用--tree-pickle |
| No valid result directories | 路径错误 | 检查目录是否存在 |
| DNA sequences None | DNA cache未建立 | 确保提供target_dna_dir |

## 文件大小参考

| 文件 | 大小 | 说明 |
|------|------|------|
| humanLncAtlas_tree.pkl | 2.87 GB | 目录树索引 |
| 单个.fa文件 | ~50-500 KB | DNA序列 |
| 单个TFOsorted | ~100 KB-10 MB | TFO结果 |
| 输出文件 | 变化 | 约每结果1KB |

## 快速决策树

```
需要分析lncRNA？
├─ 是单个lncRNA？
│  ├─ 是 → 基础命令 + --target-dna-dir
│  └─ 否 → 批量处理 + --tree-pickle
├─ 有strand信息？
│  ├─ 是 → 使用 --extra-result-dirs
│  └─ 否 → 单目录分析
├─ 需要更多结果？
│  ├─ 是 → --overlap-mode overlap
│  └─ 否 → 使用默认strict模式
└─ 重复运行？
   ├─ 是 → 必须使用 --tree-pickle
   └─ 否 → 可选使用
```

## 最佳实践

1. ✅ **首次分析**：用overlap模式快速筛选
2. ✅ **精细分析**：用strict模式获取高质量结果
3. ✅ **大规模处理**：必须使用tree-pickle
4. ✅ **定期更新**：数据变化后重新生成pickle
5. ✅ **保留中间结果**：输出文件名包含参数信息

示例文件命名：
```bash
human_BA60_strict_20251115.txt
human_BA60_overlap_20251115.txt
human_minus_all_BA50_20251115.txt
```
