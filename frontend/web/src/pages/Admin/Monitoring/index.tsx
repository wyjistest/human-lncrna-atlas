import { useState } from 'react'
import { Card, Row, Col, Statistic, Button, Space, Tag, Popconfirm, message } from 'antd'
import { ReloadOutlined, CheckCircleOutlined, WarningOutlined, CloseCircleOutlined, DeleteOutlined } from '@ant-design/icons'
import { adminApi } from '@/api/admin'
import { useMonitoringMetrics } from '@/hooks/useMonitoringMetrics'
import { LoadingState } from '@/components/LoadingState'
import { ErrorState } from '@/components/ErrorState'
import {
  ResponseTimeChart,
  ErrorTrendChart,
  EndpointTable,
  SystemGauge,
  AlertsBanner,
  PercentilesCard
} from './components'
import type { HealthStatus } from '@/types/monitoring'

/**
 * Get status color and icon based on health status
 */
const getStatusConfig = (status: HealthStatus) => {
  switch (status) {
    case 'healthy':
      return { color: 'success', icon: <CheckCircleOutlined />, text: 'Healthy' }
    case 'degraded':
      return { color: 'warning', icon: <WarningOutlined />, text: 'Degraded' }
    case 'down':
      return { color: 'error', icon: <CloseCircleOutlined />, text: 'Down' }
    default:
      return { color: 'default', icon: null, text: 'Unknown' }
  }
}

/**
 * Format uptime seconds to human-readable string
 */
const formatUptime = (seconds: number): string => {
  const days = Math.floor(seconds / 86400)
  const hours = Math.floor((seconds % 86400) / 3600)
  const minutes = Math.floor((seconds % 3600) / 60)

  if (days > 0) {
    return `${days}d ${hours}h ${minutes}m`
  }
  if (hours > 0) {
    return `${hours}h ${minutes}m`
  }
  return `${minutes}m`
}

