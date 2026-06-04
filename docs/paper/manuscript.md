---
bibliography: docs/paper/references.bib
csl: docs/paper/cell.csl
link-citations: true
---

# Triplex-informed lncRNA–gene candidate networks reveal edge-level conservation and rewiring across primates

## Abstract

Trait-associated lncRNA and protein-coding gene catalogs nominate molecular nodes but rarely resolve candidate lncRNA–PCG edges or their evolutionary stability. Here, we integrate orthology of primate lncRNAs and protein-coding genes (PCGs) with triplex-informed RNA–DNA interaction prediction to reconstruct **804,630** candidate lncRNA–PCG edges across human, chimpanzee, macaque, and marmoset. Cross-species comparison shows that **node conservation is not edge conservation**: human-chimpanzee similarity was high for orthologous nodes (Jaccard **0.79**) but lower for candidate edges (Jaccard **0.37**). Nevertheless, **8,799** core-pair edges were observed in all four species, far exceeding target-permutation expectations (null mean **91.4**; empirical p < 0.001). Human epigenomic context, PCG target-program expression, Gene Ontology (GO)-based module-coherence benchmarking, and trait-gene provenance further contextualize candidate modules, including trait-centered lncRNA nominations for follow-up. We provide a frozen, reproducible analysis snapshot and the **Human LncRNA Atlas Companion**, a local-only analysis interface for inspection and reuse. This atlas prioritizes conserved and rewired lncRNA–PCG hypotheses without establishing causal regulation.

**Keywords:** lncRNA, triplex, orthology, candidate lncRNA–PCG edge, conservation, rewiring, primate, GWAS, epigenomic context

## Introduction

Long non-coding RNAs (lncRNAs) regulate gene expression through chromatin-associated, transcriptional, post-transcriptional, and nuclear-organizational mechanisms, yet assigning regulatory targets and coherent functional programs to individual lncRNAs remains difficult [@statello2021; @mattick2023]. This interpretive gap is especially limiting for trait-associated biology, where node-level catalogs alone do not define the regulatory relationships needed for network analysis or perturbation prioritization.

Large-scale lncRNA and trait resources have substantially improved transcript annotation, disease association curation, and variant-to-trait mapping, including FANTOM CAT, GENCODE, LncBook 2.0, LncRNADisease v3.0, and the NHGRI-EBI GWAS Catalog [@hon2017; @frankish2021; @li2023; @lin2024; @cerezo2025]. However, these resources generally nominate lncRNAs, PCGs, loci, and traits rather than explicit orthology-aware candidate lncRNA–PCG edges that can be compared across primates.

RNA–DNA triplex formation provides a sequence-informed mechanism by which some lncRNAs can associate with genomic regions and distal regulatory elements [@mondal2015; @leisegang2024]. Computational triplex predictors therefore offer a principled route from cataloged lncRNAs to candidate genomic contacts and downstream lncRNA–PCG relationships, although these predictions remain hypothesis-generating rather than experimental confirmation [@buske2012; @he2015].

Cross-species analysis further requires orthology-aware mapping because lncRNA sequence, structure, and expression patterns can evolve rapidly relative to PCGs [@necsulea2014; @mattick2023]. Prior primate lncRNA orthology resources and RNA homology search frameworks motivate this strategy, but regulatory conservation must still be evaluated at the edge level rather than inferred from node presence alone [@bryzghalov2020; @nawrocki2013; @harrison2024].

Here we reconstruct orthology-aware, triplex-informed candidate lncRNA–PCG edge networks across four primate species and use them to analyze network architecture, edge-level conservation and rewiring, epigenomic context, and trait-centered candidate prioritization. The **Human LncRNA Atlas Companion** is positioned as a local-only reproducibility and evidence-inspection layer rather than as the primary claim of the study.

## Results

### 1. Constructing orthology-aware, triplex-informed candidate lncRNA–PCG edge networks from prior trait-associated gene catalogs

We addressed the node-only structure of prior trait-associated catalogs by reconstructing a candidate lncRNA–PCG edge layer across human, chimpanzee, macaque, and marmoset. Species-specific lncRNAs and PCGs were normalized into shared orthologous `core_id` groups, which enabled candidate lncRNA–PCG relationships to be compared at the core-pair level across species. Triplex-informed inference was then used to nominate candidate lncRNA–DNA contacts and downstream lncRNA–PCG edges.

The frozen analysis snapshot comprises **804,630** predicted lncRNA–PCG relationships across four primate species, together with a main-text human-only epigenomic baseline of **56** experiments and **4,567,525** peaks. This reconstruction reframes prior trait-associated lncRNA and PCG lists as cross-species comparable candidate edge networks rather than disconnected nodes. The overall workflow and frozen snapshot are summarized in Figure 1.

