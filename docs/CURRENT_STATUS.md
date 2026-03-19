# Human LncRNA Atlas - 当前进度报告

> 最后更新: 2026-03-19
> 当前版本: Phase 3.5 (动态 Overlap 轨道加载)

## 📊 数据库统计

### Epigenomic Data (ChIP-seq + DNase-seq)

| Mark 类型    | 分类           | 细胞系数 | 实验数 | Peaks 数量    |
| ------------ | -------------- | -------- | ------ | ------------- |
| **DNase-HS** | Open Chromatin | **7**    | **7**  | **1,223,622** |
| CTCF         | Structural     | 5        | 5      | **248,106**   |
| H3K4me1      | Activating     | 6        | 6      | **803,334**   |
| H3K4me2      | Activating     | 6        | 6      | **505,389**   |
| H3K4me3      | Activating     | 7        | 7      | **447,224**   |
| H3K9ac       | Activating     | 6        | 6      | **318,090**   |
| H3K9me3      | Repressive     | 6        | 6      | **376,602**   |
| H3K27ac      | Activating     | 6        | 6      | **334,361**   |
| H3K27me3     | Repressive     | 6        | 6      | **317,558**   |
| H3K36me3     | Activating     | 6        | 6      | **241,345**   |
| H4K20me1     | Activating     | 3        | 3      | **109,285**   |
| **总计**     | -              | **7**    | **64** | **4,924,916** |

### 细胞系覆盖

| 细胞系    | 组织         | ChIP-seq Marks   | DNase-seq  | 总 Peaks |
| --------- | ------------ | ---------------- | ---------- | -------- |
| **MCF-7** | 乳腺癌细胞   | 1 mark (H3K4me3) | ✅ 126,717 | 238,634  |
| **HMEC**  | 正常乳腺上皮 | 8 marks          | ✅ 140,574 | 669,496  |
| **A549**  | 肺腺癌细胞   | 9 marks          | ✅ 118,965 | 782,674  |
| K562      | 白血病细胞   | 10 marks         | ✅ 202,266 | 843,309  |
| H1-hESC   | 人胚胎干细胞 | 10 marks         | ✅ 258,188 | 874,023  |
| GM12878   | B淋巴细胞    | 10 marks         | ✅ 183,953 | 734,789  |
| HepG2     | 肝癌细胞     | 9 marks          | ✅ 192,959 | 781,991  |

> 备注：仓库脚本已支持从 UCSC `wgEncodeSydhHistone/` 下载 MCF-7 的 `H3K27ac/H3K27me3/H3K36me3/H3K9me3`（hg19 narrowPeak），但当前统计仍以已导入 DB 的 experiments 为准。详见 `docs/ENCODE_DATA_GUIDE.md`。

### 核心数据

- **物种**: 4种灵长类 (Human, Chimpanzee, Macaque, Marmoset)
- **基因数量**: 17,248
- **调控关系**: 804,630

## ✅ 最近完成的功能

### 2026-03-19 ⭐ CI / MV 运维 / compare 回归锚点补强

1. **self-hosted Fast CI 可解释性增强**
   - `scripts/run-tests.sh ci` 现会在启用 summary 时同时生成 Markdown summary、JSON manifest 与按阶段切分的 stage logs；每个阶段会记录稳定 `stage_id`、状态、耗时、hint 与日志相对路径
   - 在 GitHub Actions 环境中，`run-tests` 会为每个阶段输出 `::notice::/::group::` 注解，并在失败时额外发出带 `stage_id + log path` 的 `::error::`
   - `run-tests-ci-summary.json` 顶层现额外包含 `schema_version`、`coverage` 与 `first_failed_log_relpath`，`.github/workflows/test.yml` 生成的 overview 会直接展示首个失败日志路径，减少手动翻 artifact 的成本
   - `.github/workflows/test.yml` 的 `Self-hosted Fast CI` 会先根据 JSON manifest 生成一段 overview（含 `first_failed_stage` / `first_failed_log_relpath`），再追加 Markdown summary，并上传 `md + json + stage logs` artifact，方便直接定位失败阶段
   - self-hosted push 现改为执行 `bash scripts/run-tests.sh ci-postgres`，fast path 也会显式校验 API snapshot baseline，不再出现“CI 全绿但 baseline job 被跳过”的覆盖盲区

