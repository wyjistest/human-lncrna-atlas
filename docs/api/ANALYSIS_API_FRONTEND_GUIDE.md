# Analysis API - Frontend Integration Guide

Quick reference for integrating the Analysis Results API into the frontend.

---

## API Endpoint

```
GET /api/v1/analysis/summary
```

**Response Time**: 22-35ms (cached), 1.1s (uncached)
**Cache**: 1 hour TTL

---

## Shareable URLs and Drill-down

`/analysis` 页面现在支持把关键状态编码进 URL，便于分享和复现：

- `tab=highAffinity|conservation|epigenetic|disease`
- `min_ba` / `species_id`（High Affinity）
- `mark_names`（Epigenetic，可重复 query param）
- `trait_name`（Disease）

示例：

```text
/analysis?tab=highAffinity&min_ba=150&species_id=2
/analysis?tab=epigenetic&mark_names=H3K27me3&mark_names=H3K4me3
/analysis?tab=disease&trait_name=diabetes
```

Analysis 表格中的 drill-down link 会把行级 metadata 带到下游页面：

- High Affinity → `/regulations?lncrna_gene_id=<id>&target_gene_id=<id>&min_ba=<current>`
- Epigenetic → `/lncrna-chipseq-overlap?lncrna_gene_id=<id>&target_gene_id=<id>&mark_type=<mark>&min_binding_affinity=100`
- Disease node → `/network?species_ids=<species_id>&trait_id=<trait_id>&ontology_id=<ontology_id>&min_ba=0`

对应导出接口也已经暴露这些导航字段，前端类型以 `frontend/web/src/api/analysis.ts` 为准：

- `/api/v1/export/chipseq-overlaps`：包含 `lncrna_gene_id`、`target_gene_id`
- `/api/v1/export/disease-network`：节点包含 `gene_id`、`trait_id`、`ontology_id`、`species_id`

`/network` 页面在 URL 提供完整参数时会自动发起查询：

```text
/network?species_ids=1,3&trait_id=40&ontology_id=46&min_ba=25
```

---

## TypeScript Types

```typescript
// src/types/analysis.ts

export interface TopLncRNA {
  name: string;
  target_count: number;
  avg_ba: number;
}

export interface HighAffinityAnalysis {
  total_regulations: number;
  unique_lncrnas: number;
  unique_targets: number;
  avg_ba: number;
  max_ba: number;
  top_lncrnas: TopLncRNA[];
}

export interface ConservationAnalysis {
  four_species: number;
  three_species: number;
  two_species: number;
  total_conserved: number;
}

export interface EpigeneticAnalysis {
  total_overlaps: number;
  by_mark: Record<string, number>;
  by_cell_type: Record<string, number>;
}

export interface DiseaseAnalysis {
  total_diseases: number;
  total_lncrnas: number;
  total_genes: number;
}

export interface AnalysisSummary {
  high_affinity: HighAffinityAnalysis;
  conservation: ConservationAnalysis;
  epigenetic: EpigeneticAnalysis;
  disease: DiseaseAnalysis;
}
```

---

## API Service

```typescript
// src/api/analysis.ts
import request from '@/utils/request';
import type { AnalysisSummary } from '@/types/analysis';

/**
 * Get analysis summary for all 4 analysis types
 */
export async function getAnalysisSummary(): Promise<AnalysisSummary> {
  return request.get('/api/v1/analysis/summary');
}
```

---

## Example React Component

