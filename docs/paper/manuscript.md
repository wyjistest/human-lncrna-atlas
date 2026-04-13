# Orthology-aware, triplex-informed lncRNA regulatory networks reveal conserved and rewired trait-associated gene programs across primates

**Article type:** Research Article

**Species:** Human (*Homo sapiens*), Chimpanzee (*Pan troglodytes*), Macaque (*Macaca mulatta*), Marmoset (*Callithrix jacchus*)

**Genome assemblies (IGV):** hg19, panTro5, rheMac10, calJac3

> Author note: This draft has been reframed as a research-first manuscript. All quantitative summaries, figure panels, tables, and legends must be regenerated from a single frozen submission snapshot before submission.
>
> The paper-facing freeze rules for epigenomic inventory, orthology provenance, conserved-edge definition, and binding-affinity strategy are fixed in `docs/paper/submission_snapshot.md`. Remaining package-level freeze items are the final commit SHA and final figure-panel / legend exports.

---

## Abstract

Trait-associated lncRNA and protein-coding gene catalogs are informative, but they do not by themselves specify candidate regulatory edges or explain how trait-linked programs are conserved or rewired across species. Existing lncRNA atlases resolved transcript boundaries, expression patterns, and trait-linked catalogs, yet systematic integration of cross-species orthology, predicted lncRNA to protein-coding gene edges, and epigenomic context remains limited.

Here we map orthologous lncRNAs and protein-coding genes across human, chimpanzee, macaque, and marmoset, and use triplex-informed inference to reconstruct candidate lncRNA regulatory edges that can be compared across primate evolution. The frozen working snapshot contains **804,630** predicted lncRNA to protein-coding gene relationships across four primate species.

For the paper package, epigenomic context is fixed to ENCODE DNase-HS plus eight core histone marks (`H3K27me3`, `H3K4me3`, `H3K4me2`, `H3K4me1`, `H3K27ac`, `H3K36me3`, `H3K9ac`, and `H3K9me3`). This baseline comprises **49 histone-mark experiments** and **3,343,903 histone peaks**, together with **7 DNase-HS experiments** and **1,223,622 DNase peaks**, for a combined main-text baseline of **56 experiments** and **4,567,525 peaks** across seven human cell lines. `CTCF` and `H4K20me1` remain available only as extended human tracks outside the main-text baseline.

Across these networks, we prioritize hub lncRNAs, modular target gene programs, conserved regulatory cores, and lineage-specific rewiring patterns that are not visible from trait-associated gene lists alone. We further use epigenomic context to prioritize candidate regulatory loci and trait-centered subnetworks, while treating these layers as contextual support rather than causal proof.

The resulting study reframes prior trait-associated lncRNA and protein-coding gene catalogs as orthology-aware, triplex-informed candidate regulatory networks across primates. A companion web resource and programmatic APIs provide interactive access to the reconstructed networks, genome-browser views, and downstream exports for reproducible follow-up analyses.

**Keywords:** lncRNA, triplex, orthology, regulatory network, conservation, rewiring, primate, GWAS, epigenomic context

---

## Introduction

Long non-coding RNAs (lncRNAs) regulate transcriptional and post-transcriptional programs through diverse mechanisms, yet mechanistic interpretation still lags behind cataloging. Lists of lncRNAs, expression atlases, and trait-associated genes are useful starting points, but they do not directly define which candidate regulatory edges should be compared across species or prioritized for perturbation experiments.

This limitation is especially relevant for trait-linked biology. Trait-associated lncRNA and protein-coding gene collections can nominate disease-relevant components, but without explicit lncRNA to target-gene edges they remain difficult to organize into coherent regulatory programs. Cross-species comparison adds another layer of value by distinguishing conserved regulatory cores from lineage-specific rewiring, but such analyses require orthology-aware mapping at both node and edge levels.

Triplex-informed prediction provides a principled bridge from catalogs to candidate regulatory networks. By combining ortholog mapping with sequence-based inference of lncRNA DNA-binding motifs and candidate binding sites, we can move from trait-associated node lists to explicit lncRNA to protein-coding gene candidate edges that are comparable across primates.

In this study, we position the web platform as a secondary delivery layer rather than the primary claim. The central contribution is the reconstruction of orthology-aware, triplex-informed, epigenomically contextualized candidate lncRNA regulatory networks across four primate species, and the use of these networks to reveal conserved modules, lineage-specific rewiring, and trait-centered candidate regulators.

