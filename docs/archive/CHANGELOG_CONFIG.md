> [!IMPORTANT]
> 本文档为历史记录/会话纪要（可能包含 TODO、checkbox、Mock 等信号，不代表当前实现/待办）。
> 当前真实状态与下一步请以 `docs/CURRENT_STATUS.md` 为准。

# 配置文件功能澄清 - 更新日志

## 2025-11-15：诚实化配置文件

### 问题
之前创建的 `human_lncrna_config.yaml` 包含了很多看起来支持的配置项，但实际上脚本并不读取它们，导致用户误解。

### 修复内容

#### 1. ✅ 更新配置文件
- **文件**: `human_lncrna_config.yaml`
- **修改**: 移除所有不支持的配置项
- **保留**: 仅保留实际支持的 `species.target_dna_dirs`
- **添加**: 详细注释说明限制和替代方案

#### 2. ✅ 创建配置文件说明文档
- **文件**: `CONFIG_FILE_EXPLAINED.md`
- **内容**:
  - 配置文件支持什么（只有target_dna_dirs）
  - 配置文件不支持什么（所有其他参数）
  - 实际使用示例
  - 命令行参数对照表
  - 最佳实践

#### 3. ✅ 更新主文档
- **文件**: `README.md`
- **修改**: 在YAML配置文件部分添加警告说明
- **添加**: 示例命令展示如何结合配置文件和命令行参数

#### 4. ✅ 更新文档索引
- **文件**: `DOCUMENTATION_INDEX.md`
- **修改**: 添加 `CONFIG_FILE_EXPLAINED.md` 的索引
- **强调**: 配置文件说明文档的重要性

### 实际支持的功能

#### ✅ 配置文件可以做的事：

```yaml
species:
  human:
    target_dna_dirs:
      - <data-root>/humanLncAtlas/allMergedTranscriptSeq
```

**作用**: 自动设置DNA序列目录，相当于 `--target-dna-dir`

#### ❌ 配置文件不能做的事：

以下参数**必须**通过命令行指定：
- `--tree-pickle`: Tree-Pickle文件路径
- `--overlap-mode`: Overlap检测模式
- `--extra-result-dirs`: 额外结果目录

### 正确使用方法

```bash
# ✅ 正确：配置文件 + 命令行参数
python3 analyze_peaks_binding_affinity.py \
    resultMinusLongTarget \
    60 \
    output.txt \
    --config human_lncrna_config.yaml \
    --tree-pickle <data-root>/humanLncAtlas_tree.pkl \
    --overlap-mode overlap \
    --extra-result-dirs resultAllLongTarget

# ❌ 错误：期望配置文件提供所有设置
python3 analyze_peaks_binding_affinity.py \
    resultMinusLongTarget \
    60 \
    output.txt \
    --config human_lncrna_config.yaml
    # 缺少 tree-pickle, overlap-mode, extra-result-dirs
```

### 为什么这样设计

1. **数据路径 vs 分析参数**
   - 数据路径（DNA目录）相对稳定 → 适合配置文件
   - 分析参数（阈值、模式）经常变化 → 适合命令行

2. **灵活性**
   - 命令行参数一目了然
   - 便于脚本化和批量处理
   - 避免配置文件过于复杂

3. **清晰性**
   - 用户明确知道每个参数的来源
   - 减少"隐式配置"导致的困惑

### 文档更新清单

- [x] `human_lncrna_config.yaml` - 诚实化配置文件
- [x] `CONFIG_FILE_EXPLAINED.md` - 新建详细说明
- [x] `README.md` - 更新YAML部分
- [x] `DOCUMENTATION_INDEX.md` - 添加新文档索引
- [x] `CHANGELOG_CONFIG.md` - 本文件

### 测试验证

```bash
# 测试配置文件加载
✅ YAML配置文件加载成功
✅ 只包含 species.target_dna_dirs
✅ 不包含 settings, strand_routing

# 测试实际运行
✅ 配置文件正确提供DNA目录
✅ 成功索引88704个DNA文件
✅ 成功处理376个文件对
✅ 输出33个有效结果
```

### 用户影响

**对新用户**:
- ✅ 配置文件功能清晰明了
- ✅ 不会产生虚假期待
- ✅ 有详细文档指导

**对现有用户**:
- ⚠️ 如果之前按旧YAML使用，需要更新命令行
- ✅ 实际功能没有变化（之前也不支持那些配置）
- ✅ 只需添加必要的命令行参数

### 后续改进建议

如果未来需要扩展配置文件功能，可以考虑添加：
1. `settings.tree_pickle_path` - 自动加载tree-pickle
2. `settings.default_overlap_mode` - 默认overlap模式
3. `strand_routing.auto_enable` - 自动启用strand路由

但当前版本保持简单明了更好。

### 参考文档

查看以下文档了解详情：
- [CONFIG_FILE_EXPLAINED.md](CONFIG_FILE_EXPLAINED.md) - 配置文件详细说明
- [human_lncrna_config.yaml](human_lncrna_config.yaml) - 更新后的配置文件
- [README.md](README.md) - 主文档
