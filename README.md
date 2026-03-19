# Human LncRNA Atlas

A cross-species lncRNA (long non-coding RNA) regulatory relationship database and visualization platform. This project integrates regulatory relationship data between lncRNAs and protein-coding genes across four primate species: Human, Chimpanzee, Macaque, and Marmoset.

## Features

- **Regulatory Relationship Query**: Multi-dimensional filtering by species, gene name, chromosome, binding affinity (BA)
- **Sequence Data Display**: View lncRNA and DNA target site sequences
- **Disease Association Analysis**: GWAS data integration for lncRNA-disease/trait associations
- **Network Visualization**: Interactive network visualization of regulatory relationships using Cytoscape.js
- **IGV Genome Browser**: Integrated genome browser with multi-species support
  - Genome assemblies: hg19 (Human), panTro5 (Chimpanzee), rheMac10 (Macaque), calJac3 (Marmoset)
  - Reference genomes optimized for IGV.js visualization
- **ChIP-seq Epigenetic Marks**: ENCODE histone peaks (8 core marks; see `docs/CURRENT_STATUS.md` for coverage/stats)
  - H3K27me3, H3K4me3, H3K4me2, H3K4me1, H3K27ac, H3K36me3, H3K9ac, H3K9me3
  - Bivalent domain detection (H3K27me3 + H3K4me3)
  - Multi-mark comparison and visualization
- **DNase-seq Open Chromatin**: ENCODE DNase-HS peaks (~1.22M peaks, 7 cell lines; see `docs/CURRENT_STATUS.md`)
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
- **Framework**: React 19 + TypeScript
- **Build Tool**: Vite
- **UI Library**: Ant Design 6
- **State Management**: TanStack Query (React Query)
- **Routing**: React Router v7
- **i18n**: i18next (Chinese/English)
- **Charts**: ECharts 6
- **Network Graph**: Cytoscape.js

## Status / Roadmap

- Docs index (dev/maintainers): `docs/README.md`
- Current status: `docs/CURRENT_STATUS.md`
- Roadmap (1–2 weeks): `docs/ROADMAP_2026-02-03.md`
- CI / self-hosted runner guide: `docs/CI_SELF_HOSTED_RUNNER.md`

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
- PostgreSQL 15+
- Redis (optional, for caching)

CI reference (GitHub Actions): Python 3.11 + Node.js 20 (see `.github/workflows/test.yml`).

### Install PostgreSQL (Ubuntu/Debian)

If you don't have PostgreSQL installed locally (Ubuntu/Debian only):

```bash
./scripts/install_postgresql.sh
```

