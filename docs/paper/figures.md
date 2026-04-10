# Figures / Tables Checklist (Paper)

This file tracks the target figure and table set for the research-first manuscript. The goal is to lead with network reconstruction and biological findings, while keeping the web resource as a secondary or optional component.

> Freeze rule: all counts, legends, and panel labels must be generated from one frozen submission snapshot. The paper-facing epigenomic inventory, orthology provenance, conserved-edge definition, and BA strategy are fixed in `docs/paper/submission_snapshot.md`.

---

## Figures

1. **Figure 1 — From prior trait-associated gene catalogs to orthology-aware candidate regulatory edges**
   Goal: establish the conceptual gap and the reconstruction workflow.
   Recommended panels:
   - prior trait-associated lncRNA / protein-coding gene catalogs do not specify regulatory edges;
   - ortholog mapping across human, chimpanzee, macaque, and marmoset;
   - triplex-informed edge reconstruction workflow;
   - frozen-snapshot overview of nodes, edges, and species coverage.
   Source: new composite figure required (workflow + data overview from frozen snapshot)
   Status: pending

2. **Figure 2 — Global architecture of primate lncRNA regulatory networks**
   Goal: summarize hub structure, affinity landscape, and readable modules after Figure 1 establishes the workflow.
   Recommended panels:
   - degree / target-count / binding-affinity summaries;
   - top hub lncRNAs;
   - centrality or module statistics;
   - filtered readable subnetworks.
   Provisional source material:
   - `notebooks/figures/01_ba_distribution_analysis.png`
   - `notebooks/figures/02_top_lncrnas_visualization.png`
   - `notebooks/figures/03_centrality_analysis.png`
   - `notebooks/figures/04_regulatory_network_visualization.png`
   Status: restructure existing assets into one main-text figure and/or Supplementary panels

3. **Figure 3 — Cross-species conservation and lineage-specific rewiring of regulatory edges**
   Goal: make edge conservation, not only node conservation, a core result.
   Fixed definition: a conserved regulatory edge is a `(lncrna_core_id, target_core_id)` core pair observed in at least one regulation within a species; species presence is summarized in the fixed order human, chimpanzee, macaque, marmoset.
   Fixed BA rule: main conservation / rewiring overview uses all orthology-mappable edges with `min_species_count >= 2` and no additional BA cutoff.
   Recommended panels:
   - conservation strata across one to four species (UpSet preferred over Venn);
   - node conservation versus edge conservation;
   - species-pair sharing heatmaps;
   - representative conserved and lineage-specific modules.
   Source: new figure required; existing conservation notebook outputs are starting material
   Status: pending

4. **Figure 4 — Epigenomic context prioritizes candidate regulatory loci and modules**
   Goal: show contextual support without over-claiming causality.
   Paper-facing fixed inventory: `8 core histone marks + DNase-HS` (`56` experiments, `4,567,525` peaks); `CTCF` and `H4K20me1` are excluded from the main-text baseline and may appear only as explicitly labeled extended human tracks.
   Cross-mark comparison subset: `A549`, `GM12878`, `H1-hESC`, `HepG2`, `HMEC`, and `K562`; exclude `MCF-7` from main-text multi-mark panels.
   Recommended panels:
   - histone-mark / DNase overlap summary;
   - mark-composition or chromatin-context comparison;
   - bivalent versus non-bivalent contrast;
   - representative IGV snapshots.
   Source: new figure required; use final frozen mark inventory only
   Status: pending

5. **Figure 5 — Trait-centered subnetworks prioritize candidate functional lncRNAs**
   Goal: turn trait-associated gene lists into interpretable regulatory programs.
   Recommended panels:
   - tripartite trait to lncRNA to protein-coding gene subnetwork;
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
   Goal: summarize species coverage, node counts, edge counts, and sequence coverage from the submission snapshot only.
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
- Figure 4 should use conservative wording such as context, overlap, or co-localization unless a matched-background enrichment workflow is frozen for submission.
- Paper-facing inventory language is fixed to `8 core histone marks + DNase-HS`; `CTCF` and `H4K20me1` remain extended human tracks outside the main-text baseline.
- Main-text cross-mark comparisons should use the fixed six-cell-line subset `A549`, `GM12878`, `H1-hESC`, `HepG2`, `HMEC`, and `K562`; `MCF-7` should remain outside those panels.
- Figure 6 is optional and should be the first figure moved out of the main text when targeting a research-first journal.
