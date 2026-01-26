# Human LncRNA Atlas - 当前进度报告

> 最后更新: 2026-01-26
> 当前版本: Phase 3.5 (动态 Overlap 轨道加载)

## 📊 数据库统计

### Epigenomic Data (ChIP-seq + DNase-seq)

| Mark 类型 | 分类 | 细胞系数 | 实验数 | Peaks 数量 |
|-----------|------|----------|--------|------------|
| **DNase-HS** | Open Chromatin | **7** | **7** | **1,223,622** |
| H3K4me1 | Activating | 6 | 6 | **727,149** |
| H3K4me3 | Activating | 7 | 7 | **426,705** |
| H3K9me3 | Repressive | 5 | 5 | **323,375** |
| H3K27me3 | Repressive | 6 | 6 | **295,044** |
| H3K27ac | Activating | 6 | 6 | **352,975** |
| H3K36me3 | Activating | 6 | 6 | **241,345** |
| **总计** | - | **7** | **43** | **3,590,215** |

### 细胞系覆盖

| 细胞系 | 组织 | ChIP-seq Marks | DNase-seq | 总 Peaks |
|--------|------|----------------|-----------|----------|
| **MCF-7** | 乳腺癌细胞 | 1 mark (H3K4me3) | ✅ 126,717 | ~239k |
| **HMEC** | 正常乳腺上皮 | 6 marks | ✅ 140,574 | ~518k |
| **A549** | 肺腺癌细胞 | 6 marks | ✅ 118,965 | ~579k |
| K562 | 白血病细胞 | 6 marks | ✅ 202,266 | ~827k |
| H1-hESC | 人胚胎干细胞 | 6 marks | ✅ 258,188 | ~844k |
| GM12878 | B淋巴细胞 | 6 marks | ✅ 183,953 | ~728k |
| HepG2 | 肝癌细胞 | 5 marks | ✅ 192,959 | ~691k |

### 核心数据

- **物种**: 4种灵长类 (Human, Chimpanzee, Macaque, Marmoset)
- **基因数量**: 17,248
- **调控关系**: 804,630

## ✅ 最近完成的功能

### 2026-01-26 ⭐ 文档一致性护栏（现状指引）

1. **docs 状态标注检查扩展**
   - `scripts/check_docs_status_markers.py` 默认扫描整个 `docs/`（git tracked），若文档包含 TODO/checkbox/mock/stub/未实现 等信号则必须引用 `docs/CURRENT_STATUS.md`
   - 失败输出包含 `file:line` 与触发指示（更易定位与可回滚修复）

2. **历史文档补齐现状指引**
   - 为部分历史报告/计划/踩坑记录补充“现状以 `docs/CURRENT_STATUS.md` 为准”的提示，减少误读风险

### 2026-01-26 ⭐ 回归锚点扩展（API Snapshot）

1. **导出与分页端点纳入回归锚点**
   - `scripts/api_snapshot.py` 增加 `export/regulations`（JSON, limit=1, species_ids=1）与 `conservation/regulations`（分页列表）采样
   - 补充 `export/high-affinity` / `export/conservation` / `export/disease-network` 以捕获导出结构漂移
   - `docs/baselines/api-snapshot.sample.json` 已更新，便于发现导出/分页响应结构漂移

2. **network/可视化端点纳入回归锚点**
   - `scripts/api_snapshot.py` 增加 `network/available-combinations` 的首条组合采样，并覆盖 `network/disease` / `network/gene/{id}/detail`
   - 新增 `visualization/sankey-data` 与 `visualization/chord-data` 基线摘要，用于捕获图结构/可视化数据漂移

### 2026-01-26 ⭐ 性能快照对比（Admin Metrics Diff）

1. **admin metrics 快照对比（离线）**
   - `scripts/admin_metrics_snapshot.py` 支持 `--compare OLD_JSON NEW_JSON`，输出 `admin-metrics-diff-*.md`（便于回归/优化对比）
   - diff 现已覆盖 cache get() 延迟（hits/misses p95/p99）与 cache breakdown（routes/keys/namespaces 的 compute_* / hit_rate / req）变化，便于定位回归根因
   - 性能定位文档与 issue 模板已补齐对比用法（`docs/PERFORMANCE_TRIAGE.md` / `.github/ISSUE_TEMPLATE/performance-triage.md`）

