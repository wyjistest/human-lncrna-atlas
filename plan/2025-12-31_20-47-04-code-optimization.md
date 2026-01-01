---
mode: plan
cwd: /data/wenyujianData/human-lncrna-atlas-github
task: 仓库级代码优化空间盘点与落地计划
complexity: medium
tool: mcp__sequential-thinking__sequentialthinking
total_thoughts: 7
created_at: 2025-12-31T20:47:04+08:00
---

# Plan: 仓库代码优化空间（Backend / Frontend / ETL / CI）

🎯 任务概述
本仓库包含 FastAPI 后端、React/Vite 前端与 ETL 脚本，优化空间通常集中在「工程卫生与可维护性」「性能与数据可靠性」「CI 与安全基线固化」。
本计划目标是先建立可度量基线与可跟踪 backlog，再分模块以小步 PR 方式落地改进，并以测试/CI 作为验收门槛避免回归。

📋 执行计划
1. 现状盘点与基线建立（1 天）
   - 产出：一份“当前状态报告”（测试是否全绿、构建耗时、主要告警、目录体积/大文件分布）。
   - 操作建议：
     - 跑现有测试与构建：`./scripts/run-tests.sh all`、`cd frontend/web && npm run build`
     - 记录 CI 现有 job 与门槛（哪些是 must-pass、哪些是 best-effort）。
   - 完成定义：基线命令可在本机/CI 重复跑通，并记录耗时与失败点。

2. Repo 工程卫生与忽略规则校验（0.5–1 天，低风险高收益）
   - 目标：避免 `node_modules/`、`.venv/`、缓存/日志等目录污染搜索、影响 CI/打包、或误入版本库。
   - 操作建议：
     - 校验是否被跟踪：`git ls-files | rg '^(frontend/web/node_modules|frontend/backend/.venv)/' || true`
     - 统一忽略：检查/补充 `.gitignore`（cache、session、log、coverage、dist 等）
     - 为本地工具提速：必要时增加 `.rgignore`/IDE 配置（仅当团队需要）。
   - 完成定义：大目录不被 git 跟踪；`rg`/lint/测试不再扫描虚拟环境与依赖目录。

3. 后端工程化：lint/format/type-check 门槛对齐（1–2 天）
   - 目标：让后端像前端一样有稳定的代码质量门槛（减少“能跑但难维护”的债务）。
   - 操作建议：
     - 选型：优先 ruff（lint + format），类型检查在 mypy 与 pyright 中选一（先“增量启用”）。
     - 落地：新增配置文件（例如 `frontend/backend/pyproject.toml` 或 `ruff.toml`）、脚本入口（例如 `./scripts/run-tests.sh backend-lint`）。
     - CI：在 `.github/workflows/test.yml` 中增加后端 lint/typecheck job（与现有 unit tests 解耦）。
   - 完成定义：本地一条命令可跑完后端 lint/format/typecheck；CI 对应 job 稳定通过。

4. 后端性能：DB 查询与缓存策略梳理（2–5 天，按热点拆分 PR）
   - 目标：在不改变业务语义的前提下，降低慢查询与大 payload 的开销。
   - 操作建议：
     - 发现热点：对关键 API（如 regulations/genes/network/stats）做采样压测与 SQL 日志统计；对慢查询做 `EXPLAIN (ANALYZE, BUFFERS)`。
     - 常见落点：索引补齐、N+1 查询消除（selectinload/joinedload）、分页/字段裁剪、缓存（Redis 可选）与 HTTP 缓存头。
     - 验收：新增/完善 API 合同测试与统计校验（返回字段、行数、排序等），避免“优化”引入数据差异。
   - 完成定义：选定的 2–3 个热点 endpoint 有明确的耗时下降数据，且测试覆盖回归点。

5. ETL 可靠性与性能：幂等、事务与批量写入（2–5 天）
   - 目标：提升全量/增量导入的可重复性与可观测性，降低内存峰值与导入耗时。
   - 操作建议：
     - 幂等：明确主键/唯一约束，采用 upsert 或“先落地 staging 表再合并”。
     - 性能：分批提交、使用 COPY/批量插入、减少逐行 ORM 操作；长任务加进度与断点续跑。
     - 验收：在临时库跑一次全量导入，记录关键表行数对齐与耗时；失败可安全重跑。
   - 完成定义：ETL 关键脚本可在相同输入下重复执行不产生脏数据，并显著降低峰值内存或耗时。

6. 前端工程化门槛补齐：typecheck + 产物体积可见性（1–2 天）
   - 目标：让 TypeScript 类型问题尽早暴露，并对 bundle 体积/依赖膨胀可观测。
   - 操作建议：
     - 若缺失：增加 `npm run typecheck`（`tsc --noEmit`）并在 CI 中运行。
     - bundle 可见性：引入/启用 `vite --mode production` 的分析报告（仅作为报告或阈值门槛，避免一次性卡死）。
   - 完成定义：CI 里存在明确的 typecheck job；产物体积有基线记录（不一定立刻设硬阈值）。

