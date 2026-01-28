/**
 * 语言切换组件
 *
 * 支持简体中文和英文切换，状态持久化到 localStorage
 */

import { Select } from 'antd'
import { GlobalOutlined } from '@ant-design/icons'
import { useTranslation } from 'react-i18next'
import { SUPPORTED_LANGUAGES } from '@/i18n'

export function LanguageSwitch() {
  const { i18n } = useTranslation()

  const handleChange = (lang: string) => {
    i18n.changeLanguage(lang)
  }

  // 当前语言（处理 zh-CN 和 zh 的兼容）
  const currentLang = i18n.language?.startsWith('zh') ? 'zh-CN' : 'en'

  return (
    <Select
      aria-label={currentLang === 'zh-CN' ? '语言' : 'Language'}
      data-testid="language-switcher"
      className="language-switcher"
      value={currentLang}
      onChange={handleChange}
      options={SUPPORTED_LANGUAGES.map(lang => ({
        value: lang.code,
        label: (
          <span>
            <span style={{ marginRight: 6 }}>{lang.flag}</span>
            {lang.label}
          </span>
        )
      }))}
      style={{ width: 130 }}
      variant="borderless"
      suffixIcon={<GlobalOutlined style={{ color: 'rgba(255,255,255,0.65)' }} />}
      popupMatchSelectWidth={false}
    />
  )
}
