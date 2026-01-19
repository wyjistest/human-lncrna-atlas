/**
 * Database Metrics Card
 * Displays DB query/per-request percentiles and slow query leaderboard.
 */

import { Row, Col, Statistic, Table, Empty, Tooltip } from 'antd'
import type { ColumnsType } from 'antd/es/table'
import type { DatabaseMetrics, PercentileMetrics, SlowQuerySummary } from '@/types/monitoring'

interface PercentilesBlockProps {
  title: string
  samples: number
  avgMs: number
  percentiles: PercentileMetrics | null | undefined
}

function PercentilesBlock({ title, samples, avgMs, percentiles }: PercentilesBlockProps) {
  if (!percentiles) {
    return (
      <div style={{ height: 160, display: 'flex', alignItems: 'center', justifyContent: 'center' }}>
        <Empty description={`${title}: collecting samples (${samples}/10)`} />
      </div>
    )
  }

  return (
    <Row gutter={16} style={{ height: 160, alignItems: 'center' }}>
      <Col span={6} style={{ textAlign: 'center' }}>
        <Statistic title="Avg" value={avgMs.toFixed(2)} suffix="ms" />
      </Col>
      <Col span={6} style={{ textAlign: 'center' }}>
        <Statistic title="P50" value={percentiles.p50_ms.toFixed(2)} suffix="ms" />
      </Col>
      <Col span={6} style={{ textAlign: 'center' }}>
        <Statistic title="P95" value={percentiles.p95_ms.toFixed(2)} suffix="ms" />
      </Col>
      <Col span={6} style={{ textAlign: 'center' }}>
        <Statistic title="P99" value={percentiles.p99_ms.toFixed(2)} suffix="ms" />
      </Col>
    </Row>
  )
}

interface DatabaseMetricsCardProps {
  data: DatabaseMetrics | null | undefined
}

export function DatabaseMetricsCard({ data }: DatabaseMetricsCardProps) {
  if (!data) {
    return <Empty description="No database stats available" />
  }

  const columns: ColumnsType<SlowQuerySummary> = [
    {
      title: 'Fingerprint',
      dataIndex: 'fingerprint',
      key: 'fingerprint',
      width: 120,
      render: (value: string) => <code style={{ fontSize: 12 }}>{value}</code>,
    },
    {
      title: 'Count',
      dataIndex: 'count',
      key: 'count',
      width: 80,
      sorter: (a, b) => a.count - b.count,
      defaultSortOrder: 'descend',
      align: 'right',
    },
    {
      title: 'Avg (ms)',
      dataIndex: 'avg_ms',
      key: 'avg_ms',
      width: 100,
      sorter: (a, b) => a.avg_ms - b.avg_ms,
      render: (value: number) => value.toFixed(2),
      align: 'right',
    },
    {
      title: 'Max (ms)',
      dataIndex: 'max_ms',
      key: 'max_ms',
      width: 100,
      sorter: (a, b) => a.max_ms - b.max_ms,
      render: (value: number) => value.toFixed(2),
      align: 'right',
    },
    {
      title: 'Route',
      dataIndex: 'route',
      key: 'route',
      width: 180,
      render: (value: string | null | undefined) =>
        value ? <code style={{ fontSize: 12 }}>{value}</code> : <span style={{ color: '#8c8c8c' }}>-</span>,
    },
    {
      title: 'Statement',
      dataIndex: 'statement',
      key: 'statement',
      ellipsis: true,
      render: (value: string) => (
        <Tooltip title={<pre style={{ margin: 0, whiteSpace: 'pre-wrap' }}>{value}</pre>} placement="topLeft">
          <code style={{ fontSize: 12 }}>{value}</code>
        </Tooltip>
      ),
    },
  ]

  return (
    <div data-testid="admin-monitoring-database-metrics">
      <Row gutter={[16, 16]}>
        <Col xs={24} lg={12}>
          <div style={{ fontWeight: 600, marginBottom: 8 }}>
            Query latency (n={data.query_samples.toLocaleString()})
          </div>
          <PercentilesBlock
            title="Query latency"
            samples={data.query_samples}
            avgMs={data.avg_ms}
            percentiles={data.percentiles}
          />
        </Col>
        <Col xs={24} lg={12}>
          <div style={{ fontWeight: 600, marginBottom: 8 }}>
            Per-request DB time (n={data.request_samples.toLocaleString()})
          </div>
          <PercentilesBlock
            title="Per-request DB time"
            samples={data.request_samples}
            avgMs={data.request_avg_ms}
            percentiles={data.request_percentiles}
          />
        </Col>
      </Row>

      <div style={{ marginTop: 16 }} data-testid="admin-monitoring-database-slow-queries">
        <div style={{ fontWeight: 600, marginBottom: 8 }}>
          Slow queries (threshold ≥ {data.slow_query_threshold_ms.toFixed(0)}ms)
        </div>
        {data.slow_queries.length === 0 ? (
          <Empty description="No slow queries recorded" />
        ) : (
          <Table<SlowQuerySummary>
            columns={columns}
            dataSource={data.slow_queries}
            rowKey={(row) => `${row.fingerprint}:${row.route ?? 'none'}`}
            size="small"
            pagination={{ pageSize: 10, showSizeChanger: true }}
            scroll={{ x: 'max-content' }}
          />
        )}
      </div>
    </div>
  )
}

