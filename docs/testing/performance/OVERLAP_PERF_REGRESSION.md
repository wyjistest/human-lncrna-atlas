# Overlap 性能回归检查（Perf Regression Gate）

目标：为 Overlap 的两个高风险端点提供一个**可定位、可回滚**的性能回归门禁（默认不阻塞 main push，仅用于手动触发）。

- `GET /api/v1/lncrna-chipseq-overlap`
- `GET /api/v1/lncrna-chipseq-overlap/compare`

本门禁基于 `GET /api/v1/admin/metrics` 的端点级尾延迟与 DB 百分位（P95/P99），通过 warmup 制造少量固定流量，生成 compact snapshot，并与仓库内 baseline 做对比。

## 最短路径（本地）

前提：后端已运行（并且能访问 `/api/v1/admin/metrics`）。

### 1) 生成 baseline（第一次必须做）

```bash
python3 scripts/perf_overlap_regression.py generate-baseline \
  --base-url "http://127.0.0.1:8000" \
  --baseline-raw-metrics-file "docs/baselines/performance/overlap-admin-metrics.baseline.raw.json" \
  --warmup-rounds 30 \
  --lncrna-gene-id 17276 \
  --species-ids "1,3"

git add docs/baselines/performance/overlap-admin-metrics.baseline.json \
  docs/baselines/performance/overlap-admin-metrics.baseline.raw.json
git commit -m "perf(baseline): set overlap admin-metrics baseline"
```

说明：
- baseline 文件初始为 `UNSET`，`check` 模式会直接失败，避免“未初始化基线”导致的静默放过。
- 为避免把机器/runner 的绝对路径写进 artifact：若 `--baseline-file` 指向仓库内路径，输出 snapshot 会把 `meta.baseline_file` 记录为 repo 相对路径（统一为 `/` 分隔）。
- `--lncrna-gene-id` 需要在你的数据库中存在且具备 `core_id`（否则 compare 端点会返回 404/400）。  
  若 warmup 阶段 compare 返回 404/400/422，脚本会 best-effort 调用 `/api/v1/genes/options` 自动挑选一个带 `core_id` 的候选 gene_id（确定性规则：在候选集中选择最小 `gene_id`），并把“请求值/实际使用值”记录到输出 snapshot 的 `meta.scenario` 中，便于审计与回滚。
- 如你的环境对 `/api/v1/admin/metrics` 需要鉴权，请提供 Admin API Key：
  - 环境变量：`export ADMIN_API_KEY="..."`，或
  - 参数：`--admin-api-key "..."`（会作为 `X-Admin-API-Key` 发送）。

### 2) 跑回归检查（每次优化/重构后）

```bash
python3 scripts/perf_overlap_regression.py check \
  --base-url "http://127.0.0.1:8000" \
  --baseline-raw-metrics-file "docs/baselines/performance/overlap-admin-metrics.baseline.raw.json" \
  --warmup-rounds 30 \
  --lncrna-gene-id 17276 \
  --species-ids "1,3"
```

输出默认写入 `docs/reports/`：
- `perf-overlap-<timestamp>.md`（可直接贴 issue/comment）
- `perf-overlap-<timestamp>.json`（compact snapshot）
- `perf-overlap-raw-metrics-<timestamp>.json`（原始 `/admin/metrics`）
- （可选）`perf-overlap-admin-metrics-diff-<timestamp>.md`（当门禁失败或显式启用 diff 时：对比 baseline raw metrics vs 当前 raw metrics，用于定位慢点/慢查询/缓存变化）

## 无现成后端时：用 Docker Compose 启动 sample backend（可选）

如果你本机没有可用的 backend（例如 `http://127.0.0.1:8000` 连接拒绝），可以用仓库自带脚本启动一套**隔离的** docker compose（Postgres+Redis+Backend，加载 v2.3 sample 数据），然后跑 perf gate：

```bash
MODE=generate-baseline bash scripts/baselines/run_overlap_perf_regression_docker.sh
```

该脚本会把生成的 baseline 写回：

- `docs/baselines/performance/overlap-admin-metrics.baseline.json`
- `docs/baselines/performance/overlap-admin-metrics.baseline.raw.json`（用于定位 diff）

并在退出时自动清理容器（可用 `KEEP_DOCKER=true` 保留用于排障）。

## 门禁规则（当前阈值）

- 最小样本：每个端点 `requests >= 20`（否则直接 FAIL，避免“样本不足导致 percentiles 为 null”的静默通过）
- 触发 FAIL 的回归阈值（同时满足“比例 + 绝对值”）：
  - Response：`>8%` 且 `>5ms`
  - DB：`>8%` 且 `>2ms`

> 仍然采用“比例 + 绝对值”双阈值以降低环境抖动；阈值已收紧，用于更早发现回归。  
> 如需临时调整：可通过参数覆盖（例如 `--response-regression-pct`、`--db-regression-pct`、`--min-samples`）。

## GitHub Actions（workflow_dispatch）

工作流：`Performance Overlap`（见 `.github/workflows/performance-overlap.yml`）

建议用法：
1. 第一次：选择 `mode=generate-baseline` 生成 baseline。
2. 如果 runner 上没有常驻后端：把 `backend_mode` 设为 `docker-sample`（会自动启动 sample backend 后再跑）。
3. 下载 artifact 中的 baseline 文件，并提交到仓库。
4. 后续：选择 `mode=check`（同理可选 `backend_mode=docker-sample`）用于验证优化/重构是否引入明显回归。

Artifacts（即使失败也会上传）：
- `docs/reports/perf-overlap-*.md`
- `docs/reports/perf-overlap-*.json`
- `docs/baselines/performance/overlap-admin-metrics.baseline.json`
- `docs/baselines/performance/overlap-admin-metrics.baseline.raw.json`
