# lncRNA-ChIP-seq Overlap API Documentation

> 更新（2026-01-24）：本文档为 API 文档快照；如与当前实现不一致，以 `docs/CURRENT_STATUS.md` 与实际接口行为为准。

## Overview

This API provides endpoints for querying overlaps between lncRNA binding sites and ChIP-seq peaks, enabling analysis of lncRNA-mediated epigenetic regulation mechanisms.

## Endpoints

### 1. Query Overlaps (GET `/api/v1/lncrna-chipseq-overlap`)

Get paginated list of lncRNA-ChIP-seq overlaps with flexible filtering.

#### Performance Notes

- When the materialized view `mv_lncrna_chipseq_overlaps` is available and populated, the API uses it automatically (`using_materialized_view=true`).
- When MV is **not** available (fallback join query):
  - If no selective filters are provided (`lncrna_gene_id`, `target_gene_id`, `chromosome`, `mark_type`, `cell_type`, or `min_binding_affinity > 0`), the server applies a default `chromosome=chr22` (`default_filter_applied=true`) to prevent timeouts.
  - For large chromosomes (`chr1`, `chr2`, `chr3`), a **chromosome-only** request is rejected with `400` (`error=QUERY_TOO_BROAD`) unless you add at least one additional narrowing filter (e.g. `mark_type`, `cell_type`, `lncrna_gene_id`, `target_gene_id`, `min_binding_affinity`, `min_peak_strength`, `min_overlap_length`).

#### Query Parameters

| Parameter | Type | Required | Default | Description |
|-----------|------|----------|---------|-------------|
| `lncrna_gene_id` | integer | No | - | Filter by specific lncRNA gene ID |
| `target_gene_id` | integer | No | - | Filter by specific target gene ID |
| `mark_type` | string | No | - | Filter by mark type(s), comma-separated (e.g., "H3K27me3,H3K4me3") |
| `cell_type` | string | No | - | Filter by cell type(s), comma-separated (e.g., "K562,GM12878") |
| `chromosome` | string | No | - | Filter by chromosome (e.g., "chr1") |
| `min_overlap_length` | integer | No | - | Minimum overlap length in bp (>= 1) |
| `min_binding_affinity` | float | No | - | Minimum binding affinity score (>= 0) |
| `min_peak_strength` | float | No | - | Minimum peak fold enrichment (>= 0) |
| `max_qvalue` | float | No | 0.05 | Maximum Q-value (FDR) for peaks (0-1) |
| `page` | integer | No | 1 | Page number (>= 1) |
| `page_size` | integer | No | 100 | Items per page (1-1000) |
| `sort_by` | string | No | "binding_affinity" | Sort field: "binding_affinity", "overlap_length", "peak_fold_enrichment", "peak_qvalue" |
| `sort_order` | string | No | "desc" | Sort order: "asc" or "desc" |

### 1.1 Cursor Pagination (GET `/api/v1/lncrna-chipseq-overlap/cursor`)

当客户端需要“顺序翻页/无限滚动”时，推荐使用 cursor（keyset）分页，避免 deep `OFFSET` 扫描造成的性能劣化。

#### 重要说明

- 该端点仍会返回 `total`（沿用现有 COUNT(*) 缓存策略），但不再返回 `page/total_pages`。
- 排序稳定键为 `(sort_field, overlap_id)`。
- `sort_by=peak_qvalue` 已支持：排序语义为“非 NULL 的 qvalue 先按 `asc/desc` 排序，然后 NULL 的记录最后；同 qvalue 或 NULL 段内使用 overlap_id 作为稳定 tie-breaker”。cursor 为 opaque token，客户端无需解析，原样回传即可。

#### Query Parameters（新增）

| Parameter | Type | Required | Default | Description |
|-----------|------|----------|---------|-------------|
| `cursor` | string | No | - | Opaque cursor token from previous response |
| `page_size` | integer | No | 100 | Items per page (1-1000) |

其余过滤参数与 `/api/v1/lncrna-chipseq-overlap` 相同（`lncrna_gene_id/target_gene_id/mark_type/cell_type/chromosome/...`）。

#### Response Schema

```json
{
  "total": 219213,
  "page_size": 100,
  "items": [],
  "next_cursor": "<opaque>",
  "has_more": true,
  "default_filter_applied": false,
  "effective_chromosome": "chr22",
  "using_materialized_view": true
}
```

