# Human LncRNA Atlas 项目记忆文件

## 元信息

| 项目 | 信息 |
|------|------|
| 版本 | Phase 9.27 |
| 状态 | 🟢 生产就绪 |
| 更新 | 2025-12-24 |
| 数据库 | PostgreSQL 15+ (NULLS NOT DISTINCT) |
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
| 前端 | React 19 + TypeScript + Vite + Ant Design 6 |
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
npm run lint          # ESLint (0 errors, 0 warnings)
npm run test:run      # 单元测试 (全部通过)
npm run build         # 生产构建
python3 -c "import main"  # 后端导入

# OpenAPI 类型生成 (后端 API 变更后执行)
npm run generate:types  # 需后端运行中

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
| API 500 | `tail -f frontend/backend/logs/api.log` |
| 数据库连接 | 检查 `.env` DB_HOST/DB_NAME 等 |
| 前端编译失败 | 同步 `src/config/` 配置 |

> 详细踩坑记录: [docs/PITFALLS.md](docs/PITFALLS.md)

## 环境变量

| 变量 | 说明 |
|------|------|
| ENV | 运行环境: production / development (默认 development) |
| DB_HOST | PostgreSQL 主机 (默认 localhost) |
| DB_PORT | PostgreSQL 端口 (默认 5432) |
| DB_USER | 数据库用户 |
| DB_PASSWORD | 数据库密码 |
| DB_NAME | 数据库名称 (默认 lncrna_production) |
| DB_POOL_SIZE | 连接池大小 (默认 5) |
| DB_POOL_MAX_OVERFLOW | 连接池溢出 (默认 10) |
| REDIS_HOST | Redis 主机 (默认 localhost) |
| GENOMES_DIR | 基因组文件目录 (IGV.js) |
| ADMIN_API_KEY | Admin API 密钥 (生产环境必需) |
| ADMIN_REQUIRE_API_KEY | 严格模式 - 必须 API Key (默认 **true**) ⚠️ |
| TRUSTED_PROXIES | 可信代理 IP 列表 (JSON 数组格式) |
| RATE_LIMIT_BYPASS_PRIVATE | 私网 IP 绕过限流 (默认 false) |
| REQUEST_LOG_ENABLED | 启用请求日志 (默认 true) |
| REQUEST_LOG_SLOW_THRESHOLD_MS | 慢请求阈值毫秒 (0=全部) |
| REQUEST_LOG_SAMPLE_RATE | 日志采样率 0.0-1.0 (默认 1.0) |
| SECURITY_ALLOW_INSECURE | 跳过安全检查 (仅开发环境，默认 false) ⚠️ |
| QUERY_TIMEOUT | SQL 查询超时秒数 (默认 30) |
| ENABLE_HSTS | 启用 HSTS 头 (仅 HTTPS 就绪后，默认 false) |
| HSTS_MAX_AGE | HSTS 有效期秒数 (默认 31536000 = 1年) |
| HSTS_INCLUDE_SUBDOMAINS | HSTS 包含子域名 (默认 true) |
| HSTS_PRELOAD | HSTS preload 指令 (默认 false，谨慎启用) |
| CORS_ORIGINS | CORS 允许的来源 (JSON 数组, 需完整 URL 如 http://localhost:5173) |
| TRUSTED_HOSTS | 允许的 Host 头 (JSON 数组, 支持 *.example.com 通配符) |

## 生产环境安全配置

⚠️ **启动时安全验证 (Fail-Fast)**

后端在启动时会执行安全配置验证。若检测到致命错误，应用将 **拒绝启动**：

| 检查项 | 行为 |
|--------|------|
| `ADMIN_REQUIRE_API_KEY=false` | FATAL - 拒绝启动 |
| `ADMIN_REQUIRE_API_KEY=true` 但无 `ADMIN_API_KEY` | FATAL - 拒绝启动 |
| slowapi 未安装 | FATAL - 拒绝启动 |
| `SECURITY_ALLOW_INSECURE=true` (ENV=production) | FATAL - 拒绝启动 (Phase 9.19) |
| `TRUSTED_HOSTS` 为空 (ENV=production) | FATAL - 拒绝启动 (Phase 9.19) |
| `TRUSTED_HOSTS` 仅含 localhost (ENV=production) | FATAL - 拒绝启动 (Phase 9.19) |
| 数据库连接失败 (ENV=production) | FATAL - 拒绝启动 |
| 数据库连接失败 (ENV=development) | WARNING - 允许启动 |
| 连接池过小 (< 20) | WARNING - 仅警告 |

**开发环境绕过**：设置 `SECURITY_ALLOW_INSECURE=true` 可跳过 fail-fast（生产环境禁止使用）

### ⚠️ 前端 Admin API Key 安全风险 (Phase 9.13)

前端通过 `VITE_ADMIN_API_KEY` 环境变量注入 Admin API Key，该 Key 会嵌入构建产物中。

| 部署场景 | 风险 | 建议方案 |
|---------|------|----------|
| **内网/VPN 部署** | 低 | 可使用 `VITE_ADMIN_API_KEY` |
| **公网部署 (CDN)** | **高** ❌ | 禁止使用！Key 会泄露 |
| **公网部署 (反代)** | 中 | 由 Nginx 注入 `X-Admin-API-Key` 头 |
| **公网部署 (完整)** | 低 | 后端实现会话式认证替代 |

**安全的 Nginx 配置示例**:
```nginx
location /api/v1/admin {
    # 仅内网可访问，或配合 IP 白名单
    allow 10.0.0.0/8;
    allow 192.168.0.0/16;
    deny all;

    # 由 Nginx 注入 Admin Key，前端无需配置
    proxy_set_header X-Admin-API-Key "your-secure-key-here";
    proxy_pass http://backend:8000;
}
```

**检查清单**:
- [ ] 公网部署时确认 `VITE_ADMIN_API_KEY` 未设置
- [ ] 使用反向代理限制 Admin 端点访问
- [ ] 或实现后端会话认证替代 API Key

```bash
# 生产环境必需配置
ADMIN_REQUIRE_API_KEY=true
ADMIN_API_KEY=$(openssl rand -hex 32)

# 确保 slowapi 已安装
pip install slowapi

# 高并发建议
DB_POOL_SIZE=10
DB_POOL_MAX_OVERFLOW=20
```

**限流策略**:
| 端点类型 | 限制 | 说明 |
|---------|------|------|
| Admin API | 2-10/min | 最严格，防止暴力破解 |
| 数据导出 | 5/min | 资源密集型操作 |
| 统计/保守性/特征 | 30/min | 通常有缓存 |
| IGV 可视化 | 60/min | 交互式浏览需要 |
| ChIP-seq | 30/min | 大数据量查询 |

**启动验证**: 后端启动时会自动检查安全配置，不安全配置会输出 WARNING/ERROR 日志。

## 版本里程碑

| Phase | 功能 | 完成日期 |
|-------|------|----------|
| 1-4 | 数据库核心功能 | 2024-2025 |
| 5.0-5.3 | 性能优化 (550x 加速) | 2025-12-10 |
| 6.0 | 科研数据分析 (4 API + 4 Notebooks) | 2025-12-11 |
| 7.0-7.5 | API 完善 + 单元测试 + 模块化 | 2025-12-12/13 |
| 8.0-8.3 | 代码审查 + ETL 一致性 + Codex 审查 | 2025-12-13 |
| 9.0 | 高级可视化 (Chord/聚类热力图) | 2025-12-15 |
| 9.1 | ESLint 警告清零 (135→0) | 2025-12-15 |
| 9.2 | Ruff Lint 全面修复 (106 issues) | 2025-12-15 |
| 9.3 | 全面代码审查 + 安全/性能修复 | 2025-12-16 |
| 9.4 | 安全加固 (限流 + 启动验证 + 文档) | 2025-12-18 |
| 9.5 | Fail-Fast 安全启动 + ETL 断点续传 | 2025-12-18 |
| 9.6 | NULL 安全去重 + 缓存键修复 + MSW 健壮性 | 2025-12-18 |
| 9.7 | 安全头加固 (HSTS/CSP) + 日志脱敏 + 静态服务安全 | 2025-12-18 |
| 9.8 | Codex 安全审查: 时序攻击防护 + SecretStr + 输入验证 | 2025-12-18 |
| 9.9 | Codex 代码审查修复: Tabnabbing 防护 + 代码去重 + Builtin 遮蔽修复 | 2025-12-18 |
| 9.10 | XSS 全面防护: ECharts tooltip escapeHtml (26+ 处) + /metrics 认证 + 区域大小限制 | 2025-12-19 |
| 9.11 | Codex 安全审查修复: Admin UI 认证 + ChIP-seq max_rows/max_overlaps 内存保护 + JSONL 流式 + 共享验证器 | 2025-12-19 |
| 9.12 | Codex DoS 防护: compare 端点 marks/cell_types 数量限制 + MV 缓存 TTL + /genomes 目录边界文档 | 2025-12-19 |
| 9.13 | 安全审查修复: LIKE 通配符绕过防护 + species_ids 解析验证 + MV 降级处理 + ETL 密码支持 + 103 项安全测试 | 2025-12-20 |
| 9.14 | 性能优化: export_regulations JSON 内存限制 (5000 条) + cross-species N+1 查询优化 (2N → 2 查询) | 2025-12-20 |
| 9.15 | Codex 安全审查修复: DoS 防护 (列表参数限制) + ETL 字段修正 + BatchManager 事务状态 + 枚举参数强约束 | 2025-12-22 |
| 9.16 | Codex 代码审查修复: Admin Key 安全警告 + /genomes 白名单 + CORS 收敛 + 日志轮转 + main.py 模块化重构 | 2025-12-22 |
| 9.17 | Codex 二次审查修复: LIKE 转义防护 + URL.create() 密码编码 + 日志优雅降级 + console.info 移除 | 2025-12-22 |
| 9.18 | Codex 三次审查修复: CORS URL 校验 + TrustedHostMiddleware + 生产 DB fail-fast + TS 错误类型注册 | 2025-12-22 |
| 9.19 | Codex 四次审查修复: CORS 增强校验 (path/userinfo) + TRUSTED_HOSTS 格式/空列表校验 + 生产 SECURITY_ALLOW_INSECURE 硬拒绝 + 27 集成测试 | 2025-12-22 |
| 9.20 | Codex 五次审查修复: ChIP-seq 分区表命名 + CI 安全审计 (pip-audit/npm audit) + 测试层优化 (slow marker) + init_db.sh 验证修正 | 2025-12-23 |
| 9.21 | Codex 六次审查修复: 异常处理防回归 (HTTPException) + 缓存统计线程安全 + uvloop 测试稳定性 + 脚本健壮性增强 | 2025-12-23 |
| **9.22** | **Codex 七次审查修复: MV 缓存重复定义修复 + SQLAlchemy Builder 重构 + diseases count 优化 + 文档版本更新 + DB 名统一 + IGV 类型去重** | **2025-12-23** |
| **9.23** | **Codex 八次审查修复: /genomes BigBed 白名单 (.bb/.bigbed) + /statistics 和 /export DoS 防护 (parse_comma_list 输入限制)** | **2025-12-24** |
| 9.24 | Codex 九次审查修复: MV 缓存线程安全 (app/core/mv_cache.py) + MV 查询异常自动 fallback + time.monotonic() + FastAPI>=0.118.0 + Docker 安全部署方案 | 2025-12-24 |
| 9.25 | Codex 十次审查修复: slowapi Redis 分布式限流 + 前端 CI Admin Key 护栏 + /genomes 白名单对齐 + main.py reload 防误用 + 缓存返回类型一致性 | 2025-12-24 |
| 9.26 | Codex 十一次审查修复: 响应头注入防护 (sanitize_filename + RFC 5987) + Admin Key 三道闸 (代码/构建/CI) + CSV 公式注入防护 + Conservation JOIN 优化 + /genes/options 分页 + ETL --legacy 显式启用 + SQL 聚合下推 | 2025-12-24 |
| **9.27** | **Codex 十二次审查修复: /genomes 路径遍历深度防御 (dotfile/traversal 阻断) + 可选依赖优雅降级 (psutil/redis) + 前端类型重构 (conservationApi.ts 分离) + Middleware 顺序修正 + 7 项新增安全测试** | **2025-12-24** |

> 详细 Phase 历史: [docs/phases/PHASE_HISTORY.md](docs/phases/PHASE_HISTORY.md)

## 安全测试覆盖

| 测试文件 | 测试数 | 覆盖范围 |
|---------|--------|----------|
| `test_security_like_filter.py` | 51 | LIKE 通配符防护 + Sankey 转义 |
| `test_security_input_validation.py` | 33 | species_ids 解析验证 + SQL 注入防护 |
| `test_security_mv_graceful.py` | 19 | MV 降级处理 + 响应完整性 |
| `test_phase_9_19_validation.py` | 27 | CORS/TRUSTED_HOSTS 校验 + 生产环境 fail-fast (集成测试) |
| `test_phase_9_23_fixes.py` | 15 | BigBed 白名单 + parse_comma_list DoS 防护 |
| `test_mv_cache_thread_safety.py` | 13 | MV 缓存线程安全 + TTL + 并发读写 (Phase 9.24) |
| `test_security_content_disposition.py` | 2 | Content-Disposition 响应头注入防护 (Phase 9.26) |

**运行测试**:
```bash
# 所有安全测试（单元 + 集成）
pytest tests/test_security*.py -v

# 仅单元测试（67 个，无需后端）
pytest tests/test_security*.py -v -m unit

# 仅集成测试（36 个，需后端运行）
pytest tests/test_security*.py -v -m integration
```

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
| **数据库 Schema** | `frontend/backend/docs/SCHEMA.md` |
| **数据库迁移** | `etl/migrations/002_fix_regulations_unique_null_safe.sql` |
| **存量数据去重** | `scripts/migrate_dedup_regulations.sql` |
| **代码审查报告** | `frontend/backend/CODE_REVIEW_REPORT_2025-12-16.md` |
| API 文档 | http://localhost:8000/docs |
| Jupyter 使用指南 | `notebooks/README.md` |

---

**Human LncRNA Atlas Project** · MIT License · 2024-2025
