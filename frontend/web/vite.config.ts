import { defineConfig, loadEnv } from 'vite'
import react from '@vitejs/plugin-react'
import path from 'path'

// https://vite.dev/config/
export default defineConfig(({ mode }) => {
  // SECURITY: Disallow embedding Admin API Key into production bundles.
  // Any VITE_* env var is statically embedded into dist/ by Vite.
  const env = loadEnv(mode, process.cwd(), '')
  const adminKey = (env.VITE_ADMIN_API_KEY || '').trim()
  if (mode === 'production' && adminKey) {
    throw new Error(
      'SECURITY: VITE_ADMIN_API_KEY must NOT be set for production builds. ' +
      'Use reverse proxy injection (recommended) or backend auth instead.'
    )
  }

  return ({
  plugins: [react()],
  resolve: {
    alias: {
      '@': path.resolve(__dirname, './src'),
    },
  },
  // Phase 9.17: 生产环境只删除 console.log/debug/info，保留 warn/error
  // console.warn/error 用于显示安全警告和错误信息，不应被删除
  // 参考: Codex 代码审查 - api.ts 的 Admin Key 警告在生产环境永远不显示
  esbuild: mode === 'production' ? {
    drop: ['debugger'],
    pure: ['console.log', 'console.debug', 'console.info'],  // 移除 log/debug/info，保留 warn/error
  } : {},
  build: {
    minify: 'esbuild',  // Use esbuild (faster)
    rollupOptions: {
      output: {
        manualChunks: {
          // Core React vendor (loaded immediately)
          'react-vendor': ['react', 'react-dom', 'react-router-dom'],

          // UI framework (loaded immediately)
          'antd-vendor': ['antd', '@ant-design/icons'],

          // Data fetching (loaded immediately)
          'query-vendor': ['@tanstack/react-query'],

          // Visualization - split into separate chunks for lazy loading
          // ECharts is large (~800KB), split for dynamic import
          'echarts-core': ['echarts'],
          'echarts-react': ['echarts-for-react'],

          // Network visualization (used on specific pages)
          'cytoscape-vendor': ['cytoscape', 'cytoscape-svg'],

          // Genome browser (large, dynamically loaded in GenomeBrowser component)
          'igv-vendor': ['igv'],

          // Export utilities (loaded on demand)
          'export-vendor': ['file-saver', 'jspdf', 'html2canvas', 'jszip'],

          // i18n (loaded immediately)
          'i18n-vendor': ['i18next', 'react-i18next', 'i18next-browser-languagedetector'],
        },
      },
    },
    // Increase warning limit slightly since we now have more fine-grained chunks
    chunkSizeWarningLimit: 650,
  },
  })
})