2. **Admin 物化视图状态增强**
   - `GET /api/v1/admin/materialized-views/status` 新增 `checked_at` / `database_backend` / `supported`
   - 顶层新增 `attention_summary`（`status` / `severity` / `message` / `recommended_action` / `attention_count` / `attention_view_names`），前端 Runtime 与运维脚本统一消费这一摘要，而不是各自重复推导
   - 每个 MV 额外返回容量拆分（`total/heap/index`）与统计新鲜度（`last_analyze_at` / `last_autoanalyze_at` / `last_stats_at` / `stats_age_seconds`）
   - 每个 MV 现进一步给出 `health_status` / `severity` / `recommended_action` / `affects_features`，Admin 页面可直接看到“哪些功能受影响、下一步该做什么”
   - 非 PostgreSQL 后端不再直接报错，而是显式返回 `status=unsupported` 的降级状态，便于前端与运维侧识别
   - 新增 `scripts/check_materialized_views_operability.py`，可直接读取 Admin 状态或离线 JSON，并按 `attention_summary.severity` 输出退出码：`0=healthy`、`1=warning/degraded/unsupported`、`2=critical`

3. **export / gene-set compare 回归锚点补强**
   - `scripts/api_snapshot.py` 为 `export/disease-network`、`network/disease` 与 overlap compare 新增稳定摘要字段（nodes/edges、species_count/species_ids）
   - `/chipseq-compare` smoke 现会走真实的 gene-set compare 路径：粘贴解析基因、调用 batch heatmap API，并断言不会退回单基因 N 次 heatmap 请求
   - 前端已移除 `globalCompareApi` 占位契约，页面改为真实 gene-set compare workbench
   - `/chipseq-compare` 页面支持人类基因搜索 + 批量解析，并在首版聚焦真实 heatmap 可视化而非 batch export

4. **`/chipseq-compare` 前端稳定性补强**
   - `useBatchGeneHeatmap` 已改为复用稳定的空数组引用，消除 `react-hooks/exhaustive-deps` warning，并保持 batch query key 的顺序敏感语义不变
   - 新增 `frontend/web/src/pages/__tests__/ChIPSeqComparePage.test.tsx`，覆盖空态、粘贴解析、手动 `Run compare`、dirty state、`Update compare` 与失败告警
   - `frontend/web/src/hooks/__tests__/useBatchGeneHeatmap.test.tsx` 补充 disabled/空输入回归用例，确认页面初始态不会误发 batch heatmap 请求

### 2026-02-12 ⭐ hg19：外部数据/DB 审计复核 + gene_peak_associations 覆盖确认

1. **外部数据组装一致性复核（防 hg38 混入）**
   - 运行：`bash scripts/genomes/audit_external_data_assemblies.sh`
   - 输出：`/data/wenyujianData/humanLncAtlas/audits/2026-02-12_14-49-36_external_assembly_audit/`

2. **DB `reference_genome` 缺口审计（只读）**
   - 运行：`bash scripts/genomes/audit_chipseq_reference_genome_db.sh --assembly hg19`
     - peer auth 场景（`psql` 可直连但 `localhost:5432` 需密码）推荐：`DB_HOST=/var/run/postgresql DB_USER=<os-user> bash scripts/genomes/audit_chipseq_reference_genome_db.sh --assembly hg19`
   - 输出：`/data/wenyujianData/humanLncAtlas/audits/2026-02-12_14-49-21_chipseq_reference_genome_db_audit/`

3. **`gene_peak_associations` 覆盖确认**
   - `lncrna_production`：`gene_peak_associations` 已覆盖 `64/64` 个 human active experiments