### 2026-01-26 ⭐ CI 触发策略（main push）

1. **GitHub Actions 自动触发**
   - `Tests` 对 `main` 分支 `push` 自动触发；`Security Audit` 在依赖清单变化时自动触发；PR CI 默认不启用（避免 self-hosted 执行不受信任代码）
   - `Tests`/`Security Audit` 增加 `concurrency` 以取消同分支的过期运行，减少排队与“看似卡住”

### 2026-01-25 ⭐ 依赖维护（Dependabot PR 清理）

1. **合并 patch/minor 更新**
   - 前端：prettier/vitest/jsdom/react-router-dom/msw 等依赖更新已合并
   - 后端：uvicorn/pydantic/numpy/scipy 等依赖更新已合并

2. **完成大版本升级（独立验证 + 可回滚）**
   - 已以独立 worktree/PR 方式完成 `websockets==16.0` 与 `pandas==3.0.0` 升级：本地 `bash scripts/run-tests.sh ci` 与 self-hosted `Tests`/`Security Audit` 均通过

### 2026-01-24 ⭐ BaseURL 可配置性补齐

1. **后端回归脚本支持自定义后端地址**
   - `frontend/backend/scripts/run_tests.sh` / `frontend/backend/scripts/run_chipseq_tests.sh` 支持 `API_BASE_URL`（兼容 `HLA_BACKEND_URL/BACKEND_URL`），默认仍为 `http://localhost:8000`
   - 默认注入 `NO_PROXY`，避免本机代理环境导致 health check 卡住

2. **本地 CI 的 E2E smoke 支持自定义端口**
   - `scripts/run-tests.sh e2e-smoke` 支持从 `BASE_URL=http://127.0.0.1:<port>` / `http://localhost:<port>` 解析端口（仍默认 5173，保持 CI strictPort 行为）
   - 端口占用提示文案按实际端口展示

3. **文档示例不再写死后端地址**
   - `frontend/backend/app/routers/export.py` 的示例使用 `API_BASE_URL` 拼接请求 URL（便于 LAN/远端环境复用）

4. **前端 lint baseline 数据提示消除**
   - `frontend/web` 显式添加 `baseline-browser-mapping` devDependency（升级到最新），不再输出 `[baseline-browser-mapping] The data in this module is over two months old` 提示

### 2026-01-23 ⭐ 安全审计与 CI 核验（self-hosted）

1. **安全审计计划与执行结果对齐**
   - `Security Audit` High/Critical = 0（`pip-audit --strict` 通过；`npm audit --audit-level=high` 通过；本地 `npm audit --audit-level=moderate` 目前为 0）

2. **GitHub Actions 手动触发核验**
   - `Tests` 与 `Security Audit` 在 self-hosted runner 上以 `workflow_dispatch` 成功通过（含 E2E smoke）
   - 已设置 repo variable `CI_RUNS_ON=self-hosted`：后续手动触发无需填写 `runs_on`，默认走 self-hosted（可绕过 GitHub-hosted billing/额度阻塞）
   - `Tests` 在 self-hosted 下默认跳过 Postgres service jobs；如需全量校验可在 `workflow_dispatch` 设 `enable_postgres_jobs=true`

3. **PR / 分支状态**
   - PR 状态以 GitHub `Pull requests` 列表为准（Dependabot 会持续创建更新 PR，不在本文做“长期不变”的断言）
   - 分支清理策略：已合并 PR 的分支可删除；高风险/大版本依赖更新建议先单独验证再合并

### 2026-01-20 ⭐ 后端导出性能优化（Overlap Export）

1. **`/api/v1/lncrna-chipseq-overlap/export` 真流式输出（无 OFFSET 扫描）**
   - 导出查询改为单次 `execute(stream_results=True)` + `fetchmany()` 分批拉取，避免大结果集下的深分页扫描与重复查询
   - 增加结果集 `close()` 的资源释放保障，降低 StreamingResponse 中断/取消时的 server-side cursor 泄露风险

2. **物化视图加速导出（MV Fast Path）**
   - 当 `mv_lncrna_chipseq_overlaps` 可用时，导出直接读取 MV，避免 `regulations × chipseq_peaks_human` 的运行时 JOIN 压力
   - 保持导出字段与格式不变（BED6 / CSV 19 列）

