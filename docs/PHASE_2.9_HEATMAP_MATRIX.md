# Phase 2.9: 热图矩阵可视化功能

> **完成时间**: 2025-12-07
> **版本**: Phase 2.9
> **功能**: 多细胞系 × 多 Marks 热图矩阵可视化

---

## 📋 功能概述

新增"热图矩阵模式"，支持在单个视图中同时对比多个细胞系和多个组蛋白修饰的表观遗传学特征。

### 核心价值

1. **多维度可视化**: 一眼看出不同细胞系在多个 marks 上的差异模式
2. **模式识别**: 识别细胞类型特异性的组蛋白修饰组合
3. **数据完整性**: 清晰标识缺失数据（某些细胞系-Mark组合无数据）

---

## 🔧 技术实现

### 后端 API

**新增端点**:
```
GET /api/v1/features/chipseq/genes/{gene_id}/heatmap-matrix
```

**参数**:
| 参数 | 类型 | 必需 | 默认值 | 说明 |
|------|------|------|--------|------|
| `marks` | string | 是 | - | 逗号分隔的 mark 列表（1-8个），如 `H3K27me3,H3K4me3,H3K27ac` |
| `cell_types` | string | 是 | - | 逗号分隔的细胞系列表（1-10个），如 `K562,HepG2,GM12878,H1-hESC` |
| `metric` | enum | 否 | `median_fold_enrichment` | 矩阵值类型: `median_fold_enrichment`, `peak_count`, `total_coverage_bp`, `avg_signal` |
| `flanking` | int | 否 | 10000 | 基因侧翼区域（bp） |
| `max_qvalue` | float | 否 | 0.05 | Q-value 阈值 |
| `include_details` | bool | 否 | true | 是否包含详细统计 |

**响应结构**:
```json
{
  "gene_id": 17276,
  "gene_ensembl_id": "CATG00000000011.1",
  "cell_types": ["K562", "HepG2", "GM12878", "H1-hESC"],
  "marks": ["H3K27me3", "H3K4me3", "H3K27ac", "H3K4me1", "H3K36me3", "H3K9me3"],
  "metric": "median_fold_enrichment",
  "matrix": [
    [13.17, 41.50, 35.73, 8.16, 4.45, 1.58],
    [4.09, null, null, null, null, null],
    [null, null, null, null, null, null],
    [null, null, null, null, null, null]
  ],
  "details": {
    "K562": {
      "H3K27me3": {"median_fold_enrichment": 13.17, "peak_count": 1, "total_coverage_bp": 112},
      "H3K4me3": {"median_fold_enrichment": 41.50, "peak_count": 1, "total_coverage_bp": 4945}
    }
  },
  "missing_combinations": [...],
  "total_combinations": 24,
  "valid_combinations": 7
}
```

---

### 前端组件

**新增组件**: `CellLineHeatmapMatrix.tsx` (~350 行)

**功能特性**:
1. **ECharts 矩阵热图**
   - X 轴: Histone marks（显示 shortName）
   - Y 轴: 细胞系（带颜色指示器）
   - 热图值: 可切换指标（富集倍数/峰值数/覆盖度/信号）

2. **交互式 Tooltip**
   - 显示细胞系名称、Mark 类型
   - 显示指标值和额外统计（peaks, coverage）
   - 双语支持（中文/英文）

3. **指标切换**
   - Segmented 控件（4个选项）
   - 不同指标使用不同色阶（蓝/绿/粉/橙）

4. **统计面板**
   - 总组合数
   - 有效组合数（百分比）
   - 细胞系数量
   - Marks 数量
   - 缺失数据列表

5. **缺失数据处理**
   - 空白格子表示无数据
   - Tag 列表显示所有缺失组合

**集成位置**: ChIPSeqPeaksTable 对比模式，新增 "矩阵视图" Tab

---

## 📊 数据示例

### 示例 1: K562 完整数据（6 marks）

```
K562 细胞系在基因 CATG00000000011.1 的表观遗传模式:
  H3K27me3: 13.17x  (抑制性修饰 - 中等)
  H3K4me3:  41.50x  (活性启动子 - 强)
  H3K27ac:  35.73x  (活性增强子 - 强)
  H3K4me1:   8.16x  (增强子标记 - 中等)
  H3K36me3:  4.45x  (转录延伸 - 弱)
  H3K9me3:   1.58x  (异染色质 - 极弱)
```

