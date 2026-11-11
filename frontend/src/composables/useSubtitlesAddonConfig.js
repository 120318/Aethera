import { computed, ref } from 'vue'
import { useI18n } from 'vue-i18n'

import { saveAddons } from '@/api/config'
import { useNotificationStore } from '@/stores/notification'

const DEFAULT_SUBTITLE_CONFIG = {
  enabled: false,
  provider: 'opensubtitles',
  api_key: '',
  username: '',
  password: '',
  languages: ['zh-cn', 'zh-tw', 'en'],
  auto_fill_enabled: false,
}

export function useSubtitlesAddonConfig(config) {
  const { t } = useI18n()
  const notification = useNotificationStore()
  const dialogVisible = ref(false)
  const saving = ref(false)

  function ensureConfig() {
    if (!config.value.addons.subtitles) {
      config.value.addons.subtitles = { ...DEFAULT_SUBTITLE_CONFIG }
    }
    return config.value.addons.subtitles
  }

  const subtitleConfig = computed(() => ensureConfig())
  const languageOptions = computed(() => [
    { label: t('settings.addons.subtitles.simplifiedChinese'), value: 'zh-cn' },
    { label: t('settings.addons.subtitles.traditionalChinese'), value: 'zh-tw' },
    { label: t('settings.addons.subtitles.english'), value: 'en' },
  ])

  async function persist() {
    saving.value = true
    try {
      const updated = await saveAddons(config.value.addons)
      Object.assign(config.value.addons, updated)
      notification.success(t('settings.addons.subtitles.saved'))
      return true
    } finally {
      saving.value = false
    }
  }

  async function toggleEnabled(enabled) {
    subtitleConfig.value.enabled = enabled
    await persist()
  }

  async function save() {
    if (await persist()) dialogVisible.value = false
  }

  return {
    dialogVisible,
    saving,
    subtitleConfig,
    languageOptions,
    toggleEnabled,
    save,
  }
}
