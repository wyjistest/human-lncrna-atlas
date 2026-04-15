# Figures / Tables Checklist (Paper)

This file tracks the target figure and table set for the research-first manuscript. The goal is to lead with network reconstruction and biological findings, while keeping the web resource as a secondary or optional component.

> Freeze rule: all counts, legends, and panel labels must be generated from one frozen submission snapshot. The paper-facing epigenomic inventory, orthology provenance, conserved-edge definition, and BA strategy are fixed in `docs/paper/submission_snapshot.md`.

---

## Figures

1. **Figure 1 — From prior trait-associated gene catalogs to orthology-aware candidate regulatory edges**
   Goal: establish the conceptual gap and the reconstruction workflow.
   Recommended panels:
   - catalog-gap schematic: prior trait-associated lncRNA / protein-coding gene catalogs nominate nodes, not edges;
   - ortholog mapping across human, chimpanzee, macaque, and marmoset into comparable `core_id` groups;
   - triplex-informed edge reconstruction workflow using conservative wording such as candidate regulatory edges;
   - frozen-snapshot KPI tiles using only already frozen metrics (`4` primate species, `804,630` predicted lncRNA to protein-coding gene relationships, `56` experiments, `4,567,525` peaks).
   Source: new composite figure required (workflow + data overview from frozen snapshot)
   Status: revised draft available for panel D (`paper_figures/fig1/fig1D_*`); panels A-C still pending manual design

2. **Figure 2 — Global architecture of primate lncRNA regulatory networks**
   Goal: summarize hub structure, affinity landscape, and readable modules after Figure 1 establishes the workflow.
   Recommended panels:
   - binding-affinity landscape with the high-affinity zone (`BA >= 100`) highlighted for prioritization;
   - top hub lncRNAs;
   - centrality or module statistics that separate broad hubs from network organizers;
   - filtered readable subnetworks.
   Provisional source material:
   - `notebooks/figures/01_ba_distribution_analysis.png`
   - `notebooks/figures/02_top_lncrnas_visualization.png`
   - `notebooks/figures/03_centrality_analysis.png`
   - `notebooks/figures/04_regulatory_network_visualization.png`
   Status: revised draft available for panels A/B/C (`paper_figures/fig2/`); panel D exemplar selection still pending

3. **Figure 3 — Cross-species conservation and lineage-specific rewiring of regulatory edges**
   Goal: make edge conservation, not only node conservation, a core result.
   Fixed definition: a conserved regulatory edge is a `(lncrna_core_id, target_core_id)` core pair observed in at least one regulation within a species; species presence is summarized in the fixed order human, chimpanzee, macaque, marmoset.
   Fixed BA rule: main conservation / rewiring overview uses all orthology-mappable edges with `min_species_count >= 2` and no additional BA cutoff.
   Recommended panels:
   - main-text UpSet overview of conserved-edge strata across two to four species (`1`-species singleton edges move to Supplementary);
   - node conservation versus edge conservation;
   - species-pair sharing heatmaps;
   - paired exemplars in a shared layout: one conserved module and one lineage-specific rewiring module.
   Source: new figure required; existing conservation notebook outputs are starting material
   Status: revised draft available for panels A/B/C (`paper_figures/fig3/`); panel D exemplar selection still pending

4. **Figure 4 — Epigenomic context prioritizes candidate regulatory loci and modules**
   Goal: show contextual support without over-claiming causality.
   Paper-facing fixed inventory: `8 core histone marks + DNase-HS` (`56` experiments, `4,567,525` peaks); `CTCF` and `H4K20me1` are excluded from the main-text baseline and may appear only as explicitly labeled extended human tracks.
   Cross-mark comparison subset: `A549`, `GM12878`, `H1-hESC`, `HepG2`, `HMEC`, and `K562`; exclude `MCF-7` from main-text multi-mark panels.
   Recommended panels:
   - histone-mark / DNase overlap summary, using `NA` rather than `0` when a mark-by-cell-line combination has no experiment in the frozen baseline;
   - direct mark-overlap signatures / mark-combination classes unless chromatin-state calling rules are separately frozen;
   - bivalent versus non-bivalent contrast;
   - representative IGV snapshots.
   Source: new figure required; use final frozen mark inventory only
   Status: pending

5. **Figure 5 — Trait-centered subnetworks prioritize candidate functional lncRNAs**
   Goal: turn trait-associated gene lists into interpretable regulatory programs.
   Recommended panels:
   - simplified tripartite trait to lncRNA to protein-coding gene subnetwork;
   - integrated ranking of candidate lncRNAs;
   - shared versus trait-specific regulators;
   - one or two focused case studies.
   Source: new figure required; disease notebook outputs are starting material
   Status: pending

6. **Figure 6 — Web resource and programmatic access**
   Goal: document the interactive platform only if the target journal expects a resource-facing figure in the main text.
   Recommended panels:
   - query interface;
   - network view;
   - IGV browser view;
   - export / API workflow.
   Source: application screenshots or annotated mockups
   Status: optional
   Note: move to Supplementary / Extended Data for research-first submissions.

---

## Tables

1. **Table 1 — Frozen-snapshot study scope across four primate species**
   Goal: summarize species coverage, node counts, and edge counts from the submission snapshot only.
   Source: frozen export summary
   Status: pending

2. **Table 2 — Final epigenomic dataset inventory used in the manuscript**
   Goal: report the fixed paper-facing baseline (`8 core histone marks + DNase-HS` = `56` experiments, `4,567,525` peaks), and separately document `CTCF` / `H4K20me1` as excluded extended human tracks.
   Source: `docs/paper/submission_snapshot.md` + `docs/CURRENT_STATUS.md`
   Status: drafted (inventory fixed; table body/legend TBC)

