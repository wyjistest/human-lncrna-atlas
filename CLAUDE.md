# Human LncRNA Atlas 项目记忆文件

## 元信息
- **更新日期**: 2025-12-10
- **当前版本**: Phase 5.2 (Genes Options API 优化)
- **上一版本**: Phase 5.1 (Network 页面性能优化)
- **项目状态**: 生产就绪，可用于科研分析
- **GitHub**: https://github.com/wyjistest/human-lncrna-atlas

## 项目概述
跨物种 LncRNA（长非编码 RNA）调控关系数据库和可视化平台，整合人类、黑猩猩、猕猴、狨猴四个灵长类物种数据。采用 FastAPI + PostgreSQL + React 18 + TypeScript 技术栈。核心功能包括 80 万+调控关系查询、IGV 基因组浏览器、ChIP-seq/DNase-seq 表观遗传数据整合、RepeatMasker 重复序列注释。

## 快速启动

```bash
# 后端
cd /data/wenyujianData/humanLncAtlas/backend/app
source venv/bin/activate
uvicorn main:app --reload --port 8000

# 前端
cd /data/wenyujianData/humanLncAtlas/frontend/web
npm run dev
```

**默认访问**：
- 前端界面：http://localhost:5173
- API 文档：http://localhost:8000/docs
- 健康检查：http://localhost:8000/health

## 代码搜索规则

**必须优先使用 Augment MCP 搜索代码上下文**

| 场景 | 工具选择 |
|------|----------|
| 理解功能实现 | mcp__auggie-mcp-d3__codebase-retrieval |
| 查找相关代码 | mcp__auggie-mcp-d3__codebase-retrieval |
| 分析代码依赖 | mcp__auggie-mcp-d3__codebase-retrieval |
| 精确文件路径 | Read |
| 精确字符串匹配 | Grep |

## 项目目录结构

| 目录 | 用途 | 说明 |
|------|------|------|
| `/data/wenyujianData/humanLncAtlas/` | 本地开发 | 含完整数据文件、LongTarget 结果 |
| `/data/wenyujianData/human-lncrna-atlas-github/` | GitHub 仓库 | 代码同步，不含大数据文件 |

```
human-lncrna-atlas-github/
├── frontend/
│   ├── backend/app/      # FastAPI 后端
│   └── web/              # React 前端
├── etl/                  # 数据导入脚本
├── schema/               # 数据库 SQL
└── docs/                 # 项目文档
```

## 技术栈

| 层级 | 技术 |
|------|------|
| 后端 | FastAPI + PostgreSQL + Redis |
| 前端 | React 18 + TypeScript + Vite + Ant Design 5 |
| 可视化 | IGV.js (基因组) + Cytoscape.js (网络) + ECharts (图表) |
| 数据源 | ENCODE, UCSC Genome Browser |

## 项目特异规则

| 规则 | 说明 |
|------|------|
| 双目录开发 | 在 humanLncAtlas 开发，同步到 human-lncrna-atlas-github |
| 推送前编译 | 必须在 GitHub 目录运行 `npm run build` 验证 |
| 配置同步 | 注意 `src/config/` 和 `src/i18n/config/` 双份配置 |
| 物种 ID | Human=1, Chimp=2, Macaque=3, Marmoset=4 |
| 坐标系统 | 使用 hg19/hg38 人类参考基因组 |

## 数据库统计

| 表 | 记录数 | 说明 |
|----|--------|------|
| species | 4 | 灵长类物种 |
| regulations | 804,630 | 调控关系 |
| sequences | 804,630 | 序列数据 |
| chip_peaks | 4,620,036 | ChIP-seq/DNase peaks |
| repeat_masker | 5,481,341 | 重复序列注释 |
| **mv_lncrna_chipseq_overlaps** | **6,537,078** | **物化视图 (预计算重叠)** |

### 物化视图性能优化 (Phase 4.2)

| 查询类型 | 优化前 | 优化后 | 提升 |
|----------|--------|--------|------|
| chr1 查询 | 3-5 min | 0.16s | 1800x |
| chr22 查询 | 9s | 0.098s | 90x |

**刷新命令**: `scripts/refresh_materialized_views.sh`

## 开发工作流