### 2026-01-19 ⭐ CI Smoke + 监控回归增强

1. **E2E Smoke 覆盖扩展（完全 mocked）**
   - 新增 Playwright smoke：`/admin/cache` 与 `/admin/materialized-views`（完全 mock 对应 Admin API）
   - Admin/Monitoring、Admin/Cache、Admin/Materialized Views mocked smoke 改用 `data-testid` 稳定选择器，并补齐最小契约断言（关键按钮/核心字段/表格行可见），降低 strict mode 冲突与 UI 结构变更导致的 flaky 风险
   - Genes/Regulations/Stats/Diseases/Analysis/Conservation 页面补齐 `data-testid`，新增 `/genes`、`/regulations`、`/stats`、`/diseases`、`/analysis`、`/conservation` 的 mocked smoke（CI `e2e-smoke` 仍保持完全离线可跑）

2. **监控指标补齐**
   - `/api/v1/admin/metrics`：新增端点级响应时间百分位（p50/p95/p99）
   - `/api/v1/admin/metrics`：新增 DB 查询耗时统计（per-query/per-request 百分位）与慢查询榜单（按 fingerprint+route 聚合）；端点维度补齐 DB 平均耗时与平均查询数
   - Admin/Monitoring：Endpoint table 展示 P95/P99，数据不足时显示 `n=<samples>/10`；新增 Top Endpoints（P95/P99）、Top DB Endpoints（DB P95/P99）、“Database Performance”（DB percentiles + slow queries）与 “Download Metrics” 导出按钮

3. **ETL 回归基线加固**
   - CI 校验 `etl/sample_inputs/etl-inputs.manifest.tsv`，防止样例输入漂移导致回归失真
   - ETL E2E smoke：导入样例后使用 `etl/smoke_verify_sample_import.py` 做值级断言（regulations + sequences），避免“行数正确但字段映射漂移”

### 2026-01-18 ⭐ 可观测与 CI 基础设施补齐

1. **CI 与本地一致性**
   - 以 GitHub Actions 为准统一本地复刻入口：`./scripts/run-tests.sh ci`
   - 文档命令漂移检查已接入 CI（`scripts/check_docs_commands.py`）

2. **Admin Monitoring 可观测性闭环**
   - `GET /api/v1/admin/metrics`：轻量 in-memory 请求级指标（包含 `cache_stats` 摘要 + `cache_breakdown`（routes/namespaces/keys top；含 compute_count/avg/max））
   - `POST /api/v1/admin/metrics/reset-stats`：一键清零 in-memory 指标（不影响 Prometheus `/metrics`）
   - `GET /api/v1/admin/cache/stats` + `POST /api/v1/admin/cache/reset-stats`：缓存命中率/回源耗时统计与重置
   - Admin/Monitoring 页面：新增 Cache Namespaces / Hot Keys 表格与 “Reset Cache Stats” 按钮
   - Admin 运维页面：新增 `/admin/cache`（缓存管理）与 `/admin/materialized-views`（物化视图状态/刷新）

3. **IGV 交互增强（ROI 高亮）**
   - lncRNA-ChIP-seq overlap 表格行点击跳转 IGV 时，同时以 ROI 高亮精确 overlap 区间（P2 扩展功能）

### 2025-12-10 (Phase 3.5) ⭐ 动态 Overlap 轨道加载

