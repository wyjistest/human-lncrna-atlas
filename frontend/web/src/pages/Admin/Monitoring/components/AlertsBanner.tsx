/**
 * Alerts Banner Component
 * Displays system alerts sorted by severity (critical first)
 */

import { Alert as AntAlert, Space } from 'antd'
import { ExclamationCircleOutlined, CloseCircleOutlined } from '@ant-design/icons'
import type { Alert } from '@/types/monitoring'

interface AlertsBannerProps {
  /** Array of active alerts */
  alerts: Alert[]
}

/**
 * Sort alerts by severity (critical > warning)
 */
function sortAlertsBySeverity(alerts: Alert[]): Alert[] {
  return [...alerts].sort((a, b) => {
    if (a.type === 'critical' && b.type === 'warning') return -1
    if (a.type === 'warning' && b.type === 'critical') return 1
    return 0
  })
}

/**
 * Get Ant Design alert type from alert severity
 */
function getAlertType(type: Alert['type']): 'error' | 'warning' {
  return type === 'critical' ? 'error' : 'warning'
}

/**
 * Get icon for alert type
 */
function getAlertIcon(type: Alert['type']) {
  return type === 'critical' ? <CloseCircleOutlined /> : <ExclamationCircleOutlined />
}

export function AlertsBanner({ alerts }: AlertsBannerProps) {
  if (!alerts || alerts.length === 0) {
    return null
  }

  const sortedAlerts = sortAlertsBySeverity(alerts)

  // If only one alert, show single banner
  if (sortedAlerts.length === 1) {
    const alert = sortedAlerts[0]
    return (
      <AntAlert
        type={getAlertType(alert.type)}
        icon={getAlertIcon(alert.type)}
        message={alert.message}
        description={`${alert.metric}: ${alert.value.toFixed(1)} (threshold: ${alert.threshold})`}
        showIcon
        style={{ marginBottom: 16 }}
      />
    )
  }

  // Multiple alerts - determine overall severity
  const hasCritical = sortedAlerts.some(a => a.type === 'critical')
  const overallType = hasCritical ? 'error' : 'warning'

  return (
    <AntAlert
      type={overallType}
      icon={hasCritical ? <CloseCircleOutlined /> : <ExclamationCircleOutlined />}
      message={`${sortedAlerts.length} Active Alerts`}
      description={
        <Space orientation="vertical" size={4} style={{ width: '100%' }}>
          {sortedAlerts.map((alert, index) => (
            <div key={index}>
              <strong style={{ color: alert.type === 'critical' ? '#cf1322' : '#d48806' }}>
                [{alert.type.toUpperCase()}]
              </strong>{' '}
              {alert.message} ({alert.metric}: {alert.value.toFixed(1)}, threshold: {alert.threshold})
            </div>
          ))}
        </Space>
      }
      showIcon
      style={{ marginBottom: 16 }}
    />
  )
}
