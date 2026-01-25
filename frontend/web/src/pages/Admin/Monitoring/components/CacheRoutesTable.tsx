/**
 * Cache Routes Table
 * Displays cache miss-compute attribution by route template
 */

import { useMemo } from 'react'
import { Table, Empty } from 'antd'
import type { ColumnsType } from 'antd/es/table'
import type { CacheRouteBreakdownItem } from '@/types/monitoring'

interface CacheRoutesTableProps {
  data?: CacheRouteBreakdownItem[]
}

export function CacheRoutesTable({ data }: CacheRoutesTableProps) {
  const columns: ColumnsType<CacheRouteBreakdownItem> = useMemo(
    () => [
      {
        title: 'Route',
        dataIndex: 'route',
        key: 'route',
        sorter: (a, b) => a.route.localeCompare(b.route),
        render: (route: string) => (
          <code
            title={route}
            style={{
              fontSize: 12,
              backgroundColor: '#f5f5f5',
              padding: '2px 6px',
              borderRadius: 4,
              display: 'inline-block',
              maxWidth: 520,
              overflow: 'hidden',
              textOverflow: 'ellipsis',
              whiteSpace: 'nowrap',
              verticalAlign: 'bottom',
            }}
          >
            {route}
          </code>
        ),
      },
      {
        title: 'Compute Count',
        dataIndex: 'compute_count',
        key: 'compute_count',
        sorter: (a, b) => a.compute_count - b.compute_count,
        defaultSortOrder: 'descend',
        render: (value: number) => value.toLocaleString(),
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
    return <Empty description="No cache route compute stats available" />
  }

  return (
    <Table<CacheRouteBreakdownItem>
      columns={columns}
      dataSource={data}
      rowKey="route"
      size="small"
      pagination={false}
    />
  )
}