### 2. Global network architecture prioritizes hub lncRNAs and modular target gene programs

We next summarized the architecture of the reconstructed networks using binding-affinity distributions, target-core coverage, hub rankings, eigenvector centrality, and readable filtered subnetworks. Edges with BA ≥ 100 ranged from **2.9%** (macaque) to **5.7%** (human), indicating that high-affinity candidate relationships represent a focused prioritization layer rather than the full network.

Ranking lncRNAs by unique target-core breadth prioritized a small set of candidate broad hubs spanning approximately **300–540** target core groups in the frozen analysis snapshot, while eigenvector centrality separated broadly connected hubs from network-central organizers. Readable subnetwork extraction further showed that these quantitative summaries map onto compact candidate modules rather than dense whole-network visualizations. These global architecture patterns are summarized in Figure 2.

### 3. Conserved and rewired candidate lncRNA–PCG edges across primates

We treated candidate edge conservation as an edge-level property rather than a node-level property. Conserved candidate lncRNA–PCG edges were defined as `(lncrna_core_id, target_core_id)` core pairs, with species presence assigned when at least one predicted relationship linked the corresponding core pair within a species. Under the fixed all-edge overview rule (`min_species_count >= 2`, no additional BA cutoff), the frozen snapshot contains **8,799** candidate edge core pairs observed in all four species, **22,749** three-species shared core-pair edges, and **42,955** two-species shared core-pair edges.

Pairwise comparisons showed that node-level similarity is substantially higher than edge-level similarity. For example, human-chimpanzee sharing was high at the node level (Jaccard **0.79**) but much lower at the edge level (Jaccard **0.37**), and chimpanzee-macaque sharing showed the same pattern (node Jaccard **0.82** versus edge Jaccard **0.27**). Node-level sharing is informative context, whereas edge-level sharing is the primary comparative readout for conservation and rewiring in this study. These contrasts indicate that orthologous nodes can be broadly retained while candidate lncRNA–PCG edges are lost, gained, or rewired.

Figure 3E moves the compact observed-vs-null calibration into the main figure: after 1,000 target-permutation iterations, the observed four-species stratum remained well above both the matched-null mean and the interpolated 95th-percentile null bound (**8,799** observed core-pair edges versus a null mean of **91.4** and an interpolated null p95 of approximately **107**; empirical p < 0.001 across 1,000 permutations).

A degree-bin matched target-permutation null is reported in Supplementary Figure 7D to assess whether the signal persists under a stricter rewiring baseline; in that analysis, the four-species observed count remained above the degree-bin matched null p95 (**118**). A marmoset-edge-count random downsampling sensitivity in Supplementary Figure 7E further restricted human, chimpanzee, and macaque species-edge rows to the marmoset edge count and recomputed four-species sharing across 1,000 random draws; the observed median remained **228** shared core-pair edges (p05-p95 **203-254**) versus a matched target-permutation null p95 of **7**, and the observed lower bound (p05 = 203) remained well above the matched null p95 of 7. Supplementary Figure 7 retains the complete BA sensitivity tiers, pairwise target-permutation null details, degree-bin matched null, and marmoset coverage sensitivity. Paired conserved and rewired exemplars in Figure 3 therefore illustrate how the same comparative framework captures both persistent candidate core-pair patterns and lineage-specific candidate rewiring patterns without treating the robustness layer as direct functional evidence.

### 4. Human epigenomic context stratifies candidate loci

We next evaluated whether candidate loci reside in interpretable chromatin contexts using a frozen human-only epigenomic context layer of eight core histone marks plus DNase I hypersensitive sites (DNase-HS) [@moore2020; @roadmap2015]. Cross-mark summaries in the fixed six-cell-line subset identified **26 of 54 possible cell-line x mark combinations** as observed and **28** unavailable combinations as `NA`, allowing true missing experiments to be separated from low-overlap measurements.

The most prevalent all-edge mark-overlap signatures in the frozen analysis snapshot were H3K36me3 (**24.7%**), H3K9me3 (**14.5%**), and DNase-HS (**12.0%**), whereas high-affinity overlaps more frequently involved DNase-HS (**20.2%**) and H3K36me3 (**16.9%**). In Figure 4, BA ≥ 100 is used only as a prioritization zone within the human-only epigenomic context layer, not as a universal inclusion threshold. Direct context labeling further separated **13,764** active-like non-bivalent candidate observations from **2,400** bivalent-like observations, providing a chromatin-context stratification layer rather than causal evidence. Representative local epigenomic tracks in Figure 4 allow prioritized candidate loci to be inspected together with histone and DNase-HS signals.

### 5. Trait-centered subnetworks prioritize candidate trait-relevant lncRNAs