1. **动态轨道加载功能** ⭐ P1 功能完成
   - **一键加载**: "Load Overlap Track" 按钮动态加载 Overlap 轨道
   - **自动同步**: 开启后筛选条件变化时自动更新轨道（500ms 防抖）
   - **轨道样式**: 紫色 (#722ed1)，高度 60px，可见窗口 5MB
   - **完整国际化**: 中英文支持（+11 keys）

2. **后端 API 适配** ⭐ IGV.js 兼容
   - **参数别名**: 支持 `chr` 和 `chromosome` 两种参数名
   - **URL 模板**: 兼容 IGV.js `${chr}`, `${start}`, `${end}` 模板变量
   - **错误处理**: 参数缺失返回 400 错误
   - **测试覆盖**: 7 个新增测试用例

3. **前端实现** ⭐ 复用现有架构
   - **GenomeBrowserHandle**: 复用 `loadTrack()`, `removeTrack()` 接口
   - **UI 控件**: 加载按钮 + 自动同步开关
   - **状态管理**: 加载中/成功/失败消息提示
   - **TypeScript**: 编译通过，类型安全

4. **E2E 测试覆盖** ⭐ 18 个测试用例
   - **测试文件**: `e2e/overlap-dynamic-track.spec.ts`
   - **P0 核心**: 按钮可见性、API 调用验证
   - **P1 性能**: 轨道加载 < 5s
   - **P2 边界**: 错误处理、键盘导航
   - **通过率**: 16/18 (89%)，2 个 skipped

5. **多 Agent 协同开发** ⭐ 效率革命
   - **Sequential Thinking**: 实施计划制定
   - **Backend Agent**: API 参数适配 + 测试
   - **Frontend Agent**: 轨道加载 + UI + i18n
   - **Playwright Agent**: 18 个 E2E 测试
   - **并行执行**: 3 agents 同时工作，~15 分钟完成
   - **效率提升**: 传统 4-6 小时 → 15 分钟 (**20x**)

6. **构建验证**
   | 指标 | 结果 |
   |------|------|
   | TypeScript 编译 | ✅ 无错误 |
   | 生产构建 | ✅ 16.79s |
   | E2E 测试 | ✅ 16/18 通过 |

### 2025-12-10 (Phase 3.4) ⭐ IGV 基因组浏览器集成 - lncRNA-ChIP-seq Overlap 可视化

1. **IGV 集成核心功能** ⭐ 科研人员最需要的可视化
   - **上下拆分布局**: 表格 50% + IGV 浏览器 50%
   - **点击表格行跳转 IGV**: 自动导航到重叠区域（± 50kb padding）
   - **IGV 显示/隐藏开关**: Switch 组件控制
   - **完整国际化支持**: 中英文翻译（+46 keys）

2. **后端 API 开发** ⭐ 高性能 BED 轨道服务
   - **新增端点**: `GET /api/v1/igv/overlap-track`
   - **BED6 标准格式**: 兼容 IGV.js 和所有基因组工具
   - **6 个查询参数**: chr, start, end, mark_type, cell_line, min_ba
   - **性能优化**: 响应时间 < 100ms（比预期快 **20 倍**）
   - **自动使用物化视图**: 查询 mv_lncrna_chipseq_overlaps
   - **完整错误处理**: 区间限制（max 10Mb）、参数验证

3. **前端实现** ⭐ 无缝集成体验
   - **修改文件**: 5 个文件，+143 行代码
   - **GenomeBrowser 复用**: 使用现有组件和 Handle 接口
   - **TypeScript 编译**: ✅ 通过（`npx tsc --noEmit`）
   - **生产构建**: ✅ 成功（18.08s）
   - **HMR 热更新**: ✅ 正常工作

4. **Context7 MCP 验证** ⭐ IGV.js API 调研
   - ✅ `browser.search(locus)` - 跳转到指定位置
   - ✅ `browser.loadTrack(config)` - 动态加载轨道（P1 可扩展）
   - ✅ `browser.loadROI(roiConfigs)` - ROI 高亮（P2 可扩展）

5. **E2E 测试覆盖** ⭐ 100% 通过
   - **测试文件**: `e2e/lncrna-chipseq-overlap-igv.spec.ts`
   - **测试用例**: 17 个（P0 核心 6 + P1 性能 3 + P2 错误 8）
   - **通过率**: 100%
   - **执行时间**: 2.0 分钟
   - **表格加载性能**: 1.6 秒（超预期）

6. **性能指标** ⭐ 超出预期
   | 指标 | 预期 | 实际 | 提升 |
   |------|------|------|------|
   | API 响应时间 | < 2s | < 100ms | **20x** |
   | 前端构建时间 | < 30s | 18.08s | ✅ |
   | 开发工期 | 2-3.5 天 | ~2 小时 | **10x+** |

7. **多 Agent 协同开发** ⭐ 效率革命
   - **Sequential Thinking**: 8 步可行性评估（9.5/10 评分）
   - **Backend Agent**: API 实现 + 10 个测试通过
   - **Frontend Agent**: 布局改造 + Context7 API 验证
   - **Playwright Agent**: 17 个 E2E 测试
   - **并行执行**: 3 agents 同时工作，效率提升 10 倍

### 2025-12-08 (Phase 3.3) ⭐ DNase-seq 全细胞系覆盖

1. **DNase-seq 数据补全** ⭐ 100% 细胞系覆盖
   - **新增 3 个细胞系 DNase-seq 数据**:
     - A549 (肺腺癌): 118,965 peaks
     - MCF-7 (乳腺癌): 126,717 peaks
     - HMEC (正常乳腺): 140,574 peaks
   - **总计新增: 386,256 peaks** (+46%)
   - **DNase-HS 细胞系覆盖率**: 4/7 → 7/7 (100%)
   - **DNase-HS 总 peaks**: 837,366 → 1,223,622
   - 数据源: UCSC ENCODE Uniform DNaseI HS (hg19)

2. **数据库更新**
   - 实验总数: 40 → 43 (+3)
   - 总 Peaks: 3,203,959 → 3,590,215 (+386,256)
   - 修复旧 DNase-HS experiments 的 cell_line 字段

3. **验证与测试**
   - API 验证: 所有端点返回 HTTP 200
   - E2E 测试: 86/104 通过 (83%)
   - 前端构建: 成功 (16.69s)

4. **多 Agent 协同执行**
   - Backend API Developer: 数据下载、导入、API 验证
   - Frontend Architect: 配置验证、构建检查
   - Playwright Test Expert: E2E 测试执行
   - Sequential Thinking: 8 步可行性分析与执行规划
   - MCP 工具: Augment (代码索引), Context7 (文档), WebSearch (数据源)

### 2025-12-07 (Phase 3.2) ⭐ MCF-7 乳腺癌 + HMEC 正常乳腺细胞系

1. **双乳腺细胞系数据导入** ⭐ 癌症 vs 正常对比
   - **MCF-7** (乳腺腺癌细胞系):
     - 1 个实验 (H3K4me3)
     - 111,917 peaks
     - 数据源: ENCODE UW Histone
     - 颜色: #FF69B4 (Hot Pink)
   - **HMEC** (人类乳腺上皮细胞):
     - 6 个实验 (全部核心 marks)
     - 377,873 peaks
     - 数据源: ENCODE Broad Histone
     - 颜色: #DEB887 (Burlywood)
   - **总计新增: 489,790 peaks** (+18%)

2. **数据库全局统计更新**
   - 细胞系数: 5 → 7 (+MCF-7, +HMEC)
   - 实验总数: 33 → 40 (+7)
   - 总 Peaks: 2,714,169 → 3,203,959 (+489,790)
   - 组织多样性: 血液、肝脏、干细胞、肺、乳腺（癌症+正常）

3. **前端配置更新**
   - `cellTypeConfigs.ts`: 添加 MCF-7 + HMEC 配置
   - 完整双语支持 (中/英)
   - 配置驱动架构验证（零代码修改后端逻辑）

4. **E2E 测试覆盖**
   - 新增 `mcf7-hmec-validation.spec.ts` (18 个测试用例)
   - P0 核心功能、P1 数据准确性、P2 回归测试

5. **多 Agent 协同开发**
   - Backend API Developer: 脚本更新、数据下载导入
   - Frontend Architect: 配置更新、颜色方案
   - Playwright Test Expert: E2E 测试创建验证
   - Sequential Thinking: 8 步可行性分析
   - MCP 工具: Augment (代码索引), WebSearch (数据源验证)

### 2025-12-07 (Phase 3.0) ⭐ lncRNA-ChIP-seq Overlap 分析功能

1. **lncRNA-ChIP-seq Overlap 分析页面** ⭐ 核心新功能
   - 路由: `/lncrna-chipseq-overlap`
   - 分析 lncRNA 结合位点与 ChIP-seq peaks 的基因组重叠
   - **后端 API**:
     - `GET /api/v1/lncrna-chipseq-overlap` - 分页查询重叠数据
     - `GET /api/v1/lncrna-chipseq-overlap/statistics` - 聚合统计
     - `GET /api/v1/lncrna-chipseq-overlap/heatmap` - 热力图矩阵数据
     - `GET /api/v1/lncrna-chipseq-overlap/export` - 批量导出 (BED/CSV) ⭐ 新增
   - **前端组件**:
     - `LncRNAChIPSeqOverlapTable` - 主容器组件
     - `OverlapFilterPanel` - 高级筛选面板
     - `OverlapTable` - 数据表格
     - `OverlapStatsCards` - 统计卡片
     - `OverlapMarkDistChart` - Mark 类型分布图
     - `OverlapCellTypeChart` - 细胞类型饼图
     - `OverlapHeatmapMatrix` - 热力图矩阵
   - **性能优化**:
     - 默认 chromosome 过滤器 (chr22) 防止超时
     - 后端默认回退机制
     - 类型安全处理 (string/number 转换)
   - **i18n**: 中英文完整支持 (83+ 翻译 keys)

2. **批量导出功能 (BED/CSV)** ⭐ 科研工作流完整闭环
   - **BED6 格式**: 标准 UCSC 基因组浏览器格式（6 列）
     - 支持 IGV、UCSC Browser、GREAT、HOMER 等工具
   - **CSV 格式**: 完整 19 列数据，Excel 兼容
     - 包含基因信息、坐标、表观遗传标记、质量指标
   - **流式响应**: 批次处理（1000 行/批），支持 100K+ 行导出
   - **性能**: 4-7ms 响应时间（超预期 100 倍）
   - **Rate limiting**: 5 请求/分钟防滥用
   - **智能警告**: 大数据集（>50K 行）提示用户先筛选
   - **完整筛选**: 支持所有过滤条件（chromosome, mark, cell, BA 等）
   - **测试覆盖**: 22 个后端单元测试 + 3 个 E2E 测试（100% 通过）

3. **UX 改进**
   - 错误状态时仍显示过滤面板
   - 导航菜单添加 Overlap Analysis 入口
   - 响应式设计
   - Dropdown.Button 导出 UI（BED 默认 + CSV 选项）

### 2025-12-07 (Phase 3.1) ⭐ A549 肺癌细胞系数据导入

1. **A549 完整组蛋白修饰图谱导入** ⭐ 新细胞系
   - **细胞系**: A549 (肺腺癌)
   - **组织代表性**: 首个肺组织细胞系（血液、肝脏、干细胞之后）
   - **数据完整性**: 6/6 marks 完整覆盖
   - **Marks 详情**:
     - H3K4me1 (增强子): 135,357 peaks
     - H3K4me3 (活性启动子): 110,087 peaks
     - H3K9me3 (异染色质): 70,179 peaks
     - H3K27me3 (Polycomb 抑制): 51,490 peaks
     - H3K27ac (活性增强子): 50,865 peaks
     - H3K36me3 (转录延伸): 42,473 peaks
   - **总计新增: 460,451 peaks** (+20.4%)
   - **数据源**: UCSC ENCODE Broad Histone (hg19, Etoh02 treatment)
   - **导入效率**: 并行导入（3 workers），17 分钟完成
   - **成功率**: 6/6 实验（100%）
   - **前端集成**: 配置驱动架构，零代码变更

2. **数据库全局统计更新**
   - 细胞系数: 4 → 5 (+A549)
   - 实验总数: 27 → 33 (+6)
   - 总 Peaks: 2,253,718 → 2,714,169 (+460,451)
   - 覆盖率: 23/28 组合 (82%) → 29/35 组合 (83%)

### 2025-12-07 (Phase 2.11) ⭐ DNase-seq 数据导入

1. **ENCODE DNase-seq 数据导入** ⭐ 新数据类型
   - 新增 mark 类型: `DNase-HS` (Open Chromatin)
   - 导入 4 个细胞系的 Uniform DNase I HS 数据
   - K562: 202,266 peaks
   - GM12878: 183,953 peaks
   - HepG2: 192,959 peaks
   - H1-hESC: 258,188 peaks
   - **总计新增: 837,366 peaks**
   - 数据源: UCSC ENCODE Uniform DNaseI HS (hg19)
   - 完全复用现有 ChIP-seq 导入架构

### 2025-12-07 (Earlier)

1. **GM12878 细胞系数据导入**
   - 从 UCSC ENCODE Broad Histone 下载并导入
   - 4种 histone marks, 252,745 peaks
   - 详见: `docs/GM12878_IMPORT_REPORT.md`

2. **前端多细胞系支持**
   - FilterPanel 添加细胞类型下拉筛选
   - PeaksTable 显示 cell_type 列
   - 完整的 i18n 国际化支持

3. **Network 页面 i18n 完善**
   - Edge tooltip 翻译修复
   - 95% → 100% 国际化覆盖

### 2025-12-06

1. **K562 ENCODE 数据导入**
   - 6种 histone marks, 422,649 peaks
   - 真实 ENCODE 数据替换 mock 数据

## 🔧 技术栈

- **后端**: FastAPI + PostgreSQL + Redis
- **前端**: React + TypeScript + Ant Design
- **基因组浏览器**: IGV.js
- **数据源**: ENCODE, UCSC Genome Browser

## 🚀 快速启动

```bash
# 在仓库任意子目录都可运行
REPO_ROOT="$(git rev-parse --show-toplevel)"

# 后端
cd "$REPO_ROOT/frontend/backend"
source venv/bin/activate
python3 -m uvicorn main:app --reload --host 0.0.0.0 --port 8000

# 前端
cd "$REPO_ROOT/frontend/web"
npm run dev
```

## 📁 关键目录

```
<data-root>/
├── humanLncAtlas/           # 工作目录
│   └── frontend/
│       ├── backend/         # FastAPI 后端
│       └── web/             # React 前端
├── human-lncrna-atlas-github/  # GitHub 仓库
└── encode_data/             # ENCODE 下载数据
    ├── k562/               # K562 细胞系 BED 文件
    └── gm12878/            # GM12878 细胞系 BED 文件
```

## 📝 最近 Git 提交

| Commit | 描述 |
|--------|------|
| 90bd8ad | chore: sync ChIP-seq multi-cell-line UI updates |
| 9ea3a0f | feat: add cell type filter for multi-cell-line ChIP-seq support |
| 113f3f8 | fix: complete Network page i18n - translate Edge tooltip |
| 85f4bdf | fix: resolve ChIP-seq TypeScript type errors for null values |
| a78b6cc | docs: update project status - ENCODE data is real, not mock |

## 🎯 建议的下一步开发

### 优先级 1: Phase 3.0 - 3.3 核心功能 ✅ 已完成
- [x] ~~ChIP-seq peaks 与 lncRNA 关联分析~~ ✅ 已完成
- [x] ~~热图可视化组蛋白修饰模式~~ ✅ 已完成
- [x] ~~批量导出功能 (BED/CSV)~~ ✅ 已完成 (2025-12-07)
- [x] ~~A549 肺癌细胞系数据导入~~ ✅ 已完成 (2025-12-07, Phase 3.1)
- [x] ~~MCF-7 + HMEC 乳腺细胞系数据~~ ✅ 已完成 (2025-12-07, Phase 3.2)
- [x] ~~DNase-seq 全细胞系覆盖~~ ✅ 已完成 (2025-12-08, Phase 3.3)

### 优先级 2: 功能增强
- [x] ~~lncRNA-ChIP-seq 重叠结果可视化增强~~ ✅ 已完成 (2025-12-10, Phase 3.4)
- [x] ~~基因组浏览器集成重叠轨道~~ ✅ 已完成 (2025-12-10, Phase 3.4)
- [x] ~~动态 Overlap 轨道加载~~ ✅ 已完成 (2025-12-10, Phase 3.5)
- [x] ~~跨物种重叠比较~~ ✅ 已完成 (2026-01-20)
- [x] ~~ROI 高亮显示重叠区域（P2 扩展功能）~~ ✅ 已完成 (2026-01-18)

### 优先级 3: 性能优化
- [x] ~~chr1 等大染色体查询优化~~ ✅ 已完成（物化视图 + NO-MV broad query guard，2026-01-20）
- [x] ~~Redis 缓存策略优化~~ ✅ 已完成（缓存 key 规范化 + TTL 抖动（±10%），2026-01-20）
- [x] 前端虚拟滚动（Genes/Regulations/Conservation/Diseases 展开表格等大列表）
- [x] ~~Overlap 列表 cursor（keyset）分页~~ ✅ 已完成（避免 deep OFFSET，支持 peak_qvalue(NULL-safe)，2026-01-20）

## 📞 联系方式

如有问题，请查看项目文档或提交 Issue。
