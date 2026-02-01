# Baselines（可提交的回归锚点）

本目录存放**可提交到仓库**的最小基线文件，用于在重构/优化时提供“可 diff”的回归锚点（通常以统计摘要 + hash 形式表达）。

## API Snapshot Baseline

- 基线文件：`docs/baselines/api-snapshot.sample.json`
- 生成逻辑：`scripts/api_snapshot.py`
- 生成脚本：
  - Docker Compose：`scripts/baselines/generate_api_snapshot_baseline.sh`
  - 本地 PostgreSQL：`scripts/baselines/generate_api_snapshot_baseline_local.sh`
  - 两个脚本都会在 v2.3 core/extension 之外额外加载 `frontend/backend/sql/chipseq_schema.sql`，以便样例库能产出 overlap 非空回归锚点。

校验：
- 统一入口：`python3 scripts/verify_baselines.py --mode local`
- 已运行后端（无需建库/导入样例数据）：`python3 scripts/verify_baselines.py --mode running --base-url http://localhost:8000`
- Docker Compose：`python3 scripts/verify_baselines.py --mode docker`

说明：
- `api-snapshot.sample.json` 使用 `--deterministic --no-json` 生成，避免时间戳、Git SHA、base_url 或完整 JSON body 导致的噪音 diff。
- 为避免 runner/本机时区差异导致 `timestamptz` 序列化漂移，后端在 Postgres 连接建立时会统一 `SET TIME ZONE 'UTC'`（见 `frontend/backend/app/core/database.py`）。
- Snapshot 覆盖少量关键端点（健康检查 + 核心分页查询 + options（含 regulations lncrna/target options）+ ChIP-seq marks/stats/experiments(list+detail)/regions + IGV chipseq marks + overlap list/cursor/statistics + overlap compare（含 `species_ids` 子集用例）+ network available combinations + network disease/gene detail + visualization/sankey-data + visualization/chord-data + export/regulations（JSON, limit=1, species_ids=1）+ conservation/regulations（分页列表）+ export/high-affinity + export/conservation + export/disease-network），用于快速发现“返回结构/数据摘要”的意外变化。
- 对于仅安装 core/extension 的最小样例库：若未安装 ChIP-seq peaks 相关表，overlap 端点会**优雅降级**为空结果（避免 500 打断基线校验）；这属于预期行为。
- 为了让基线稳定、且不依赖 Redis，生成脚本默认在 `ENV=development` + `ENABLE_CACHE=false` 下运行（可按需覆盖）。

CI：
- `Tests` 工作流会在 Postgres service 上加载 `schema/v2.3/03_sample_data.sql`，并在 **禁用缓存（`ENABLE_CACHE=false`）** 的情况下校验 `api-snapshot.sample.json`（见 `.github/workflows/test.yml` 的 `api-snapshot-baseline` job）。

## Performance Baseline（Overlap，手动门禁）

- 基线文件：`docs/baselines/performance/overlap-admin-metrics.baseline.json`
- 定位用基线（可选但推荐）：`docs/baselines/performance/overlap-admin-metrics.baseline.raw.json`（baseline 时刻的原始 `/api/v1/admin/metrics`）
- 生成逻辑：`scripts/perf_overlap_regression.py`（基于 `GET /api/v1/admin/metrics` 的端点尾延迟/DB 百分位）
- 生成命令（建议在稳定环境，例如 self-hosted runner）：

  ```bash
  python3 scripts/perf_overlap_regression.py generate-baseline \
    --base-url "http://127.0.0.1:8000" \
    --baseline-raw-metrics-file "docs/baselines/performance/overlap-admin-metrics.baseline.raw.json" \
    --warmup-rounds 20 \
    --lncrna-gene-id 17276 \
    --species-ids "1,3"
  ```

校验：
- `python3 scripts/perf_overlap_regression.py check --base-url "http://127.0.0.1:8000" --baseline-raw-metrics-file "docs/baselines/performance/overlap-admin-metrics.baseline.raw.json"`

说明：
- baseline 初始为 `UNSET`，避免“未初始化基线”的静默通过；请先生成并提交一次 baseline。
- percentiles 对样本量敏感：脚本会做 warmup，并在样本不足时直接 FAIL（更利于发现“指标不足/环境不稳定”的问题）。
- 若你没有现成可用后端，可使用 docker compose + sample 数据的止损脚本：`bash scripts/baselines/run_overlap_perf_regression_docker.sh`（见 `docs/testing/performance/OVERLAP_PERF_REGRESSION.md`）。
- 当门禁失败且提供了 baseline raw metrics 文件时，会额外输出 `docs/reports/perf-overlap-admin-metrics-diff-*.md`，用于定位慢点/慢查询/缓存变化。

## Research（可选：本地烟测）

本仓库还提供一个“本地 sample DB 烟测”脚本，用于快速验证 Research 导出脚本能跑通（不依赖真实大库）。

- 脚本：
  - `scripts/research/generate_top_lncrna_sample_baseline_local.sh`（Top lncRNA 榜单）
  - `scripts/research/generate_top_lncrna_target_genes_sample_baseline_local.sh`（Top lncRNA 靶基因列表，用于富集输入）
  - `scripts/research/generate_conserved_lncrna_sample_baseline_local.sh`（跨物种保守性分层统计 + Top 列表）
  - `scripts/research/generate_conservation_matrix_sample_baseline_local.sh`（保守性矩阵：共享数量 + 行归一化共享率）
  - `scripts/research/generate_conservation_distance_correlation_sample_baseline_local.sh`（进化距离 vs 保守性相关性：pairwise 指标 + Pearson/Spearman）
  - `scripts/research/generate_conserved_lncrna_target_genes_sample_baseline_local.sh`（保守等级分层靶基因列表：TSV/TXT/MD，用于富集输入）
  - `scripts/research/generate_epigenetic_summary_sample_baseline_local.sh`（表观遗传重叠汇总：mark×cell_type×category）
  - `scripts/research/generate_disease_network_summary_sample_baseline_local.sh`（疾病网络汇总：Top diseases / Top lncRNAs）
- 默认输出目录：`docs/baselines/research/`
- 说明：
  - v2.3 sample 数据集的 BA 大约在 55–82，默认 `MIN_BA=50`；若你用 `MIN_BA=100`，大概率会得到空榜单（这是样例数据集的限制，不代表生产数据）。
  - 若需要稳定对比/可提交的 Markdown，可固定 `GENERATED_AT`（脚本默认 `GENERATED_AT=sample`）或使用 `--generated-at` 参数。