Finally, we reorganized trait-associated lncRNAs and PCGs into trait-centered candidate subnetworks. Trait-level flagship selection followed a fixed frozen rule based on unique lncRNA count, unique target gene count, and maximum BA, under which obesity ranked first in the frozen analysis snapshot. The within-trait flagship case then applied conserved-edge and non-other epigenomic-context filters before selecting the lead obesity-centered lncRNA example. In the frozen flagship example, the obesity-centered subnetwork displays **14** representative nodes and is associated with **188** candidate edges in the exported flagship subnetwork, demonstrating how disconnected trait-associated nodes can be reorganized into an interpretable lncRNA-centered module. Supplementary Table 1 summarizes literature-backed trait-gene context from the frozen trait-gene association layer across the prioritized traits and within the flagship obesity-centered module.

The integrated ranking matrix combines target coverage, binding-affinity summaries, high-affinity edge counts, conservation or rewiring labels, epigenomic context, and flagship-network membership. Its heatmap uses a column-normalized score for visualization, while binary or categorical evidence layers indicate class membership rather than continuous effect sizes. Top-ranked candidates in the frozen analysis snapshot included `RP11-356I2.4`, `CATG00000043927.1`, `CATG00000090178.1`, `CATG00000077557.1`, and `CATG00000035185.1`, while the focused obesity case study centers on `CATG00000045621.1` with **8** candidate targets and **8** high-affinity edges. Figure 5 and Supplementary Table 1 therefore provide a trait-centered prioritization view that layers candidate lncRNA ranking with literature-backed trait-gene context for downstream experimental follow-up rather than experimental confirmation of regulation.

### 6. External evidence layers benchmark and contextualize prioritized modules

We next used external evidence layers to benchmark and contextualize prioritized modules without treating these layers as experimental confirmation of the triplex-informed edge set. Figure 6 summarizes atlas-wide external evidence across **20** top-prioritized modules, **1,045** conserved modules, **1,993** rewired or species-specific modules, and the obesity flagship module while retaining a candidate/prioritization interpretation. Across the evaluated module classes, evidence layers were summarized separately for top-prioritized, conserved, rewired/species-specific, and obesity flagship modules, with the obesity module retained as a representative case rather than the sole evidence layer. Trait-gene provenance overlapped **626** of **940** obesity-linked target genes in the frozen trait layer, and **6** of the **8** displayed flagship targets carried literature-backed obesity context. These provenance overlaps anchor the target program without demonstrating that the lead lncRNA regulates those targets.

PCG target-program expression context was summarized as a mappable subset analysis using processed GTEx (Genotype-Tissue Expression) v8 median-expression summaries for the Figure 6B PCG targets, while ENCODE (Encyclopedia of DNA Elements) cell-line contexts are retained in the panel manifest for processed RNA-seq inputs when available. ENCODE and GTEx therefore serve as processed expression-context sources, not as direct evidence of lncRNA–PCG regulation. The lead lncRNA was left as missing when no reliable expression alias mapped to the processed matrix, so expression context evaluates the target program rather than direct lncRNA–PCG co-expression. Across GTEx adipose, liver, skeletal muscle, and blood contexts, the PCG target subset mapped at **100%** after restricting Figure 6B to the PCG target-program scope, with transcripts per million (TPM) ≥ 1 fractions ranging from **37.5%** in whole blood to **62.5%** in liver and skeletal muscle.

GO coherence benchmarking was performed with biological-process annotations and same-size, target-availability matched-null gene sets drawn from the high-affinity background. Figure 6C extends this readout to **11** module entries across top-prioritized, conserved, rewired, and obesity flagship classes; **1** of **11** exceeded its matched-null p95, and no module survived Benjamini-Hochberg false discovery rate (FDR) < 0.1. The displayed obesity target program showed limited module-level coherence, with an observed coherence score of **0.29** versus a matched-null mean of **0.22**, empirical p = **0.077**, and multi-module FDR = **0.846**. Figure 6 therefore benchmarks and contextualizes prioritized modules rather than experimentally confirming candidate lncRNA–PCG regulation.

## Discussion

This study converts prior trait-associated lncRNA and PCG catalogs from node lists into orthology-aware, triplex-informed candidate edge networks across primates. That edge layer is the main contribution of the manuscript and provides a basis for both within-species prioritization and cross-species comparative interpretation.

The comparative results suggest that edge-level conservation is more selective than node-level conservation: orthologous nodes can be broadly retained while their candidate lncRNA–PCG edges are lost, gained, or rewired. This pattern is consistent with the rapid evolution and context dependence of lncRNA biology [@necsulea2014; @mattick2023]. This is the conceptual advance of the study: node conservation is not edge conservation, and edge-level lncRNA–PCG conservation or rewiring can be used as a comparative edge-level signal. In parallel, hub breadth and network-centrality analyses prioritize a subset of lncRNAs that may organize broad candidate target programs and merit focused follow-up.

