# Cell Genomics Submission Package Draft

This draft tracks Cell Genomics submission-facing elements that are not part of the scientific Results narrative. It is intentionally conservative: identifiers, author metadata, funding, and archival DOI fields remain `TBD` until the authors provide verified information.

## Highlights

- Primate lncRNA networks decouple node conservation from edge conservation
- 804,630 lncRNA–PCG relationships reconstructed across four primates
- Four-species shared edges (8,799) exceed target-permutation null p95 (~107)
- Trait-centered subnetworks nominate obesity-linked lncRNAs for follow-up

## In Brief

This study reconstructs orthology-aware, triplex-informed lncRNA–gene candidate networks across four primates and shows that conserved molecular nodes do not imply conserved candidate edges. External evidence layers and reviewer-facing manifests benchmark prioritization, reproducibility, and follow-up nominations without claiming causal evidence.

## eTOC Blurb

Use the In Brief text above as the eTOC blurb unless the submission portal requests a shorter variant.

## Graphical Abstract Concept

Concept only; no image asset is claimed here. The graphical abstract should show a left-to-right flow:

1. Trait-associated lncRNA and PCG node catalogs.
2. Orthology-aware triplex-informed edge reconstruction across four primates.
3. Node conservation versus edge conservation and rewiring.
4. External evidence layers for module benchmarking and contextualization.
5. Reviewer package and Human LncRNA Atlas Companion for evidence inspection.

## Key Resources Table Draft

| REAGENT or RESOURCE | SOURCE | IDENTIFIER | NOTES |
| --- | --- | --- | --- |
| **Software and algorithms** |  |  |  |
| Human LncRNA Atlas code | GitHub repository | Commit SHA recorded in manuscript; release tag TBD | Rebuild scripts, source code, reviewer package |
| Figure-generation scripts | Repository-local scripts | `scripts/paper/rebuild_cellgenomics_package.py --skip-manuscript` | Rebuilds Figure 3E, Figure 6, manifests, and reviewer tables |
| Cell CSL | Cell Press / Cell Genomics citation style | `docs/paper/cell.csl` | Active manuscript CSL for submission-prep rendering |
| **Deposited data** |  |  |  |
| Figure-panel manifest | Repository export | `paper_figures/cell_genomics_manifest.tsv` | Figure provenance and output traceability |
| External evidence manifest | Repository export | `paper_figures/cell_genomics_external_data_manifest.tsv` | Processed GTEx / ENCODE / GO provenance |
| GTEx v8 median expression summaries | Processed repository input | TBD source accession / processed path | PCG target-program expression context |
| ENCODE RNA-seq input slot | Repository-frozen processed slot | TBD source accession / processed path | Cell-line expression context when available; not direct regulation evidence |
| GO biological-process annotations | Processed repository input | TBD source accession / processed path | GO coherence benchmarking |
| Zenodo/Figshare DOI | Zenodo/Figshare archive | TBD | Do not claim an archival DOI until the deposit exists |
| **Other** |  |  |  |
| Human LncRNA Atlas Companion | Repository-local backend / local-only companion interface | No public URL; local OpenAPI `/docs` | Evidence-inspection layer rather than primary result |

## Required Submission Metadata

- Title: `Triplex-informed lncRNA–gene candidate networks reveal edge-level conservation and rewiring across primates`
- Authors, affiliations, and ORCID IDs: TBD by authors.
- Lead Contact: TBD by authors.
- Corresponding author email: TBD by authors.
- Author Contributions: TBD using CRediT taxonomy.
- Acknowledgments: TBD.
- Funding: TBD.
- Competing Interests: TBD.

## Materials Availability

This is a computational study and no new physical reagents or biological materials are generated in the current manuscript package. Authors should confirm whether any internal datasets or processed archives require a materials-access statement before submission.

## Data and Code Availability

