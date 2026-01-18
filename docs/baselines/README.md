# Baselines（可提交的回归锚点）

本目录存放**可提交到仓库**的最小基线文件，用于在重构/优化时提供“可 diff”的回归锚点（通常以统计摘要 + hash 形式表达）。

## API Snapshot Baseline

- 基线文件：`docs/baselines/api-snapshot.sample.json`
- 生成逻辑：`scripts/api_snapshot.py`
- 生成脚本：
  - Docker Compose：`scripts/baselines/generate_api_snapshot_baseline.sh`
  - 本地 PostgreSQL：`scripts/baselines/generate_api_snapshot_baseline_local.sh`

校验：
- 统一入口：`python3 scripts/verify_baselines.py --mode local`
- 已运行后端（无需建库/导入样例数据）：`python3 scripts/verify_baselines.py --mode running --base-url http://localhost:8000`
- Docker Compose：`python3 scripts/verify_baselines.py --mode docker`

说明：
- `api-snapshot.sample.json` 使用 `--deterministic --no-json` 生成，避免时间戳、Git SHA、base_url 或完整 JSON body 导致的噪音 diff。
- Snapshot 覆盖少量关键端点（健康检查 + 核心分页查询 + options），用于快速发现“返回结构/数据摘要”的意外变化。