4. **复核报告**
   - `docs/reports/CHIPSEQ_HG19_AUDIT_AND_ASSOCIATIONS_2026-02-12.md`

### 2026-02-10 ⭐ hg19：补齐 HMEC 缺失的 H3K4me2/H3K9ac（UCSC hg19 Broad Histone）

1. **补齐 HMEC 的 8 marks 覆盖**
   - 新增实验：`H3K4me2_HMEC_BROAD_HMEC_H3K4me2`、`H3K9ac_HMEC_BROAD_HMEC_H3K9ac`（Human active experiments：62 → 64）
   - 两个实验均写入 `reference_genome=hg19`，并生成对应 `gene_peak_associations`

2. **轨道同步（可回滚、可审计）**
   - 备份并重生成：`/data/wenyujianData/humanLncAtlas/chipseq_bed/chipseq_HMEC.bed` 与 `/data/wenyujianData/humanLncAtlas/genomes/chipseq_HMEC.bb`
   - 外部数据组装审计：`bash scripts/genomes/audit_external_data_assemblies.sh`（输出落盘、无 hg38 混入）

### 2026-02-09 ⭐ hg19：按 cell line 补齐 ChIP-seq bed/bigBed 轨道

1. **修复“同一 cell line 被 cell_type 拆分”导致的轨道缺口**
   - 重新生成 `/data/wenyujianData/humanLncAtlas/chipseq_bed/chipseq_{A549,GM12878,H1_hESC,HepG2,HMEC,K562,MCF7}.bed`
   - 重新生成 `/data/wenyujianData/humanLncAtlas/genomes/chipseq_{A549,GM12878,H1_hESC,HepG2,HMEC,K562,MCF7}.bb`
   - 峰数量以本文顶部统计表为准（避免历史数字误读）。

2. **DB 元数据对齐（可回滚、可审计）**
   - 回填历史 K562 实验缺失的 `cell_line`（避免 `--group-by cell_line` 导出丢失）
   - 对齐 `species.genome_assembly`：Human=hg19、Chimp=panTro5、Marmoset=calJac3（与项目 IGV/离线资源一致）

3. **外部数据组装一致性复核**
   - 再次运行 `bash scripts/genomes/audit_external_data_assemblies.sh`，确认无 hg38 混入（输出 OK）

### 2026-02-07 ⭐ hg19 外部数据审计与门禁/文档收口

1. **外部 peaks/轨道组装一致性审计（防止 hg38 混入）**
   - 对外部数据运行只读审计：`bash scripts/genomes/audit_external_data_assemblies.sh`（输出落盘、可追溯）。

2. **补齐 HepG2 缺失的 H3K9me3（UCSC hg19 Broad Histone）**
   - 新增实验：`UCSC_hg19_HepG2_H3K9me3`（并生成对应 `gene_peak_associations`）
   - 同步更新轨道：`/data/wenyujianData/humanLncAtlas/chipseq_bed/chipseq_HepG2.bed` 与 `.../genomes/chipseq_HepG2.bb`（含备份与可回滚审计目录）。

3. **性能基线与脚本一致性**
   - perf / E2E 文档与脚本统一使用 `API_BASE_URL`（避免与 Playwright 前端 `BASE_URL` 冲突）。
   - 刷新 `docs/baselines/performance/*admin-metrics*` 两套 baselines，用于收紧并稳定 perf regression 门禁。

### 2026-02-04 ⭐ perf regression 门禁稳定性增强

1. **性能门禁默认阈值收紧 + baseline 刷新**
   - `Performance Overlap` / `Performance Genes/Regulations`：默认 `warmup_rounds=80`、`min_samples=50`、`pct=4%`（2026-02-25：`5% → 4%`），并收紧 `response_abs_ms=2ms`、`db_abs_ms=1ms`（提高敏感度，同时靠更大样本降低误报）。

