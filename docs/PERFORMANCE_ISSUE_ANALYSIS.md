# PostgreSQL 进程过多问题分析和解决方案

> **问题发现日期**: 2025-12-07
> **问题状态**: ✅ 已解决
> **根本原因**: COUNT(*) 查询全表扫描导致慢查询堆积

---

## 📊 问题概述

### 症状

在 Phase 1 开发和测试期间，发现系统出现：
- PostgreSQL 进程数达到 **29 个**（正常为 6-8 个）
- CPU 使用率持续 **97-99%**
- 多个查询运行超过 **16-75 分钟**仍未完成

### 影响

- 系统资源占用过高
- 新查询响应变慢
- 可能影响其他服务

---

## 🔍 根本原因分析

### 1. 慢查询来源

**测试脚本查询**（2 个，运行 72-75 分钟）:
```sql
-- lncrna_peak_overlap_test.sql 中的 EXPLAIN 查询
EXPLAIN (ANALYZE, BUFFERS)
SELECT ...
FROM regulations r
JOIN chipseq_peaks_human p ON ...
WHERE r.best_peak_chr = 'chr1'
LIMIT 100;
```

**API 统计查询**（17 个，运行 16-17 分钟）:
```sql
-- API 端点中的 COUNT(*) 查询
SELECT COUNT(*) AS total
FROM regulations r
JOIN chipseq_peaks_human p ON
    r.species_id = p.species_id
    AND r.best_peak_chr = p.chromosome
    AND r.best_peak_start < p.peak_end
    AND r.best_peak_end > p.peak_start
JOIN chipseq_experiments e ON p.experiment_id = e.experiment_id
JOIN epigenetic_mark_types m ON e.mark_type_id = m.mark_type_id
WHERE r.species_id = 1
  AND e.is_active = TRUE;
  -- 没有其他筛选条件！
```

### 2. 为什么这些查询这么慢？

#### 数据规模

- **regulations 表**: 496,064 条（human species）
- **chipseq_peaks 表**: 2,253,718 条
- **潜在比较次数**: 496K × 2.25M = **1.12 万亿次**

#### 查询特点

**数据查询** (LIMIT 100):
- ✅ 快速（2.9 ms）
- 原因：只需找到前 100 个匹配即可停止

**COUNT 查询** (COUNT(*)):
- ⚠️ 慢（16+ 分钟）
- 原因：必须扫描所有匹配行才能计数

#### EXPLAIN 分析

```sql
EXPLAIN ANALYZE 结果:

Nested Loop (cost=0.42..80729441.52 rows=1072587019 width=78)
  -- 估计需要处理 10 亿行！
  -- 实际只执行了 2.9ms（因为 LIMIT 100）

但对于 COUNT(*) 查询:
  -- 必须完整执行 Nested Loop
  -- 需要处理所有匹配行（估计 100 万+）
  -- 执行时间：16+ 分钟
```

### 3. PostgreSQL 并行执行机制

当 PostgreSQL 检测到大查询时，会自动启动 **并行工作进程**（parallel workers）:

```
主查询进程 (PID 3708708)
├─ Parallel Worker 1 (PID 3708711)
└─ Parallel Worker 2 (PID 3708712)
```

**19 个慢查询** × **2-3 个 workers** = **40-50 个进程**

---

## ✅ 解决方案

### 临时方案（已执行）

**终止长时间运行的查询**:
```sql
SELECT pg_terminate_backend(pid)
FROM pg_stat_activity
WHERE datname = 'lncrna_production'
  AND state = 'active'
  AND query_start < NOW() - INTERVAL '10 minutes';
```

**结果**:
- ✅ 终止 19 个慢查询
- ✅ 进程数从 29 → 8
- ✅ CPU 从 97% → 4%

### 永久方案（推荐实施）

#### 方案 1：物化视图（最佳，预计提速 1000x）

