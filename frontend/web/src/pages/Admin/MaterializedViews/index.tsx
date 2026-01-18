import { useMemo, useState } from 'react'
import { Button, Card, InputNumber, Popconfirm, Space, Switch, Table, Tag, message } from 'antd'
import { ReloadOutlined } from '@ant-design/icons'
import type { ColumnsType } from 'antd/es/table'

import { adminApi } from '@/api/admin'
import { ErrorState } from '@/components/ErrorState'
import { LoadingState } from '@/components/LoadingState'
import { useMaterializedViewsStatus } from '@/hooks/useMaterializedViewsStatus'
import type { MaterializedViewRefreshResultItem, MaterializedViewStatusItem, MaterializedViewsRefreshResponse } from '@/types/admin'

export default function MaterializedViews() {
  const { data, isLoading, error, refetch, isFetching } = useMaterializedViewsStatus()
  const [concurrently, setConcurrently] = useState(true)
  const [analyze, setAnalyze] = useState(true)
  const [timeoutSeconds, setTimeoutSeconds] = useState<number | null>(null)
  const [isRefreshing, setIsRefreshing] = useState(false)
  const [lastResult, setLastResult] = useState<MaterializedViewsRefreshResponse | null>(null)

  const viewNames = useMemo(() => (data?.views ? data.views.map((v) => v.name) : []), [data?.views])

  const columns: ColumnsType<MaterializedViewStatusItem> = useMemo(
    () => [
      {
        title: 'Name',
        dataIndex: 'name',
        key: 'name',
        render: (name: string) => (
          <code style={{ fontSize: 12, backgroundColor: '#f5f5f5', padding: '2px 6px', borderRadius: 4 }}>
            {name}
          </code>
        ),
      },
      {
        title: 'Exists',
        dataIndex: 'exists',
        key: 'exists',
        render: (exists: boolean) => (
          <Tag color={exists ? 'success' : 'default'}>{exists ? 'yes' : 'no'}</Tag>
        ),
      },
      {
        title: 'Populated',
        dataIndex: 'populated',
        key: 'populated',
        render: (populated: boolean | null) => {
          if (populated === null) return <Tag>unknown</Tag>
          return <Tag color={populated ? 'success' : 'warning'}>{populated ? 'yes' : 'no'}</Tag>
        },
      },
      {
        title: 'Rows (est.)',
        dataIndex: 'rows_estimate',
        key: 'rows_estimate',
        align: 'right',
        render: (value: number | null) => (value === null ? '-' : value.toLocaleString()),
      },
      {
        title: 'Total Size',
        dataIndex: 'total_size',
        key: 'total_size',
        align: 'right',
        render: (value: string | null) => value ?? '-',
      },
    ],
    []
  )

  const refreshColumns: ColumnsType<MaterializedViewRefreshResultItem> = useMemo(
    () => [
      {
        title: 'Name',
        dataIndex: 'name',
        key: 'name',
        render: (name: string) => (
          <code style={{ fontSize: 12, backgroundColor: '#f5f5f5', padding: '2px 6px', borderRadius: 4 }}>
            {name}
          </code>
        ),
      },
      {
        title: 'Result',
        key: 'result',
        render: (_, row) => {
          if (row.skipped) return <Tag>skipped</Tag>
          if (row.ok) return <Tag color="success">ok</Tag>
          if (row.ok === false) return <Tag color="error">failed</Tag>
          return <Tag>unknown</Tag>
        },
      },
      {
        title: 'Duration (s)',
        dataIndex: 'duration_seconds',
        key: 'duration_seconds',
        align: 'right',
        render: (value?: number) => (typeof value === 'number' ? value.toFixed(3) : '-'),
      },
      {
        title: 'Note/Error',
        key: 'note',
        render: (_, row) => row.error || row.note || row.reason || '-',
      },
    ],
    []
  )

  if (isLoading) return <LoadingState />
  if (error) return <ErrorState error={error} onRetry={() => refetch()} />

  const lockAvailable = data?.refresh_lock_available
  const lockColor = lockAvailable === undefined ? 'default' : (lockAvailable ? 'success' : 'error')
  const lockLabel = lockAvailable === undefined ? 'unknown' : (lockAvailable ? 'available' : 'busy')
  const refreshDisabled = lockAvailable === false

  const handleRefresh = async () => {
    if (lockAvailable === false) {
      message.warning('MV refresh lock is busy')
      return
    }

    setIsRefreshing(true)
    try {
      const body = {
        views: null as string[] | null,
        concurrently,
        analyze,
        timeout_seconds: timeoutSeconds,
      }
      const resp = await adminApi.refreshMaterializedViews(body)
      setLastResult(resp.data)
      message.success(`MV refresh: ${resp.data.status}`)
      refetch()
    } catch {
      message.error('Failed to refresh materialized views')
    } finally {
      setIsRefreshing(false)
    }
  }

  return (
    <div style={{ padding: 24 }}>
      <Space style={{ marginBottom: 24, width: '100%', justifyContent: 'space-between' }}>
        <h1 style={{ margin: 0 }}>Materialized Views</h1>
        <Space>
          <div>
            <span style={{ marginRight: 8 }}>MV Refresh Lock</span>
            <Tag color={lockColor}>{lockLabel}</Tag>
          </div>
          <Button
            icon={<ReloadOutlined spin={isFetching} />}
            onClick={() => refetch()}
            loading={isFetching}
          >
            Refresh Status
          </Button>
          <Popconfirm
            title="Refresh materialized views?"
            description="This runs a synchronous REFRESH MATERIALIZED VIEW operation (can take time)."
            onConfirm={handleRefresh}
            okText="Refresh"
            cancelText="Cancel"
          >
            <Button type="primary" loading={isRefreshing} disabled={isRefreshing || refreshDisabled}>
              Refresh Views
            </Button>
          </Popconfirm>
        </Space>
      </Space>

      <Card title="Status">
        <Table<MaterializedViewStatusItem>
          columns={columns}
          dataSource={data?.views ?? []}
          rowKey="name"
          size="small"
          pagination={false}
        />
      </Card>

      <Card title="Refresh Options" style={{ marginTop: 16 }}>
        <Space wrap>
          <span>Concurrently</span>
          <Switch checked={concurrently} onChange={(checked) => setConcurrently(checked)} />
          <span>Analyze</span>
          <Switch checked={analyze} onChange={(checked) => setAnalyze(checked)} />
          <span>Timeout (s)</span>
          <InputNumber
            min={0}
            value={timeoutSeconds}
            onChange={(v) => setTimeoutSeconds(typeof v === 'number' ? v : null)}
            placeholder="default"
          />
          <Tag>{viewNames.length ? `${viewNames.length} views` : 'no views'}</Tag>
        </Space>
      </Card>

      {lastResult && (
        <Card
          title="Last Refresh Result"
          style={{ marginTop: 16 }}
          extra={
            <Space>
              <Tag color={lastResult.status === 'success' ? 'success' : 'warning'}>{lastResult.status}</Tag>
              <span>{lastResult.total_duration_seconds.toFixed(3)}s</span>
            </Space>
          }
        >
          <Table<MaterializedViewRefreshResultItem>
            columns={refreshColumns}
            dataSource={lastResult.views}
            rowKey="name"
            size="small"
            pagination={false}
          />
        </Card>
      )}
    </div>
  )
}
