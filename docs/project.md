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

## 项目结构

```
/data/wenyujianData/humanLncAtlas/
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
│   │   └── main.py                # FastAPI 入口
│   └── web/                       # React 前端
│       └── src/
│           ├── api/               # API 客户端
│           ├── components/        # 通用组件
│           ├── hooks/             # 自定义 Hooks
│           ├── pages/             # 页面组件
│           ├── i18n/              # 国际化（中/英）
│           └── types/             # TypeScript 类型
├── *_batch_*.txt                  # 源数据文件
└── resultAllLongTarget/           # LongTarget 计算结果
```

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
| GeneDetail | `/genes/:id` | 基因详情（含调控关系和序列） |
| Regulations | `/regulations` | 调控关系列表 |
| Diseases | `/diseases` | 疾病关联 |
| Network | `/network` | 网络可视化 |
| Stats | `/stats` | 统计图表 |

### 关键组件

| 组件 | 路径 | 说明 |
|------|------|------|
| `SequenceViewer` | `components/SequenceViewer.tsx` | 序列查看器（Modal） |
| `LoadingState` | `components/LoadingState.tsx` | 加载状态 |
| `ErrorState` | `components/ErrorState.tsx` | 错误状态 |

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

### 2025-12-01 测试框架与 Redis 缓存

#### 🧪 E2E 测试框架

新增完整的测试基础设施，覆盖 34 个测试用例：

| 类型 | 框架 | 测试数 | 文件 |
|------|------|--------|------|
| 后端 API 合同测试 | pytest + httpx | 14 | `tests/conftest.py`, `tests/test_api_contracts.py` |
| 前端 E2E 测试 | Playwright | 14 | `e2e/genes-flow.spec.ts`, `e2e/regulations-flow.spec.ts` |
| 前端单元测试 | Vitest | 6 | 已有 |

**新增文件**:
- `frontend/backend/tests/conftest.py` - pytest fixtures 和 Schema 验证工具
- `frontend/backend/tests/test_api_contracts.py` - API 合同测试
- `frontend/web/playwright.config.ts` - Playwright 配置
- `frontend/web/e2e/genes-flow.spec.ts` - 基因浏览流程测试
- `frontend/web/e2e/regulations-flow.spec.ts` - 调控关系流程测试
- `.github/workflows/test.yml` - CI/CD 配置
- `scripts/run-tests.sh` - 一键测试脚本

#### 🚀 Redis 缓存优化

实现 Redis 缓存层，显著提升高频 API 性能：

| API | 无缓存 | 有缓存 | 提升 |
|-----|--------|--------|------|
| `/stats/overview` | 242ms | 21ms | **11x** |
| `/stats/ba-range` | ~150ms | ~5ms | **30x** |

**缓存策略**:
| 数据类型 | TTL | 说明 |
|----------|-----|------|
| 统计概览 | 1 小时 | 数据变化频率极低 |
| BA 范围 | 1 小时 | 几乎不变 |
| 列表数据 | 5 分钟 | 按查询参数缓存 |

**修改文件**:
- `frontend/backend/app/core/cache.py` - 重写为 Redis + 内存回退双层缓存
- `frontend/backend/app/routers/stats.py` - 添加缓存支持

**新增 API**:
- `GET /api/v1/stats/cache-status` - 查看缓存状态和命中率

---

### 2025-12-01 代码审查与数据质量核查

#### 🔴 高优先级 Bug 修复

| 问题 | 文件 | 修复说明 |
|------|------|----------|
| SQL LIKE 模式特殊字符未转义 | `regulations.py`, `genes.py`, `diseases.py` | 添加 `escape_like_pattern()` 函数，防止 `%` `_` 被误解析为通配符 |
| CSV 导出公式注入风险 | `export.ts`, `Network/index.tsx` | 以 `=+\-@\t\r` 开头的字符串前添加单引号防护 |
| BA 分布直方图 N+1 查询 | `stats.py:331-366` | 从 N 次循环查询优化为单次 GROUP BY，性能提升 10x+ |
| Network 接口路径不匹配 | `network.py:242` | `/gene/{id}/network` → `/gene/{id}`，与前端一致 |

#### 🟡 中优先级优化

