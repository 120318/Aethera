import { reactive, ref } from 'vue'

import { getSystemConfig } from '@/api/config'
import { t } from '@/i18n'

export function useSystemConfig() {
  const loading = ref(true)
  const system = reactive({
    download: {
      default_path: '/data/download',
      movies_category: 'movies',
      tv_category: 'tv',
      anime_category: 'anime',
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
    library: {
      media_file_extensions: [],
      default_movie_template_id: null,
      default_tv_template_id: null,
    },
  })

  async function fetchSystemConfig() {
    loading.value = true
    try {
      const data = await getSystemConfig()
      const payload = data.system || data
      Object.assign(system, payload)
    } catch (error) {
      console.error(t('settings.system.loadConfigFailed'), error)
    } finally {
      loading.value = false
    }
  }

  return {
    system,
    loading,
    fetchSystemConfig,
  }
}
