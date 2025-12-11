# Human LncRNA Atlas

A cross-species lncRNA (long non-coding RNA) regulatory relationship database and visualization platform. This project integrates regulatory relationship data between lncRNAs and protein-coding genes across four primate species: Human, Chimpanzee, Macaque, and Marmoset.

## Features

- **Regulatory Relationship Query**: Multi-dimensional filtering by species, gene name, chromosome, binding affinity (BA)
- **Sequence Data Display**: View lncRNA and DNA target site sequences
- **Disease Association Analysis**: GWAS data integration for lncRNA-disease/trait associations
- **Network Visualization**: Interactive network visualization of regulatory relationships using Cytoscape.js
- **IGV Genome Browser**: Integrated genome browser with multi-species support (hg19, panTro4, rheMac8, calJac3)
- **ChIP-seq Epigenetic Marks**: Real ENCODE data integration (K562, 6 marks, 422K peaks)
  - H3K27me3, H3K4me3, H3K4me1, H3K27ac, H3K36me3, H3K9me3
  - Bivalent domain detection (H3K27me3 + H3K4me3)
  - Multi-mark comparison and visualization
- **DNase-seq Open Chromatin**: ENCODE DNase-HS data (1.22M peaks, 76 cell lines)
  - Pre-indexed bigBed (`/genomes/dnase_hs_peaks.bb`) for optimal IGV.js region streaming
  - "Open Chromatin" category in genome browser track selector（ChIP-seq toggle → DNase-HS）
- **RepeatMasker Annotations**: 5.48M repeat elements (hg19)
- **Data Export**: CSV/XLSX export support

## Tech Stack

### Backend
- **Framework**: FastAPI
- **ORM**: SQLAlchemy 2.0
- **Validation**: Pydantic v2
- **Database**: PostgreSQL
- **Caching**: Redis (optional)

### Frontend
- **Framework**: React 18 + TypeScript
- **Build Tool**: Vite
- **UI Library**: Ant Design 5
- **State Management**: TanStack Query (React Query)
- **Routing**: React Router v6
- **i18n**: i18next (Chinese/English)
- **Charts**: ECharts
- **Network Graph**: Cytoscape.js

## Project Structure

```
human-lncrna-atlas/
├── docs/                          # Documentation
├── etl/                           # Data import scripts
│   ├── import_regulations.py      # Regulatory relationship import
│   ├── import_sequences.py        # Sequence data import
│   ├── import_ortholog_data.py    # Ortholog gene import
│   └── import_table15.py          # Disease data import
├── frontend/
│   ├── backend/                   # FastAPI backend
│   │   ├── app/
│   │   │   ├── core/              # Config and database
│   │   │   ├── models/            # SQLAlchemy ORM models
│   │   │   ├── routers/           # API routers
│   │   │   ├── schemas/           # Pydantic schemas
│   │   │   └── middleware/        # Middleware
│   │   └── main.py                # FastAPI entry point
│   └── web/                       # React frontend
│       └── src/
│           ├── api/               # API client
│           ├── components/        # Shared components
│           ├── hooks/             # Custom hooks
│           ├── pages/             # Page components
│           ├── i18n/              # Internationalization
│           └── types/             # TypeScript types
├── schema/                        # Database schema
├── scripts/                       # Utility scripts
└── tests/                         # Test files
```

## Quick Start

### Prerequisites
- Python 3.10+
- Node.js 18+
- PostgreSQL 14+
- Redis (optional, for caching)

### Backend Setup

```bash
cd frontend/backend
pip install -r requirements.txt
python3 -m uvicorn main:app --host 0.0.0.0 --port 8000
```

### Frontend Setup

```bash
cd frontend/web
npm install
npm run dev -- --host 0.0.0.0
```

### Access

| Service | Local | Network (LAN) |
|---------|-------|---------------|
| Frontend | http://localhost:5173 | http://192.168.6.135:5173 |
| API Docs | http://localhost:8000/docs | http://192.168.6.135:8000/docs |

**Server IP**: `192.168.6.135`

## Database

### Species Data Distribution

| Species | Code | Genes | Regulations |
|---------|------|-------|-------------|
| Human | human | ~5,484 | 496,064 |
| Chimpanzee | chimp | ~6,138 | 156,136 |
| Macaque | macaque | ~5,406 | 102,430 |
| Marmoset | marmoset | ~4,805 | 50,000 |

### Data Quality
- Total regulations: 804,630
- Sequences: 804,630 (100% coverage)
- Empty DNA sequences: 203 (0.025%) - located on unlocated scaffolds
- BA range: 50.0 - 756.0

## API Endpoints

| Endpoint | Method | Description |
|----------|--------|-------------|
| `/api/v1/genes` | GET | Gene list (paginated) |
| `/api/v1/genes/{id}` | GET | Gene details |
| `/api/v1/regulations` | GET | Regulation list (multi-filter) |
| `/api/v1/regulations/{id}` | GET | Regulation details with sequences |
| `/api/v1/stats/overview` | GET | Statistics overview |
| `/api/v1/diseases` | GET | Disease/trait list |
| `/api/v1/network/gene/{id}` | GET | Gene network data |

## Testing

```bash
# Run all tests
./scripts/run-tests.sh all

# Backend tests only
cd frontend/backend && pytest tests/test_api_contracts.py -v

# Frontend unit tests
cd frontend/web && npm run test:run

# E2E tests
cd frontend/web && npm run test:e2e
```

## License

MIT License

## Contributing

Pull requests are welcome. For major changes, please open an issue first to discuss what you would like to change.
