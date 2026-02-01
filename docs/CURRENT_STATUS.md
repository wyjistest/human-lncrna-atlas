# Current Status

> 最后更新：2026-01-31  
> 说明：仓库内大量 `docs/**` 为历史快照/规划记录（用于回溯与对照），不代表当前实现现状。  
> 当你在文档里看到类似 “TODO / checkbox / mock / stub / 待实现” 等信号时，请以本页为唯一权威现状入口。

## TL;DR（最短路径）

**本地核心门禁（≈ CI）**

```bash
bash scripts/run-tests.sh ci
```

**本地 CI 自举指引（新机器/新环境）**

见：`docs/LOCAL_CI_BOOTSTRAP.md`

**最新路线图（1–2 周）**

见：`docs/roadmaps/ROADMAP_CURRENT.md`

**仅跑文档门禁**

```bash
bash scripts/run-tests.sh docs-check
```

**Overlap 性能回归门禁（本地）**

```bash
python3 scripts/perf_overlap_regression.py check \
  --base-url "http://127.0.0.1:8000" \
  --warmup-rounds 20 \
  --lncrna-gene-id 17276 \
  --species-ids "1,3"
```

**Genes / Regulations 性能回归门禁（本地）**

```bash
python3 scripts/perf_genes_regulations_regression.py check \
  --base-url "http://127.0.0.1:8000" \
  --baseline-raw-metrics-file "docs/baselines/performance/genes-regulations-admin-metrics.baseline.raw.json" \
  --warmup-rounds 20 \
  --genes-species-id 1 \
  --genes-gene-type "lncRNA" \
  --genes-page-size 100 \
  --regulations-species-id 1 \
  --regulations-page-size 100
```

**性能定位导出（Admin metrics，一键生成 JSON + Markdown）**

```bash
python3 scripts/admin_metrics_snapshot.py --base-url "http://127.0.0.1:8000"
```

## 常用环境变量

- `API_BASE_URL`：后端 base url（供脚本/CI 使用）
- `ADMIN_API_KEY`：访问 `/api/v1/admin/metrics`（脚本会作为 `X-Admin-API-Key` 发送；不要贴到 issue）
- `CI_RUNS_ON`：Actions 运行在哪（`self-hosted` / `ubuntu-latest`，见 `docs/CI_SELF_HOSTED_RUNNER.md`）
- `CI_ENABLE_POSTGRES_JOBS`：是否在 self-hosted 上启用 Postgres service job（见 `docs/CI_SELF_HOSTED_RUNNER.md`）

## 当前可用能力（面向使用者）

- 基因/调控/疾病查询与筛选：Genes / Regulations / Diseases 页面
- 统计与分析：Stats / Analysis / Conservation（含多个 tab）
- 基因组浏览：IGV（多物种 reference + 轨道配置）
- ChIP-seq 功能：marks/experiments/regions 查询 + overlap 分析（list + compare）
- Admin 页面：Monitoring / Cache / Materialized Views（用于性能定位与运维）
- 导出：部分列表/统计提供 CSV/XLSX 或接口导出（具体入口以页面与 API 文档为准）

## 回归与性能门禁（面向开发者）

- 性能定位：`docs/PERFORMANCE_TRIAGE.md`（配套脚本：`scripts/admin_metrics_snapshot.py`）
- 前端 bundle 体积定位：`cd frontend/web && npm run build && npm run report:bundle -- --top 15`
- 前端 bundle 体积对比（含首屏回归门禁，默认阈值 +3%）：`cd frontend/web && npm run report:bundle -- --json bundle-baseline.json && npm run build && npm run report:bundle -- --json bundle-current.json && node scripts/compare-bundle-sizes.mjs bundle-baseline.json bundle-current.json --max-entry-regression-pct 3 --max-preloads-regression-pct 3`
- Overlap 性能回归：`docs/testing/performance/OVERLAP_PERF_REGRESSION.md`（workflow：`.github/workflows/performance-overlap.yml`）
- Genes / Regulations 性能回归：`docs/testing/performance/GENES_REGULATIONS_PERF_REGRESSION.md`（workflow：`.github/workflows/performance-genes-regulations.yml`）
- CI 止损（billing/额度阻塞时）：`docs/CI_SELF_HOSTED_RUNNER.md`

## CI / self-hosted runner 现状

如果 GitHub-hosted runner 被账单/额度阻塞，优先按 `docs/CI_SELF_HOSTED_RUNNER.md` 切换到 self-hosted runner 作为止损路径。

## 已知限制 / 常见坑

- 本机 `git push` 可能因 pre-push hook 触发 `bash scripts/run-tests.sh ci` 而变慢；如开发机缺少后端依赖（常见：`psycopg2`），`scripts/run-tests.sh` 会自动创建 `frontend/backend/.venv` 并安装依赖（可用 `SKIP_BACKEND_VENV_BOOTSTRAP=1` 禁用，或用 `BACKEND_PYTHON` 指向你的解释器）。
- 在代理环境下，`git`/Actions 下载可能出现 TLS 握手不稳定；建议优先“单次命令走代理”，详见 `docs/CI_SELF_HOSTED_RUNNER.md`。
- self-hosted runner 上 Playwright 可能需要预装系统依赖（`npx playwright install-deps chromium`），详见 `docs/CI_SELF_HOSTED_RUNNER.md`。

## 下一步（1–2 周）

- 补齐本地 CI 自举指引（围绕 Python 依赖与数据库相关可重复运行性）
- 持续清理历史文档中容易被误读为“当前 backlog”的表述（保持“历史可追溯”但“现状不误导”）
- 继续把性能门禁/回归锚点做成稳定工作流（小步提交、可审计可回滚）
