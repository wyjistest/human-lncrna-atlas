# lncRNA-ChIP-seq Overlap API Documentation

## Overview

This API provides endpoints for querying overlaps between lncRNA binding sites and ChIP-seq peaks, enabling analysis of lncRNA-mediated epigenetic regulation mechanisms.

## Endpoints

### 1. Query Overlaps (GET `/api/v1/lncrna-chipseq-overlap`)

Get paginated list of lncRNA-ChIP-seq overlaps with flexible filtering.

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
| `sort_by` | string | No | "binding_affinity" | Sort field: "binding_affinity", "overlap_length", "peak_fold_enrichment" |
| `sort_order` | string | No | "desc" | Sort order: "asc" or "desc" |

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
  ]
}
```

#### Example Requests

**Basic query:**
```bash
curl "http://localhost:8000/api/v1/lncrna-chipseq-overlap?chromosome=chr1&page=1&page_size=10"
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
curl "http://localhost:8000/api/v1/lncrna-chipseq-overlap?chromosome=chr1&sort_by=overlap_length&sort_order=desc&page=1&page_size=10"
```

### 2. Get Statistics (GET `/api/v1/lncrna-chipseq-overlap/statistics`)

Get summary statistics for lncRNA-ChIP-seq overlaps.

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
  "avg_overlap_length": 96.34,
  "avg_binding_affinity": 69.62,
  "avg_peak_strength": 17.15
}
```

#### Example Requests

**Overall statistics:**
```bash
curl "http://localhost:8000/api/v1/lncrna-chipseq-overlap/statistics"
```

**Statistics for chr1:**
```bash
curl "http://localhost:8000/api/v1/lncrna-chipseq-overlap/statistics?chromosome=chr1"
```

**Statistics for specific mark type:**
```bash
curl "http://localhost:8000/api/v1/lncrna-chipseq-overlap/statistics?mark_type=H3K27me3"
```

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

- Query time: ~15-50 seconds for complex queries (with multiple joins and filters)
- Total overlaps: 219,213 for chr1 (human, species_id=1)
- Database: PostgreSQL with partitioned chipseq_peaks table

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
curl "http://localhost:8000/api/v1/lncrna-chipseq-overlap?chromosome=chr1&page=1&page_size=5" | jq
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
