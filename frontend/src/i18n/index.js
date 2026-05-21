import { createI18n } from 'vue-i18n'
import zhCN from './locales/zh-CN'
import enUS from './locales/en-US'

export const SUPPORTED_LOCALES = [
  { value: 'zh-CN', labelKey: 'language.zhCN' },
  { value: 'en-US', labelKey: 'language.enUS' },
]

const STORAGE_KEY = 'locale-preference'
const FALLBACK_LOCALE = 'zh-CN'

function normalizeLocale(value) {
  if (!value) return ''
  const normalized = String(value).replace('_', '-').toLowerCase()
  if (normalized === 'zh' || normalized.startsWith('zh-cn') || normalized.startsWith('zh-hans')) {
    return 'zh-CN'
  }
  if (normalized === 'en' || normalized.startsWith('en-')) {
    return 'en-US'
  }
  return ''
}

export function detectInitialLocale() {
  const stored = normalizeLocale(window.localStorage.getItem(STORAGE_KEY))
  if (stored) return stored

  for (const language of window.navigator.languages || []) {
    const matched = normalizeLocale(language)
    if (matched) return matched
  }

  return normalizeLocale(window.navigator.language) || FALLBACK_LOCALE
}

export const i18n = createI18n({
  legacy: false,
  globalInjection: true,
  locale: detectInitialLocale(),
  fallbackLocale: FALLBACK_LOCALE,
  messages: {
    'zh-CN': zhCN,
    'en-US': enUS,
  },
})

export function setI18nLocale(locale) {
  const normalized = normalizeLocale(locale) || FALLBACK_LOCALE
  i18n.global.locale.value = normalized
  window.localStorage.setItem(STORAGE_KEY, normalized)
  document.documentElement.lang = normalized
}

export function t(key, params) {
  return i18n.global.t(key, params)
}

document.documentElement.lang = i18n.global.locale.value