This edge-centered framing turns rewired modules into testable comparative hypotheses rather than descriptive species labels. In particular, lineage-specific edge gains or losses can be evaluated against trait-gene provenance, tissue expression context, chromatin state, and future perturbation or RNA–chromatin interaction assays to ask whether candidate edge rewiring is concentrated in phenotypically relevant target programs.

Epigenomic context stratifies candidate hypotheses by placing predicted loci within chromatin environments associated with active, bivalent, repressive, or open regulatory elements [@moore2020; @roadmap2015]. However, chromatin overlap does not itself establish regulation, and triplex-informed edges remain computational predictions rather than experimentally validated interactions. The current resource should therefore be interpreted as a comparative, hypothesis-generating atlas whose strongest outputs are candidate edges, conserved candidate core-pair patterns, rewired candidate modules, and trait-centered lncRNA nominations for future perturbation or direct RNA–DNA interaction studies.

Several limitations are important for interpretation. First, triplex-informed edges are repository-frozen computational predictions and do not establish direct RNA–DNA contact or regulatory causality. Second, orthology assignments affect both node-conservation and rewiring calls, especially for rapidly evolving lncRNAs with incomplete one-to-one correspondence. Third, hub breadth may be influenced by transcript length, repeat content, GC composition, and triplex-compatible motif opportunity, so hub rankings should be treated as prioritization features rather than direct measures of biological regulatory capacity. Fourth, the epigenomic context layer is human-centric and restricted to available cell-line experiments, which may not match the trait-relevant cell states. Fifth, trait associations identify candidate loci and programs but do not by themselves demonstrate that a prioritized lncRNA causally influences the corresponding phenotype. Sixth, LongTarget- and Triplexator-derived predictions carry algorithm-specific sensitivity and false-positive-rate limitations, so edge nominations should be interpreted as prediction-prioritized hypotheses rather than exhaustive or fully calibrated RNA–DNA interaction calls.

Future work should prioritize perturbation-based testing of candidate lncRNAs and targets, direct RNA–DNA interaction assays, and cell-type-matched epigenomic profiling. Candidate follow-up assays include CRISPRi/CRISPRa, antisense knockdown, ChIRP/CHART/RAP-style mapping, triplex-disruption mutagenesis, and perturbation-coupled single-cell readouts. These follow-up steps will be necessary to move from comparative candidate-edge prioritization toward experimentally resolved regulatory mechanisms.

## Methods

### 1. Source datasets and frozen analysis snapshot

All manuscript summaries were generated from a single frozen analysis snapshot spanning four primate species and a fixed human-only epigenomic baseline. The snapshot used throughout the paper contains **804,630** predicted lncRNA–PCG relationships, **49** core histone-mark experiments, **3,343,903** histone peaks, **7** DNase-HS experiments, and **1,223,622** DNase peaks, for a combined main-text human-only baseline of **56** experiments and **4,567,525** peaks. CTCF and H4K20me1 were retained only as extended human tracks outside the main-text baseline.

### 2. Trait-associated lncRNA and PCG collection

Trait-associated node inputs were assembled from repository-frozen lncRNA catalogs together with imported trait, ontology, and trait-to-gene association layers [@hon2017; @li2023; @lin2024; @cerezo2025]. Duplicate trait-to-core assignments were collapsed so that each `(core_id, trait_id, ontology_id)` combination contributed once to downstream summaries, while archived statistical and provenance fields were retained with the frozen repository snapshot. For manuscript analyses, trait terms were carried forward as contextual labels for trait-centered subnetworks, whereas lncRNAs and PCGs were normalized through `core_id` before cross-species comparison rather than interpreted as isolated catalog entries.

### 3. Ortholog mapping across four primates

Cross-species comparison was based on a repository-frozen ortholog import snapshot derived from `ortholog_lnc_table.csv` and `ortholog_gene_table.csv`. The lncRNA ortholog table records Infernal-derived homology assignments, whereas the PCG ortholog table records Ensembl-derived ortholog export assignments. Imported rows were normalized into shared numeric `core_id` groups. `CATG` identifiers were converted into numeric `core_id` values after version stripping, whereas `ENSG` identifiers were normalized in the same way and offset by `500000000` to avoid collisions with the `CATG` range. When multiple species shared a `core_id`, the human row was preferred for canonical symbol assignment. Genes with `core_id = NULL` were excluded from cross-species conservation analyses [@bryzghalov2020; @nawrocki2013; @harrison2024].

### 4. Triplex-informed candidate edge reconstruction

