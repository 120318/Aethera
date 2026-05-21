import { computed } from 'vue'
import { defineStore } from 'pinia'
import { SUPPORTED_LOCALES, i18n, setI18nLocale, t } from '@/i18n'

export const useLocaleStore = defineStore('locale', () => {
  const currentLocale = computed(() => i18n.global.locale.value)
  const availableLocales = computed(() => SUPPORTED_LOCALES.map((item) => ({
    ...item,
    label: t(item.labelKey),
  })))
  const currentLocaleLabel = computed(() => (
    availableLocales.value.find((item) => item.value === currentLocale.value)?.label || currentLocale.value
  ))

  function setLocale(locale) {
    setI18nLocale(locale)
  }

  return {
    currentLocale,
    currentLocaleLabel,
    availableLocales,
    setLocale,
  }
})
