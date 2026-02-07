# Conservation Matrix (by Binding Affinity)

- Species IDs: **1, 2, 3, 4**
- Species labels: **人类 (species_id=1), 黑猩猩 (species_id=2), 猕猴 (species_id=3), 狨猴 (species_id=4)**
- Filter: **binding_affinity >= 50.0**
- Generated (UTC): **sample**

Metric definitions:
- `L_s`: lncRNA core_id set per species `s` under the filter
- `count(i,j) = |L_i ∩ L_j|`
- `row_share(i,j) = |L_i ∩ L_j| / |L_i|`

Outputs:
- Counts CSV: `docs/baselines/research/conservation-matrix-ba50-species-all-counts.csv`
- Row-share CSV: `docs/baselines/research/conservation-matrix-ba50-species-all-row-share.csv`
- Counts heatmap (PNG): _skipped (matplotlib not available)_
- Row-share heatmap (PNG): _skipped (matplotlib not available)_

## Per-species lncRNA set size

| species_id | species | lncrna_count |
|---:|---|---:|
| 1 | 人类 (species_id=1) | 2 |
| 2 | 黑猩猩 (species_id=2) | 0 |
| 3 | 猕猴 (species_id=3) | 0 |
| 4 | 狨猴 (species_id=4) | 0 |

## Shared lncRNA count matrix

| species_id | 1 | 2 | 3 | 4 |
|---:|---:|---:|---:|---:|
| 1 | 2 | 0 | 0 | 0 |
| 2 | 0 | 0 | 0 | 0 |
| 3 | 0 | 0 | 0 | 0 |
| 4 | 0 | 0 | 0 | 0 |

## Shared lncRNA row-share matrix

| species_id | 1 | 2 | 3 | 4 |
|---:|---:|---:|---:|---:|
| 1 | 100.00% | 0.00% | 0.00% | 0.00% |
| 2 | 0.00% | 0.00% | 0.00% | 0.00% |
| 3 | 0.00% | 0.00% | 0.00% | 0.00% |
| 4 | 0.00% | 0.00% | 0.00% | 0.00% |

