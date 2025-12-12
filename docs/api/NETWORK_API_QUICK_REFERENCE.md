# Network API Quick Reference

**For Frontend Developers**

---

## Compare Species Networks

### Endpoint

```
GET /api/v1/network/compare
```

### Parameters

| Parameter | Type | Required | Default | Description |
|-----------|------|----------|---------|-------------|
| `lncrna_gene_id` | int | ✅ Yes | - | Gene ID of the lncRNA |
| `min_ba` | float | No | 50 | Minimum binding affinity (0-100) |
| `max_targets_per_species` | int | No | 100 | Max targets per species (1-500) |

### Example Requests

```bash
# Basic query
curl "http://localhost:8000/api/v1/network/compare?lncrna_gene_id=17276&min_ba=50"

# High BA threshold
curl "http://localhost:8000/api/v1/network/compare?lncrna_gene_id=17276&min_ba=80"

# Limited targets
curl "http://localhost:8000/api/v1/network/compare?lncrna_gene_id=17276&max_targets_per_species=10"
```

### Response Structure

```typescript
interface CompareResponse {
  lncrna_core_id: number;
  species_names: {
    [species_id: string]: string;  // e.g., {"1": "Human", "2": "Chimpanzee"}
  };
  species_networks: {
    [species_id: string]: {
      lncrna_gene_id: number;
      species_id: number;
      species_name: string;          // "Human", "Chimpanzee", etc.
      target_count: number;
      total_target_count: number;
      truncated: boolean;
      targets: Array<{
        target_gene_id: number;
        target_name: string;
        target_core_id: number;
        binding_affinity: number;
      }>;
    };
  };
  conserved_target_count: number;
  conserved_targets: number[];       // Core IDs of conserved targets
}
```

### Frontend Integration Example

```typescript
// Fetch comparison data
const response = await fetch(
  `/api/v1/network/compare?lncrna_gene_id=${geneId}&min_ba=50`
);
const data: CompareResponse = await response.json();

// Build species dropdown
const speciesOptions = Object.entries(data.species_names).map(([id, name]) => ({
  value: id,
  label: name  // "Human", "Chimpanzee", etc.
}));

// Display results
Object.values(data.species_networks).forEach(network => {
  console.log(`${network.species_name}:`);
  console.log(`  - ${network.target_count} targets`);
  if (network.truncated) {
    console.log(`  - Showing top ${network.target_count} of ${network.total_target_count}`);
  }
});

// Show conservation stats
console.log(`Conserved targets: ${data.conserved_target_count}`);
```

### Error Responses

| Status | Error | Solution |
|--------|-------|----------|
| 404 | "LncRNA not found" | Check if gene_id exists |
| 422 | Validation error | Check parameter types/ranges |

---

## Other Network Endpoints

### Available Combinations

```bash
GET /api/v1/network/available-combinations?species_id=1
```

Returns list of available trait-ontology combinations.

### Disease Network

```bash
GET /api/v1/network/disease?trait_id=40&ontology_id=46&species_id=1
```

Returns network data (nodes and edges) for a disease-ontology combination.

### Gene Detail

```bash
GET /api/v1/network/gene/17276/detail
```

Returns detailed information about a gene including conservation data and connection statistics.

### Gene Network

```bash
GET /api/v1/network/gene/17276?min_ba=50&depth=1&max_edges=500
```

Returns regulatory network centered on a gene with configurable depth and size.

---

## Performance Notes

- **Average Response Time**: 65-75ms
- **Recommended `max_targets_per_species`**: 100-200 for optimal UI performance
- **Conservation Calculation**: Automatic (no extra cost)

---

## Tips for Frontend

1. **Always check `truncated` flag**:
   ```typescript
   if (network.truncated) {
     showWarning(`Showing ${network.target_count} of ${network.total_target_count} targets`);
   }
   ```

2. **Use `species_names` for labels**:
   - No need to hardcode species mappings
   - Consistent with backend

3. **Highlight conserved targets**:
   ```typescript
   const isConserved = (coreId: number) =>
     data.conserved_targets.includes(coreId);
   ```

4. **Handle loading states**:
   - API typically responds in < 100ms
   - Still show loading indicator for UX

---

**Full Documentation**: http://localhost:8000/docs
