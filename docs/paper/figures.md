# Figures / Tables Checklist (Paper)

This file tracks the locked figure and table set for the research-first manuscript. The paper leads with network reconstruction and biological findings, while the Human LncRNA Atlas Companion remains a secondary local-only analysis interface.

> Freeze rule: all counts, legends, panel labels, and table bodies must be regenerated from one frozen submission snapshot. The paper-facing epigenomic inventory, orthology provenance, conserved-edge definition, and BA strategy are fixed in `docs/paper/submission_snapshot.md`.

---

## Figures

1. **Figure 1 — From prior trait-associated gene catalogs to orthology-aware candidate lncRNA–PCG edges**
   Goal: establish the conceptual gap and the reconstruction workflow.
   Final panels:
   - A. Catalog gap: prior trait-associated lncRNA / protein-coding gene catalogs nominate nodes, not edges.
   - B. Ortholog mapping across human, chimpanzee, macaque, and marmoset into comparable `core_id` groups.
   - C. Orthology-aware, triplex-informed workflow from catalogs to candidate lncRNA–PCG edges.
   - D. Frozen submission snapshot using only frozen metrics (`4` species, `804,630` candidate relationships, `56` experiments, `4,567,525` peaks).
   Source: paper-facing draft assets available under `paper_figures/fig1/`
   Status: revised draft available for panels A/B/C/D (`paper_figures/fig1/fig1A_*`, `fig1B_*`, `fig1C_*`, `fig1D_*`)

2. **Figure 2 — Global architecture of primate candidate lncRNA–gene networks**
   Goal: summarize hub structure, affinity landscape, and readable modules after Figure 1 establishes the workflow.
   Final panels:
   - A. Binding-affinity landscape with the prioritization zone highlighted at BA ≥ 100.
   - B. Unadjusted target-core breadth prioritization with paper-facing hub aliases.
   - C. Hub breadth versus eigenvector centrality for network-central candidate organizers.
   - D. Representative filtered subnetworks.
   Source: paper-facing draft assets available under `paper_figures/fig2/`
   Status: revised draft available for panels A/B/C/D (`paper_figures/fig2/fig2A_*`, `fig2B_*`, `fig2C_*`, `fig2D_*`)

3. **Figure 3 — Cross-species conservation and lineage-specific rewiring of candidate lncRNA–PCG edges**
   Goal: make edge conservation, not only node conservation, a core result.
   Fixed definition: a conserved candidate edge is a `(lncrna_core_id, target_core_id)` core pair observed in at least one predicted relationship within a species; species presence is summarized in the fixed order human, chimpanzee, macaque, marmoset.
   Fixed BA rule: the main conservation / rewiring overview uses all orthology-mappable edges with `min_species_count >= 2` and no additional BA cutoff.
   Final panels:
   - A. Conserved-edge strata across two to four species.
   - B. Node conservation versus edge conservation.
   - C. Species-pair node and edge sharing.
   - D1 / D2. Paired exemplars in a shared layout: one conserved module and one lineage-specific rewiring module.
   - E. Compact observed-vs-null calibration summary moved into the main-text figure.
   Source: paper-facing draft assets available under `paper_figures/fig3/`
   Status: revised draft available for panels A/B/C/D/E (`paper_figures/fig3/fig3A_*`, `fig3B_*`, `fig3C_*`, `fig3D_*`, `fig3E_*`)

4. **Figure 4 — Epigenomic context of candidate loci**
   Goal: show context from a human-only epigenomic context layer without over-claiming causality.
   Paper-facing fixed inventory: `8 core histone marks + DNase-HS` (`56` experiments, `4,567,525` peaks); `CTCF` and `H4K20me1` are excluded from the main-text baseline and may appear only as explicitly labeled extended human tracks.
   Cross-mark comparison subset: `A549`, `GM12878`, `H1-hESC`, `HepG2`, `HMEC`, and `K562`; exclude `MCF-7` from main-text multi-mark panels.
   Final structure:
   - Unnumbered header strip: baseline summary only; not a lettered panel.
   - A. Histone-mark / DNase overlap summary, using `NA` rather than `0` when a mark-by-cell-line combination has no experiment in the frozen baseline.
   - B. Mark-overlap context classes / mark-combination classes.
   - C. Bivalent versus non-bivalent contrast.
   - D. Representative local epigenomic tracks.
   Source: paper-facing draft assets available under `paper_figures/fig4/`
   Status: revised draft available for panels A/B/C/D (`paper_figures/fig4/fig4A_*`, `fig4B_*`, `fig4C_*`, `fig4D_*`)

