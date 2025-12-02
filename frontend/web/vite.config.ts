import { defineConfig } from 'vite'
import react from '@vitejs/plugin-react'
import path from 'path'

// https://vite.dev/config/
export default defineConfig({
  plugins: [react()],
  resolve: {
    alias: {
      '@': path.resolve(__dirname, './src'),
    },
  },
  // 生产环境移除 console.log 和 debugger
  esbuild: {
    drop: ['console', 'debugger'],
  },
  build: {
    minify: 'esbuild',  // 使用 esbuild（更快）
    rollupOptions: {
      output: {
        manualChunks: {
          'react-vendor': ['react', 'react-dom', 'react-router-dom'],
          'antd-vendor': ['antd', '@ant-design/icons'],
          'query-vendor': ['@tanstack/react-query'],
          'echarts-vendor': ['echarts'],
          'cytoscape-vendor': ['cytoscape', 'cytoscape-svg'],
        },
      },
    },
    chunkSizeWarningLimit: 600,
  },
})
