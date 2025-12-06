# Human LncRNA Atlas 项目文档

## 项目概述

Human LncRNA Atlas 是一个跨物种 LncRNA（长非编码 RNA）调控关系数据库和可视化平台。该项目整合了人类、黑猩猩、猕猴和狨猴四个灵长类物种的 LncRNA 与蛋白编码基因之间的调控关系数据，并提供疾病关联分析功能。

### 核心功能
- **调控关系查询**：支持按物种、基因名、染色体、结合亲和力(BA)等多维度筛选
- **序列数据展示**：展示 LncRNA 和 DNA 靶位点序列
- **疾病关联分析**：关联 GWAS 数据，展示 LncRNA 与疾病/性状的关联
- **网络可视化**：调控关系的交互式网络图展示
- **数据导出**：支持 CSV/XLSX 格式导出

---

## 目录说明

| 目录 | 用途 | 说明 |
|------|------|------|
| `/data/wenyujianData/human-lncrna-atlas-github/` | GitHub 仓库 | 用于版本控制和代码托管，不含数据文件 |
| `/data/wenyujianData/humanLncAtlas/` | 本地运行 | 包含完整数据文件、LongTarget 结果等大文件 |

### 开发工作流程

```bash
# 1. 在 humanLncAtlas 目录进行开发和测试
cd /data/wenyujianData/humanLncAtlas/frontend/backend
python3 -m uvicorn main:app --host 0.0.0.0 --port 8000

# 2. 开发完成后，同步修改的文件到 GitHub 目录
cp -r humanLncAtlas/frontend/backend/app/* human-lncrna-atlas-github/frontend/backend/app/
cp -r humanLncAtlas/frontend/web/src/* human-lncrna-atlas-github/frontend/web/src/
cp humanLncAtlas/docs/project.md human-lncrna-atlas-github/docs/
# ... 根据实际修改的文件同步

# 3. 切换到 GitHub 目录提交
cd /data/wenyujianData/human-lncrna-atlas-github
git add -A && git commit -m "feat/fix/docs: 描述" && git push
```

> **Commit 类型规范**：`feat`(新功能) / `fix`(修复) / `docs`(文档) / `refactor`(重构) / `perf`(性能)

---

## 项目结构

```
human-lncrna-atlas-github/         # GitHub 仓库目录
├── .github/                       # GitHub Actions CI/CD
├── docs/                          # 项目文档
├── etl/                           # 数据导入脚本
│   ├── import_regulations.py      # 调控关系导入
│   ├── import_sequences.py        # 序列数据导入
│   ├── import_ortholog_data.py    # 直系同源基因导入
│   └── import_table15.py          # Table15 疾病数据导入
├── frontend/
│   ├── backend/                   # FastAPI 后端
│   │   ├── app/
│   │   │   ├── core/              # 配置和数据库连接
│   │   │   ├── models/            # SQLAlchemy ORM 模型
│   │   │   ├── routers/           # API 路由
│   │   │   ├── schemas/           # Pydantic 数据模型
│   │   │   └── middleware/        # 中间件（日志、限流）
│   │   ├── tests/                 # 后端测试
│   │   └── main.py                # FastAPI 入口
│   └── web/                       # React 前端
│       ├── src/
│       │   ├── api/               # API 客户端
│       │   ├── components/        # 通用组件
│       │   ├── hooks/             # 自定义 Hooks
│       │   ├── pages/             # 页面组件
│       │   ├── i18n/              # 国际化（中/英）
│       │   └── types/             # TypeScript 类型
│       └── e2e/                   # E2E 测试 (Playwright)
├── schema/                        # 数据库 Schema 和迁移
├── scripts/                       # 运维脚本
└── tests/                         # 集成测试
```

**本地运行目录额外包含**（不上传 GitHub）：
- `*_batch_*.txt` - 源数据文件
- `resultAllLongTarget/` - LongTarget 计算结果
- `allMergedTranscriptSeq/` - 序列文件

---

## 数据库设计

### 数据库信息
- **数据库**: PostgreSQL
- **数据库名**: `lncrna_production`
- **用户**: `amax`
- **主机**: `localhost:5432`

### 数据表结构

