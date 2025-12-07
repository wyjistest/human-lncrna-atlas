import { Result, Button } from 'antd'
import { useTranslation } from 'react-i18next'

interface ErrorStateProps {
  error: Error | unknown
  onRetry?: () => void
}

export const ErrorState = ({ error, onRetry }: ErrorStateProps) => {
  const { t } = useTranslation('common')
  const message = error instanceof Error ? error.message : t('error.unknown')

  return (
    <Result
      status="error"
      title={t('error.loadFailed')}
      subTitle={message}
      extra={onRetry && <Button type="primary" onClick={onRetry}>{t('error.retry')}</Button>}
    />
  )
}