```sql
-- 1. 创建物化视图（预计算所有重叠）
CREATE MATERIALIZED VIEW mv_lncrna_chipseq_overlaps AS
SELECT
    CONCAT('reg_', r.regulation_id, '_peak_', p.peak_id) AS overlap_id,
    r.regulation_id,
    r.lncrna_gene_id,
    lnc.gene_name AS lncrna_name,
    r.target_gene_id,
    tgt.gene_name AS target_gene_name,
    m.mark_name AS mark_type,
    m.mark_category,
    e.cell_type,
    r.best_peak_chr AS chromosome,
    r.best_peak_start AS lncrna_binding_start,
    r.best_peak_end AS lncrna_binding_end,
    p.peak_start,
    p.peak_end,
    GREATEST(r.best_peak_start, p.peak_start) AS overlap_start,
    LEAST(r.best_peak_end, p.peak_end) AS overlap_end,
    LEAST(r.best_peak_end, p.peak_end) - GREATEST(r.best_peak_start, p.peak_start) AS overlap_length,
    r.binding_affinity,
    p.fold_enrichment AS peak_fold_enrichment,
    p.qvalue AS peak_qvalue
FROM regulations r
JOIN genes lnc ON r.lncrna_gene_id = lnc.gene_id
JOIN genes tgt ON r.target_gene_id = tgt.gene_id
JOIN chipseq_peaks_human p ON
    r.species_id = p.species_id
    AND r.best_peak_chr = p.chromosome
    AND r.best_peak_start < p.peak_end
    AND r.best_peak_end > p.peak_start
JOIN chipseq_experiments e ON p.experiment_id = e.experiment_id
JOIN epigenetic_mark_types m ON e.mark_type_id = m.mark_type_id
WHERE r.species_id = 1 AND e.is_active = TRUE;

-- 2. 为物化视图创建索引
CREATE INDEX idx_mv_overlaps_lncrna ON mv_lncrna_chipseq_overlaps (lncrna_gene_id);
CREATE INDEX idx_mv_overlaps_target ON mv_lncrna_chipseq_overlaps (target_gene_id);
CREATE INDEX idx_mv_overlaps_chr ON mv_lncrna_chipseq_overlaps (chromosome);
CREATE INDEX idx_mv_overlaps_mark ON mv_lncrna_chipseq_overlaps (mark_type);
CREATE INDEX idx_mv_overlaps_cell ON mv_lncrna_chipseq_overlaps (cell_type);
CREATE INDEX idx_mv_overlaps_ba ON mv_lncrna_chipseq_overlaps (binding_affinity);
CREATE INDEX idx_mv_overlaps_overlap_len ON mv_lncrna_chipseq_overlaps (overlap_length);

-- 3. 修改 API 查询，从物化视图读取
SELECT * FROM mv_lncrna_chipseq_overlaps
WHERE chromosome = 'chr1'
LIMIT 100;  -- 查询时间：< 1 ms

SELECT COUNT(*) FROM mv_lncrna_chipseq_overlaps
WHERE chromosome = 'chr1';  -- 查询时间：< 1 ms
```

**优点**:
- ✅ COUNT 查询从 16 分钟 → **< 1 毫秒**
- ✅ 数据查询从 46 秒 → **< 1 秒**
- ✅ 支持所有筛选条件

**缺点**:
- ⚠️ 占用存储空间（预计 1-5 GB）
- ⚠️ 需要定期刷新（每天 1 次）
- ⚠️ 初次创建时间较长（预计 30-60 分钟）

**刷新策略**:
```bash
# 添加到 cron（每天凌晨 3 点刷新）
0 3 * * * psql -U amax -d lncrna_production -c "REFRESH MATERIALIZED VIEW CONCURRENTLY mv_lncrna_chipseq_overlaps;"
```

#### 方案 2：优化 COUNT 查询（次佳，提速 10-30x）

```sql
-- 1. 添加 BRIN 索引（Block Range Index）
CREATE INDEX idx_regulations_brin ON regulations
USING BRIN (species_id, best_peak_chr, best_peak_start, best_peak_end);

CREATE INDEX idx_chipseq_peaks_brin ON chipseq_peaks_human
USING BRIN (chromosome, peak_start, peak_end);

-- 2. 使用估算而非精确计数
SELECT reltuples::bigint AS estimated_count
FROM pg_class
WHERE relname = 'mv_lncrna_chipseq_overlaps';

-- 3. 修改 API，使用估算 + 缓存
-- 精确计数太慢时，返回估算值并标记
{
  "total": 219213,
  "is_estimate": true,
  "last_updated": "2025-12-07T03:00:00Z"
}
```

