# Overlap 物化视图（`mv_lncrna_chipseq_overlaps`）创建与维护指南

本项目的 overlap 相关接口在 **MV 存在且可用**时，会自动走物化视图加速；当 **MV 不存在/不可用**时，后端会退化为实时 JOIN（在 `chr1/chr2/chr3` 等大染色体上容易触发超大查询）。

如果你在 overlap 相关接口中遇到 `400` 且 `error=QUERY_TOO_BROAD`：
- **短期**：按返回的 `suggest_filters` 增加至少一个过滤条件，缩小查询范围；
- **长期（推荐）**：创建/刷新 `mv_lncrna_chipseq_overlaps`，让大染色体查询也能稳定、快速。

---

## 1) 适用范围

该 MV 主要加速以下接口（以及前端 Overlap 页面）：
- `GET /api/v1/lncrna-chipseq-overlap`
- `GET /api/v1/lncrna-chipseq-overlap/statistics`
- `GET /api/v1/lncrna-chipseq-overlap/heatmap`
- `GET /api/v1/lncrna-chipseq-overlap/export`

---

## 2) 创建 MV（一次性）

### 前置条件

- PostgreSQL 14+（建议与后端一致）
- 已导入 ChIP-seq 相关表结构与扩展（`chipseq_schema.sql` 会启用 `btree_gist`，用于 overlap range 索引）

### 执行命令

```bash
# 1) 确保 ChIP-seq schema/扩展已安装（只需一次；如已安装可跳过）
psql -d lncrna_production -f frontend/backend/sql/chipseq_schema.sql

# 2) 创建 overlap MV + 索引（首次创建可能需要 30–60 分钟，取决于数据量）
psql -d lncrna_production -f schema/v2.3/05_mv_lncrna_chipseq_overlaps.sql
```

---

## 3) 刷新 MV（推荐定期/ETL 后）

### 方式 A：刷新脚本（推荐）

```bash
./scripts/refresh_materialized_views.sh
```

### 方式 B：直接 SQL（只刷新 overlap MV）

```bash
psql -d lncrna_production -c "REFRESH MATERIALIZED VIEW CONCURRENTLY mv_lncrna_chipseq_overlaps;"
```

> 说明：`CONCURRENTLY` 需要 MV 上存在唯一索引；`schema/v2.3/05_mv_lncrna_chipseq_overlaps.sql` 已包含 `idx_mv_overlap_unique`。

---

## 4) 验证 MV 可用性

### 方式 A：SQL 快速检查

```bash
psql -d lncrna_production -c "SELECT COUNT(*) FROM mv_lncrna_chipseq_overlaps;"
```

### 方式 B：后端 Admin API（需要 `X-Admin-API-Key`）

```bash
curl -H "X-Admin-API-Key: <ADMIN_API_KEY>" "http://localhost:8000/api/v1/admin/materialized-views/status"
curl -X POST -H "X-Admin-API-Key: <ADMIN_API_KEY>" -H "Content-Type: application/json" \
  "http://localhost:8000/api/v1/admin/materialized-views/refresh" \
  -d '{"concurrently": true, "timeout_seconds": 600}'
```

---

## 5) 常见问题排查

### 5.1 `REFRESH MATERIALIZED VIEW CONCURRENTLY` 报错缺少唯一索引

现象：
- 报错类似：`cannot refresh materialized view concurrently because it does not have a unique index`

处理：
- 确认已执行 `schema/v2.3/05_mv_lncrna_chipseq_overlaps.sql`
- 确认存在唯一索引：`idx_mv_overlap_unique`

### 5.2 仍然出现 `QUERY_TOO_BROAD`

含义：
- 后端检测到 MV 不可用，且当前查询（尤其是 `chr1/chr2/chr3`）过宽

处理：
- 检查 MV 是否存在、是否有数据、是否刷新成功
- 或先按返回的 `suggest_filters` 增加过滤条件进行收敛

---

## 6) 参考文件

- MV SQL：`schema/v2.3/05_mv_lncrna_chipseq_overlaps.sql`
- ChIP-seq schema/扩展：`frontend/backend/sql/chipseq_schema.sql`
- 刷新脚本：`scripts/refresh_materialized_views.sh`
- Overlap API 文档：`docs/api/LNCRNA_CHIPSEQ_OVERLAP_API.md`

