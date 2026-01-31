# Phase 2.10: 批量基因热图可视化功能

> **完成时间**: 2025-12-07
> **版本**: Phase 2.10
> **功能**: 多基因 × 细胞系 × Marks 批量热图对比

---

## 📋 功能概述

从单基因热图矩阵扩展到批量基因对比，支持在单个视图中同时分析多个基因的表观遗传学特征模式。

### 核心价值

1. **跨基因模式识别**: 识别具有相似表观遗传模式的基因集合
2. **批量对比分析**: 一次性对比多个调控网络靶基因
3. **数据密度高**: 单个热图展示数百个数据点

---

## 🔧 技术实现

### 后端 API

**新增端点**:
```
POST /api/v1/features/chipseq/genes/batch-heatmap-matrix
```

**请求体**:
```json
{
  "gene_ids": [17276, 17277, 17278],
  "marks": ["H3K27me3", "H3K4me3", "H3K27ac"],
  "cell_types": ["K562", "HepG2", "GM12878", "H1-hESC"],
  "metric": "median_fold_enrichment",
  "flanking": 10000,
  "max_qvalue": 0.05,
  "include_details": false
}
```

**响应结构**:
```json
{
  "genes": [
    {
      "gene_id": 17276,
      "gene_ensembl_id": "CATG00000000011.1",
      "matrix": [[13.17, 41.50, 35.73], [4.09, null, null], ...],
      "valid_combinations": 4,
      "total_combinations": 12
    }
  ],
  "total_genes": 3,
  "successful_genes": 3,
  "failed_genes": [],
  "query_time_ms": 15
}
```

### 前端组件

**新增组件目录**: `src/components/BatchGeneHeatmap/`

1. **GeneSelector.tsx** (269 行)
   - 多选基因输入器
   - 支持搜索和快速添加
   - 最多 10 个基因限制

2. **BatchHeatmapMatrix.tsx** (517 行)
   - 大矩阵热图可视化
   - Y 轴: 基因 × 细胞系
   - X 轴: Histone marks
   - 动态高度计算

3. **useBatchGeneHeatmap.ts** (231 行)
   - React Query `useQueries` 并行查询
   - 自动缓存和状态管理

---

## 📈 性能指标

| 查询规模 | 响应时间 | 目标 | 状态 |
|---------|---------|------|------|
| 1 基因 × 3 marks × 4 细胞系 | 4 ms | <100ms | ✅ 优秀 |
| 3 基因 × 3 marks × 4 细胞系 | 15 ms | <200ms | ✅ 优秀 |
| 10 基因 × 4 marks × 4 细胞系 | ~80 ms (估) | <1000ms | ✅ 预估优秀 |

**性能评估**: 远超预期，单基因平均仅需 5ms

---

## ✅ 测试覆盖

### 后端测试

**test_batch_heatmap_api.py** (9 tests):
- 基本批量查询（3/10/50 基因）
- 性能测试（< 1s/3s/5s）
- 响应结构验证
- 错误处理测试

### 前端 E2E 测试

**batch-heatmap.spec.ts** (12 tests):
- 基因选择 UI
- 批量提交
- 矩阵渲染
- 指标切换
- 导出功能

**总测试数**: 21 个

---

## 🎨 UI/UX 设计

### 批量热图布局

```
┌─────────────────────────────────────────┐
│ 基因选择器: [基因17276] [基因17277] ... │
│ Marks: [H3K27me3] [H3K4me3] [H3K27ac]   │
│ 细胞系: [K562] [HepG2] [GM12878]        │
│ 指标: ○ 富集倍数 ○ 峰值数 ○ 覆盖度     │
├─────────────────────────────────────────┤
│         H3K27me3  H3K4me3  H3K27ac       │
│ Gene1-K562   █████    ████    ███        │
│ Gene1-HepG2  ███      ░░░░    ░░░░       │
│ Gene1-GM12878 ░░░░    ░░░░    ░░░░       │
│ Gene2-K562   ████     █████   ████       │
│ Gene2-HepG2  ██       ░░░░    ░░░░       │
│ ...                                      │
└─────────────────────────────────────────┘
```

### 颜色编码

保持与单基因热图一致的色阶：
- 富集倍数: 浅蓝 → 深蓝
- 峰值数量: 浅绿 → 深绿
- 覆盖度: 浅粉 → 深粉
- 平均信号: 浅橙 → 深橙

---

## 📝 新增文件

| 文件 | 行数 | 说明 |
|------|------|------|
| `app/schemas/chipseq.py` | +110 | 2 个新 Schema |
| `app/routers/chipseq.py` | +237 | 1 个新端点 |
| `tests/test_batch_heatmap_api.py` | 300 | 9 个 API 测试 |
| `frontend/web/src/components/BatchGeneHeatmap/*` | 1,070 | 3 个组件 |
| `frontend/web/src/hooks/useBatchGeneHeatmap.ts` | 231 | React Query Hook |
| `e2e/batch-heatmap.spec.ts` | 274 | 12 个 E2E 测试 |

**总计**: ~2,222 行新代码

---

## 🚀 使用示例

### API 调用

```bash
curl -X POST "http://localhost:8000/api/v1/features/chipseq/genes/batch-heatmap-matrix" \
  -H "Content-Type: application/json" \
  -d '{
    "gene_ids": [17276, 17277, 17278],
    "marks": ["H3K27me3", "H3K4me3"],
    "cell_types": ["K562", "HepG2"],
    "metric": "median_fold_enrichment"
  }'
```

### 前端使用

```tsx
import { BatchGeneHeatmapViewer } from '@/components/BatchGeneHeatmap'

<BatchGeneHeatmapViewer
  availableGenes={genesList}
  onGenesChange={(genes) => console.log(genes)}
/>
```

---

## 💡 科学应用场景

### 场景 1: 调控网络靶基因对比

**操作**: 选择某个 lncRNA 的所有靶基因（如 10 个）
**预期**: 发现靶基因在表观遗传修饰上的共性和差异

### 场景 2: 细胞类型特异性基因筛选

**操作**: 批量对比 50 个候选基因
**预期**: 识别在特定细胞系（如 K562）有独特修饰模式的基因

---

## 📚 相关文档

- [Phase 2.9 热图矩阵](./PHASE_2.9_HEATMAP_MATRIX.md)
- [Phase 2.8 细胞系对比](./PHASE_2.8_CELL_LINE_COMPARISON.md)
