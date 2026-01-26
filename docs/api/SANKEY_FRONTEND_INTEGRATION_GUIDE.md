# Sankey API 快速集成指南（前端）

**API 端点**: `GET /api/v1/visualization/sankey-data`
**基础 URL**: `http://localhost:8000`

---

## 快速开始

### 1. TypeScript 类型定义

```typescript
// src/api/types/visualization.ts

export interface SankeyNode {
  id: string;      // 节点唯一 ID (lncrna_123, gene_456, disease_789)
  name: string;    // 显示名称
  layer: number;   // 层级 (0=lncRNA, 1=gene, 2=disease)
}

export interface SankeyLink {
  source: string;     // 源节点 ID
  target: string;     // 目标节点 ID
  value: number;      // 连接权重
  flow_count: number; // 流经的记录数
}

export interface SankeyStats {
  total_lncrnas: number;
  total_genes: number;
  total_diseases: number;
  total_regulations: number;
  total_associations: number;
  avg_binding_affinity: number;
  species_id: number;
}

export interface SankeyResponse {
  success: boolean;
  data: {
    nodes: SankeyNode[];
    links: SankeyLink[];
  };
  stats: SankeyStats;
  query_params: Record<string, any>;
}
```

### 2. API 客户端

```typescript
// src/api/visualization.ts

import axios from 'axios';
import type { SankeyResponse } from './types/visualization';

const API_BASE = `${window.location.protocol}//${window.location.hostname || 'localhost'}:8000/api/v1`;

export interface SankeyParams {
  species_id?: number;    // 1=人类, 2=黑猩猩, 3=猕猴, 4=狨猴
  min_ba?: number;        // 最小结合亲和力（默认 100）
  trait_name?: string;    // 疾病名称（模糊搜索）
  limit?: number;         // 最大返回数据量（默认 500）
}

export async function getSankeyData(params: SankeyParams = {}): Promise<SankeyResponse> {
  const response = await axios.get<SankeyResponse>(`${API_BASE}/visualization/sankey-data`, {
    params: {
      species_id: 1,
      min_ba: 100,
      limit: 500,
      ...params
    }
  });
  return response.data;
}
```

### 3. React Hook

```typescript
// src/hooks/useVisualization.ts

import { useQuery } from '@tanstack/react-query';
import { getSankeyData, type SankeyParams } from '@/api/visualization';

export function useSankeyData(params: SankeyParams) {
  return useQuery({
    queryKey: ['sankey-data', params],
    queryFn: () => getSankeyData(params),
    staleTime: 5 * 60 * 1000, // 5 分钟
  });
}
```

---

## ECharts 集成

### 完整示例

```tsx
// src/pages/Visualization/SankeyChart.tsx

import React, { useMemo } from 'react';
import ReactECharts from 'echarts-for-react';
import { useSankeyData } from '@/hooks/useVisualization';
import { Spin, Alert } from 'antd';

interface Props {
  speciesId: number;
  minBa: number;
  traitName?: string;
}

export default function SankeyChart({ speciesId, minBa, traitName }: Props) {
  const { data, isLoading, error } = useSankeyData({
    species_id: speciesId,
    min_ba: minBa,
    trait_name: traitName,
    limit: 500
  });

  const option = useMemo(() => {
    if (!data) return {};

    return {
      title: {
        text: 'LncRNA → Gene → Disease 流向图',
        subtext: `节点: ${data.stats.total_lncrnas} lncRNA, ${data.stats.total_genes} 基因, ${data.stats.total_diseases} 疾病`
      },
      tooltip: {
        trigger: 'item',
        formatter: (params: any) => {
          if (params.dataType === 'node') {
            return `${params.name}<br/>Layer: ${params.data.layer}`;
          } else {
            return `${params.data.source} → ${params.data.target}<br/>权重: ${params.value.toFixed(2)}<br/>数量: ${params.data.flow_count}`;
          }
        }
      },
      series: [
        {
          type: 'sankey',
          layout: 'none',
          emphasis: {
            focus: 'adjacency'
          },
          data: data.data.nodes.map(node => ({
            name: node.name,
            itemStyle: {
              color: node.layer === 0 ? '#5470c6' : node.layer === 1 ? '#91cc75' : '#ee6666'
            },
            ...node
          })),
          links: data.data.links.map(link => ({
            source: link.source,
            target: link.target,
            value: link.value,
            lineStyle: {
              opacity: 0.3
            },
            ...link
          })),
          lineStyle: {
            color: 'gradient',
            curveness: 0.5
          }
        }
      ]
    };
  }, [data]);

  if (isLoading) return <Spin size="large" />;
  if (error) return <Alert type="error" title="加载失败" description={error.message} />;
  if (!data) return null;

  return (
    <ReactECharts
      option={option}
      style={{ height: '600px' }}
      notMerge={true}
      lazyUpdate={true}
    />
  );
}
```

---

## 筛选组件

```tsx
// src/pages/Visualization/SankeyFilters.tsx

import React from 'react';
import { Form, Select, InputNumber, Input, Button } from 'antd';

