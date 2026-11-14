import { ref, watch } from 'vue'
import { useI18n } from 'vue-i18n'
import { getTaskEpisodeSelection, updateTaskEpisodeSelection } from '@/api/resource'
import { useNotificationStore } from '@/stores/notification'

const emptySelection = () => ({ available_episodes: [], selected_episodes: [], locked_episodes: [], episode_count: null })

export function useTaskEpisodeSelection(emit) {
  const { t } = useI18n()
  const notification = useNotificationStore()
  const episodeSelectionVisible = ref(false)
  const episodeSelectionLoading = ref(false)
  const episodeSelectionSaving = ref(false)
  const episodeSelection = ref(emptySelection())
  const selectedEpisodes = ref([])
  let currentTaskId = ''
  let requestVersion = 0

  function reset() {
    requestVersion += 1
    currentTaskId = ''
    episodeSelection.value = emptySelection()
    selectedEpisodes.value = []
    episodeSelectionLoading.value = false
    episodeSelectionSaving.value = false
  }

  watch(episodeSelectionVisible, (visible) => { if (!visible) reset() }, { flush: 'sync' })

  async function handleSelectEpisodes(task) {
    const taskId = task?.id || task?.task_data?.id || ''
    if (!taskId) return
    reset()
    const version = requestVersion
    currentTaskId = taskId
    episodeSelectionVisible.value = true
    episodeSelectionLoading.value = true
    try {
      const payload = await getTaskEpisodeSelection(taskId)
      if (version !== requestVersion || !episodeSelectionVisible.value) return
      episodeSelection.value = payload
      selectedEpisodes.value = [...(payload.selected_episodes || [])]
    } catch {
      if (version === requestVersion) episodeSelectionVisible.value = false
    } finally {
      if (version === requestVersion) episodeSelectionLoading.value = false
    }
  }

  async function saveEpisodeSelection() {
    const taskId = currentTaskId
    if (!taskId || episodeSelectionLoading.value || episodeSelectionSaving.value || selectedEpisodes.value.length === 0) return
    const version = requestVersion
    episodeSelectionSaving.value = true
    try {
      await updateTaskEpisodeSelection(taskId, [...selectedEpisodes.value])
      emit('task-view-updated')
      emit('task-updated', { id: taskId })
      if (version !== requestVersion) return
      notification.success(t('episodeSelection.saved'))
      episodeSelectionVisible.value = false
    } catch {
      // The shared HTTP interceptor surfaces API errors; do not mutate another task's dialog.
    } finally {
      if (version === requestVersion) episodeSelectionSaving.value = false
    }
  }

  return {
    episodeSelectionVisible, episodeSelectionLoading, episodeSelectionSaving,
    episodeSelection, selectedEpisodes, handleSelectEpisodes, saveEpisodeSelection,
  }
}
