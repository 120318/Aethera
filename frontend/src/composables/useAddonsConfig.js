import { reactive, ref } from 'vue'

import { getAddonsTabConfig } from '@/api/config'
import { t } from '@/i18n'

export function useAddonsConfig() {
  const loading = ref(false)
  const loaded = ref(false)
  const addons = reactive({
    auth: {
      enabled: false,
      default_provider_id: null,
      providers: [],
    },
    notifications: {
      enabled: false,
      channels: [],
    },
    danmu: {
      enabled: false,
      directory_ids: [],
      providers: ['iqiyi', 'bilibili', 'youku', 'qq'],
      backfill_enabled: true,
      backfill_interval_seconds: 21600,
      backfill_recent_days: 30,
      backfill_missing_window_days: 90,
      output_xml: true,
      output_ass: true,
      font_size: 60,
      font_opacity_percent: 80,
      scroll_duration_seconds: 20,
      density_percent: 20,
      display_area: 'top',
    },
  })

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