#### Example Requests

```bash
# First page
curl "http://localhost:8000/api/v1/lncrna-chipseq-overlap/cursor?chromosome=chr22&page_size=100&sort_by=binding_affinity&sort_order=desc"

# Next page (use next_cursor from previous response)
curl "http://localhost:8000/api/v1/lncrna-chipseq-overlap/cursor?chromosome=chr22&page_size=100&sort_by=binding_affinity&sort_order=desc&cursor=<opaque>"

# Sort by peak_qvalue (NULL-safe ordering)
curl "http://localhost:8000/api/v1/lncrna-chipseq-overlap/cursor?chromosome=chr22&page_size=100&sort_by=peak_qvalue&sort_order=asc"
```

#### Response Schema

```json
{
  "total": 219213,
  "page": 1,
  "page_size": 5,
  "total_pages": 43843,
  "items": [
    {
      "overlap_id": "reg_804963_peak_1195794",
      "regulation_id": 804963,
      "lncrna_gene_id": 19101,
      "lncrna_name": "RP11-243A14.1",
      "target_gene_id": 27047,
      "target_gene_name": "KIF21B",
      "mark_type": "H3K36me3",
      "mark_category": "activating",
      "cell_type": "GM12878",
      "chromosome": "chr1",
      "lncrna_binding_start": 200975886,
      "lncrna_binding_end": 200977026,
      "peak_start": 200931640,
      "peak_end": 200994697,
      "overlap_start": 200975886,
      "overlap_end": 200977026,
      "overlap_length": 1140,
      "binding_affinity": "495.0100",
      "peak_fold_enrichment": "2.9803",
      "peak_qvalue": null
    }
  ],
  "default_filter_applied": false,
  "effective_chromosome": "chr1",
  "using_materialized_view": true
}
```

#### Example Requests

**Basic query:**
```bash
curl "http://localhost:8000/api/v1/lncrna-chipseq-overlap?chromosome=chr22&page=1&page_size=10"
```

**Filter by mark type and binding affinity:**
```bash
curl "http://localhost:8000/api/v1/lncrna-chipseq-overlap?mark_type=H3K27me3&min_binding_affinity=60&page=1&page_size=10"
```

**Multiple filters:**
```bash
curl "http://localhost:8000/api/v1/lncrna-chipseq-overlap?mark_type=H3K27me3,H3K4me3&cell_type=K562&min_overlap_length=50&page=1&page_size=10"
```

**Sort by overlap length:**
```bash
curl "http://localhost:8000/api/v1/lncrna-chipseq-overlap?chromosome=chr1&mark_type=H3K27me3&sort_by=overlap_length&sort_order=desc&page=1&page_size=10"
```

### 2. Get Statistics (GET `/api/v1/lncrna-chipseq-overlap/statistics`)

Get summary statistics for lncRNA-ChIP-seq overlaps.

#### Performance Notes

- When the materialized view `mv_lncrna_chipseq_overlaps` is available and populated, the API uses it automatically (`using_materialized_view=true`).
- When MV is **not** available (fallback join query):
  - If no selective filters are provided (`lncrna_gene_id`, `target_gene_id`, `chromosome`, `mark_type`, `cell_type`, or `min_binding_affinity > 0`), the server applies a default `chromosome=chr22` (`default_filter_applied=true`) to prevent timeouts.
  - For large chromosomes (`chr1`, `chr2`, `chr3`), a **chromosome-only** request is rejected with `400` (`error=QUERY_TOO_BROAD`) unless you add at least one additional narrowing filter (e.g. `mark_type`, `cell_type`, `lncrna_gene_id`, `target_gene_id`, `min_binding_affinity`).

#### Query Parameters

| Parameter | Type | Required | Default | Description |
|-----------|------|----------|---------|-------------|
| `lncrna_gene_id` | integer | No | - | Filter by specific lncRNA gene ID |
| `target_gene_id` | integer | No | - | Filter by specific target gene ID |
| `mark_type` | string | No | - | Filter by mark type(s), comma-separated |
| `cell_type` | string | No | - | Filter by cell type(s), comma-separated |
| `chromosome` | string | No | - | Filter by chromosome |
| `min_binding_affinity` | float | No | - | Minimum binding affinity score |
| `max_qvalue` | float | No | 0.05 | Maximum Q-value (FDR) |

#### Response Schema