**优点**:
- ✅ 无需额外存储
- ✅ 查询时间从 16 分钟 → 10-30 秒

**缺点**:
- ⚠️ 仍然较慢（相比物化视图）
- ⚠️ COUNT 不精确（估算值）

#### 方案 3：强制要求筛选条件（快速方案，提速 100x）

```python
# 修改 API，强制要求至少提供一个筛选条件
@router.get("")
def get_lncrna_chipseq_overlaps(...):
    # 验证至少有一个筛选条件
    if not any([lncrna_gene_id, target_gene_id, chromosome, mark_type, cell_type]):
        raise HTTPException(
            status_code=400,
            detail="至少提供一个筛选条件：lncrna_gene_id, target_gene_id, chromosome, mark_type, 或 cell_type"
        )

    # 继续查询...
```

**优点**:
- ✅ 无需数据库改动
- ✅ 立即生效
- ✅ 避免全库扫描

**缺点**:
- ⚠️ 限制用户操作（不能"查看所有"）

---

## 🎯 推荐方案（组合使用）

### 短期（今天实施）

✅ **方案 3: 强制筛选条件**
- 立即修改 API，要求至少提供 chromosome
- 工作量：5 分钟
- 效果：避免未来的慢查询

### 中期（明天实施）

✅ **方案 1: 创建物化视图**
- 预计算所有重叠关系
- 工作量：0.5 天（包括测试）
- 效果：查询时间 < 1s

### 配置优化

```sql
-- 调整 PostgreSQL 配置，限制并行查询资源
ALTER DATABASE lncrna_production SET max_parallel_workers_per_gather = 2;
ALTER DATABASE lncrna_production SET parallel_setup_cost = 10000;  -- 提高并行阈值
```

---

## 📝 预防措施

### 1. 查询超时保护

```python
# 在 API 中添加超时
from sqlalchemy import create_engine

engine = create_engine(
    DATABASE_URL,
    connect_args={
        "options": "-c statement_timeout=30000"  # 30 秒超时
    }
)
```

### 2. 监控慢查询

```sql
-- 启用慢查询日志
ALTER SYSTEM SET log_min_duration_statement = 1000;  -- 记录 > 1s 的查询
ALTER SYSTEM SET log_line_prefix = '%t [%p]: [%l-1] user=%u,db=%d,app=%a,client=%h ';

-- 重载配置
SELECT pg_reload_conf();
```

### 3. 定期检查活跃查询

```bash
# 添加到监控脚本
psql -U amax -d lncrna_production -c "
SELECT
    pid,
    EXTRACT(EPOCH FROM (NOW() - query_start)) / 60 AS minutes_running,
    state,
    LEFT(query, 100) AS query
FROM pg_stat_activity
WHERE state = 'active'
  AND query_start < NOW() - INTERVAL '5 minutes'
ORDER BY query_start;
"
```

### 4. API 限流

```python
# 使用 slowapi 或 fastapi-limiter
from slowapi import Limiter
from slowapi.util import get_remote_address

limiter = Limiter(key_func=get_remote_address)

@router.get("", dependencies=[Depends(RateLimiter(times=10, seconds=60))])
def get_lncrna_chipseq_overlaps(...):
    # 限制每分钟最多 10 次请求
    ...
```

---

## 🛠️ 实施计划

### Phase 1: 立即实施（今天，5 分钟）

- [ ] 修改 API，强制要求至少一个筛选条件
- [ ] 添加查询超时保护（30 秒）
- [ ] 重启后端服务

### Phase 2: 性能优化（明天，0.5 天）

- [ ] 创建物化视图 `mv_lncrna_chipseq_overlaps`
- [ ] 为物化视图创建 7 个索引
- [ ] 修改 API 查询，从物化视图读取
- [ ] 测试性能提升
- [ ] 配置自动刷新（cron）

### Phase 3: 监控和告警（本周，0.5 天）

