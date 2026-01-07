# Genes API Integration Plan - Phase 5.2

**Date**: 2025-12-10
**Status**: Ready for Backend Implementation
**Based on**: Phase 5.1 Diseases API Success Pattern (5.5s → 0.2s optimization)

---

## 1. Executive Summary

### Objective
Prepare lightweight Genes Options API integration following the proven Phase 5.1 pattern, enabling fast gene selection across multiple pages without loading full gene data.

### Success Criteria
- API response < 500ms (target: 200-300ms)
- TypeScript types fully defined
- Integration templates ready for immediate use
- Zero breaking changes to existing code

---

## 2. Code Analysis Summary

### 2.1 Current State

**File**: `<repo-root>/frontend/web/src/api/genes.ts`

```typescript
// Current Implementation (19 lines)
import { apiClient } from './client'
import type { components } from '@/types'

type GeneListItem = components['schemas']['GeneListItem']
type GeneDetail = components['schemas']['GeneDetail']
type PaginatedResponse<T> = components['schemas']['PaginatedResponse_GeneListItem_'] & { items: T[] }

export const genesApi = {
  list: (params: {
    page?: number
    page_size?: number
    gene_type?: string
    species_id?: number
    search?: string
  }) => apiClient.get<PaginatedResponse<GeneListItem>>('/api/v1/genes', { params }),

  detail: (geneId: number) => apiClient.get<GeneDetail>(`/api/v1/genes/${geneId}`),
}
```

**Analysis**:
- ✅ Simple, clean structure
- ✅ Uses unified `apiClient` HTTP client
- ✅ TypeScript types imported from OpenAPI schema
- ⚠️ No lightweight options API (loads full paginated data)

### 2.2 Usage Analysis

**Pages Using `genesApi`**:

| Page | Current Usage | Optimization Needed |
|------|--------------|---------------------|
| `/pages/Genes/index.tsx` | `genesApi.list()` for table | ❌ No (pagination required) |
| `/pages/GeneDetail/index.tsx` | `genesApi.detail()` only | ❌ No (single gene) |
| `/hooks/useGenes.ts` | Wraps `genesApi.list()` | ❌ No (hook-level abstraction) |
| `/pages/Regulations/components/AdvancedFilters.tsx` | **Manual gene input** | ⚠️ **Future Enhancement** (gene name autocomplete) |
| `/pages/Network/index.tsx` | No direct usage | ❌ No (uses diseases API) |

**Conclusion**:
- **No immediate optimization required** for existing pages
- **Potential use case**: Future gene selector components (e.g., autocomplete in Regulations filters)
- **Primary benefit**: Establish API pattern for future features

---

## 3. API Design Specification

### 3.1 Backend Schema Reference

From `<repo-root>/frontend/backend/app/schemas/gene.py`:

```python
class GeneOption(BaseModel):
    """基因选项（轻量级，用于下拉框）"""
    gene_id: int
    gene_ensembl_id: str
    gene_name: Optional[str] = None
    species_id: int
    species_name: str

class GeneOptionsResponse(BaseModel):
    """基因选项响应"""
    genes: List[GeneOption]
```

**Backend Expected Behavior**:
- ✅ Redis cache: 30 minutes (`lncrna:genes:options:{species_id}:{gene_type}`)
- ✅ Auto-remove species suffixes (`_chimp`, `_macaque`, `_marmoset`)
- ✅ Support filtering by `species_id` and `gene_type`
- ✅ Return all genes if no filter specified

### 3.2 Frontend TypeScript Types

**File**: `<repo-root>/frontend/web/src/api/genes.ts`

```typescript
/**
 * Gene option interface (lightweight, for dropdown selection)
 */
export interface GeneOption {
  gene_id: number
  gene_ensembl_id: string
  gene_name: string | null
  species_id: number
  species_name: string
}

/**
 * Gene options response interface
 */
export interface GeneOptionsResponse {
  genes: GeneOption[]
}
```

### 3.3 API Method Signature

