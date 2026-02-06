# Human LncRNA Atlas: a cross-species lncRNA regulatory relationship database with integrated epigenomic context across four primate species

**Article type:** Research Article (database/resource)

**Species:** Human (*Homo sapiens*), Chimpanzee (*Pan troglodytes*), Macaque (*Macaca mulatta*), Marmoset (*Callithrix jacchus*)

**Genome assemblies (IGV):** hg19, panTro5, rheMac10, calJac3

> Author note: This is a working draft. Numbers marked as **TBC** should be re-checked against the exported snapshot used for submission.

---

## Abstract

Long non-coding RNAs (lncRNAs) regulate gene expression through diverse mechanisms, yet cross-species resources that integrate predicted lncRNA–target regulatory relationships with epigenomic context remain limited. Here we present **Human LncRNA Atlas**, a database and visualization platform that integrates lncRNA regulatory relationships across four primate species (human, chimpanzee, macaque, and marmoset), together with orthology-aware comparison and epigenomic annotations.

The current release contains **804,630** predicted lncRNA–protein-coding gene regulations (binding affinity, genomic coordinates, and linked lncRNA/DNA sequences) across four species, with complete sequence coverage for all regulations. To contextualize regulatory relationships, we integrate ENCODE-derived epigenomic tracks including ChIP-seq histone modification peaks (six core marks; **~2.37M** peaks across 7 cell lines), DNase-seq open chromatin peaks (**~1.22M** peaks across 7 cell lines), and RepeatMasker annotations (**5.48M** elements), as well as GWAS trait associations (**~67k** gene–trait links; TBC) to enable disease-centric exploration.

Human LncRNA Atlas provides a web interface and APIs for multi-dimensional querying, interactive network visualization, genome browser inspection, and data export, supporting cross-species hypothesis generation and reproducible downstream analyses.

**Keywords:** lncRNA, regulatory network, cross-species, primate, epigenomics, ChIP-seq, DNase-seq, database, visualization

---

## Introduction

Long non-coding RNAs (lncRNAs) have emerged as key regulators of transcriptional and post-transcriptional processes. Many lncRNAs show lineage-specific expression and rapid sequence evolution, complicating functional inference across species. Cross-species regulatory atlases can help distinguish conserved versus species-specific regulatory programs and prioritize lncRNAs for experimental follow-up.

Meanwhile, epigenomic assays such as ChIP-seq histone modifications and DNase-seq provide orthogonal context for interpreting regulatory relationships (e.g., promoter activation, repression, and bivalent states). Integrating regulatory network edges with epigenomic features at relevant genomic loci can refine hypotheses about regulatory mechanisms and cell-type specificity.

To address these needs, we built Human LncRNA Atlas, a cross-species lncRNA regulatory relationship database spanning four primate species, coupled with a web platform that supports interactive network exploration, genome browser visualization, and exportable, reproducible analyses.

---

## Data Content

### Regulatory relationships (lncRNA → target gene)

Human LncRNA Atlas stores predicted regulatory relationships between lncRNAs and protein-coding target genes, each annotated with binding affinity, genomic coordinates, and supporting sequences.

**Species distribution (current snapshot)**:

| Species | Code | Genes | Regulations |
|---|---|---:|---:|
| Human | `human` | ~5,484 | 496,064 |
| Chimpanzee | `chimp` | ~6,138 | 156,136 |
| Macaque | `macaque` | ~5,406 | 102,430 |
| Marmoset | `marmoset` | ~4,805 | 50,000 |

### Orthology mapping for cross-species comparison

Genes are linked across species through a shared **core gene identifier** (core_id), enabling orthology-aware network comparison and conservation analysis (TBC: orthology source/version should be stated explicitly in the finalized manuscript).

### Epigenomic annotations

We provide integrated epigenomic features for contextualizing regulatory relationships:

- ChIP-seq histone modification peaks (ENCODE; 7 cell lines; H3K27me3, H3K4me3, H3K4me1, H3K27ac, H3K36me3, H3K9me3; peak-level statistics and multi-mark comparison).
- DNase-seq DNase-HS open chromatin peaks (ENCODE; pre-indexed bigBed for fast genome browser streaming).
- RepeatMasker repeat element annotations (UCSC; genome-wide coverage).

### Disease/trait associations (GWAS)

GWAS-derived gene–trait associations enable disease-centric network exploration that links trait-associated genes to upstream lncRNA regulators.

---

## Platform and Access

### Web interface

Human LncRNA Atlas supports:

- multi-parameter querying by species, gene name, chromosome region, and binding affinity;
- interactive network visualization (Cytoscape.js);
- IGV.js genome browser integration across four assemblies;
- epigenetic mark comparison and bivalent domain inspection;
- data export (CSV/XLSX/JSON/BED where applicable).

### Programmatic APIs

The backend provides documented APIs (FastAPI OpenAPI) for query, network retrieval, and export. Example endpoints include:

- `GET /api/v1/regulations` (filtered list)
- `GET /api/v1/network/gene/{id}` (gene-centered network)
- `GET /api/v1/network/compare` (cross-species comparison via orthology mapping)
- `GET /api/v1/export/*` (analysis exports; e.g., disease network, ChIP-seq overlaps)

---

## Results (initial analyses; extend as needed)

### High-affinity regulators and subnetwork structure

Using the provided notebooks, we ranked lncRNAs by the number of high-affinity targets and summarized species-specific distributions (TBC: specify BA threshold used for this ranking and regenerate from a pinned export snapshot).

