# Human LncRNA Atlas - Frontend

React frontend for the Human LncRNA Atlas database and visualization platform.

## Tech Stack

- **Framework**: React 19 + TypeScript
- **Build Tool**: Vite
- **UI Library**: Ant Design 6
- **State Management**: TanStack Query (React Query) v5
- **Routing**: React Router v7
- **i18n**: i18next (Chinese/English)
- **Charts**: ECharts 6
- **Network Graph**: Cytoscape.js
- **Genome Browser**: IGV.js

## Quick Start

```bash
# Install dependencies
npm ci

# Start development server
npm run dev

# Build for production
npm run build

# Run unit tests
npm run test:run

# Run E2E tests
npm run test:e2e
```

## Project Structure

```
src/
├── api/           # API client and endpoints
├── components/    # Shared UI components
├── hooks/         # Custom React hooks
├── pages/         # Page components
├── i18n/          # Internationalization
│   └── locales/   # Translation files (en, zh-CN)
├── types/         # TypeScript type definitions
├── utils/         # Utility functions
└── test/          # Test utilities
```

## Key Features

- **Gene Browser**: Search and explore lncRNA/protein-coding genes
- **Regulation Analysis**: View regulatory relationships with binding affinity
- **Genome Browser**: IGV.js integration for genomic visualization
- **ChIP-seq Overlap**: Visualize lncRNA-ChIP-seq peak overlaps
- **Network Visualization**: Cytoscape.js for gene-disease networks
- **Conservation Analysis**: Cross-species conservation patterns
- **Data Export**: CSV, Excel, and image export support

## Environment Variables

Create `.env.local` for local development:

```env
VITE_API_BASE_URL=http://localhost:8000
```

## Testing

```bash
# Unit tests
npm run test:run

# E2E tests (requires backend running)
npm run test:e2e

# E2E tests with UI
npm run test:e2e:ui

# Performance tests (requires backend + frontend running)
npm run test:performance
npm run test:performance:compare
```

## Build

```bash
npm run build
```

Build artifacts are output to `dist/`.