5. **Figure 5 — Trait-centered subnetworks prioritize candidate trait-relevant lncRNAs**
   Goal: turn trait-associated gene lists into interpretable candidate target programs, using a fixed flagship-trait rule rather than an ad hoc example choice.
   Final panels:
   - A. Simplified trait to lncRNA to protein-coding gene tripartite subnetwork.
   - B. Integrated ranking matrix for candidate lncRNAs.
   - C. Shared versus trait-specific regulators.
   - D. One focused flagship case study.
   Source: paper-facing draft assets available under `paper_figures/fig5/`
   Status: revised draft available for panels A/B/C/D (`paper_figures/fig5/fig5A_*`, `fig5B_*`, `fig5C_*`, `fig5D_*`)

6. **Figure 6 — External evidence layers benchmark and contextualize prioritized modules**
   Goal: provide Cell Genomics-style external benchmarking and contextualization without changing the candidate-prioritization claim.
   Final panels:
   - A. atlas-wide benchmarking summary covering top prioritized, conserved, rewired, and obesity flagship modules plus main and degree-bin matched edge-conservation null calibration.
   - B. PCG target-program expression context as a mappable subset analysis, not direct lncRNA–PCG co-expression.
   - C. Multi-module GO coherence benchmarking versus matched-null gene sets.
   - D. obesity flagship as a representative case card integrating lead lncRNA, 8 displayed targets, 8 high-affinity edges, BA range, conservation/rewiring class, epigenomic class, literature-backed target provenance, expression context, and GO coherence benchmarking.
   Source: `paper_figures/fig6/` plus `paper_figures/cell_genomics_manifest.tsv`
   Status: revised draft available for panels A/B/C/D (`paper_figures/fig6/fig6A_*`, `fig6B_*`, `fig6C_*`, `fig6D_*`)

7. **Supplementary Figure 6 — Human LncRNA Atlas Companion local interface and programmatic access**
   Goal: document repository-local query, network, genome-browser, export, and FastAPI `/docs` workflows without implying a public deployment URL.
   Final panels:
   - A. Query interface.
   - B. Network view.
   - C. Genome-browser view.
   - D. Export / API workflow.
   Source: `paper_figures/supplementary/suppfig6_companion_access.*`
   Status: revised draft available.

---

## Tables

1. **Table 1 — Frozen-snapshot study scope across four primate species**
   Goal: summarize species coverage, node counts, and edge counts from the submission snapshot only.
   Source: frozen export summary.
   Status: pending.

2. **Table 2 — Final epigenomic dataset inventory used in the manuscript**
   Goal: report the fixed paper-facing baseline (`8 core histone marks + DNase-HS` = `56` experiments, `4,567,525` peaks), and separately document `CTCF` / `H4K20me1` as excluded extended human tracks.
   Source: `paper_figures/tables/table2_epigenomic_inventory.tsv`
   Status: revised draft available.

3. **Table 3 — Orthology mapping and conservation definitions**
   Goal: make the repository-frozen ortholog import provenance, `core_id` normalization rules, node-conservation rule, and conserved-edge core-pair definition explicit.
   Source: `docs/paper/submission_snapshot.md` + finalized Methods section.
   Status: drafted (definitions fixed; table body/legend TBC).

4. **Table 4 — Trait-centered prioritization summary**
   Goal: report representative traits, prioritized lncRNAs, contextual evidence layers, and conservation / rewiring labels.
   Source: `paper_figures/tables/table4_trait_prioritization.tsv`
   Status: revised draft available.

5. **Supplementary Table 1 — Trait-level literature-backed target context for flagship prioritization**
   Goal: summarize trait-level and flagship-module target coverage with prior literature-backed trait-gene context so the flagship example is biologically anchored rather than ad hoc.
   Source: `paper_figures/tables/supp_table1_trait_literature_support.tsv`
   Status: revised draft available.

---

## Figure Strategy Notes

