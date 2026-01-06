# ChIP-seq Epigenetic Marks Backend Architecture

## Overview

This document describes the unified backend architecture for supporting multiple histone modifications (epigenetic marks) in the Human lncRNA Atlas. The design follows **Scheme C: Unified Track with mark_type Field**, enabling extensible support for 20+ different marks while maintaining query performance.

## Architecture Summary

### Design Principles

1. **Single Track Registration**: One `chipseq_epigenetic` track in `feature_tracks` table
2. **Dedicated Tables**: `chipseq_peaks` and `chipseq_experiments` for optimal performance
3. **Flexible Metadata**: `mark_type` and `mark_category` fields enable filtering
4. **Partitioned Storage**: Peaks table partitioned by `species_id` for scalability
5. **Pre-computed Associations**: `gene_peak_associations` for fast gene-level queries
6. **Materialized Views**: Cached statistics for dashboard performance

### Key Components

```
epigenetic_mark_types     -- Reference table of mark definitions
       |
       v
chipseq_experiments       -- Experiment metadata with mark_type
       |
       v
chipseq_peaks             -- Peak data (partitioned by species_id)
       |
       v
gene_peak_associations    -- Pre-computed gene-peak relationships
```

## File Locations

| File | Location | Purpose |
|------|----------|---------|
| SQL DDL | `/frontend/backend/sql/chipseq_schema.sql` | Database schema |
| Pydantic Schemas | `/frontend/backend/app/schemas/chipseq.py` | API models |
| API Router | `/frontend/backend/app/routers/chipseq.py` | Endpoints |
| Import Script | `/frontend/backend/scripts/import_chipseq.py` | Data import |
| Config Template | `/frontend/backend/scripts/chipseq_experiment_template.json` | Import config |

---

## API Endpoints Reference

### Mark Types

| Endpoint | Method | Description |
|----------|--------|-------------|
| `/features/chipseq/marks` | GET | List all available mark types |
| `/features/chipseq/marks/{species_id}` | GET | Get marks with data for species |
| `/features/chipseq/marks/relationships` | GET | Get mark relationships (bivalent, etc.) |

### Experiments

| Endpoint | Method | Description |
|----------|--------|-------------|
| `/features/chipseq/experiments` | GET | List experiments with filtering |
| `/features/chipseq/experiments/{id}` | GET | Get experiment details |

### Gene-Level Queries (Primary Use Case)

| Endpoint | Method | Description |
|----------|--------|-------------|
| `/features/chipseq/genes/{gene_id}` | GET | Get peaks for gene region |
| `/features/chipseq/genes/{gene_id}/summary` | GET | Get aggregated statistics |
| `/features/chipseq/genes/{gene_id}/compare` | GET | Compare multiple marks |

### Region-Based Queries

| Endpoint | Method | Description |
|----------|--------|-------------|
| `/features/chipseq/regions/{species_id}` | GET | Query peaks by genomic region |

### Statistics

| Endpoint | Method | Description |
|----------|--------|-------------|
| `/features/chipseq/stats` | GET | Global ChIP-seq statistics |

### Query Parameters

Common parameters for filtering:

```
?mark_type=H3K27me3,H3K4me3    # Filter by mark type(s)
?mark_category=repressive      # Filter by category
?min_fold_enrichment=2.0       # Signal threshold
?max_qvalue=0.05               # Significance threshold
?flanking=20000                # Flanking region size (bp)
```

---

## Performance Optimization Strategies

### 1. Indexing Strategy

#### Primary Indexes (Critical)

```sql
-- Genomic range queries (most important)
CREATE INDEX idx_chipseq_peaks_location
    ON chipseq_peaks (species_id, chromosome, peak_start, peak_end);

-- Experiment + location (for mark-filtered queries)
CREATE INDEX idx_chipseq_peaks_exp_location
    ON chipseq_peaks (experiment_id, chromosome, peak_start, peak_end);

-- Gene-peak association lookups
CREATE INDEX idx_gene_peak_assoc_gene_exp
    ON gene_peak_associations (gene_id, experiment_id);
```

