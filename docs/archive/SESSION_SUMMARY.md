# Multi-Species lncRNA Regulatory Network Analysis - Session Summary

## Overview

This document summarizes the comprehensive work on multi-species closed regulatory network analysis for disease-associated genes, focusing on autism spectrum disorder, neuroblastoma, and hepatocellular carcinoma.

**Date**: 2025-11-19
**Working Directory**: `<data-root>/humanLncAtlas/`
**Main Script**: `draw_multispecies_network.py`
**Total Networks Generated**: 23 images (4 autism + 12 neuroblastoma + 11 HCC)

---

## Critical User Requirements

1. **No Rework Tolerance**: User emphasized multiple times: "ultrathink，再仔细确认一下，跑这些要很久，我不想再返工了"
2. **No ID Truncation**: "肯定不能截断，截断了会误导别人" - Gene IDs must never be truncated
3. **Complete Gene Names**: All genes must display proper gene names (e.g., RP11-13K12.1, CTA-211A9.5) rather than IDs
4. **Production Quality**: All code must be thoroughly reviewed before execution due to high computational cost

---

## Key Technical Concepts

### Closed Network Logic
- **Definition**: Only shows regulatory relationships within the gene set specified in table15
- **Example**: Autism MTG has 49 genes → network only shows regulations among these 49 genes, NOT all possible targets
- **Implementation**: Filters both lncRNAs and targets to ensure both exist in the specified gene set

### Species Mapping
- **Human**: Reference species, gene names as-is
- **Chimp/Macaque/Marmoset**: Ortholog mapping via core_id, gene names get `_species` suffix
- **Marmoset Special Case**: Ortholog table has `_marmoset` suffix, BA files don't → code uses `replace('_marmoset', '')`

### Binding Affinity (BA)
- **Threshold**: 50 used across all analyses
- **Normalization**: Edge weights normalized using min-max scaling
- **Edge Case**: When all BA values equal → use constant 0.5 to avoid division by zero

### Dual-Role lncRNAs
- **Issue**: Some lncRNAs both regulate genes AND are regulated by other lncRNAs
- **Examples**: ENSG00000267506.1 (RP11-13K12.1), ENSG00000269998.1 (RP11-272L13.3)
- **Solution**: Check `lnc_to_core` first when processing targets, then fall back to `gene_to_core`

---

## Files and Data

### Main Script
**`<data-root>/humanLncAtlas/draw_multispecies_network.py`**
- Generates 4-species closed regulatory networks
- Creates 20×20 inch PNG files with statistics panels, colorbars, and legends
- Handles ortholog mapping, gene name display, and edge weight normalization

### Input Data
1. **`<data-root>/standard_data/table15_normalized_full.csv`**
   - 67,763 rows of trait-gene associations
   - Used to identify disease-specific gene sets

2. **Ortholog Tables**:
   - Human-Chimp: `<data-root>/standard_data/human_chimp_orthologs.csv`
   - Human-Macaque: `<data-root>/standard_data/human_macaque_orthologs.csv`
   - Human-Marmoset: `<data-root>/standard_data/human_marmoset_orthologs.csv`

3. **Binding Affinity Files**:
   - Human: `human_batch_human.txt`
   - Chimp: `chimp_batch_BA50.txt`
   - Macaque: `macaque_batch_BA50.txt`
   - Marmoset: `marmoset_batch_BA50.txt`

4. **Gene Name Mappings**:
   - lncRNA: `<data-root>/standard_data/human_lncRNA_id_to_name.csv`
   - Coding: `<data-root>/standard_data/human_gene_id_to_name.csv`

### Generated Files

**Cancer Trait Analysis**:
- `cancer_traits_summary.csv` - 30 cancer-related traits (4,588 records, 794 genes)
- `neuroblastoma_ontology_breakdown.csv` - 13 tissue/cell types
- `hcc_ontology_breakdown.csv` - 19 tissue/cell types

**Network Images (23 total)**:

*Autism Spectrum Disorder + Middle Temporal Gyrus (4 images)*:
- `autism_4species_MTG_closed_network_human.png` (13MB)
- `autism_4species_MTG_closed_network_chimp.png`
- `autism_4species_MTG_closed_network_macaque.png`
- `autism_4species_MTG_closed_network_marmoset.png`
- **Gene Set**: 49 genes (18 lncRNA + 31 coding)