```typescript
// src/pages/AnalysisResults/index.tsx
import React, { useEffect, useState } from 'react';
import { Card, Statistic, Row, Col, Spin, Table } from 'antd';
import {
  RiseOutlined,
  GroupOutlined,
  ExperimentOutlined,
  MedicineBoxOutlined,
} from '@ant-design/icons';
import { getAnalysisSummary } from '@/api/analysis';
import type { AnalysisSummary } from '@/types/analysis';

export default function AnalysisResults() {
  const [summary, setSummary] = useState<AnalysisSummary | null>(null);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    getAnalysisSummary()
      .then(setSummary)
      .finally(() => setLoading(false));
  }, []);

  if (loading) {
    return (
      <div style={{ textAlign: 'center', padding: '100px' }}>
        <Spin size="large" />
      </div>
    );
  }

  if (!summary) {
    return <div>No data available</div>;
  }

  return (
    <div style={{ padding: 24 }}>
      <h1>Analysis Results</h1>

      {/* High Affinity Section */}
      <Card
        title={
          <>
            <RiseOutlined /> High Binding Affinity
          </>
        }
        style={{ marginBottom: 16 }}
      >
        <Row gutter={16}>
          <Col span={6}>
            <Statistic
              title="Total Regulations"
              value={summary.high_affinity.total_regulations}
            />
          </Col>
          <Col span={6}>
            <Statistic
              title="Unique lncRNAs"
              value={summary.high_affinity.unique_lncrnas}
            />
          </Col>
          <Col span={6}>
            <Statistic
              title="Unique Targets"
              value={summary.high_affinity.unique_targets}
            />
          </Col>
          <Col span={6}>
            <Statistic
              title="Avg BA"
              value={summary.high_affinity.avg_ba}
              precision={2}
            />
          </Col>
        </Row>

        <h3 style={{ marginTop: 24 }}>Top 20 lncRNAs</h3>
        <Table
          dataSource={summary.high_affinity.top_lncrnas}
          rowKey="name"
          pagination={false}
          columns={[
            {
              title: 'lncRNA Name',
              dataIndex: 'name',
              key: 'name',
            },
            {
              title: 'Target Count',
              dataIndex: 'target_count',
              key: 'target_count',
              sorter: (a, b) => a.target_count - b.target_count,
            },
            {
              title: 'Avg BA',
              dataIndex: 'avg_ba',
              key: 'avg_ba',
              render: (val: number) => val.toFixed(2),
            },
          ]}
        />
      </Card>

      {/* Conservation Section */}
      <Card
        title={
          <>
            <GroupOutlined /> Cross-Species Conservation
          </>
        }
        style={{ marginBottom: 16 }}
      >
        <Row gutter={16}>
          <Col span={6}>
            <Statistic
              title="4 Species"
              value={summary.conservation.four_species}
            />
          </Col>
          <Col span={6}>
            <Statistic
              title="3 Species"
              value={summary.conservation.three_species}
            />
          </Col>
          <Col span={6}>
            <Statistic
              title="2 Species"
              value={summary.conservation.two_species}
            />
          </Col>
          <Col span={6}>
            <Statistic
              title="Total Conserved"
              value={summary.conservation.total_conserved}
            />
          </Col>
        </Row>
      </Card>

      {/* Epigenetic Section */}
      <Card
        title={
          <>
            <ExperimentOutlined /> Epigenetic Marks
          </>
        }
        style={{ marginBottom: 16 }}
      >
        <Statistic
          title="Total ChIP-seq Overlaps"
          value={summary.epigenetic.total_overlaps}
        />

        <Row gutter={16} style={{ marginTop: 16 }}>
          <Col span={12}>
            <h4>By Histone Mark</h4>
            {Object.entries(summary.epigenetic.by_mark)
              .sort(([, a], [, b]) => b - a)
              .map(([mark, count]) => (
                <div key={mark}>
                  <strong>{mark}:</strong> {count.toLocaleString()}
                </div>
              ))}
          </Col>
          <Col span={12}>
            <h4>By Cell Type</h4>
            {Object.entries(summary.epigenetic.by_cell_type)
              .sort(([, a], [, b]) => b - a)
              .slice(0, 10)
              .map(([cell, count]) => (
                <div key={cell}>
                  <strong>{cell}:</strong> {count.toLocaleString()}
                </div>
              ))}
          </Col>
        </Row>
      </Card>

      {/* Disease Section */}
      <Card
        title={
          <>
            <MedicineBoxOutlined /> Disease Associations
          </>
        }
      >
        <Row gutter={16}>
          <Col span={8}>
            <Statistic
              title="Total Diseases"
              value={summary.disease.total_diseases}
            />
          </Col>
          <Col span={8}>
            <Statistic
              title="Associated lncRNAs"
              value={summary.disease.total_lncrnas}
            />
          </Col>
          <Col span={8}>
            <Statistic
              title="Associated Genes"
              value={summary.disease.total_genes}
            />
          </Col>
        </Row>
      </Card>
    </div>
  );
}
```

---

## Sample Data

```json
{
  "high_affinity": {
    "total_regulations": 37434,
    "unique_lncrnas": 1836,
    "unique_targets": 6707,
    "avg_ba": 125.17,
    "max_ba": 755.99,
    "top_lncrnas": [
      {
        "name": "RP11-750H9.5",
        "target_count": 856,
        "avg_ba": 150.36
      }
    ]
  },
  "conservation": {
    "four_species": 2943,
    "three_species": 1199,
    "two_species": 537,
    "total_conserved": 4679
  },
  "epigenetic": {
    "total_overlaps": 6537078,
    "by_mark": {
      "H3K4me3": 694655,
      "H3K27me3": 754284
    },
    "by_cell_type": {
      "K562": 1119978,
      "GM12878": 338901
    }
  },
  "disease": {
    "total_diseases": 273,
    "total_lncrnas": 1969,
    "total_genes": 5484
  }
}
```

---

## Error Handling

```typescript
async function fetchAnalysisSummary() {
  try {
    const summary = await getAnalysisSummary();
    setSummary(summary);
  } catch (error) {
    message.error('Failed to load analysis summary');
    console.error('Analysis API error:', error);
  } finally {
    setLoading(false);
  }
}
```

---

## Chart Examples

### Conservation Pie Chart (ECharts)

```typescript
const conservationChartOption = {
  title: { text: 'Conservation Distribution' },
  tooltip: { trigger: 'item' },
  series: [
    {
      type: 'pie',
      data: [
        { value: summary.conservation.four_species, name: '4 Species' },
        { value: summary.conservation.three_species, name: '3 Species' },
        { value: summary.conservation.two_species, name: '2 Species' },
      ],
    },
  ],
};
```

### Epigenetic Bar Chart (ECharts)

```typescript
const epigeneticChartOption = {
  title: { text: 'ChIP-seq Overlaps by Mark' },
  xAxis: {
    type: 'category',
    data: Object.keys(summary.epigenetic.by_mark),
  },
  yAxis: { type: 'value' },
  series: [
    {
      type: 'bar',
      data: Object.values(summary.epigenetic.by_mark),
    },
  ],
};
```

---

## Notes

1. **Caching**: The API uses 1-hour caching, so data refreshes every hour
2. **Performance**: First load ~1s, subsequent loads ~30ms
3. **Error States**: Always handle loading and error states
4. **Number Formatting**: Use `.toLocaleString()` for large numbers
5. **Top lncRNAs**: Always 20 entries, sorted by target count

---

**Questions?** Check `/api/v1/docs#/analysis` for live API documentation.