| 表名 | 说明 | 记录数 |
|------|------|--------|
| `species` | 物种表 | 4 |
| `genes` | 基因表（物种特异性） | 17,248 |
| `core_genes` | 核心基因表（跨物种唯一标识） | 5,484 |
| `regulations` | 调控关系表 | 804,630 |
| `sequences` | 序列存储表 | 804,630 |
| `traits` | 疾病/性状表 | 273 |
| `trait_gene_associations` | 性状-基因关联表 | 67,763 |
| `ontologies` | 本体/功能分类表 | - |
| `import_batches` | 导入批次表 | - |
| `feature_tracks` | 扩展层轨道配置表 | 1 |
| `genomic_features` | 基因组特征表（分区） | 5,481,341 |

### 物种数据分布

| 物种 | 代码 | 基因数 | 调控关系数 |
|------|------|--------|-----------|
| Human | human | ~5,484 | 496,064 |
| Chimpanzee | chimp | ~6,138 | 156,136 |
| Macaque | macaque | ~5,406 | 102,430 |
| Marmoset | marmoset | ~4,805 | 50,000 |

### 核心表关系

```
species (1) ──< genes (N) ──< regulations (N) ──< sequences (1)
                  │
                  └──> core_genes (1) ──< trait_gene_associations (N) ──> traits
```

---

## 后端 API

### 技术栈
- **框架**: FastAPI
- **ORM**: SQLAlchemy 2.0
- **验证**: Pydantic v2
- **连接池**: QueuePool (pool_size=5, max_overflow=10)

### 主要端点

| 端点 | 方法 | 说明 |
|------|------|------|
| `/api/v1/genes` | GET | 基因列表（分页） |
| `/api/v1/genes/{id}` | GET | 基因详情 |
| `/api/v1/regulations` | GET | 调控关系列表（多条件筛选） |
| `/api/v1/regulations/{id}` | GET | 调控详情（含序列） |
| `/api/v1/regulations/gene/{id}` | GET | 指定基因的调控关系 |
| `/api/v1/stats/overview` | GET | 统计概览 |
| `/api/v1/stats/detailed` | GET | 详细统计（图表数据） |
| `/api/v1/diseases` | GET | 疾病/性状列表 |
| `/api/v1/network/gene/{id}` | GET | 基因网络数据 |
| `/api/v1/admin/metrics` | GET | 系统监控指标（CPU/内存/告警/百分位） |
| `/api/v1/features/tracks` | GET | 扩展层轨道列表 |
| `/api/v1/features/genes/{id}/repeats` | GET | 基因区域 RepeatMasker |
| `/api/v1/features/repeats/{species}/classes` | GET | 重复类型列表 |
| `/api/v1/igv/config/repeatmasker/{species}` | GET | RepeatMasker IGV 轨道配置 |

### 启动命令

```bash
cd /data/wenyujianData/humanLncAtlas/frontend/backend
python3 -m uvicorn main:app --host 0.0.0.0 --port 8000
```

---

## 前端

### 技术栈
- **框架**: React 18 + TypeScript
- **构建**: Vite
- **UI**: Ant Design 5
- **状态**: TanStack Query (React Query)
- **路由**: React Router v6
- **国际化**: i18next（中/英双语）
- **图表**: ECharts
- **网络图**: Cytoscape.js

### 页面结构

| 页面 | 路径 | 说明 |
|------|------|------|
| Home | `/` | 首页概览 |
| Genes | `/genes` | 基因列表 |
| GeneDetail | `/genes/:id` | 基因详情（Tabs: Core Data / Genomic Features） |
| Regulations | `/regulations` | 调控关系列表 |
| Diseases | `/diseases` | 疾病关联 |
| Network | `/network` | 网络可视化 |
| Stats | `/stats` | 统计图表 |
| Monitoring | `/admin/monitoring` | 系统监控仪表板 |

### 关键组件

| 组件 | 路径 | 说明 |
|------|------|------|
| `SequenceViewer` | `components/SequenceViewer.tsx` | 序列查看器（Modal） |
| `LoadingState` | `components/LoadingState.tsx` | 加载状态 |
| `ErrorState` | `components/ErrorState.tsx` | 错误状态 |
| `RepeatMaskerTable` | `components/RepeatMaskerTable/` | RepeatMasker 数据表格 |
| `GenomeBrowser` | `components/GenomeBrowser/` | IGV.js 基因组浏览器 |

### 启动命令

```bash
cd /data/wenyujianData/humanLncAtlas/frontend/web
npm run dev -- --host 0.0.0.0
```

### 访问地址
- 本地: http://localhost:5173
- 内网: http://192.168.6.135:5173

