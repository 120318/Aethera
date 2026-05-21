import { reactive, ref } from 'vue'

import { getMediaServersTabConfig } from '@/api/config'
import { t } from '@/i18n'

export function useMediaServersTabConfig() {
  const loading = ref(false)
  const loaded = ref(false)
  const config = reactive({
    media_servers: [],
    default_media_server_id: null,
  })

  async function fetchConfig(force = false) {
    if (loading.value || (loaded.value && !force)) {
      return
    }
    loading.value = true
    try {
      const payload = await getMediaServersTabConfig()
      config.media_servers = payload.media_servers || []
      config.default_media_server_id = payload.default_media_server_id || null
      loaded.value = true
    } catch (error) {
      console.error(t('settings.mediaServer.loadConfigFailed'), error)
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