```json
{
  "total_overlaps": 219213,
  "unique_lncrnas": 1706,
  "unique_target_genes": 519,
  "unique_marks": 7,
  "unique_cell_types": 0,
  "avg_overlap_length": 96.34,
  "avg_binding_affinity": 69.62,
  "avg_peak_strength": 17.15,
  "by_mark_type": [],
  "by_cell_type": [],
  "default_filter_applied": true,
  "effective_chromosome": "chr22"
}
```

#### Example Requests

**Overall statistics:**
```bash
curl "http://localhost:8000/api/v1/lncrna-chipseq-overlap/statistics"
```

**Statistics for chr1 (requires additional filter when MV is unavailable):**
```bash
curl "http://localhost:8000/api/v1/lncrna-chipseq-overlap/statistics?chromosome=chr1&mark_type=H3K27me3"
```

**Statistics for specific mark type:**
```bash
curl "http://localhost:8000/api/v1/lncrna-chipseq-overlap/statistics?mark_type=H3K27me3"
```

### 2.1 Cross-species Compare (GET `/api/v1/lncrna-chipseq-overlap/compare`)

基于 `core_id` 的同源映射，将输入的 `lncrna_gene_id`（可选 `target_gene_id`）映射到多个物种，并返回每个物种各自的 overlap 汇总统计（与 `/statistics` 的统计结构一致）。

对比物种集合（`species_id`）：

- `1`: Human
- `2`: Chimpanzee
- `3`: Rhesus Macaque
- `4`: Marmoset

#### Notes

- 若某物种缺少同源基因（或指定了 `target_gene_id` 但缺少 target 同源基因），该物种返回 empty stats（`total_overlaps=0`）。
- `top_n` 用于限制每个物种的 breakdown（`by_mark_type/by_cell_type`）返回条数，避免 payload 过大。
- 可选参数 `species_ids` 可限制参与对比的物种集合（用于减少查询量/提升响应速度）；未指定时默认对比 `1,2,3,4`。

#### Query Parameters

| Parameter | Type | Required | Default | Description |
|-----------|------|----------|---------|-------------|
| `lncrna_gene_id` | integer | Yes | - | lncRNA基因ID（任意物种；用于 `core_id` 同源映射） |
| `target_gene_id` | integer | No | - | 目标基因ID（可选；任意物种；用于 `core_id` 同源映射） |
| `mark_type` | string | No | - | Mark type(s), comma-separated |
| `cell_type` | string | No | - | Cell type(s), comma-separated |
| `chromosome` | string | No | - | Chromosome filter (optional) |
| `min_binding_affinity` | float | No | - | Minimum binding affinity |
| `max_qvalue` | float | No | 0.05 | Maximum Q-value (FDR) for peaks (0-1) |
| `top_n` | integer | No | 10 | Top-N breakdown items per species (1-50) |
| `species_ids` | string | No | `1,2,3,4` | Species IDs to compare, comma-separated (subset of 1-4) |

#### Response Schema

> `species_stats` 为“按物种 ID 分组的 map”，在 JSON 中 key 会被序列化为字符串（例如 `"1"`, `"2"`）。当使用 `species_ids` 时，该 map 仅包含被选择的物种。

```json
{
  "lncrna_core_id": 12345,
  "target_core_id": 67890,
  "species_names": {
    "1": "Human",
    "2": "Chimpanzee",
    "3": "Rhesus Macaque",
    "4": "Marmoset"
  },
  "species_stats": {
    "1": {
      "species_id": 1,
      "species_name": "Human",
      "lncrna_gene_id": 19101,
      "target_gene_id": 27047,
      "statistics": {
        "total_overlaps": 0,
        "unique_lncrnas": 0,
        "unique_target_genes": 0,
        "unique_marks": 0,
        "unique_cell_types": 0,
        "avg_overlap_length": 0.0,
        "avg_binding_affinity": 0.0,
        "avg_peak_strength": 0.0,
        "by_mark_type": [],
        "by_cell_type": [],
        "default_filter_applied": false,
        "effective_chromosome": "chr22"
      }
    }
  }
}
```

#### Example Requests

```bash
curl "http://localhost:8000/api/v1/lncrna-chipseq-overlap/compare?lncrna_gene_id=19101&target_gene_id=27047&chromosome=chr22&top_n=10"
curl "http://localhost:8000/api/v1/lncrna-chipseq-overlap/compare?lncrna_gene_id=19101&species_ids=1,3&top_n=10"
```

