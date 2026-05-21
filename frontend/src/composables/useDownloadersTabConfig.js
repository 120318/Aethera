import { reactive, ref } from 'vue'

import { getDownloadersTabConfig } from '@/api/config'
import { t } from '@/i18n'

export function useDownloadersTabConfig() {
  const loading = ref(false)
  const loaded = ref(false)
  const config = reactive({
    download: {
      default_downloader_id: null,
    },
    downloaders: [],
  })

  async function fetchConfig(force = false) {
    if (loading.value || (loaded.value && !force)) {
      return
    }
    loading.value = true
    try {
      const payload = await getDownloadersTabConfig()
      config.download = payload.download || { default_downloader_id: null }
      config.downloaders = payload.downloaders || []
      loaded.value = true
    } catch (error) {
      console.error(t('settings.downloader.loadConfigFailed'), error)
    } finally {
      loading.value = false
    }
  }

  function patchConfig(patch) {
    Object.assign(config, patch)
  }

  function invalidate() {
    loaded.value = false
  }

  return {
    config,
    loading,
    loaded,
    fetchConfig,
    patchConfig,
    invalidate,
  }
}