3. **Table 3 — Orthology mapping and conservation definitions**
   Goal: make the repository-frozen ortholog import provenance, `core_id` normalization rules, node-conservation rule, and conserved-edge core-pair definition explicit.
   Source: `docs/paper/submission_snapshot.md` + finalized Methods section
   Status: drafted (definitions fixed; table body/legend TBC)

4. **Table 4 — Trait-centered prioritization summary**
   Goal: report representative traits, prioritized lncRNAs, supporting evidence layers, and conservation / rewiring labels.
   Source: frozen trait-network exports
   Status: pending

---

## Figure Strategy Notes

- Main-text figures should each answer one question. Do not mix conservation, epigenomic context, and trait prioritization into the same figure.
- Figure 2 should absorb the current BA distribution / top lncRNAs / centrality / subnetwork outputs instead of letting those legacy panels define the manuscript opening.
- Figure 3 must explicitly report edge conservation or rewiring; node-only ortholog comparisons are not sufficient.
- Figure 3 should define conserved edges at the `(lncrna_core_id, target_core_id)` level and use the fixed species order human, chimpanzee, macaque, marmoset for all conservation labels.
- Figure 3 main overview should use the fixed all-edge conservation workflow (`min_species_count >= 2`, no BA cutoff), while Figure 2 / Figure 4 priority analyses continue to use `BA >= 100`.
- Main-text Figure 3A should show only `2`/`3`/`4`-species conserved-edge strata; `1`-species singleton edges belong in Supplementary panels.
- Figure 4 should use conservative wording such as context, overlap, or co-localization unless a matched-background enrichment workflow is frozen for submission.
- Figure 4 panel titles and legends should use direct mark-overlap signatures / mark-combination classes unless chromatin-state calling rules are separately frozen.
- Paper-facing inventory language is fixed to `8 core histone marks + DNase-HS`; `CTCF` and `H4K20me1` remain extended human tracks outside the main-text baseline.
- Main-text cross-mark comparisons should use the fixed six-cell-line subset `A549`, `GM12878`, `H1-hESC`, `HepG2`, `HMEC`, and `K562`; `MCF-7` should remain outside those panels.
- Figure 5 tripartite network panels should use at most two quantitative encodings; additional evidence layers belong in the ranking matrix rather than in the network layout.
- Figure 6 is optional and should be the first figure moved out of the main text when targeting a research-first journal.

---

## Figure Caption Drafts

### Figure 1. From prior trait-associated gene catalogs to orthology-aware candidate regulatory edges

Prior trait-associated lncRNA and protein-coding gene catalogs nominate relevant genes but do not specify candidate regulatory edges. We therefore map lncRNA and protein-coding orthologs across human, chimpanzee, macaque, and marmoset into comparable `core_id` groups and apply triplex-informed inference to reconstruct candidate lncRNA-to-protein-coding-gene edges. The frozen submission snapshot shown here is limited to paper-facing metrics fixed in `docs/paper/submission_snapshot.md`, including four primate species, `804,630` predicted lncRNA-to-protein-coding-gene relationships, and the main-text epigenomic baseline of `56` experiments and `4,567,525` peaks.

### Figure 2. Global architecture of primate lncRNA regulatory networks

After network reconstruction, the inferred primate regulatory networks can be summarized by their binding-affinity landscape, hub structure, and readable modules. The main-text prioritization view highlights the high-affinity zone at `BA >= 100`, identifies lncRNAs with unusually broad target coverage, and separates broad hubs from network organizers using centrality-aware summaries. Filtered subnetworks are shown instead of full-network hairballs so that hub-centered and modular candidate regulatory programs remain interpretable.

### Figure 3. Cross-species conservation and lineage-specific rewiring of regulatory edges

Cross-species comparison is evaluated primarily at the edge level rather than only at the node level. Conserved regulatory edges are defined as `(lncrna_core_id, target_core_id)` core pairs observed in at least one regulation within a species, using the fixed species order human, chimpanzee, macaque, and marmoset. The main-text overview shows only two-, three-, and four-species conserved-edge strata under the fixed all-edge workflow (`min_species_count >= 2`, no additional BA cutoff), whereas singleton edges are reported in Supplementary material. Node conservation, edge conservation, species-pair sharing, and paired conserved-versus-rewired exemplars are displayed separately to distinguish preserved modules from lineage-specific rewiring.

### Figure 4. Epigenomic context prioritizes candidate regulatory loci and modules

Epigenomic data are used here as contextual support rather than causal proof. Main-text analyses are restricted to the frozen paper-facing baseline of eight core histone marks plus DNase-HS (`56` experiments, `4,567,525` peaks), with cross-mark comparisons limited to `A549`, `GM12878`, `H1-hESC`, `HepG2`, `HMEC`, and `K562`. Overlap summaries should distinguish unavailable experiments (`NA`) from measured combinations with low overlap, and mark-combination classes should be described directly unless a separate chromatin-state calling workflow is frozen. Representative IGV snapshots place prioritized loci in active-like or bivalent-like chromatin contexts.

### Figure 5. Trait-centered subnetworks prioritize candidate functional lncRNAs

Trait-associated gene lists are reorganized into interpretable candidate regulatory programs by linking traits to lncRNAs and protein-coding genes through reconstructed edges. The flagship tripartite network should remain visually simple, using no more than two quantitative encodings in the network view, while additional evidence layers such as conservation and epigenomic support are summarized in the integrated ranking matrix. Trait-centered prioritization treats binding affinity as a ranking feature rather than a hidden hard inclusion threshold and highlights both shared regulators and trait-specific candidates through focused case studies.
