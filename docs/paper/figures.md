# Figures / Tables Checklist (Paper)

This file tracks the locked figure and table set for the research-first manuscript. The paper leads with network reconstruction and biological findings, while the web resource remains a secondary or optional component.

> Freeze rule: all counts, legends, panel labels, and table bodies must be regenerated from one frozen submission snapshot. The paper-facing epigenomic inventory, orthology provenance, conserved-edge definition, and BA strategy are fixed in `docs/paper/submission_snapshot.md`.

---

## Figures

1. **Figure 1 — From prior trait-associated gene catalogs to orthology-aware candidate regulatory edges**
   Goal: establish the conceptual gap and the reconstruction workflow.
   Final panels:
   - A. Catalog gap: prior trait-associated lncRNA / protein-coding gene catalogs nominate nodes, not edges.
   - B. Ortholog mapping across human, chimpanzee, macaque, and marmoset into comparable `core_id` groups.
   - C. Orthology-aware, triplex-informed workflow from catalogs to candidate regulatory edges.
   - D. Frozen submission snapshot stats bar using only frozen metrics (`4` species, `804,630` candidate relationships, `56` experiments, `4,567,525` peaks).
   Source: paper-facing draft assets available under `paper_figures/fig1/`
   Status: revised draft available for panels A/B/C/D (`paper_figures/fig1/fig1A_*`, `fig1B_*`, `fig1C_*`, `fig1D_*`)

2. **Figure 2 — Global architecture of primate lncRNA regulatory networks**
   Goal: summarize hub structure, affinity landscape, and readable modules after Figure 1 establishes the workflow.
   Final panels:
   - A. Binding-affinity landscape with the prioritization zone highlighted at `BA >= 100`.
   - B. Top hub lncRNAs with paper-facing hub aliases.
   - C. Hub breadth versus eigenvector centrality.
   - D. Representative filtered subnetworks.
   Source: paper-facing draft assets available under `paper_figures/fig2/`
   Status: revised draft available for panels A/B/C/D (`paper_figures/fig2/fig2A_*`, `fig2B_*`, `fig2C_*`, `fig2D_*`)

3. **Figure 3 — Cross-species conservation and lineage-specific rewiring of regulatory edges**
   Goal: make edge conservation, not only node conservation, a core result.
   Fixed definition: a conserved regulatory edge is a `(lncrna_core_id, target_core_id)` core pair observed in at least one regulation within a species; species presence is summarized in the fixed order human, chimpanzee, macaque, marmoset.
   Fixed BA rule: the main conservation / rewiring overview uses all orthology-mappable edges with `min_species_count >= 2` and no additional BA cutoff.
   Final panels:
   - A. Conserved-edge strata across two to four species.
   - B. Node conservation versus edge conservation.
   - C. Species-pair edge sharing heatmap.
   - D1 / D2. Paired exemplars in a shared layout: one conserved module and one lineage-specific rewiring module.
   Source: paper-facing draft assets available under `paper_figures/fig3/`
   Status: revised draft available for panels A/B/C/D (`paper_figures/fig3/fig3A_*`, `fig3B_*`, `fig3C_*`, `fig3D_*`)

4. **Figure 4 — Epigenomic context of candidate regulatory loci**
   Goal: show contextual support without over-claiming causality.
   Paper-facing fixed inventory: `8 core histone marks + DNase-HS` (`56` experiments, `4,567,525` peaks); `CTCF` and `H4K20me1` are excluded from the main-text baseline and may appear only as explicitly labeled extended human tracks.
   Cross-mark comparison subset: `A549`, `GM12878`, `H1-hESC`, `HepG2`, `HMEC`, and `K562`; exclude `MCF-7` from main-text multi-mark panels.
   Final structure:
   - Unnumbered header strip: baseline summary only; not a lettered panel.
   - A. Histone-mark / DNase overlap summary, using `NA` rather than `0` when a mark-by-cell-line combination has no experiment in the frozen baseline.
   - B. Direct mark-overlap signature classes / mark-combination classes.
   - C. Bivalent versus non-bivalent contrast.
   - D. Representative IGV snapshots.
   Source: paper-facing draft assets available under `paper_figures/fig4/`
   Status: revised draft available for panels A/B/C/D (`paper_figures/fig4/fig4A_*`, `fig4B_*`, `fig4C_*`, `fig4D_*`)

5. **Figure 5 — Trait-centered subnetworks prioritize candidate lncRNAs**
   Goal: turn trait-associated gene lists into interpretable regulatory programs.
   Final panels:
   - A. Simplified trait to lncRNA to protein-coding gene tripartite subnetwork.
   - B. Integrated ranking matrix for candidate lncRNAs.
   - C. Shared versus trait-specific regulators.
   - D. One focused flagship case study.
   Source: paper-facing draft assets available under `paper_figures/fig5/`
   Status: revised draft available for panels A/B/C/D (`paper_figures/fig5/fig5A_*`, `fig5B_*`, `fig5C_*`, `fig5D_*`)

6. **Figure 6 — Web resource and programmatic access**
   Goal: document the interactive platform only if the target journal expects a resource-facing figure in the main text.
   Suggested panels:
   - query interface;
   - network view;
   - IGV browser view;
   - export / API workflow.
   Source: application screenshots or annotated mockups.
   Status: optional.
   Note: move to Supplementary / Extended Data for research-first submissions by default.

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
   Goal: report representative traits, prioritized lncRNAs, supporting evidence layers, and conservation / rewiring labels.
   Source: `paper_figures/tables/table4_trait_prioritization.tsv`
   Status: revised draft available.

