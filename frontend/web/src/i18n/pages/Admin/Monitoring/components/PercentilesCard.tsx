/**
 * Percentiles Card Component
 * Displays P50/P95/P99 response time statistics
 */

import { Row, Col, Statistic, Empty } from 'antd'
import type { PercentileMetrics } from '@/types/monitoring'

interface PercentilesCardProps {
  /** Percentile metrics data */
  data: PercentileMetrics | null | undefined
}

/**
 * Get color based on response time value
 * - P50: Green baseline
 * - P95: Yellow if > 200ms, Red if > 500ms
 * - P99: Yellow if > 500ms, Red if > 1000ms
 */
function getP50Color(value: number): string {
  if (value > 200) return '#cf1322' // Red
  if (value > 100) return '#faad14' // Yellow
  return '#3f8600' // Green
}

function getP95Color(value: number): string {
  if (value > 500) return '#cf1322' // Red
  if (value > 200) return '#faad14' // Yellow
  return '#3f8600' // Green
}

function getP99Color(value: number): string {
  if (value > 1000) return '#cf1322' // Red
  if (value > 500) return '#faad14' // Yellow
  return '#3f8600' // Green
}

export function PercentilesCard({ data }: PercentilesCardProps) {
  if (!data) {
    return (
      <div style={{ height: 200, display: 'flex', alignItems: 'center', justifyContent: 'center' }}>
        <Empty description="Collecting percentile data..." />
      </div>
    )
  }

  return (
    <Row gutter={16} style={{ height: 200, alignItems: 'center' }}>
      <Col span={8} style={{ textAlign: 'center' }}>
        <Statistic
          title="P50 (Median)"
          value={data.p50_ms.toFixed(0)}
          suffix="ms"
          valueStyle={{ color: getP50Color(data.p50_ms) }}
        />
      </Col>
      <Col span={8} style={{ textAlign: 'center' }}>
        <Statistic
          title="P95"
          value={data.p95_ms.toFixed(0)}
          suffix="ms"
          valueStyle={{ color: getP95Color(data.p95_ms) }}
        />
      </Col>
      <Col span={8} style={{ textAlign: 'center' }}>
        <Statistic
          title="P99"
          value={data.p99_ms.toFixed(0)}
          suffix="ms"
          valueStyle={{ color: getP99Color(data.p99_ms) }}
        />
      </Col>
    </Row>
  )
}