**科学解读**: K562 在该基因显示活性表观遗传状态（H3K4me3 和 H3K27ac 高富集），同时存在一定的抑制性修饰（H3K27me3），可能处于平衡状态。

### 示例 2: HepG2 部分数据

```
HepG2 细胞系:
  H3K27me3: 4.09x   (抑制性修饰 - 弱)
  其他 marks: 无数据
```

**科学解读**: HepG2 在该基因的 ChIP-seq 数据不完整，仅有 H3K27me3 数据，表现为较弱的抑制性修饰。

---

## ✅ 测试覆盖

### 后端 API 测试

**TestHeatmapMatrix** (12 tests):
- `test_matrix_2x2` - 2×2 矩阵基本功能
- `test_matrix_4x4` - 4×4 矩阵
- `test_matrix_with_missing_data` - 缺失数据处理
- `test_matrix_response_structure` - 响应结构验证
- `test_matrix_different_metrics` - 不同指标测试
- `test_matrix_with_details` - 详细统计字段
- `test_matrix_parameter_limits_marks` - Marks 数量限制
- `test_matrix_parameter_limits_cell_types` - 细胞系数量限制
- `test_matrix_invalid_gene` - 无效基因处理
- `test_matrix_invalid_metric` - 无效指标处理
- `test_matrix_with_flanking` - 侧翼区域参数
- `test_matrix_single_mark_single_cell` - 1×1 矩阵（退化情况）

**测试结果**: ✅ 12/12 passed in 2.49s

### 性能测试

**TestHeatmapMatrixPerformance** (8 tests):
- `test_2x2_matrix_response_time` - 2×2 矩阵 ~25ms ✅
- `test_4x4_matrix_response_time` - 4×4 矩阵 ~28ms ✅
- `test_4x4_matrix_with_details` - 带详情 ~27ms ✅
- `test_different_metrics_performance` - 各指标 ~26ms ✅
- `test_repeated_requests_consistency` - 稳定性测试 ✅
- `test_scaling_with_marks` - Marks 扩展性测试 ✅
- `test_scaling_with_cell_types` - 细胞系扩展性测试 ✅
- `test_matrix_vs_compare_cell_lines` - 与现有端点性能对比 ✅

**性能汇总**:
| 矩阵大小 | 响应时间 | 性能目标 | 状态 |
|---------|---------|---------|------|
| 2×2 | ~25ms | <200ms | ✅ 优秀 |
| 4×4 | ~28ms | <300ms | ✅ 优秀 |
| 4×6 | ~30ms | <400ms | ✅ 优秀 |

---

## 🎨 UI/UX 设计

### 矩阵热图视觉设计

**热图模式**:
```
         H3K27me3  H3K4me3  H3K27ac  H3K4me1  H3K36me3  H3K9me3
K562      [深蓝]   [深蓝]   [深蓝]   [中蓝]   [浅蓝]   [极浅]
HepG2     [浅蓝]   [空白]   [空白]   [空白]   [空白]   [空白]
GM12878   [空白]   [空白]   [空白]   [空白]   [空白]   [空白]
H1-hESC   [空白]   [空白]   [空白]   [空白]   [空白]   [空白]

色阶: 浅蓝(0x) ═════► 深蓝(50x)
```

**颜色方案**:
| 指标 | 色阶 | 说明 |
|------|------|------|
| 富集倍数 | 浅蓝 → 深蓝 | `#f0f5ff` → `#003a8c` |
| 峰值数量 | 浅绿 → 深绿 | `#f6ffed` → `#135200` |
| 覆盖度 | 浅粉 → 深粉 | `#fff0f6` → `#9e1068` |
| 平均信号 | 浅橙 → 深橙 | `#fff7e6` → `#ad4e00` |

### Tab 导航结构

```
ChIP-seq 对比模式:
  ├─ 合并视图 (现有)
  ├─ 并行对比 (禁用)
  ├─ 统计对比 (现有)
  ├─ 细胞系 (Phase 2.8)
  └─ 矩阵视图 (Phase 2.9) ⭐ NEW
```