- Main-text figures should each answer one question. Do not mix conservation, epigenomic context, and trait prioritization into the same figure.
- Figure 2 panel C must use eigenvector centrality wording consistently in the panel title, legend, and manuscript text.
- Figure 3 must explicitly report edge conservation or rewiring; node-only ortholog comparisons are not sufficient.
- Figure 3 should define conserved edges at the `(lncrna_core_id, target_core_id)` level and use the fixed species order human, chimpanzee, macaque, marmoset for all conservation labels.
- Figure 3 main overview must use the fixed all-edge conservation workflow (`min_species_count >= 2`, no additional BA cutoff), while Figure 2 / Figure 4 priority analyses continue to use BA ≥ 100.
- Main-text Figure 3A should show only `2`/`3`/`4`-species conserved-edge strata; `1`-species singleton edges belong in Supplementary panels.
- Figure 4 should use conservative wording such as context, overlap, or co-localization unless a matched-background enrichment workflow is frozen for submission.
- Figure 4 panel titles and legends should use direct mark-overlap signatures / mark-combination classes unless chromatin-state calling rules are separately frozen.
- Figure 4 keeps the inventory strip unnumbered; the formal panels remain A-D.
- Paper-facing inventory language is fixed to `8 core histone marks + DNase-HS`; `CTCF` and `H4K20me1` remain extended human tracks outside the main-text baseline.
- Main-text cross-mark comparisons should use the fixed six-cell-line subset `A549`, `GM12878`, `H1-hESC`, `HepG2`, `HMEC`, and `K562`; `MCF-7` should remain outside those panels.
- Figure 5 tripartite network panels should use at most two quantitative encodings; additional evidence layers belong in the ranking matrix rather than in the network layout.
- Figure 5 uses binding affinity as a ranking feature, not as a hidden hard inclusion threshold.
- Figure 5 flagship selection should stay fixed to the frozen sort on unique lncRNA count, unique target gene count, and maximum BA; in the current snapshot, obesity ranked first and the within-trait case must continue to use conserved-edge and non-other epigenomic-context filters.
- Figure 6 is now the Cell Genomics external benchmarking figure; the Human LncRNA Atlas Companion remains Supplementary Figure 6.

---

## Figure Caption Drafts

Canonical submission-facing legend text now lives in `docs/paper/manuscript.md` under `## Figure Legends`. The draft captions below remain the planning reference and should be kept semantically aligned with the manuscript legends.


### Figure 1. From prior trait-associated gene catalogs to orthology-aware candidate lncRNA–PCG edges

Panel (A) shows that prior trait-associated lncRNA and PCG catalogs nominate candidate molecular nodes but do not specify candidate lncRNA–PCG edges. (B) lncRNA and PCG orthologs are mapped across human, chimpanzee, macaque, and marmoset into comparable `core_id` groups; this panel reports orthology-mapped catalog node counts for lncRNAs and PCGs rather than shared-edge or comparable-core totals. (C) Triplex-informed inference reconstructs candidate lncRNA–PCG edges from mapped catalog nodes. (D) The frozen analysis snapshot shown here includes four primate species, 804,630 predicted lncRNA–PCG relationships, and the main-text human-only epigenomic baseline of 56 experiments and 4,567,525 peaks.

### Figure 2. Global architecture of primate candidate lncRNA–gene networks

Panel (A) summarizes the full candidate-edge binding-affinity distribution and highlights the high-affinity prioritization zone at BA ≥ 100. (B) Unadjusted target-core breadth prioritizes candidate broad hubs; this breadth summary is not normalized for transcript length, GC content, repeat content, or triplex-compatible motif opportunity and should be interpreted as a prioritization feature. (C) Hub breadth is compared with eigenvector centrality to separate broad hubs from network-central candidate organizers, not direct biological regulators. (D) Representative filtered subnetworks are shown instead of dense whole-network visualizations so that hub-centered and modular candidate target programs remain interpretable.

### Figure 3. Cross-species conservation and lineage-specific rewiring of candidate lncRNA–PCG edges