#### GiST Index for Overlap Queries (PostgreSQL 14+)

```sql
CREATE INDEX idx_chipseq_peaks_range
    ON chipseq_peaks USING GIST (
        species_id,
        chromosome,
        int8range(peak_start, peak_end, '[]')
    );
```

This enables efficient `&&` (overlap) operator queries:
```sql
WHERE int8range(peak_start, peak_end) && int8range(region_start, region_end)
```

### 2. Table Partitioning

The `chipseq_peaks` table is partitioned by `species_id`:

```sql
CREATE TABLE chipseq_peaks (
    ...
) PARTITION BY LIST (species_id);

CREATE TABLE chipseq_peaks_human PARTITION OF chipseq_peaks FOR VALUES IN (1);
CREATE TABLE chipseq_peaks_mouse PARTITION OF chipseq_peaks FOR VALUES IN (2);
CREATE TABLE chipseq_peaks_default PARTITION OF chipseq_peaks DEFAULT;
```

**Benefits:**
- Query partition pruning (only scan relevant species)
- Parallel index maintenance
- Easier data management per species

### 3. Materialized Views

Pre-computed statistics for dashboard/overview queries:

```sql
-- Mark type statistics (refresh after import)
CREATE MATERIALIZED VIEW mv_chipseq_mark_stats AS ...;

-- Gene-level mark summary (for gene detail pages)
CREATE MATERIALIZED VIEW mv_gene_mark_summary AS ...;
```

**Refresh Strategy:**
```sql
-- Called after data import
SELECT refresh_chipseq_stats();

-- Or via cron job (e.g., daily)
REFRESH MATERIALIZED VIEW CONCURRENTLY mv_chipseq_mark_stats;
```

### 4. Query Optimization Patterns

#### Gene Region Query (Optimized)

```sql
-- Use index hint via WHERE clause ordering
SELECT p.*
FROM chipseq_peaks p
JOIN chipseq_experiments e ON p.experiment_id = e.experiment_id
WHERE p.species_id = 1                    -- Partition pruning FIRST
  AND p.chromosome = 'chr1'               -- Index filter
  AND p.peak_start < region_end           -- Range scan
  AND p.peak_end > region_start
  AND e.is_active = TRUE;
```

#### Avoid Common Anti-Patterns

```sql
-- BAD: Function on indexed column
WHERE LOWER(chromosome) = 'chr1'

-- GOOD: Pre-normalize data
WHERE chromosome = 'chr1'

-- BAD: OR conditions on different columns
WHERE experiment_id = 1 OR mark_type = 'H3K27me3'

-- GOOD: Use UNION or separate queries
```

### 5. Connection Pooling

Configure SQLAlchemy for async with connection pooling:

```python
# In database.py
from sqlalchemy.ext.asyncio import create_async_engine

engine = create_async_engine(
    DATABASE_URL,
    pool_size=20,
    max_overflow=10,
    pool_timeout=30,
    pool_recycle=1800,
)
```

### 6. Caching Strategy

Implement multi-level caching:

```python
# Example using Redis
@cached(ttl=3600, key_builder=lambda g, mt: f"chipseq:{g}:{mt}")
async def get_gene_chipseq_cached(gene_id: int, mark_types: str):
    ...
```

**Cache Hierarchy:**
1. **In-memory** (LRU, 5 min): Frequently accessed genes
2. **Redis** (1 hour): Mark type lists, statistics
3. **Materialized Views** (daily): Global aggregations

---

## Scalability Assessment

### Data Volume Projections

| Metric | Current | 6 Months | 1 Year |
|--------|---------|----------|--------|
| Mark Types | 15 | 20 | 25+ |
| Experiments/Mark | 5 | 30 | 50 |
| Peaks/Experiment | 100K | 100K | 100K |
| Total Peaks (Human) | 7.5M | 60M | 125M |
| Total Peaks (All Species) | 15M | 120M | 250M |

