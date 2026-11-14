import { computed, ref, watch } from 'vue'
import { useI18n } from 'vue-i18n'
import { previewResourceEpisodeSelection } from '@/api/resource'
import { buildMediaExecutionSnapshot, parseMediaId } from '@/composables/mediaIdentitySupport'
import { useNotificationStore } from '@/stores/notification'

const emptySelection = () => ({ selectable: false, available_episodes: [], selected_episodes: [], episode_count: null })

export function useDownloadEpisodeSelection(props) {
  const { t } = useI18n()
  const notification = useNotificationStore()
  const episodeSelection = ref(emptySelection())
  const selectedEpisodes = ref([])
  const episodeSelectionLoading = ref(false)
  const episodeSelectionError = ref(false)
  let requestVersion = 0
  const mediaType = computed(() => (
    props.mediaInfo?.media_type || props.mediaInfo?.type
    || parseMediaId(props.mediaInfo?.media_id || props.mediaInfo?.id)?.media_type || null
  ))
  const resultId = computed(() => {
    const resource = props.resourceData?.resource || props.resourceData || {}
    return resource.result_id || props.resourceData?.result_id || resource.id || props.resourceData?.id || ''
  })
  const showEpisodeSelection = computed(() => (
    mediaType.value === 'tv' && episodeSelection.value.selectable
    && episodeSelection.value.available_episodes.length > 1
  ))

  function reset() {
    requestVersion += 1
    episodeSelection.value = emptySelection()
    selectedEpisodes.value = []
    episodeSelectionLoading.value = false
    episodeSelectionError.value = false
  }

  async function load() {
    reset()
    const version = requestVersion
    if (mediaType.value !== 'tv' || !resultId.value) return
    const media = buildMediaExecutionSnapshot({
      ...props.mediaInfo,
      season_number: props.seasonNumber || props.mediaInfo?.season_number,
    })
    if (!media) return
    episodeSelectionLoading.value = true
    try {
      const preview = await previewResourceEpisodeSelection({ result_id: resultId.value, media })
      if (version !== requestVersion || !props.visible) return
      episodeSelection.value = preview
      selectedEpisodes.value = [...(preview.selected_episodes || [])]
    } catch (error) {
      if (version !== requestVersion || !props.visible) return
      episodeSelectionError.value = true
      notification.error(error?.response?.data?.message || t('episodeSelection.loadFailed'))
    } finally {
      if (version === requestVersion) episodeSelectionLoading.value = false
    }
  }

  watch(
    () => [props.visible, resultId.value, props.mediaInfo?.media_id, props.seasonNumber, props.mediaInfo?.season_number],
    ([visible]) => { if (visible) load(); else reset() },
    { immediate: true },
  )

  return { mediaType, episodeSelection, selectedEpisodes, episodeSelectionLoading, episodeSelectionError, showEpisodeSelection }
}
