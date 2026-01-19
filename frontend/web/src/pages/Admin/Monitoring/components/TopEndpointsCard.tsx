/**
 * Top Endpoints Card
 * Shows top endpoints by tail latency (P95 / P99).
 */

import { Empty } from 'antd'
import type { EndpointStats } from '@/types/monitoring'

type PercentileKey = 'p95_ms' | 'p99_ms'

interface TopEndpointsCardProps {
  title: string
  endpoints?: EndpointStats[] | null
  percentileKey: PercentileKey
  topN?: number
}

export function TopEndpointsCard({ title, endpoints, percentileKey, topN = 5 }: TopEndpointsCardProps) {
  const items =
    endpoints
      ?.map((ep) => ({
        path: ep.path,
        value: ep.percentiles?.[percentileKey] ?? null,
      }))
      .filter((x) => x.value != null)
      .sort((a, b) => (b.value ?? -1) - (a.value ?? -1))
      .slice(0, topN) ?? []

  if (items.length === 0) {
    return <Empty description={`${title}: no percentile samples yet`} />
  }

  return (
    <div>
      {items.map((item, idx) => (
        <div
          key={`${item.path}:${item.value}`}
          style={{
            display: 'flex',
            width: '100%',
            justifyContent: 'space-between',
            gap: 12,
            padding: '6px 0',
            borderBottom: idx === items.length - 1 ? 'none' : '1px solid #f0f0f0',
          }}
        >
          <code style={{ fontSize: 12, backgroundColor: '#f5f5f5', padding: '2px 6px', borderRadius: 4 }}>
            {item.path}
          </code>
          <div style={{ fontVariantNumeric: 'tabular-nums' }}>{(item.value as number).toFixed(1)}ms</div>
        </div>
      ))}
    </div>
  )
}
