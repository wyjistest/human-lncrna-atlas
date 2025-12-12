# Network Page Cross-Species Comparison Enhancement

**Date**: 2025-12-12
**Status**: ✅ Complete
**Build Status**: ✅ Successful (18.21s)

## Overview

Enhanced the Network page with cross-species comparison functionality, allowing users to compare lncRNA target genes across multiple primate species (Human, Chimpanzee, Macaque, Marmoset).

## Implementation Summary

### 1. Extended Network API Client

**File**: `/frontend/web/src/api/network.ts`

**New Methods**:
- `compareSpecies(lncrnaGeneId, params)` - Cross-species comparison endpoint
- `getAvailableCombinations(speciesId?)` - Get available disease-ontology combinations
- `getDiseaseNetwork(params)` - Get disease network data
- `getGeneDetail(geneId)` - Get detailed gene information

**Changes**: +30 lines

### 2. Added TypeScript Interfaces

**File**: `/frontend/web/src/types/network.ts`

**New Interfaces**:
```typescript
- CompareParams
- SpeciesTargetGene
- SpeciesNetworkData
- SpeciesNetworkComparison
- AvailableCombination
- AvailableCombinationsResponse
- DiseaseNetworkParams
```

**Changes**: +58 lines

### 3. Added i18n Translations

**Files**:
- `/frontend/web/src/i18n/locales/en/network.json`
- `/frontend/web/src/i18n/locales/zh-CN/network.json`

**New Translation Section**: `comparison` with 18 keys
- Button labels, modal titles, table headers
- Loading/error states, conserved target messages
- Truncation warnings, export options

**Changes**: +22 lines per file

### 4. Enhanced Network Page

**File**: `/frontend/web/src/pages/Network/index.tsx`

**New Features**:
- ✅ "Compare Across Species" button in NetworkCard header (with SwapOutlined icon)
- ✅ Cross-species comparison drawer (800px wide)
- ✅ Species-wise comparison tabs with target gene tables
- ✅ Conserved targets highlighting with species count
- ✅ Table filtering (conserved vs not conserved)
- ✅ Sortable binding affinity column
- ✅ Truncation warning alerts
- ✅ Statistics summary (lncRNA info, conserved count)

**New State**:
```typescript
- comparisonDrawerOpen: boolean
- selectedLncrnaForComparison: { geneId, coreId, geneName } | null
```

**New Queries**:
- `comparisonData` - Fetches cross-species comparison data via `networkApi.compareSpecies()`

**UI Layout**:
```
┌──────────────────────────────────────────────┐
│ Cross-Species Comparison                   X │
├──────────────────────────────────────────────┤
│ LncRNA: CATG00000000034 (core_id: 12345)    │
│ Conserved Targets: 15 (across 4 species)     │
├──────────────────────────────────────────────┤
│ [Tabs: Human | Chimp | Macaque | Marmoset]   │
├──────────────────────────────────────────────┤
│ Target Gene | Core ID | BA     | Conserved? │
│ GENE1       | 100     | 150.5  | ✓ (4)      │
│ GENE2       | 101     | 120.3  | ✓ (2)      │
│ GENE3       | 102     | 100.0  |            │
└──────────────────────────────────────────────┘
```

**Changes**: +250 lines

### 5. Refactored API Calls

**Before**:
```typescript
apiClient.get('/api/v1/network/available-combinations')
apiClient.get('/api/v1/network/disease', { params })
apiClient.get(`/api/v1/network/gene/${geneId}/detail`)
```

**After**:
```typescript
networkApi.getAvailableCombinations()
networkApi.getDiseaseNetwork(params)
networkApi.getGeneDetail(geneId)
```

**Benefits**:
- ✅ Centralized API logic
- ✅ Type-safe parameters
- ✅ Easier to maintain and test
- ✅ Consistent error handling

## Key Features

### 1. Compare Button
- **Location**: NetworkCard header (next to Export dropdown)
- **Icon**: SwapOutlined (Ant Design)
- **Trigger**: Automatically finds lncRNA node in the network
- **Validation**: Warns if no lncRNA found

### 2. Comparison Drawer
- **Width**: 800px
- **Placement**: Right side
- **Summary Section**:
  - LncRNA name
  - Core ID
  - Conserved target count with species count
- **Tabs Section**:
  - One tab per species
  - Target count badge on each tab
  - Sortable table with 4 columns

