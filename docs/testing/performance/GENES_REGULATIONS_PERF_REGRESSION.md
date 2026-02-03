# Genes / Regulations 性能回归检查（Perf Regression Gate）

目标：为两个高风险列表端点提供一个**可定位、可回滚**的性能回归门禁（默认不阻塞 main push，仅用于手动触发）。

- `GET /api/v1/genes`
- `GET /api/v1/regulations`

本门禁基于 `GET /api/v1/admin/metrics` 的端点级尾延迟与 DB 百分位（P95/P99），通过 warmup 制造少量固定流量，生成 compact snapshot，并与仓库内 baseline 做对比。

## 最短路径（本地）

前提：后端已运行（并且能访问 `/api/v1/admin/metrics`）。

### 1) 生成 baseline（第一次必须做）

```bash
python3 scripts/perf_genes_regulations_regression.py generate-baseline \
  --base-url "http://127.0.0.1:8000" \
  --baseline-raw-metrics-file "docs/baselines/performance/genes-regulations-admin-metrics.baseline.raw.json" \
  --warmup-rounds 30 \
  --genes-species-id 1 \
  --genes-gene-type "lncRNA" \
  --genes-page-size 100 \
  --regulations-species-id 1 \
  --regulations-page-size 100

git add docs/baselines/performance/genes-regulations-admin-metrics.baseline.json \
  docs/baselines/performance/genes-regulations-admin-metrics.baseline.raw.json
git commit -m "perf(baseline): set genes/regulations admin-metrics baseline"
```

如你的环境对 `/api/v1/admin/metrics` 需要鉴权，请提供 Admin API Key：

- 环境变量：`export ADMIN_API_KEY="..."`，或
- 参数：`--admin-api-key "..."`（会作为 `X-Admin-API-Key` 发送）。

### 2) 跑回归检查（每次优化/重构后）

```bash
python3 scripts/perf_genes_regulations_regression.py check \
  --base-url "http://127.0.0.1:8000" \
  --baseline-raw-metrics-file "docs/baselines/performance/genes-regulations-admin-metrics.baseline.raw.json" \
  --warmup-rounds 30 \
  --genes-species-id 1 \
  --genes-gene-type "lncRNA" \
  --genes-page-size 100 \
  --regulations-species-id 1 \
  --regulations-page-size 100
```

输出默认写入 `docs/reports/`：

- `perf-genes-regulations-<timestamp>.md`（可直接贴 issue/comment）
- `perf-genes-regulations-<timestamp>.json`（compact snapshot）
- `perf-genes-regulations-raw-metrics-<timestamp>.json`（原始 `/admin/metrics`）
- （可选）`perf-genes-regulations-admin-metrics-diff-<timestamp>.md`（当门禁失败或显式启用 diff 时：对比 baseline raw metrics vs 当前 raw metrics，用于定位慢点/慢查询/缓存变化）

> 你也可以加 `--emit-admin-metrics-diff` 在通过时强制输出 diff（需要 `--baseline-raw-metrics-file`）。

## 无现成后端时：用 Docker Compose 启动 sample backend（可选）

如果你本机没有可用的 backend（例如 `http://127.0.0.1:8000` 连接拒绝），可以用仓库自带脚本启动一套**隔离的** docker compose（Postgres+Redis+Backend，加载 v2.3 sample 数据），然后跑 perf gate：

```bash
MODE=generate-baseline bash scripts/baselines/run_genes_regulations_perf_regression_docker.sh
```

该脚本会把生成的 baseline 写回：

- `docs/baselines/performance/genes-regulations-admin-metrics.baseline.json`
- `docs/baselines/performance/genes-regulations-admin-metrics.baseline.raw.json`（用于定位 diff）

并在退出时自动清理容器（可用 `KEEP_DOCKER=true` 保留用于排障）。

## 门禁规则（当前阈值）

- 最小样本：每个端点 `requests >= 20`（否则直接 FAIL，避免“样本不足导致 percentiles 为 null”的静默通过）
- 触发 FAIL 的回归阈值（同时满足“比例 + 绝对值”）：
  - Response：`>8%` 且 `>20ms`
  - DB：`>8%` 且 `>2ms`

> 如需临时调整：可通过参数覆盖（例如 `--response-regression-pct`、`--db-regression-pct`、`--min-samples`）。

## GitHub Actions（workflow_dispatch）

工作流：`Performance Genes/Regulations`（见 `.github/workflows/performance-genes-regulations.yml`）

建议用法：

1. 第一次：选择 `mode=generate-baseline` 生成 baseline。
2. 如果 runner 上没有常驻后端：把 `backend_mode` 设为 `docker-sample`（会自动启动 sample backend 后再跑）。
3. 下载 artifact 中的 baseline 文件，并提交到仓库。
4. 后续：选择 `mode=check`（同理可选 `backend_mode=docker-sample`）用于验证优化/重构是否引入明显回归。

Artifacts（即使失败也会上传）：

- `docs/reports/perf-genes-regulations-*.md`
- `docs/reports/perf-genes-regulations-*.json`
- `docs/baselines/performance/genes-regulations-admin-metrics.baseline.json`
- `docs/baselines/performance/genes-regulations-admin-metrics.baseline.raw.json`
