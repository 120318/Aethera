import { reactive, ref } from 'vue'

import { getMetadataTabConfig } from '@/api/config'
import { t } from '@/i18n'

export function useServicesConfig() {
  const loading = ref(false)
  const loaded = ref(false)
  const services = reactive({
    browse_source: 'douban',
    themoviedb: { api_key: '', proxy_images: false },
    douban: { discover_lists: [], proxy_images: true },
  })

  async function fetchServicesConfig(force = false) {
    if (loading.value || (loaded.value && !force)) {
      return
    }
    loading.value = true
    try {
      const payload = await getMetadataTabConfig()
      Object.assign(services, payload)
      loaded.value = true
    } catch (error) {
      console.error(t('settings.metadata.loadConfigFailed'), error)
    } finally {
      loading.value = false
    }
  }

  function patchServicesConfig(patch) {
    Object.assign(services, patch)
  }

  return {
    services,
    loading,
    loaded,
    fetchServicesConfig,
    patchServicesConfig,
  }
}
