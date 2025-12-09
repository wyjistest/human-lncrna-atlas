# Human LncRNA Atlas 文档索引

> **更新日期**: 2025-12-09
> **当前版本**: Phase 4.0+
> **维护者**: Claude Code (Opus 4.5)

---

## 快速导航

| 文档 | 说明 |
|------|------|
| [@README.md](../README.md) | 项目概述、快速开始、安装部署 |
| [@CLAUDE.md](../CLAUDE.md) | 项目记忆、开发规范、工作流程 |
| [@CHANGELOG.md](../CHANGELOG.md) | 版本变更历史 |

---

## 按主题分类

### 项目状态

| 文档 | 说明 | 更新频率 |
|------|------|----------|
| [PROJECT_STATUS_REPORT.md](PROJECT_STATUS_REPORT.md) | 完整项目状态报告（已完成 + 未完成） | 每阶段 |
| [CURRENT_STATUS.md](CURRENT_STATUS.md) | 当前进度摘要、数据库统计 | 每日 |

### 架构设计

| 文档 | 说明 |
|------|------|
| [DATABASE_DESIGN_FINAL.md](DATABASE_DESIGN_FINAL.md) | 数据库设计、表结构、索引策略 |
| [VERSION_MIGRATION_STRATEGY.md](VERSION_MIGRATION_STRATEGY.md) | 版本管理、迁移策略 |
| [PHASE_2.3_CHIPSEQ_ARCHITECTURE.md](PHASE_2.3_CHIPSEQ_ARCHITECTURE.md) | ⭐ ChIP-seq 通用架构设计（推荐阅读） |
| [PHASE_2.3_ARCHITECTURE_VISUAL.md](PHASE_2.3_ARCHITECTURE_VISUAL.md) | 架构可视化图表 |

### 功能模块

| 文档 | 说明 |
|------|------|
| [IGV_INTEGRATION_PLAN.md](IGV_INTEGRATION_PLAN.md) | IGV 基因组浏览器集成 |
| [ENCODE_DATA_GUIDE.md](ENCODE_DATA_GUIDE.md) | ENCODE ChIP-seq 数据下载与导入 |
| [QUICKSTART_CHIPSEQ.md](QUICKSTART_CHIPSEQ.md) | ChIP-seq 功能快速开始 |

### 里程碑报告

| 文档 | 说明 |
|------|------|
| [PHASE_1_MVP_COMPLETION_REPORT.md](PHASE_1_MVP_COMPLETION_REPORT.md) | Phase 1 核心平台完成报告 |
| [PHASE_2.3_DELIVERY_SUMMARY.md](PHASE_2.3_DELIVERY_SUMMARY.md) | ChIP-seq 架构交付总结 |
| [PHASE_2.3_2.4_COMPLETION_REPORT.md](PHASE_2.3_2.4_COMPLETION_REPORT.md) | 多 Marks 验证完成报告 |
| [PHASE_2.3_IMPLEMENTATION_CHECKLIST.md](PHASE_2.3_IMPLEMENTATION_CHECKLIST.md) | 实施检查清单 |

### 更新日志

| 文档 | 主要内容 |
|------|----------|
| [changelog/2025-12-05.md](changelog/2025-12-05.md) | RepeatMasker 扩展层、548 万条数据导入 |
| [changelog/2025-12-03.md](changelog/2025-12-03.md) | IGV.js 基因组浏览器集成 |
| [changelog/2025-12-02.md](changelog/2025-12-02.md) | 监控仪表板、分页索引优化 |
| [changelog/2025-12-01.md](changelog/2025-12-01.md) | E2E 测试框架、Redis 缓存 |

### 前端开发

| 文档 | 说明 |
|------|------|
| [@frontend/web/README.md](../frontend/web/README.md) | 前端开发指南 |
| [@frontend/TODO_IMPLEMENTATION_PLAN.md](../frontend/TODO_IMPLEMENTATION_PLAN.md) | 前端待办事项（已完成） |

### 后端开发

| 文档 | 说明 |
|------|------|
| [@frontend/backend/README.md](../frontend/backend/README.md) | 后端 API 开发指南 |
| [@frontend/backend/BACKEND_STATUS.md](../frontend/backend/BACKEND_STATUS.md) | 后端状态报告 |

### 部署与运维

| 资源 | 说明 |
|------|------|
| [@scripts/start.sh](../scripts/start.sh) | 一键启动脚本 |
| [@scripts/stop.sh](../scripts/stop.sh) | 一键停止脚本 |
| [@scripts/run-tests.sh](../scripts/run-tests.sh) | 测试运行脚本 |
| [@.env.example](../frontend/backend/.env.example) | 环境变量配置示例 |

---

## 技术栈速查

### 后端
- **框架**: FastAPI + Uvicorn
- **ORM**: SQLAlchemy 2.0
- **数据库**: PostgreSQL 15
- **缓存**: Redis
- **验证**: Pydantic v2
- **测试**: pytest + httpx

### 前端
- **框架**: React 18 + TypeScript + Vite
- **UI**: Ant Design 5
- **状态**: TanStack Query (React Query)
- **路由**: React Router v6
- **图表**: ECharts
- **网络图**: Cytoscape.js
- **基因组**: IGV.js
- **国际化**: i18next
- **测试**: Vitest + Playwright

