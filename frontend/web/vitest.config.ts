import { defineConfig } from 'vitest/config'
import react from '@vitejs/plugin-react'
import path from 'path'

export default defineConfig({
  plugins: [react()],
  test: {
    globals: true,
    environment: 'jsdom',
    testTimeout: 15000,
    setupFiles: './src/test/setup.ts',
    include: ['src/**/*.{test,spec}.{ts,tsx}'],
    coverage: {
      reporter: ['text', 'json', 'html'],
      exclude: ['node_modules/', 'src/test/'],
    },
    // Filter CSS parsing errors from console output (secondary layer)
    // Primary suppression is in setup.ts via stderr interception
    onConsoleLog(log) {
      if (log.includes('Could not parse CSS stylesheet')) {
        return false
      }
      return true
    },
  },
  resolve: {
    alias: {
      '@': path.resolve(__dirname, './src'),
    },
  },
})