*Neuroblastoma (12 images)*:
- T cell: 4 species × `neuroblastoma_Tcell_network_*.png`
- NK cell: 4 species × `neuroblastoma_NK_network_*.png`
- Thymus: 4 species × `neuroblastoma_thymus_network_*.png`

*Hepatocellular Carcinoma (11 images)*:
- B cell: 4 species × `HCC_Bcell_network_*.png`
- Monocyte: 4 species × `HCC_monocyte_network_*.png`
- Leukocyte: 3 species × `HCC_leukocyte_network_*.png` (macaque has 0 regulations)

---

## Critical Bugs Fixed

### 1. Division by Zero in Edge Weight Normalization
**Location**: Lines 356-366
**Problem**: When all BA values are equal, `(max - min) = 0` causes NaN
**Fix**:
```python
weight_range = edge_weights.max() - edge_weights.min()
if weight_range > 0:
    edge_norm = (edge_weights - edge_weights.min()) / weight_range
else:
    edge_norm = np.full(len(edge_weights), 0.5)  # All edges equal
```

### 2. Gene ID Truncation Causing Misleading Labels
**Location**: Lines 401-404, 430-433
**Problem**: `CATG00000074991` truncated to `CATG00000074` (first 12 chars)
**User Feedback**: "CATG00000074，这个基因ID就是这个吗，没有被截断把" → "肯定不能截断，截断了会误导别人"
**Fix**: Removed all `[:12]` truncation, only remove version numbers (`.1`, `.7`)

### 3. Gene Names with '.' Being Incorrectly Split
**Problem**: `CTA-211A9.5_chimp` → `split('.')[0]` → `CTA-211A9` (lost `.5` and `_chimp`)
**Fix**: Only split '.' for IDs starting with ENSG/CATG:
```python
if label.startswith('ENSG') or label.startswith('CATG'):
    if '.' in label:
        label = label.split('.')[0]
```

### 4. Dual-Role lncRNAs Losing Gene Names
**Location**: Lines 268-296
**Problem**: `ENSG00000267506.1` and `ENSG00000269998.1` showed as IDs instead of gene names
**Root Cause**: When appearing as targets, `gene_to_core` lookup failed (only contains coding genes)
**Fix**: Check `lnc_to_core` first for targets, then fall back to `gene_to_core`

### 5. Network Statistics and Colorbar Overlapping Nodes
**User Feedback**: "network statistics遮挡了节点；遮挡了lncRNA和target的注释"
**Fix**:
- Moved Statistics from ax.text to fig.text at (0.02, 0.96)
- Moved colorbar to top-right (bottom=0.71, aligned with statistics)
- Moved legend to lower left

### 6. Docstring Inconsistency
**Location**: Lines 120-127
**Problem**: `get_trait_genes()` said returns 3 values, actually returns 2
**Fix**: Updated docstring to match implementation

---

## Example Command Usage

### Basic Network Generation
```bash
python3 draw_multispecies_network.py \
  --trait "autism spectrum disorder" \
  --ontology "middle temporal gyrus" \
  --min-ba 50 \
  --human-ba human_batch_human.txt \
  --chimp-ba chimp_batch_BA50.txt \
  --macaque-ba macaque_batch_BA50.txt \
  --marmoset-ba marmoset_batch_BA50.txt \
  --output autism_4species_MTG_closed_network.png
```

### Output Statistics Example (Autism MTG - Human)
```
Network Statistics:
• Trait    : autism spectrum disorder
• Ontology : middle temporal gyrus
• Species  : human
• Total Genes        : 49
• lncRNA Regulators  : 18
• Target Genes       : 31
• Regulations        : 341
• Min BA    : 50.03
• Max BA    : 80.69
• Median BA : 55.18
```

---

## Key Findings

### Cancer Trait Analysis
- **30 cancer-related traits** identified from table15
- **4,588 total records** involving **794 unique genes**
- **Top traits by record count**:
  1. Neuroblastoma: 514 records, 74 genes
  2. Hodgkin's lymphoma: 478 records, 67 genes
  3. Chronic lymphocytic leukemia: 353 records, 78 genes

### Neuroblastoma Ontology Breakdown
- **13 tissue/cell types**, ALL immune cells
- **Recommended for analysis**: T cell (53 genes), NK cell (44 genes), Thymus (44 genes)