---

## 数据导入流程

### 1. 调控关系导入
```bash
cd /data/wenyujianData/humanLncAtlas/etl
python3 import_regulations.py
```

数据源文件：
- `human_batch_human.txt` - Human 数据 (BA>=50)
- `chimp_batch_BA50.txt` - Chimpanzee 数据
- `macaque_batch_BA50.txt` - Macaque 数据
- `marmoset_batch_BA50.txt` - Marmoset 数据

### 2. 序列数据导入
```bash
python3 import_sequences.py
```

关键逻辑：
- 通过 (lncrna_gene_id, target_gene_id, lncrna_start, lncrna_end, dna_start, dna_end) 匹配 regulation
- 支持基因 ID 版本号灵活匹配（ENSG00000129484.9 → ENSG00000129484）
- 支持物种后缀处理（CATG00000016469.1_marmoset → CATG00000016469.1）

### 3. 疾病关联导入
```bash
python3 import_table15.py
```

### 4. RepeatMasker 导入 (Phase 2.1)
```bash
# 下载 UCSC RepeatMasker 数据
wget https://hgdownload.gi.ucsc.edu/goldenPath/hg19/database/rmsk.txt.gz
gunzip rmsk.txt.gz

# 导入数据（约 4 分钟）
python3 import_ucsc_rmsk.py rmsk.txt --batch-size 50000
```

数据来源：UCSC Genome Browser hg19 RepeatMasker (5,481,341 条)

---

## 配置说明

### 后端配置 (`backend/app/core/config.py`)

```python
DATABASE_HOST = "localhost"
DATABASE_PORT = 5432
DATABASE_USER = "amax"
DATABASE_PASSWORD = ""
DATABASE_NAME = "lncrna_production"
```

### 前端配置 (`web/src/config/constants.ts`)

```typescript
export const API_BASE_URL = '/api/v1'
export const EXPORT_LIMITS = {
  MAX_FRONTEND: 100000,  // 前端导出限制
  WARNING_THRESHOLD: 10000
}
```

---

## 常见操作

### 重启后端
```bash
pkill -f "uvicorn main:app"
cd /data/wenyujianData/humanLncAtlas/frontend/backend
nohup python3 -m uvicorn main:app --host 0.0.0.0 --port 8000 > /tmp/backend.log 2>&1 &
```

### 重启前端
```bash
pkill -f "vite"
cd /data/wenyujianData/humanLncAtlas/frontend/web
nohup npm run dev -- --host 0.0.0.0 > /tmp/frontend.log 2>&1 &
```

### 检查服务状态
```bash
ps aux | grep -E "(uvicorn|vite)" | grep -v grep
```

### 查看数据库统计
```bash
PGPASSWORD="" psql -h localhost -U amax -d lncrna_production -c "
SELECT
    s.species_code,
    COUNT(DISTINCT r.regulation_id) as regulations,
    COUNT(DISTINCT seq.sequence_id) as sequences
FROM species s
LEFT JOIN regulations r ON s.species_id = r.species_id
LEFT JOIN sequences seq ON r.regulation_id = seq.regulation_id
GROUP BY s.species_id, s.species_code
"
```

---

## 更新日志

详细更新记录见 `docs/changelog/` 目录：

| 日期 | 主要内容 | 文件 |
|------|----------|------|
| 2025-12-05 | **Phase 2.1 RepeatMasker 扩展层**、548 万条数据导入 | [2025-12-05.md](changelog/2025-12-05.md) |
| 2025-12-03 | **IGV.js 基因组浏览器集成**、FANTOM CAT 基因轨道 | [2025-12-03.md](changelog/2025-12-03.md) |
| 2025-12-02 | **监控仪表板**、分页索引优化、前端缓存 | [2025-12-02.md](changelog/2025-12-02.md) |
| 2025-12-01 | E2E 测试框架、Redis 缓存、代码审查 | [2025-12-01.md](changelog/2025-12-01.md) |
| 2024-12-01 | 序列展示、性能优化 | [2024-12-01.md](changelog/2024-12-01.md) |

---

## 测试

### 测试覆盖

| 类型 | 框架 | 测试数 | 路径 |
|------|------|--------|------|
| 后端 API 合同测试 | pytest + httpx | 14 | `frontend/backend/tests/test_api_contracts.py` |
| 前端单元测试 | Vitest | 6 | `frontend/web/src/**/*.test.tsx` |
| 前端 E2E 测试 | Playwright | 14 | `frontend/web/e2e/*.spec.ts` |
| **总计** | | **34** | |

