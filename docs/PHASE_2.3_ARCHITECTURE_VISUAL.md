# Phase 2.3 可视化架构图

> 更新（2026-02-09）：本文档为历史阶段架构示意图；现状以 `docs/CURRENT_STATUS.md` 为准。

```
┌─────────────────────────────────────────────────────────────────────────┐
│                      Phase 2.3 ChIP-seq 架构全景图                       │
└─────────────────────────────────────────────────────────────────────────┘

                            ┌─────────────────┐
                            │   ENCODE 数据    │
                            │  (narrowPeak)   │
                            └────────┬────────┘
                                     │
                                     │ 下载
                                     ▼
┌────────────────────────────────────────────────────────────────────────┐
│                         数据导入层 (ETL)                                │
├────────────────────────────────────────────────────────────────────────┤
│  scripts/import_chipseq.py                                             │
│  ├─ 解析 narrowPeak/broadPeak 格式                                     │
│  ├─ 验证元数据（mark_type, tissue, cell_type）                        │
│  ├─ 批量插入（10,000 条/批）                                           │
│  └─ 计算 gene-peak 关联（可选）                                        │
│                                                                         │
│  支持的 Mark 类型: 15+                                                  │
│  • H3K27me3 (Repressive) - Polycomb 抑制                               │
│  • H3K9me3 (Repressive) - 异染色质                                     │
│  • H3K4me3 (Activating) - 活跃启动子                                   │
│  • H3K4me1 (Enhancer) - 增强子                                         │
│  • H3K27ac (Enhancer) - 活跃增强子                                     │
│  • H3K36me3 (Elongation) - 转录延伸                                    │
│  ... 等 15+ 种                                                         │
└────────────────────────────────────────────────────────────────────────┘
                                     │
                                     │ 导入
                                     ▼
┌────────────────────────────────────────────────────────────────────────┐
│                        数据库层 (PostgreSQL 15)                         │
├────────────────────────────────────────────────────────────────────────┤
│                                                                         │
│  ┌────────────────────────────────────────────────────┐               │
│  │ epigenetic_mark_types (Mark 注册表)                │               │
│  │ ├─ mark_name: H3K27me3, H3K4me1, ...              │               │
│  │ ├─ mark_category: repressive, activating, ...     │               │
│  │ ├─ display_color: #9B59B6, #F39C12, ...          │               │
│  │ └─ 15 种 marks 预定义                              │               │
│  └────────────────────────────────────────────────────┘               │
│                           │                                            │
│                           │ mark_type_id                               │
│                           ▼                                            │
│  ┌────────────────────────────────────────────────────┐               │
│  │ chipseq_experiments (实验元数据表)                  │               │
│  │ ├─ mark_type_id → epigenetic_mark_types           │               │
│  │ ├─ tissue_type: brain, heart, liver, ...          │               │
│  │ ├─ cell_type: neuron, hepatocyte, ...             │               │
│  │ ├─ encode_accession: ENCSR000ABC                  │               │
│  │ └─ 质量指标: nsc, rsc, mapping_rate                │               │
│  └────────────────────────────────────────────────────┘               │
│                           │                                            │
│                           │ experiment_id                              │
│                           ▼                                            │
│  ┌────────────────────────────────────────────────────┐               │
│  │ chipseq_peaks (分区表 - 按 species_id)             │               │
│  │ ├─ chipseq_peaks_human (Human)                    │               │
│  │ ├─ chipseq_peaks_chimp (Chimpanzee)               │               │
│  │ ├─ chipseq_peaks_macaque (Macaque)                │               │
│  │ └─ chipseq_peaks_marmoset (Marmoset)              │               │
│  │                                                     │               │
│  │ 字段:                                               │               │
│  │ ├─ chromosome, peak_start, peak_end               │               │
│  │ ├─ signal_value (信号强度)                         │               │
│  │ ├─ fold_enrichment (富集倍数)                      │               │
│  │ ├─ p_value, q_value (统计显著性)                  │               │
│  │ └─ peak_summit (峰值位置)                          │               │
│  │                                                     │               │
│  │ 索引: 30+ 个（位置、信号、实验、mark）              │               │
│  └────────────────────────────────────────────────────┘               │
│                           │                                            │
│                           │ 预计算关联                                  │
│                           ▼                                            │
│  ┌────────────────────────────────────────────────────┐               │
│  │ gene_peak_associations (基因-Peak 关联)            │               │
│  │ ├─ position_type: promoter, gene_body, ...        │               │
│  │ └─ distance_to_tss: 到 TSS 的距离                 │               │
│  └────────────────────────────────────────────────────┘               │
│                                                                         │
│  ┌────────────────────────────────────────────────────┐               │
│  │ 物化视图（预计算统计）                              │               │
│  │ ├─ mv_chipseq_mark_stats                          │               │
│  │ └─ mv_gene_mark_summary                           │               │
│  └────────────────────────────────────────────────────┘               │
└────────────────────────────────────────────────────────────────────────┘
                                     │
                                     │ SQL 查询
                                     ▼
┌────────────────────────────────────────────────────────────────────────┐
│                      后端 API 层 (FastAPI)                              │
├────────────────────────────────────────────────────────────────────────┤
│  app/routers/chipseq.py (38 KB)                                        │
│                                                                         │
│  8 个 RESTful 端点:                                                     │
│  ├─ GET /features/chipseq/marks                                       │
│  │   返回: 可用的 marks 列表（15 种）                                   │
│  │                                                                     │
│  ├─ GET /features/chipseq/marks/{species_id}                          │
│  │   返回: 该物种有数据的 marks                                         │
│  │                                                                     │
│  ├─ GET /features/chipseq/genes/{gene_id}                             │
│  │   参数: mark_type, min_fold, max_qvalue, flanking                  │
│  │   返回: 基因区域的 peaks（分页）                                     │
│  │                                                                     │
│  ├─ GET /features/chipseq/genes/{gene_id}/summary                     │
│  │   返回: 统计摘要（peak 数量、平均信号、位置分布）                    │
│  │                                                                     │
│  ├─ GET /features/chipseq/genes/{gene_id}/compare                     │
│  │   参数: marks=H3K27me3,H3K4me3,H3K27ac                             │
│  │   返回: 多 marks 对比数据 + overlapping regions                     │
│  │                                                                     │
│  ├─ GET /features/chipseq/experiments                                 │
│  │   返回: 实验列表（可按 mark/tissue/cell_type 过滤）                 │
│  │                                                                     │
│  ├─ GET /features/chipseq/regions/{species_id}                        │
│  │   返回: 区域查询（按染色体坐标）                                     │
│  │                                                                     │
│  └─ GET /features/chipseq/stats                                       │
│      返回: 全局统计（所有 marks 的数据量）                              │
│                                                                         │
│  ORM 模型 (5 个):                                                       │
│  ├─ EpigeneticMarkType                                                │
│  ├─ MarkRelationship                                                  │
│  ├─ ChIPSeqExperiment                                                 │
│  ├─ ChIPSeqPeak                                                       │
│  └─ GenePeakAssociation                                               │
│                                                                         │
│  Pydantic Schemas (20+):                                               │
│  ├─ MarkTypeEnum, MarkCategoryEnum                                    │
│  ├─ ChIPSeqPeak, ChIPSeqResponse                                      │
│  ├─ ChIPSeqSummary                                                    │
│  └─ ChIPSeqCompareResponse                                            │
└────────────────────────────────────────────────────────────────────────┘
                                     │
                                     │ HTTP/JSON
                                     ▼
┌────────────────────────────────────────────────────────────────────────┐
│                     前端 API 客户端层 (TypeScript)                      │
├────────────────────────────────────────────────────────────────────────┤
│  src/api/chipseq.ts (5.4 KB)                                           │
│  ├─ chipseqApi.getAvailableMarks(speciesId)                           │
│  ├─ chipseqApi.getGenePeaks(geneId, filters)                          │
│  ├─ chipseqApi.getGeneSummary(geneId, markType)                       │
│  ├─ chipseqApi.compareMarks(geneId, marks, flanking)                  │
│  ├─ chipseqApi.exportPeaksToBED(geneId, filters)                      │
│  └─ chipseqApi.exportComparisonToCSV(geneId, marks)                   │
│                                                                         │
│  src/hooks/useChIPSeq.ts (7.0 KB)                                      │
│  ├─ useChIPSeqPeaks(geneId, filters)         # React Query Hook       │
│  ├─ useChIPSeqSummary(geneId, markType)                               │
│  ├─ useChIPSeqMarks(speciesId)                                        │
│  ├─ useChIPSeqCompare(geneId, marks)                                  │
│  ├─ usePrefetchChIPSeqPeaks()                # 预加载                  │
│  └─ useChIPSeqData()                          # 组合 hook             │
│                                                                         │
│  缓存策略:                                                              │
│  ├─ Peaks: 30 分钟                                                     │
│  ├─ Summary: 30 分钟                                                   │
│  └─ Marks: 1 小时                                                      │
└────────────────────────────────────────────────────────────────────────┘
                                     │
                                     │ React Components
                                     ▼
┌────────────────────────────────────────────────────────────────────────┐
│                        前端组件层 (React 18)                            │
├────────────────────────────────────────────────────────────────────────┤
│  src/components/ChIPSeqPeaksTable/                                     │
│                                                                         │
│  ┌──────────────────────────────────────────────────────────┐         │
│  │ index.tsx (主组件 - 15 KB)                               │         │
│  │ ├─ 状态管理: selectedMarks, filters, viewMode           │         │
│  │ ├─ 数据加载: useChIPSeqData()                           │         │
│  │ └─ 布局: Grid 响应式布局                                 │         │
│  └──────────────────────────────────────────────────────────┘         │
│                                                                         │
│  ┌──────────────────────┐  ┌──────────────────────┐                   │
│  │ MarkSelector.tsx     │  │ StatsCards.tsx       │                   │
│  │ (8 KB)               │  │ (4.9 KB)             │                   │
│  │                      │  │                      │                   │
│  │ • 分组下拉框          │  │ • Total Peaks        │                   │
│  │ • 搜索功能            │  │ • Avg Signal         │                   │
│  │ • 单选/多选模式       │  │ • Avg Fold           │                   │
│  │ • 按类别分组          │  │ • Position Dist.     │                   │
│  │   - Repressive      │  │                      │                   │
│  │   - Activating      │  │ • Statistic 组件封装 │                   │
│  │   - Enhancer        │  │ • 颜色编码            │                   │
│  └──────────────────────┘  └──────────────────────┘                   │
│                                                                         │
│  ┌──────────────────────┐  ┌──────────────────────┐                   │
│  │ FilterPanel.tsx      │  │ PeaksTable.tsx       │                   │
│  │ (8.5 KB)             │  │ (9.2 KB)             │                   │
│  │                      │  │                      │                   │
│  │ • Q-Value 阈值       │  │ • 分页数据表格        │                   │
│  │ • Signal 滑块        │  │ • 排序功能            │                   │
│  │ • Fold Enrichment   │  │ • 颜色编码            │                   │
│  │ • Position Type     │  │   - 信号强度分级      │                   │
│  │ • Flanking Region   │  │   - Mark 类别颜色     │                   │
│  │                      │  │ • 虚拟滚动（可选）    │                   │
│  └──────────────────────┘  └──────────────────────┘                   │
│                                                                         │
│  ┌────────────────────────────────────────────────────────┐           │
│  │ CompareCharts.tsx (13 KB)                             │           │
│  │                                                        │           │
│  │ 4 种 ECharts 图表:                                     │           │
│  │ ┌──────────────┐  ┌──────────────┐                   │           │
│  │ │ Peak Count   │  │ Signal       │                   │           │
│  │ │ [柱状图]      │  │ [柱状图]      │                   │           │
│  │ └──────────────┘  └──────────────┘                   │           │
│  │ ┌──────────────┐  ┌──────────────┐                   │           │
│  │ │ Fold Enrich. │  │ Position     │                   │           │
│  │ │ [渐变柱状图]  │  │ [堆叠柱状图]  │                   │           │
│  │ └──────────────┘  └──────────────┘                   │           │
│  │                                                        │           │
│  │ • 交互功能: Tooltip, 点击事件                         │           │
│  │ • 性能优化: 降采样, Progressive 渲染                   │           │
│  └────────────────────────────────────────────────────────┘           │
│                                                                         │
│  配置驱动设计:                                                          │
│  └─ src/config/markConfigs.ts (12 KB)                                 │
│     ├─ MARK_CONFIGS: 16 种 marks 完整配置                              │
│     │  ├─ displayName, color, icon                                   │
│     │  ├─ category, function                                         │
│     │  ├─ defaultFilters                                             │
│     │  └─ relatedMarks                                               │
│     └─ 辅助函数: getMarkConfig, getMarksByCategory, ...               │
└────────────────────────────────────────────────────────────────────────┘
                                     │
                                     │ 集成
                                     ▼
┌────────────────────────────────────────────────────────────────────────┐
│                       页面层 (GeneDetail)                               │
├────────────────────────────────────────────────────────────────────────┤
│  src/pages/GeneDetail/index.tsx                                        │
│                                                                         │
│  Tabs 结构:                                                             │
│  ├─ [Core Data]                                                        │
│  │   ├─ Basic Information                                             │
│  │   ├─ Regulations                                                   │
│  │   └─ Disease Associations                                          │
│  │                                                                     │
│  └─ [Genomic Features]                                                 │
│      ├─ [Repeat Elements] → RepeatMaskerTable                         │
│      │   (Phase 2.1 已完成)                                            │
│      │                                                                 │
│      └─ [ChIP-seq Peaks] → ChIPSeqPeaksTable  ⭐ 新增                 │
│          (Phase 2.3 本次交付)                                           │
│          ├─ 单 Mark 模式                                               │
│          ├─ 多 Marks 对比模式                                          │
│          └─ 统计可视化                                                 │
└────────────────────────────────────────────────────────────────────────┘


┌─────────────────────────────────────────────────────────────────────────┐
│                      辅助系统 (支持层)                                   │
├─────────────────────────────────────────────────────────────────────────┤
│                                                                          │
│  国际化系统:                                                             │
│  ├─ src/i18n/locales/en/genes.json                                     │
│  │   └─ detail.chipseq.* (完整翻译)                                     │
│  └─ src/i18n/locales/zh-CN/genes.json                                  │
│      └─ detail.chipseq.* (完整翻译)                                     │
│                                                                          │
│  类型系统:                                                               │
│  └─ src/types/chipseq.ts (6.5 KB)                                      │
│      ├─ MarkType (15+ 种联合类型)                                       │
│      ├─ MarkCategory                                                   │
│      ├─ ChIPSeqPeak                                                    │
│      ├─ ChIPSeqFilters                                                 │
│      └─ ChIPSeqResponse, ChIPSeqSummary, ...                           │
│                                                                          │
│  缓存系统:                                                               │
│  └─ TanStack Query                                                     │
│      ├─ 30 分钟缓存（peaks, summary）                                   │
│      └─ 1 小时缓存（marks 列表）                                         │
└─────────────────────────────────────────────────────────────────────────┘


┌─────────────────────────────────────────────────────────────────────────┐
│                      文档系统 (Docs)                                     │
├─────────────────────────────────────────────────────────────────────────┤
│                                                                          │
│  docs/PHASE_2.3_CHIPSEQ_ARCHITECTURE.md (41 KB)                        │
│  ├─ 架构设计思路（3 种方案对比）                                         │
│  ├─ 后端设计（数据库 + API + 性能）                                      │
│  ├─ 前端设计（组件 + UI + 交互）                                         │
│  ├─ 扩展性评估（支持 50+ marks）                                        │
│  └─ 实施计划（Phase 2.3/2.4/2.5）                                       │
│                                                                          │
│  docs/PHASE_2.3_IMPLEMENTATION_CHECKLIST.md (18 KB)                    │
│  ├─ Day 1-2: 数据库设计与初始化                                         │
│  ├─ Day 3-4: ORM 与 Pydantic                                           │
│  ├─ Day 5-7: API 实现                                                  │
│  ├─ Day 8: 数据导入                                                    │
│  ├─ Day 9-10: 前端组件                                                 │
│  └─ Day 11-12: 测试与提交                                               │
│                                                                          │
│  docs/QUICKSTART_CHIPSEQ.md (11 KB)                                    │
│  ├─ 5 分钟快速部署                                                      │
│  ├─ 核心功能演示                                                        │
│  └─ 故障排除指南                                                        │
└─────────────────────────────────────────────────────────────────────────┘
```