### 数据库
- **数据库**: PostgreSQL 15
- **核心表**: 10 张
- **扩展表**: 7 张（Phase 2+）
- **数据规模**: 800 万+ 行
- **存储需求**: ~10 GB

---

## 数据统计速查

### 核心数据

| 数据表 | 记录数 | 说明 |
|--------|--------|------|
| `species` | 4 | 灵长类物种 |
| `genes` | 17,248 | 物种特异性基因 |
| `regulations` | 804,630 | 调控关系 |
| `chipseq_peaks` | 3,590,215 | ChIP-seq/DNase-seq peaks |
| `genomic_features` | 5,481,341 | RepeatMasker 注释 |

### 细胞系覆盖

| 细胞系 | 组织 | Marks | 状态 |
|--------|------|-------|------|
| K562 | 白血病细胞 | 8 | ⭐ 完整 |
| GM12878 | B淋巴细胞 | 8 | ⭐ 完整 |
| H1-hESC | 胚胎干细胞 | 8 | ⭐ 完整 |
| HepG2 | 肝癌细胞 | 7 | ⭐ 完整 |
| A549 | 肺腺癌 | 7 | ⭐ 完整 |
| MCF-7 | 乳腺癌 | 2 | 部分 |
| HMEC | 正常乳腺 | 7 | ⭐ 完整 |

---

## 常用命令速查

### 启动服务
```bash
# 后端
cd /data/wenyujianData/humanLncAtlas/backend/app
source venv/bin/activate
uvicorn main:app --reload --port 8000

# 前端
cd /data/wenyujianData/humanLncAtlas/frontend/web
npm run dev
```

### 运行测试
```bash
# 全部测试
./scripts/run-tests.sh all

# 后端测试
cd frontend/backend && pytest tests/ -v

# 前端单元测试
cd frontend/web && npm run test:run

# E2E 测试
cd frontend/web && npm run test:e2e
```

### 数据库操作
```bash
# 连接数据库
psql -U amax -d lncrna_production

# 查看表统计
psql -U amax -d lncrna_production -c "
  SELECT schemaname, tablename, n_live_tup
  FROM pg_stat_user_tables
  ORDER BY n_live_tup DESC
"

# 刷新物化视图
psql -U amax -d lncrna_production -c "
  REFRESH MATERIALIZED VIEW mv_chipseq_mark_stats;
  REFRESH MATERIALIZED VIEW mv_gene_mark_summary;
"
```

---

## API 端点速查

### 核心 API

| 端点 | 方法 | 说明 |
|------|------|------|
| `/api/v1/genes` | GET | 基因列表 |
| `/api/v1/genes/{id}` | GET | 基因详情 |
| `/api/v1/regulations` | GET | 调控关系 |
| `/api/v1/diseases` | GET | 疾病关联 |
| `/api/v1/stats/overview` | GET | 统计概览 |
| `/api/v1/network/gene/{id}` | GET | 网络数据 |

### ChIP-seq API

| 端点 | 方法 | 说明 |
|------|------|------|
| `/api/v1/features/chipseq/marks` | GET | 可用 marks |
| `/api/v1/features/chipseq/genes/{id}` | GET | 基因 peaks |
| `/api/v1/features/chipseq/global-compare` | GET | 全局对比 |

### IGV API

| 端点 | 方法 | 说明 |
|------|------|------|
| `/api/v1/igv/genomes` | GET | 基因组列表 |
| `/api/v1/igv/tracks/{species}` | GET | 轨道配置 |

**完整 API 文档**: http://localhost:8000/docs

---

## 访问地址

### 内网访问
- **前端**: http://192.168.6.135:5173
- **后端**: http://192.168.6.135:8000
- **Swagger**: http://192.168.6.135:8000/docs

### 外网访问（frp）
- **前端**: http://45.62.117.191:6003
- **后端**: http://45.62.117.191:6004

---

## 文档维护规范

### 更新原则

1. **代码同步**: 所有文档必须与代码保持同步
2. **功能变更**: 重大功能变更必须更新相关文档
3. **状态更新**: 每个开发阶段结束后更新 PROJECT_STATUS_REPORT.md
4. **日志记录**: 重要更新添加到 changelog/ 目录

### 文档分类

| 类型 | 更新时机 | 负责人 |
|------|----------|--------|
| 状态报告 | 每阶段完成 | 开发者 |
| 架构文档 | 架构变更时 | 架构师/Claude |
| 更新日志 | 每日/每功能 | 开发者 |
| API 文档 | Swagger 自动生成 | 自动 |

### 命名规范

- 状态报告: `PROJECT_STATUS_REPORT.md`, `CURRENT_STATUS.md`
- 阶段文档: `PHASE_X.X_*.md`
- 更新日志: `changelog/YYYY-MM-DD.md`
- 指南文档: `*_GUIDE.md`, `QUICKSTART_*.md`

---

## 历史文档（参考）

以下文档为历史版本，仅供参考：

| 文档 | 说明 | 状态 |
|------|------|------|
| [changelog/2024-12-01.md](changelog/2024-12-01.md) | 早期版本更新 | 归档 |

---

**Human LncRNA Atlas 项目组**
- 开发者: wyjistest
- AI 协助: Claude Code (Opus 4.5)
- GitHub: https://github.com/wyjistest/human-lncrna-atlas
