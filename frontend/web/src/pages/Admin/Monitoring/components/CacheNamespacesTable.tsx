/**
 * Cache Namespaces Table
 * Displays cache stats breakdown by namespace
 */

import { useMemo } from 'react'
import { Table, Empty } from 'antd'
import type { ColumnsType } from 'antd/es/table'
import type { CacheNamespaceBreakdownItem } from '@/types/monitoring'

interface CacheNamespacesTableProps {
  data?: CacheNamespaceBreakdownItem[]
}

export function CacheNamespacesTable({ data }: CacheNamespacesTableProps) {
  const columns: ColumnsType<CacheNamespaceBreakdownItem> = useMemo(
    () => [
      {
        title: 'Namespace',
        dataIndex: 'namespace',
        key: 'namespace',
        sorter: (a, b) => a.namespace.localeCompare(b.namespace),
        render: (ns: string) => (
          <code style={{ fontSize: 12, backgroundColor: '#f5f5f5', padding: '2px 6px', borderRadius: 4 }}>
            {ns}
          </code>
        ),
      },
      {
        title: 'Requests',
        dataIndex: 'requests',
        key: 'requests',
        sorter: (a, b) => a.requests - b.requests,
        defaultSortOrder: 'descend',
        render: (value: number) => value.toLocaleString(),
        align: 'right',
      },
      {
        title: 'Hit Rate',
        dataIndex: 'hit_rate_pct',
        key: 'hit_rate_pct',
        sorter: (a, b) => a.hit_rate_pct - b.hit_rate_pct,
        render: (value: number) => (
          <span style={{ color: value >= 90 ? '#3f8600' : value >= 70 ? '#faad14' : '#cf1322' }}>
            {value.toFixed(1)}%
          </span>
        ),
        align: 'right',
      },
      {
        title: 'Compute Avg (ms)',
        dataIndex: 'compute_avg_ms',
        key: 'compute_avg_ms',
        sorter: (a, b) => a.compute_avg_ms - b.compute_avg_ms,
        render: (value: number) => value.toFixed(1),
        align: 'right',
      },
      {
        title: 'Compute Max (ms)',
        dataIndex: 'compute_max_ms',
        key: 'compute_max_ms',
        sorter: (a, b) => a.compute_max_ms - b.compute_max_ms,
        render: (value: number) => value.toFixed(1),
        align: 'right',
      },
    ],
    []
  )

  if (!data || data.length === 0) {
    return <Empty description="No cache namespace stats available" />
  }

  return (
    <Table<CacheNamespaceBreakdownItem>
      columns={columns}
      dataSource={data}
      rowKey="namespace"
      size="small"
      pagination={false}
    />
  )
}