### 运行测试

```bash
# 一键运行所有测试（需要服务已启动）
./scripts/run-tests.sh all

# 仅运行后端测试
./scripts/run-tests.sh backend

# 仅运行前端单元测试
./scripts/run-tests.sh unit

# 仅运行 E2E 测试
./scripts/run-tests.sh e2e

# 或分别运行
cd frontend/backend && pytest tests/test_api_contracts.py -v
cd frontend/web && npm run test:run
cd frontend/web && npm run test:e2e
```

### CI/CD

- GitHub Actions 配置: `.github/workflows/test.yml`
- 触发条件: push/PR 到 main/master/develop 分支
- 包含: 单元测试、Lint、构建检查

---

## 待办事项

### 数据侧
- [x] 检查 203 条空 DNA 序列是否可从其他来源补充 ✅ (2025-12-02 完成：从 8chimpManualProPromoterSeq 目录补充)

### 前端体验
- [x] 为 Network 页和 Regulations 列表加加载/空态/错误提示 ✅ (2025-12-02 验收)
- [x] 补一个序列查看的复制/下载入口 ✅ (2025-12-02 完成 FASTA 下载)
- [x] 检查大分页滚动性能 ✅ (2025-12-02 验收：服务端分页 + 预加载)

### 性能与缓存
- [x] 为高频查询添加 Redis 缓存 ✅ (2025-12-01 完成)
- [x] 确认分页排序字段覆盖索引 ✅ (2025-12-02 完成)

### 回归与监控
- [x] 补前端 E2E 或 API 合同测试 ✅ (2025-12-01 完成)
- [x] 简化日志/metrics 为可视化看板 ✅ (2025-12-02 完成：完整监控仪表板)

### 文档与运维
- [x] 完善一键启动脚本 ✅ (2025-12-02 完成：scripts/start.sh + stop.sh)
- [x] 记录常见查询示例与数据字典 ✅ (2025-12-02 验收：DATABASE_DESIGN_FINAL.md + API_GUIDE.md)

---

## 下一步规划

### Phase 2.3: ChIP-seq Epigenetic Marks（架构设计完成）⭐

**状态**: 架构设计完成，所有代码和文档已交付，等待实施

**核心特性**:
- ✅ 通用架构设计，支持 **15+ 种组蛋白修饰** (H3K27me3, H3K4me1, H3K4me3, H3K27ac 等)
- ✅ 配置驱动 UI，新增 mark 仅需 2 天（vs 单一设计的 10 天）
- ✅ 前后端完整代码生成（21+ 个文件，~240 KB）
- ✅ Bivalent domain 识别（H3K27me3 + H3K4me3 重叠区域）
- ✅ 多 marks 对比功能

**交付文档**:
- `PHASE_2.3_CHIPSEQ_ARCHITECTURE.md` - 完整架构设计（41 KB）
- `PHASE_2.3_IMPLEMENTATION_CHECKLIST.md` - 逐步实施指南（18 KB）
- `QUICKSTART_CHIPSEQ.md` - 快速开始指南（11 KB）
- `PHASE_2.3_DELIVERY_SUMMARY.md` - 交付总结（20 KB）
- `PHASE_2.3_ARCHITECTURE_VISUAL.md` - 可视化架构图

**预计工期**: 10 个工作日（首个 mark），后续每个 mark 仅需 2 天

### Phase 2.4: 多 Marks 验证（✅ 已完成 2025-12-06）
- ✅ 导入 ENCODE K562 真实数据（6 种 marks，422,649 peaks）
  - H3K4me1: 125,713 peaks
  - H3K27me3: 88,069 peaks
  - H3K27ac: 58,937 peaks
  - H3K36me3: 54,277 peaks
  - H3K4me3: 52,422 peaks
  - H3K9me3: 43,231 peaks
- ✅ 验证通用架构的扩展性
- ✅ IGV ChIP-seq 轨道集成

### Phase 2.5: 高级对比功能（规划中）
- 实现多 marks 对比 API
- 4 种 ECharts 对比图表
- Overlapping regions + Bivalent domain 可视化
- 预计工期: 7 天

---

## 联系信息

项目路径: `/data/wenyujianData/humanLncAtlas`