### 日常开发流程
```bash
# 1. 在开发目录修改代码
cd /data/wenyujianData/humanLncAtlas/frontend/web
# ... 开发 ...

# 2. 同步到 GitHub 目录
cp -r src/* /data/wenyujianData/human-lncrna-atlas-github/frontend/web/src/

# 3. 验证编译
cd /data/wenyujianData/human-lncrna-atlas-github/frontend/web
npm install && npm run build

# 4. 提交推送
git add -A && git commit -m "feat: 描述" && git push
```

### Commit 类型规范
- `feat` - 新功能
- `fix` - 修复
- `docs` - 文档
- `refactor` - 重构
- `perf` - 性能优化

## 调试入口

| 问题类型 | 快速检查 |
|----------|----------|
| API 500 错误 | 检查后端日志 `tail -f /tmp/fastapi.log` |
| 数据库连接 | 检查 `.env` 中 DATABASE_URL |
| 前端编译失败 | 检查 `src/config/` 和 `src/i18n/config/` 同步 |
| IGV 轨道加载 | 检查基因组文件路径和 CORS 设置 |
| ChIP-seq 无数据 | 确认物种 ID 和 mark 类型参数 |

### 常见编译错误

| 错误 | 原因 | 解决 |
|------|------|------|
| `Property 'xxx' is missing` | 配置文件未同步 | 同步所有同名配置文件 |
| `Cannot find module 'igv'` | 依赖未安装 | `npm install` |
| `TS2741: Property missing` | 类型不完整 | 检查 `types/` 目录 |
| `ModuleNotFoundError: app.routers.xxx` | router 文件不存在 | 检查 `main.py` 导入，移除不存在的 router |

### 数据库方言支持 (Phase 4.3)

`database.py` 支持多种数据库方言：

| 方言 | 连接池 | statement_timeout | 说明 |
|------|--------|-------------------|------|
| PostgreSQL | QueuePool | ✅ 30s | 生产环境推荐 |
| SQLite | StaticPool | ❌ 不支持 | Demo/测试模式 |
| 其他 | QueuePool | ❌ 不支持 | 通用配置 |

**注意**: `with_timeout()` 上下文管理器在非 PostgreSQL 数据库中为 no-op（优雅降级）。

### Conservation API (Phase 5.0)

跨物种保守性分析功能，通过 `core_id` 机制实现跨物种基因映射。

| API 端点 | 方法 | 说明 |
|----------|------|------|
| `/api/v1/conservation/overview` | GET | 保守性统计概览 |
| `/api/v1/conservation/matrix` | GET | 物种间保守性矩阵（热图数据） |
| `/api/v1/conservation/regulations` | GET | 保守调控关系列表（分页） |
| `/api/v1/conservation/venn` | GET | Venn 图数据 |
| `/api/v1/conservation/lncrna/{core_id}` | GET | 单个 lncRNA 保守性详情 |

**保守性统计**：
| 物种数 | LncRNA 数 | 调控关系 | 占比 |
|--------|-----------|----------|------|
| 4 物种 | 1,001 | 437,478 | 50.84% |
| 3 物种 | 653 | 246,860 | 33.16% |
| 2 物种 | 276 | 109,861 | 14.02% |
| 1 物种 | 39 | 10,431 | 1.98% |

**前端页面**: `/conservation` - 支持热图、表格、筛选、导出

### Network 页面性能优化 (Phase 5.1 - 2025-12-10)

疾病选项 API 优化，通过三 Agent 协同完成（Backend + Frontend + Playwright）。

#### 优化成果

| 指标 | 优化前 | 优化后 | 提升幅度 |
|------|--------|--------|----------|
| API 响应时间 | 4951 ms | 7-50 ms | **99% ↓ (550x)** |
| 响应大小 | 240 KB | ~20 KB | **92% ↓** |
| 返回数据 | 500 条（含重复） | 273 条（去重） | 数据精简 |
| 前端处理 | O(n²) 去重 | O(n) 过滤 | 算法优化 |
| 缓存命中 | 0% | Redis 30min | 新能力 |

#### API 端点

| 端点 | 说明 | 缓存 | 响应时间 |
|------|------|------|----------|
| `/api/v1/diseases/options` | 轻量级疾病选项（仅 id + name） | 30 分钟 | 7-50ms |

#### 代码改动

**后端**：
- `app/routers/diseases.py`：新增 `/options` 端点 (+44 行)
- `app/schemas/disease.py`：新增 `DiseaseOption` Schema (+7 行)
- `app/middleware/logging.py`：增强慢查询日志 (+6 行)