Candidate lncRNA–PCG edges were reconstructed from repository-frozen LongTarget-derived prediction tables grounded in RNA–DNA triplex inference [@mondal2015; @buske2012; @he2015]. These imported predictions trace to an archived upstream triplex workflow whose command structure and parameter files are preserved with the frozen repository snapshot. The manuscript does not re-run triplex prediction during manuscript generation; instead, it carries forward the frozen prediction outputs with `Best_Site_BA` retained as the source binding-affinity summary. Each imported prediction row is treated as one directed candidate edge linking `lncrna_gene_id` to `target_gene_id`, and the edge-weight field `binding_affinity` is carried forward from the source `Best_Site_BA` value. Target-region coordinates are preserved as `target_chromosome`, `target_start`, and `target_end`, while linked RNA and DNA sequence fields retain per-edge sequence context. These repository-frozen rows are computational predictions used for downstream normalization, ranking, and comparative interpretation rather than re-estimated triplex calls generated during manuscript writing.

Within-species network summaries operate on regulation rows, whereas cross-species conservation collapses rows to the `(lncrna_core_id, target_core_id)` core-pair level. If multiple predicted relationships linked the same core pair within a species, species presence was counted once for conservation and unique target-core breadth was counted once per target core. BA ≥ 100 was reserved for the high-affinity prioritization tier used in Figures 2, 4, and 5, rather than applied as a global inclusion threshold across all analyses.

Triplex-informed inference captures only one of several mechanisms by which lncRNAs may engage chromatin. Edges nominated here are therefore biased toward sequence-encoded triplex-compatible interactions and should be interpreted as a mechanistically restricted subset of candidate lncRNA–PCG relationships.

The upstream frozen marmoset LongTarget prediction input contains approximately 50,000 candidate rows, reflecting the upstream LongTarget input pipeline coverage rather than a plotting or manuscript-generation cap. After restricting to non-null binding affinity and orthology-mappable edges for the conservation matrix, 31,798 orthology-mappable marmoset species-edge rows entered the marmoset-edge-count downsampling sensitivity.

### 5. Network construction and graph analyses

Candidate lncRNA–PCG networks were represented as directed graphs. Figure-generation scripts summarize these graphs with `networkx` 3.2.1, using directed lncRNA–PCG graphs whose edge weight is `mean_ba`. For centrality summaries, eigenvector centrality was evaluated on the full undirected weighted projection and reported for lncRNA nodes. Hub breadth was summarized as the number of unique target core groups connected to each lncRNA, and centrality summaries used eigenvector centrality to distinguish broad hubs from network-central organizers. Readable subnetworks were generated by filtering to compact hub-centered or community-centered modules suitable for visual interpretation.

### 6. Conservation and rewiring metrics

Node conservation and edge conservation were evaluated separately. Node conservation used species presence for each non-null `core_id` in the fixed species order human, chimpanzee, macaque, and marmoset. Edge conservation used the `(lncrna_core_id, target_core_id)` core pair, with species presence assigned when at least one predicted relationship linked that pair in a species. Figure 3 used the fixed all-edge conservation overview with `min_species_count >= 2` and no additional BA cutoff, whereas singleton edges were excluded from the main overview.

Supplementary Figure 7 calibrates these comparative summaries in four ways: BA sensitivity was evaluated across thresholds of 0, 100, and 150; observed conservation strata were compared against within-species target-permutation null models that permute target-core assignments while preserving species-level lncRNA and target marginals; an additional degree-bin matched null preserves lncRNA row-degree tiers and target row-degree tiers within each species before recomputing cross-species core-pair sharing; and a marmoset-edge-count downsampling sensitivity exports the same shared-edge calibration after downsampling human, chimpanzee, and macaque species-edge rows to the marmoset edge count.

For the marmoset-edge-count sensitivity, human, chimpanzee, and macaque species-edge rows were independently downsampled without replacement to the number of marmoset species-edge rows with non-null binding affinity and orthology-mappable core-pair assignments. In each iteration, the observed statistic was computed directly from the randomly downsampled edge sets, and the corresponding null statistic was computed by applying within-species target permutation to those same downsampled edge sets. Downsampling summaries used 1,000 random draws with random seed 42; p05 and p95 values were computed with `numpy.quantile`, so percentile-interpolated edge-count bounds can be non-integer.

Pairwise edge-sharing Jaccard values were likewise compared against the corresponding null distributions. These analyses serve as robustness calibration for edge-level conservation and rewiring summaries rather than as functional confirmation.

### 7. Epigenomic context and overlap summaries

