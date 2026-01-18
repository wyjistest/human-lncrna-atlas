import { AxiosError } from 'axios'

/**
 * 错误类型分类
 */
export type ErrorType =
  | 'network'      // 网络错误（无响应）
  | 'timeout'      // 请求超时
  | 'canceled'     // 请求被取消（AbortController / axios cancel）
  | 'validation'   // 4xx 客户端/验证错误
  | 'rate_limit'   // 429 限流
  | 'server'       // 5xx 服务端错误
  | 'unknown'      // 未知错误

/**
 * 错误信息解析结果
 */
export interface ParsedError {
  /** 用户友好的错误消息 */
  message: string
  /** 错误类型分类 */
  type: ErrorType
  /** 后端错误码（如果后端返回了 detail.error） */
  errorCode?: string
  /** 错误 ID（如果后端返回了） */
  errorId?: string
  /** HTTP 状态码 */
  statusCode?: number
}

/**
 * 从错误对象中提取用户友好的错误消息
 *
 * 兼容后端多种错误格式：
 * - 脱敏格式：{detail: {error, message, error_id}}
 * - Admin 403 格式：{detail: {error: "...", message: "..."}}
 * - Pydantic 验证：{detail: [{msg: "..."}]}
 * - 字符串：{detail: "error message"}
 */
/**
 * 根据状态码确定错误类型
 */
function getErrorTypeFromStatus(status: number): ErrorType {
  if (status === 429) return 'rate_limit'
  if (status >= 400 && status < 500) return 'validation'
  if (status >= 500) return 'server'
  return 'unknown'
}

export function parseError(error: unknown): ParsedError {
  // 处理 AxiosError（包括取消/超时/网络/服务端）
  if (error instanceof AxiosError) {
    // Axios v1 取消：error.code === 'ERR_CANCELED'
    // 这类“错误”通常来自组件卸载/查询失效，不应打扰用户。
    if (error.code === 'ERR_CANCELED' || error.name === 'CanceledError') {
      return { message: 'Request canceled', type: 'canceled' }
    }

    if (error.response) {
      const { status, data } = error.response
      const detail = data?.detail
      const errorType = getErrorTypeFromStatus(status)

      // 处理 detail 为对象的情况（包括脱敏格式和 Admin 错误）
      if (typeof detail === 'object' && detail !== null && !Array.isArray(detail)) {
        // 提取 error_id（如果存在）用于调试追踪
        const errorId = 'error_id' in detail ? String(detail.error_id) : undefined
        const errorCode = 'error' in detail && typeof detail.error === 'string' ? detail.error : undefined

        // 优先使用 message 字段
        if ('message' in detail && typeof detail.message === 'string') {
          return {
            message: errorId ? `${detail.message} [${errorId}]` : detail.message,
            type: errorType,
            errorCode,
            errorId,
            statusCode: status,
          }
        }
        // 其次使用 error 字段
        if ('error' in detail && typeof detail.error === 'string') {
          return {
            message: errorId ? `${detail.error} [${errorId}]` : detail.error,
            type: errorType,
            errorCode,
            errorId,
            statusCode: status,
          }
        }
        // 最后尝试 JSON 序列化（避免显示 [object Object]）
        try {
          return {
            message: JSON.stringify(detail),
            type: errorType,
            errorCode,
            errorId,
            statusCode: status,
          }
        } catch {
          // Fall through to default handling
        }
      }

      // 处理 Pydantic 验证错误（数组格式）
      if (Array.isArray(detail)) {
        const messages = detail
          .map((e: { msg?: string; message?: string }) => e.msg || e.message)
          .filter(Boolean)
          .join(', ')
        return {
          message: messages || 'Validation error',
          type: 'validation',
          statusCode: status,
        }
      }

      // 处理字符串 detail 或根据状态码返回默认消息
      const defaultMessages: Record<number, string> = {
        400: 'Invalid request parameters',
        403: 'Access denied',
        404: 'Resource not found',
        422: 'Validation error',
        429: 'Too many requests, please try later',
        500: 'Server error',
      }

      return {
        message: detail || defaultMessages[status] || 'Request failed',
        type: errorType,
        statusCode: status,
      }
    }

    // 处理网络错误（请求已发出但没有响应）
    if (error.request) {
      // 检查是否为超时错误
      const isTimeout = error.code === 'ECONNABORTED' || error.message.includes('timeout')
      return {
        message: isTimeout
          ? 'Request timed out, please try again'
          : 'Network error, please check your connection',
        type: isTimeout ? 'timeout' : 'network',
      }
    }
  }

  // 处理 fetch/DOM AbortError（兜底：即使未来不用 axios 也能静默取消）
  if (error instanceof Error && error.name === 'AbortError') {
    return { message: 'Request canceled', type: 'canceled' }
  }

  // 处理普通 Error 对象
  if (error instanceof Error) {
    return {
      message: error.message,
      type: 'unknown',
    }
  }

  // 处理字符串错误
  if (typeof error === 'string') {
    return {
      message: error,
      type: 'unknown',
    }
  }

  // 未知错误类型
  return {
    message: 'An unexpected error occurred',
    type: 'unknown',
  }
}

/**
 * 简单版本：只返回错误消息字符串
 */
export function getErrorMessage(error: unknown): string {
  return parseError(error).message
}