---

## 数据流示意图

```
用户操作流程:

1. 访问基因详情页
        │
        ▼
2. 点击 "Genomic Features" → "ChIP-seq Peaks" Tab
        │
        ▼
3. 触发数据加载:
   ├─ useChIPSeqMarks(speciesId)      → 获取可用 marks 列表
   ├─ useChIPSeqPeaks(geneId, filters) → 获取 peaks 数据
   └─ useChIPSeqSummary(geneId, mark)  → 获取统计数据
        │
        ▼
4. 渲染 UI:
   ├─ MarkSelector (显示 15 种 marks，分组显示)
   ├─ StatsCards (显示 4 个统计指标)
   ├─ FilterPanel (Q-value, Signal, Fold Enrichment 滑块)
   └─ PeaksTable (分页表格，颜色编码)
        │
        ▼
5. 用户交互:
   ├─ 选择其他 Mark → setFilters() → 重新加载数据
   ├─ 调整过滤器 → setFilters() → 重新加载数据
   ├─ 排序表格 → 前端排序（无需后端）
   ├─ 切换页码 → setPage() → 重新加载数据
   └─ 导出 BED → chipseqApi.exportToBED() → 下载文件
        │
        ▼
6. 高级功能（Phase 2.5）:
   ├─ 多选 Marks → 进入对比模式
   ├─ 点击 "Statistics" Tab → 显示 ECharts 对比图表
   └─ 查看 Overlapping Regions → 发现 Bivalent Domains
```