### 3. Get Heatmap (GET `/api/v1/lncrna-chipseq-overlap/heatmap`)

Get heatmap matrix data for lncRNA-ChIP-seq overlap visualization (ECharts/D3 friendly).

#### Query Parameters

| Parameter | Type | Required | Default | Description |
|-----------|------|----------|---------|-------------|
| `x_axis` | string | Yes | - | X-axis dimension: `mark_type` or `cell_type` |
| `y_axis` | string | Yes | - | Y-axis dimension: `lncrna` or `target_gene` |
| `metric` | string | No | `count` | Cell metric: `count`, `avg_binding_affinity`, `total_overlap_length` |
| `top_n` | integer | No | 50 | Limit Y-axis items (1-100) |
| `chromosome` | string | No | - | Filter by chromosome |
| `min_binding_affinity` | float | No | - | Minimum binding affinity score (>= 0) |
| `max_qvalue` | float | No | 0.05 | Maximum Q-value (FDR) for peaks (0-1) |

#### Response Schema

```json
{
  "x_labels": ["H3K27me3", "H3K4me3"],
  "y_labels": ["RP11-243A14.1", "MALAT1"],
  "data": [
    { "x": "H3K27me3", "y": "RP11-243A14.1", "value": 12 }
  ],
  "metric": "count",
  "total_combinations": 100,
  "valid_combinations": 42,
  "default_filter_applied": true,
  "effective_chromosome": "chr22"
}
```

#### Example Requests

```bash
curl "http://localhost:8000/api/v1/lncrna-chipseq-overlap/heatmap?x_axis=mark_type&y_axis=lncrna&metric=count&top_n=30"
```

#### Performance Notes

- Cached for 10 minutes and rate-limited (30/minute).
- Without MV, if neither `chromosome` nor `min_binding_affinity` is provided, the server defaults to `chromosome=chr22`.
- Without MV, for `chromosome=chr1/chr2/chr3` you must set `min_binding_affinity > 0`, otherwise the API returns `400` (`error=QUERY_TOO_BROAD`).

### 4. Export Overlaps (GET `/api/v1/lncrna-chipseq-overlap/export`)

Export overlaps in `bed` (BED6) or `csv` format. Large exports are streamed to reduce memory usage.

#### Query Parameters

All filters from the main query endpoint are supported, plus:

| Parameter | Type | Required | Default | Description |
|-----------|------|----------|---------|-------------|
| `format` | string | No | `bed` | Export format: `bed` or `csv` |
| `max_rows` | integer | No | 100000 | Maximum rows to export (1-100000) |

#### Example Requests

```bash
# Export chr22 overlaps as BED6
curl "http://localhost:8000/api/v1/lncrna-chipseq-overlap/export?format=bed&chromosome=chr22" -o overlaps_chr22.bed

# Export H3K27me3 overlaps as CSV
curl "http://localhost:8000/api/v1/lncrna-chipseq-overlap/export?format=csv&mark_type=H3K27me3&chromosome=chr22" -o overlaps_H3K27me3.csv
```

#### Performance Notes

- Rate-limited (5/minute). Without MV, if no selective filters are provided, the server defaults to `chromosome=chr22`.
- Without MV, for `chromosome=chr1/chr2/chr3` you must add at least one additional narrowing filter (e.g. `mark_type`, `cell_type`, `lncrna_gene_id`, `target_gene_id`, `min_binding_affinity`, `min_peak_strength`, `min_overlap_length`), otherwise the API returns `400` (`error=QUERY_TOO_BROAD`).

## Database Schema

### Key Tables

The API queries the following tables:

- **regulations**: lncRNA binding sites (best_peak_chr, best_peak_start, best_peak_end, binding_affinity)
- **chipseq_peaks_human**: ChIP-seq peaks (chromosome, peak_start, peak_end, fold_enrichment, qvalue)
- **chipseq_experiments**: Experiment metadata (cell_type, is_active)
- **epigenetic_mark_types**: Mark type information (mark_name, mark_category)
- **genes**: Gene information (gene_id, gene_name)

### Overlap Logic

Overlaps are calculated using genomic coordinate intersection:

```sql
r.best_peak_chr = p.chromosome
AND r.best_peak_start < p.peak_end
AND r.best_peak_end > p.peak_start
```