Notes:
- Requires root/sudo privileges.
- Creates a PostgreSQL role matching your OS user by default (override via `APP_DB_USER`).
- In non-interactive environments, the script exits safely to avoid hanging on sudo prompts (use `ASSUME_YES=yes` only if you know what you're doing).

### PostgreSQL Extensions (recommended)

Some SQL scripts create/require PostgreSQL extensions. You may need elevated privileges (or enable them in managed PostgreSQL):

- `pgcrypto` (required): used by `schema/v2.3/01_core.sql` for `gen_random_uuid()`
- `pg_trgm` (optional): used by `frontend/backend/migrations/001_pg_trgm_indexes.sql` for faster `ILIKE` fuzzy search
- `btree_gist` (optional): used by `frontend/backend/sql/chipseq_schema.sql` and overlap MVs for composite GiST indexes

### One-command (local/LAN)

```bash
./scripts/dev.sh
```

This will auto-inject LAN-friendly defaults (`TRUSTED_HOSTS`, `CORS_ORIGINS`, `VITE_API_BASE_URL`) and enable private-IP rate-limit bypass for local development (`RATE_LIMIT_BYPASS_PRIVATE=true`).

If you access via a public IP/domain and see `Invalid host header`, pass it explicitly:

```bash
PUBLIC_HOST=<public-ip-or-domain> ./scripts/dev.sh
```

If you are behind FRP/NAT and the public ports differ from local ports, set them too:

```bash
PUBLIC_HOST=<public-ip-or-domain> PUBLIC_FRONTEND_PORT=6003 PUBLIC_BACKEND_PORT=6004 ./scripts/dev.sh
```

Quick self-check (backend):

```bash
curl -s http://<public-ip-or-domain>:<public-backend-port>/health | python3 -m json.tool
curl -s http://<public-ip-or-domain>:<public-backend-port>/ | python3 -m json.tool
```

Tip: if the homepage shows very small numbers (e.g. `Total Genes=12`, `lncRNA=2`), your backend is likely
using the perf baseline DB (`lncrna_baseline`, used by `scripts/baselines/*`). To run against the full DB
(`lncrna_production`), confirm `/` returns `db_mode=baseline`/`db_name=lncrna_baseline`, then start backend
on another port and point the frontend to it, for example:

```bash
BACKEND_PORT=8001 ./scripts/dev.sh
```

Stop services:

```bash
./scripts/stop.sh
```

Show status (ports / PID):

```bash
./scripts/stop.sh -s
```

### Docker (production-like)

```bash
cp .env.example .env
# edit .env (DB_PASSWORD / ADMIN_API_KEY / TRUSTED_HOSTS / CORS_ORIGINS)
docker compose up -d
```

数据库用户约定：
- `.env` / 后端运行时里的 `DB_USER` 表示应用连接数据库时使用的账号。
- `scripts/init_db.sh`、`scripts/refresh_materialized_views.sh` 这类维护脚本可以单独传 `DB_USER=postgres`（或别的高权限维护账号），因为建库、安装扩展、刷新 MV 需要更高权限。
- 不建议把两类场景强行统一成同一个默认值；关键是按职责选择正确账号。

### Backend Setup

```bash
cd frontend/backend
python3 -m pip install -r requirements.txt -c constraints.txt
# For development/testing (pytest/ruff):
# python3 -m pip install -r requirements-dev.txt -c constraints.txt
python3 -m uvicorn main:app --host 0.0.0.0 --port 8000
```

### Frontend Setup

```bash
cd frontend/web
npm ci
npm run dev -- --host 0.0.0.0
```

前端环境变量说明：
- `VITE_API_BASE_URL` 只能填写站点 origin，例如 `http://localhost:8000` 或 `https://your-domain.com`。
- 不要把 `/api` 或 `/api/v1` 拼进 `VITE_API_BASE_URL`，因为前端请求路径本身已经包含 `/api/v1`。
- `frontend/web/.env.example` 已按这个约定更新。

ChIP-seq Compare 页面说明：
- `/chipseq-compare` 当前是一个诚实的状态页，不再展示 mock 图表。
- 现有后端只支持 gene-scoped ChIP-seq 接口（`/api/v1/features/chipseq/genes/{gene_id}/...`）。
- 如需真实数据，请从基因级 ChIP-seq 页面进入 compare / heatmap / export 流程。

### Access

**Note**: Replace `<server-ip>` with your server's IP address.

| Service | Local | Network (LAN) |
|---------|-------|---------------|
| Frontend | http://localhost:5173 | http://<server-ip>:5173 |
| API Docs | http://localhost:8000/docs | http://<server-ip>:8000/docs |

### CI / Quality Gates (recommended before push)

These match the checks in `.github/workflows/test.yml`.

```bash
# One-shot (mirrors CI core checks, excluding secret scan / security-audit)
./scripts/run-tests.sh ci
# Note: does NOT require PostgreSQL/Redis (unit tests + import/syntax checks only).
# Note: if you use a backend venv at `frontend/backend/.venv` or `frontend/backend/venv`,
#       the script will auto-run `pip install -r requirements-dev.txt -c constraints.txt`
#       when those files drift (e.g. after `git pull` dependency updates).
#
# CI also runs two additional smoke jobs (see `.github/workflows/test.yml`):
# - Playwright E2E smoke (fully mocked, no backend/DB): `e2e-smoke`
# - ETL E2E smoke (PostgreSQL 15+ service, sample import): `etl-e2e-smoke`
#
# Reproduce CI Playwright smoke locally (no backend/DB):
./scripts/run-tests.sh e2e-smoke

# Docs-only (fast fail: check for drift in startup command examples)
./scripts/run-tests.sh docs-check

# Frontend
cd frontend/web
npm ci
npm run test:run
npm run lint
npm run build

# Backend
cd frontend/backend
python3 -m pip install -r requirements-dev.txt -c constraints.txt
ruff check .
pytest -m unit -v
python3 -c "import main"
python3 -m py_compile main.py
find app -name "*.py" -exec python3 -m py_compile {} \;
```

Optional (recommended before push): install a local pre-push hook that runs the CI gate automatically.

```bash
bash scripts/install_git_hooks.sh
```

Skip once with `git push --no-verify`, or set `SKIP_LOCAL_CI=1 git push`. To run a lighter gate, use `LOCAL_CI_TARGET=smoke git push`. To include Playwright smoke, use `LOCAL_CI_TARGET=ci-plus git push` (or `ci-full` for the strictest gate).

GitHub Actions CI 默认对 `main` 分支 `push` 自动触发（`Tests`），`Security Audit` 会在依赖清单变化时自动触发；也支持 `workflow_dispatch` 手动触发。

出于安全考虑，PR CI（`pull_request`）默认不启用（避免在 self-hosted runner 上执行不受信任代码）。

If you trigger a workflow run manually, you can check the latest run with:

```bash
gh run list --limit 1
```

If a workflow fails to start with an annotation like:

> The job was not started because recent account payments have failed or your spending limit needs to be increased

then GitHub Actions is blocked by billing/spending limits. Fix it in GitHub **Settings → Billing & plans**, or run the same checks locally via `./scripts/run-tests.sh ci` (and optionally `./scripts/run-tests.sh e2e-smoke`).

Self-hosted runner fallback (does not consume GitHub Actions minutes): see `docs/CI_SELF_HOSTED_RUNNER.md`.
If your local `git push` / `git fetch` is unstable due to network/proxy constraints, see `docs/CI_SELF_HOSTED_RUNNER.md` (Section “6.2”: proxy one-liners + GitHub API fallback push via `scripts/gh_push_commit.py`).

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

### Materialized Views (Optional, for Performance)

Some endpoints are significantly faster when the optional PostgreSQL materialized views exist (cache-miss latency, large exports, heavy aggregations).

```bash
# Analysis summary (High Affinity section, BA >= 100)
psql -d lncrna_production -f schema/v2.3/07_mv_analysis_summary_high_affinity_ba100.sql

# ChIP-seq schema (tables + optional dashboard MVs)
psql -d lncrna_production -f frontend/backend/sql/chipseq_schema.sql

# Overlaps MV (may take a while on full data)
psql -d lncrna_production -f schema/v2.3/05_mv_lncrna_chipseq_overlaps.sql

# Epigenetic summary MV (BA >= 100) for /analysis/summary
psql -d lncrna_production -f schema/v2.3/06_mv_lncrna_chipseq_overlaps_epigenetic_summary_ba100.sql

# Refresh managed MVs (weekly or after ETL)
./scripts/refresh_materialized_views.sh

# Admin API (optional): check status / trigger refresh (requires X-Admin-API-Key)
curl -H "X-Admin-API-Key: <ADMIN_API_KEY>" "http://localhost:8000/api/v1/admin/materialized-views/status"
curl -X POST -H "X-Admin-API-Key: <ADMIN_API_KEY>" -H "Content-Type: application/json" \
  "http://localhost:8000/api/v1/admin/materialized-views/refresh" \
  -d '{"concurrently": true, "timeout_seconds": 600}'

# Optional: ETL post-run backend notify (best-effort)
# Enable cache invalidation and (optionally) refresh materialized views after ETL scripts finish.
export HLA_NOTIFY_BACKEND=true
export HLA_BACKEND_URL="http://localhost:8000"
export HLA_ADMIN_API_KEY="<ADMIN_API_KEY>"
# Optional (default=false): trigger MV refresh (can take a while)
export HLA_REFRESH_MATERIALIZED_VIEWS=true
export HLA_MV_REFRESH_TIMEOUT_SECONDS=600
```

Frontend Admin pages (require Admin access):
- `/admin/monitoring` - JSON monitoring dashboard
- `/admin/cache` - cache management (stats/reset/invalidate/clear)
- `/admin/materialized-views` - MV status + refresh controls

More details:
- `docs/backend/OVERLAP_MATERIALIZED_VIEW.md` - overlap MV (`mv_lncrna_chipseq_overlaps`) create/refresh + `QUERY_TOO_BROAD` troubleshooting

### IGV Offline Genome Assets (Optional)

If you want IGV.js to avoid external network dependencies (UCSC/GitHub) and run fully offline, place genome assets under `GENOMES_DIR` (served by backend as `/genomes`).

```bash
# Core hg19 assets (2bit / cytoband / chrom.sizes / alias table)
GENOMES_DIR="/path/to/genomes" ./scripts/genomes/download_hg19_igv_assets.sh

# Optional: download conservation BigWig (large files)
./scripts/genomes/download_hg19_igv_assets.sh --with-conservation "/path/to/genomes"

# Other UCSC assemblies (examples)
./scripts/genomes/download_hg19_igv_assets.sh --assembly panTro5 "/path/to/genomes"
./scripts/genomes/download_hg19_igv_assets.sh --assembly rheMac10 "/path/to/genomes"
./scripts/genomes/download_hg19_igv_assets.sh --assembly calJac3 "/path/to/genomes"

# Optional: write a manifest (bytes + SHA256; large-file SHA256 is opt-in)
./scripts/genomes/download_hg19_igv_assets.sh --write-manifest "/path/to/genomes"
./scripts/genomes/download_hg19_igv_assets.sh --write-manifest --hash-large-files "/path/to/genomes"
```

Optional SHA256 verification (fails fast if mismatch):

```bash
# Prefix rule: <ASSEMBLY> uppercased, non-alnum removed (hg19 -> HG19, panTro5 -> PANTRO5)
export HG19_2BIT_SHA256="<64-hex>"
export HG19_CYTOBAND_SHA256="<64-hex>"
export HG19_CHROMSIZES_SHA256="<64-hex>"
export HG19_ALIAS_SHA256="<64-hex>"
export HG19_PHASTCONS_SHA256="<64-hex>"
export HG19_PHYLOP_SHA256="<64-hex>"
```

### ETL Input Manifest (Optional)

Create a small, portable baseline for external input files (bytes/lines/SHA256), then verify before running ETL imports:

```bash
# Build a manifest (record lines/SHA256 only when you need strong verification)
python3 -m etl.input_manifest build --output etl-inputs.manifest.tsv --lines --sha256 \
  /path/to/input1.tsv /path/to/input2.tsv

# Verify (fails fast on mismatch)
python3 -m etl.input_manifest verify etl-inputs.manifest.tsv
```

Optional: let ETL import scripts run the same verification automatically before connecting to the DB:

```bash
# Example (regulations import)
python3 etl/import_regulations.py --file /path/to/input1.tsv --input-manifest etl-inputs.manifest.tsv --user "$DB_USER"
```

### API Snapshot Baseline (Optional)

Verify a deterministic API snapshot baseline against the sample dataset (useful regression anchor for refactors):

```bash
# Docker Compose (isolated, loads schema/v2.3/03_sample_data.sql automatically)
python3 scripts/verify_baselines.py --mode docker

# If you already have a backend running
python3 scripts/verify_baselines.py --mode running --base-url http://localhost:8000
```

CI also runs this baseline check (see `.github/workflows/test.yml`, job `api-snapshot-baseline`).

## API Endpoints

| Endpoint | Method | Description |
|----------|--------|-------------|
| `/api/v1/genes` | GET | Gene list (paginated) |
| `/api/v1/genes/options` | GET | Gene options (lightweight, for selectors) |
| `/api/v1/genes/batch` | POST | Batch resolve genes by identifiers |
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

# Backend lint (Ruff)
./scripts/run-tests.sh backend-lint

# Backend tests only
cd frontend/backend && pytest tests/test_api_contracts.py -v

# Frontend typecheck (TypeScript)
cd frontend/web && npm run typecheck

# Frontend unit tests
cd frontend/web && npm run test:run

# E2E tests
cd frontend/web && npm run test:e2e

# Note: Some E2E specs include environment-dependent performance assertions.
# You can override budgets via E2E_* env vars (see docs/testing/e2e/README.md).
```

Minimal end-to-end database bootstrap (creates `lncrna_e2e_test` and loads `schema/v2.3/03_sample_data.sql`):

```bash
# The script will prompt before DROP DATABASE; for non-interactive use set ALLOW_DROP_DB=true
ALLOW_DROP_DB=true DB_USER=postgres ./scripts/end_to_end_test.sh
```

Recommended (starts backend+frontend in test mode, then runs Playwright):

```bash
./scripts/e2e.sh
```

Performance baseline (EXPLAIN for hot SQL queries, requires PostgreSQL + data):

```bash
cd frontend/backend && ./.venv/bin/python scripts/explain_hot_queries.py
```

## Troubleshooting

- `ERR_CONNECTION_REFUSED` when opening `http://<server-ip>`: the frontend is on `:5173` by default → open `http://<server-ip>:5173` and check status via `./scripts/stop.sh -s`.
- `http://<server-ip>` (port 80/443) shows `ERR_CONNECTION_REFUSED` or `502`: this repo does not start a reverse proxy by default → access `http://<server-ip>:5173` (frontend) / `http://<server-ip>:8000/docs` (backend), or set up Nginx/Caddy to proxy 80/443 to those ports.

## License

MIT License

## Contributing

Pull requests are welcome. For major changes, please open an issue first to discuss what you would like to change.
