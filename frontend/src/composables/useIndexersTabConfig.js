import { reactive, ref } from 'vue'

import { getIndexersTabConfig } from '@/api/config'
import { t } from '@/i18n'

export function useIndexersTabConfig() {
  const loading = ref(false)
  const loaded = ref(false)
  const config = reactive({
    indexers: [],
  })

  async function fetchConfig(force = false) {
    if (loading.value || (loaded.value && !force)) {
      return
    }
    loading.value = true
    try {
      const payload = await getIndexersTabConfig()
      config.indexers = payload.indexers || []
      loaded.value = true
    } catch (error) {
      console.error(t('settings.indexer.loadConfigFailed'), error)
    } finally {
      loading.value = false
    }
  }

  function patchConfig(patch) {
    Object.assign(config, patch)
  }

  return {
    config,
    loading,
    loaded,
    fetchConfig,
    patchConfig,
  }
}