- Top-100 high-affinity lncRNAs show a strong enrichment in human entries (79/100), consistent with the larger human regulation set in the current snapshot.
- The derived high-affinity subnetwork contains 2,610 nodes (550 lncRNAs and 2,060 target genes) and 8,871 edges (CSV summary; see `docs/paper/results_summary.md`).

**Figure 1.** Binding affinity distribution and summary statistics (caption TBC).  
`notebooks/figures/01_ba_distribution_analysis.png`

**Figure 2.** Top lncRNAs visualization (targets and affinity summaries; caption TBC).  
`notebooks/figures/02_top_lncrnas_visualization.png`

**Figure 3.** Centrality analysis of the derived regulatory subnetwork (caption TBC).  
`notebooks/figures/03_centrality_analysis.png`

**Figure 4.** Regulatory network visualization (subnetwork; caption TBC).  
`notebooks/figures/04_regulatory_network_visualization.png`

### Cross-species conservation patterns (TBC)

We provide orthology-aware network comparison and conservation stratification across species. The finalized manuscript should report:

1. definitions for conserved nodes/edges (e.g., core_id-level mapping rules);
2. conservation distribution across 1–4 species;
3. robustness to BA thresholds and orthology filtering.

### Epigenomic context for regulatory relationships (TBC)

We support mapping ChIP-seq peaks and other genomic features to gene-associated regions to contextualize regulatory edges. The finalized manuscript should report:

1. mark enrichment near target genes or lncRNAs (region definitions, flanking size);
2. bivalent domain identification strategy;
3. representative case studies (genes/lncRNAs) with IGV views.

---

## Methods (working draft)

### Database schema and implementation

Human LncRNA Atlas is implemented as a FastAPI backend with a PostgreSQL database (SQLAlchemy ORM) and a React-based web frontend. The schema organizes:

- multi-species gene records (`species`, `genes`) linked by orthology groups (`core_genes`, via `genes.core_id`);
- regulatory edges (`regulations`) and per-edge sequences (`sequences`, 1:1 with `regulations`);
- GWAS trait associations (`traits`, `ontologies`, `trait_gene_associations` at the `core_id` level);
- epigenomic datasets, including generalized feature tracks (`feature_tracks`, `genomic_features`) and ChIP-seq-specific tables (`epigenetic_mark_types`, `chipseq_experiments`, `chipseq_peaks`, `gene_peak_associations`).

See `docs/paper/data_dictionary.md` for a concise mapping between tables and analysis fields.

### Regulatory relationship ingestion (lncRNA → target)

Regulatory relationships are imported from tab-separated source files via ETL scripts under `etl/` (TBC: cite the upstream prediction method and its version). Each imported record links an lncRNA gene and a target gene within the same species, stores genomic coordinates for the predicted target region, and records a binding-affinity score (`binding_affinity`, derived from the input field `Best_Site_BA`).

Sequences associated with each regulation are imported into `sequences` and linked by `regulation_id` (1:1).

### Cross-species mapping (orthology)

Cross-species comparison is enabled by mapping species-specific genes to shared orthology groups (`core_id`). Analyses that quantify conservation should explicitly define:

1. how lncRNAs and protein-coding genes are mapped to `core_id` (source dataset/version, filtering);
2. the definition of node/edge conservation across 2–4 species;
3. sensitivity to orthology ambiguity and missing mappings (`core_id = NULL`).

### Network construction and filtering

Regulatory networks are modeled as directed edges from lncRNA genes to target genes. Edge weights can be defined using binding affinity and filtered by user-defined thresholds. For reproducible analyses, all figures and tables should be generated from exported snapshots with recorded parameters and commit SHA.

### Cross-species mapping and conservation

Cross-species comparison is performed by mapping genes to core_id (orthology groups). Conservation can be defined at the node or edge level. Sensitivity analyses should quantify the impact of orthology mapping quality and BA cutoffs.

### Epigenomic mapping and multi-track context

ChIP-seq peaks are stored with experiment metadata and can be associated to genes via precomputed gene–peak associations (promoter/gene body/upstream relationships). Other genomic feature tracks (e.g., repeats) are stored in a generalized feature table.

For epigenomic analyses in the finalized manuscript, define:

- the region model for associating peaks to genes/lncRNAs (e.g., promoter window and flanking size);
- peak filtering rules (e.g., q-value thresholds, per-mark configs);
- the operational definition for bivalent domains (e.g., co-occurrence of H3K27me3 and H3K4me3 within a window).

### Reproducible analysis workflow

The repository provides analysis notebooks under `notebooks/` and stores pre-generated outputs under `notebooks/results/` and `notebooks/figures/`. A lightweight, dependency-free summary of the CSV outputs can be generated via:

```bash
python3 scripts/paper/generate_results_summary.py
```

---

## Data and Code Availability

- **Code**: this repository (commit SHA should be pinned for submission).
- **APIs**: FastAPI OpenAPI at `GET /docs` when the backend is running.
- **Notebooks**: `notebooks/` contains analysis notebooks and pre-generated outputs referenced in this draft.

---

## Limitations

1. Orthology mapping uncertainty can affect conservation conclusions; the mapping source, filters, and sensitivity analyses must be reported.
2. Epigenomic coverage is not uniform across marks/cell types/species; cross-species comparisons should be restricted to comparable subsets and stated explicitly.
3. Network-level conclusions may be sensitive to binding-affinity thresholds and filtering; analyses should report threshold choices and robustness.

---

## Acknowledgements (placeholder)

TBC.

## References (placeholder)

TBC (recommend: maintain `references.bib` and use Pandoc/LaTeX for final formatting).