interface Props {
  onSubmit: (values: any) => void;
}

export default function SankeyFilters({ onSubmit }: Props) {
  const [form] = Form.useForm();

  return (
    <Form
      form={form}
      layout="inline"
      onFinish={onSubmit}
      initialValues={{ species_id: 1, min_ba: 100, limit: 500 }}
    >
      <Form.Item name="species_id" label="物种">
        <Select style={{ width: 120 }}>
          <Select.Option value={1}>人类</Select.Option>
          <Select.Option value={2}>黑猩猩</Select.Option>
          <Select.Option value={3}>猕猴</Select.Option>
          <Select.Option value={4}>狨猴</Select.Option>
        </Select>
      </Form.Item>

      <Form.Item name="min_ba" label="最小 BA">
        <InputNumber min={0} max={1000} />
      </Form.Item>

      <Form.Item name="trait_name" label="疾病筛选">
        <Input placeholder="例如: diabetes" allowClear />
      </Form.Item>

      <Form.Item name="limit" label="数据量">
        <InputNumber min={50} max={5000} step={50} />
      </Form.Item>

      <Form.Item>
        <Button type="primary" htmlType="submit">
          查询
        </Button>
      </Form.Item>
    </Form>
  );
}
```

---

## 完整页面示例

```tsx
// src/pages/Visualization/index.tsx

import React, { useState } from 'react';
import { Card, Space } from 'antd';
import SankeyFilters from './SankeyFilters';
import SankeyChart from './SankeyChart';

export default function VisualizationPage() {
  const [params, setParams] = useState({
    species_id: 1,
    min_ba: 100,
    limit: 500
  });

  return (
    <Space direction="vertical" style={{ width: '100%' }} size="large">
      <Card title="Sankey 流向图可视化">
        <SankeyFilters onSubmit={setParams} />
      </Card>

      <Card>
        <SankeyChart {...params} />
      </Card>
    </Space>
  );
}
```

---

## 路由配置

```tsx
// src/routes/index.tsx

import VisualizationPage from '@/pages/Visualization';

export const routes = [
  // ... 其他路由
  {
    path: '/visualization',
    element: <VisualizationPage />,
    meta: {
      title: '可视化',
      icon: 'BarChartOutlined'
    }
  }
];
```

---

## 性能优化建议

### 1. 虚拟化（大数据量）

```tsx
// 当节点数 > 300 时，限制显示数量
const displayNodes = useMemo(() => {
  if (data.data.nodes.length > 300) {
    return data.data.nodes.slice(0, 300);
  }
  return data.data.nodes;
}, [data]);
```

### 2. 防抖查询

```typescript
import { useDebouncedCallback } from 'use-debounce';

const debouncedSearch = useDebouncedCallback((value) => {
  setParams({ ...params, trait_name: value });
}, 500);
```

### 3. 缓存策略

```typescript
// 使用 React Query 缓存
queryClient.setDefaultOptions({
  queries: {
    staleTime: 5 * 60 * 1000,  // 5 分钟
    cacheTime: 10 * 60 * 1000  // 10 分钟
  }
});
```

---

## 常见问题

### Q1: 如何根据层级设置不同颜色？

```typescript
const getNodeColor = (layer: number): string => {
  switch (layer) {
    case 0: return '#5470c6';  // lncRNA - 蓝色
    case 1: return '#91cc75';  // Gene - 绿色
    case 2: return '#ee6666';  // Disease - 红色
    default: return '#666666';
  }
};
```

### Q2: 如何处理节点名称过长？

```typescript
// ECharts 配置
label: {
  formatter: (params: any) => {
    const name = params.name;
    return name.length > 20 ? name.substring(0, 20) + '...' : name;
  }
}
```

### Q3: 如何导出图表？

```typescript
const chartRef = useRef<ReactECharts>(null);

const handleExport = () => {
  const instance = chartRef.current?.getEchartsInstance();
  const url = instance?.getDataURL({ type: 'png', pixelRatio: 2 });
  // 下载或保存 url
};

return <ReactECharts ref={chartRef} option={option} />;
```

---

## 测试数据

### 快速测试 URL

```bash
# 基本查询
http://localhost:8000/api/v1/visualization/sankey-data?limit=50

# Diabetes 相关
http://localhost:8000/api/v1/visualization/sankey-data?trait_name=diabetes&limit=100

# 高亲和力
http://localhost:8000/api/v1/visualization/sankey-data?min_ba=200&limit=100
```

### 预期数据量

| 参数 | 节点数 | 连接数 |
|------|--------|--------|
| limit=50 | ~55 | ~64 |
| limit=100 | ~119 | ~183 |
| limit=500 | ~261 | ~536 |
| diabetes | ~76 | ~148 |

---

## 依赖安装

```bash
# NPM
npm install echarts echarts-for-react @tanstack/react-query axios

# Yarn
yarn add echarts echarts-for-react @tanstack/react-query axios

# TypeScript 类型
npm install -D @types/echarts
```

---

**文档版本**: v1.0
**API 版本**: v1
**最后更新**: 2025-12-12
**联系方式**: 后端 API 开发团队
