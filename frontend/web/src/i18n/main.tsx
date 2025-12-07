// i18n 必须在 App 之前导入
import './i18n'

import { StrictMode } from 'react'
import { createRoot } from 'react-dom/client'
import { BrowserRouter } from 'react-router-dom'
import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import './index.css'
import App from './App.tsx'

const queryClient = new QueryClient({
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
