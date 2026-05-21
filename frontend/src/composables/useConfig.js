import { ref, reactive } from 'vue'
import { getObjectConfig } from '@/api/config'
import { t } from '@/i18n'

export function useConfig() {
  const loading = ref(false)
  const loaded = ref(false)
  const config = reactive({
    themoviedb: {
      api_key: '',
      proxy_images: false,
    },
    douban: {
      discover_lists: [],
      proxy_images: true,
    },
    download: {
      default_downloader_id: null
    },
    downloaders: [],
    indexers: [],
    media_servers: [],
    directories: [],
    naming_templates: [],
    filter_presets: [],
    tags: [],
    default_media_server_id: null,
    default_indexer_id: null,
    default_movie_template_id: null,
    default_tv_template_id: null,
  })

  async function fetchConfig(force = false) {
    if (loading.value || (loaded.value && !force)) {
      return
    }
    loading.value = true
    try {
      const data = await getObjectConfig()
      const configData = data.config || data
      Object.assign(config, {
        themoviedb: configData.themoviedb || { api_key: '', proxy_images: false },
        douban: configData.douban || { discover_lists: [], proxy_images: true },
        download: configData.download || { default_downloader_id: null },
        downloaders: configData.downloaders || [],
        indexers: configData.indexers || [],
        media_servers: configData.media_servers || [],
        directories: configData.directories || [],
        naming_templates: configData.naming_templates || [],
        filter_presets: configData.filter_presets || [],
        tags: configData.tags || [],
        default_media_server_id: configData.default_media_server_id || null,
        default_indexer_id: configData.default_indexer_id || null,
        default_movie_template_id: configData.default_movie_template_id || null,
        default_tv_template_id: configData.default_tv_template_id || null,
      })
      loaded.value = true
    } catch (e) {
      console.error(t('settings.loadConfigFailed'), e)
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
