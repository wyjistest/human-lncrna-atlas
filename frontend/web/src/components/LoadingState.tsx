import { Spin, Typography, Space } from 'antd'
import { useTranslation } from 'react-i18next'

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
 */
export const LoadingState = ({
  message,
  tip,
  minHeight = 400,
  size = 'large'
}: LoadingStateProps) => {
  const { t } = useTranslation('common')

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
      <Space direction="vertical" align="center" size="middle">
        <Spin size={size} />
        {message && (
          <Text style={{ color: '#666', fontSize: 14 }}>
            {message}
          </Text>
        )}
        {tip && (
          <Text type="secondary" style={{ fontSize: 12 }}>
            {tip}
          </Text>
        )}
        {!message && !tip && (
          <Text type="secondary" style={{ fontSize: 12 }}>
            {t('loading', 'Loading...')}
          </Text>
        )}
      </Space>
    </div>
  )
}

export default LoadingState