---

## Results

### 1. Constructing orthology-aware, triplex-informed lncRNA regulatory networks from prior trait-associated gene catalogs

The study begins with a conceptual gap: prior trait-associated lncRNA and protein-coding gene catalogs nominate relevant genes, but do not specify the lncRNA to protein-coding gene edges needed for network-level interpretation. We therefore restructure the manuscript around a workflow that maps orthologous lncRNAs and protein-coding genes across four primates, applies triplex-informed inference to reconstruct candidate regulatory edges, and organizes the resulting edges into cross-species comparable networks.

The working repository snapshot already supports four-species coverage for orthology-aware network reconstruction. Orthology provenance for the paper is fixed to the repository-frozen import tables `ortholog_lnc_table.csv` and `ortholog_gene_table.csv`, imported through `etl/import_ortholog_data.py` v1.0 (2025-11-20) and normalized into shared `core_id` groups. All numeric summaries shown in the main figures should be generated from that frozen snapshot rather than copied across README, notebook, and status documents.

**Figure 1.** From prior trait-associated gene catalogs to orthology-aware candidate regulatory edges across primates.
Recommended content: conceptual gap, workflow schematic, four-species scope, and frozen-snapshot data overview.

### 2. Global network architecture identifies hub lncRNAs and modular target gene programs

After the construction workflow is established, the manuscript can summarize the global organization of the inferred networks. This section should consolidate binding-affinity distributions, target-count summaries, hub lncRNA rankings, centrality metrics, and readable subnetworks into a single coherent overview of network architecture.

This is the correct place for the current high-affinity and centrality analyses. Those outputs remain useful, but they no longer define the opening claim of the manuscript. Instead, they support a second-stage result: once candidate edges are reconstructed, the global network architecture identifies lncRNAs with broad target coverage, modular structures that organize target gene programs, and filtered subnetworks suitable for biological interpretation.

**Figure 2.** Global architecture of primate lncRNA regulatory networks.
Current source material: `notebooks/figures/01_ba_distribution_analysis.png`, `notebooks/figures/02_top_lncrnas_visualization.png`, `notebooks/figures/03_centrality_analysis.png`, and `notebooks/figures/04_regulatory_network_visualization.png` should be reorganized into a research-first figure or redistributed between the main text and Supplementary material.

### 3. Conserved and rewired lncRNA regulatory edges across primate evolution

Cross-species comparison should be framed primarily at the edge level, not only at the node level. Orthologous lncRNAs and protein-coding genes can be conserved without preserving the same lncRNA to target-gene connections, so the main claim of this section is the distinction between conserved regulatory modules and lineage-specific rewiring.

For the paper, node conservation and edge conservation are fixed as separate definitions. Node conservation is computed from `genes.core_id` presence across the four species in the fixed order human, chimpanzee, macaque, and marmoset. Conserved regulatory edges are defined at the `(lncrna_core_id, target_core_id)` level: a species contributes presence if at least one regulation links that core pair in that species. Genes with `core_id = NULL` are excluded from cross-species conservation analyses. The main overview in Figure 3 should show only two- to four-species conserved-edge strata under the fixed all-edge workflow (`min_species_count >= 2`, no additional BA cutoff), while singleton edges are reported in Supplementary material. Species-pair sharing and representative examples of conserved versus lineage-specific modules should therefore be interpreted at the core-pair level rather than from node-only ortholog lists.

**Figure 3.** Cross-species conservation and lineage-specific rewiring of lncRNA regulatory edges.
Recommended content: conservation strata or UpSet-style overview, node versus edge conservation summary, species-pair heatmaps, and representative conserved and lineage-specific modules.

### 4. Epigenomic context prioritizes candidate regulatory loci and modules

Epigenomic data are most useful here as contextual support that helps prioritize candidate regulatory loci and modules. This section should summarize histone-mark and DNase context around predicted loci, compare mark compositions across candidate modules, and highlight representative regions in IGV snapshots. Unless a matched background model and enrichment workflow are frozen for submission, the text should use conservative language such as overlap, context, or co-localization rather than causal or over-strong enrichment claims.

