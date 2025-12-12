# Phase 6.0-B Jupyter Notebooks Guide

**Project**: Human LncRNA Atlas
**Phase**: Phase 6.0-B (Research Data Analysis)
**Updated**: 2025-12-12
**Status**: All Notebooks Ready (English version)

---

## Notebooks Overview

| Notebook | Analysis Topic | Expected Output |
|----------|---------------|-----------------|
| `01_high_affinity_analysis.ipynb` | High-affinity regulatory network | Top 100 lncRNA + Network graphs |
| `02_conservation_patterns.ipynb` | Cross-species conservation | Conservation heatmap + Statistics |
| `03_epigenetic_marks.ipynb` | Epigenetic mark associations | Bivalent domain analysis |
| `04_disease_networks.ipynb` | Disease association networks | Therapeutic target ranking |

---

## Quick Start

### 1. Install Dependencies

```bash
cd /data/wenyujianData/human-lncrna-atlas-github/notebooks
pip install -r requirements.txt
pip install matplotlib-venn python-louvain
```

### 2. Start Jupyter

```bash
jupyter notebook --ip=0.0.0.0 --port=8888
```

### 3. Ensure Backend API is Running

```bash
cd /data/wenyujianData/human-lncrna-atlas-github/frontend/backend
python3 -m uvicorn main:app --reload --port 8000

# Test API
curl http://localhost:8000/health
```

---

## Species Name Mapping

All notebooks automatically convert Chinese species names from the database to English:

| Database (Chinese) | Display (English) |
|-------------------|-------------------|
| 人类 | Human |
| 黑猩猩 | Chimpanzee |
| 猕猴 | Macaque |
| 狨猴 | Marmoset |

This is handled by `SPECIES_MAP` in each notebook.

---

## Expected Output

### Data Files (results/)
- `top_100_high_affinity_lncrnas.xlsx` - Top 100 lncRNA ranking
- `network_nodes.csv` / `network_edges.csv` - Network data for Cytoscape
- `conservation_summary.xlsx` - Conservation statistics
- `diabetes_lncrna_targets.xlsx` - Disease-associated targets

### Figures (figures/)
- 16+ publication-quality figures (300 DPI)
- Distribution plots, heatmaps, network graphs, Venn diagrams

---

## Troubleshooting

### API Connection Error
```bash
# Check if backend is running
curl http://localhost:8000/health
```

### Memory Issues
```python
# Reduce LIMIT parameter
LIMIT = 1000  # Default is 10000
```

### Font Issues
All notebooks use `DejaVu Sans` font which supports standard ASCII characters.

---

**Updated**: 2025-12-12
**Version**: Phase 6.0-B (English)