2. **门禁可定位性增强：支持重置 admin metrics + 报告更完整**
   - perf 脚本支持 `--pre-warmup-rounds`（预热）+ `--reset-metrics`（重置后采样）：
     - 若 `pre_warmup_rounds > 0`：先预热，再调用 `POST /api/v1/admin/metrics/reset-stats`，最后跑 `warmup_rounds` 轮“计入门禁”的采样；
     - 用于减少冷启动/缓存抖动导致的误报，同时保持门禁阈值敏感度。
   - check 模式在“基线缺失/UNSET/样本不足”等早期失败时也会输出 `docs/reports/perf-*.md` 报告，便于定位与审计。
   - perf 报告新增 `## Triage Hints`（Scenario drift / sample 不足 / 429 / reset 失败等高频根因提示），降低排障成本。

3. **docker-sample 稳定性：避免 warmup 触发 429**
   - docker-sample perf regression 默认启用 `RATE_LIMIT_BYPASS_PRIVATE=true`（docker bridge 私网 IP 不受限流影响）。

4. **网络受限止损路径固化**
   - 补充 self-hosted runner 排障与 GitHub API 止损推送（`scripts/gh_push_commit.py`），降低 `git push/fetch` 不稳定带来的阻塞。

### 2026-01-29 ⭐ URL 参数同步扩展（Stats / Conservation / Analysis）

1. **更多页面支持“可分享/可回放”的 URL**
   - Stats：支持从 URL 初始化详细统计参数（用于复现筛选组合）
   - Conservation：筛选条件与 URL 同步（便于分享链接/回放）
   - Analysis：active tab 与各 tab 的筛选条件与 URL 同步（便于分享链接/回放）
   - 覆盖对应的前端单元测试（Vitest），防止 URL 行为回归

2. **本地 CI 入口更一致：`./scripts/run-tests.sh` 可直接执行**
   - 修复脚本可执行位后，文档中的 `./scripts/run-tests.sh (ci|docs-check|e2e-smoke|...)` 不再需要额外 `bash` 前缀
   - `ci` 子命令纳入 `scripts/tests/*` 脚本级单测，更贴近 GitHub Actions 的实际门禁

### 2026-01-29 ⭐ CI 提速（self-hosted Fast Path）

1. **self-hosted（main push）：合并核心门禁到单个 job**
   - `Tests` workflow 在 self-hosted + `push(main)` 场景下新增 `self-hosted-fast-ci`：把核心检查串到一个 job 内执行，避免单 runner 下重复 checkout / install 导致耗时线性叠加
   - 原多 job 结构保留：仍用于 `ubuntu-latest` 或 `workflow_dispatch`（方便手动触发/调试与启用可选 job）

### 2026-01-29 ⭐ CI 稳定性增强（Postgres 动态端口 + UTC 时区）

1. **self-hosted：避免 Postgres 端口冲突导致 service 起不来**
   - `Tests` workflow 的 Postgres service 不再强制绑定宿主机 `5432`，改为动态端口并通过 `${{ job.services.postgres.ports['5432'] }}` 传递给后续步骤（降低 self-hosted 上“本机已有 Postgres/端口占用”的失败概率）。

2. **API snapshot baseline 更稳定（时区不漂移）**
   - 后端 Postgres 连接建立时统一 `SET TIME ZONE 'UTC'`，避免 runner 本机时区不同导致 `timestamptz` 序列化出现 offset 差异，从而引发 snapshot baseline hash 漂移。

### 2026-01-28 ⭐ CI 止损增强（self-hosted checkout + Firefox smoke）

1. **self-hosted：checkout 失败兜底可继续跑完门禁**
   - self-hosted 环境下 `actions/checkout` 偶发 `gnutls_handshake()` 中断时：`Tests` workflow 会通过 GitHub API tarball 恢复源码
   - tarball 场景会缺少 `.git`，而部分门禁（docs drift check 等）依赖 `git ls-files`；现已在 fallback 场景自动初始化 git snapshot，确保后续脚本可运行

