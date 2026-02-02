> [!IMPORTANT]
> 本文档为历史记录/会话纪要（可能包含 TODO、checkbox、Mock 等信号，不代表当前实现/待办）。
> 当前真实状态与下一步请以 `docs/CURRENT_STATUS.md` 为准。

# YAML配置文件说明

## ✅ 配置文件支持什么

### 当前支持的功能

配置文件**只支持一个功能**：设置DNA序列查找目录

```yaml
species:
  human:
    target_dna_dirs:
      - <data-root>/humanLncAtlas/allMergedTranscriptSeq
```

**作用**：
- 脚本会自动从这个目录查找DNA序列文件
- 等效于命令行的 `--target-dna-dir allMergedTranscriptSeq`
- 但更灵活：可以指定多个目录，按顺序搜索

**优势**：
- ✅ 不需要每次手动指定DNA目录
- ✅ 可以配置多个备用目录
- ✅ 便于团队共享配置

## ❌ 配置文件不支持什么

以下参数**不能**通过YAML配置，必须使用命令行：

| 参数 | 命令行写法 | 说明 |
|------|-----------|------|
| Tree-Pickle路径 | `--tree-pickle <path>` | 性能优化必需 |
| Overlap模式 | `--overlap-mode <mode>` | strict或overlap |
| 额外结果目录 | `--extra-result-dirs <dirs>` | Strand-based路由需要 |
| 手动DNA目录 | `--target-dna-dir <dir>` | 覆盖YAML配置 |

## 📝 实际使用示例

### 示例1：只用配置文件

```bash
# 配置文件提供DNA目录
python3 analyze_peaks_binding_affinity.py \
    resultAllLongTarget/CATG00000000034.1 \
    60 \
    output.txt \
    --config human_lncrna_config.yaml
```

**等效于**：
```bash
python3 analyze_peaks_binding_affinity.py \
    resultAllLongTarget/CATG00000000034.1 \
    60 \
    output.txt \
    --target-dna-dir <data-root>/humanLncAtlas/allMergedTranscriptSeq
```

### 示例2：配置文件 + 性能优化

```bash
# 配置文件 + tree-pickle（推荐）
python3 analyze_peaks_binding_affinity.py \
    resultAllLongTarget/CATG00000000034.1 \
    60 \
    output.txt \
    --config human_lncrna_config.yaml \
    --tree-pickle <data-root>/humanLncAtlas_tree.pkl
```

### 示例3：配置文件 + 所有选项

```bash
# 完整配置（生产环境推荐）
python3 analyze_peaks_binding_affinity.py \
    resultMinusLongTarget \
    60 \
    output.txt \
    --config human_lncrna_config.yaml \
    --extra-result-dirs resultAllLongTarget \
    --tree-pickle <data-root>/humanLncAtlas_tree.pkl \
    --overlap-mode overlap
```

## 🤔 为什么不支持更多配置？

当前版本的脚本设计为：
- **配置文件**：管理数据路径（DNA序列目录）
- **命令行参数**：控制分析行为（阈值、模式、优化选项）

这样设计的原因：
1. ✅ 数据路径相对稳定，适合写在配置文件
2. ✅ 分析参数经常变化，命令行更灵活
3. ✅ 避免配置文件过于复杂
4. ✅ 命令行参数一目了然

## 📊 配置文件 vs 命令行

| 场景 | 推荐方式 | 原因 |
|------|---------|------|
| DNA目录路径 | ✅ 配置文件 | 路径固定，团队共享 |
| Threshold值 | ✅ 命令行 | 每次分析可能不同 |
| Tree-Pickle | ✅ 命令行 | 可选的性能优化 |
| Overlap模式 | ✅ 命令行 | 分析策略选择 |
| 结果目录 | ✅ 命令行 | 每次运行不同 |

## 🔮 未来可能支持的功能

如果有需求，可以扩展配置文件支持：

```yaml
# 未来可能的配置（当前不支持）
settings:
  tree_pickle_path: <data-root>/humanLncAtlas_tree.pkl  # 自动加载pickle
  default_overlap_mode: strict                     # 默认模式
  default_threshold: 60                            # 默认阈值

strand_routing:
  enabled: true                                    # 自动启用路由
  minus_dir: resultMinusLongTarget                 # 负链目录
  all_dir: resultAllLongTarget                     # 正链目录
```

**但目前这些都不起作用！** 如需这些功能，必须使用命令行参数。

## ✅ 最佳实践

### 推荐的工作流程

1. **团队共享配置文件**
   ```bash
   # 团队所有人使用相同的human_lncrna_config.yaml
   git commit human_lncrna_config.yaml
   ```

2. **个人使用命令行定制分析**
   ```bash
   # 每个人根据需要调整参数
   python3 analyze_peaks_binding_affinity.py \
       resultAllLongTarget/CATG00000000034.1 \
       $MY_THRESHOLD \
       $MY_OUTPUT \
       --config human_lncrna_config.yaml \
       --tree-pickle $PICKLE_FILE \
       --overlap-mode $MY_MODE
   ```

3. **脚本化批量处理**
   ```bash
   #!/bin/bash
   # 批量处理脚本
   CONFIG=<data-root>/humanLncAtlas/human_lncrna_config.yaml
   PICKLE=<data-root>/humanLncAtlas_tree.pkl

   for threshold in 50 60 70; do
       for mode in strict overlap; do
           python3 analyze_peaks_binding_affinity.py \
               resultAllLongTarget \
               $threshold \
               output_${threshold}_${mode}.txt \
               --config $CONFIG \
               --tree-pickle $PICKLE \
               --overlap-mode $mode
       done
   done
   ```

## 💡 总结

**记住三点**：

1. ✅ 配置文件只管DNA目录路径
2. ⚠️ 其他参数都要命令行指定
3. 🚀 这是设计特性，不是bug

如有疑问，查看配置文件顶部的注释！
