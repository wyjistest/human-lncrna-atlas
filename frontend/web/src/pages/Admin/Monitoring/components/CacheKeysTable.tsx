/**
 * Cache Keys Table
 * Displays cache hot keys with request distribution
 */

import { useMemo } from 'react'
import { Table, Empty } from 'antd'
import type { ColumnsType } from 'antd/es/table'
import type { CacheKeyBreakdownItem } from '@/types/monitoring'

interface CacheKeysTableProps {
  data?: CacheKeyBreakdownItem[]
}

export function CacheKeysTable({ data }: CacheKeysTableProps) {
  const columns: ColumnsType<CacheKeyBreakdownItem> = useMemo(
    () => [
      {
        title: 'Key',
        dataIndex: 'key',
        key: 'key',
        sorter: (a, b) => a.key.localeCompare(b.key),
        render: (key: string) => (
          <code
            title={key}
            style={{
              fontSize: 12,
              backgroundColor: '#f5f5f5',
              padding: '2px 6px',
              borderRadius: 4,
              display: 'inline-block',
              maxWidth: 420,
              overflow: 'hidden',
              textOverflow: 'ellipsis',
              whiteSpace: 'nowrap',
              verticalAlign: 'bottom',
            }}
          >
            {key}
          </code>
        ),
      },
      {
        title: 'Namespace',
        dataIndex: 'namespace',
        key: 'namespace',
        sorter: (a, b) => (a.namespace ?? '').localeCompare(b.namespace ?? ''),
        render: (ns?: string | null) => ns ?? '-',
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
        title: 'Hits',
        dataIndex: 'hits',
        key: 'hits',
        sorter: (a, b) => a.hits - b.hits,
        render: (value: number) => value.toLocaleString(),
        align: 'right',
      },
      {
        title: 'Misses',
        dataIndex: 'misses',
        key: 'misses',
        sorter: (a, b) => a.misses - b.misses,
        render: (value: number) => value.toLocaleString(),
        align: 'right',
      },
    ],
    []
  )

  if (!data || data.length === 0) {
    return <Empty description="No cache key stats available" />
  }

  return (
    <Table<CacheKeyBreakdownItem>
      columns={columns}
      dataSource={data}
      rowKey="key"
      size="small"
      pagination={false}
    />
  )
}

