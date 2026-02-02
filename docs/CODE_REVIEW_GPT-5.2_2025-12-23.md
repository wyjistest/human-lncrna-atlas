# Human LncRNA Atlas（human-lncrna-atlas-github）代码审查报告（GPT-5.2）

**审查日期**：2025-12-23  
**审查范围**：全仓（`frontend/backend`、`frontend/web`、`etl`、`schema`、`scripts`、`.github/workflows`、`docs`、`tests`）  
**目标维度**：代码质量/架构/异常处理/性能/安全/文档/测试/依赖管理  

---

## 0. 项目结构速览（用于定位模块）

- **后端（FastAPI + SQLAlchemy）**：`frontend/backend/`
- **前端（React 19 + TS + Vite）**：`frontend/web/`
- **ETL 数据导入**：`etl/`
- **数据库 Schema/SQL**：`schema/`
- **运维与测试脚本**：`scripts/`
- **CI**：`.github/workflows/`

---

## 1. 总体评价（优点）

### 1.1 安全与防护面做得比较完整
- CORS、TrustedHost、`X-Forwarded-For` 信任链、/metrics 防护、速率限制等关键点都有明确策略与实现。
- 多处关键查询已有输入校验与 LIKE 模式转义，且配套有安全相关测试用例（后端 `tests/`）。

### 1.2 性能与可运维性意识强
- 缓存（Redis + 内存回退）、查询超时保护（statement_timeout）、流式导出/大数据接口限流等，都体现了“线上可用”的设计。
- CI 包含 secret scan、npm/pip audit、前端单测、后端单测与构建，整体质量门禁较完善。

### 1.3 模块化边界清晰
- 后端按 `core/models/schemas/routers/middleware/mounts` 分层，前端按 `api/components/pages/hooks/types` 分层，整体可维护性较好。

---

## 2. 逐模块审查与建议

> 说明：这里以“可落地/可验证/兼容性可控”为优先级原则。部分建议属于“下一阶段工程化提升”，不建议一次性大改。

### 2.1 Backend（`frontend/backend`）

**代码质量与规范性**
- ✅ 路由函数与 schema/model 分离清晰；关键参数普遍有 `Query` 约束。
- 🟡 建议：对“跨模块重复的小逻辑”做适度复用（如 gene name suffix 清理在多个位置出现），属于可选优化（避免过度抽象）。

**异常处理与契约**
- ✅ 已有全局异常脱敏（防信息泄露）的意识与实现。
- 🔴 建议：显式保留 FastAPI 默认的 `HTTPException` / `RequestValidationError` 行为，避免被“兜底 Exception handler”误捕获造成 404/422 变 500 的回归风险（尤其在 Starlette 产生的 404 场景）。

**性能与并发**
- ✅ 缓存分层与 TTL 设计合理。
- 🟡 建议：缓存命中/未命中计数属于监控用途，但在多线程环境下递增并非原子操作，统计可能不准；建议加锁保障统计一致性（不影响功能）。

**安全性**
- ✅ `/genomes` 静态文件服务已做扩展名白名单与安全头，整体防护意识到位。
- 🟡 建议：ETL/脚本导入环节与线上 API 的权限边界要继续保持（当前做法总体 OK）。

### 2.2 Frontend（`frontend/web`）

**代码质量与模块化**
- ✅ API client 统一封装、全局错误处理下沉到 QueryClient，工程化成熟度较高。
- ✅ 大型依赖页面做了懒加载（Network/ECharts/IGV.js），对首屏体验友好。

**安全性**
- 🟡 Admin API key 注入已明确标注风险且默认空值；建议保持“生产默认不配置”的实践，并在部署文档中强调“推荐用反向代理注入”模式（当前已有提示，更多是文档层面强调）。

### 2.3 ETL（`etl`）

**可靠性**
- ✅ 多处脚本已有批次管理、回滚、索引前置检查等“数据工程必需”的防护。
- 🟡 建议：对外部下载/导入脚本增加“可选校验”（如 checksum 或最小文件尺寸检查），避免静默下载损坏文件导致后续脏数据；该项改动涉及外部数据源差异，建议单独迭代验证。

### 2.4 运维脚本（`scripts`）

- 🟡 建议：`start.sh` / `run-tests.sh` 增强脚本健壮性（`set -euo pipefail`、关键命令存在性检查、参数缺失时给出明确错误），能减少“环境差异导致脚本误行为”的概率。

### 2.5 Schema（`schema`）

- ✅ SQL 版本化、注释与索引策略写得较清晰。
- 🟡 建议：在 README 或部署指南中标记“必须的扩展/版本依赖”（如 PostgreSQL 版本要求、扩展 pgcrypto/pg_trgm 等），避免部署时踩坑（部分内容已有，建议集中化）。

### 2.6 CI / 依赖管理（`.github/workflows`、requirements、package-lock）

- ✅ 前后端分别有 audit；测试与 lint 也在 CI 内。
- 🟡 建议（后续迭代）：Python 依赖可考虑引入 lock/constraints（如 pip-tools/uv），提升可复现性；但这会影响开发流程与 CI，属于“工程化升级项”，建议单独里程碑推进。

---

## 3. 本轮已落地修改（基于上述建议的最小集合）

### 3.1 后端：显式复用 FastAPI 默认异常处理（防回归）
- 目的：避免 404/422 等被泛化为 500；保持默认错误响应契约不变，同时继续保留 500 的脱敏处理。

### 3.2 后端：缓存统计线程安全
- 目的：多线程环境下 `_hits/_misses` 统计更一致（仅影响监控统计，不改变缓存行为）。

### 3.3 脚本：启动/测试脚本健壮性增强
- 目的：减少环境差异导致的启动/测试失败；对缺少依赖命令与参数缺失给出更清晰提示。

---

## 4. 后续建议（不建议本轮一次性大改）

1. **download 脚本的校验与去 wget 依赖**：需要更充分的环境验证（断点续传、代理、证书、镜像源差异）。
2. **Python 依赖锁定/拆分 requirements**：收益高但涉及 CI/开发流程变更，建议独立 PR/里程碑处理。
3. **指标体系增强**：如缓存命中率 Prometheus 指标化（当前已有基础 metrics 能力，扩展成本可控）。

