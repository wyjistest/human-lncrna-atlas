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

## i18n Loading Strategy

- 首屏只 eager 加载 `common`、`nav`、`home`
- 页面级 namespace 通过 `src/i18n/index.ts` 中的 `ensureNamespaces()` 按需动态导入
- 路由级懒加载统一使用 `src/i18n/lazyWithNamespaces.ts`，确保页面模块渲染前翻译资源已注册

对首屏性能敏感的改动，建议在提交前执行：

```bash
npm run build
node scripts/report-bundle-sizes.mjs --json "../../docs/baselines/frontend/bundle-sizes.baseline.json"
```

## Key Features

- **Gene Browser**: Search, filter, and batch query genes (with CSV export)
- **Regulation Analysis**: View regulatory relationships with binding affinity
- **Genome Browser**: IGV.js integration for genomic visualization
- **ChIP-seq Overlap**: Visualize lncRNA-ChIP-seq peak overlaps
- **Network Visualization**: Cytoscape.js for gene-disease networks
- **Conservation Analysis**: Cross-species conservation patterns
- **Data Export**: CSV, Excel, and image export support

## Environment Variables

Create `.env.local` for local development:

```env
# Optional (DEV):
# If not set, the frontend defaults to http(s)://<frontend-hostname>:8000
# This helps when accessing the Vite dev server via LAN IP.
VITE_API_BASE_URL=http://localhost:8000
```

## Dev Server Troubleshooting

### `Failed to fetch dynamically imported module`

If a route suddenly shows an error like:

```text
Failed to fetch dynamically imported module: http://<host>:5173/src/pages/<Page>/index.tsx
```

check the browser network tab first. If the route module itself is `200`, but one of the Vite pre-bundled deps under `/node_modules/.vite/deps/` returns:

```text
504 Outdated Optimize Dep
```

then the usual root cause is a stale Vite optimize cache in a long-running dev server, not a broken route module.

Restart the frontend dev server with forced re-optimization:

```bash
npm run dev -- --host 0.0.0.0 --port 5173 --strictPort --force
```

If you access the app via LAN IP, keep the same host/port you are using in the browser.

### Heavy Cytoscape dependencies

`/regulations` now delays loading `cytoscape` until the batch visualization modal is actually opened. This keeps the list page usable even if the network graph dependency fails to load during local development.

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

### E2E Environment Overrides

Playwright supports overriding the target servers via env vars:

```bash
# Override frontend and backend URLs (e.g. when testing via LAN IP)
BASE_URL=http://localhost:5173 API_BASE_URL=http://localhost:8000 npm run test:e2e
```

## Build

```bash
npm run build
```

Build artifacts are output to `dist/`.