### Storage Estimates

| Component | Per Record | 100M Records |
|-----------|------------|--------------|
| chipseq_peaks | ~200 bytes | ~20 GB |
| Indexes | ~100 bytes | ~10 GB |
| gene_peak_associations | ~50 bytes | ~5 GB (10M records) |
| Total | | ~35-50 GB |

### Query Performance Benchmarks

Expected response times with proper indexing:

| Query Type | Records | Expected Time |
|------------|---------|---------------|
| Single gene, all marks | ~100 peaks | < 50ms |
| Single gene, 1 mark | ~20 peaks | < 20ms |
| Region query (1MB) | ~1000 peaks | < 100ms |
| Mark comparison (2 marks) | ~200 peaks | < 100ms |
| Global statistics | Cached | < 10ms |

### Scaling Strategies

#### Horizontal Scaling (Future)

1. **Read Replicas**: Route read queries to replicas
2. **Sharding by Species**: Separate databases per species
3. **Time-based Partitioning**: Archive older experiments

#### Vertical Scaling (Recommended First)

1. **Index Optimization**: Analyze and tune indexes quarterly
2. **Memory Tuning**: Increase `shared_buffers` for large datasets
3. **SSD Storage**: Critical for index-heavy workloads

---

## Compatibility with Existing Architecture

### RepeatMasker Coexistence

The ChIP-seq architecture is designed to coexist with RepeatMasker:

| Aspect | RepeatMasker | ChIP-seq |
|--------|--------------|----------|
| Track Name | `repeatmasker_repeats` | `chipseq_epigenetic` |
| Track Category | `repeat` | `epigenetic` |
| Data Table | `genomic_features` | `chipseq_peaks` |
| API Prefix | `/features/repeats/` | `/features/chipseq/` |

### Shared Infrastructure

Both systems use:
- Same `species` table reference
- Same `import_batches` table for tracking
- Same `genes` table for gene lookups
- Same authentication/authorization layer

### Feature Tracks Registration

```sql
-- RepeatMasker (existing)
INSERT INTO feature_tracks (track_name, track_category, display_name)
VALUES ('repeatmasker_repeats', 'repeat', 'RepeatMasker Annotations');

-- ChIP-seq (new)
INSERT INTO feature_tracks (track_name, track_category, display_name)
VALUES ('chipseq_epigenetic', 'epigenetic', 'ChIP-seq Histone Modifications');
```

### API Router Registration

```python
# In main.py
from app.routers import features, chipseq

app.include_router(features.router)  # RepeatMasker: /features/...
app.include_router(chipseq.router)   # ChIP-seq: /features/chipseq/...
```

---

## Data Import Workflow

### 1. Prepare Metadata

Create experiment configuration JSON:

```json
{
    "input_file": "H3K27me3_peaks.narrowPeak.gz",
    "mark_type": "H3K27me3",
    "species_code": "human",
    "experiment_name": "ENCODE_H1_H3K27me3",
    "cell_type": "H1-hESC",
    "source_database": "ENCODE",
    "source_accession": "ENCSR000AKP"
}
```

### 2. Run Import

```bash
# Using config file
python3 scripts/import_chipseq.py --config experiment.json

# Or with CLI arguments
python3 scripts/import_chipseq.py \
    --input H3K27me3_peaks.narrowPeak.gz \
    --mark-type H3K27me3 \
    --species human \
    --experiment-name "ENCODE_H1_H3K27me3" \
    --cell-type "H1-hESC"
```

### 3. Verify Import

```sql
-- Check experiment
SELECT * FROM chipseq_experiments WHERE experiment_name = 'ENCODE_H1_H3K27me3';

-- Check peak count
SELECT COUNT(*) FROM chipseq_peaks WHERE experiment_id = :id;

-- Check import batch
SELECT * FROM import_batches WHERE batch_type = 'chipseq' ORDER BY import_date DESC;
```

