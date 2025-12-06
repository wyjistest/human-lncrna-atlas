# Phase 2.3+: 通用 ChIP-seq Epigenetic Marks 架构设计

> **创建日期**: 2025-12-06
> **版本**: v1.0
> **状态**: 架构设计完成，待实施

---

## 执行摘要

本文档详细阐述了 Human LncRNA Atlas 项目 Phase 2.3 及后续阶段的**通用 ChIP-seq 组蛋白修饰架构设计**。该架构经过深度思考和前后端 agent 协同评估，能够支持 **20-50+ 种组蛋白修饰信号**（H3K27me3, H3K4me1, H3K4me3, H3K27ac 等），具有高度的扩展性和灵活性。

### 核心亮点

| 维度 | 评分 | 说明 |
|------|------|------|
| **扩展性** | ⭐⭐⭐⭐⭐ | 支持 20-50+ marks，新增 mark 仅需 2 天 |
| **性能** | ⭐⭐⭐⭐ | 预估支持 6000 万 peaks，查询 <100ms |
| **代码复用** | ⭐⭐⭐⭐⭐ | 前后端高度通用，避免重复开发 |
| **开发效率** | ⭐⭐⭐⭐ | 初期 10 天，后续每个 mark 2 天 |
| **生物学智能** | ⭐⭐⭐⭐ | 支持 bivalent domain 识别、mark 关系建模 |

---

## 目录