- [ ] 启用慢查询日志
- [ ] 配置监控脚本（每 5 分钟检查）
- [ ] 添加 Grafana 监控面板（可选）

---

## 📊 预期效果

### 优化前 vs 优化后

| 指标 | 优化前 | 优化后（预期）| 提升 |
|------|--------|-------------|------|
| **数据查询（100 条）** | 46.4s | < 1s | **46x** |
| **COUNT 查询** | 16+ 分钟 | < 1ms | **960,000x** |
| **并发查询能力** | 1-2 个 | 50+ 个 | **25x** |
| **CPU 使用率** | 97% | < 10% | **90% 降低** |
| **PostgreSQL 进程数** | 29 个 | 8 个 | **-72%** |

---

## 🔍 问题复现（用于测试）

如果需要复现问题（不推荐）:

```bash
# 1. 启动慢查询（会导致进程堆积）
curl "http://localhost:8000/api/v1/lncrna-chipseq-overlap?page=1&page_size=100" &

# 2. 重复启动多个（会产生多个慢查询）
for i in {1..5}; do
  curl "http://localhost:8000/api/v1/lncrna-chipseq-overlap?page=$i&page_size=100" &
done

# 3. 等待 5 分钟后检查进程数
sleep 300
ps aux | grep postgres | wc -l
```

**预期**: 进程数会快速增加到 20-30 个

---

## 📋 检查清单

### 日常检查（每天）

- [ ] 检查 PostgreSQL 进程数（应 < 10 个）
  ```bash
  ps aux | grep postgres | wc -l
  ```

- [ ] 检查活跃查询（应无超过 5 分钟的查询）
  ```sql
  SELECT pid, EXTRACT(EPOCH FROM (NOW() - query_start)) / 60 AS minutes
  FROM pg_stat_activity
  WHERE state = 'active' AND query_start < NOW() - INTERVAL '5 minutes';
  ```

- [ ] 检查慢查询日志
  ```bash
  tail -f /var/log/postgresql/postgresql-17-main.log | grep "duration:"
  ```

### 性能检查（每周）

- [ ] 检查物化视图刷新状态
  ```sql
  SELECT schemaname, matviewname, last_refresh
  FROM pg_matviews
  WHERE matviewname = 'mv_lncrna_chipseq_overlaps';
  ```

- [ ] 检查表和索引大小
  ```sql
  SELECT
    pg_size_pretty(pg_total_relation_size('mv_lncrna_chipseq_overlaps')) AS total_size,
    pg_size_pretty(pg_relation_size('mv_lncrna_chipseq_overlaps')) AS table_size,
    pg_size_pretty(pg_indexes_size('mv_lncrna_chipseq_overlaps')) AS indexes_size;
  ```

---

## 🎓 经验教训

### 1. 大数据 JOIN 的挑战

**教训**:
- 80 万 × 225 万的 JOIN 需要谨慎设计
- COUNT(*) 比 LIMIT 查询慢 1000 倍+

**最佳实践**:
- 总是使用物化视图预计算大 JOIN
- 避免实时 COUNT(*)，使用缓存或估算
- 强制要求筛选条件，减少扫描范围

### 2. PostgreSQL 并行执行

**教训**:
- 并行执行会倍增进程数
- 多个慢查询会耗尽系统资源

**最佳实践**:
- 限制 `max_parallel_workers_per_gather`
- 监控长时间运行的查询
- 设置查询超时（statement_timeout）

### 3. API 设计原则

**教训**:
- 不加筛选条件的"查看所有"功能危险
- COUNT(*) 应该缓存或估算

**最佳实践**:
- 强制至少一个筛选条件
- 使用游标（cursor）分批查询
- 对 COUNT 结果缓存 5-10 分钟

---

## 📞 参考资源

- **物化视图文档**: https://www.postgresql.org/docs/current/sql-creatematerializedview.html
- **查询性能优化**: https://www.postgresql.org/docs/current/performance-tips.html
- **慢查询分析**: https://www.postgresql.org/docs/current/runtime-config-logging.html

---

**文档版本**: v1.0
**创建日期**: 2025-12-07
**状态**: 问题已解决，优化方案已提供

**下一步**: 实施物化视图优化（预计明天完成）