**前端**：
- `src/api/diseases.ts`：新增 `getOptions()` 方法 (+25 行)
- `src/pages/Network/index.tsx`：优化查询和 UI (+51 行, -29 行)

#### 性能测试

详细测试报告位于：
- `frontend/web/PHASE2_TEST_ANALYSIS.md`
- `frontend/web/TEST_FIX_GUIDE.md`
- `frontend/web/performance-baseline-summary.txt`

#### 缓存监控

```bash
# 查看疾病选项缓存
redis-cli KEYS "lncrna:diseases:options*"
redis-cli TTL "lncrna:diseases:options"

# 手动清除缓存
redis-cli DEL "lncrna:diseases:options"
```

### Genes Options API (Phase 5.2 - 2025-12-10)

基因选项 API 优化，为基因列表页面提供快速选项加载，复用 Phase 5.1 成功模式。

#### 优化成果

| 指标 | 数值 | 说明 |
|------|------|------|
| API 响应时间（首次） | 308 ms | 查询 17,248 基因 |
| API 响应时间（缓存） | 238 ms | Redis 缓存命中 |
| 缓存加速比 | 1.29x | 缓存比数据库快 29% |
| 响应大小 | 2.05 MB | 所有物种所有基因 |
| 返回数据 | 17,248 条 | 4 个物种的基因 |
| 缓存命中 | Redis 30min | 新能力 |

#### API 端点

| 端点 | 说明 | 缓存 | 响应时间 |
|------|------|------|----------|
| `/api/v1/genes/options` | 轻量级基因选项（id + name + species） | 30 分钟 | 308ms (首次) / 238ms (缓存) |
| `/api/v1/genes/options?species_id=1` | 人类基因（5,484 条） | 30 分钟 | 185ms |
| `/api/v1/genes/options?gene_type=lncRNA` | lncRNA 基因（6,554 条） | 30 分钟 | 150ms |

#### 代码改动

**后端**：
- `app/schemas/gene.py`：新增 `GeneOption`, `GeneOptionsResponse` Schema (+17 行)
- `app/routers/genes.py`：新增 `/options` 端点 (+95 行)

#### 查询参数

| 参数 | 类型 | 说明 |
|------|------|------|
| `species_id` | int | 物种过滤（1=人类, 2=黑猩猩, 3=猕猴, 4=狨猴） |
| `gene_type` | str | 基因类型过滤（lncRNA/protein_coding） |

#### 性能测试

详细测试报告位于：
- `frontend/backend/GENES_OPTIONS_API_REPORT.md`

#### 缓存监控

```bash
# 查看基因选项缓存
redis-cli KEYS "lncrna:genes:options*"
redis-cli TTL "lncrna:genes:options:all:all"

# 手动清除缓存
redis-cli DEL "lncrna:genes:options:all:all"

# 批量清除
redis-cli KEYS "lncrna:genes:options*" | xargs redis-cli DEL
```

#### 特殊处理

- **物种后缀移除**: 自动移除 `_chimp`, `_macaque`, `_marmoset` 后缀
- **分组缓存**: 按 `species_id` 和 `gene_type` 组合生成缓存键

## 文档索引

> **注意**: 仅在需要时手动读取这些文档，避免占用上下文

| 文档 | 路径 | 说明 |
|------|------|------|
| 项目状态 | `docs/PROJECT_STATUS_REPORT.md` | 完整状态报告 |
| 当前进度 | `docs/CURRENT_STATUS.md` | 数据库统计、最近更新 |
| API 文档 | http://localhost:8000/docs | Swagger UI |

## 记忆更新规范

遇到踩坑点时立即记录：

1. **问题记录格式**：
   ```
   [日期] 问题描述
   - 现象：...
   - 原因：...
   - 解决：...
   - 预防：...
   ```

2. **更新位置**：
   - 通用规则 → 更新本文件
   - 技术细节 → 更新对应 docs/ 文档
   - 版本变更 → 更新 CHANGELOG.md

## 环境变量

| 变量 | 说明 | 默认值 |
|------|------|--------|
| DATABASE_URL | PostgreSQL 连接串 | 见 .env |
| REDIS_URL | Redis 连接 | redis://localhost:6379 |
| GENOME_DATA_PATH | 基因组文件目录 | /data/genomes |
| CORS_ORIGINS | 允许的前端域名 | http://localhost:5173 |

---

**Human LncRNA Atlas 项目组**
- 开发者: wyjistest
- AI 协助: Claude Code (Opus 4.5)