- [1. 背景与动机](#1-背景与动机)
- [2. 架构设计思路](#2-架构设计思路)
- [3. 后端架构设计](#3-后端架构设计)
- [4. 前端架构设计](#4-前端架构设计)
- [5. 数据导入流程](#5-数据导入流程)
- [6. 性能优化策略](#6-性能优化策略)
- [7. 扩展性评估](#7-扩展性评估)
- [8. 实施计划](#8-实施计划)
- [9. 风险与缓解](#9-风险与缓解)
- [10. 总结与建议](#10-总结与建议)

---

## 1. 背景与动机

### 1.1 初始需求

Phase 2.3 最初计划仅支持 **H3K27me3** ChIP-seq 数据（Polycomb 抑制标记）。

### 1.2 需求扩展

经过深度思考，我们认识到：
1. 组蛋白修饰是一个**家族**，不仅仅是 H3K27me3
2. 不同 marks 有不同的生物学功能：
   - **Repressive marks** (抑制): H3K27me3, H3K9me3, H4K20me3
   - **Activating marks** (激活): H3K4me1, H3K4me3, H3K27ac, H3K36me3
   - **Bivalent marks** (双价): H3K4me3 + H3K27me3
3. 数据结构和查询模式高度相似
4. **为每个 mark 重复开发是低效的**

### 1.3 设计目标

设计一个**通用架构**，满足：
- ✅ 支持 20-50+ 种组蛋白修饰
- ✅ 新增 mark 无需修改核心代码
- ✅ 配置驱动的 UI，高度复用
- ✅ 统一 API 端点，避免端点爆炸
- ✅ 支持多 marks 对比功能
- ✅ 与现有 RepeatMasker 架构兼容

---

## 2. 架构设计思路

### 2.1 方案对比（深度思考结果）

经过 15 轮深度思考，我们评估了三种方案：

#### 方案 A：每个 mark 一个 track

```
feature_tracks:
  - h3k27me3_chipseq
  - h3k4me1_chipseq
  - h3k4me3_chipseq
  ...（20+ tracks）
```

**评估**: ❌ 不够通用，扩展性差

---

#### 方案 B：统一 ChIP-seq track + mark_type 字段

```
feature_tracks:
  - chipseq_epigenetic (唯一)

experiments:
  - mark_type: 'H3K27me3'
  - mark_type: 'H3K4me1'
  ...
```

**评估**: ✅ 通用性强，但牺牲部分灵活性

---

#### 方案 C：混合分层架构（**推荐**）

```
feature_tracks:
  - chipseq_epigenetic (统一类别)

epigenetic_mark_types (新表):
  - mark_name: 'H3K27me3'
  - mark_category: 'repressive'
  - mark_function: 'Polycomb repression'

chipseq_experiments:
  - mark_type_id (外键到 epigenetic_mark_types)
  - tissue_type, cell_type, ...

chipseq_peaks:
  - experiment_id
  - JSONB attributes
```

**评估**: ⭐⭐⭐⭐⭐ **最佳方案**，平衡通用性和灵活性

---

### 2.2 核心设计决策

| 决策点 | 选择 | 理由 |
|--------|------|------|
| **数据表设计** | 独立 `chipseq_peaks` 表 | 避免与 RepeatMasker 混淆 |
| **Mark 管理** | `epigenetic_mark_types` 表 | 规范化管理 marks |
| **API 端点** | `/features/chipseq?mark_type=X` | 统一端点，避免爆炸 |
| **前端组件** | `ChIPSeqPeaksTable`（通用） | 配置驱动，高度复用 |
| **扩展策略** | 配置文件驱动 | 新增 mark 无需修改代码 |

---

## 3. 后端架构设计

### 3.1 数据库 Schema

#### 核心表结构

```
epigenetic_mark_types (15 pre-defined marks)
    |
    +-- mark_relationships (bivalent, antagonistic, synergistic)
    |
    v
chipseq_experiments (实验元数据)
    |
    v
chipseq_peaks (PARTITIONED by species_id)
    |
    v
gene_peak_associations (预计算查找表)
    |
    v
mv_chipseq_mark_stats (物化视图)
```

---

#### 表 1: `epigenetic_mark_types` (Mark 类型注册表)

```sql
CREATE TABLE epigenetic_mark_types (
    mark_type_id SERIAL PRIMARY KEY,
    mark_name VARCHAR(50) UNIQUE NOT NULL,  -- 'H3K27me3'
    mark_category VARCHAR(50) NOT NULL,     -- 'repressive', 'activating', 'enhancer'
    mark_function TEXT,                     -- 'Polycomb repressive mark'
    modification_type VARCHAR(50),          -- 'methylation', 'acetylation'
    histone_target VARCHAR(10),             -- 'H3', 'H4'
    residue_position VARCHAR(10),           -- 'K27', 'K4'
    display_color VARCHAR(20),              -- '#9B59B6'
    display_order INTEGER,
    is_active BOOLEAN DEFAULT TRUE
);
```

**预定义 15 种 marks**:

| Category | Marks | 颜色 |
|----------|-------|------|
| Repressive | H3K27me3, H3K9me3, H4K20me3, H3K9me2 | 紫色系 |
| Activating | H3K4me3, H3K4me2, H3K9ac, H3K4ac | 绿色系 |
| Enhancer | H3K4me1, H3K27ac | 橙色系 |
| Elongation | H3K36me3, H3K79me2 | 蓝色系 |
| Structural | H2A.Z, CTCF | 青色系 |

---

#### 表 2: `mark_relationships` (Mark 关系表)

```sql
CREATE TABLE mark_relationships (
    relationship_id SERIAL PRIMARY KEY,
    mark_type_1 INTEGER REFERENCES epigenetic_mark_types(mark_type_id),
    mark_type_2 INTEGER REFERENCES epigenetic_mark_types(mark_type_id),
    relationship_type VARCHAR(50),  -- 'bivalent', 'antagonistic', 'synergistic'
    confidence_score DECIMAL(3,2),
    biological_significance TEXT,
    UNIQUE(mark_type_1, mark_type_2)
);
```

**典型关系**:
- `H3K27me3 + H3K4me3` → bivalent (发育基因)
- `H3K27me3 ⊥ H3K27ac` → antagonistic (互斥)
- `H3K4me1 + H3K27ac` → synergistic (增强子)

---

#### 表 3: `chipseq_experiments` (实验元数据)

```sql
CREATE TABLE chipseq_experiments (
    experiment_id SERIAL PRIMARY KEY,
    mark_type_id INTEGER NOT NULL REFERENCES epigenetic_mark_types(mark_type_id),
    species_id INTEGER NOT NULL REFERENCES species(species_id),

    -- ENCODE 元数据
    encode_accession VARCHAR(50) UNIQUE,
    biosample_accession VARCHAR(50),

    -- 生物学元数据
    tissue_type VARCHAR(100) NOT NULL,
    cell_type VARCHAR(100),
    cell_line VARCHAR(100),

    -- 实验条件
    treatment VARCHAR(200),
    developmental_stage VARCHAR(50),
    antibody_target VARCHAR(100),
    antibody_source VARCHAR(100),

    -- 数据质量
    replicate_type VARCHAR(20),
    total_reads BIGINT,
    mapped_reads BIGINT,
    mapping_rate DECIMAL(5,2),
    frac_of_reads_in_peaks DECIMAL(5,2),
    nsc DECIMAL(5,2),         -- NSC score
    rsc DECIMAL(5,2),         -- RSC score
    quality_score DECIMAL(5,2),

    -- 管理字段
    batch_id INTEGER REFERENCES import_batches(batch_id),
    source_database VARCHAR(50) DEFAULT 'ENCODE',
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    is_active BOOLEAN DEFAULT TRUE,

    UNIQUE (mark_type_id, species_id, encode_accession)
);

-- 索引
CREATE INDEX idx_chipseq_exp_mark ON chipseq_experiments(mark_type_id);
CREATE INDEX idx_chipseq_exp_species ON chipseq_experiments(species_id);
CREATE INDEX idx_chipseq_exp_tissue ON chipseq_experiments(tissue_type);
CREATE INDEX idx_chipseq_exp_mark_species ON chipseq_experiments(mark_type_id, species_id);
```

---

#### 表 4: `chipseq_peaks` (分区表)

```sql
CREATE TABLE chipseq_peaks (
    peak_id BIGSERIAL,
    experiment_id INTEGER NOT NULL REFERENCES chipseq_experiments(experiment_id),
    species_id INTEGER NOT NULL REFERENCES species(species_id),

    -- 基因组坐标
    chromosome VARCHAR(20) NOT NULL,
    peak_start BIGINT NOT NULL,
    peak_end BIGINT NOT NULL,
    strand VARCHAR(1) CHECK (strand IN ('+', '-', '.')),

    -- 信号强度
    signal_value DECIMAL(12,4),
    fold_enrichment DECIMAL(12,4),
    p_value DECIMAL(15,10),
    q_value DECIMAL(15,10),

    -- Peak 特性
    peak_summit INTEGER,  -- 相对于 peak_start 的偏移
    peak_width INTEGER GENERATED ALWAYS AS (peak_end - peak_start) STORED,
    peak_type VARCHAR(20),  -- 'narrow', 'broad'

    -- 批次追踪
    batch_id INTEGER REFERENCES import_batches(batch_id),
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,

    PRIMARY KEY (species_id, peak_id),
    CHECK (peak_start >= 0 AND peak_end > peak_start)
) PARTITION BY LIST (species_id);

-- 创建分区
CREATE TABLE chipseq_peaks_human PARTITION OF chipseq_peaks FOR VALUES IN (1);
CREATE TABLE chipseq_peaks_chimp PARTITION OF chipseq_peaks FOR VALUES IN (2);
CREATE TABLE chipseq_peaks_macaque PARTITION OF chipseq_peaks FOR VALUES IN (3);
CREATE TABLE chipseq_peaks_marmoset PARTITION OF chipseq_peaks FOR VALUES IN (4);

-- 索引策略
CREATE INDEX idx_peaks_human_exp ON chipseq_peaks_human(experiment_id);
CREATE INDEX idx_peaks_human_location ON chipseq_peaks_human(chromosome, peak_start, peak_end);
CREATE INDEX idx_peaks_human_exp_loc ON chipseq_peaks_human(experiment_id, chromosome, peak_start, peak_end);
CREATE INDEX idx_peaks_human_signal ON chipseq_peaks_human(signal_value) WHERE signal_value > 10;
CREATE INDEX idx_peaks_human_fold ON chipseq_peaks_human(fold_enrichment) WHERE fold_enrichment > 5;
CREATE INDEX idx_peaks_human_qvalue ON chipseq_peaks_human(q_value) WHERE q_value < 0.05;
```

---

#### 表 5: `gene_peak_associations` (预计算关联表)

```sql
CREATE TABLE gene_peak_associations (
    association_id BIGSERIAL PRIMARY KEY,
    gene_id INTEGER NOT NULL REFERENCES genes(gene_id),
    peak_id BIGINT NOT NULL,
    species_id INTEGER NOT NULL,
    experiment_id INTEGER NOT NULL,
    mark_type_id INTEGER NOT NULL,

    -- 关联类型
    position_type VARCHAR(50),  -- 'promoter', 'gene_body', 'downstream', 'intergenic'
    distance_to_tss INTEGER,    -- TSS 距离
    overlap_bp INTEGER,         -- 重叠碱基数

    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,

    UNIQUE(gene_id, peak_id, species_id),
    FOREIGN KEY (species_id, peak_id) REFERENCES chipseq_peaks(species_id, peak_id)
);

CREATE INDEX idx_gpa_gene ON gene_peak_associations(gene_id);
CREATE INDEX idx_gpa_peak ON gene_peak_associations(peak_id, species_id);
CREATE INDEX idx_gpa_mark ON gene_peak_associations(mark_type_id);
CREATE INDEX idx_gpa_gene_mark ON gene_peak_associations(gene_id, mark_type_id);
```

---

#### 物化视图 1: `mv_chipseq_mark_stats`

```sql
CREATE MATERIALIZED VIEW mv_chipseq_mark_stats AS
SELECT
    emt.mark_type_id,
    emt.mark_name,
    emt.mark_category,
    s.species_id,
    s.species_code,
    COUNT(DISTINCT ce.experiment_id) AS experiment_count,
    COUNT(cp.peak_id) AS peak_count,
    AVG(cp.signal_value) AS avg_signal,
    AVG(cp.fold_enrichment) AS avg_fold_enrichment,
    AVG(cp.peak_width) AS avg_peak_width
FROM epigenetic_mark_types emt
LEFT JOIN chipseq_experiments ce ON emt.mark_type_id = ce.mark_type_id
LEFT JOIN species s ON ce.species_id = s.species_id
LEFT JOIN chipseq_peaks cp ON ce.experiment_id = cp.experiment_id AND s.species_id = cp.species_id
WHERE emt.is_active = TRUE
GROUP BY emt.mark_type_id, emt.mark_name, emt.mark_category, s.species_id, s.species_code;

CREATE UNIQUE INDEX ON mv_chipseq_mark_stats(mark_type_id, species_id);
```

---

### 3.2 API 端点设计

#### 端点 1: 获取可用 Marks

```
GET /api/v1/features/chipseq/marks?species_id=1
```

**响应**:
```json
{
  "success": true,
  "data": [
    {
      "mark_type_id": 1,
      "mark_name": "H3K27me3",
      "mark_category": "repressive",
      "display_color": "#9B59B6",
      "experiment_count": 15,
      "peak_count": 125000
    },
    {
      "mark_type_id": 2,
      "mark_name": "H3K4me1",
      "mark_category": "enhancer",
      "display_color": "#F39C12",
      "experiment_count": 12,
      "peak_count": 98000
    }
  ]
}
```

---

#### 端点 2: 获取基因区域 Peaks

```
GET /api/v1/features/chipseq/genes/{gene_id}
    ?mark_type=H3K27me3
    &flanking=10000
    &min_fold_enrichment=5
    &max_qvalue=0.01
    &page=1
    &page_size=50
```

**响应**:
```json
{
  "success": true,
  "data": {
    "gene_id": 12345,
    "gene_name": "HOTAIR",
    "region": {
      "chromosome": "chr12",
      "start": 54346800,
      "end": 54366800
    },
    "total": 42,
    "items": [
      {
        "peak_id": 987654,
        "chromosome": "chr12",
        "peak_start": 54350000,
        "peak_end": 54352500,
        "peak_width": 2500,
        "signal_value": 45.6,
        "fold_enrichment": 12.3,
        "p_value": 1.23e-10,
        "q_value": 5.67e-09,
        "position_type": "promoter",
        "distance_to_tss": -500,
        "experiment": {
          "experiment_id": 101,
          "encode_accession": "ENCSR000ABC",
          "tissue_type": "brain",
          "cell_type": "neuron",
          "mark_name": "H3K27me3"
        }
      }
    ],
    "page": 1,
    "page_size": 50
  }
}
```

---

#### 端点 3: 多 Marks 对比

```
GET /api/v1/features/chipseq/genes/{gene_id}/compare
    ?marks=H3K27me3,H3K4me3,H3K27ac
    &flanking=10000
```

**响应**:
```json
{
  "success": true,
  "data": {
    "gene_id": 12345,
    "gene_name": "HOTAIR",
    "marks": [
      {
        "mark_name": "H3K27me3",
        "peak_count": 15,
        "avg_signal": 34.5,
        "avg_fold_enrichment": 8.2,
        "position_distribution": {
          "promoter": 5,
          "gene_body": 8,
          "downstream": 2
        },
        "peaks": [...]
      },
      {
        "mark_name": "H3K4me3",
        "peak_count": 8,
        "avg_signal": 56.7,
        "avg_fold_enrichment": 15.3,
        "position_distribution": {
          "promoter": 7,
          "gene_body": 1,
          "downstream": 0
        },
        "peaks": [...]
      }
    ],
    "overlapping_regions": [
      {
        "chromosome": "chr12",
        "start": 54350000,
        "end": 54351000,
        "marks": ["H3K27me3", "H3K4me3"],
        "domain_type": "bivalent"
      }
    ]
  }
}
```

---

### 3.3 性能优化策略

#### 1. 分区表策略

- `chipseq_peaks` 按 `species_id` 分区
- 每个物种独立索引，查询时只扫描相关分区
- 预估性能提升：**4x**

#### 2. 索引策略

| 索引类型 | 适用场景 | 预估提升 |
|---------|---------|---------|
| `(experiment_id)` | 按实验查询 | 10x |
| `(chromosome, start, end)` | 区域查询 | 5x |
| `(experiment_id, chromosome, start, end)` | 复合查询 | 20x |
| `(signal_value) WHERE signal_value > 10` | 信号过滤 | 3x |
| `(fold_enrichment) WHERE fold_enrichment > 5` | 富集过滤 | 3x |

#### 3. 物化视图

- `mv_chipseq_mark_stats`: 预计算每个 mark 的统计数据
- `mv_gene_mark_summary`: 预计算基因-mark 关联统计
- 定期刷新（每小时）

#### 4. 缓存策略

```python
from functools import lru_cache
from cachetools import TTLCache

# API 层缓存
@cache.cached(ttl=3600, key_prefix="chipseq_marks")
def get_available_marks(species_id: int):
    """缓存可用 marks 列表（1 小时）"""
    pass

@cache.cached(ttl=1800, key_prefix="gene_peaks")
def get_gene_peaks(gene_id: int, mark_type: str, filters: dict):
    """缓存基因 peaks 数据（30 分钟）"""
    pass
```

---

## 4. 前端架构设计

### 4.1 组件层级结构

```
ChIPSeqPeaksTable (主组件)
├── MarkSelector (Mark 选择器)
│   ├── 分组下拉框（Repressive / Activating / Enhancer）
│   ├── 搜索功能
│   └── 多选模式
├── StatsCards (统计卡片)
│   ├── Total Peaks
│   ├── Avg Signal
│   ├── Avg Fold Enrichment
│   └── Position Distribution
├── FilterPanel (过滤面板)
│   ├── Q-Value 阈值 (Select)
│   ├── Signal 滑块 (Slider)
│   ├── Fold Enrichment 滑块
│   └── Position Type (Dropdown)
├── CompareCharts (对比图表 - 仅对比模式)
│   ├── Peak Count Chart (柱状图)
│   ├── Signal Comparison Chart
│   ├── Fold Enrichment Chart
│   └── Position Distribution Chart (堆叠柱状图)
└── PeaksTable (数据表格)
    ├── 分页控件
    ├── 排序功能
    └── 颜色编码
```

---

### 4.2 配置驱动设计

#### `markConfigs.ts`

```typescript
export interface MarkConfig {
  displayName: string
  displayNameShort: string
  color: string
  category: MarkCategory
  function: string
  icon: string
  defaultFilters: {
    min_fold_enrichment: number
    max_qvalue: number
  }
  recommendedFilters?: {
    min_signal?: number
  }
  relatedMarks?: MarkType[]
}

export const MARK_CONFIGS: Record<MarkType, MarkConfig> = {
  H3K27me3: {
    displayName: 'H3K27me3 (Polycomb Repressive)',
    displayNameShort: 'H3K27me3',
    color: '#9B59B6',
    category: 'repressive',
    function: 'Polycomb repression, gene silencing',
    icon: '🚫',
    defaultFilters: {
      min_fold_enrichment: 5,
      max_qvalue: 0.01
    },
    relatedMarks: ['H3K4me3', 'H3K9me3']
  },
  H3K4me1: {
    displayName: 'H3K4me1 (Enhancer Mark)',
    displayNameShort: 'H3K4me1',
    color: '#F39C12',
    category: 'enhancer',
    function: 'Enhancer activity',
    icon: '✨',
    defaultFilters: {
      min_fold_enrichment: 3,
      max_qvalue: 0.05
    },
    relatedMarks: ['H3K27ac', 'H3K4me3']
  },
  // ... 其他 15+ marks
}
```

---

### 4.3 TypeScript 类型定义

```typescript
// types/chipseq.ts

export type MarkType =
  | 'H3K27me3' | 'H3K9me3' | 'H3K9me2' | 'H4K20me3'    // Repressive
  | 'H3K4me1' | 'H3K4me3' | 'H3K27ac' | 'H3K36me3'     // Activating/Enhancer
  | 'H3K4me2' | 'H3K79me2' | 'H3K9ac' | 'H3K4ac'       // Activating
  | 'H2AZ' | 'H2BK120ub' | 'H4K20me1' | 'CTCF'         // Other

export type MarkCategory =
  | 'repressive'
  | 'activating'
  | 'enhancer'
  | 'elongation'
  | 'other'

export interface ChIPSeqPeak {
  peak_id: number
  chromosome: string
  peak_start: number
  peak_end: number
  peak_width: number
  signal_value: number
  fold_enrichment: number
  p_value: number
  q_value: number
  position_type: 'promoter' | 'gene_body' | 'downstream' | 'intergenic'
  distance_to_tss: number
  experiment: {
    experiment_id: number
    encode_accession: string
    tissue_type: string
    cell_type: string
    mark_name: MarkType
  }
}

export interface ChIPSeqFilters {
  mark_type?: MarkType | MarkType[]
  min_fold_enrichment?: number
  max_qvalue?: number
  min_signal?: number
  position_type?: string[]
  flanking?: number
  page?: number
  page_size?: number
}

export interface ChIPSeqResponse {
  gene_id: number
  gene_name: string
  region: {
    chromosome: string
    start: number
    end: number
  }
  total: number
  items: ChIPSeqPeak[]
  page: number
  page_size: number
}

export interface ChIPSeqSummary {
  total_peaks: number
  avg_signal: number
  max_signal: number
  avg_fold_enrichment: number
  max_fold_enrichment: number
  position_distribution: Record<string, number>
}

export interface MarkComparisonData {
  mark_name: MarkType
  peak_count: number
  avg_signal: number
  avg_fold_enrichment: number
  position_distribution: Record<string, number>
  peaks: ChIPSeqPeak[]
}

export interface ChIPSeqCompareResponse {
  gene_id: number
  gene_name: string
  marks: MarkComparisonData[]
  overlapping_regions: Array<{
    chromosome: string
    start: number
    end: number
    marks: MarkType[]
    domain_type: 'bivalent' | 'active' | 'repressed'
  }>
}
```

---

### 4.4 主组件 Props

```typescript
interface ChIPSeqPeaksTableProps {
  geneId: number

  /** 初始选择的 mark（单个） */
  initialMarkType?: MarkType

  /** 可选的 marks 列表（限制选项） */
  availableMarks?: MarkType[]

  /** 是否启用对比模式（多选） */
  enableComparison?: boolean

  /** 默认侧翼区域（bp） */
  defaultFlanking?: number

  /** Mark 变更回调 */
  onMarkChange?: (marks: MarkType[]) => void

  /** 外部控制的 marks（受控模式） */
  selectedMarks?: MarkType[]

  /** 是否显示图表 */
  showCharts?: boolean

  /** 是否显示统计卡片 */
  showStats?: boolean
}
```

---

### 4.5 API 客户端

```typescript
// api/chipseq.ts

export const chipseqApi = {
  /**
   * 获取物种可用的 marks
   */
  getAvailableMarks: (speciesId: number) =>
    apiClient.get<MarkTypeResponse[]>(`/features/chipseq/marks`, {
      params: { species_id: speciesId }
    }),

  /**
   * 获取基因区域的 ChIP-seq peaks
   */
  getGenePeaks: (geneId: number, filters: ChIPSeqFilters) =>
    apiClient.get<ChIPSeqResponse>(`/features/chipseq/genes/${geneId}`, {
      params: {
        mark_type: Array.isArray(filters.mark_type)
          ? filters.mark_type.join(',')
          : filters.mark_type,
        min_fold_enrichment: filters.min_fold_enrichment,
        max_qvalue: filters.max_qvalue,
        flanking: filters.flanking,
        page: filters.page,
        page_size: filters.page_size,
      }
    }),

  /**
   * 获取基因的 ChIP-seq 统计摘要
   */
  getGeneSummary: (geneId: number, markType: MarkType) =>
    apiClient.get<ChIPSeqSummary>(
      `/features/chipseq/genes/${geneId}/summary`,
      { params: { mark_type: markType } }
    ),

  /**
   * 对比多个 marks
   */
  compareMarks: (geneId: number, marks: MarkType[], flanking: number = 10000) =>
    apiClient.get<ChIPSeqCompareResponse>(
      `/features/chipseq/genes/${geneId}/compare`,
      { params: { marks: marks.join(','), flanking } }
    ),

  /**
   * 导出为 BED 格式
   */
  exportPeaksToBED: (geneId: number, filters: ChIPSeqFilters) => {
    const params = new URLSearchParams()
    if (filters.mark_type) params.append('mark_type', String(filters.mark_type))
    if (filters.min_fold_enrichment) params.append('min_fold_enrichment', String(filters.min_fold_enrichment))

    const url = `${API_BASE_URL}/features/chipseq/genes/${geneId}/export?${params}`
    window.open(url, '_blank')
  }
}

// Query Keys Factory
export const chipseqQueryKeys = {
  all: ['chipseq'] as const,
  availableMarks: (speciesId: number) => [...chipseqQueryKeys.all, 'marks', speciesId] as const,
  gene: (geneId: number) => [...chipseqQueryKeys.all, 'gene', geneId] as const,
  peaks: (geneId: number, filters: ChIPSeqFilters) =>
    [...chipseqQueryKeys.gene(geneId), 'peaks', filters] as const,
  summary: (geneId: number, markType: MarkType) =>
    [...chipseqQueryKeys.gene(geneId), 'summary', markType] as const,
  compare: (geneId: number, marks: MarkType[], flanking: number) =>
    [...chipseqQueryKeys.gene(geneId), 'compare', marks, flanking] as const,
}
```

---

### 4.6 Custom Hooks

```typescript
// hooks/useChIPSeq.ts

export function useChIPSeqPeaks(
  geneId: number,
  filters: ChIPSeqFilters,
  options?: UseQueryOptions
) {
  return useQuery({
    queryKey: chipseqQueryKeys.peaks(geneId, filters),
    queryFn: () => chipseqApi.getGenePeaks(geneId, filters),
    staleTime: 30 * 60 * 1000, // 30 minutes
    enabled: geneId > 0 && !!filters.mark_type,
    ...options
  })
}

export function useChIPSeqSummary(
  geneId: number,
  markType: MarkType,
  options?: UseQueryOptions
) {
  return useQuery({
    queryKey: chipseqQueryKeys.summary(geneId, markType),
    queryFn: () => chipseqApi.getGeneSummary(geneId, markType),
    staleTime: 30 * 60 * 1000,
    enabled: geneId > 0 && !!markType,
    ...options
  })
}

export function useChIPSeqMarks(
  speciesId: number,
  options?: UseQueryOptions
) {
  return useQuery({
    queryKey: chipseqQueryKeys.availableMarks(speciesId),
    queryFn: () => chipseqApi.getAvailableMarks(speciesId),
    staleTime: 60 * 60 * 1000, // 1 hour
    enabled: speciesId > 0,
    ...options
  })
}

export function useChIPSeqCompare(
  geneId: number,
  marks: MarkType[],
  flanking: number = 10000
) {
  return useQuery({
    queryKey: chipseqQueryKeys.compare(geneId, marks, flanking),
    queryFn: () => chipseqApi.compareMarks(geneId, marks, flanking),
    staleTime: 30 * 60 * 1000,
    enabled: geneId > 0 && marks.length > 1,
  })
}

// 组合 Hook
export function useChIPSeqData(
  geneId: number,
  markType: MarkType,
  filters: ChIPSeqFilters
) {
  const peaks = useChIPSeqPeaks(geneId, { ...filters, mark_type: markType })
  const summary = useChIPSeqSummary(geneId, markType)

  return {
    peaks: peaks.data,
    summary: summary.data,
    isLoading: peaks.isLoading || summary.isLoading,
    isError: peaks.isError || summary.isError,
    error: peaks.error || summary.error,
  }
}
```

---

### 4.7 UI 布局设计

#### 单 Mark 模式

```
+----------------------------------------------------------+
| Gene Detail: MALAT1                                       |
+----------------------------------------------------------+
| [Core Data] [Genomic Features]                            |
+----------------------------------------------------------+
|   [Repeat Elements] [ChIP-seq Peaks]                      |
+----------------------------------------------------------+
| Select Mark: [H3K27me3 (Repressive) v]  [Export BED]     |
+----------------------------------------------------------+
| +------------+ +------------+ +------------+ +------------+|
| | Total Peaks| | Avg Signal | | Avg Fold   | | Max Signal ||
| |   1,234    | |    45.6    | |   12.3x    | |   234.5    ||
| +------------+ +------------+ +------------+ +------------+|
| Position Distribution: [Promoter: 45%] [Gene Body: 35%]   |
+----------------------------------------------------------+
| Filters:                                    [Reset]       |
| Q-Value: [0.01 v] Signal: [min __] Position: [All v]     |
| Fold Enrichment: [===o==========] 5-50x    [Apply]       |
+----------------------------------------------------------+
| ChIP-seq Peaks (1,234)                                    |
| +------+-------+-------+-------+-------+-------+--------+|
| | Chr  | Start | End   | Width | Signal| Fold  | Q-Val  ||
| +------+-------+-------+-------+-------+-------+--------+|
| | chr1 | 1,234 | 1,534 | 300bp | 45.6  | 12.3x | 1e-10  ||
| | chr1 | 2,100 | 2,400 | 300bp | 34.2  | 8.7x  | 2e-8   ||
| +------+-------+-------+-------+-------+-------+--------+|
| [< 1 2 3 ... 50 >]    20/page v    1-20 / 1,234 records  |
+----------------------------------------------------------+
```

#### 对比模式

```
+----------------------------------------------------------+
| Selected Marks:                                           |
| [H3K27me3 (Repressive) x] [H3K4me3 (Activating) x]       |
| [H3K27ac (Enhancer) x]  [+ Add Mark]                     |
+----------------------------------------------------------+
| [Merged View] [Statistics] [Parallel] (if 2 marks)       |
+----------------------------------------------------------+
| +------------------------+ +------------------------+     |
| |  Peak Counts by Mark   | |   Signal Comparison    |     |
| |        [Bar Chart]     | |      [Bar Chart]       |     |
| +------------------------+ +------------------------+     |
| +------------------------+ +------------------------+     |
| | Avg Fold Enrichment    | | Position Distribution  |     |
| |     [Bar Chart]        | |    [Stacked Bar]       |     |
| +------------------------+ +------------------------+     |
+----------------------------------------------------------+
| Merged Table (All Marks)                                  |
| +------+-------+-------+-------+-------+-------+--------+|
| | Chr  | Start | End   | Mark  | Signal| Fold  | Q-Val  ||
| +------+-------+-------+-------+-------+-------+--------+|
| | chr1 | 1,234 | 1,534 |H3K27me3| 45.6 | 12.3x | 1e-10  ||
| | chr1 | 1,250 | 1,450 |H3K4me3| 67.8 | 18.5x | 3e-12  ||
| +------+-------+-------+-------+-------+-------+--------+|
+----------------------------------------------------------+
| Overlapping Regions: 3 found                              |
| [Bivalent Domain] chr1:1,250-1,450 (H3K27me3 + H3K4me3)  |
+----------------------------------------------------------+
```

---

### 4.8 国际化支持

```json
// en/genes.json
{
  "detail": {
    "chipseq": {
      "title": "ChIP-seq Epigenetic Marks",
      "selectMark": "Select Mark",
      "selectedMarks": "Selected Marks",
      "addMark": "Add Mark",
      "exportBED": "Export BED",
      "exportCSV": "Export CSV",

      "marks": {
        "H3K27me3": "H3K27me3 (Polycomb Repressive)",
        "H3K9me3": "H3K9me3 (Heterochromatin)",
        "H3K4me1": "H3K4me1 (Enhancer)",
        "H3K4me3": "H3K4me3 (Active Promoter)",
        "H3K27ac": "H3K27ac (Active Enhancer)",
        // ... 其他 marks
      },

      "categories": {
        "repressive": "Repressive Marks",
        "activating": "Activating Marks",
        "enhancer": "Enhancer Marks",
        "elongation": "Elongation Marks",
        "other": "Other Marks"
      },

      "stats": {
        "totalPeaks": "Total Peaks",
        "avgSignal": "Avg Signal",
        "avgFold": "Avg Fold Enrichment",
        "maxSignal": "Max Signal",
        "positionDistribution": "Position Distribution"
      },

      "filters": {
        "qvalue": "Q-Value",
        "signal": "Signal Value",
        "foldEnrichment": "Fold Enrichment",
        "positionType": "Position Type",
        "flanking": "Flanking Region (bp)"
      },

      "positionTypes": {
        "promoter": "Promoter",
        "gene_body": "Gene Body",
        "downstream": "Downstream",
        "intergenic": "Intergenic"
      },

      "compareMode": {
        "mergedView": "Merged View",
        "parallelView": "Parallel View",
        "statisticsView": "Statistics",
        "overlappingRegions": "Overlapping Regions",
        "bivalentDomain": "Bivalent Domain"
      }
    }
  }
}
```

---

## 5. 数据导入流程

### 5.1 统一导入脚本

```bash
python scripts/import_chipseq.py \
    --input H3K27me3_brain_peaks.narrowPeak.gz \
    --mark-type H3K27me3 \
    --species human \
    --experiment-name "ENCODE_Brain_H3K27me3_Rep1" \
    --tissue-type "brain" \
    --cell-type "neuron" \
    --encode-accession "ENCSR000ABC" \
    --batch-size 10000 \
    --compute-associations  # 可选：计算 gene-peak 关联
```

### 5.2 元数据 JSON 格式

```json
{
  "mark_type": "H3K27me3",
  "mark_category": "repressive",
  "encode_accession": "ENCSR000ABC",
  "biosample_accession": "ENCBS000DEF",
  "tissue_type": "brain",
  "cell_type": "neuron",
  "cell_line": null,
  "treatment": null,
  "developmental_stage": "adult",
  "antibody_target": "H3K27me3",
  "antibody_source": "Abcam ab6002",
  "replicate_type": "biological",
  "total_reads": 45000000,
  "mapped_reads": 42000000,
  "mapping_rate": 93.33,
  "frac_of_reads_in_peaks": 15.2,
  "nsc": 1.05,
  "rsc": 0.95,
  "quality_score": 85.5,
  "peak_type": "broad"
}
```

### 5.3 批量导入配置

```yaml
# batch_import_chipseq.yaml
species: human
experiments:
  - mark_type: H3K27me3
    files:
      - path: data/H3K27me3_brain.narrowPeak
        metadata: data/H3K27me3_brain_metadata.json
      - path: data/H3K27me3_heart.narrowPeak
        metadata: data/H3K27me3_heart_metadata.json

  - mark_type: H3K4me1
    files:
      - path: data/H3K4me1_brain.narrowPeak
        metadata: data/H3K4me1_brain_metadata.json

options:
  batch_size: 10000
  compute_associations: true
  parallel: 4
```

```bash
python scripts/batch_import_chipseq.py batch_import_chipseq.yaml
```

---

## 6. 性能优化策略

### 6.1 查询性能预估

| 查询类型 | 数据量 | 预估时间 | 优化策略 |
|---------|--------|---------|---------|
| 单基因区域 (10kb) | ~50 peaks | **< 30ms** | location + experiment 索引 |
| 单基因 + mark 过滤 | ~50 peaks | **< 50ms** | mark_type_id + location 索引 |
| 多 marks 对比 (3 marks) | ~150 peaks | **< 150ms** | 并行查询 + JOIN |
| 基因统计聚合 | ~50 peaks | **< 80ms** | 物化视图预计算 |
| 可用 marks 列表 | 15 marks | **< 20ms** | 物化视图 + 缓存 |

### 6.2 扩展性评估

#### 数据规模预估（1 年后）

| 指标 | 保守估计 | 乐观估计 |
|------|---------|---------|
| Mark 类型 | 20 | 50 |
| 每个 mark 实验数 | 30 | 100 |
| 每个实验 peaks 数 | 50,000 | 200,000 |
| 总 peaks 数 | **30,000,000** | **1,000,000,000** |
| 存储需求 | **10-15 GB** | **35-50 GB** |

#### 架构承载能力

| 数据规模 | 评估 | 缓解措施 |
|---------|------|---------|
| < 1000 万 peaks | ✅ 无压力 | 现有架构足够 |
| 1000-5000 万 peaks | ✅ 可管理 | 物化视图预计算 |
| 5000 万-1 亿 peaks | ⚠️ 需优化 | 分区表 + 预聚合 |
| > 1 亿 peaks | ⚠️ 挑战 | 考虑列式存储（如 ClickHouse） |

---

## 7. 实施计划

### 7.1 Phase 2.3: 通用架构 + H3K27me3

**工期**: 10 个工作日

| 阶段 | 任务 | 工作量 |
|------|------|--------|
| **Day 1-2** | 数据库设计 | 2 天 |
| - 创建 SQL DDL | - | - |
| - 执行建表脚本 | - | - |
| - 插入 15 种 marks 预定义数据 | - | - |
| **Day 3-4** | 后端 ORM + Pydantic | 2 天 |
| - Experiment, Peak ORM 模型 | - | - |
| - Pydantic schemas | - | - |
| **Day 5-7** | 后端 API 实现 | 3 天 |
| - `/chipseq/marks` 端点 | - | - |
| - `/chipseq/genes/{id}` 端点 | - | - |
| - `/chipseq/genes/{id}/summary` 端点 | - | - |
| **Day 8** | 数据导入脚本 | 1 天 |
| - `import_chipseq.py` | - | - |
| - 导入 H3K27me3 测试数据 | - | - |
| **Day 9-10** | 前端组件开发 | 2 天 |
| - TypeScript 类型定义 | - | - |
| - markConfigs.ts | - | - |
| - ChIPSeqPeaksTable 基础组件 | - | - |
| - MarkSelector 组件 | - | - |
| - 集成到 GeneDetail 页面 | - | - |

---

### 7.2 Phase 2.4: 多 Marks 支持

**工期**: 5 个工作日

| 阶段 | 任务 | 工作量 |
|------|------|--------|
| **Day 1-3** | 数据导入 | 3 天 |
| - 导入 H3K4me1, H3K4me3, H3K27ac 数据 | - | - |
| **Day 4** | 前端配置扩展 | 1 天 |
| - 添加新 marks 的 markConfigs | - | - |
| - 国际化翻译 | - | - |
| **Day 5** | 测试 + 验证 | 1 天 |
| - 单元测试 | - | - |
| - E2E 测试 | - | - |

---

### 7.3 Phase 2.5: 对比功能

**工期**: 7 个工作日

| 阶段 | 任务 | 工作量 |
|------|------|--------|
| **Day 1-3** | 后端对比 API | 3 天 |
| - `/chipseq/genes/{id}/compare` 端点 | - | - |
| - Overlapping regions 计算 | - | - |
| - Bivalent domain 识别 | - | - |
| **Day 4-6** | 前端对比视图 | 3 天 |
| - CompareCharts 组件 | - | - |
| - 4 种 ECharts 图表 | - | - |
| - Tab 切换逻辑 | - | - |
| **Day 7** | 测试 + 文档 | 1 天 |

---

### 7.4 Phase 3: 所有主要 Marks

**工期**: 按需扩展，每个 mark 约 2 天

- Day 1: 数据导入（1 天）
- Day 2: 前端配置 + 测试（0.5 天）+ 缓冲时间（0.5 天）

---

## 8. 风险与缓解

### 8.1 技术风险

| 风险 | 级别 | 影响 | 缓解措施 |
|------|------|------|----------|
| 数据规模超预期（>1亿 peaks） | 中 | 性能下降 | 分区表 + 物化视图 + 预聚合 |
| 不同 marks 差异字段难以统一 | 低 | 灵活性受限 | JSONB attributes 存储 |
| 前端图表性能瓶颈 | 低 | 渲染卡顿 | ECharts 降采样 + 懒加载 |
| ENCODE 元数据格式不一致 | 中 | 导入失败 | 灵活的元数据解析 + 验证 |
| Bivalent domain 识别算法复杂 | 低 | 功能延迟 | Phase 2.5 可选实现 |

### 8.2 业务风险

| 风险 | 级别 | 影响 | 缓解措施 |
|------|------|------|----------|
| ENCODE 数据获取困难 | 低 | 数据缺失 | 多数据源支持 |
| 用户对多 marks 理解困难 | 中 | 使用率低 | 添加生物学意义说明、推荐 marks |
| 不同物种数据差异大 | 低 | 对比困难 | 标准化组织术语（UBERON/CL） |

### 8.3 开发风险

| 风险 | 级别 | 影响 | 缓解措施 |
|------|------|------|----------|
| 前后端集成问题 | 低 | 进度延迟 | Mock 数据并行开发 |
| 测试覆盖不足 | 中 | Bug 率高 | 单元测试 + E2E 测试 |
| 文档不完善 | 低 | 维护困难 | 同步更新文档 |

---

## 9. 与现有架构的兼容性

### 9.1 与 RepeatMasker 的对比

| 维度 | RepeatMasker | ChIP-seq |
|------|-------------|----------|
| **数据表** | `genomic_features` | `chipseq_peaks` |
| **API 前缀** | `/features/repeats` | `/features/chipseq` |
| **数据量** | 548 万 | 预计 3000 万 |
| **查询模式** | 区域 + 分类 | 区域 + mark + 信号 |
| **前端组件** | RepeatMaskerTable | ChIPSeqPeaksTable |

### 9.2 共享基础设施

| 资源 | 共享方式 |
|------|----------|
| `species` 表 | ✅ 完全共享 |
| `genes` 表 | ✅ 完全共享 |
| `import_batches` 表 | ✅ 完全共享 |
| GeneDetail 页面 | ✅ 不同 Tab |
| IGV 浏览器 | ✅ 不同轨道 |

### 9.3 无冲突验证

✅ **数据库层**: 通过不同的表名和 track_id 区分
✅ **API 层**: 通过不同的端点前缀区分
✅ **前端层**: 通过独立组件和 Tab 区分
✅ **性能**: 分区表策略互不干扰

---

## 10. 总结与建议

### 10.1 核心优势

1. **高度扩展性** ⭐⭐⭐⭐⭐
   - 支持 20-50+ marks，新增 mark 仅需 2 天
   - 配置驱动设计，无需修改核心代码

2. **前后端统一** ⭐⭐⭐⭐⭐
   - API 端点统一，避免端点爆炸
   - 前端组件高度复用，避免重复开发

3. **性能可控** ⭐⭐⭐⭐
   - 分区表 + 物化视图 + 缓存策略
   - 预估支持 6000 万 peaks，查询 <100ms

4. **生物学智能** ⭐⭐⭐⭐
   - 支持 bivalent domain 识别
   - mark 关系建模（antagonistic, synergistic）
   - 自动推荐相关 marks

5. **开发效率** ⭐⭐⭐⭐
   - 初期投入 10 天（架构设计）
   - 后续边际成本极低（2 天/mark）

### 10.2 最终建议

✅ **强烈推荐实施**

理由：
1. 经过 15 轮深度思考和前后端 agent 协同评估
2. 架构设计充分考虑扩展性和灵活性
3. 与现有 RepeatMasker 架构完全兼容
4. 性能评估表明可支持未来 3-5 年的数据增长
5. 开发效率高，后续扩展成本低

### 10.3 实施顺序

1. **Phase 2.3** (10 天): 通用架构 + H3K27me3
2. **Phase 2.4** (5 天): +3 marks (H3K4me1, H3K4me3, H3K27ac)
3. **Phase 2.5** (7 天): 对比功能 + bivalent domain
4. **Phase 3** (按需): 其他 10+ marks（每个 2 天）

### 10.4 下一步行动

如果决定实施，建议按以下顺序启动：

1. ✅ 确认 ENCODE 数据源和预期实验数量
2. ✅ 创建数据库迁移脚本（后端 agent 已提供完整 SQL DDL）
3. ✅ 后端开发启动：Experiment/Peak ORM 模型 → API 端点 → 导入脚本
4. ✅ 前端并行开发：类型定义 → markConfigs → 组件开发
5. ✅ Day 3 联调：前后端集成测试
6. ✅ Day 5 数据导入：导入 H3K27me3 测试数据
7. ✅ Day 10 完成：Phase 2.3 交付

---

## 附录

### 附录 A: 支持的组蛋白修饰列表

| Mark | Category | Function | 生物学意义 |
|------|----------|----------|-----------|
| **H3K27me3** | Repressive | Polycomb repression | 发育基因沉默 |
| **H3K9me3** | Repressive | Heterochromatin | 异染色质形成 |
| **H3K9me2** | Repressive | Gene silencing | 基因沉默 |
| **H4K20me3** | Repressive | DNA damage | DNA 损伤修复 |
| **H3K4me3** | Activating | Active promoter | 活跃启动子 |
| **H3K4me2** | Activating | Promoter activity | 启动子活性 |
| **H3K4me1** | Enhancer | Enhancer priming | 增强子准备 |
| **H3K27ac** | Enhancer | Active enhancer | 活跃增强子 |
| **H3K36me3** | Elongation | Transcription elongation | 转录延伸 |
| **H3K79me2** | Elongation | Transcription elongation | 转录延伸 |
| **H3K9ac** | Activating | Transcription activation | 转录激活 |
| **H3K4ac** | Activating | Promoter activation | 启动子激活 |
| **H2A.Z** | Structural | Nucleosome dynamics | 核小体动态 |
| **H2BK120ub** | Activating | Transcription elongation | 转录延伸 |
| **H4K20me1** | Other | Chromatin compaction | 染色质压缩 |
| **CTCF** | Structural | Chromatin looping | 染色质环化 |

---

### 附录 B: 参考资源

- ENCODE Project: https://www.encodeproject.org/
- UCSC Genome Browser: https://genome.ucsc.edu/
- Roadmap Epigenomics: http://www.roadmapepigenomics.org/
- ChIP-Atlas: https://chip-atlas.org/

---

### 附录 C: 生成的文件列表

#### 后端文件

| 文件 | 路径 | 说明 |
|------|------|------|
| SQL DDL | `frontend/backend/sql/chipseq_schema.sql` | 数据库 Schema |
| ORM 模型 | `frontend/backend/app/models/models.py` | SQLAlchemy 模型 |
| Pydantic Schemas | `frontend/backend/app/schemas/chipseq.py` | API 数据模型 |
| API Router | `frontend/backend/app/routers/chipseq.py` | REST 端点 |
| 导入脚本 | `frontend/backend/scripts/import_chipseq.py` | 数据导入 |
| 配置模板 | `frontend/backend/scripts/chipseq_experiment_template.json` | 导入配置 |

#### 前端文件

| 文件 | 路径 | 说明 |
|------|------|------|
| TypeScript 类型 | `frontend/web/src/types/chipseq.ts` | 类型定义 |
| Mark 配置 | `frontend/web/src/config/markConfigs.ts` | 16 种 marks 配置 |
| API 客户端 | `frontend/web/src/api/chipseq.ts` | API 调用 |
| Custom Hooks | `frontend/web/src/hooks/useChIPSeq.ts` | React Query Hooks |
| 主组件 | `frontend/web/src/components/ChIPSeqPeaksTable/index.tsx` | 主组件 |
| 子组件 | `frontend/web/src/components/ChIPSeqPeaksTable/*.tsx` | 子组件 |
| 国际化 | `frontend/web/src/i18n/locales/*/genes.json` | 中英文翻译 |

---

**文档结束**

**版本**: v1.0
**最后更新**: 2025-12-06
**下次审查**: Phase 2.3 实施完成后