7. 前端性能与交互体验：大列表/图可视化热点优化（2–5 天，按页面拆分）
   - 目标：在真实数据规模下保证关键页面（列表、网络图、IGV 轨道）的可用性。
   - 操作建议：
     - 大表/列表：虚拟滚动、请求去抖与缓存、分页策略优化。
     - 图可视化：渲染分层、按需加载、避免频繁全量重绘。
     - 验收：Playwright 关键路径回归（已有 e2e 框架）；必要时把性能预算写成可配置阈值。
   - 完成定义：选定的 1–2 个页面在大数据下卡顿明显降低，且 E2E 覆盖主路径。

8. 固化与交接：脚本统一、文档更新、持续防反弹（0.5–1 天）
   - 目标：把“怎么跑/怎么验收/怎么发布”固化到脚本与文档，降低新成员上手成本。
   - 操作建议：
     - `scripts/` 下补齐常用入口（lint/fmt/typecheck/test/build），并在 `README.md`/`LOCAL_DEV.md` 中统一指向。
     - 记录一份“优化 backlog + 优先级”列表（P0/P1/P2），便于后续迭代。
   - 完成定义：一条入口脚本可完成开发者常用动作；文档与实际命令一致。

⚠️ 风险与注意事项
- 工具链引入（lint/typecheck）可能一次性产生大量告警：建议先“仅 CI 报告/增量启用”，分批修复，避免巨型 PR。
- DB/缓存优化可能改变语义或一致性：必须先补合同测试/统计校验，再做实现替换。
- ETL 重构有数据破坏风险：必须在临时库/备份上验证全量导入；上线前保留回滚路径。
- 前端性能优化可能影响交互：必须配套 E2E 主路径回归，且性能阈值可配置。

📎 参考
- `README.md:1`
- `.github/workflows/test.yml:1`
- `.github/workflows/security-audit.yml:1`
- `frontend/backend/pytest.ini:1`
- `frontend/web/package.json:1`

---

# Execution Log

## Phase 1: 基线与现状盘点（2026-01-01）

**Repo/环境**
- git: `main@5c59c52`
- python: `Python 3.11.10` (pip 25.3)
- node: `v22.21.0` (npm 10.9.4)

**目录体积（du -sh）**
- `frontend/`: 1.1G（其中 `frontend/web/node_modules`: 572M；`frontend/backend/.venv`: 492M）
- `notebooks/`: 20M
- `docs/`: 2.1M
- `etl/`: 528K

**CI 门槛（来自 .github/workflows/test.yml）**
- 必跑：frontend unit tests / eslint lint / backend import+syntax checks / backend unit tests / production build
- 可选：E2E（仅 workflow_dispatch + self-hosted）

**本地基线结果（本机跑通）**
- Backend unit tests: ✅ 通过（`pytest -m unit`，248 passed / 259 deselected，real 4.33s）
- Backend import+syntax checks: ✅ 通过（import checks + `py_compile`）
- Frontend unit tests: ✅ 通过（Vitest，20 files / 195 tests，real 9.33s）
- Frontend lint: ✅ 通过（ESLint，real 12.72s）
- Frontend build: ✅ 通过（`tsc -b && vite build`，real 22.31s）

**观察点（后续优化候选）**
- Vite build 有 chunk size 警告（>650kB）：后续可按页面/依赖拆包或手动 chunks（Phase 6/7）。
- 仓库内存在大体积 `node_modules/` 与 `.venv/`：需要确保不被 git 跟踪、并让搜索/工具默认跳过（Phase 2）。

## Phase 3: 后端质量门槛（2026-01-01）

**落地内容**
- ✅ 引入 Ruff 作为后端基础 lint gate（仅 E4/E7/E9/F：语法/未定义名/明显错误）
- ✅ CI 增加后端 `ruff check .` 步骤（与现有 import/syntax checks 并行理念一致）
- ✅ 本地脚本增加入口：`./scripts/run-tests.sh backend-lint`
- ✅ 修复一处真实问题：`app/core/config.py` 中 `quote()` 未导入导致潜在运行时 `NameError`

**验证**
- `./scripts/run-tests.sh backend-lint` ✅
- `./scripts/run-tests.sh backend-unit` ✅

## Phase 4: 后端性能热点（进行中）

**静态审计结论（无需 DB 即可确认）**
- 列表接口已具备：分页、count 缓存（移除 order_by + fast-path COUNT）、参数规范化减少缓存碎片化。
- 已存在索引迁移：`frontend/backend/migrations/002_regulation_indexes.sql`、`frontend/backend/migrations/003_regulations_best_peak_indexes.sql` 覆盖常见过滤与排序路径。

**下一步（需要 PostgreSQL + 真实数据集）**
- 对热点接口跑 `EXPLAIN (ANALYZE, BUFFERS)`，确认是否命中 `idx_regulations_species_ba` / `idx_regulations_species_chr` / best_peak 相关索引。
- 基于慢查询结果再决定：增加/调整复合索引、字段裁剪、或进一步缓存策略。

### Phase 4 进展：本机 PostgreSQL 跑法与 EXPLAIN 基线

