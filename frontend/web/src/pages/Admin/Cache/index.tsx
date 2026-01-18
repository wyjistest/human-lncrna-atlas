import { useEffect, useMemo, useState } from 'react'
import { Button, Card, Col, Popconfirm, Row, Select, Space, Statistic, message } from 'antd'
import { DeleteOutlined, ReloadOutlined } from '@ant-design/icons'

import { adminApi } from '@/api/admin'
import { LoadingState } from '@/components/LoadingState'
import { ErrorState } from '@/components/ErrorState'
import { useAdminCacheStats } from '@/hooks/useAdminCacheStats'
import { CacheKeysTable, CacheNamespacesTable } from '../Monitoring/components'

const FALLBACK_CACHE_NAMESPACES = [
  'regulations',
  'genes',
  'stats',
  'export',
  'conservation',
  'chipseq',
  'network',
  'diseases',
  'features',
  'igv',
  'analysis',
  'visualization',
] as string[]

export default function CacheManagement() {
  const { data, isLoading, error, refetch, isFetching } = useAdminCacheStats()
  const [isResetting, setIsResetting] = useState(false)
  const [isClearing, setIsClearing] = useState(false)
  const [isInvalidating, setIsInvalidating] = useState(false)
  const [selectedNamespace, setSelectedNamespace] = useState<string>('stats')

  const allowedNamespaces = useMemo(() => {
    const fromApi = data?.allowed_namespaces
    if (Array.isArray(fromApi) && fromApi.length) {
      return [...fromApi].sort()
    }
    return [...FALLBACK_CACHE_NAMESPACES].sort()
  }, [data?.allowed_namespaces])

  const namespaceOptions = useMemo(
    () => allowedNamespaces.map((ns) => ({ label: ns, value: ns })),
    [allowedNamespaces]
  )

  useEffect(() => {
    if (!allowedNamespaces.length) return
    if (!allowedNamespaces.includes(selectedNamespace)) {
      setSelectedNamespace(allowedNamespaces[0])
    }
  }, [allowedNamespaces, selectedNamespace])

  if (isLoading) return <LoadingState />
  if (error) return <ErrorState error={error} onRetry={() => refetch()} />

  const handleResetStats = async () => {
    setIsResetting(true)
    try {
      const resp = await adminApi.resetCacheStats()
      message.success(resp.data.message || 'Cache stats reset')
      refetch()
    } catch {
      message.error('Failed to reset cache stats')
    } finally {
      setIsResetting(false)
    }
  }

  const handleClearCache = async () => {
    setIsClearing(true)
    try {
      const resp = await adminApi.clearCache()
      const deleted = resp.data.deleted
      const suffix = typeof deleted === 'number' ? ` (${deleted.toLocaleString()} deleted)` : ''
      message.success((resp.data.message || 'Cache cleared') + suffix)
      refetch()
    } catch {
      message.error('Failed to clear cache')
    } finally {
      setIsClearing(false)
    }
  }

  const handleInvalidateNamespace = async () => {
    setIsInvalidating(true)
    try {
      const resp = await adminApi.invalidateCacheNamespace(selectedNamespace)
      const deleted = resp.data.deleted
      const suffix = typeof deleted === 'number' ? ` (${deleted.toLocaleString()} deleted)` : ''
      message.success(`Namespace invalidated: ${selectedNamespace}${suffix}`)
      refetch()
    } catch {
      message.error('Failed to invalidate namespace cache')
    } finally {
      setIsInvalidating(false)
    }
  }

  const backendLabel = data?.backend ? data.backend : '-'
  const hitRateLabel = data?.enabled ? `${(data?.hit_rate_pct ?? 0).toFixed(1)}%` : '-'
  const memorySize = data?.memory?.size
  const redisConnected = data?.redis?.connected

  return (
    <div style={{ padding: 24 }}>
      <Space style={{ marginBottom: 24, width: '100%', justifyContent: 'space-between' }}>
        <h1 style={{ margin: 0 }}>Cache Management</h1>
        <Space>
          <Button
            icon={<ReloadOutlined spin={isFetching} />}
            onClick={() => refetch()}
            loading={isFetching}
          >
            Refresh
          </Button>
          <Popconfirm
            title="Reset cache stats?"
            description="This clears hit/miss counters and hot-key breakdown (does not clear cached values)."
            onConfirm={handleResetStats}
            okText="Reset"
            cancelText="Cancel"
          >
            <Button danger icon={<DeleteOutlined />} loading={isResetting}>
              Reset Cache Stats
            </Button>
          </Popconfirm>
        </Space>
      </Space>

      <Row gutter={[16, 16]}>
        <Col xs={12} sm={12} md={6}>
          <Card>
            <Statistic title="Backend" value={backendLabel} />
          </Card>
        </Col>
        <Col xs={12} sm={12} md={6}>
          <Card>
            <Statistic title="Hit Rate" value={hitRateLabel} />
          </Card>
        </Col>
        <Col xs={12} sm={12} md={6}>
          <Card>
            <Statistic title="Total Requests" value={data?.total_requests ?? 0} />
          </Card>
        </Col>
        <Col xs={12} sm={12} md={6}>
          <Card>
            <Statistic
              title={redisConnected !== undefined ? 'Redis Connected' : 'Memory Cache Size'}
              value={redisConnected !== undefined ? (redisConnected ? 'yes' : 'no') : (memorySize ?? 0)}
            />
          </Card>
        </Col>
      </Row>

      <Row gutter={[16, 16]} style={{ marginTop: 16 }}>
        <Col xs={24} lg={12}>
          <Card title="Invalidate Namespace">
            <Space>
              <Select
                style={{ minWidth: 220 }}
                options={namespaceOptions}
                value={selectedNamespace}
                onChange={(value) => setSelectedNamespace(value)}
              />
              <Popconfirm
                title="Invalidate namespace cache?"
                description={`Invalidate cached entries in namespace '${selectedNamespace}'.`}
                onConfirm={handleInvalidateNamespace}
                okText="Invalidate"
                cancelText="Cancel"
              >
                <Button danger loading={isInvalidating}>
                  Invalidate Namespace
                </Button>
              </Popconfirm>
            </Space>
          </Card>
        </Col>
        <Col xs={24} lg={12}>
          <Card title="Clear Cache">
            <Popconfirm
              title="Clear all cache?"
              description="This deletes all lncrna:* cache entries. This action is irreversible."
              onConfirm={handleClearCache}
              okText="Clear"
              cancelText="Cancel"
            >
              <Button danger icon={<DeleteOutlined />} loading={isClearing}>
                Clear Cache
              </Button>
            </Popconfirm>
          </Card>
        </Col>
      </Row>

      <Row gutter={[16, 16]} style={{ marginTop: 16 }}>
        <Col xs={24} lg={12}>
          <Card
            title="Cache Namespaces"
            extra={data?.namespaces ? `tracked: ${data.namespaces.tracked}` : undefined}
          >
            <CacheNamespacesTable data={data?.namespaces?.top} />
          </Card>
        </Col>
        <Col xs={24} lg={12}>
          <Card
            title="Cache Hot Keys"
            extra={data?.keys ? `tracked: ${data.keys.tracked}` : undefined}
          >
            <CacheKeysTable data={data?.keys?.top} />
          </Card>
        </Col>
      </Row>
    </div>
  )
}
