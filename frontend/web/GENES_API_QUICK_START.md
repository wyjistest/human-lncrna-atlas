# Genes API Quick Integration Guide

**Ready to use after backend implementation** ✅

---

## 1. Replace genes.ts (One Command)

```bash
cd /data/wenyujianData/human-lncrna-atlas-github/frontend/web
mv src/api/genes.ts src/api/genes.ts.backup
mv src/api/genes.ts.NEW src/api/genes.ts
```

**Rollback if needed**:
```bash
mv src/api/genes.ts.backup src/api/genes.ts
```

---

## 2. Instant Integration Templates

### Template 1: Basic Gene Selector (Most Common)

```typescript
import { useQuery } from '@tanstack/react-query'
import { genesApi } from '@/api/genes'
import { Select } from 'antd'

function MyComponent() {
  const { data: geneOptions, isLoading } = useQuery({
    queryKey: ['gene-options'],
    queryFn: () => genesApi.getOptions(),
    staleTime: 10 * 60 * 1000,
  })

  return (
    <Select
      loading={isLoading}
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
  )
}
```

### Template 2: Species-Specific (Recommended for Performance)

```typescript
const [speciesId, setSpeciesId] = useState<number>()

const { data: geneOptions, isLoading } = useQuery({
  queryKey: ['gene-options', speciesId],
  queryFn: () => genesApi.getOptions({ species_id: speciesId }),
  staleTime: 10 * 60 * 1000,
  enabled: !!speciesId, // Only load when species selected
})

return (
  <Space>
    <Select
      placeholder="Select species"
      onChange={setSpeciesId}
      options={[
        { value: 1, label: 'Human' },
        { value: 2, label: 'Chimpanzee' },
        { value: 3, label: 'Macaque' },
        { value: 4, label: 'Marmoset' },
      ]}
    />
    <Select
      disabled={!speciesId || isLoading}
      loading={isLoading}
      options={geneOptions?.genes.map(g => ({
        value: g.gene_id,
        label: g.gene_name || g.gene_ensembl_id
      })) || []}
    />
  </Space>
)
```

### Template 3: Autocomplete for Search

```typescript
import { AutoComplete } from 'antd'
import { useMemo, useState } from 'react'

function GeneAutocomplete() {
  const [searchTerm, setSearchTerm] = useState('')

  const { data: geneOptions } = useQuery({
    queryKey: ['gene-options'],
    queryFn: () => genesApi.getOptions(),
    staleTime: 10 * 60 * 1000,
  })

  const suggestions = useMemo(() => {
    if (!geneOptions?.genes || !searchTerm) return []

    return geneOptions.genes
      .filter(g =>
        (g.gene_name?.toLowerCase().includes(searchTerm.toLowerCase())) ||
        g.gene_ensembl_id.toLowerCase().includes(searchTerm.toLowerCase())
      )
      .slice(0, 50)
      .map(g => ({
        value: g.gene_name || g.gene_ensembl_id,
        label: `${g.gene_name || g.gene_ensembl_id} (${g.species_name})`
      }))
  }, [geneOptions, searchTerm])

  return (
    <AutoComplete
      value={searchTerm}
      onChange={setSearchTerm}
      options={suggestions}
      placeholder="Type gene name..."
      style={{ width: 250 }}
    />
  )
}
```

---

## 3. API Testing (After Backend Ready)

### Browser Console Test

```javascript
// Open DevTools Console on http://localhost:5173

// Import API
const { genesApi } = await import('/src/api/genes.ts')

// Test 1: All genes
const all = await genesApi.getOptions()
console.log('Total genes:', all.genes.length)
console.log('Sample:', all.genes[0])

// Test 2: Human genes only
const human = await genesApi.getOptions({ species_id: 1 })
console.log('Human genes:', human.genes.length)

// Test 3: lncRNA genes only
const lncRNAs = await genesApi.getOptions({ gene_type: 'lncRNA' })
console.log('lncRNA genes:', lncRNAs.genes.length)

// Test 4: Combined filter
const humanLncRNAs = await genesApi.getOptions({
  species_id: 1,
  gene_type: 'lncRNA'
})
console.log('Human lncRNA genes:', humanLncRNAs.genes.length)
```

