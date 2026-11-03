import { reactive, ref } from 'vue'

import { getAddonsTabConfig } from '@/api/config'
import { createInitialAddonConfig } from '@/addons/registry'
import { t } from '@/i18n'

export function useAddonsConfig() {
  const loading = ref(false)
  const loaded = ref(false)
  const addons = reactive(createInitialAddonConfig())

  async function fetchAddonsConfig(force = false) {
    if (loading.value || (loaded.value && !force)) {
      return
    }
    loading.value = true
    try {
      const data = await getAddonsTabConfig()
      Object.assign(addons, data.addons || data)
      loaded.value = true
    } catch (error) {
      console.error(t('settings.addons.loadConfigFailed'), error)
    } finally {
      loading.value = false
    }
  }

  return {
    addons,
    loading,
    loaded,
    fetchAddonsConfig,
  }
}