For the main text, the epigenomic inventory is fixed to `8 core histone marks + DNase-HS`, while `CTCF` and `H4K20me1` remain excluded from the core baseline and may appear only as explicitly labeled extended human tracks. Cross-mark comparisons in Figure 4 and related tables default to the six-cell-line subset `A549`, `GM12878`, `H1-hESC`, `HepG2`, `HMEC`, and `K562`; `MCF-7` is excluded from multi-mark main-text comparisons because the frozen hg19 baseline only contributes `H3K4me3` there.

**Figure 4.** Epigenomic context for candidate regulatory loci and modules.
Recommended content: mark-overlap summary, direct mark-overlap signatures or mark-combination comparisons, bivalent versus non-bivalent contrasts, and representative IGV snapshots.

### 5. Trait-centered subnetworks prioritize candidate disease-relevant lncRNAs

Trait-associated biology should be presented through tripartite subnetworks that connect trait terms to lncRNAs and protein-coding genes through the reconstructed candidate regulatory edges. This framing turns gene lists into interpretable programs and allows integrated prioritization of candidate lncRNAs using trait coverage, conservation, network centrality, and epigenomic context.

The strongest version of this section should combine one flagship trait case study with a cross-trait summary that distinguishes shared regulators from trait-specific ones. The flagship tripartite network should remain visually simple, using at most two quantitative encodings in the network view, while additional evidence layers such as conservation and epigenomic support are summarized in the ranking matrix. The emphasis should remain on prioritization and interpretation rather than on claiming direct validation.

**Figure 5.** Trait-centered subnetworks highlight candidate functional lncRNAs.
Recommended content: trait to lncRNA to protein-coding gene tripartite network, integrated ranking, shared versus trait-specific regulator summary, and one or two representative case studies.

### 6. Web resource and programmatic access

The platform remains valuable, but it is now positioned as supporting infrastructure rather than the first result. If the target journal strongly favors resource papers, this section and its corresponding figure can stay in the main text. For research-first submissions, the same material should move to Supplementary or Extended Data.

The web layer supports filtered regulation queries, network visualization, genome-browser inspection, and exportable downstream analyses. Example endpoints currently exposed by the backend include `GET /api/v1/regulations`, `GET /api/v1/network/gene/{id}`, `GET /api/v1/network/compare`, and `GET /api/v1/export/*`.

**Figure 6.** Web resource and programmatic access (optional main-text figure).
Recommended placement: main text only for resource-oriented submissions; otherwise Supplementary / Extended Data.

---

## Discussion

This manuscript should be read primarily as a study of network reconstruction and comparative regulatory organization, not as a platform description. The main advance is the conversion of prior trait-associated lncRNA and protein-coding gene catalogs into orthology-aware, triplex-informed candidate regulatory edges that can be compared across primates.

Within that framework, two biological interpretations matter most. First, conserved modules point to regulatory programs that may persist despite primate divergence. Second, lineage-specific rewiring highlights where trait-associated regulatory relationships may have been remodeled during evolution. These two signals should be discussed together rather than treated as competing interpretations.

Epigenomic context strengthens prioritization by identifying candidate loci with compatible chromatin environments, but it does not by itself prove regulation. The text should remain explicit that the current evidence chain is predictive and contextual, and that perturbation-based validation remains outside the present scope.

The main limitations are also clear. Orthology mapping uncertainty can alter both node- and edge-level conservation. Triplex-informed edges remain predictions rather than experimentally validated interactions. Epigenomic datasets are uneven across marks, cell lines, and species, and may not match the cell states relevant to each trait-centered subnetwork. Future work should therefore focus on frozen cross-species snapshots, explicit sensitivity analyses, and experimental follow-up through perturbation or direct triplex assays.

---

## Methods

### 1. Source datasets and frozen submission snapshot

The final manuscript must pin a single submission snapshot covering the database export timestamp, repository commit SHA, notebook outputs, and figure/table inputs. No quantitative summary should be copied from mixed documentation sources after this freeze point.

### 2. Trait-associated lncRNA and protein-coding gene collection

Describe the exact upstream trait-associated catalogs used to seed the analysis and specify how lncRNAs and protein-coding genes were carried forward into the network reconstruction workflow. Until that source chain is finalized, the manuscript should use the conservative phrase *prior trait-associated lncRNA and protein-coding gene catalogs* rather than over-committing to a single intermediate table name in the main claim.

### 3. Ortholog mapping across four primates

