import { defineConfig } from 'vitest/config'
import react from '@vitejs/plugin-react'
import path from 'path'

export default defineConfig({
  plugins: [react()],
  test: {
    globals: true,
    environment: 'jsdom',
    setupFiles: './src/test/setup.ts',
    include: ['src/**/*.{test,spec}.{ts,tsx}'],
    coverage: {
      reporter: ['text', 'json', 'html'],
      exclude: ['node_modules/', 'src/test/'],
    },
    // Filter JSDOM CSS warnings (doesn't fully suppress due to worker threads,
    // but reduces noise). JSDOM doesn't support modern CSS used by Antd.
    onConsoleLog(log) {
      if (log.includes('Could not parse CSS stylesheet')) {
        return false
      }
    },
  },
  resolve: {
    alias: {
      '@': path.resolve(__dirname, './src'),
    },
  },
})