export default function Monitoring() {
  const { data, isLoading, error, refetch, isFetching } = useMonitoringMetrics()
  const [isResetting, setIsResetting] = useState(false)

  if (isLoading) return <LoadingState />
  if (error) return <ErrorState error={error} onRetry={() => refetch()} />

  const statusConfig = data ? getStatusConfig(data.health.status) : null

  const handleReset = async () => {
    setIsResetting(true)
    try {
      await adminApi.resetMetrics()
      message.success('Monitoring metrics reset')
      refetch()
    } catch {
      message.error('Failed to reset monitoring metrics')
    } finally {
      setIsResetting(false)
    }
  }

  return (
    <div style={{ padding: 24 }}>
      <Space style={{ marginBottom: 24, width: '100%', justifyContent: 'space-between' }}>
        <h1 style={{ margin: 0 }}>System Monitoring</h1>
        <Space>
          <Popconfirm
            title="Reset monitoring metrics?"
            description="This clears in-memory counters used by this page (Prometheus /metrics is not affected)."
            onConfirm={handleReset}
            okText="Reset"
            cancelText="Cancel"
          >
            <Button danger icon={<DeleteOutlined />} loading={isResetting}>
              Reset Stats
            </Button>
          </Popconfirm>
          <Button
            icon={<ReloadOutlined spin={isFetching} />}
            onClick={() => refetch()}
            loading={isFetching}
          >
            Refresh
          </Button>
        </Space>
      </Space>

      {/* Phase 3: Alerts Banner - conditionally rendered at top */}
      {data?.alerts && data.alerts.length > 0 && (
        <AlertsBanner alerts={data.alerts} />
      )}

      <Row gutter={[16, 16]}>
        {/* Request Total Card */}
        <Col xs={12} sm={12} md={6}>
          <Card>
            <Statistic
              title="Total Requests"
              value={data?.request.total ?? 0}
              suffix={
                <span style={{ fontSize: 14, color: '#52c41a' }}>
                  +{data?.request.last_minute ?? 0}/min
                </span>
              }
            />
          </Card>
        </Col>

        {/* Error Rate Card */}
        <Col xs={12} sm={12} md={6}>
          <Card>
            <Statistic
              title="Error Rate"
              value={((data?.errors.rate ?? 0) * 100).toFixed(2)}
              suffix="%"
              styles={{
                content: { color: (data?.errors.rate ?? 0) > 0.05 ? '#cf1322' : '#3f8600' }
              }}
            />
            <div style={{ marginTop: 8, fontSize: 12, color: '#8c8c8c' }}>
              {data?.errors.total ?? 0} total errors
            </div>
          </Card>
        </Col>

        {/* Average Response Time Card */}
        <Col xs={12} sm={12} md={6}>
          <Card>
            <Statistic
              title="Avg Response Time"
              value={data?.response_time.avg_ms?.toFixed(0) ?? 0}
              suffix="ms"
              styles={{
                content: { color: (data?.response_time.avg_ms ?? 0) > 500 ? '#cf1322' : '#3f8600' }
              }}
            />
          </Card>
        </Col>

        {/* System Status Card */}
        <Col xs={12} sm={12} md={6}>
          <Card>
            <Statistic
              title="System Status"
              valueRender={() => (
                <Tag
                  icon={statusConfig?.icon}
                  color={statusConfig?.color as string}
                  style={{ fontSize: 16, padding: '4px 12px' }}
                >
                  {statusConfig?.text}
                </Tag>
              )}
            />
            <div style={{ marginTop: 12, fontSize: 12, color: '#8c8c8c' }}>
              <div>Uptime: {data ? formatUptime(data.health.uptime_seconds) : '-'}</div>
              <div style={{ marginTop: 4 }}>
                DB:{' '}
                <Tag color={data?.health.database === 'ok' ? 'success' : 'error'} style={{ marginRight: 8 }}>
                  {data?.health.database ?? '-'}
                </Tag>
                Cache:{' '}
                <Tag
                  color={
                    data?.health.cache === 'ok'
                      ? 'success'
                      : data?.health.cache === 'not_configured'
                        ? 'default'
                        : 'error'
                  }
                >
                  {data?.health.cache ?? '-'}
                </Tag>
              </div>
              <div style={{ marginTop: 4 }}>
                Cache Hit Rate:{' '}
                {data?.cache_stats?.enabled
                  ? `${data.cache_stats.hit_rate_pct.toFixed(1)}% (${data.cache_stats.backend || 'unknown'})`
                  : '-'}
              </div>
            </div>
          </Card>
        </Col>
      </Row>

      {/* Phase 3: System Resources & Percentiles */}
      <Row gutter={[16, 16]} style={{ marginTop: 16 }}>
        <Col xs={12} sm={12} md={8} lg={6}>
          <Card title="CPU Usage">
            <SystemGauge
              value={data?.system?.cpu_percent ?? 0}
              title="CPU"
            />
          </Card>
        </Col>
        <Col xs={12} sm={12} md={8} lg={6}>
          <Card title="Memory Usage">
            <SystemGauge
              value={data?.system?.memory?.percent ?? 0}
              title="Memory"
              subtitle={
                data?.system?.memory
                  ? `${(data.system.memory.used_mb / 1024).toFixed(1)} / ${(data.system.memory.total_mb / 1024).toFixed(1)} GB`
                  : undefined
              }
            />
          </Card>
        </Col>
        <Col xs={24} sm={24} md={8} lg={12}>
          <Card title="Response Time Percentiles">
            <PercentilesCard data={data?.percentiles} />
          </Card>
        </Col>
      </Row>

      {/* Phase 2: Response Time Distribution & Error Trend Charts */}
      <Row gutter={[16, 16]} style={{ marginTop: 16 }}>
        <Col xs={24} lg={12}>
          <Card title="Response Time Distribution">
            <ResponseTimeChart data={data?.response_time_distribution} />
          </Card>
        </Col>
        <Col xs={24} lg={12}>
          <Card title="Error Rate Trend (Last 10 min)">
            <ErrorTrendChart data={data?.error_trend} />
          </Card>
        </Col>
      </Row>

      {/* Phase 2: Endpoint Statistics Table */}
      <Row style={{ marginTop: 16 }}>
        <Col span={24}>
          <Card title="Endpoint Statistics">
            <EndpointTable data={data?.endpoints} />
          </Card>
        </Col>
      </Row>
    </div>
  )
}
