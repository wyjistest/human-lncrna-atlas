# Submission Snapshot Freeze

This note records the paper-facing submission freeze decisions that are no longer treated as draft alternatives.

## Scope

- Manuscript: `docs/paper/manuscript.md`
- Figure plan: `docs/paper/figures.md`
- Paper entry note: `docs/paper/README.md`
- Repository status source: `docs/CURRENT_STATUS.md`

## Generated Figure Provenance

Batch-1 figure assets under `paper_figures/` record generation provenance with
two explicit metadata fields:

- `generated_at`: UTC timestamp for the asset generation event
- `source_commit`: git revision used as the frozen source context for that generation run

Interpretation rule:

- `source_commit` is **not required** to match the later commit that adds regenerated
  SVG / PNG / TSV files back into the branch
- when a paper-facing freeze needs deterministic provenance, regenerate with
  `python3 scripts/paper/generate_batch1_figures.py --generated-at <UTC> --source-commit <git-ref>`

Cell Genomics benchmarking package rule:

- `scripts/paper/generate_cellgenomics_validation.py` consumes frozen Figure 5D, Supplementary Figure 7, Supplementary Table 1, and compact processed external evidence TSVs
- `scripts/paper/rebuild_cellgenomics_package.py --skip-manuscript` is the single reviewer-facing rebuild entrypoint for Figure 3E, atlas-wide Figure 6, Supplementary Data, known-evidence benchmark, and manifest outputs
- reviewer traceability is recorded in `paper_figures/cell_genomics_manifest.tsv`
- external evidence provenance is recorded in `paper_figures/cell_genomics_external_data_manifest.tsv`
- Figure 6B summarizes PCG target-program expression context; missing or ambiguous lead-lncRNA aliases are reported as missing or ambiguous rather than zero expression
- Figure 3E and Supplementary Figure 7 target-permutation null summaries use 1,000 permutations with `rng_seed=42`
- Supplementary Figure 7D adds a degree-bin matched target-permutation null preserving lncRNA row-degree tiers and target row-degree tiers within species

Figure 2B label rule:

- `docs/paper/fig2b_aliases.tsv` is the paper-facing alias manifest for top hub labels
- the current batch-1 draft fills this manifest with neutral `Hub-XX (short accession)` labels rather than inventing human gene-like names
- if `display_label` is blank, Figure 2B falls back to the automatic shortened accession label
- if `display_label` is non-empty, its `reference_accession` must match the current hub accession for that `lncrna_core_id`

Figure 2A / conservation-matrix count check:

- the upstream frozen marmoset LongTarget prediction input contains approximately `50,000` candidate rows, reflecting upstream pipeline coverage rather than a plotting or export cap
- after restricting to non-null binding affinity and orthology-mappable edges for the conservation matrix, `31,798` marmoset species-edge rows entered the marmoset-edge-count downsampling sensitivity

Figure 2C label rule:

- the centrality scatter remains ordered by eigenvector-centrality-first summaries, but the main-text draft labels only the top five rows of the current centrality ranking
- no extra out-degree-only labels are reintroduced unless the figure plan is revised again

## Epigenomic Inventory: Fixed Main-Text Rule

The main-text epigenomic baseline is fixed to:

- **Eight core histone marks**:
  - `H3K27me3`
  - `H3K4me3`
  - `H3K4me2`
  - `H3K4me1`
  - `H3K27ac`
  - `H3K36me3`
  - `H3K9ac`
  - `H3K9me3`
- **DNase-HS**

The following tracks are **not part of the main-text baseline**:

- `CTCF`
- `H4K20me1`

They remain available in the current human database snapshot as **extended human tracks** and may appear in Supplementary material only if explicitly labeled as such.

## Frozen Counts for the Paper Baseline

Derived from the current human epigenomic snapshot documented in `docs/CURRENT_STATUS.md`:

- **8 core histone marks**: `49` experiments, `3,343,903` peaks
- **DNase-HS**: `7` experiments, `1,223,622` peaks
- **Combined paper-facing baseline**: `56` experiments, `4,567,525` peaks

Extended tracks excluded from the main-text baseline:

- **CTCF**: `5` experiments, `248,106` peaks
- **H4K20me1**: `3` experiments, `109,285` peaks
- **Combined excluded extended inventory**: `8` experiments, `357,391` peaks

## Comparable Cell-Line Subset: Fixed Main-Text Rule

Cross-mark comparison panels in the main text default to the following six human cell lines:

- `A549`
- `GM12878`
- `H1-hESC`
- `HepG2`
- `HMEC`
- `K562`

`MCF-7` is **excluded from main-text multi-mark comparisons** because the frozen hg19 baseline does not provide comparable eight-mark coverage there. In the current snapshot, `MCF-7` contributes only `H3K4me3` within the core baseline and therefore may be used for:

- inventory reporting;
- single-mark browsing;
- Supplementary notes that explicitly acknowledge sparse coverage.

## Wording Rules

Use the following rules consistently across the paper package:

1. Main text: `8 core histone marks + DNase-HS`
2. Extended tracks: refer to `CTCF` and `H4K20me1` separately as extended human tracks
3. Figure 4 / Table 2: use the fixed six-cell-line subset for cross-mark comparisons
4. Do not describe `CTCF` or `H4K20me1` as part of the core baseline totals
5. Do not revert to phrases such as “unless the submission snapshot states otherwise” for the epigenomic inventory

