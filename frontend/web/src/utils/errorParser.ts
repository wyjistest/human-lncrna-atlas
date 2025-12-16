import { AxiosError } from 'axios'

/**
 * 错误信息解析结果
 */
export interface ParsedError {
  /** 用户友好的错误消息 */
  message: string
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
export function parseError(error: unknown): ParsedError {
  // 处理 AxiosError
  if (error instanceof AxiosError && error.response) {
    const { status, data } = error.response
    const detail = data?.detail

    // 处理 detail 为对象的情况（包括脱敏格式和 Admin 错误）
    if (typeof detail === 'object' && detail !== null && !Array.isArray(detail)) {
      // 提取 error_id（如果存在）用于调试追踪
      const errorId = 'error_id' in detail ? String(detail.error_id) : undefined

      // 优先使用 message 字段
      if ('message' in detail && typeof detail.message === 'string') {
        return {
          message: errorId ? `${detail.message} [${errorId}]` : detail.message,
          errorId,
          statusCode: status,
        }
      }
      // 其次使用 error 字段
      if ('error' in detail && typeof detail.error === 'string') {
        return {
          message: errorId ? `${detail.error} [${errorId}]` : detail.error,
          errorId,
          statusCode: status,
        }
      }
      // 最后尝试 JSON 序列化（避免显示 [object Object]）
      try {
        return {
          message: JSON.stringify(detail),
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
      statusCode: status,
    }
  }

  // 处理网络错误（请求已发出但没有响应）
  if (error instanceof AxiosError && error.request) {
    return {
      message: 'Network error, please check your connection',
    }
  }

  // 处理普通 Error 对象
  if (error instanceof Error) {
    return {
      message: error.message,
    }
  }

  // 处理字符串错误
  if (typeof error === 'string') {
    return {
      message: error,
    }
  }

  // 未知错误类型
  return {
    message: 'An unexpected error occurred',
  }
}

/**
 * 简单版本：只返回错误消息字符串
 */
export function getErrorMessage(error: unknown): string {
  return parseError(error).message
}