| 问题 | 文件 | 修复说明 |
|------|------|----------|
| 基因名后缀处理逻辑错误 | `genes.py:112-119` | 使用 `endswith` 替代 `split`，避免截断 `TP53_AS1` 等含下划线基因名 |
| 相关子查询性能问题 | `diseases.py:191-229` | 使用 `DISTINCT ON` 子查询 + LEFT JOIN 替代相关子查询 |
| 多个独立 COUNT 查询 | `genes.py`, `diseases.py`, `network.py` | 使用 CASE WHEN 合并为单次查询 |
| 函数内部导入 | `network.py` | `Species`, `Counter`, `case`, `or_` 移至文件顶部 |
| datetime.utcnow 弃用 | `models.py` | 添加 `utc_now()` 函数，兼容 Python 3.12+ |
| 数据类型不一致 | `models.py:152-153` | `lncrna_start/end` 从 Integer 改为 BigInteger |
| 统计概览物种列表未排序 | `stats.py:84` | 添加 `order_by(Species.species_id)` 保证稳定顺序 |

#### 🟢 ETL 脚本优化

| 问题 | 文件 | 修复说明 |
|------|------|----------|
| 基因缓存检查效率低 | `import_regulations.py` | 添加 `_loaded_species` Set，O(1) 替代 O(n) 检查 |
| 事务边界注释不清晰 | `import_table15.py` | 更新注释准确描述事务行为 |

#### ✨ 新功能

| 功能 | 文件 | 说明 |
|------|------|------|
| 序列可用性标记 | `schemas/regulation.py`, `routers/regulations.py` | API 返回 `lncrna_sequence_available`、`dna_sequence_available`、`sequence_unavailable_reason` 字段 |

#### 📊 数据质量核查结果

**数据库统计** (2025-12-01):
| 表 | 记录数 | 状态 |
|----|--------|------|
| species | 4 | ✅ |
| core_genes | 5,484 | ✅ |
| genes | 17,248 | ✅ |
| regulations | 804,630 | ✅ |
| sequences | 804,630 | ✅ |
| traits | 273 | ✅ |
| ontologies | 135 | ✅ |
| trait_gene_associations | 67,763 | ✅ |

**数据质量指标**:
- ✅ 空 lncRNA 序列: 0
- ⚠️ 空 DNA 序列: 203 (0.025%) - 均位于黑猩猩未定位 scaffold (`*_random`)
- ✅ 孤立调控关系: 0
- ✅ 孤立疾病关联: 0
- ✅ 唯一 lncRNA-target 组合: 581,348
- ✅ BA 范围: 50.0 - 756.0

**多结合位点说明**:
- 804,630 条调控记录对应 581,348 个唯一 (lncRNA, target, species) 组合
- 这是正常的生物学特征：同一 lncRNA-target 对在基因组不同位置有多个结合位点
- 每条记录有独特的位置坐标 (lncrna_start/end, dna_start/end) 和 BA 值

---

### 2024-12-01 (历史记录)

#### 新增功能
- **序列数据展示**：在 GeneDetail 页面添加"查看序列"功能
- **SequenceViewer 组件**：支持 LncRNA/DNA 序列展示和复制

#### Bug 修复
- 修复 clipboard API 错误处理
- 修复 regulations router 中未使用变量
- 优化 N+1 查询问题（4次查询 → 1次 JOIN）
- 修复分页逻辑重复状态更新
- 修复 Sequence 关系定义 (uselist=False)

#### 性能优化
- 使用 LEFT JOIN 替代标量子查询
- 配置 QueuePool 连接池
- 添加查询排序确保分页稳定

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
- [ ] 检查 203 条空 DNA 序列是否可从其他来源补充

### 前端体验
- [ ] 为 Network 页和 Regulations 列表加加载/空态/错误提示
- [ ] 补一个序列查看的复制/下载入口
- [ ] 检查大分页滚动性能

### 性能与缓存
- [ ] 为高频查询添加 Redis 缓存
- [ ] 确认分页排序字段覆盖索引

### 回归与监控
- [x] 补前端 E2E 或 API 合同测试 ✅ (2025-12-01 完成)
- [ ] 简化日志/metrics 为可视化看板

### 文档与运维
- [ ] 完善一键启动脚本
- [ ] 记录常见查询示例与数据字典

---

## 联系信息

项目路径: `/data/wenyujianData/humanLncAtlas`
