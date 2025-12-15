import { Result, Button, Space, Typography } from 'antd'
import { useTranslation } from 'react-i18next'
import { ReloadOutlined, HomeOutlined } from '@ant-design/icons'

const { Text } = Typography

interface ErrorStateProps {
  /** The error object or message */
  error: Error | unknown
  /** Retry callback */
  onRetry?: () => void
  /** Go back callback */
  onGoBack?: () => void
  /** Custom title */
  title?: string
  /** Custom description */
  description?: string
  /** Show home button */
  showHomeButton?: boolean
  /** Minimum height of container */
  minHeight?: number | string
}

/**
 * ErrorState Component
 *
 * A consistent error display for failed operations.
 * Provides clear feedback and recovery options.
 *
 * @example Basic usage with retry
 * ```tsx
 * if (error) {
 *   return <ErrorState error={error} onRetry={refetch} />
 * }
 * ```
 *
 * @example With custom message
 * ```tsx
 * <ErrorState
 *   error={error}
 *   title="Failed to load data"
 *   description="Please check your network connection"
 *   onRetry={refetch}
 *   showHomeButton
 * />
 * ```
 */
export const ErrorState = ({
  error,
  onRetry,
  onGoBack,
  title,
  description,
  showHomeButton = false,
  minHeight
}: ErrorStateProps) => {
  const { t } = useTranslation('common')

  // Extract error message
  const getErrorMessage = (): string => {
    if (description) return description
    if (error instanceof Error) {
      // Handle axios errors
      if ('response' in error && (error as { response?: { data?: { detail?: string } } }).response?.data?.detail) {
        return (error as { response: { data: { detail: string } } }).response.data.detail
      }
      return error.message
    }
    if (typeof error === 'string') return error
    return t('error.unknown', 'An unknown error occurred')
  }

  // Determine error status for Result component
  const getStatus = (): 'error' | 'warning' | '500' | '404' | '403' => {
    if (error instanceof Error && 'response' in error) {
      const status = (error as { response?: { status?: number } }).response?.status
      if (status === 404) return '404'
      if (status === 403) return '403'
      if (status === 500) return '500'
    }
    return 'error'
  }

  const handleGoHome = () => {
    window.location.href = '/'
  }

  return (
    <div style={{ minHeight }}>
      <Result
        status={getStatus()}
        title={title || t('error.loadFailed', 'Loading Failed')}
        subTitle={
          <Space orientation="vertical" size="small">
            <Text type="secondary">{getErrorMessage()}</Text>
            {import.meta.env.DEV && error instanceof Error && (
              <Text type="secondary" style={{ fontSize: 11 }}>
                {error.name}: {error.stack?.split('\n')[0]}
              </Text>
            )}
          </Space>
        }
        extra={
          <Space>
            {onRetry && (
              <Button type="primary" icon={<ReloadOutlined />} onClick={onRetry}>
                {t('error.retry', 'Retry')}
              </Button>
            )}
            {onGoBack && (
              <Button onClick={onGoBack}>
                {t('action.goBack', 'Go Back')}
              </Button>
            )}
            {showHomeButton && (
              <Button icon={<HomeOutlined />} onClick={handleGoHome}>
                {t('action.goHome', 'Go Home')}
              </Button>
            )}
          </Space>
        }
      />
    </div>
  )
}

export default ErrorState
