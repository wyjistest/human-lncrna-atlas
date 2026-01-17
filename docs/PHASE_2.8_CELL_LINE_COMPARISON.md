# Phase 2.8: 跨细胞系对比分析功能

> **完成时间**: 2025-12-07
> **版本**: Phase 2.8
> **功能**: 跨细胞系 ChIP-seq 对比分析

---

## 📋 功能概述

新增"固定 Mark，对比多细胞系"维度分析，允许用户比较同一组蛋白修饰在不同细胞类型中的表观遗传学差异。

### 核心价值

1. **科学价值**: 识别细胞类型特异性调控元件
2. **保守性分析**: 发现跨细胞系保守的表观遗传标记
3. **分化研究**: 比较分化细胞（K562, HepG2）vs 干细胞（H1-hESC）的染色质状态

---

## 🔧 技术实现

### 后端 API

**新增端点**:
```
GET /api/v1/features/chipseq/genes/{gene_id}/compare-cell-lines
```

**参数**:
| 参数 | 类型 | 必需 | 默认值 | 说明 |
|------|------|------|--------|------|
| `mark_type` | string | 是 | - | 组蛋白修饰类型（如 H3K27me3） |
| `cell_types` | string | 是 | - | 逗号分隔的细胞系列表（至少2个） |
| `flanking` | int | 否 | 10000 | 基因侧翼区域（bp） |
| `max_qvalue` | float | 否 | 0.05 | Q-value 阈值 |
| `include_overlaps` | bool | 否 | true | 是否包含重叠分析 |

**示例请求**:
```bash
curl "http://localhost:8000/api/v1/features/chipseq/genes/17276/compare-cell-lines?mark_type=H3K27me3&cell_types=K562,HepG2,H1-hESC"
```

**响应数据**:
```json
{
  "gene_id": 17276,
  "gene_name": "CATG00000000011.1",
  "gene_ensembl_id": "CATG00000000011.1",
  "chromosome": "chr10",
  "region_start": 70925039,
  "region_end": 70950336,
  "mark_type": "H3K27me3",
  "cell_lines": [
    {
      "cell_type": "HepG2",
      "total_peaks": 8,
      "avg_signal": 4.23,
      "median_fold_enrichment": 4.09,
      "std_fold_enrichment": 2.15,
      "total_coverage_bp": 2297,
      "peak_width_percentiles": {"p25": 200, "p50": 304, "p75": 372}
    },
    {
      "cell_type": "K562",
      "total_peaks": 1,
      "median_fold_enrichment": 13.17,
      "total_coverage_bp": 112
    }
  ],
  "overlap_statistics": [
    {
      "cell_pair": "HepG2:K562",
      "overlap_count": 0,
      "total_overlap_bp": 0,
      "jaccard_index": 0.0
    }
  ],
  "total_cell_lines": 2,
  "common_peaks": 0
}
```

---

### 前端组件

**新增组件**:
1. **CellLineComparePanel** - 细胞系选择面板
   - 按类别分组显示（Cancer, Normal, Stem）
   - 颜色编码细胞系标签
   - 多选 Checkbox 支持

2. **CellLineHeatmap** - 热图可视化
   - ECharts 热图展示细胞系间差异
   - 柱状图模式切换
   - 多指标支持（富集倍数、信号、Peak数量、覆盖度）
   - 详细统计卡片

3. **CellLineCompareView** - 容器组件
   - 组合选择面板和可视化
   - React Query 数据管理
   - 加载和错误状态处理

**集成位置**: `ChIPSeqPeaksTable` 组件，新增"Cell Lines"对比 Tab

---

## 📊 数据统计

### 算法实现

1. **Peaks 查询**:
```sql
SELECT e.cell_type, p.*, m.mark_name
FROM chipseq_peaks p
JOIN chipseq_experiments e ON p.experiment_id = e.experiment_id
JOIN epigenetic_mark_types m ON e.mark_type_id = m.mark_type_id
WHERE p.chromosome = :chromosome
  AND p.peak_start < :region_end
  AND p.peak_end > :region_start
  AND m.mark_name = :mark_type
  AND e.cell_type = ANY(:cell_types)
```

2. **Overlap 检测**:
   - 排序算法: 时间复杂度 O(n×m)
   - Jaccard 相似性: `|A ∩ B| / |A ∪ B|`

3. **统计计算**:
   - Median fold enrichment: `np.median()`
   - Standard deviation: `np.std()`
   - Percentiles (p25, p50, p75): `np.percentile()`

---

## ✅ 测试覆盖

### 后端 API 测试

**文件**: `tests/test_chipseq_api.py`

**新增测试类**: `TestChIPSeqCellLineComparison` (9 tests)
- `test_compare_cell_lines_endpoint_exists`
- `test_compare_two_cell_lines`
- `test_compare_all_four_cell_lines`
- `test_compare_cell_lines_with_flanking`
- `test_compare_single_cell_line_fails`
- `test_compare_response_structure`
- `test_compare_different_marks`
- `test_compare_with_invalid_cell_type`
- `test_compare_cell_lines_invalid_gene`

**测试结果**: ✅ 9 passed in 1.86s

### 数据验证测试

**文件**: `tests/test_cell_line_data_validation.py` (9 tests)

**测试类**:
- `TestCellLineDataValidation` (6 tests)
- `TestCellLineComparisonEdgeCases` (2 tests)
- `TestCellLineComparisonPerformance` (1 test)

### 前端 E2E 测试

