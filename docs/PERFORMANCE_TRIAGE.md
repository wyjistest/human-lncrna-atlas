# 性能定位快速指南（Admin Monitoring）

目标：用 **1 次导出 + 1 次截图** 在 issue 中复现并定位性能问题：

- 哪条端点慢（P95/P99 / DB P95）
- 慢在 DB 还是业务/缓存（对比 Response vs DB 百分位 + cache hit rate / routes+namespaces+keys compute）
- 具体慢查询是什么（fingerprint + route + SQL）

本项目已有的观测入口：

- `GET /api/v1/admin/metrics`：轻量 in-memory 指标（端点尾延迟、DB 百分位、慢查询榜单、cache 统计）
- `Admin/Monitoring` 页面：可视化查看 Top Endpoints（P95/P99/DB P95）、Cache、Database Performance

## 1) 一键导出（JSON + Markdown）

推荐使用脚本导出一份可直接贴到 issue 的 Markdown 摘要，同时保存完整 JSON 作为附件：

- Markdown 摘要包含：Top endpoints（Response P95/P99 + DB P95）、DB 慢查询榜单、Cache（hit rate / get() percentiles / namespaces / keys / routes）。

```bash
python3 scripts/admin_metrics_snapshot.py --base-url "http://localhost:8000"
```

也支持使用环境变量默认值（可省略参数）：

- `API_BASE_URL`：默认 backend base url
- `ADMIN_API_KEY`：默认 Admin API Key（会作为 `X-Admin-API-Key` 发送）

如果导出里出现 `n=<samples>/10`（样本不足，percentiles 为 null），可以先用 warmup 选项制造少量流量再导出：

```bash
python3 scripts/admin_metrics_snapshot.py \
  --base-url "http://localhost:8000" \
  --warmup-rounds 10
```

如遇到 403（生产/严格模式或非内网访问），带上 Admin API Key：

```bash
python3 scripts/admin_metrics_snapshot.py \
  --base-url "http://localhost:8000" \
  --admin-api-key "$ADMIN_API_KEY"
```

输出文件默认写入 `docs/reports/`：

- `docs/reports/admin-metrics-<timestamp>.json`
- `docs/reports/admin-metrics-<timestamp>.md`

## 2) 对比两次导出（可选，但强烈推荐）

当你在做优化/回归验证时，建议导出两份 JSON（优化前/优化后），然后生成一份差异报告（可直接贴到 issue/comment）：

```bash
python3 scripts/admin_metrics_snapshot.py --compare \
  "docs/reports/admin-metrics-OLD.json" \
  "docs/reports/admin-metrics-NEW.json"
```

输出：

- `docs/reports/admin-metrics-diff-<timestamp>.md`

提示：

- 两次快照尽量保持同一环境/同一流量模型；必要时都加 `--warmup-rounds` 预热
- 若字段缺失/样本不足，diff 会显示为 `-` 或落入 “Other changes”

## 3) 截图（用于快速沟通）

打开 `Admin/Monitoring` 页面，至少截 1 张包含以下内容的截图：

- Top Endpoints（Response P95/P99 + DB P95）
- Database Performance（Query / Per-request DB percentiles + Slow queries）
- Cache（hit rate、get() 延迟、namespaces/keys）

## 4) Issue 里怎么写（建议结构）

建议把导出的 Markdown 直接贴到 issue，并附上 JSON 文件与截图：

1. **Symptom**：具体哪个页面/哪个操作慢，预期耗时 vs 实际耗时
2. **Evidence**
   - `admin-metrics-*.md`（粘贴）
   - `admin-metrics-*.json`（附件）
   - Monitoring 页面截图（附件）
3. **Quick triage**
   - Response P95 高但 DB P95 低：优先看 cache routes/namespaces/keys 的 `compute_*`（回源次数 + avg/max，常见于回源计算/IO）
   - 命中率异常：优先看 cache routes 的 `hit_rate_pct` / `misses`（快速定位“哪个端点在频繁 miss”）
   - DB P95 高：优先看 slow queries（fingerprint+route）定位具体 SQL 与触发端点
   - 若慢点集中在 `GET /api/v1/lncrna-chipseq-overlap/compare`：可先用 `species_ids=1,3`（或前端弹窗勾选物种子集）缩小计算量，验证是否为“多物种计算”导致尾延迟

## 参考

- `frontend/backend/app/routers/admin.py:864`（`GET /api/v1/admin/metrics`）
- `frontend/backend/app/middleware/admin_metrics.py:140`（in-memory 指标采集）
- `frontend/backend/app/core/cache.py:897`（cache hit/miss、routes/namespaces/keys、compute_* 统计）