---

## Figure Strategy Notes

- Main-text figures should each answer one question. Do not mix conservation, epigenomic context, and trait prioritization into the same figure.
- Figure 2 panel C must use eigenvector centrality wording consistently in the panel title, legend, and manuscript text.
- Figure 3 must explicitly report edge conservation or rewiring; node-only ortholog comparisons are not sufficient.
- Figure 3 should define conserved edges at the `(lncrna_core_id, target_core_id)` level and use the fixed species order human, chimpanzee, macaque, marmoset for all conservation labels.
- Figure 3 main overview must use the fixed all-edge conservation workflow (`min_species_count >= 2`, no additional BA cutoff), while Figure 2 / Figure 4 priority analyses continue to use `BA >= 100`.
- Main-text Figure 3A should show only `2`/`3`/`4`-species conserved-edge strata; `1`-species singleton edges belong in Supplementary panels.
- Figure 4 should use conservative wording such as context, overlap, or co-localization unless a matched-background enrichment workflow is frozen for submission.
- Figure 4 panel titles and legends should use direct mark-overlap signatures / mark-combination classes unless chromatin-state calling rules are separately frozen.
- Figure 4 keeps the inventory strip unnumbered; the formal panels remain A-D.
- Paper-facing inventory language is fixed to `8 core histone marks + DNase-HS`; `CTCF` and `H4K20me1` remain extended human tracks outside the main-text baseline.
- Main-text cross-mark comparisons should use the fixed six-cell-line subset `A549`, `GM12878`, `H1-hESC`, `HepG2`, `HMEC`, and `K562`; `MCF-7` should remain outside those panels.
- Figure 5 tripartite network panels should use at most two quantitative encodings; additional evidence layers belong in the ranking matrix rather than in the network layout.
- Figure 5 uses binding affinity as a ranking feature, not as a hidden hard inclusion threshold.
- Figure 6 is optional and should be the first figure moved out of the main text when targeting a research-first journal.

---

## Figure Caption Drafts

### Figure 1. From prior trait-associated gene catalogs to orthology-aware candidate regulatory edges

Prior trait-associated lncRNA and protein-coding gene catalogs nominate relevant genes but do not specify candidate regulatory edges. We therefore map lncRNA and protein-coding orthologs across human, chimpanzee, macaque, and marmoset into comparable `core_id` groups and apply triplex-informed inference to reconstruct candidate lncRNA-to-protein-coding-gene edges. The frozen submission snapshot shown here is limited to paper-facing metrics fixed in `docs/paper/submission_snapshot.md`, including four primate species, `804,630` predicted lncRNA-to-protein-coding-gene relationships, and the main-text epigenomic baseline of `56` experiments and `4,567,525` peaks.

### Figure 2. Global architecture of primate lncRNA regulatory networks

After network reconstruction, the inferred primate regulatory networks are summarized by their binding-affinity landscape, hub structure, hub breadth versus eigenvector centrality, and readable filtered subnetworks. The main-text prioritization view highlights the high-affinity zone at `BA >= 100`, identifies lncRNAs with unusually broad target coverage, and separates broad hubs from network-central organizers using an eigenvector-centrality-first summary. Filtered subnetworks are shown instead of full-network hairballs so that hub-centered and modular candidate regulatory programs remain interpretable.

### Figure 3. Cross-species conservation and lineage-specific rewiring of regulatory edges

Cross-species comparison is evaluated primarily at the edge level rather than only at the node level. Conserved regulatory edges were defined as `(lncrna_core_id, target_core_id)` core pairs observed in at least one regulation within a species. The main conservation overview includes all orthology-mappable edges with `min_species_count >= 2` and applies no additional BA cutoff. Node conservation, edge conservation, species-pair sharing, and paired conserved-versus-rewired exemplars are displayed separately to distinguish preserved modules from lineage-specific rewiring.

### Figure 4. Epigenomic context of candidate regulatory loci

Epigenomic data are used here as contextual support rather than causal evidence. Main-text analyses are restricted to the frozen paper-facing baseline of eight core histone marks plus DNase-HS (`56` experiments, `4,567,525` peaks), with cross-mark comparisons limited to `A549`, `GM12878`, `H1-hESC`, `HepG2`, `HMEC`, and `K562`. The top baseline strip is informational only and is not a lettered panel. Overlap summaries distinguish unavailable experiments (`NA`) from measured combinations with low overlap, and mark-combination classes are described directly rather than as causal chromatin states. Representative IGV snapshots place prioritized loci in active-like or bivalent-like chromatin contexts.

### Figure 5. Trait-centered subnetworks prioritize candidate lncRNAs

Trait-associated gene lists are reorganized into interpretable candidate regulatory programs by linking traits to lncRNAs and protein-coding genes through reconstructed edges. The flagship tripartite network remains visually simple, using no more than two quantitative encodings in the network view, while additional evidence layers such as conservation, rewiring labels, and epigenomic support are summarized in the integrated ranking matrix. Trait-centered prioritization treats binding affinity as a ranking feature rather than a hidden hard inclusion threshold and highlights both shared regulators and trait-specific candidates through one focused flagship case study.
