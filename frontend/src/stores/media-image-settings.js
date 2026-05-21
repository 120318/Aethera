import { defineStore } from 'pinia'
import { ref } from 'vue'
import { getMetadataTabConfig } from '@/api/config'
import { t } from '@/i18n'

export const useMediaImageSettingsStore = defineStore('media-image-settings', () => {
  const tmdbProxyImages = ref(false)
  const doubanProxyImages = ref(true)
  const loaded = ref(false)
  const loading = ref(false)

  function patchFromServicesConfig(services = {}) {
    tmdbProxyImages.value = !!services?.themoviedb?.proxy_images
    doubanProxyImages.value = services?.douban?.proxy_images !== false
    loaded.value = true
  }

  async function fetch(force = false) {
    if (loading.value || (loaded.value && !force)) return
    loading.value = true
    try {
      const payload = await getMetadataTabConfig()
      patchFromServicesConfig(payload)
    } catch (error) {
      console.error(t('mediaImageSettings.fetchFailed'), error)
    } finally {
      loading.value = false
    }
  }

  return {
    tmdbProxyImages,
    doubanProxyImages,
    loaded,
    loading,
    patchFromServicesConfig,
    fetch,
  }
})
