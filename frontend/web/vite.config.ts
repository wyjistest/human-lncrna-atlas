import { defineConfig } from 'vite'
import react from '@vitejs/plugin-react'
import path from 'path'

// https://vite.dev/config/
export default defineConfig(({ mode }) => ({
  plugins: [react()],
  resolve: {
    alias: {
      '@': path.resolve(__dirname, './src'),
    },
  },
  // Remove console.* and debugger statements in production builds
  // Note: drop: ['console'] removes ALL console methods including console.error
  // This is intentional for production to reduce bundle size and prevent info leaks
  esbuild: mode === 'production' ? {
    drop: ['console', 'debugger'],
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
}))
