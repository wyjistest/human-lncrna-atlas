/**
 * Endpoint Statistics Table
 * Displays per-endpoint metrics with sorting and formatting
 */

import { useMemo } from 'react'
import { Table, Empty } from 'antd'
import type { ColumnsType } from 'antd/es/table'
import type { EndpointStats } from '@/types/monitoring'

interface EndpointTableProps {
  data?: EndpointStats[]
}

export function EndpointTable({ data }: EndpointTableProps) {
  const columns: ColumnsType<EndpointStats> = useMemo(
    () => [
      {
        title: 'Path',
        dataIndex: 'path',
        key: 'path',
        sorter: (a, b) => a.path.localeCompare(b.path),
        render: (path: string) => (
          <code style={{ fontSize: 12, backgroundColor: '#f5f5f5', padding: '2px 6px', borderRadius: 4 }}>
            {path}
          </code>
        )
      },
      {
        title: 'Requests',
        dataIndex: 'requests',
        key: 'requests',
        sorter: (a, b) => a.requests - b.requests,
        defaultSortOrder: 'descend',
        render: (value: number) => value.toLocaleString(),
        align: 'right'
      },
      {
        title: 'Avg (ms)',
        dataIndex: 'avg_ms',
        key: 'avg_ms',
        sorter: (a, b) => a.avg_ms - b.avg_ms,
        render: (value: number) => (
          <span style={{ color: value > 500 ? '#cf1322' : value > 200 ? '#faad14' : '#3f8600' }}>
            {value.toFixed(1)}
          </span>
        ),
        align: 'right'
      },
      {
        title: 'DB Avg (ms)',
        key: 'db_avg_ms',
        sorter: (a, b) => (a.db_avg_ms ?? 0) - (b.db_avg_ms ?? 0),
        render: (_: unknown, record: EndpointStats) => {
          const value = record.db_avg_ms
          if (value == null) return <span style={{ color: '#8c8c8c' }}>-</span>
          return (
            <span style={{ color: value > 500 ? '#cf1322' : value > 200 ? '#faad14' : '#3f8600' }}>
              {value.toFixed(1)}
            </span>
          )
        },
        align: 'right'
      },
      {
        title: 'DB q/req',
        key: 'db_query_avg',
        sorter: (a, b) => (a.db_query_avg ?? 0) - (b.db_query_avg ?? 0),
        render: (_: unknown, record: EndpointStats) => {
          const value = record.db_query_avg
          if (value == null) return <span style={{ color: '#8c8c8c' }}>-</span>
          return <span>{value.toFixed(2)}</span>
        },
        align: 'right'
      },
      {
        title: 'P95 (ms)',
        key: 'p95_ms',
        sorter: (a, b) => (a.percentiles?.p95_ms ?? -1) - (b.percentiles?.p95_ms ?? -1),
        render: (_: unknown, record: EndpointStats) => {
          const value = record.percentiles?.p95_ms
          if (value == null) {
            const samples = record.samples
            if (samples == null) return <span style={{ color: '#8c8c8c' }}>-</span>
            return <span style={{ color: '#8c8c8c' }}>n={samples}/10</span>
          }
          return (
            <span style={{ color: value > 500 ? '#cf1322' : value > 200 ? '#faad14' : '#3f8600' }}>
              {value.toFixed(1)}
            </span>
          )
        },
        align: 'right'
      },
      {
        title: 'P99 (ms)',
        key: 'p99_ms',
        sorter: (a, b) => (a.percentiles?.p99_ms ?? -1) - (b.percentiles?.p99_ms ?? -1),
        render: (_: unknown, record: EndpointStats) => {
          const value = record.percentiles?.p99_ms
          if (value == null) {
            const samples = record.samples
            if (samples == null) return <span style={{ color: '#8c8c8c' }}>-</span>
            return <span style={{ color: '#8c8c8c' }}>n={samples}/10</span>
          }
          return (
            <span style={{ color: value > 1000 ? '#cf1322' : value > 500 ? '#faad14' : '#3f8600' }}>
              {value.toFixed(1)}
            </span>
          )
        },
        align: 'right'
      },
      {
        title: 'DB P95 (ms)',
        key: 'db_p95_ms',
        sorter: (a, b) => (a.db_percentiles?.p95_ms ?? -1) - (b.db_percentiles?.p95_ms ?? -1),
        render: (_: unknown, record: EndpointStats) => {
          const value = record.db_percentiles?.p95_ms
          if (value == null) {
            const samples = record.db_samples
            if (samples == null) return <span style={{ color: '#8c8c8c' }}>-</span>
            return <span style={{ color: '#8c8c8c' }}>n={samples}/10</span>
          }
          return (
            <span style={{ color: value > 500 ? '#cf1322' : value > 200 ? '#faad14' : '#3f8600' }}>
              {value.toFixed(1)}
            </span>
          )
        },
        align: 'right'
      },
      {
        title: 'Errors',
        dataIndex: 'errors',
        key: 'errors',
        sorter: (a, b) => a.errors - b.errors,
        render: (value: number) => (
          <span style={{ color: value > 0 ? '#cf1322' : 'inherit', fontWeight: value > 0 ? 500 : 400 }}>
            {value.toLocaleString()}
          </span>
        ),
        align: 'right'
      },
      {
        title: 'Error Rate',
        dataIndex: 'error_rate',
        key: 'error_rate',
        sorter: (a, b) => a.error_rate - b.error_rate,
        render: (value: number) => {
          const percentage = (value * 100).toFixed(2)
          return (
            <span style={{ color: value > 0.05 ? '#cf1322' : value > 0.01 ? '#faad14' : '#3f8600' }}>
              {percentage}%
            </span>
          )
        },
        align: 'right'
      }
    ],
    []
  )

  if (!data || data.length === 0) {
    return <Empty description="No endpoint statistics available" />
  }

  return (
    <Table<EndpointStats>
      columns={columns}
      dataSource={data}
      rowKey="path"
      size="small"
      scroll={{ x: 'max-content' }}
      pagination={{
        pageSize: 10,
        showSizeChanger: true,
        showTotal: (total, range) => `${range[0]}-${range[1]} of ${total} endpoints`
      }}
    />
  )
}