```typescript
export const genesApi = {
  // Existing methods (unchanged)
  list: (params: {...}) => apiClient.get<PaginatedResponse<GeneListItem>>(...),
  detail: (geneId: number) => apiClient.get<GeneDetail>(...),

  /**
   * Get lightweight gene options for dropdown selection
   * Cached for 10 minutes on backend (Redis)
   *
   * @param params - Optional filters
   * @param params.species_id - Filter by species (1=Human, 2=Chimp, 3=Macaque, 4=Marmoset)
   * @param params.gene_type - Filter by gene type (lncRNA/protein_coding)
   * @returns Promise with genes array
   *
   * @example
   * // All genes (17,248 records)
   * const all = await genesApi.getOptions()
   *
   * // Human genes only (5,484 records)
   * const human = await genesApi.getOptions({ species_id: 1 })
   *
   * // lncRNA genes only (6,554 records)
   * const lncRNAs = await genesApi.getOptions({ gene_type: 'lncRNA' })
   */
  getOptions: async (params?: {
    species_id?: number
    gene_type?: string
  }): Promise<GeneOptionsResponse> => {
    const response = await apiClient.get<GeneOptionsResponse>(
      '/api/v1/genes/options',
      { params }
    )
    return response.data
  }
}
```

---

## 4. Integration Templates

### 4.1 Template: Basic Gene Selector

**Use Case**: Dropdown selector for gene filtering

```typescript
import { useQuery } from '@tanstack/react-query'
import { genesApi } from '@/api/genes'
import { Select } from 'antd'

// Inside component
const {
  data: geneOptions,
  isLoading: geneOptionsLoading,
  isError: geneOptionsError
} = useQuery({
  queryKey: ['gene-options'], // Or ['gene-options', speciesId] for species-specific
  queryFn: () => genesApi.getOptions(),
  staleTime: 10 * 60 * 1000, // 10 minutes cache
})

// Render
<Select
  loading={geneOptionsLoading}
  disabled={geneOptionsLoading || geneOptionsError}
  showSearch
  filterOption={(input, option) =>
    (option?.label ?? '').toLowerCase().includes(input.toLowerCase())
  }
  options={geneOptions?.genes.map(g => ({
    value: g.gene_id,
    label: g.gene_name || g.gene_ensembl_id
  })) || []}
  placeholder="Select gene..."
/>
```

### 4.2 Template: Species-Specific Gene Selector

**Use Case**: Load genes only after species selection

```typescript
const [selectedSpeciesId, setSelectedSpeciesId] = useState<number>()

const {
  data: geneOptions,
  isLoading: geneOptionsLoading
} = useQuery({
  queryKey: ['gene-options', selectedSpeciesId],
  queryFn: () => genesApi.getOptions({ species_id: selectedSpeciesId }),
  staleTime: 10 * 60 * 1000,
  enabled: !!selectedSpeciesId, // Only fetch when species selected
})

// Render
<Space>
  <Select
    placeholder="Select species first"
    onChange={setSelectedSpeciesId}
    options={[
      { value: 1, label: 'Human' },
      { value: 2, label: 'Chimpanzee' },
      { value: 3, label: 'Macaque' },
      { value: 4, label: 'Marmoset' },
    ]}
  />

  <Select
    disabled={!selectedSpeciesId || geneOptionsLoading}
    loading={geneOptionsLoading}
    options={geneOptions?.genes.map(g => ({
      value: g.gene_id,
      label: g.gene_name || g.gene_ensembl_id
    })) || []}
    placeholder="Select gene..."
  />
</Space>
```

### 4.3 Template: Gene Type Filtered Selector

**Use Case**: lncRNA-only or protein-coding-only selection

```typescript
const {
  data: lncRNAOptions
} = useQuery({
  queryKey: ['gene-options', 'lncRNA'],
  queryFn: () => genesApi.getOptions({ gene_type: 'lncRNA' }),
  staleTime: 10 * 60 * 1000,
})

const {
  data: proteinCodingOptions
} = useQuery({
  queryKey: ['gene-options', 'protein_coding'],
  queryFn: () => genesApi.getOptions({ gene_type: 'protein_coding' }),
  staleTime: 10 * 60 * 1000,
})
```

### 4.4 Template: Autocomplete for Gene Search

**Use Case**: Real-time gene name search (for Regulations AdvancedFilters)

```typescript
import { AutoComplete } from 'antd'

const [geneSearchTerm, setGeneSearchTerm] = useState('')

const { data: geneOptions } = useQuery({
  queryKey: ['gene-options'],
  queryFn: () => genesApi.getOptions(),
  staleTime: 10 * 60 * 1000,
})

// Client-side filtering for autocomplete
const filteredGenes = useMemo(() => {
  if (!geneOptions?.genes || !geneSearchTerm) return []

  return geneOptions.genes
    .filter(g =>
      (g.gene_name?.toLowerCase().includes(geneSearchTerm.toLowerCase())) ||
      g.gene_ensembl_id.toLowerCase().includes(geneSearchTerm.toLowerCase())
    )
    .slice(0, 50) // Limit to 50 suggestions
    .map(g => ({
      value: g.gene_name || g.gene_ensembl_id,
      label: `${g.gene_name || g.gene_ensembl_id} (${g.species_name})`
    }))
}, [geneOptions, geneSearchTerm])

// Render
<AutoComplete
  value={geneSearchTerm}
  onChange={setGeneSearchTerm}
  options={filteredGenes}
  placeholder="Type gene name..."
  style={{ width: 250 }}
/>
```