### Backend API Test

```bash
# Direct API test
curl "http://localhost:8000/api/v1/genes/options" | jq '.genes | length'
# Expected: 17248

curl "http://localhost:8000/api/v1/genes/options?species_id=1" | jq '.genes | length'
# Expected: 5484

curl "http://localhost:8000/api/v1/genes/options?gene_type=lncRNA" | jq '.genes | length'
# Expected: 6554
```

---

## 4. Performance Verification

### Check Response Time

```bash
# Using curl with timing
curl -w "\nTime: %{time_total}s\n" \
  "http://localhost:8000/api/v1/genes/options" \
  -o /dev/null -s

# Expected: < 0.5s (first call), < 0.3s (cached)
```

### Check Redis Cache

```bash
# View cached keys
redis-cli KEYS "lncrna:genes:options*"

# Check TTL
redis-cli TTL "lncrna:genes:options:all:all"

# View cache size
redis-cli --stat | grep memory
```

---

## 5. Common Issues & Solutions

### Issue 1: Large Response Size Warning

**Symptom**: Browser shows "Large response detected"

**Solution**: Use species filter to reduce data size
```typescript
// ❌ Don't load all genes if not needed
genesApi.getOptions()

// ✅ Load only relevant genes
genesApi.getOptions({ species_id: selectedSpeciesId })
```

### Issue 2: Slow Initial Load

**Symptom**: First load takes > 500ms

**Solution**: Check backend caching
```bash
# Verify Redis is running
redis-cli PING
# Expected: PONG

# Check cache hit rate
redis-cli INFO stats | grep keyspace_hits
```

### Issue 3: TypeScript Errors

**Symptom**: `Property 'getOptions' does not exist`

**Solution**: Rebuild types
```bash
npm run build
# or
npx tsc --noEmit
```

---

## 6. Integration Checklist

Before integrating into a page:

- [ ] Backend `/api/v1/genes/options` endpoint is implemented
- [ ] Backend returns data in `GeneOptionsResponse` format
- [ ] Redis cache is configured (30min TTL)
- [ ] Frontend `genes.ts` updated with new method
- [ ] API test passes in browser console
- [ ] Response time < 500ms
- [ ] Existing pages (Genes list, Gene detail) still work

---

## 7. Best Practices

### ✅ Do

- Use `staleTime: 10 * 60 * 1000` (10 minutes) for React Query
- Filter by species when possible to reduce response size
- Use `enabled: !!condition` to prevent unnecessary API calls
- Implement `showSearch` with `filterOption` for large lists
- Limit autocomplete suggestions to 50-100 items

### ❌ Don't

- Call `getOptions()` without filters unless absolutely necessary
- Forget to handle loading and error states
- Cache for less than 5 minutes (defeats backend caching)
- Load all genes if you only need one species
- Use this API for paginated tables (use `genesApi.list()` instead)

---

## 8. Performance Expectations

| Scenario | Expected Response | Data Size |
|----------|------------------|-----------|
| All genes (first) | 250-350 ms | 2.05 MB |
| All genes (cached) | 150-250 ms | 2.05 MB |
| Human only | 150-200 ms | ~600 KB |
| lncRNA only | 150-200 ms | ~800 KB |

---

## 9. Support & References

- **Full Integration Guide**: `GENES_API_INTEGRATION_PLAN.md`
- **Backend Schema**: `/frontend/backend/app/schemas/gene.py`
- **Similar Pattern**: `src/api/diseases.ts` (Phase 5.1)
- **Project Memory**: `CLAUDE.md` (Phase 5.2 section)

---

## 10. Quick Commands Summary

```bash
# Replace genes.ts
mv src/api/genes.ts.NEW src/api/genes.ts

# Test API (browser console)
const all = await genesApi.getOptions()

# Check Redis cache
redis-cli KEYS "lncrna:genes:options*"

# Monitor response time
curl -w "\nTime: %{time_total}s\n" http://localhost:8000/api/v1/genes/options

# Rollback if needed
mv src/api/genes.ts.backup src/api/genes.ts
```

---

**Status**: ✅ Ready for Immediate Integration (After Backend Complete)
**Last Updated**: 2025-12-10
