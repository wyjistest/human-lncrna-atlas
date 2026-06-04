# Cell Genomics Presubmission Inquiry Draft

## Working Title

Triplex-informed lncRNA–gene candidate networks reveal edge-level conservation and rewiring across primates

## Abstract

Trait-associated lncRNA and protein-coding gene catalogs nominate molecular nodes but rarely resolve candidate lncRNA–PCG edges or their evolutionary stability. Here, we integrate primate lncRNA and protein-coding gene orthology with triplex-informed RNA–DNA interaction prediction to reconstruct 804,630 candidate lncRNA–PCG edges across human, chimpanzee, macaque, and marmoset. Cross-species comparison shows that node conservation is not edge conservation: human-chimpanzee node Jaccard 0.79 versus edge Jaccard 0.37, and 8,799 observed four-species core-pair edges versus a target-permutation null mean 91.4 (empirical p < 0.001). Human epigenomic context, PCG target-program expression, GO-based module-coherence benchmarking, and trait-gene provenance further contextualize candidate modules, including trait-centered lncRNA nominations for follow-up. We provide a frozen, reproducible analysis snapshot and the Human LncRNA Atlas Companion, a local-only analysis interface for inspection and reuse. This atlas prioritizes conserved and rewired lncRNA–PCG hypotheses without establishing causal regulation.

## Main Results

The study makes three linked contributions. First, it converts prior trait-associated lncRNA and PCG catalogs from node lists into an orthology-aware edge layer comprising 804,630 predicted lncRNA–PCG relationships across four primates. Second, Figure 3 establishes edge-level lncRNA–PCG conservation and rewiring as a comparative discovery signal distinct from node-level orthology, including Figure 3 observed-vs-null calibration of four-species shared core-pair edges and an additional degree-bin matched null sensitivity layer. Third, Figure 6 asks how external evidence layers benchmark and contextualize prioritized modules without claiming causal regulation: it summarizes atlas-wide evidence across top prioritized, conserved, rewired, and obesity flagship modules, with the obesity module retained as a representative case card.

The current Cell Genomics package includes 1,000-iteration target-permutation null calibration for Figure 3E and Supplementary Figure 7, a degree-bin matched null sensitivity layer for edge-conservation robustness, a PCG target-program expression framing for Figure 6B, multi-module GO-based module-coherence benchmarking with size/annotation-matched nulls for Figure 6C, and reviewer-facing manifests that trace all Figure 3E / Figure 6 outputs.

## Fit for Cell Genomics

We believe this work fits Cell Genomics because it is a computational and comparative genomics study centered on a new candidate edge interpretation layer rather than a database-only resource. The main advance is conceptual and analytical: conserved nodes do not imply conserved candidate lncRNA–PCG edges, and edge-level lncRNA–PCG conservation and rewiring can nominate comparative candidate modules not visible from trait-gene catalogs alone.

The Human LncRNA Atlas Companion is positioned as a local-only reproducibility and evidence-inspection layer for reviewers and readers. It is not the primary claim of the paper. The manuscript is currently intended for presubmission inquiry before formal submission, so editorial feedback can guide whether additional orthogonal public-data enrichment or wet-lab confirmation is warranted.
