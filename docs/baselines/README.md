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
- Snapshot 覆盖少量关键端点（健康检查 + 核心分页查询 + options（含 regulations lncrna/target options）+ ChIP-seq marks/stats/experiments(list+detail)/regions + IGV chipseq marks + overlap list/cursor/statistics + overlap compare（含 `species_ids` 子集用例）+ network available combinations + export/regulations（JSON, limit=1, species_ids=1）+ conservation/regulations（分页列表）+ export/high-affinity + export/conservation + export/disease-network），用于快速发现“返回结构/数据摘要”的意外变化。
- 对于仅安装 core/extension 的最小样例库：若未安装 ChIP-seq peaks 相关表，overlap 端点会**优雅降级**为空结果（避免 500 打断基线校验）；这属于预期行为。
- 为了让基线稳定、且不依赖 Redis，生成脚本默认在 `ENV=development` + `ENABLE_CACHE=false` 下运行（可按需覆盖）。

CI：
- `Tests` 工作流会在 Postgres service 上加载 `schema/v2.3/03_sample_data.sql`，并在 **禁用缓存（`ENABLE_CACHE=false`）** 的情况下校验 `api-snapshot.sample.json`（见 `.github/workflows/test.yml` 的 `api-snapshot-baseline` job）。