### 3. Conserved Targets
- **Highlighting**: Green tag with species count
- **Filtering**: Filter by conserved/not conserved
- **Sorting**: By binding affinity (ascending/descending)
- **Pagination**: 20 items per page, adjustable

### 4. Truncation Handling
- **Alert**: Info message when showing top N targets
- **Message**: "Showing top {count} targets (total: {total})"
- **Style**: Blue info alert with icon

## File Changes Summary

| File | Type | Lines Added | Status |
|------|------|-------------|--------|
| `src/api/network.ts` | API | +30 | ✅ |
| `src/types/network.ts` | Types | +58 | ✅ |
| `src/pages/Network/index.tsx` | Component | +250 | ✅ |
| `src/i18n/locales/en/network.json` | i18n | +22 | ✅ |
| `src/i18n/locales/zh-CN/network.json` | i18n | +22 | ✅ |
| **Total** | | **+382** | ✅ |

## Testing

### Build Verification
```bash
cd /data/wenyujianData/human-lncrna-atlas-github/frontend/web
npm run build
```

**Result**: ✅ Success (18.21s)

### Expected Behavior

1. **Button Visibility**:
   - Button appears when `lncrnaCoreId` and `lncrnaGeneId` props are provided
   - Button hidden if network has no lncRNA nodes

2. **Drawer Opening**:
   - Click "Compare Across Species" button
   - Drawer slides in from right
   - Loading state shown while fetching data

3. **Data Display**:
   - Summary shows lncRNA info and conserved count
   - Tabs show one per species with target count badge
   - Table displays target genes with conserved status
   - Conserved targets have green tag with species count (e.g., "✓ (4)")

4. **Interactions**:
   - Switch between species tabs
   - Filter by conserved/not conserved
   - Sort by binding affinity
   - Paginate through results
   - Close drawer to return to network view

## Backend API Requirements

The following API endpoints must be implemented in the backend:

### 1. Cross-Species Comparison
```
GET /api/v1/network/compare
Query Parameters:
  - lncrna_gene_id: number (required)
  - min_ba: number (optional, default: 0)
  - max_targets_per_species: number (optional, default: 100)

Response:
{
  lncrna_core_id: number,
  species_networks: {
    [species_id: number]: {
      lncrna_gene_id: number,
      species_id: number,
      target_count: number,
      total_target_count: number,
      truncated: boolean,
      targets: [{
        target_gene_id: number,
        target_name: string | null,
        target_core_id: number,
        binding_affinity: number | null
      }]
    }
  },
  conserved_target_count: number,
  conserved_targets: number[]
}
```

### 2. Available Combinations (Already Exists)
```
GET /api/v1/network/available-combinations
Query Parameters:
  - species_id: number (optional)

Response:
{
  combinations: [{
    trait_id: number,
    ontology_id: number,
    species_id: number
  }]
}
```

### 3. Disease Network (Already Exists)
```
GET /api/v1/network/disease
Query Parameters:
  - trait_id: number (required)
  - ontology_id: number (required)
  - species_id: number (optional)
  - min_ba: number (optional)
  - max_nodes: number (optional)
  - max_edges: number (optional)
```

### 4. Gene Detail (Already Exists)
```
GET /api/v1/network/gene/{gene_id}/detail
```

## Next Steps

1. **Backend Implementation**:
   - Implement `/api/v1/network/compare` endpoint
   - Add cross-species query logic using `core_id` mapping
   - Add pagination support for large target lists

2. **Testing**:
   - Unit tests for API client methods
   - Integration tests for comparison drawer
   - E2E tests for user workflows

3. **Enhancements** (Optional):
   - Export comparison results to CSV/Excel
   - Add Venn diagram visualization of conserved targets
   - Add heatmap of binding affinities across species
   - Support comparing multiple lncRNAs simultaneously

## Notes

- The comparison button is only shown when `lncrnaCoreId` and `lncrnaGeneId` props are provided to NetworkCard
- The API assumes that `core_id` is used to identify orthologous genes across species
- Conserved targets are identified by `target_core_id` appearing in multiple species
- The drawer width (800px) accommodates 4-column tables comfortably
- All text is internationalized (English and Chinese)
- The implementation follows existing patterns in the codebase (useQuery, Ant Design components, drawer pattern)

---

**Implementation Team**: Claude Sonnet 4.5
**Review Status**: Awaiting backend API implementation