### 4. Refresh Statistics

```sql
SELECT refresh_chipseq_stats();
```

---

## Monitoring and Maintenance

### Key Metrics to Monitor

1. **Query Performance**
   - P95 response time for gene queries
   - Slow query log entries

2. **Data Growth**
   - Peak count per experiment
   - Table/index sizes

3. **Cache Hit Rates**
   - Redis hit/miss ratio
   - Materialized view freshness

### Maintenance Tasks

| Task | Frequency | Command |
|------|-----------|---------|
| Refresh MV | After import | `SELECT refresh_chipseq_stats()` |
| Vacuum Analyze | Weekly | `VACUUM ANALYZE chipseq_peaks` |
| Index Rebuild | Monthly | `REINDEX TABLE chipseq_peaks` |
| Statistics Update | Monthly | `ANALYZE chipseq_peaks` |

### Health Check Query

```sql
SELECT
    'chipseq_peaks' as table_name,
    pg_size_pretty(pg_total_relation_size('chipseq_peaks')) as total_size,
    pg_size_pretty(pg_indexes_size('chipseq_peaks')) as index_size,
    (SELECT COUNT(*) FROM chipseq_peaks) as row_count,
    (SELECT COUNT(DISTINCT experiment_id) FROM chipseq_peaks) as experiments;
```

---

## Future Extensions

### Planned Features

1. **Chromatin State Annotations**: Integration with ChromHMM states
2. **Signal Tracks**: BigWig signal visualization
3. **Multi-omics Integration**: Combined analysis with ATAC-seq, DNase-seq
4. **Machine Learning Features**: Bivalent domain prediction, enhancer classification

### Extensibility Points

1. **New Mark Types**: Add to `epigenetic_mark_types` table
2. **New Peak Attributes**: Extend `attributes` JSONB column
3. **New Analysis Types**: Add computed columns or materialized views
4. **New Species**: Create new partition automatically

---

## Appendix: Complete Table Schema

### epigenetic_mark_types

| Column | Type | Description |
|--------|------|-------------|
| mark_type_id | SERIAL | Primary key |
| mark_name | VARCHAR(50) | Mark identifier (e.g., H3K27me3) |
| mark_category | VARCHAR(30) | Category (repressive, activating, etc.) |
| display_name | VARCHAR(100) | Human-readable name |
| display_color | VARCHAR(20) | Hex color for visualization |
| biological_function | TEXT | Brief description |
| associated_state | VARCHAR(100) | Chromatin state |
| is_active | BOOLEAN | Active flag |
| sort_order | INTEGER | Display order |

### chipseq_experiments

| Column | Type | Description |
|--------|------|-------------|
| experiment_id | SERIAL | Primary key |
| experiment_name | VARCHAR(200) | Unique name |
| species_id | INTEGER | FK to species |
| mark_type_id | INTEGER | FK to mark_types |
| cell_type | VARCHAR(200) | Cell type |
| tissue_type | VARCHAR(200) | Tissue type |
| source_database | VARCHAR(100) | ENCODE, GEO, etc. |
| source_accession | VARCHAR(100) | Accession number |
| peak_caller | VARCHAR(50) | Peak calling tool |
| frip_score | NUMERIC(5,4) | Quality metric |
| is_active | BOOLEAN | Active flag |

### chipseq_peaks (Partitioned)

| Column | Type | Description |
|--------|------|-------------|
| peak_id | BIGSERIAL | Primary key (part) |
| experiment_id | INTEGER | FK to experiments |
| species_id | INTEGER | Partition key |
| chromosome | VARCHAR(20) | Chromosome name |
| peak_start | BIGINT | Start position |
| peak_end | BIGINT | End position |
| summit_position | BIGINT | Summit position |
| fold_enrichment | NUMERIC(10,4) | Signal strength |
| qvalue | NUMERIC(15,10) | FDR-corrected significance |
| peak_width | INTEGER | Computed (end - start) |
| attributes | JSONB | Flexible attributes |