## Orthology Provenance: Fixed Paper Rule

The paper does **not** claim an external orthology release version that is not preserved in the repository. The fixed manuscript wording is:

- cross-species mapping is based on the repository-frozen import tables `ortholog_lnc_table.csv` and `ortholog_gene_table.csv`;
- these tables are imported through `etl/import_ortholog_data.py` **v1.0** dated **2025-11-20**;
- imported rows generate shared `core_id` assignments recorded with `assignment_source = 'ortholog_table'`.

Normalization rules fixed for the paper:

- `CATG...` identifiers are converted to numeric `core_id` values after removing version suffixes;
- `ENSG...` identifiers are converted in the same way, then offset by `500000000` to avoid collisions with `CATG` numeric ranges;
- when multiple species share a `core_id`, the import prefers the human row when choosing the canonical symbol or human reference identifier.

The manuscript should therefore describe orthology provenance as a **repository-frozen ortholog import snapshot**, not as a separately versioned external orthology release.

## Conservation Definitions: Fixed Paper Rule

### Node conservation

Node conservation is defined at the `core_id` level using species presence in the `genes` table.

- input: `genes.core_id` with non-null `core_id`
- species order: human (`1`), chimpanzee (`2`), macaque (`3`), marmoset (`4`)
- conservation label: a 4-bit string such as `1110`
- conservation count: the number of species in which that `core_id` is present

### Conserved edge

Conserved candidate lncRNA–PCG edges are defined at the **core-pair** level:

- edge key: `(lncrna_core_id, target_core_id)`
- a species contributes presence for that edge if there is at least one regulation linking any gene with `lncrna_core_id` to any gene with `target_core_id` in that species
- edge conservation label: the same fixed 4-bit species order used for node conservation
- edge conservation count: the number of distinct species in which the core pair is observed

Exclusion rule:

- genes with `core_id = NULL` are excluded from cross-species node and edge conservation analyses

Interpretation rule:

- node conservation and edge conservation must be reported separately
- edge conservation is the primary definition for Figure 3 and related rewiring claims

## Binding-Affinity Strategy: Fixed Paper Rule

The manuscript uses a fixed two-tier BA strategy rather than a single threshold for every figure.

### Tier 1: All-edge conservation overview

Used for Figure 3 conservation / rewiring overview.

- source workflow: `notebooks/02_conservation_patterns.ipynb`
- export route: `GET /api/v1/export/conservation`
- fixed filter: `min_species_count >= 2`
- BA rule: **no additional BA cutoff**

### Tier 2: High-affinity prioritization

Used for high-affinity network summaries and epigenomic-overlap prioritization.

- high-affinity workflow: `notebooks/01_high_affinity_analysis.ipynb`
- overlap workflow: `notebooks/03_epigenetic_marks.ipynb`
- export routes:
  - `GET /api/v1/export/high-affinity`
  - `GET /api/v1/export/chipseq-overlaps`
- fixed BA rule: **`BA >= 100`**

### Disease / trait-centered subnetworks

The current disease notebook uses `GET /api/v1/export/disease-network` without an explicit BA threshold.

- current export behavior: no hard BA filter; regulation edges are ordered by `binding_affinity DESC`
- fixed paper interpretation: treat BA as a **ranking feature** in the current disease-network workflow, not as a hidden hard inclusion threshold


## Submission package checklist

Before a submission build is finalized, the paper package should be checked for the following manuscript-facing invariants:

1. orthology provenance is described as the repository-frozen import snapshot;
2. conserved-edge claims use the `(lncrna_core_id, target_core_id)` core-pair rule;
3. Figure 3 keeps the fixed all-edge overview with `min_species_count >= 2` and no additional BA cutoff;
4. high-affinity prioritization and epigenomic-overlap summaries use `BA >= 100` only as the prioritization tier;
5. the main-text epigenomic baseline remains `8 core histone marks + DNase-HS`;
6. cross-mark main-text comparisons remain restricted to `A549`, `GM12878`, `H1-hESC`, `HepG2`, `HMEC`, and `K562`;
7. abstract, tables, legends, and manuscript prose all use the same frozen snapshot counts.
8. Figure 3 includes the compact observed-vs-null calibration summary in the main-text figure, with full BA sensitivity and pairwise null details retained in Supplementary Figure 7.
9. Figure 3E and Supplementary Figure 7 null summaries use 1,000 permutations with random seed 42, including the Supplementary Figure 7D degree-bin matched null sensitivity layer.
10. Figure 6 remains benchmarking / contextualization only and must preserve candidate-prioritization language.
11. Figure 6A is atlas-wide across top prioritized, conserved, rewired, and obesity flagship modules; Figure 6D keeps the obesity case as representative.
12. expression mapping uses PCG target-program mappable subset wording and must not treat missing or ambiguous lncRNA aliases as zero expression.

## Remaining Items Outside This Freeze

The following items still require independent paper-level freezing, but they are outside the epigenomic inventory decision captured here:

- final figure panel exports and legend wording
- final commit SHA for the submission package
- final GitHub release and Zenodo/Figshare DOI