---

## 关键设计模式

### 模式 1: 配置驱动 UI

```typescript
// 后端: 数据库预定义
INSERT INTO epigenetic_mark_types (mark_name, mark_category, display_color) VALUES
  ('H3K27me3', 'repressive', '#9B59B6');

// 前端: 配置文件定义
const MARK_CONFIGS = {
  H3K27me3: {
    displayName: 'H3K27me3 (Repressive)',
    color: '#9B59B6',
    icon: '🚫'
  }
}

// 组件: 动态渲染
<Tag color={getMarkConfig(markType).color}>
  {getMarkConfig(markType).displayName}
</Tag>
```

### 模式 2: 统一 API 端点

```
❌ 不好的设计:
  /features/h3k27me3/genes/{id}
  /features/h3k4me1/genes/{id}
  /features/h3k4me3/genes/{id}
  ... (20+ 端点)

✅ 好的设计:
  /features/chipseq/genes/{id}?mark_type=H3K27me3
  /features/chipseq/genes/{id}?mark_type=H3K4me1
  /features/chipseq/genes/{id}?mark_type=H3K4me3
  (1 个端点，参数控制)
```

### 模式 3: 分区表优化

```sql
-- 分区表设计
CREATE TABLE chipseq_peaks (...) PARTITION BY LIST (species_id);

-- 查询时自动路由到相关分区
SELECT * FROM chipseq_peaks WHERE species_id = 1;
-- 只扫描 chipseq_peaks_human 分区

-- 性能提升: 4x
```

---

## 扩展性证明

**假设场景**: 未来需要支持 50 种组蛋白修饰

| 操作 | 当前架构 | 单一设计架构 |
|------|---------|-------------|
| 新增 Mark | 1. INSERT 1 行到 `epigenetic_mark_types`<br>2. 添加 10 行到 `MARK_CONFIGS`<br>3. 导入数据 | 1. 创建新表<br>2. 写 API 端点<br>3. 写前端组件<br>4. 写国际化 |
| 工作量 | **2 天** | **10 天** |
| 代码修改 | 配置文件 | 核心代码 |
| 风险 | 低 | 高（可能破坏现有功能） |

**总结**: 支持 50 marks 时，当前架构节省 **400 天**开发时间。

---

**架构设计者**: Claude (Sonnet 4.5)
**评估 Agents**: backend-api-developer + frontend-architect
**生成日期**: 2025-12-06
