# Database Schema Documentation

## Overview

Human LncRNA Atlas uses PostgreSQL as the primary database with the following characteristics:

- **Total records**: 12M+ across all tables
- **Primary data**: 800K+ regulatory relationships, 4.6M+ ChIP-seq peaks
- **Extensions**: pg_trgm (trigram search)

## Core Tables

### species
Physical storage for supported primate species.

| Column | Type | Description |
|--------|------|-------------|
| species_id | INTEGER PK | Species ID (1=Human, 2=Chimp, 3=Macaque, 4=Marmoset) |
| species_code | VARCHAR(20) | Short code (e.g., "human", "chimp") |
| display_name | VARCHAR(100) | Display name (e.g., "Human") |
| latin_name | VARCHAR(100) | Latin name (e.g., "Homo sapiens") |
| genome_assembly | VARCHAR(50) | Reference genome (e.g., "hg38") |

### core_genes
Cross-species gene identifiers using human orthologs as reference.

| Column | Type | Description |
|--------|------|-------------|
| core_id | INTEGER PK | Cross-species gene ID |
| gene_type | VARCHAR(20) | "lncRNA" or "protein_coding" |
| canonical_symbol | VARCHAR(100) | Standard gene symbol |
| human_ensembl_id | VARCHAR(50) | Human Ensembl ID |
| description | TEXT | Gene description |

### genes
Species-specific gene records linked to core_genes.

| Column | Type | Description |
|--------|------|-------------|
| gene_id | INTEGER PK | Species-specific gene ID |
| core_id | INTEGER FK | Reference to core_genes (nullable) |
| species_id | INTEGER FK | Reference to species |
| gene_ensembl_id | VARCHAR(50) | Ensembl gene ID |
| gene_name | VARCHAR(100) | Gene symbol |
| chromosome | VARCHAR(20) | Chromosome |
| gene_start | BIGINT | Start position |
| gene_end | BIGINT | End position |
| strand | VARCHAR(1) | "+" or "-" |

**Unique constraint**: (species_id, gene_ensembl_id)

### regulations
LncRNA-target gene regulatory relationships (~800K records).

| Column | Type | Description |
|--------|------|-------------|
| regulation_id | BIGINT PK | Auto-increment ID |
| species_id | INTEGER FK | Reference to species |
| lncrna_gene_id | INTEGER FK | LncRNA gene reference |
| target_gene_id | INTEGER FK | Target gene reference |
| target_chromosome | VARCHAR(50) | Target chromosome |
| target_start | BIGINT | Target region start |
| target_end | BIGINT | Target region end |
| binding_affinity | NUMERIC(10,4) | Predicted binding affinity |
| triplex_score | NUMERIC(10,4) | Triplex formation score |
| tfo_file | VARCHAR(500) | Source TFO file path |
| total_sites | INTEGER | Total binding sites |
| kept_sites | INTEGER | Filtered binding sites |

**Key indexes**:
- `idx_regulations_lncrna_gene_id` - JOIN optimization
- `idx_regulations_target_gene_id` - JOIN optimization
- `idx_regulations_species_ba` - (species_id, binding_affinity DESC)
- `idx_regulations_species_chr` - (species_id, target_chromosome)

### traits
Disease/trait information from GWAS studies.

| Column | Type | Description |
|--------|------|-------------|
| trait_id | INTEGER PK | Trait ID |
| trait_name | VARCHAR(500) | Disease/trait name |
| trait_category | VARCHAR(100) | Category (e.g., "cancer") |
| trait_doid | VARCHAR(50) | Disease Ontology ID |
| description | TEXT | Trait description |

**Key indexes**:
- `idx_traits_trait_name_trgm` - GIN trigram index for ILIKE search

### trait_gene_associations
Disease-gene associations with statistical evidence.

| Column | Type | Description |
|--------|------|-------------|
| association_id | INTEGER PK | Association ID |
| trait_id | INTEGER FK | Reference to traits |
| core_id | INTEGER FK | Reference to core_genes |
| ontology_id | INTEGER FK | Reference to ontologies |
| odds_ratio | NUMERIC | Association strength |
| fdr | NUMERIC | False discovery rate |
| evidence_species_id | INTEGER FK | Evidence source species |

### chip_peaks
ChIP-seq peak data (~4.6M records).

| Column | Type | Description |
|--------|------|-------------|
| peak_id | BIGINT PK | Peak ID |
| experiment_id | INTEGER FK | Reference to chipseq_experiments |
| chromosome | VARCHAR(50) | Chromosome |
| start_pos | BIGINT | Peak start |
| end_pos | BIGINT | Peak end |
| signal_value | NUMERIC | Peak signal strength |
| p_value | NUMERIC | Statistical significance |
| q_value | NUMERIC | FDR-adjusted p-value |
| fold_enrichment | NUMERIC | Fold enrichment over background |

### chipseq_experiments
ChIP-seq experiment metadata.

| Column | Type | Description |
|--------|------|-------------|
| experiment_id | INTEGER PK | Experiment ID |
| encode_id | VARCHAR(50) | ENCODE accession |
| target_protein | VARCHAR(100) | Target protein/histone mark |
| cell_type | VARCHAR(200) | Cell type |
| biosample_type | VARCHAR(100) | Biosample type |
| species_id | INTEGER FK | Reference to species |

**Key indexes**:
- `idx_chipseq_experiments_cell_type_trgm` - GIN trigram index for ILIKE search

### mv_lncrna_chipseq_overlaps
Materialized view for pre-computed regulatory-ChIP overlap (~6.5M records).

| Column | Type | Description |
|--------|------|-------------|
| overlap_id | BIGINT PK | Overlap ID |
| regulation_id | BIGINT FK | Reference to regulations |
| peak_id | BIGINT FK | Reference to chip_peaks |
| overlap_start | BIGINT | Overlap region start |
| overlap_end | BIGINT | Overlap region end |
| overlap_length | INTEGER | Overlap length in bp |

## Performance Indexes

### Trigram Indexes (pg_trgm)
Enable efficient ILIKE '%pattern%' queries:

```sql
-- traits.trait_name
idx_traits_trait_name_trgm USING GIN (trait_name gin_trgm_ops)

-- chipseq_experiments.cell_type
idx_chipseq_experiments_cell_type_trgm USING GIN (cell_type gin_trgm_ops)
```

### Regulation Table Indexes
Optimize JOIN and filter operations:

```sql
idx_regulations_lncrna_gene_id (lncrna_gene_id)
idx_regulations_target_gene_id (target_gene_id)
idx_regulations_species_ba (species_id, binding_affinity DESC)
idx_regulations_species_chr (species_id, target_chromosome)
```

## Migrations

Schema changes are managed through versioned SQL scripts in `migrations/`:

```bash
# Check status
python migrations/run_migrations.py --status

# Apply pending migrations
python migrations/run_migrations.py
```

See `migrations/README.md` for details.