Overlap coordinates:
- `overlap_start = GREATEST(r.best_peak_start, p.peak_start)`
- `overlap_end = LEAST(r.best_peak_end, p.peak_end)`
- `overlap_length = overlap_end - overlap_start`

## Performance Notes

### Current Performance

- **With MV (`mv_lncrna_chipseq_overlaps`)**: optimized for interactive queries, including large chromosomes.
- **Without MV (fallback join query)**: can be slow for broad requests; the API applies safety defaults (chr22) and rejects chromosome-only queries for chr1/chr2/chr3 unless additional filters are provided.

### Optimization Opportunities

1. **Add indexes** on commonly filtered columns:
   ```sql
   CREATE INDEX idx_regulations_best_peak_coords
   ON regulations(species_id, best_peak_chr, best_peak_start, best_peak_end);

   CREATE INDEX idx_chipseq_peaks_coords
   ON chipseq_peaks_human(chromosome, peak_start, peak_end);
   ```

2. **Materialized view** for frequently accessed overlaps:
   ```sql
   CREATE MATERIALIZED VIEW mv_lncrna_chipseq_overlaps AS
   SELECT ... FROM regulations r JOIN chipseq_peaks_human p ...;
   ```

3. **Limit result set** by using more selective filters (chromosome, mark_type, cell_type)

## Error Handling

### Validation Errors

The API validates all input parameters and returns detailed error messages:

```json
{
  "detail": [
    {
      "type": "greater_than_equal",
      "loc": ["query", "page"],
      "msg": "Input should be greater than or equal to 1",
      "input": "-1",
      "ctx": {"ge": 1}
    }
  ]
}
```

### Query Too Broad (fallback without MV)

When MV is unavailable and the request is too broad (e.g. `chromosome=chr1` without additional filters),
the API returns `400` with a structured error payload:

This can happen on:
- `GET /api/v1/lncrna-chipseq-overlap`
- `GET /api/v1/lncrna-chipseq-overlap/cursor`
- `GET /api/v1/lncrna-chipseq-overlap/statistics`
- `GET /api/v1/lncrna-chipseq-overlap/heatmap`
- `GET /api/v1/lncrna-chipseq-overlap/export`

```json
{
  "detail": {
    "error": "QUERY_TOO_BROAD",
    "suggest_filters": ["mark_type", "cell_type", "min_binding_affinity"],
    "message": "Query for chr1 is too broad without materialized view 'mv_lncrna_chipseq_overlaps'. Please add additional filters (...)",
    "chromosome": "chr1",
    "using_materialized_view": false
  }
}
```

### Empty Results

When no overlaps match the criteria:

```json
{
  "total": 0,
  "page": 1,
  "page_size": 100,
  "total_pages": 0,
  "items": []
}
```

## Testing

### Run Test Suite

```bash
# Make executable
chmod +x test_lncrna_chipseq_overlap_api.sh

# Run all tests
./test_lncrna_chipseq_overlap_api.sh
```

### Manual Testing

```bash
# Check health
curl http://localhost:8000/health

# View Swagger docs
open http://localhost:8000/docs

# Test basic query
curl "http://localhost:8000/api/v1/lncrna-chipseq-overlap?chromosome=chr22&page=1&page_size=5" | jq
```

## Implementation Files

| File | Description |
|------|-------------|
| `/frontend/backend/app/routers/lncrna_chipseq_overlap.py` | API endpoints and query logic |
| `/frontend/backend/app/schemas/lncrna_chipseq_overlap.py` | Pydantic models for request/response |
| `/frontend/backend/main.py` | Router registration |
| `/test_lncrna_chipseq_overlap_api.sh` | Test script |

## Next Steps

### Phase 1 Backend (Completed ✅)
- [x] Create Pydantic schemas
- [x] Implement API endpoints
- [x] Register router in main.py
- [x] Test with real database
- [x] Validate parameter handling
- [x] Document API

### Phase 2 Frontend (Next)
- [ ] Create React components for overlap visualization
- [ ] Implement filter UI (mark type, cell type, etc.)
- [ ] Add IGV.js integration for genomic visualization
- [ ] Create statistics dashboard

### Phase 3 Optimization (Future)
- [ ] Add database indexes
- [ ] Create materialized views
- [ ] Implement caching for statistics
- [ ] Add export functionality (CSV, BED format)
