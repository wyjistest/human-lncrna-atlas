> [!IMPORTANT]
> 本文档为历史记录/会话纪要（可能包含 TODO、checkbox、Mock 等信号，不代表当前实现/待办）。
> 当前真实状态与下一步请以 `docs/CURRENT_STATUS.md` 为准。

# 文档索引

## 📚 我该看哪个文档？

### 🚀 我是新手，第一次使用
**推荐**: [README.md](README.md)
- 快速开始指南
- 基本概念介绍
- 最常用的命令

### 📖 我想看详细的使用示例
**推荐**: [USAGE_EXAMPLES.md](USAGE_EXAMPLES.md)
- 20+个实际使用场景
- 参数组合示例
- 性能对比数据
- 问题排查指南

### ⚡ 我需要快速查命令
**推荐**: [QUICK_REFERENCE.md](QUICK_REFERENCE.md)
- 一行命令速查
- 参数速查表
- 常用数据分析命令
- 性能对比表

### ⚙️ 我想用配置文件
**推荐**: [CONFIG_FILE_EXPLAINED.md](CONFIG_FILE_EXPLAINED.md)
- 配置文件功能说明
- 支持和不支持的功能对比
- 实际使用示例

**配置文件**: [human_lncrna_config.yaml](human_lncrna_config.yaml)
- YAML配置模板
- 详细注释说明

### 🔧 我想了解Tree-Pickle
**推荐**: [marmoset/inputForShenzhen/TREE_PICKLE_USAGE.md](marmoset/inputForShenzhen/TREE_PICKLE_USAGE.md)
- Tree-Pickle原理
- 性能提升数据
- 生成和使用方法

### 📁 我想了解目录树工具
**推荐**: [marmoset/inputForShenzhen/DIRECTORY_TREE_GUIDE.md](marmoset/inputForShenzhen/DIRECTORY_TREE_GUIDE.md)
- generate_directory_tree.py使用指南
- 目录树扫描详解

## 📂 文档结构

```
humanLncAtlas/
├── README.md                      # 主文档 - 从这里开始
├── QUICK_REFERENCE.md             # 快速参考 - 速查命令
├── USAGE_EXAMPLES.md              # 使用示例 - 详细教程
├── CONFIG_FILE_EXPLAINED.md       # ⚠️ 配置文件说明 - 必读！
├── DOCUMENTATION_INDEX.md         # 本文件 - 文档导航
├── human_lncrna_config.yaml       # YAML配置文件
├── analyze_peaks_binding_affinity.py  # 主程序
└── marmoset/inputForShenzhen/
    ├── TREE_PICKLE_USAGE.md       # Tree-Pickle详细说明
    ├── DIRECTORY_TREE_GUIDE.md    # 目录树工具指南
    └── generate_directory_tree.py # 目录树生成工具
```

## 🎯 按任务查找文档

### 任务1: 分析单个lncRNA
1. 阅读 [README.md § 快速开始](README.md#快速开始)
2. 运行命令：
   ```bash
   python3 analyze_peaks_binding_affinity.py \
       resultAllLongTarget/CATG00000000034.1 60 out.txt \
       --target-dna-dir allMergedTranscriptSeq
   ```

### 任务2: 批量处理多个lncRNA
1. 阅读 [USAGE_EXAMPLES.md § 批量处理](USAGE_EXAMPLES.md#批量处理多个lncRNA)
2. 生成tree-pickle（参考 [TREE_PICKLE_USAGE.md](marmoset/inputForShenzhen/TREE_PICKLE_USAGE.md)）
3. 运行批量分析

### 任务3: 使用Strand-Based路由
1. 阅读 [README.md § Strand-Based路由机制](README.md#strand-based路由机制)
2. 阅读 [USAGE_EXAMPLES.md § Strand-Based目录路由](USAGE_EXAMPLES.md#5-strand-based目录路由)
3. 确保同时提供minus和all两个目录

### 任务4: 优化性能
1. 阅读 [README.md § 性能优化](README.md#性能优化)
2. 阅读 [TREE_PICKLE_USAGE.md](marmoset/inputForShenzhen/TREE_PICKLE_USAGE.md)
3. 生成并使用tree-pickle

### 任务5: 理解Overlap Mode
1. 阅读 [README.md § Overlap Mode说明](README.md#overlap-mode说明)
2. 阅读 [USAGE_EXAMPLES.md § Overlap模式效果对比](USAGE_EXAMPLES.md#overlap模式效果对比)
3. 比较strict和overlap的结果

### 任务6: 分析输出结果
1. 阅读 [README.md § 输出格式](README.md#输出格式)
2. 使用 [QUICK_REFERENCE.md § 常用数据分析命令](QUICK_REFERENCE.md#常用数据分析命令)
3. 检查DNA序列提取成功率

### 任务7: 排查问题
1. 查看 [QUICK_REFERENCE.md § 常见错误速查](QUICK_REFERENCE.md#常见错误速查)
2. 查看 [USAGE_EXAMPLES.md § 常见问题](USAGE_EXAMPLES.md#常见问题)
3. 检查参数和路径是否正确

## 📊 文档对比

| 文档 | 长度 | 适合人群 | 阅读时间 |
|------|------|---------|---------|
| README.md | 中 | 所有用户 | 5-10分钟 |
| QUICK_REFERENCE.md | 短 | 有经验用户 | 2-3分钟 |
| USAGE_EXAMPLES.md | 长 | 深度用户 | 15-20分钟 |
| CONFIG_FILE_EXPLAINED.md | 短 | 使用配置文件的用户 | 5分钟 |
| TREE_PICKLE_USAGE.md | 中 | 性能优化需求 | 10-15分钟 |
| DIRECTORY_TREE_GUIDE.md | 中 | 工具开发者 | 10分钟 |

## 🔗 外部资源

- Python文档: https://docs.python.org/3/
- YAML语法: https://yaml.org/
- TFO背景知识: [相关论文链接]
- 数据集说明: [humanLncAtlas数据集文档]

## 💡 学习路径建议

### 初学者路径
```
1. README.md (快速开始)
   ↓
2. 运行第一个命令
   ↓
3. QUICK_REFERENCE.md (查询常用命令)
   ↓
4. USAGE_EXAMPLES.md (学习更多用法)
```

### 进阶用户路径
```
1. TREE_PICKLE_USAGE.md (性能优化)
   ↓
2. 生成tree-pickle
   ↓
3. USAGE_EXAMPLES.md (复杂场景)
   ↓
4. human_lncrna_config.yaml (配置管理)
```

### 开发者路径
```
1. README.md (了解功能)
   ↓
2. DIRECTORY_TREE_GUIDE.md (理解工具)
   ↓
3. analyze_peaks_binding_affinity.py (源代码)
   ↓
4. 贡献代码或报告bug
```

## 📝 文档更新日志

- **2025-11-15**: 创建完整文档集
  - README.md
  - USAGE_EXAMPLES.md
  - QUICK_REFERENCE.md
  - human_lncrna_config.yaml
  - DOCUMENTATION_INDEX.md

## 🤝 反馈与贡献

如果发现文档问题或有改进建议：
1. 直接修改相应的Markdown文件
2. 或者联系维护团队

---

**提示**: 善用 `Ctrl+F` 在文档中搜索关键词！
