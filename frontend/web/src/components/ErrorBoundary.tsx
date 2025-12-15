import { Component, ErrorInfo, ReactNode } from 'react'
import { Result, Button } from 'antd'

interface Props {
  children: ReactNode
  fallback?: ReactNode
}

interface State {
  hasError: boolean
  error?: Error
  errorInfo?: ErrorInfo
}

/**
 * Error Boundary 组件
 * 捕获子组件树中的 JavaScript 错误，防止整个应用崩溃
 */
export class ErrorBoundary extends Component<Props, State> {
  constructor(props: Props) {
    super(props)
    this.state = { hasError: false }
  }

  static getDerivedStateFromError(error: Error): State {
    // 更新 state 使下一次渲染显示降级 UI
    return { hasError: true, error }
  }

  componentDidCatch(error: Error, errorInfo: ErrorInfo): void {
    // 可以将错误日志上报给服务端
    console.error('ErrorBoundary caught an error:', error, errorInfo)
    this.setState({ errorInfo })
  }

  handleReload = (): void => {
    window.location.reload()
  }

  handleGoHome = (): void => {
    window.location.href = '/'
  }

  render(): ReactNode {
    if (this.state.hasError) {
      // 如果提供了自定义 fallback，使用它
      if (this.props.fallback) {
        return this.props.fallback
      }

      // 默认的错误 UI
      return (
        <div style={{
          display: 'flex',
          justifyContent: 'center',
          alignItems: 'center',
          minHeight: '100vh',
          padding: 24
        }}>
          <Result
            status="error"
            title="Something went wrong"
            subTitle={
              import.meta.env.DEV
                ? this.state.error?.message
                : 'An unexpected error occurred. Please try again.'
            }
            extra={[
              <Button type="primary" key="reload" onClick={this.handleReload}>
                Reload Page
              </Button>,
              <Button key="home" onClick={this.handleGoHome}>
                Go to Home
              </Button>,
            ]}
          >
            {import.meta.env.DEV && this.state.error && (
              <div style={{
                textAlign: 'left',
                marginTop: 24,
                padding: 16,
                background: '#f5f5f5',
                borderRadius: 4,
                overflow: 'auto',
                maxHeight: 300
              }}>
                <pre style={{ margin: 0, fontSize: 12, whiteSpace: 'pre-wrap' }}>
                  {this.state.error.stack}
                </pre>
              </div>
            )}
          </Result>
        </div>
      )
    }

    return this.props.children
  }
}

export default ErrorBoundary
