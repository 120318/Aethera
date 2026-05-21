import { reactive, ref } from 'vue'

import { getSystemTabConfig } from '@/api/config'
import { t } from '@/i18n'

export function useSystemSettings() {
  const loading = ref(false)
  const loaded = ref(false)
  const systemConfig = reactive({
    download: {
      default_path: '/data/download',
      movies_category: 'movies',
      tv_category: 'tv',
      anime_category: 'anime',
      default_tag: 'Aethera',
    },
    logging: {
      dir: '/config/logs',
      file: 'backend.log',
      level: 'INFO',
      server_retention_days: 7,
    },
    scheduler: {
      sync_active_downloads_interval_seconds: 30,
      process_completed_tasks_interval_seconds: 60,
      subscription_sweep_interval_seconds: 600,
      schedule_refresh_sweep_interval_seconds: 21600,
      cleanup_expired_sessions_interval_seconds: 3600,
    },
    auth: {
      enabled: true,
      session_ttl_seconds: 86400,
    },
    library: {},
  })

  async function fetchSystemSettings(force = false) {
    if (loading.value || (loaded.value && !force)) {
      return
    }
    loading.value = true
    try {
      const payload = await getSystemTabConfig()
      Object.assign(systemConfig.download, payload.download || {})
      Object.assign(systemConfig.logging, payload.logging || {})
      Object.assign(systemConfig.auth, payload.auth || {})
      Object.assign(systemConfig.scheduler, payload.scheduler || {})
      loaded.value = true
    } catch (error) {
      console.error(t('settings.system.loadSettingsFailed'), error)
    } finally {
      loading.value = false
    }
  }

  function patchSystemConfig(patch) {
    Object.assign(systemConfig, patch)
  }

  return {
    systemConfig,
    loading,
    loaded,
    fetchSystemSettings,
    patchSystemConfig,
  }
}
