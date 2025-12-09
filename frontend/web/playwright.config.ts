import { defineConfig, devices } from '@playwright/test'

/**
 * Playwright E2E 测试配置
 * @see https://playwright.dev/docs/test-configuration
 */
export default defineConfig({
  // 测试目录
  testDir: './e2e',

  // 完全并行运行测试
  fullyParallel: true,

  // CI 环境禁止 .only
  forbidOnly: !!process.env.CI,

  // CI 环境重试失败的测试
  retries: process.env.CI ? 2 : 0,

  // CI 环境使用单 worker
  workers: process.env.CI ? 1 : undefined,

  // 报告器配置
  reporter: [
    ['html', { open: 'never' }],
    ['list'],
  ],

  // 全局配置
  use: {
    // 基础 URL
    baseURL: process.env.BASE_URL || 'http://localhost:5173',

    // 失败时记录 trace
    trace: 'on-first-retry',

    // 失败时截图
    screenshot: 'only-on-failure',

    // 视频录制（仅失败时）
    video: 'on-first-retry',

    // 默认超时
    actionTimeout: 10000,
    navigationTimeout: 30000,
  },

  // 全局超时
  timeout: 60000,

  // 期望超时
  expect: {
    timeout: 10000,
  },

  // 浏览器配置
  projects: [
    {
      name: 'chromium',
      use: { ...devices['Desktop Chrome'] },
    },
    // 可选：添加更多浏览器
    // {
    //   name: 'firefox',
    //   use: { ...devices['Desktop Firefox'] },
    // },
  ],

  // Web 服务器配置（可选，如果需要自动启动）
  // webServer: {
  //   command: 'npm run dev',
  //   url: 'http://localhost:5173',
  //   reuseExistingServer: !process.env.CI,
  //   timeout: 120 * 1000,
  // },
})
