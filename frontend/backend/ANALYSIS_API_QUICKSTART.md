# Analysis API - Quick Start

Get started with the Analysis Results API in 5 minutes.

---

## 1. Test the Endpoint

```bash
# Basic request
curl http://localhost:8000/api/v1/analysis/summary

# Pretty JSON
curl -s http://localhost:8000/api/v1/analysis/summary | python3 -m json.tool

# Check response time
time curl -s http://localhost:8000/api/v1/analysis/summary > /dev/null
```

---

## 2. View API Documentation

Open in browser:
- **Swagger UI**: http://localhost:8000/docs#/analysis/get_analysis_summary_api_v1_analysis_summary_get
- **ReDoc**: http://localhost:8000/redoc#tag/analysis

---

## 3. Copy TypeScript Types

```typescript
// src/types/analysis.ts
export interface AnalysisSummary {
  high_affinity: {
    total_regulations: number;
    unique_lncrnas: number;
    unique_targets: number;
    avg_ba: number;
    max_ba: number;
    top_lncrnas: Array<{
      name: string;
      target_count: number;
      avg_ba: number;
    }>;
  };
  conservation: {
    four_species: number;
    three_species: number;
    two_species: number;
    total_conserved: number;
  };
  epigenetic: {
    total_overlaps: number;
    by_mark: Record<string, number>;
    by_cell_type: Record<string, number>;
  };
  disease: {
    total_diseases: number;
    total_lncrnas: number;
    total_genes: number;
  };
}
```

---

## 4. Create API Service

```typescript
// src/api/analysis.ts
import request from '@/utils/request';

export async function getAnalysisSummary(): Promise<AnalysisSummary> {
  return request.get('/api/v1/analysis/summary');
}
```

---

## 5. Use in React Component

```typescript
// src/pages/AnalysisResults/index.tsx
import { useEffect, useState } from 'react';
import { Card, Statistic, Row, Col, Spin } from 'antd';
import { getAnalysisSummary } from '@/api/analysis';

export default function AnalysisResults() {
  const [data, setData] = useState(null);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    getAnalysisSummary()
      .then(setData)
      .finally(() => setLoading(false));
  }, []);

  if (loading) return <Spin />;

  return (
    <div>
      <Card title="High Affinity Analysis">
        <Row gutter={16}>
          <Col span={8}>
            <Statistic
              title="Regulations"
              value={data.high_affinity.total_regulations}
            />
          </Col>
          <Col span={8}>
            <Statistic
              title="lncRNAs"
              value={data.high_affinity.unique_lncrnas}
            />
          </Col>
          <Col span={8}>
            <Statistic
              title="Avg BA"
              value={data.high_affinity.avg_ba}
              precision={2}
            />
          </Col>
        </Row>
      </Card>

      {/* Add more cards for conservation, epigenetic, disease */}
    </div>
  );
}
```

---

## 6. Monitor Cache

```bash
# Check cache exists
redis-cli EXISTS "lncrna:analysis:summary"

# Check TTL (should be ~3600 seconds)
redis-cli TTL "lncrna:analysis:summary"

# Clear cache to force refresh
redis-cli DEL "lncrna:analysis:summary"
```

---

## Response Time Expectations

| Scenario | Time | Notes |
|----------|------|-------|
| First request | ~1 second | Computes from database |
| Cached request | ~30 milliseconds | Served from Redis |
| After 1 hour | ~1 second | Cache expired, recomputes |

---

## Sample Response Data

**High Affinity**: 37,434 regulations, 1,836 lncRNAs, 6,707 targets
**Conservation**: 4,679 lncRNAs (2,943 in 4 species)
**Epigenetic**: 6.5M overlaps across 11 marks and 17 cell types
**Disease**: 273 diseases, 1,969 lncRNAs

---

## Need Help?

- 📖 **Full Guide**: `ANALYSIS_API_FRONTEND_GUIDE.md`
- 📋 **Detailed Report**: `PHASE_6.0_C_COMPLETION_REPORT.md`
- 🌐 **API Docs**: http://localhost:8000/docs#/analysis
- 🔍 **Example Code**: See ANALYSIS_API_FRONTEND_GUIDE.md

---

**Ready to build your Analysis Results page!** 🚀
