import { computed } from 'vue'
import { defineStore } from 'pinia'
import { getSystemConfig, saveSystemConfig } from '@/api/config'
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
    const normalized = setI18nLocale(locale)
    void syncBackendLocale(normalized)
  }

  async function syncBackendLocale(locale) {
    try {
      const data = await getSystemConfig()
      const system = data.system || data
      await saveSystemConfig({
        ...system,
        locale,
      })
    } catch (error) {
      console.error('Failed to sync backend locale', error)
    }
  }

  return {
    currentLocale,
    currentLocaleLabel,
    availableLocales,
    setLocale,
  }
})
