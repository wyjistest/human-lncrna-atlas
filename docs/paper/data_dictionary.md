# Data Dictionary (Paper Working Notes)

This document summarizes the core entities, fields, and conventions used by **Human LncRNA Atlas** for the purpose of writing the academic article. It is intentionally concise and focuses on fields that appear in analyses, figures, or API exports.

**Primary schema sources**

- ORM: `frontend/backend/app/models/models.py`
- Design doc: `docs/DATABASE_DESIGN_FINAL.md`

---

## Conventions

### Species

The database uses numeric `species_id` plus a stable `species_code`:

| species_id | species_code | display |
|---:|---|---|
| 1 | `human` | Human |
| 2 | `chimp` | Chimpanzee |
| 3 | `macaque` | Macaque |
| 4 | `marmoset` | Marmoset |

### Core gene mapping (orthology)

Cross-species linkage is represented by `core_id` (table `core_genes`). A per-species gene record (`genes.gene_id`) may have `core_id = NULL` when no orthology information is available.

### Regulatory edge (lncRNA → target)

The primary regulatory relationship is stored in `regulations` with:

- direction: `lncrna_gene_id` → `target_gene_id`
- weight: `binding_affinity` (numeric; derived from input `Best_Site_BA`)

### Genomic coordinates

Coordinates are stored as integer/bigint fields (e.g., `gene_start`, `gene_end`, `peak_start`, `peak_end`). For manuscript Methods, explicitly state the coordinate convention used for each data type (TBC if not confirmed).

---

## Core tables (multi-species regulatory atlas)

### `species`

Metadata for each species/assembly.

**Key fields**: `species_id`, `species_code`, `display_name`, `latin_name`, `genome_assembly`

### `core_genes`

Cross-species gene entities and orthology grouping.

**Key fields**:

- `core_id`: cross-species identifier
- `gene_type`: `lncRNA` or `protein_coding`
- `canonical_symbol`: canonical name/symbol (if available)
- `human_ensembl_id`: human Ensembl ID (if available)

### `genes`

Species-specific gene records.

**Key fields**:

- `gene_id`: per-species gene identifier (primary key used by most APIs)
- `core_id`: optional link to `core_genes.core_id`
- `species_id`: FK to `species`
- `gene_ensembl_id`: Ensembl-like identifier (species-specific; may include suffix in non-human cases)
- `gene_name`: display name
- `chromosome`, `gene_start`, `gene_end`, `strand`

### `regulations`

Predicted lncRNA regulatory relationships (edge table).

**Key fields**:

- `regulation_id`: unique edge record
- `species_id`: species of this regulatory relationship
- `lncrna_gene_id`: FK to `genes.gene_id` (lncRNA node)
- `target_gene_id`: FK to `genes.gene_id` (protein-coding node)
- `binding_affinity`: edge weight (numeric)
- target region (optional details used by IGV/exports): `target_chromosome`, `target_start`, `target_end`
- peak/site summary fields used by upstream prediction pipeline: `best_*`, `total_sites`, `kept_sites`, `num_peaks`, etc.

### `sequences`

Per-regulation linked sequences.

**Key fields**:

- `regulation_id`: FK to `regulations.regulation_id` (1:1)
- `lncrna_sequence`: lncRNA sequence segment
- `dna_sequence`: target DNA sequence segment

### `import_batches`

Tracks ETL imports and provenance.

**Key fields**: `batch_id`, `batch_name`, `batch_type`, `species_id`, `source_file`, `record_count`, `status`, `completed_at`

---

## Disease/trait integration (GWAS)

### `traits`

Disease/trait metadata.

**Key fields**: `trait_id`, `trait_name`, `trait_doid`, `trait_category`, `description`

### `ontologies`

Ontology terms (e.g., tissue/cell type groupings) used in trait association context.

**Key fields**: `ontology_id`, `ontology_name`, `ontology_cl_id`, `ontology_type`

### `trait_gene_associations`

Trait ↔ gene associations at **core_id** level.

**Key fields**:

- `core_id`: FK to `core_genes.core_id`
- `trait_id`, `ontology_id`
- statistical fields: `odds_ratio`, `fdr`, `trait_snp_pvalue`, `ontology_mw_pvalue`, `ontology_fold_enrichment`
- provenance: `source_table`, `source_row_number`, `evidence_species_id`

---

## Generic genomic features (RepeatMasker, conservation, etc.)

### `feature_tracks`

Track registry (metadata + JSON schema for attributes).

**Key fields**:

- `track_name` (unique), `track_category` (e.g., `repeat`, `epigenetic`, `conservation`)
- `display_name`, `display_color`
- `attribute_schema` (JSON schema-like)
- `source_database`, `version`, `is_active`

### `genomic_features`

Partitioned table for genomic intervals associated to a track (`feature_tracks`), partitioned by `species_id`.

**Key fields**:

- `track_id`, `species_id`
- `chromosome`, `feature_start`, `feature_end`, `strand`
- `feature_name`, `score`
- `attributes` (JSON; e.g., repeat class/family/divergence)

---

## ChIP-seq epigenetic marks

### `epigenetic_mark_types`

Reference table for mark types.

**Key fields**: `mark_name`, `mark_category`, `display_name`, `display_color`, `biological_function`, `sort_order`

### `mark_relationships`

Defines relationships between mark types (e.g., bivalent pairs).

**Key fields**: `mark_type_id_1`, `mark_type_id_2`, `relationship_type`, `biological_significance`

### `chipseq_experiments`

Experiment metadata.

**Key fields**:

- `experiment_name`, `species_id`, `mark_type_id`
- sample metadata: `cell_type`, `tissue_type`, `cell_line`, `treatment`
- processing metadata: `source_database`, `source_accession`, `data_url`, `pipeline_version`, `peak_caller`, `reference_genome`
- QC fields (optional): `total_reads`, `mapped_reads`, `duplicate_rate`, `frip_score`

### `chipseq_peaks`

Partitioned peak table (by `species_id`) linked to `chipseq_experiments`.

**Key fields**:

- `experiment_id`, `species_id`
- `chromosome`, `peak_start`, `peak_end`, `summit_position`, `strand`
- signal metrics: `fold_enrichment`, `pvalue`, `qvalue`, `signal_value`, `score`
- `attributes` (JSON; optional)

### `gene_peak_associations`

Precomputed gene–peak relationships (used for fast gene-centric queries and exports).

**Key fields**:

- `gene_id`, `peak_id`, `species_id`, `experiment_id`
- `overlap_type` (e.g., promoter / gene body / upstream)
- `distance_to_tss`, `overlap_bp`, `overlap_percentage`
- cached peak metrics: `peak_fold_enrichment`, `peak_qvalue`

---

## API exports useful for paper figures (examples)

- Disease network export: `GET /api/v1/export/disease-network?trait_name=...`
- ChIP-seq overlaps export: `GET /api/v1/export/chipseq-overlaps?mark_names=...`
- lncRNA–ChIP-seq overlap export: `GET /api/v1/lncrna-chipseq-overlap/export?...`

For finalized Methods, pin the exact query parameters and commit SHA used to generate each figure/table.