### Hepatocellular Carcinoma Ontology Breakdown
- **19 tissue/cell types**, ALL immune cells (NO liver tissue)
- **Key observation**: Reflects tumor microenvironment, not liver cells
- **Recommended for analysis**: B cell (25 genes), Monocyte (22 genes), Leukocyte (22 genes)
- **Data gap**: Macaque has 0 regulations for HCC + leukocyte

---

## Network Complexity Across Species

### Autism Spectrum Disorder + Middle Temporal Gyrus
| Species | lncRNAs | Targets | Regulations | Min BA | Max BA | Median BA |
|---------|---------|---------|-------------|--------|--------|-----------|
| Human | 18 | 31 | 341 | 50.03 | 80.69 | 55.18 |
| Chimp | 12 | 20 | 89 | 50.01 | 63.74 | 52.49 |
| Macaque | 9 | 15 | 38 | 50.01 | 59.41 | 52.14 |
| Marmoset | 5 | 9 | 10 | 50.36 | 56.94 | 52.77 |

**Observation**: Network complexity decreases with evolutionary distance from human

---

## Code Quality Validation

Performed systematic 7-category review:
1. ✅ **Data Flow Integrity**: All file paths, ortholog mappings, and BA lookups verified
2. ✅ **Closed Network Logic**: Confirmed both lncRNAs and targets are filtered
3. ✅ **Cross-Species Consistency**: Ortholog mapping and suffix handling validated
4. ✅ **Gene Name Mapping**: Dual-role lncRNA handling, version number removal
5. ✅ **Edge Case Handling**: Division by zero, missing orthologs, empty networks
6. ✅ **Graphical Elements**: Statistics panel, colorbar, legend positioning
7. ✅ **End-to-End Testing**: Full autism MTG pipeline validated

---

## Next Steps (Not Yet Executed)

Potential future work:
1. Generate networks for other high-record cancer traits:
   - Hodgkin's lymphoma (478 records, 67 genes)
   - Chronic lymphocytic leukemia (353 records, 78 genes)
   - Lung carcinoma (245 records)

2. Comparative analysis:
   - Network topology differences across cancer types
   - Evolutionary conservation patterns
   - Binding affinity distribution analysis

3. Code improvements:
   - Add CLI parameters for ortholog table paths (currently hardcoded)
   - Fix tight_layout warning with colorbar
   - Add option for non-closed networks

---

## Important Notes

1. **Marmoset Data Constraint**: All marmoset genes are subsets of human genes (1,299 core_ids all exist in human)

2. **Gene ID Format**:
   - Human lncRNA: CATG00000000001.1 (with version)
   - Human coding: ENSG00000000001.1 (with version)
   - Gene names: May contain '.' (e.g., CTA-211A9.5, RP11-13K12.1)

3. **Network Interpretation**:
   - Red nodes: lncRNA regulators
   - Green nodes: Target genes
   - Edge color: Binding affinity (purple=low, yellow=high)
   - Edge thickness: Binding affinity magnitude

4. **File Sizes**:
   - Human networks are largest (most regulations) ~13MB
   - Marmoset networks are smallest ~1-2MB

---

## User Feedback History

1. "ultrathink，再仔细审查一下，返工代价很大"
2. "把性状里面和肿瘤相关的性状找出来"
3. "CATG00000074，这个基因ID就是这个吗，没有被截断把" → Led to fixing truncation bug
4. "ultrathink，怎么回事，ENSG00269、267没有gene name吗" → Led to fixing dual-role lncRNA bug
5. "肯定不能截断，截断了会误导别人" → Confirmed strict no-truncation requirement
6. Detailed code review with 6-point feedback → Led to fixing statistics panel positioning

---

## Execution Environment

- **Platform**: Linux 5.15.0-46-generic
- **Python**: 3.x with NetworkX, Matplotlib, Pandas, NumPy
- **Working Directory**: `<data-root>/humanLncAtlas/`
- **Data Location**: `<data-root>/standard_data/`

---

## Session Completion Status

**All explicitly requested work completed**:
- ✅ Comprehensive code review (7 categories)
- ✅ 6 critical bugs fixed
- ✅ 30 cancer traits identified and documented
- ✅ 23 network images generated (autism, neuroblastoma, HCC)
- ✅ Session summary documentation created

**No pending tasks**.
