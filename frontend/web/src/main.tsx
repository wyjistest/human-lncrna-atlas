// i18n 必须在 App 之前导入
import './i18n'

import { StrictMode } from 'react'
import { createRoot } from 'react-dom/client'
import { BrowserRouter } from 'react-router-dom'
import { QueryClient, QueryClientProvider, QueryCache, MutationCache } from '@tanstack/react-query'
import './index.css'
import App from './App.tsx'
import { parseError } from '@/utils/errorParser'
import { throttledMessage } from '@/utils/throttledMessage'

const queryClient = new QueryClient({
  queryCache: new QueryCache({
    onError: (error, query) => {
      // 跳过有自定义错误处理的查询（通过 meta.skipGlobalErrorHandler 标记）
      if (query.meta?.skipGlobalErrorHandler) {
        return
      }
      // 使用带错误类型感知的节流消息队列
      // - 网络/超时错误: 10秒内只显示一次
      // - 限流错误(429): 30秒内只显示一次
      // - 验证/服务端错误: 标准节流 (2秒去重, 5秒窗口内最多3条)
      const parsed = parseError(error)
      throttledMessage.showError(parsed)
    },
  }),
  mutationCache: new MutationCache({
    onError: (error, _variables, _context, mutation) => {
      // 跳过有自定义错误处理的 mutation
      if (mutation.meta?.skipGlobalErrorHandler) {
        return
      }
      const parsed = parseError(error)
      throttledMessage.showError(parsed)
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

// Global unhandled promise rejection handler
// Prevents silent failures when a Promise is rejected without a catch handler.
// Note: React Query errors are handled by QueryCache/MutationCache above.
window.addEventListener('unhandledrejection', (event) => {
  const parsed = parseError(event.reason)
  throttledMessage.showError(parsed)
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
    console.warn('[MSW] Disabled (VITE_USE_MOCK=false)')
    return
  }

  console.warn('[MSW] Starting...')

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

  console.warn('[MSW] Started successfully')
}

/**
 * 渲染应用
 *
 * 独立函数确保即使 MSW 初始化失败，应用也能正常挂载
 */
function renderApp() {
  createRoot(document.getElementById('root')!).render(
    <StrictMode>
      <QueryClientProvider client={queryClient}>
        <BrowserRouter>
          <App />
        </BrowserRouter>
      </QueryClientProvider>
    </StrictMode>,
  )
}

// 确保 MSW 启动完成后再挂载 App
// 添加错误处理：MSW 失败不应阻止应用启动
enableMocking()
  .then(() => {
    renderApp()
  })
  .catch((error) => {
    // MSW 是可选的开发工具，其失败不应阻止应用启动
    console.warn('[MSW] Failed to initialize, continuing without mocking:', error)
    renderApp()
  })
