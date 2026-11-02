import { onMounted, ref } from 'vue'
import { useI18n } from 'vue-i18n'

import { getAddons } from '@/api/resource'
import { resolveLibraryAddonActions } from '@/addons/resourceActions'
import { useNotificationStore } from '@/stores/notification'
import { useOperationsStore } from '@/stores/operations'

export function useLocalResourceAddons({ mediaId, seasonNumber, emit }) {
  const { t } = useI18n()
  const notification = useNotificationStore()
  const operations = useOperationsStore()
  const subtitlesEnabled = ref(false)
  const addonResourceActions = ref([])
  const subtitleDialogVisible = ref(false)
  const subtitleResource = ref(null)
  const subtitleBatchLoading = ref(false)

  async function loadAddonActions() {
    try {
      const response = await getAddons()
      const addons = response?.items || []
      addonResourceActions.value = resolveLibraryAddonActions(addons)
      subtitlesEnabled.value = addons.some(item => item.name === 'subtitles' && item.enabled)
    } catch {
      addonResourceActions.value = []
      subtitlesEnabled.value = false
    }
  }

  async function fillMissing() {
    if (!mediaId.value) return
    subtitleBatchLoading.value = true
    try {
      const target = { media_id: mediaId.value }
      if (seasonNumber.value) target.season_number = seasonNumber.value
      const command = await operations.submitCommand(
        {
          type: 'addon.run',
          payload: {
            addon_id: 'subtitles',
            operation_id: 'fill_missing',
            target,
          },
        },
        { dedupeKey: `media:${mediaId.value}:${seasonNumber.value || ''}:subtitles.fill_missing` },
      )
      if (command) {
        emit('command-submitted', command)
        notification.success(t('localResources.subtitles.fillQueued'))
      }
    } finally {
      subtitleBatchLoading.value = false
    }
  }

  function openSubtitleSearch(resource) {
    subtitleResource.value = resource
    subtitleDialogVisible.value = true
  }

  onMounted(loadAddonActions)

  return {
    subtitlesEnabled,
    addonResourceActions,
    subtitleDialogVisible,
    subtitleResource,
    subtitleBatchLoading,
    fillMissing,
    openSubtitleSearch,
  }
}