Main-text epigenomic analyses were restricted to eight core histone marks plus DNase-HS [@moore2020; @roadmap2015]. Gene-centered chromatin context was derived from a precomputed peak-to-gene association layer that matches peaks and genes on shared species and chromosome, then retains peaks satisfying `peak_start < gene_end + flanking` and `peak_end > max(0, gene_start - flanking)` with `flanking=10000` and `promoter_window=2000`. The stored fields `overlap_type`, `distance_to_tss`, `overlap_bp`, and `overlap_percentage` therefore distinguish overlapping, gene-body, upstream, downstream, and promoter-proximal associations, with `promoter` assigned when the peak midpoint falls within 2 kb of the transcription start site. This gene-centered layer was used to summarize promoter-proximal and gene-body chromatin context around target genes rather than to define the Figure 4 overlap counts.

Figure 4 overlap summaries were drawn from a denormalized human-specific overlap export in which each row represents one regulation-peak overlap observation from an active human ChIP-seq or DNase experiment, with overlap defined by direct spatial intersection between regulation `best_peak_chr`, `best_peak_start`, and `best_peak_end` coordinates and human peak intervals. The all-edge cohort was used to summarize baseline mark-overlap signatures without an additional BA cutoff. The high-affinity prioritization cohort was generated with `min_ba=100`. For cross-mark heatmaps, overlap fractions were computed from distinct overlapped `regulation_id` counts per mark-by-cell-line combination divided by the total number of candidate regulations in the corresponding cohort, so each regulation contributed at most once to a given mark-by-cell-line summary; combinations lacking experiments were labeled `NA` rather than treated as zero-overlap observations. Representative local track panels retain this human-only epigenomic context layer while displaying the stored `target_start` and `target_end` interval as the predicted triplex target region for visual interpretation.

Cross-mark comparisons used the fixed six-cell-line subset A549, GM12878, H1-hESC, HepG2, HMEC, and K562, while MCF-7 was excluded from multi-mark main-text panels because only sparse coverage was available in the frozen baseline. Direct context classes were assigned after collapsing repeated peak rows to `(regulation_id, cell_line)` observations and summarizing their observed mark sets. `bivalent-like` required joint H3K4me3 and H3K27me3 overlap within the same cell line, whereas `active-like non-bivalent` required at least one activating histone mark (H3K4me3, H3K27ac, or H3K4me1) without H3K27me3; remaining observations were labeled `other`.

### 8. Trait-centered prioritization

Trait-centered subnetworks were assembled from a repository-frozen trait-network export. The trait-gene layer joins `trait_gene_associations` to species-specific `genes` through shared `core_id` values and orders exported rows by trait and gene identifiers, after which the regulation layer appends lncRNA–PCG candidate edges ordered by `binding_affinity DESC` without imposing a separate hard BA threshold. Figure 5 therefore treats binding affinity as a ranking feature within the exported trait-centered networks rather than as a hidden inclusion rule.

The integrated ranking matrix combines candidate target count, mean and maximum BA, high-affinity edge count, best edge-conservation count, rewiring label, and epigenomic context class. Its color scale is column-normalized for visualization only, whereas binary or categorical layers encode evidence presence or class membership rather than quantitative effect size. Flagship trait selection follows a fixed sort on unique lncRNA count, unique target gene count, maximum BA, and `trait_id`, while the within-trait flagship case is restricted to rows passing conserved-edge and non-other epigenomic-context filters before final lncRNA ranking.

Literature-backed trait-gene context in Supplementary Table 1 was summarized from the repository-frozen `trait_gene_associations` layer. A target gene was counted as literature-backed for a trait when any exported row for that target gene carried `literature_support = TRUE` for the corresponding trait network. Counts were summarized at the target-gene level for each trait and for the selected flagship lncRNA module, and were used as provenance context rather than experimental confirmation of lncRNA regulation.

### 9. External evidence mapping and matched-null analyses

External evidence analyses were generated from compact processed TSV inputs rather than from live web queries during manuscript rendering. Expression context used processed GTEx v8 median-expression summaries for the Figure 6B PCG targets and a repository-frozen ENCODE RNA-seq input slot aligned to the Figure 4 cell-line subset. Mapping was performed through a PCG target-program mappable subset workflow: unique aliases were mapped to `core_id` values, ambiguous aliases were marked as ambiguous, and unmapped lncRNAs or PCGs were marked as missing rather than interpreted as zero expression. The Figure 6B summary is restricted to PCG target-program expression context and does not test direct lncRNA–PCG co-expression. TPM ≥ 1 was used as the expression-context threshold for processed expression rows.

GO coherence benchmarking was evaluated across the obesity target program and additional prioritized module classes using biological-process annotations. The observed module score was the fraction of annotated target genes captured by the most recurrent term in the module. Matched-null gene sets preserved target-gene set size and target annotation availability by sampling same-size sets from high-affinity target genes with GO annotations. The output reports observed score, null mean, null p95, empirical percentile, empirical p value, Benjamini-Hochberg FDR, and tested gene count. These analyses are used as module-level coherence benchmarking for prioritization, not as evidence of causal regulation.

## Resource Availability

### Lead Contact