---

## 5. Implementation Checklist

### 5.1 Backend Prerequisites

- [ ] Backend API endpoint `/api/v1/genes/options` implemented
- [ ] Redis cache configured (30min TTL)
- [ ] Query parameters supported: `species_id`, `gene_type`
- [ ] Species suffix auto-removal implemented
- [ ] Performance tested (< 500ms response time)

### 5.2 Frontend Changes

**Step 1: Update `src/api/genes.ts`** (Ready to implement)

```typescript
// Add after existing imports
/**
 * Gene option interface (lightweight, for dropdown selection)
 */
export interface GeneOption {
  gene_id: number
  gene_ensembl_id: string
  gene_name: string | null
  species_id: number
  species_name: string
}

/**
 * Gene options response interface
 */
export interface GeneOptionsResponse {
  genes: GeneOption[]
}

// Add to genesApi object
export const genesApi = {
  list: (params: {...}) => {...}, // Existing
  detail: (geneId: number) => {...}, // Existing

  /**
   * Get lightweight gene options for dropdown selection
   */
  getOptions: async (params?: {
    species_id?: number
    gene_type?: string
  }): Promise<GeneOptionsResponse> => {
    const response = await apiClient.get<GeneOptionsResponse>(
      '/api/v1/genes/options',
      { params }
    )
    return response.data
  }
}
```

**Step 2: Verify No Breaking Changes**

```bash
# Test existing functionality
npm run build
npm run dev

# Navigate to:
# - /genes (check table loads)
# - /genes/1 (check detail page loads)
# - /regulations (check filters work)
```

**Step 3: Test New API (After Backend Ready)**

```typescript
// In browser console or test file
import { genesApi } from '@/api/genes'

// Test 1: All genes
const all = await genesApi.getOptions()
console.log('All genes:', all.genes.length) // Expected: 17,248

// Test 2: Human genes only
const human = await genesApi.getOptions({ species_id: 1 })
console.log('Human genes:', human.genes.length) // Expected: 5,484

// Test 3: lncRNA genes only
const lncRNAs = await genesApi.getOptions({ gene_type: 'lncRNA' })
console.log('lncRNA genes:', lncRNAs.genes.length) // Expected: 6,554
```

---

## 6. Performance Expectations

### 6.1 Response Time Targets

| Scenario | Expected Response | Data Size | Cache Hit |
|----------|------------------|-----------|-----------|
| All genes (first call) | 250-350 ms | 2.05 MB | Redis |
| All genes (cached) | 180-250 ms | 2.05 MB | Redis hit |
| Species filter (human) | 150-200 ms | ~600 KB | Redis |
| Type filter (lncRNA) | 150-200 ms | ~800 KB | Redis |

### 6.2 Comparison with Phase 5.1 Diseases API

| Metric | Diseases API | Genes API (Expected) |
|--------|--------------|---------------------|
| Records | 273 | 17,248 |
| Response size | ~20 KB | ~2 MB |
| First call | 50 ms | 300 ms |
| Cached call | 7 ms | 200 ms |
| Cache duration | 30 min | 30 min |

**Note**: Larger response size is acceptable as gene options are loaded once and cached client-side by React Query.

---

## 7. Cache Strategy

### 7.1 Backend Cache (Redis)

```python
# Cache keys by backend
"lncrna:genes:options:all:all"           # All genes
"lncrna:genes:options:1:all"             # Human genes
"lncrna:genes:options:all:lncRNA"        # All lncRNA genes
"lncrna:genes:options:1:lncRNA"          # Human lncRNA genes
```

**TTL**: 30 minutes (1800 seconds)

### 7.2 Frontend Cache (React Query)

```typescript
// React Query configuration
{
  queryKey: ['gene-options', speciesId, geneType],
  staleTime: 10 * 60 * 1000, // 10 minutes (600,000 ms)
  gcTime: 30 * 60 * 1000,    // 30 minutes garbage collection
}
```