Cross-species comparison is evaluated primarily at the edge level rather than only at the node level. (A) Edge-conservation strata summarize orthology-mappable `(lncrna_core_id, target_core_id)` core pairs with `min_species_count >= 2` and no additional BA cutoff, including 8,799 four-species, 22,749 three-species, and 42,955 two-species shared core-pair edges. (B) Node conservation is shown as context alongside edge conservation, illustrating that broadly shared orthology-mapped nodes do not imply broadly shared candidate edges. (C) Pairwise node and edge Jaccard summaries show that node-level sharing is higher than edge-level sharing, so edge-level sharing is the primary comparative readout for conservation and rewiring. (D) Paired conserved-versus-rewired examples are illustrative candidate core-pair patterns and are not functional rewiring evidence. (E) Observed-vs-null calibration for the four-species shared edge stratum uses log-scale y-axes and compares 8,799 observed shared core-pair edges with 1,000 target-permutation iterations (null mean 91.4; p95 approximately 107), with the degree-bin matched target-permutation p95 of 118 indicated as a stricter calibration. Supplementary Figure 7E reports a marmoset-edge-count random downsampling sensitivity in which human, chimpanzee, and macaque edge sets were downsampled to the marmoset edge count across 1,000 random draws; the observed four-species median remained 228 shared core-pair edges (p05-p95 203-254), above the matched target-permutation null p95 of 7.

### Figure 4. Epigenomic context of candidate loci

Epigenomic data are used here as context rather than causal evidence. The top baseline strip is informational only and is not a lettered panel. (A) The histone-mark and DNase-HS overlap heatmap summarizes the frozen human-only baseline of eight core histone marks plus DNase-HS (56 experiments, 4,567,525 peaks) across A549, GM12878, H1-hESC, HepG2, HMEC, and K562; overlap fraction is calculated as distinct regulation IDs with mark overlap divided by candidate regulations, and unavailable experiments are labeled `NA` rather than treated as zero-overlap observations. (B) Mark-overlap context classes compare all-edge baseline observations with the BA ≥ 100 prioritization cohort, with BA ≥ 100 retained as a prioritization zone rather than a universal inclusion threshold. (C) Binding-affinity distributions are stratified across bivalent-like, active-like non-bivalent, and other context classes. (D) Representative local epigenomic tracks allow prioritized candidate loci to be inspected in active-like or bivalent-like chromatin contexts.

### Figure 5. Trait-centered subnetworks prioritize candidate trait-relevant lncRNAs

Trait-associated gene lists are reorganized into interpretable candidate target programs by linking traits to lncRNAs and PCGs through reconstructed edges. The flagship tripartite network remains visually simple, using no more than two quantitative encodings in the network view, while additional context layers such as conservation, rewiring labels, and epigenomic context are summarized in the integrated ranking matrix. The flagship trait was selected by ranking traits on unique lncRNA count, unique target gene count, and maximum BA, under which obesity ranked first in the frozen analysis snapshot; the within-trait case then applies conserved-edge and non-other epigenomic-context filters before the final lncRNA selection step. The ranking-matrix color scale is a column-normalized score used for visualization only, and binary or categorical layers indicate class membership rather than continuous effect sizes. In the focused case panel, the short network label `CATG045621` maps to the full lncRNA identifier `CATG00000045621.1`. Trait-centered prioritization treats binding affinity as a ranking feature rather than a hidden hard inclusion threshold and highlights both shared candidates and trait-specific candidates through one focused flagship case study.

### Figure 6. External evidence layers benchmark and contextualize prioritized modules

External evidence layers are summarized across top prioritized, conserved, rewired, and obesity flagship modules. (A) The atlas-wide benchmarking and robustness summary separates candidate module classes from robustness calibration, including the main edge-conservation null calibration and degree-bin matched null sensitivity layer. (B) PCG target-program expression context is summarized as a target-program-level only mappable subset analysis; lncRNA alias missing is treated as missing, not zero, and expression is framed as context for the target program rather than direct lncRNA–PCG co-expression. (C) GO coherence benchmarking compares target-program coherence across module classes against matched-null gene sets with the same target set size and annotation availability; 1 of 11 module entries exceeded the matched-null p95, no module survived FDR < 0.1, and the obesity program remained limited (observed 0.29, matched-null mean 0.22, empirical p = 0.077, FDR = 0.846). (D) The obesity flagship candidate evidence card integrates the lead lncRNA, displayed targets, high-affinity edges, BA range, conservation or rewiring class, epigenomic class, literature-backed target provenance, expression context, and GO coherence; the obesity trait layer reports 626 of 940 obesity-linked target genes with trait-gene provenance overlap, whereas the displayed flagship subset reports 6 of 8 targets with literature-backed obesity context. These layers benchmark and contextualize candidate prioritization and do not establish experimentally confirmed regulation.