---

## 📝 新增文件

### 后端

| 文件 | 行数 | 说明 |
|------|------|------|
| `app/schemas/chipseq.py` | +90 | 2 个新 Schema (CellMarkStats, HeatmapMatrixResponse) |
| `app/routers/chipseq.py` | +210 | 1 个新端点 |
| `tests/test_chipseq_api.py` | +150 | 12 个新测试 |
| `tests/test_heatmap_matrix_performance.py` | +280 | 8 个性能测试 |

### 前端

| 文件 | 行数 | 说明 |
|------|------|------|
| `src/components/ChIPSeqPeaksTable/CellLineHeatmapMatrix.tsx` | 350 | 矩阵热图组件 |
| `src/components/ChIPSeqPeaksTable/index.tsx` | +40 | 集成矩阵视图 Tab |
| `src/api/chipseq.ts` | +20 | API 客户端方法 |
| `src/types/chipseq.ts` | +30 | 类型定义 |
| `src/hooks/useChIPSeq.ts` | +25 | React Query hook |
| `e2e/chipseq-flow.spec.ts` | +80 | E2E 测试 |

---

## 🚀 使用示例

### API 调用

```bash
# 基本用法: 2×2 矩阵
curl "http://localhost:8000/api/v1/features/chipseq/genes/17276/heatmap-matrix?marks=H3K27me3,H3K4me3&cell_types=K562,HepG2&metric=median_fold_enrichment"

# 完整矩阵: 4×6
curl "http://localhost:8000/api/v1/features/chipseq/genes/17276/heatmap-matrix?marks=H3K27me3,H3K4me3,H3K27ac,H3K4me1,H3K36me3,H3K9me3&cell_types=K562,HepG2,GM12878,H1-hESC&metric=peak_count"

# 不包含详情（更快响应）
curl "...&include_details=false"
```

### 前端交互流程

1. 访问基因详情页 → ChIP-seq Tab
2. 点击 "对比细胞系" 按钮
3. 点击 "矩阵视图" Tab
4. 查看热图矩阵（默认显示所有可用的细胞系和 marks）
5. 切换指标（富集倍数 → 峰值数量）
6. Hover 查看详细统计
7. 导出热图为 PNG（toolbox 按钮）

---

## 📈 性能指标

| 指标 | 数值 |
|------|------|
| API 响应时间（2×2） | ~25ms |
| API 响应时间（4×4） | ~28ms |
| API 响应时间（4×6） | ~30ms |
| 前端渲染时间 | ~200ms |
| 指标切换延迟 | <50ms |
| 响应体积（简化） | ~2-4KB |
| 响应体积（详情） | ~8-15KB |

**性能评估**: 远超目标（<300ms），可处理大规模矩阵（如 8×10 = 80 组合）

---

## 💡 科学应用场景

### 场景 1: 识别细胞类型特异性修饰模式

**操作**: 对比 K562 vs HepG2 的 6 个 marks
**预期发现**: K562 显示完整的活性模式（H3K4me3 + H3K27ac 高），HepG2 数据不完整

### 场景 2: 发现 Bivalent Domain 模式

**操作**: 查看热图中 H3K27me3 和 H3K4me3 同时富集的细胞系
**预期发现**: 干细胞（H1-hESC）可能在某些基因同时有这两种修饰

### 场景 3: 比较分化细胞 vs 干细胞

**操作**: 矩阵热图横向对比 K562/HepG2 (分化) vs H1-hESC (干细胞)
**预期发现**: 不同发育阶段的表观遗传特征差异

---

## 🎯 未来改进方向

- [ ] 添加层次聚类（基于 Jaccard 相似性对细胞系排序）
- [ ] 批量基因矩阵（多个基因 × 细胞系 × marks 的三维可视化）
- [ ] 导出为 SVG 格式（矢量图，适合发表）
- [ ] 添加统计显著性检验（细胞系间差异 p-value）

---

## 📚 相关文档

- [Phase 2.8 细胞系对比](./PHASE_2.8_CELL_LINE_COMPARISON.md)
- [ChIP-seq 架构](./PHASE_2.3_CHIPSEQ_ARCHITECTURE.md)
- [测试报告](./PHASE_2.9_TEST_REPORT.md)