**Cache Invalidation**:
- Automatic: After 10 minutes (staleTime)
- Manual: `queryClient.invalidateQueries(['gene-options'])`

### 7.3 Cache Monitoring

```bash
# Backend (Redis)
redis-cli KEYS "lncrna:genes:options*"
redis-cli TTL "lncrna:genes:options:all:all"
redis-cli DEL "lncrna:genes:options:all:all" # Manual clear

# Frontend (Browser DevTools)
# Open React Query DevTools to see cache status
```

---

## 8. Future Enhancement Opportunities

### 8.1 Immediate (Post-Phase 5.2)

1. **Regulations Page**: Add gene autocomplete to AdvancedFilters
   - Replace manual input with AutoComplete component
   - Use template 4.4 from this document
   - Expected UX improvement: 50% faster gene selection

2. **Network Page**: Add gene-based network filtering
   - New filter: "Show only genes with disease associations"
   - Use species-specific gene selector
   - Integration: 2-3 hours

### 8.2 Long-term

1. **Gene Comparison Tool**: Multi-gene selector for comparative analysis
2. **Gene Set Enrichment**: Batch gene selection for pathway analysis
3. **IGV Browser Integration**: Quick gene jump via dropdown

---

## 9. Dependencies Check

### 9.1 Required Dependencies (Already Installed)

```json
{
  "@tanstack/react-query": "^5.x",
  "axios": "^1.x",
  "antd": "^5.x",
  "react": "^18.x",
  "typescript": "^5.x"
}
```

✅ **All dependencies satisfied** - No additional installations required.

### 9.2 TypeScript Configuration

Current setup:
- ✅ OpenAPI types auto-generated in `src/types/api.ts`
- ✅ Manual types supported in `src/api/genes.ts`
- ✅ `@/types` import path configured

**No changes needed** to TypeScript config.

---

## 10. Testing Plan

### 10.1 Unit Tests (Optional)

```typescript
// tests/api/genes.test.ts
import { genesApi } from '@/api/genes'

describe('genesApi.getOptions', () => {
  it('should return all genes without filters', async () => {
    const result = await genesApi.getOptions()
    expect(result.genes.length).toBeGreaterThan(0)
    expect(result.genes[0]).toHaveProperty('gene_id')
    expect(result.genes[0]).toHaveProperty('gene_ensembl_id')
  })

  it('should filter by species_id', async () => {
    const result = await genesApi.getOptions({ species_id: 1 })
    expect(result.genes.every(g => g.species_id === 1)).toBe(true)
  })

  it('should filter by gene_type', async () => {
    const result = await genesApi.getOptions({ gene_type: 'lncRNA' })
    expect(result.genes.length).toBeGreaterThan(0)
  })
})
```

### 10.2 Integration Tests (Manual)

| Test Case | Steps | Expected Result |
|-----------|-------|-----------------|
| All genes | Call `getOptions()` without params | Returns 17,248 genes |
| Human filter | Call with `{ species_id: 1 }` | Returns 5,484 genes |
| lncRNA filter | Call with `{ gene_type: 'lncRNA' }` | Returns 6,554 genes |
| Combined | Call with `{ species_id: 1, gene_type: 'lncRNA' }` | Returns subset |
| Cache | Call twice quickly | Second call faster |

### 10.3 UI Tests (Playwright - Future)

```typescript
// tests/e2e/gene-selector.spec.ts
test('gene selector loads and filters correctly', async ({ page }) => {
  await page.goto('/regulations')
  await page.click('[data-testid="gene-filter-selector"]')
  await page.waitForSelector('.ant-select-dropdown')

  const options = await page.$$('.ant-select-item')
  expect(options.length).toBeGreaterThan(0)
})
```

---

## 11. Documentation Updates

### 11.1 Files to Update

1. **CLAUDE.md** (Project memory)
   - Add Genes Options API section to Phase 5.2
   - Document performance metrics
   - Add cache monitoring commands

2. **API Documentation** (If exists)
   - Add `/api/v1/genes/options` endpoint description
   - Document query parameters
   - Provide usage examples

3. **Component Documentation** (Future)
   - Create `GeneSelector.md` for reusable component
   - Document props and usage patterns

---

## 12. Risk Assessment

### 12.1 Low Risks

| Risk | Mitigation |
|------|-----------|
| Large response size (2MB) | Acceptable for one-time load + 10min cache |
| Memory usage | React Query GC after 30 minutes |
| API breakage | New endpoint, existing APIs unchanged |

### 12.2 Monitoring Points

