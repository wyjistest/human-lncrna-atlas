// i18n 必须在 App 之前导入
import './i18n'

import { StrictMode } from 'react'
import { createRoot } from 'react-dom/client'
import { BrowserRouter } from 'react-router-dom'
import { QueryClient, QueryClientProvider, QueryCache, MutationCache } from '@tanstack/react-query'
import { message } from 'antd'
import { AxiosError } from 'axios'
import './index.css'
import App from './App.tsx'

/**
 * 统一错误消息映射
 * 根据 HTTP 状态码返回用户友好的错误消息
 *
 * 兼容后端多种错误格式：
 * - 脱敏格式：{detail: {error, message, error_id}}
 * - Admin 403 格式：{detail: {error: "...", message: "..."}}
 * - Pydantic 验证：{detail: [{msg: "..."}]}
 * - 字符串：{detail: "error message"}
 */
function getErrorMessage(error: unknown): string {
  if (error instanceof AxiosError && error.response) {
    const { status, data } = error.response
    const detail = data?.detail

    // 处理 detail 为对象的情况（包括脱敏格式和 Admin 错误）
    if (typeof detail === 'object' && detail !== null && !Array.isArray(detail)) {
      // 优先使用 message 字段
      if ('message' in detail && typeof detail.message === 'string') {
        return detail.message
      }
      // 其次使用 error 字段
      if ('error' in detail && typeof detail.error === 'string') {
        return detail.error
      }
      // 最后尝试 JSON 序列化（避免显示 [object Object]）
      try {
        return JSON.stringify(detail)
      } catch {
        return 'An error occurred'
      }
    }

    // 处理 Pydantic 验证错误（数组格式）
    if (Array.isArray(detail)) {
      return detail.map((e: { msg: string }) => e.msg).join(', ')
    }

    // 处理字符串 detail 或根据状态码返回默认消息
    switch (status) {
      case 400:
        return detail || 'Invalid request parameters'
      case 403:
        return detail || 'Access denied'
      case 404:
        return 'Resource not found'
      case 422:
        return detail || 'Validation error'
      case 429:
        return 'Too many requests, please try later'
      case 500:
        return detail || 'Server error'
      default:
        return detail || 'Request failed'
    }
  }

  // 网络错误或其他错误
  if (error instanceof AxiosError && error.request) {
    return 'Network error, please check your connection'
  }

  // 其他错误
  return error instanceof Error ? error.message : 'An unexpected error occurred'
}

const queryClient = new QueryClient({
  queryCache: new QueryCache({
    onError: (error, query) => {
      // 跳过有自定义错误处理的查询（通过 meta.skipGlobalErrorHandler 标记）
      if (query.meta?.skipGlobalErrorHandler) {
        return
      }
      message.error(getErrorMessage(error))
    },
  }),
  mutationCache: new MutationCache({
    onError: (error, _variables, _context, mutation) => {
      // 跳过有自定义错误处理的 mutation
      if (mutation.meta?.skipGlobalErrorHandler) {
        return
      }
      message.error(getErrorMessage(error))
    },
  }),
  defaultOptions: {
    queries: {
      staleTime: 5 * 60 * 1000, // 5分钟内数据视为新鲜，不会触发后台重新获取
      gcTime: 10 * 60 * 1000,   // 10分钟后垃圾回收未使用的缓存（v5 中 cacheTime 改名为 gcTime）
      refetchOnWindowFocus: false, // 禁用窗口聚焦时自动重新获取，减少不必要的请求
      retry: 1,
    },
  },
})

/**
 * MSW 启动逻辑（仅开发环境）
 *
 * 三重检查：
 * 1. 生产环境强制禁用
 * 2. 开发模式检查
 * 3. VITE_USE_MOCK 环境变量检查
 */
async function enableMocking() {
  // 生产环境强制禁用
  if (import.meta.env.PROD) {
    return
  }

  // 开发模式检查
  if (import.meta.env.MODE !== 'development') {
    return
  }

  // 环境变量检查
  if (import.meta.env.VITE_USE_MOCK !== 'true') {
    console.log('[MSW] Disabled (VITE_USE_MOCK=false)')
    return
  }

  console.log('[MSW] Starting...')

  const { worker } = await import('./mocks/browser')

  await worker.start({
    onUnhandledRequest(req, print) {
      // 忽略静态资源和 Vite HMR
      const url = req.url
      if (
        url.includes('/assets/') ||
        url.includes('/@vite/') ||
        url.includes('/@fs/') ||
        url.includes('/node_modules/') ||
        url.endsWith('.svg') ||
        url.endsWith('.png') ||
        url.endsWith('.ico')
      ) {
        return
      }

      // 其他未处理请求显示警告
      print.warning()
    }
  })

  console.log('[MSW] Started successfully')
}

// 确保 MSW 启动完成后再挂载 App
enableMocking().then(() => {
  createRoot(document.getElementById('root')!).render(
    <StrictMode>
      <QueryClientProvider client={queryClient}>
        <BrowserRouter>
          <App />
        </BrowserRouter>
      </QueryClientProvider>
    </StrictMode>,
  )
})
