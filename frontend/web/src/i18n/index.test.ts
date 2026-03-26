import { describe, expect, it, vi } from 'vitest'

type I18nModule = typeof import('./index') & {
  ensureNamespaces?: (namespaces: string | readonly string[]) => Promise<void>
}

async function loadI18nModule(): Promise<I18nModule> {
  vi.resetModules()
  window.localStorage.clear()

  const i18nModule = await import('./index') as I18nModule
  await waitForInitialization(i18nModule.default)

  return i18nModule
}

async function waitForInitialization(i18n: {
  isInitialized: boolean
  on: (event: string, callback: () => void) => void
  off: (event: string, callback: () => void) => void
}) {
  if (i18n.isInitialized) {
    return
  }

  await new Promise<void>((resolve) => {
    const handleInitialized = () => {
      i18n.off('initialized', handleInitialized)
      resolve()
    }

    i18n.on('initialized', handleInitialized)
  })
}

describe('i18n namespace loading', () => {
  it('只在启动时注册首页首屏所需的基础命名空间', async () => {
    const i18nModule = await loadI18nModule()

    expect(i18nModule.default.hasResourceBundle('zh-CN', 'common')).toBe(true)
    expect(i18nModule.default.hasResourceBundle('zh-CN', 'nav')).toBe(true)
    expect(i18nModule.default.hasResourceBundle('zh-CN', 'home')).toBe(true)

    expect(i18nModule.default.hasResourceBundle('zh-CN', 'stats')).toBe(false)
    expect(i18nModule.default.hasResourceBundle('en', 'stats')).toBe(false)
    expect(i18nModule.default.hasResourceBundle('zh-CN', 'globalCompare')).toBe(false)
    expect(i18nModule.default.hasResourceBundle('en', 'globalCompare')).toBe(false)
  })

  it('按需加载页面命名空间，并同时注册所有支持语言的资源', async () => {
    const i18nModule = await loadI18nModule()

    expect(typeof i18nModule.ensureNamespaces).toBe('function')

    await i18nModule.ensureNamespaces?.(['stats', 'globalCompare'])

    expect(i18nModule.default.hasResourceBundle('zh-CN', 'stats')).toBe(true)
    expect(i18nModule.default.hasResourceBundle('en', 'stats')).toBe(true)
    expect(i18nModule.default.hasResourceBundle('zh-CN', 'globalCompare')).toBe(true)
    expect(i18nModule.default.hasResourceBundle('en', 'globalCompare')).toBe(true)
  })
})
