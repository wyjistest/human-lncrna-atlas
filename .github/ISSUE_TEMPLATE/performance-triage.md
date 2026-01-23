---
name: 性能定位（Admin Metrics）
about: 使用 /api/v1/admin/metrics 快照报告性能问题（1 次导出 + 1 次截图）
title: "[perf] <简述问题>"
labels: ["perf"]
---

## Symptom（现象）

- 哪个页面/操作慢：
- 预期耗时 vs 实际耗时：
- 发生频率（必现/偶现）：

## Repro（复现步骤）

1.
2.
3.

## Evidence（证据）

### 1) Admin metrics 导出（必填）

运行：

`python3 scripts/admin_metrics_snapshot.py --base-url "http://localhost:8000" --admin-api-key "$ADMIN_API_KEY"`

说明：脚本也支持读取环境变量默认值（`API_BASE_URL` / `ADMIN_API_KEY`），已设置时可省略参数。
若样本不足导致百分位为 null，可先使用 `--warmup-rounds 10` 预热后再导出。

粘贴 `admin-metrics-*.md` 内容：

```markdown
<paste here>
```

并上传附件：

- `admin-metrics-*.json`

### 2) Monitoring 页面截图（必填）

上传至少 1 张截图，包含：

- Top Endpoints（Response P95/P99 + DB P95）
- Database Performance（Slow queries）
- Cache（hit rate、namespaces/keys）

## Quick triage（快速判断）

- Response P95 高但 DB P95 低：优先看 cache namespaces 的 `compute_*` / 热点 keys（可能是回源/计算/IO）
- DB P95 高：优先看 slow queries（fingerprint+route）定位具体 SQL 与触发端点
- 若慢点集中在 `GET /api/v1/lncrna-chipseq-overlap/compare`：可先用 `species_ids=1,3`（或前端弹窗勾选物种子集）缩小计算量，验证是否为“多物种计算”导致尾延迟