Cross-species comparison in this paper is fixed to the repository-frozen ortholog import snapshot rather than an external orthology release version that is not preserved in the repo. The import expects `ortholog_lnc_table.csv` and `ortholog_gene_table.csv`, normalizes CATG / ENSG identifiers into shared `core_id` values, applies a `500000000` offset to ENSG-derived core IDs to avoid collisions, and prefers the human row when assigning canonical symbols or human reference identifiers. Genes lacking usable `core_id` values are excluded from cross-species conservation analyses.

### 4. Triplex-informed prediction and filtering

Candidate lncRNA to protein-coding gene edges are reconstructed using triplex-informed inference. The imported edge weight is `binding_affinity` derived from the source `Best_Site_BA` field. The paper uses a fixed two-tier BA strategy: Figure 3 conservation / rewiring overview uses all orthology-mappable edges with `min_species_count >= 2` and no additional BA cutoff, whereas high-affinity network summaries and epigenomic-overlap prioritization analyses use `BA >= 100`.

### 5. Network construction and graph analyses

Regulatory networks are represented as directed lncRNA to target-gene edges. This section should define how edge weights, hub rankings, centrality metrics, module detection, and readable subnetworks are generated from the frozen snapshot.

### 6. Conservation and rewiring metrics

Node conservation and edge conservation are defined separately. Node conservation uses `genes.core_id` presence across species to generate a 4-bit label and species count. Edge conservation uses the `(lncrna_core_id, target_core_id)` core pair, with species presence defined by at least one regulation linking that pair in a species. Rewiring claims should therefore be framed as changes in core-pair presence across species, not merely as differences in node presence.

### 7. Epigenomic overlap or enrichment analyses

This section must state the fixed mark inventory, comparable cell-line subset, region definitions for associating peaks to lncRNAs or target genes, peak-level filtering rules, and the operational definition of bivalent domains. The paper-facing baseline is fixed to `8 core histone marks + DNase-HS` (`56` experiments, `4,567,525` peaks), with `CTCF` and `H4K20me1` labeled separately as extended current-snapshot tracks.

Main-text cross-mark comparisons should default to the six-cell-line subset `A549`, `GM12878`, `H1-hESC`, `HepG2`, `HMEC`, and `K562`. `MCF-7` may still appear in inventory reporting or single-mark browser views, but not in the main-text multi-mark comparison panels.

### 8. Visualization platform and reproducibility

The repository provides analysis notebooks under `notebooks/` and pre-generated outputs under `notebooks/results/` and `notebooks/figures/`. A lightweight summary of CSV outputs can be regenerated with:

```bash
python3 scripts/paper/generate_results_summary.py
```

See `docs/paper/data_dictionary.md` for a concise mapping between tables and analysis fields.

---

## Data and Code Availability

- **Code**: this repository; the final submission must pin the exact commit SHA used for exported analyses and figures.
- **APIs**: FastAPI OpenAPI at `GET /docs` when the backend is running.
- **Notebooks**: `notebooks/` contains the analysis notebooks and intermediate outputs referenced by the figure plan.
- **Exports**: all tables and figures in the final manuscript should be traceable to the frozen submission snapshot described above.

---

## Submission Freeze Checklist

Before submission, the manuscript package must unify the following items across the abstract, main text, figures, tables, legends, and Supplementary information:

1. the exact orthology source and version;
2. the operational definition of conserved edges and rewiring;
3. the binding-affinity cutoff strategy used in each analysis;
4. the epigenomic mark inventory and comparable cell-line subset;
   fixed rule: main text uses `8 core histone marks + DNase-HS` (`56` experiments, `4,567,525` peaks), with `CTCF` / `H4K20me1` excluded from the core baseline and `MCF-7` excluded from multi-mark comparison panels;
5. the orthology and conservation definitions;
   fixed rule: repository-frozen ortholog import tables define `core_id`, node conservation is `core_id` presence, and conserved edges are `(lncrna_core_id, target_core_id)` core pairs across species;
6. the binding-affinity strategy used in each analysis;
   fixed rule: Figure 3 uses all edges with `min_species_count >= 2`; high-affinity and overlap-prioritization analyses use `BA >= 100`; current disease-network exports use BA as ranking, not as a hidden hard threshold;
7. the final snapshot counts used in abstract, tables, and figure legends.

---

## References (placeholder)

TBC. Recommended workflow: maintain `references.bib` and render via Pandoc / LaTeX in the final submission pipeline.
