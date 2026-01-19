/**
 * Cache Get Latency Card
 * Displays p50/p95/p99 latency for cache hits and misses.
 */

import { Row, Col, Statistic, Empty } from 'antd'
import type { CacheGetLatencyPercentiles, PercentileMetrics } from '@/types/monitoring'

interface LatencyBlockProps {
  title: string
  samples: number
  data: PercentileMetrics | null | undefined
}

function LatencyBlock({ title, samples, data }: LatencyBlockProps) {
  if (!data) {
    return (
      <div style={{ height: 160, display: 'flex', alignItems: 'center', justifyContent: 'center' }}>
        <Empty description={`${title}: collecting samples (${samples}/10)`} />
      </div>
    )
  }

  return (
    <Row gutter={16} style={{ height: 160, alignItems: 'center' }}>
      <Col span={8} style={{ textAlign: 'center' }}>
        <Statistic title="P50" value={data.p50_ms.toFixed(2)} suffix="ms" />
      </Col>
      <Col span={8} style={{ textAlign: 'center' }}>
        <Statistic title="P95" value={data.p95_ms.toFixed(2)} suffix="ms" />
      </Col>
      <Col span={8} style={{ textAlign: 'center' }}>
        <Statistic title="P99" value={data.p99_ms.toFixed(2)} suffix="ms" />
      </Col>
    </Row>
  )
}

interface CacheGetLatencyCardProps {
  data: CacheGetLatencyPercentiles | null | undefined
}

export function CacheGetLatencyCard({ data }: CacheGetLatencyCardProps) {
  if (!data) {
    return <Empty description="No cache get latency stats available" />
  }

  return (
    <Row gutter={[16, 16]}>
      <Col xs={24} lg={12}>
        <div style={{ fontWeight: 600, marginBottom: 8 }}>
          Hits (n={data.hits_samples.toLocaleString()})
        </div>
        <LatencyBlock title="Hits" samples={data.hits_samples} data={data.hits} />
      </Col>
      <Col xs={24} lg={12}>
        <div style={{ fontWeight: 600, marginBottom: 8 }}>
          Misses (n={data.misses_samples.toLocaleString()})
        </div>
        <LatencyBlock title="Misses" samples={data.misses_samples} data={data.misses} />
      </Col>
    </Row>
  )
}