**如何确认后端能连上本机 Postgres**
- 后端配置读取：`frontend/backend/.env`（由 `app/core/config.py` 读取）
- 连接自检（无敏感信息）：
  - `cd frontend/backend && ./.venv/bin/python -c "from app.core.config import settings; print(settings.safe_database_url)"`
  - `cd frontend/backend && ./.venv/bin/python - <<'PY'\nfrom sqlalchemy import text\nfrom app.core.database import engine\nwith engine.connect() as c: c.execute(text('SELECT 1'))\nprint('DB_CONNECT_OK')\nPY`

**数据规模（pg_stat_user_tables / n_live_tup）**
- regulations: ~804,630
- sequences: ~806,357
- mv_lncrna_chipseq_overlaps: ~6,537,078

**EXPLAIN 基线脚本（可重复运行）**
- 脚本：`frontend/backend/scripts/explain_hot_queries.py`
- 用法：
  - `cd frontend/backend && ./.venv/bin/python scripts/explain_hot_queries.py`

**关键结果摘要（本机样例，单位 ms）**
- regulations list（species_id=1, limit=100）：~1–3ms（命中 `idx_reg_species_ba_id`）
- regulations list（lncrna_name~MALAT1）：~10–15ms
- analysis summary：
  - high_affinity_stats：~40–60ms（命中 `idx_reg_ba`）
  - top_lncrnas：~90–100ms（命中 `idx_reg_ba`）
  - epigenetic_group_by（MV 聚合，已加索引）：~50–60ms（命中 `idx_mv_overlap_ba100_mark_cat_cell`；优化前 ~450ms）
  - epigenetic_summary_mv（预聚合 MV）：~0.05ms（读取 61 行；最优路径）

**已落实的性能改进（无需改动 DB）**
- regulations 列表接口的 `total=count()` 改为“只对 regulations 表计数”，避免无意义 JOIN（典型场景 count 由 ~178ms 降到 ~32ms）

### Phase 4 进展：Epigenetic 聚合优化（索引 + 预聚合，2026-01-01）

- ✅ 索引路线：在 `mv_lncrna_chipseq_overlaps` 上新增 partial 复合索引 `idx_mv_overlap_ba100_mark_cat_cell`（BA>=100 + (mark_name, mark_category, cell_type)），显著降低 `/analysis/summary` 的聚合开销。
- ✅ 预聚合路线：新增汇总物化视图 `mv_lncrna_chipseq_overlaps_epigenetic_summary_ba100`，把在线 GROUP BY 变成小表读取；后端优先读取该 MV，失败则回退到原聚合查询（保持向后兼容）。
- ✅ 运维脚本：`scripts/refresh_materialized_views.sh` 已扩展为刷新两个 MV（先 base，再 summary）。

**落地文件**
- schema：`schema/v2.3/05_mv_lncrna_chipseq_overlaps.sql`（新增索引）
- schema：`schema/v2.3/06_mv_lncrna_chipseq_overlaps_epigenetic_summary_ba100.sql`（新增汇总 MV）
- backend：`frontend/backend/app/routers/analysis.py`（优先读 summary MV）

## Phase 5: ETL 可靠性性能（2026-01-01）

**现状盘点（已有能力）**
- `etl/templates/` 已提供 `BatchManager` 与 `BaseImporter`：支持批次记录、回滚、分批导入、基础数据校验
- `etl/import_regulations.py`：
  - 入库前检查 `idx_regulations_unique_key`（NULL 安全）
  - 批量导入 + 周期提交（commit_every）形成检查点
  - 失败时写入 `import_batches.error_message` 给出断点续传提示
- `etl/import_repeatmasker.py` / `etl/import_ucsc_rmsk.py`：已有 resume 参数/失败提示

**本次改进（小步、向后兼容）**
- `etl/import_regulations.py` 的 DB 参数默认从环境变量读取（与其他 ETL 脚本一致），减少“每次都要手填连接参数”的摩擦：
  - 支持 `DB_HOST/DB_PORT/DB_NAME/DB_USER/DB_PASSWORD`
  - 若未提供 `--user` 且未设置 `DB_USER`，会明确报错

## Phase 6: 前端质量门槛（2026-01-01）

- 已补齐 `npm run typecheck`（等价于 `tsc -b`；tsconfig 已 `noEmit: true`，不会产出文件）

## Phase 7: 前端性能体验（2026-01-01）

**现状确认（已具备的关键优化）**
- 路由级懒加载：`frontend/web/src/App.tsx` 对 Network/IGV/ECharts 等页面使用 `React.lazy()` + `Suspense`，避免首页把重依赖一次性拉进主包。
- 分包策略：`frontend/web/vite.config.ts` 已按 react/antd/query/echarts/igv/cytoscape/pdf/zip/i18n 拆分 vendor chunks。

**观察点（保留为后续 backlog）**
- `npm run build` 仍会对 `antd-vendor` / `igv-vendor` / `echarts-core` 给出 chunk size warning（属于预期的大依赖，是否进一步拆分需结合首屏/路由访问频率评估）。