**文件**: `e2e/chipseq-flow.spec.ts`

**新增测试套件**: `ChIP-seq Cell Line Comparison` (6 tests)
- Display cell line compare panel
- Allow selecting multiple cell lines
- Trigger comparison API call
- Display heatmap after comparison
- Require at least 2 cell lines
- Show all 4 cell types as options

---

## 🎨 UI/UX 设计

### 颜色编码方案

| 细胞系 | 颜色 | 类别 |
|--------|------|------|
| K562 | 🔴 #E74C3C | Cancer (白血病) |
| HepG2 | 🟢 #27AE60 | Cancer (肝癌) |
| GM12878 | 🔵 #3498DB | Normal (B淋巴细胞) |
| H1-hESC | 🟣 #9B59B6 | Stem (胚胎干细胞) |

### 指标选择

- **Fold Enrichment**: 信号富集倍数
- **Signal**: 平均信号强度
- **Peak Count**: Peaks 数量
- **Coverage**: 基因组覆盖度（bp）

---

## 📝 新增文件

### 后端

| 文件 | 行数 | 说明 |
|------|------|------|
| `app/schemas/chipseq.py` | +90 | 4 个新 Schema |
| `app/routers/chipseq.py` | +220 | 1 个新端点 + 3 个辅助函数 |
| `tests/test_chipseq_api.py` | +80 | 9 个新测试 |
| `tests/test_cell_line_data_validation.py` | +150 | 9 个验证测试 |

### 前端

| 文件 | 行数 | 说明 |
|------|------|------|
| `src/components/ChIPSeqPeaksTable/CellLineComparePanel.tsx` | 140 | 选择面板 |
| `src/components/ChIPSeqPeaksTable/CellLineHeatmap.tsx` | 280 | 热图可视化 |
| `src/components/ChIPSeqPeaksTable/CellLineCompareView.tsx` | 80 | 容器组件 |
| `src/components/ChIPSeqPeaksTable/index.tsx` | +30 | 集成修改 |
| `src/api/chipseq.ts` | +15 | API 客户端 |
| `src/types/chipseq.ts` | +25 | 类型定义 |
| `src/hooks/useChIPSeq.ts` | +20 | React Query hook |
| `e2e/chipseq-flow.spec.ts` | +60 | E2E 测试 |

---

## 🚀 使用示例

### API 调用

```bash
# 对比 2 个细胞系
curl "http://localhost:8000/api/v1/features/chipseq/genes/17276/compare-cell-lines?mark_type=H3K27me3&cell_types=K562,HepG2"

# 对比所有 4 个细胞系
curl "http://localhost:8000/api/v1/features/chipseq/genes/17276/compare-cell-lines?mark_type=H3K4me3&cell_types=K562,GM12878,HepG2,H1-hESC"

# 自定义参数
curl "http://localhost:8000/api/v1/features/chipseq/genes/17276/compare-cell-lines?mark_type=H3K27ac&cell_types=K562,HepG2&flanking=20000&max_qvalue=0.01&include_overlaps=true"
```

### 前端交互流程

1. 访问基因详情页 → ChIP-seq Tab
2. 点击 "Compare Cell Lines" 按钮
3. 选择 2-4 个细胞系（Cancer/Normal/Stem 分组）
4. 点击 "Compare" 按钮
5. 查看热图可视化
6. 切换指标（Fold Enrichment / Signal / Peak Count / Coverage）
7. 查看详细统计卡片

---

## 💡 科学应用场景

### 场景 1: 识别癌症特异性沉默基因

**操作**: 对比 K562 + HepG2 (癌细胞) vs H1-hESC (干细胞) 的 H3K27me3 (抑制性标记)

**预期发现**: 癌细胞中 H3K27me3 富集增强的基因可能是肿瘤抑制基因

### 场景 2: 发现干细胞特异性活性启动子

**操作**: 对比 H1-hESC vs K562/HepG2 的 H3K4me3 (活性启动子标记)

**预期发现**: H1-hESC 特异性的 H3K4me3 peaks 指示干性维持相关基因

### 场景 3: 跨细胞系保守的增强子

**操作**: 对比所有 4 个细胞系的 H3K27ac (活性增强子)

**预期发现**: 在所有细胞系中都存在的 peaks (common_peaks > 0) 表示保守的调控元件

---

## 📈 性能指标

| 指标 | 数值 |
|------|------|
| API 响应时间（2 细胞系） | ~50ms |
| API 响应时间（4 细胞系） | ~120ms |
| 前端渲染时间 | ~300ms |
| 热图交互延迟 | <50ms |

---

## 🔍 已知限制

1. **最大细胞系数量**: 建议不超过 6 个（热图可读性）
2. **基因区域大小**: 超大基因（>1Mb）可能影响响应速度
3. **Overlap 计算**: O(n²) 复杂度，当 peaks 数量>1000 时可能较慢

---

## 🎯 未来改进方向

- [ ] 添加热图导出功能（PNG/SVG）
- [ ] 支持批量基因对比（热图矩阵：基因×细胞系）
- [ ] 添加细胞系层次聚类分析
- [ ] 集成 ENCODE 元数据（抗体信息、批次效应）

---

## 📚 相关文档

- [ChIP-seq 架构设计](./PHASE_2.3_CHIPSEQ_ARCHITECTURE.md)
- [Cell Type 配置](../frontend/web/src/config/cellTypeConfigs.ts)
- [API 测试](../frontend/backend/tests/test_chipseq_api.py)