Further information and requests for resources should be directed to the Lead Contact. Lead Contact details remain TBD until verified by the submitting authors.

### Materials Availability

This study did not generate new unique reagents.

### Data and Code Availability

The **Human LncRNA Atlas Companion** provides local-only interactive access to the reconstructed candidate edge networks, including filtered lncRNA–PCG relationship queries, gene-centered network views, comparative network endpoints, genome-browser inspection, and exportable downstream analysis tables. In this manuscript, the Companion is positioned as a **reproducibility and evidence-inspection layer** rather than as the primary result of the study.

- **Code:** Source code, analysis notebooks, figure-generation scripts, and manuscript rendering utilities are available at https://github.com/wyjistest/human-lncrna-atlas; the frozen submission snapshot used for this manuscript is rooted at commit `e052da5c073c6a3c91392ae06ecd8ec9037d6437`.
- **Reviewer package:** Figure-panel provenance is recorded in `paper_figures/cell_genomics_manifest.tsv`, and external evidence provenance is recorded in `paper_figures/cell_genomics_external_data_manifest.tsv`. The Cell Genomics package can be rebuilt locally with `python3 scripts/paper/rebuild_cellgenomics_package.py --skip-manuscript`.
- **Archival release:** A frozen archival package has been prepared at the GitHub commit recorded above and will be deposited at Zenodo prior to peer review; the resulting DOI will be added to the cover letter and Data and Code Availability statement at submission.
- **APIs:** No public deployment URL is used in this manuscript; the repository-local backend exposes an OpenAPI schema through the FastAPI `/docs` endpoint when run locally.
- **Notebooks and exports:** Analysis notebooks and archived manuscript exports distributed with the repository trace to the frozen analysis snapshot used for this manuscript.

### Supplementary / Extended Data

**Supplementary Figure 6. Human LncRNA Atlas Companion local interface and programmatic access**

- A. Query interface
- B. Network view
- C. Genome-browser view
- D. Export / API workflow

**Supplementary Figure 7. Robustness analyses for edge-level conservation, rewiring, degree structure, and species-coverage sensitivity**

- A. BA sensitivity across fixed threshold tiers
- B. Shared-edge null comparisons under within-species target permutation
- C. Pairwise edge-sharing null comparisons
- D. Degree-bin matched shared-edge null comparisons
- E. Marmoset-edge-count downsampling sensitivity for shared-edge calibration

**Supplementary Table 1. Trait-level literature-backed target context for flagship prioritization**

- Trait-level coverage of target genes with prior trait-literature context
- Flagship-module coverage of candidate targets with prior trait-literature context

**Supplementary Data. Cell Genomics reviewer package**

- Figure-panel manifest, external data manifest, expression-context table, functional-coherence table, and flagship-module evidence table

## References

