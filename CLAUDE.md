# Human LncRNA Atlas 项目记忆文件

## 元信息

| 项目 | 信息 |
|------|------|
| 版本 | Phase 9.0 |
| 状态 | 🟢 生产就绪 |
| 更新 | 2025-12-15 |
| GitHub | https://github.com/wyjistest/human-lncrna-atlas |

## 项目概述

跨物种 LncRNA 调控关系数据库，整合人类、黑猩猩、猕猴、狨猴四个灵长类物种数据。
- **80 万+** 调控关系 | **460 万+** ChIP-seq peaks | **650 万+** 预计算重叠
- FastAPI + PostgreSQL + React 19 + TypeScript + ECharts

## 快速启动

```bash
# 后端
cd frontend/backend && python3 -m uvicorn main:app --reload --port 8000 --host 0.0.0.0

# 前端
cd frontend/web && npm run dev -- --host 0.0.0.0

# 验证
curl -s http://localhost:8000/health && echo " ✅ Backend OK"
```

| 服务 | 地址 |
|------|------|
| 前端 | http://localhost:5173 |
| API 文档 | http://localhost:8000/docs |

## 技术栈

| 层级 | 技术 |
|------|------|
| 后端 | FastAPI + PostgreSQL + Redis |
| 前端 | React 19 + TypeScript + Vite + Ant Design 5 |
| 可视化 | IGV.js + Cytoscape.js + ECharts |
| 分析 | scipy + scikit-learn (聚类) |

## 项目规则

| 规则 | 说明 |
|------|------|
| 推送前编译 | 必须 `npm run build` 通过 |
| 物种 ID | Human=1, Chimp=2, Macaque=3, Marmoset=4 |
| 坐标系统 | hg19/hg38 参考基因组 |
| Commit 规范 | feat/fix/docs/refactor/perf |

## 开发工作流

```bash
# 验证检查清单
npm run lint          # ESLint (0 errors)
npm run test:run      # 单元测试 (全部通过)
npm run build         # 生产构建
python3 -c "import main"  # 后端导入

# 提交
git add -A && git commit -m "feat: 描述" && git push
```

## Agent 协作模式

开发时优先使用专业化 Agent 进行任务分工：

| Agent | 用途 | 触发场景 |
|-------|------|----------|
| `backend-api-developer` | 后端 API 开发 | FastAPI 路由、数据库 Schema、SQL 查询 |
| `frontend-architect` | 前端开发 | React 组件、API 集成、状态管理 |
| `playwright-test-expert` | E2E 测试 | 功能验证、测试编写、失败诊断 |
| `code-reviewer` | 代码审查 | PR 前质量检查 |
| `Explore` | 代码探索 | 理解代码库结构、搜索功能实现 |

**并行开发示例**:
```
用户需求 → 拆分任务 → 多 Agent 并行执行 → 汇总结果
         ├── backend-api-developer (API)
         ├── frontend-architect (UI)
         └── playwright-test-expert (测试)
```

## Playwright 测试

```bash
# 运行所有 E2E 测试
cd frontend/web && npx playwright test

# 运行特定测试文件
npx playwright test e2e/visualization/sankey-flow.spec.ts

# 带 UI 调试
npx playwright test --ui

# 生成测试报告
npx playwright show-report
```

| 测试目录 | 覆盖范围 |
|---------|---------|
| `e2e/visualization/` | Sankey Flow、图表交互 |
| `e2e/lncrna-chipseq-overlap*.spec.ts` | ChIP-seq 重叠功能 |

## 数据库统计

| 表 | 记录数 |
|----|--------|
| regulations | 804,630 |
| chip_peaks | 4,620,036 |
| mv_lncrna_chipseq_overlaps | 6,537,078 |

## 调试入口

| 问题 | 检查方法 |
|------|----------|
| API 500 | `tail -f /tmp/fastapi.log` |
| 数据库连接 | 检查 `.env` DATABASE_URL |
| 前端编译失败 | 同步 `src/config/` 配置 |

> 详细踩坑记录: [docs/PITFALLS.md](docs/PITFALLS.md)

## 环境变量

| 变量 | 说明 |
|------|------|
| DATABASE_URL | PostgreSQL 连接串 |
| REDIS_URL | Redis 连接 |
| GENOMES_DIR | 基因组文件目录 |

## 版本里程碑

| Phase | 功能 | 完成日期 |
|-------|------|----------|
| 1-4 | 数据库核心功能 | 2024-2025 |
| 5.0-5.3 | 性能优化 (550x 加速) | 2025-12-10 |
| 6.0 | 科研数据分析 (4 API + 4 Notebooks) | 2025-12-11 |
| 7.0-7.5 | API 完善 + 单元测试 + 模块化 | 2025-12-12/13 |
| 8.0-8.3 | 代码审查 + ETL 一致性 + Codex 审查 | 2025-12-13 |
| **9.0** | **高级可视化 (Chord/聚类热力图)** | **2025-12-15** |

> 详细 Phase 历史: [docs/phases/PHASE_HISTORY.md](docs/phases/PHASE_HISTORY.md)

## 核心 API 端点

| 类别 | 端点 | 说明 |
|------|------|------|
| 调控 | `/api/v1/regulations` | 调控关系查询 |
| 保守性 | `/api/v1/conservation/*` | 跨物种保守性分析 |
| ChIP-seq | `/api/v1/chipseq/*` | 表观遗传数据 |
| 可视化 | `/api/v1/visualization/*` | Sankey/Chord 图数据 |
| 导出 | `/api/v1/export/*` | 数据导出 (JSON/CSV/Excel) |

## 文档索引

| 文档 | 路径 |
|------|------|
| 踩坑记录 | `docs/PITFALLS.md` |
| Phase 详细历史 | `docs/phases/PHASE_HISTORY.md` |
| 项目状态报告 | `docs/PROJECT_STATUS_REPORT.md` |
| API 文档 | http://localhost:8000/docs |
| Jupyter 使用指南 | `notebooks/README.md` |

---

**Human LncRNA Atlas Project** · MIT License · 2024-2025
