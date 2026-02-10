import { Spin, Typography, Space, Progress } from 'antd'
import { useTranslation } from 'react-i18next'
import { useState, useEffect } from 'react'

const { Text } = Typography

interface LoadingStateProps {
  /** Custom loading message */
  message?: string
  /** Optional tip displayed below the spinner */
  tip?: string
  /** Minimum height of the container */
  minHeight?: number | string
  /** Size of the spinner */
  size?: 'small' | 'default' | 'large'
  /** Show estimated time for large queries (seconds) */
  estimatedTime?: number
  /** Show progress indicator */
  showProgress?: boolean
}

/**
 * LoadingState Component
 *
 * A consistent loading indicator for async operations.
 * Provides visual feedback while data is being fetched.
 *
 * @example Basic usage
 * ```tsx
 * if (isLoading) {
 *   return <LoadingState />
 * }
 * ```
 *
 * @example With custom message
 * ```tsx
 * <LoadingState
 *   message="Loading genome data..."
 *   tip="This may take a few seconds for large chromosomes"
 * />
 * ```
 *
 * @example With estimated time for large queries
 * ```tsx
 * <LoadingState
 *   message="Querying all chromosomes..."
 *   estimatedTime={30}
 *   showProgress
 * />
 * ```
 */
export const LoadingState = ({
  message,
  tip,
  minHeight = 400,
  size = 'large',
  estimatedTime,
  showProgress = false
}: LoadingStateProps) => {
  const { t } = useTranslation('common')
  const [elapsedTime, setElapsedTime] = useState(0)

  // Timer for elapsed time display
  useEffect(() => {
    if (!estimatedTime && !showProgress) return

    const interval = setInterval(() => {
      setElapsedTime((prev) => prev + 1)
    }, 1000)

    return () => clearInterval(interval)
  }, [estimatedTime, showProgress])

  // Calculate progress percentage (cap at 95% to avoid showing 100% before completion)
  const progressPercent = estimatedTime
    ? Math.min(Math.round((elapsedTime / estimatedTime) * 100), 95)
    : undefined

  // Format time display
  const formatTime = (seconds: number) => {
    if (seconds < 60) return `${seconds}s`
    const mins = Math.floor(seconds / 60)
    const secs = seconds % 60
    return `${mins}m ${secs}s`
  }

  return (
    <div
      style={{
        display: 'flex',
        flexDirection: 'column',
        justifyContent: 'center',
        alignItems: 'center',
        minHeight,
        padding: 24
      }}
    >
      <Space orientation="vertical" align="center" size="middle">
        <Spin size={size} />
        {message && (
          <Text style={{ color: '#666', fontSize: 14 }}>
            {message}
          </Text>
        )}

        {/* Progress indicator for long-running queries */}
        {showProgress && estimatedTime && (
          <div style={{ width: 200 }}>
            <Progress
              aria-label={t('loading.progress', 'Loading progress')}
              percent={progressPercent}
              size="small"
              status="active"
              showInfo={false}
            />
            <Text type="secondary" style={{ fontSize: 12, display: 'block', textAlign: 'center', marginTop: 4 }}>
              {t('loading.elapsed', 'Elapsed')}: {formatTime(elapsedTime)}
              {estimatedTime && ` / ${t('loading.estimated', 'Est.')}: ~${formatTime(estimatedTime)}`}
            </Text>
          </div>
        )}

        {/* Simple elapsed time without progress bar */}
        {showProgress && !estimatedTime && elapsedTime > 3 && (
          <Text type="secondary" style={{ fontSize: 12 }}>
            {t('loading.elapsed', 'Elapsed')}: {formatTime(elapsedTime)}
          </Text>
        )}

        {tip && (
          <Text type="secondary" style={{ fontSize: 12 }}>
            {tip}
          </Text>
        )}
        {!message && !tip && (
          <Text type="secondary" style={{ fontSize: 12 }}>
            {t('status.loading', 'Loading...')}
          </Text>
        )}
      </Space>
    </div>
  )
}

export default LoadingState
