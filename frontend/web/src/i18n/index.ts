/**
 * i18n 国际化配置
 *
 * 支持语言：简体中文 (zh-CN)、English (en)
 * 默认语言：简体中文
 * 持久化：localStorage
 */

import i18n from 'i18next'
import { initReactI18next } from 'react-i18next'
import LanguageDetector from 'i18next-browser-languagedetector'

import zhCommon from './locales/zh-CN/common.json'
import zhNav from './locales/zh-CN/nav.json'
import zhHome from './locales/zh-CN/home.json'
import enCommon from './locales/en/common.json'
import enNav from './locales/en/nav.json'
import enHome from './locales/en/home.json'

type TranslationResource = Record<string, unknown>
type TranslationModule = { default: TranslationResource }

export const SUPPORTED_LANGUAGES = [
  { code: 'zh-CN', label: '简体中文', flag: '🇨🇳' },
  { code: 'en', label: 'English', flag: '🇺🇸' },
] as const

export type SupportedLanguage = (typeof SUPPORTED_LANGUAGES)[number]['code']

export const EAGER_NAMESPACES = ['common', 'nav', 'home'] as const
export const LAZY_NAMESPACES = [
  'stats',
  'genes',
  'diseases',
  'regulations',
  'network',
  'conservation',
  'genomeBrowser',
  'overlap',
  'globalCompare',
  'analysis',
  'visualization',
] as const

export type EagerNamespace = (typeof EAGER_NAMESPACES)[number]
export type LazyNamespace = (typeof LAZY_NAMESPACES)[number]
export type TranslationNamespace = EagerNamespace | LazyNamespace

const ALL_NAMESPACES = [...EAGER_NAMESPACES, ...LAZY_NAMESPACES] as const
const EAGER_NAMESPACE_SET = new Set<TranslationNamespace>(EAGER_NAMESPACES)

const eagerResources: Record<SupportedLanguage, Record<EagerNamespace, TranslationResource>> = {
  'zh-CN': {
    common: zhCommon,
    nav: zhNav,
    home: zhHome,
  },
  en: {
    common: enCommon,
    nav: enNav,
    home: enHome,
  },
}

const lazyResourceLoaders: Record<SupportedLanguage, Record<LazyNamespace, () => Promise<TranslationModule>>> = {
  'zh-CN': {
    stats: () => import('./locales/zh-CN/stats.json'),
    genes: () => import('./locales/zh-CN/genes.json'),
    diseases: () => import('./locales/zh-CN/diseases.json'),
    regulations: () => import('./locales/zh-CN/regulations.json'),
    network: () => import('./locales/zh-CN/network.json'),
    conservation: () => import('./locales/zh-CN/conservation.json'),
    genomeBrowser: () => import('./locales/zh-CN/genomeBrowser.json'),
    overlap: () => import('./locales/zh-CN/overlap.json'),
    globalCompare: () => import('./locales/zh-CN/globalCompare.json'),
    analysis: () => import('./locales/zh-CN/analysis.json'),
    visualization: () => import('./locales/zh-CN/visualization.json'),
  },
  en: {
    stats: () => import('./locales/en/stats.json'),
    genes: () => import('./locales/en/genes.json'),
    diseases: () => import('./locales/en/diseases.json'),
    regulations: () => import('./locales/en/regulations.json'),
    network: () => import('./locales/en/network.json'),
    conservation: () => import('./locales/en/conservation.json'),
    genomeBrowser: () => import('./locales/en/genomeBrowser.json'),
    overlap: () => import('./locales/en/overlap.json'),
    globalCompare: () => import('./locales/en/globalCompare.json'),
    analysis: () => import('./locales/en/analysis.json'),
    visualization: () => import('./locales/en/visualization.json'),
  },
}

const namespaceLoadPromises = new Map<LazyNamespace, Promise<void>>()

function toNamespaceList(
  namespaces: TranslationNamespace | readonly TranslationNamespace[],
): TranslationNamespace[] {
  if (typeof namespaces === 'string') {
    return [namespaces]
  }

  return [...new Set(namespaces)]
}

function waitForInitialization() {
  if (i18n.isInitialized) {
    return Promise.resolve()
  }

  return new Promise<void>((resolve) => {
    const handleInitialized = () => {
      i18n.off('initialized', handleInitialized)
      resolve()
    }

    i18n.on('initialized', handleInitialized)
  })
}

async function loadNamespace(namespace: LazyNamespace) {
  const existingPromise = namespaceLoadPromises.get(namespace)
  if (existingPromise) {
    return existingPromise
  }

  const loadPromise = Promise.all(
    SUPPORTED_LANGUAGES.map(async ({ code }) => {
      if (i18n.hasResourceBundle(code, namespace)) {
        return
      }

      const resourceModule = await lazyResourceLoaders[code][namespace]()
      i18n.addResourceBundle(code, namespace, resourceModule.default, true, true)
    }),
  ).then(() => undefined)

  namespaceLoadPromises.set(namespace, loadPromise)

  try {
    await loadPromise
  } catch (error) {
    namespaceLoadPromises.delete(namespace)
    throw error
  }
}

export async function ensureNamespaces(
  namespaces: TranslationNamespace | readonly TranslationNamespace[],
) {
  await waitForInitialization()

  const lazyNamespaces = toNamespaceList(namespaces).filter(
    (namespace): namespace is LazyNamespace => !EAGER_NAMESPACE_SET.has(namespace),
  )

  if (lazyNamespaces.length === 0) {
    return
  }

  await Promise.all(lazyNamespaces.map((namespace) => loadNamespace(namespace)))
}

i18n
  .use(LanguageDetector)
  .use(initReactI18next)
  .init({
    resources: eagerResources,
    fallbackLng: 'zh-CN',
    defaultNS: 'common',
    ns: ALL_NAMESPACES,
    interpolation: {
      escapeValue: false,
    },
    detection: {
      order: ['localStorage', 'navigator'],
      caches: ['localStorage'],
      lookupLocalStorage: 'i18n_lang',
    },
    react: {
      useSuspense: false,
    },
  })

export default i18n
