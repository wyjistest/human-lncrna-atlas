# Human LncRNA Atlas 项目记忆文件

## 元信息
- **更新日期**: 2025-12-09
- **当前版本**: Phase 4.1+
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
