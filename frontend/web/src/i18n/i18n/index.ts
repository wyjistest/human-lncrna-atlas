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

// ============ 导入翻译资源 ============

// 简体中文
import zhCommon from './locales/zh-CN/common.json'
import zhNav from './locales/zh-CN/nav.json'
import zhHome from './locales/zh-CN/home.json'
import zhStats from './locales/zh-CN/stats.json'
import zhGenes from './locales/zh-CN/genes.json'
import zhDiseases from './locales/zh-CN/diseases.json'
import zhRegulations from './locales/zh-CN/regulations.json'
import zhNetwork from './locales/zh-CN/network.json'
import zhGenomeBrowser from './locales/zh-CN/genomeBrowser.json'
import zhOverlap from './locales/zh-CN/overlap.json'

// English
import enCommon from './locales/en/common.json'
import enNav from './locales/en/nav.json'
import enHome from './locales/en/home.json'
import enStats from './locales/en/stats.json'
import enGenes from './locales/en/genes.json'
import enDiseases from './locales/en/diseases.json'
import enRegulations from './locales/en/regulations.json'
import enNetwork from './locales/en/network.json'
import enGenomeBrowser from './locales/en/genomeBrowser.json'
import enOverlap from './locales/en/overlap.json'

// ============ 资源配置 ============

const resources = {
  'zh-CN': {
    common: zhCommon,
    nav: zhNav,
    home: zhHome,
    stats: zhStats,
    genes: zhGenes,
    diseases: zhDiseases,
    regulations: zhRegulations,
    network: zhNetwork,
    genomeBrowser: zhGenomeBrowser,
    overlap: zhOverlap
  },
  en: {
    common: enCommon,
    nav: enNav,
    home: enHome,
    stats: enStats,
    genes: enGenes,
    diseases: enDiseases,
    regulations: enRegulations,
    network: enNetwork,
    genomeBrowser: enGenomeBrowser,
    overlap: enOverlap
  }
}

// ============ 支持的语言 ============

export const SUPPORTED_LANGUAGES = [
  { code: 'zh-CN', label: '简体中文', flag: '🇨🇳' },
  { code: 'en', label: 'English', flag: '🇺🇸' }
] as const

export type SupportedLanguage = (typeof SUPPORTED_LANGUAGES)[number]['code']

// ============ 初始化 ============

i18n
  .use(LanguageDetector)
  .use(initReactI18next)
  .init({
    resources,
    fallbackLng: 'zh-CN',
    defaultNS: 'common',
    ns: ['common', 'nav', 'home', 'stats', 'genes', 'diseases', 'regulations', 'network', 'genomeBrowser', 'overlap'],

    interpolation: {
      escapeValue: false // React 已处理 XSS
    },

    detection: {
      order: ['localStorage', 'navigator'],
      caches: ['localStorage'],
      lookupLocalStorage: 'i18n_lang'
    },

    react: {
      useSuspense: false // 避免 SSR 问题
    }
  })

export default i18n