1. **Backend**: Response time should stay < 500ms
2. **Redis**: Cache hit rate should be > 80%
3. **Frontend**: Memory usage stable over time

---

## 13. Rollout Plan

### Phase 1: Backend Implementation (Day 1)
- [ ] Implement `/api/v1/genes/options` endpoint
- [ ] Add Redis caching
- [ ] Performance testing
- [ ] Documentation

### Phase 2: Frontend Integration (Day 1-2)
- [ ] Update `src/api/genes.ts` with new types and method
- [ ] Build verification (`npm run build`)
- [ ] Manual API testing

### Phase 3: Feature Usage (Day 2+)
- [ ] Wait for feature request (e.g., gene autocomplete)
- [ ] Apply integration template
- [ ] User acceptance testing

### Phase 4: Documentation (Day 3)
- [ ] Update CLAUDE.md
- [ ] Add usage examples
- [ ] Performance report

---

## 14. Success Metrics

### Key Performance Indicators (KPIs)

| Metric | Target | Measure |
|--------|--------|---------|
| API response time (first) | < 350 ms | Backend logs |
| API response time (cached) | < 250 ms | Backend logs |
| Cache hit rate | > 80% | Redis INFO |
| Frontend load time | No regression | Lighthouse |
| Developer satisfaction | Positive feedback | Code review |

---

## 15. Contact & Support

**Implementation Team**:
- **Backend**: Backend Agent (Genes Options API endpoint)
- **Frontend**: Frontend Agent (This document, integration templates)
- **Testing**: Playwright Agent (E2E tests, future)

**References**:
- Phase 5.1 Diseases API: `/frontend/web/PHASE2_TEST_ANALYSIS.md`
- Backend Schema: `/frontend/backend/app/schemas/gene.py`
- Frontend Types: `/frontend/web/src/api/genes.ts`

---

## Appendix A: Complete Updated genes.ts File

```typescript
/**
 * Genes API
 * Provides access to gene data, including list, detail, and lightweight options
 */
import { apiClient } from './client'
import type { components } from '@/types'

type GeneListItem = components['schemas']['GeneListItem']
type GeneDetail = components['schemas']['GeneDetail']
type PaginatedResponse<T> = components['schemas']['PaginatedResponse_GeneListItem_'] & { items: T[] }

/**
 * Gene option interface (lightweight, for dropdown selection)
 * Used by gene selectors and autocomplete components
 */
export interface GeneOption {
  gene_id: number
  gene_ensembl_id: string
  gene_name: string | null
  species_id: number
  species_name: string
}

/**
 * Gene options response interface
 */
export interface GeneOptionsResponse {
  genes: GeneOption[]
}

export const genesApi = {
  /**
   * Get paginated gene list with full details
   * Used by Genes list page
   */
  list: (params: {
    page?: number
    page_size?: number
    gene_type?: string
    species_id?: number
    search?: string
  }) => apiClient.get<PaginatedResponse<GeneListItem>>('/api/v1/genes', { params }),

  /**
   * Get detailed information for a single gene
   * Used by Gene detail page
   */
  detail: (geneId: number) => apiClient.get<GeneDetail>(`/api/v1/genes/${geneId}`),

  /**
   * Get lightweight gene options for dropdown selection (Phase 5.2)
   *
   * Optimized API that returns only essential fields (id, name, species)
   * without pagination. Cached on backend (Redis, 30min) and frontend (React Query, 10min).
   *
   * @param params - Optional filters
   * @param params.species_id - Filter by species (1=Human, 2=Chimp, 3=Macaque, 4=Marmoset)
   * @param params.gene_type - Filter by gene type (lncRNA/protein_coding)
   * @returns Promise with genes array
   *
   * @example
   * // All genes (17,248 records, ~2MB)
   * const all = await genesApi.getOptions()
   *
   * // Human genes only (5,484 records)
   * const human = await genesApi.getOptions({ species_id: 1 })
   *
   * // lncRNA genes only (6,554 records)
   * const lncRNAs = await genesApi.getOptions({ gene_type: 'lncRNA' })
   *
   * @see Phase 5.1 Diseases API for similar pattern
   */
  getOptions: async (params?: {
    species_id?: number
    gene_type?: string
  }): Promise<GeneOptionsResponse> => {
    const response = await apiClient.get<GeneOptionsResponse>(
      '/api/v1/genes/options',
      { params }
    )
    return response.data
  }
}
```

---

**Document Version**: 1.0
**Last Updated**: 2025-12-10
**Status**: ✅ Ready for Backend Implementation