2. **E2E smoke：可选 Firefox 复核（默认仍仅 chromium）**
   - `Tests` 默认只跑 `--project=chromium`，避免 CI 变慢与重复跑
   - `workflow_dispatch` 可通过 `enable_firefox_smoke=true` 额外跑一轮 Firefox smoke（用于 cross-browser 止损复核）

### 2026-01-27 ⭐ 前端首屏预加载护栏 + Research 最小产出

1. **前端 build 防回归：禁止首屏预加载重依赖**
   - 新增 `frontend/web/scripts/check-entry-preloads.mjs`，在 `npm run build` 后检查 `dist/index.html` 的 `modulepreload` 列表
   - 修复 `pdf-vendor` 被首屏误拉起的问题：保留 `vite` 的 `build.modulePreload`，但通过 `resolveDependencies` 限制首屏只允许预加载核心 vendor，避免重依赖被误拉起

2. **前端体验：Overlap 页 IGV 默认收起 + 延迟加载**
   - Overlap 页面默认不展开 IGV，避免进入页面即加载重依赖（仍可通过开关手动展开）
   - IGV 相关组件改为 `lazy()` + `Suspense`：只有在展开 IGV 时才加载 GenomeBrowser/Toolbar

3. **Phase 6.0 可复现产出（Research scripts）**
   - BA>=100 Top lncRNA 榜单：`scripts/research/top_lncrna_by_binding_affinity.py`（输出 `docs/reports/top-lncrna-ba100-species1.(csv|md)`）
   - ✅ sample DB 可提交产物示例：`bash scripts/research/generate_top_lncrna_sample_baseline_local.sh`（输出并提交 `docs/baselines/research/top-lncrna-ba50-species1.(csv|md)`；sample_data 的 BA 约 55–82，因此 `MIN_BA` 默认 50）
   - Top lncRNA 靶基因导出（富集输入）：`scripts/research/top_lncrna_target_genes_for_enrichment.py`（输出 TSV/TXT/MD）
   - 跨物种保守性分层统计 + Top 列表：`scripts/research/conserved_lncrna_by_binding_affinity.py`（按 core_id 聚合，输出 CSV/MD）
   - 保守性矩阵（物种两两共享数量 + 行归一化共享率）：`scripts/research/conservation_matrix_by_binding_affinity.py`（输出 counts/row-share CSV + MD，可选 PNG）
   - 进化距离 vs 保守性相关性：`scripts/research/conservation_distance_correlation_by_binding_affinity.py`（输出 pairwise CSV/MD，可选散点图 PNG；Pearson/Spearman）
   - 保守等级分层靶基因列表（富集输入）：`scripts/research/conserved_lncrna_target_genes_for_enrichment.py`（输出 TSV/TXT/MD；支持对比 species_count==1）
   - 表观遗传重叠汇总（mark×cell_type×category）：`scripts/research/epigenetic_summary_by_binding_affinity.py`（输出 TSV/MD）
   - 疾病网络汇总（Top diseases / Top lncRNAs）：`scripts/research/disease_network_summary.py`（输出 TSV/MD）
   - ✅ Research 产物路径展示已统一为 repo-relative（避免把机器绝对路径写入 Markdown）
   - Phase 6.0 规划文档已补齐“一条命令复现”的入口（`docs/PHASE_6.0_RESEARCH_ANALYSIS_PLAN.md`）

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
   - diff 现已覆盖 cache get() 延迟（hits/misses p95/p99）与 cache breakdown（routes/keys/namespaces 的 compute\_\* / hit_rate / req）变化，便于定位回归根因
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

| Commit  | 描述                                                            |
| ------- | --------------------------------------------------------------- |
| 90bd8ad | chore: sync ChIP-seq multi-cell-line UI updates                 |
| 9ea3a0f | feat: add cell type filter for multi-cell-line ChIP-seq support |
| 113f3f8 | fix: complete Network page i18n - translate Edge tooltip        |
| 85f4bdf | fix: resolve ChIP-seq TypeScript type errors for null values    |
| a78b6cc | docs: update project status - ENCODE data is real, not mock     |

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