::: {#refs}
:::

## Figure Legends

### Figure 1. From prior trait-associated gene catalogs to orthology-aware candidate lncRNA–PCG edges

Panel (A) shows that prior trait-associated lncRNA and PCG catalogs nominate candidate molecular nodes but do not specify candidate lncRNA–PCG edges. (B) lncRNA and PCG orthologs are mapped across human, chimpanzee, macaque, and marmoset into comparable `core_id` groups; this panel reports orthology-mapped catalog node counts for lncRNAs and PCGs rather than shared-edge or comparable-core totals. (C) Triplex-informed inference reconstructs candidate lncRNA–PCG edges from mapped catalog nodes. (D) The frozen analysis snapshot shown here includes four primate species, 804,630 predicted lncRNA–PCG relationships, and the main-text human-only epigenomic baseline of 56 experiments and 4,567,525 peaks.

### Figure 2. Global architecture of primate candidate lncRNA–gene networks

Panel (A) summarizes the full candidate-edge binding-affinity distribution and highlights the high-affinity prioritization zone at BA ≥ 100. (B) Unadjusted target-core breadth prioritizes candidate broad hubs; this breadth summary is not normalized for transcript length, GC content, repeat content, or triplex-compatible motif opportunity and should be interpreted as a prioritization feature. (C) Hub breadth is compared with eigenvector centrality to separate broad hubs from network-central candidate organizers, not direct biological regulators. (D) Representative filtered subnetworks are shown instead of dense whole-network visualizations so that hub-centered and modular candidate target programs remain interpretable.

### Figure 3. Cross-species conservation and lineage-specific rewiring of candidate lncRNA–PCG edges

Cross-species comparison is evaluated primarily at the edge level rather than only at the node level. (A) Edge-conservation strata summarize orthology-mappable `(lncrna_core_id, target_core_id)` core pairs with `min_species_count >= 2` and no additional BA cutoff, including 8,799 four-species, 22,749 three-species, and 42,955 two-species shared core-pair edges. (B) Node conservation is shown as context alongside edge conservation, illustrating that broadly shared orthology-mapped nodes do not imply broadly shared candidate edges. (C) Pairwise node and edge Jaccard summaries show that node-level sharing is higher than edge-level sharing, so edge-level sharing is the primary comparative readout for conservation and rewiring. (D) Paired conserved-versus-rewired examples are illustrative candidate core-pair patterns and are not functional rewiring evidence. (E) Observed-vs-null calibration for the four-species shared edge stratum uses log-scale y-axes and compares 8,799 observed shared core-pair edges with 1,000 target-permutation iterations (null mean 91.4; p95 approximately 107), with the degree-bin matched target-permutation p95 of 118 indicated as a stricter calibration. Supplementary Figure 7E reports a marmoset-edge-count random downsampling sensitivity in which human, chimpanzee, and macaque edge sets were downsampled to the marmoset edge count across 1,000 random draws; the observed four-species median remained 228 shared core-pair edges (p05-p95 203-254), above the matched target-permutation null p95 of 7. Full BA sensitivity, pairwise null details, degree-bin matched calibration, and species-coverage sensitivity remain in Supplementary Figure 7.

### Figure 4. Epigenomic context of candidate loci

Epigenomic data are used here as context rather than causal evidence. The top baseline strip is informational only and is not a lettered panel. (A) The histone-mark and DNase-HS overlap heatmap summarizes the frozen human-only baseline of eight core histone marks plus DNase-HS (56 experiments, 4,567,525 peaks) across A549, GM12878, H1-hESC, HepG2, HMEC, and K562; overlap fraction is calculated as distinct regulation IDs with mark overlap divided by candidate regulations, and unavailable experiments are labeled `NA` rather than treated as zero-overlap observations. (B) Mark-overlap context classes compare all-edge baseline observations with the BA ≥ 100 prioritization cohort, with BA ≥ 100 retained as a prioritization zone rather than a universal inclusion threshold. (C) Binding-affinity distributions are stratified across bivalent-like, active-like non-bivalent, and other context classes. (D) Representative local epigenomic tracks allow prioritized candidate loci to be inspected in active-like or bivalent-like chromatin contexts.

### Figure 5. Trait-centered subnetworks prioritize candidate trait-relevant lncRNAs

Trait-associated gene lists are reorganized into interpretable candidate target programs by linking traits to lncRNAs and PCGs through reconstructed edges. (A) The flagship tripartite network uses the frozen trait-ranking rule (unique lncRNA count, unique target gene count, maximum BA, and `trait_id`) and shows 14 displayed nodes, while the full exported flagship subnetwork contains 188 candidate edges. (B) The integrated ranking matrix combines target coverage, BA summaries, high-affinity edge counts, conservation or rewiring labels, epigenomic context, and flagship membership; the heatmap is a column-normalized visualization only and not a regulatory effect size. (C) Trait-specificity summaries compare candidate lncRNA coverage across the prioritized trait set. (D) The focused obesity case centers on `CATG00000045621.1` and reports 8 displayed targets, 8 high-affinity edges, BA range, conservation or rewiring class, epigenomic class, and literature-backed target provenance. The short network label `CATG045621` corresponds to the full lncRNA identifier `CATG00000045621.1`. Trait-centered prioritization treats binding affinity as a ranking feature rather than a hidden hard inclusion threshold and highlights candidate follow-up hypotheses rather than experimentally confirmed regulation.

### Figure 6. External evidence layers benchmark and contextualize prioritized modules

External evidence layers are summarized across top prioritized, conserved, rewired, and obesity flagship modules. (A) The atlas-wide benchmarking and robustness summary separates candidate module classes from robustness calibration, including the main edge-conservation null calibration and degree-bin matched null sensitivity layer. (B) PCG target-program expression context is summarized as a target-program-level only mappable subset analysis; lncRNA alias missing is treated as missing, not zero, and expression is framed as context for the target program rather than direct lncRNA–PCG co-expression. (C) GO coherence benchmarking compares target-program coherence across module classes against matched-null gene sets with the same target set size and annotation availability; 1 of 11 module entries exceeded the matched-null p95, no module survived FDR < 0.1, and the obesity program remained limited (observed 0.29, matched-null mean 0.22, empirical p = 0.077, FDR = 0.846). (D) The obesity flagship candidate evidence card integrates the lead lncRNA, displayed targets, high-affinity edges, BA range, conservation or rewiring class, epigenomic class, literature-backed target provenance, expression context, and GO coherence; the obesity trait layer reports 626 of 940 obesity-linked target genes with trait-gene provenance overlap, whereas the displayed flagship subset reports 6 of 8 targets with literature-backed obesity context. These layers benchmark and contextualize candidate prioritization and do not establish experimentally confirmed regulation.
