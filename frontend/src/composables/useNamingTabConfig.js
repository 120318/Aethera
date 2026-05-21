import { reactive, ref } from 'vue'

import { getNamingTabConfig } from '@/api/config'
import { t } from '@/i18n'

export function useNamingTabConfig() {
  const loading = ref(false)
  const loaded = ref(false)
  const config = reactive({
    naming_templates: [],
    default_movie_template_id: null,
    default_tv_template_id: null,
  })

  async function fetchConfig(force = false) {
    if (loading.value || (loaded.value && !force)) {
      return
    }
    loading.value = true
    try {
      const payload = await getNamingTabConfig()
      config.naming_templates = payload.naming_templates || []
      config.default_movie_template_id = payload.default_movie_template_id || null
      config.default_tv_template_id = payload.default_tv_template_id || null
      loaded.value = true
    } catch (error) {
      console.error(t('settings.naming.loadConfigFailed'), error)
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