- GitHub repository: recorded in the manuscript Data and Code Availability section.
- Frozen commit SHA: recorded in the manuscript Data and Code Availability section.
- GitHub release tag: TBD, suggested `v1.0-cellgenomics-submission`.
- Zenodo/Figshare DOI: TBD; do not claim an archival DOI until the deposit exists.
- Reviewer rebuild command: `python3 scripts/paper/rebuild_cellgenomics_package.py --skip-manuscript`.
- Figure and evidence manifests: `paper_figures/cell_genomics_manifest.tsv` and `paper_figures/cell_genomics_external_data_manifest.tsv`.

## Zenodo / Release Checklist

Do not execute these steps until the submitting author confirms repository ownership and archive settings.

1. Confirm the frozen commit SHA in the manuscript still matches the intended reviewer package.
2. Create a GitHub release tag, suggested `v1.0-cellgenomics-submission`.
3. Archive the release through Zenodo or Figshare.
4. Record the DOI in the manuscript Data and Code Availability statement.
5. Record the DOI in this submission package and the cover letter.
6. Re-render `docs/paper/build/manuscript_rendered.md` and `.docx`.
7. Re-run the paper document tests before formal submission.

## Full Submission Robustness Checklist

These items must remain open before formal full submission until the corresponding data, archive, or editorial decision is verified. Do not describe any item below as completed in the manuscript, cover letter, or Data and Code Availability statement until the underlying result exists.

1. Replace the provisional archival-release wording with a real Zenodo/Figshare DOI after deposit.
2. Confirmed current Supplementary Figure 7E values: 228 (203-254) observed four-species shared core-pair edges versus matched null p95 7. Re-verify if the marmoset edge set or random seed is regenerated before formal submission.
   Current supplementary title to preserve: "Robustness analyses for edge-level conservation, rewiring, degree structure, and species-coverage sensitivity."
3. Hub target-breadth normalization: current status is addressed via the Figure 2B legend caveat and Discussion Limitation 3. Consider quantitative transcript-length, repeat, GC, or triplex-motif-opportunity controls only if reviewers push back.
4. Attempt coordinate-based expression rescue for the obesity lead lncRNA; if no expression mapping is recovered, keep the obesity module as a representative prioritization case rather than a functional flagship.
5. Keep the Human LncRNA Atlas Companion positioned as local-only unless the authors provide and verify a public deployment URL before full submission.

## Cover Letter Draft

TBD. The cover letter should lead with the Resource/atlas contribution and conceptual advance that node conservation is not edge conservation, then summarize the four-primate network scale, Figure 3 null calibration, Figure 6 external benchmarking layers, and reviewer-facing reproducibility package. Insert the Zenodo/Figshare DOI only after the archive exists.

## Suggested Reviewers / Excluded Reviewers

- Suggested reviewers: TBD by authors.
- Excluded reviewers: TBD by authors.
- Conflict rationale: TBD by authors where applicable.

## Open Science / Inclusion and Diversity Statement

TBD by authors. This section should state data/code availability, reuse conditions, accessibility of reviewer artifacts, and any inclusion/diversity statement required by the submission portal without inventing policy compliance details.

## Figure 6 Evidence Decision

The current manuscript frames Figure 6 as external benchmarking and contextualization for prioritization, not experimental confirmation. Before formal initial submission, choose whether to add a new orthogonal evidence layer or maintain the current conservative evidence package:

1. Option A: add orthogonal RNA-chromatin or perturbation evidence, such as ENCODE eCLIP, CRISPRi, Perturb-seq, RIC-seq, iMARGI, or related public datasets.
2. Option B: maintain the current evidence package, with GO coherence as a supplementary benchmarking layer and conservative language that the analyses do not establish causal lncRNA regulation.

## Reference Formatting Checklist

- Manuscript frontmatter now points to `docs/paper/cell.csl` for Cell-style submission-prep rendering.
- Verify Ensembl and other resource references have complete metadata.
- Add primary mechanistic and RNA-chromatin assay references only after bibliographic details are checked.
