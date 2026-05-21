import { computed, reactive, ref, watch } from 'vue'
import { checkTaskDelete, getTaskDetail as fetchTaskDetail } from '@/api/resource'
import { getErrorStageText } from '@/utils/taskStatus'
import { useI18n } from 'vue-i18n'

export function useTaskLiveDialogs(options = {}) {
  const { t } = useI18n()
  const {
    handleDelete,
  } = options

  const detailVisible = ref(false)
  const currentTask = ref(null)
  const currentTaskRaw = ref(null)
  const detailShowRaw = ref(false)
  const detailLoading = ref(false)
  const detailLoadingTaskId = ref('')
  const deleteConfirmVisible = ref(false)
  const taskToDelete = ref(null)
  const deleteExecuting = ref(false)
  const forceDelete = ref(false)
  const deleteFiles = ref(true)
  const deleteLibraryFiles = ref(false)
  const deleteMeta = reactive({ hasLibraryFiles: false, libraryFilesCount: 0 })

  const deleteTargetLabel = computed(() => (
    taskToDelete.value?.title || taskToDelete.value?.name || taskToDelete.value?.id || t('taskLive.thisTask')
  ))
  const prettyCurrentTask = computed(() => JSON.stringify(currentTaskRaw.value || currentTask.value, null, 2))
  const currentTaskDetailUrl = computed(() => getTaskDetailUrl(currentTask.value || {}))
  const currentTaskHash = computed(() => (
    currentTask.value?.info_hash
    || currentTask.value?.hash
    || currentTask.value?.torrent_hash
    || currentTask.value?.task_data?.info_hash
    || currentTask.value?.task_data?.hash
    || currentTask.value?.task_data?.torrent_hash
    || '-'
  ))
  const currentTaskTracker = computed(() => (
    currentTask.value?.site
    || currentTask.value?.indexer
    || currentTask.value?.tracker
    || '-'
  ))
  const currentTaskAttributes = computed(() => currentTask.value?.attributes || {})
  const isCurrentTaskTv = computed(() => {
    const attrs = currentTaskAttributes.value
    return (Array.isArray(attrs.seasons) && attrs.seasons.length > 0)
      || (Array.isArray(attrs.episodes) && attrs.episodes.length > 0)
  })
  const currentTaskSeasonDisplay = computed(() => {
    const attrs = currentTaskAttributes.value
    const seasonRaw = Array.isArray(attrs.seasons) && attrs.seasons.length > 0 ? attrs.seasons[0] : null
    const seasonNum = Number(seasonRaw)
    return Number.isFinite(seasonNum) ? t('taskLive.seasonLabel', { number: seasonNum }) : ''
  })
  const currentTaskEpisodeDisplay = computed(() => {
    const attrs = currentTaskAttributes.value
    const episodeRaw = Array.isArray(attrs.episodes) && attrs.episodes.length > 0 ? attrs.episodes[0] : null
    const episodeNum = Number(episodeRaw)
    return Number.isFinite(episodeNum) ? t('taskLive.episodeLabel', { number: episodeNum }) : ''
  })
  const hasCurrentTaskSpecs = computed(() => {
    const attrs = currentTaskAttributes.value
    return Object.values(attrs).some((value) => {
      if (Array.isArray(value)) return value.length > 0
      return value !== null && value !== undefined && value !== ''
    })
  })
  const combinedTaskError = computed(() => {
    const stage = getErrorStageText(currentTask.value?.error_stage || currentTask.value?.task_data?.error_stage) || '-'
    const key = currentTask.value?.error_key || currentTask.value?.task_data?.error_key
    const params = currentTask.value?.error_params || currentTask.value?.task_data?.error_params || {}
    const message = key ? t(key, params) : '-'
    return `${stage}-${message}`
  })

  function getTaskDetailUrl(task) {
    return task.page_url || task.detail_url || task.torrent_url || ''
  }
  function mapTaskForDetail(task, fallbackTask = null) {
    const rawTask = task?.raw_task || task || {}
    const viewTask = task?.task || task || {}
    const hash = rawTask?.torrent_hash || viewTask?.torrent_hash || fallbackTask?.info_hash || fallbackTask?.hash || ''
    return {
      ...(fallbackTask || {}),
      id: viewTask?.id || rawTask?.id || fallbackTask?.id || '',
      title: viewTask?.title || fallbackTask?.title || t('downloadDialog.unknownResource'),
      description: viewTask?.description || fallbackTask?.description || '',
      attributes: viewTask?.attributes || fallbackTask?.attributes || {},
      phase: viewTask?.phase || fallbackTask?.phase || '',
      phase_group: viewTask?.phase_group || fallbackTask?.phase_group || '',
      phase_label: viewTask?.phase_label || fallbackTask?.phase_label || '',
      phase_label_key: viewTask?.phase_label_key || fallbackTask?.phase_label_key || '',
      attention_reason_key: viewTask?.attention_reason_key || fallbackTask?.attention_reason_key || '',
      attention_reason_params: viewTask?.attention_reason_params || fallbackTask?.attention_reason_params || {},
      actions: viewTask?.actions || fallbackTask?.actions || [],
      action_states: viewTask?.action_states || fallbackTask?.action_states || [],
      realtime: viewTask?.realtime || fallbackTask?.realtime || {},
      task_data: {
        ...(rawTask || {}),
        download_client: viewTask?.download_client || rawTask?.download_client || fallbackTask?.task_data?.download_client || '',
        download_client_url: viewTask?.download_client_url || rawTask?.download_client_url || fallbackTask?.task_data?.download_client_url || '',
      },
      progress: viewTask?.progress ?? rawTask?.progress ?? fallbackTask?.progress ?? 0,
      status: rawTask?.status || viewTask?.status || fallbackTask?.status || '',
      state: viewTask?.realtime?.torrent_state || fallbackTask?.state || '',
      added_on: rawTask?.added_on || rawTask?.created_at || viewTask?.created_at || fallbackTask?.added_on || 0,
      size: viewTask?.size || rawTask?.size || rawTask?.metadata?.size || fallbackTask?.size || 0,
      info_hash: hash,
      hash: hash,
      torrent_hash: rawTask?.torrent_hash || viewTask?.torrent_hash || fallbackTask?.torrent_hash || hash,
      download_client: viewTask?.download_client || rawTask?.download_client || fallbackTask?.download_client || fallbackTask?.task_data?.download_client || '',
      download_client_url: viewTask?.download_client_url || rawTask?.download_client_url || fallbackTask?.download_client_url || fallbackTask?.task_data?.download_client_url || '',
      downloader_id: rawTask?.downloader_id || fallbackTask?.downloader_id || '',
      directory_name: viewTask?.directory_name || fallbackTask?.directory_name || '',
      save_path: viewTask?.save_path || rawTask?.save_path || fallbackTask?.save_path || '',
      category: rawTask?.category || fallbackTask?.category || '',
      tracker: viewTask?.site || viewTask?.indexer || rawTask?.tracker || fallbackTask?.tracker || '',
      indexer: viewTask?.indexer || fallbackTask?.indexer || '',
      site: viewTask?.site || viewTask?.indexer || fallbackTask?.site || fallbackTask?.tracker || '',
      page_url: viewTask?.page_url || fallbackTask?.page_url || '',
      detail_url: viewTask?.detail_url || fallbackTask?.detail_url || '',
      torrent_url: viewTask?.torrent_url || fallbackTask?.torrent_url || '',
      error_stage: rawTask?.error_stage || viewTask?.error_stage || fallbackTask?.error_stage || '',
      error_key: rawTask?.error_key || viewTask?.error_key || fallbackTask?.error_key || '',
      error_params: rawTask?.error_params || viewTask?.error_params || fallbackTask?.error_params || {},
      file_structure: rawTask?.metadata?.files || viewTask?.metadata?.files || fallbackTask?.file_structure || [],
      realtime_unavailable: viewTask?.realtime?.available === false,
    }
  }

  async function showTaskDetail(task) {
    currentTask.value = task
    detailVisible.value = true
    const taskId = task?.id || task?.task_data?.id
    if (!taskId) return
    if (detailLoading.value && detailLoadingTaskId.value === taskId) return

    detailLoading.value = true
    detailLoadingTaskId.value = taskId
    try {
      const res = await fetchTaskDetail(taskId)
      const responseTask = res?.task || res?.data?.task || null
      currentTaskRaw.value = res?.raw_task || res?.data?.raw_task || null
      if (responseTask) {
        currentTask.value = mapTaskForDetail({ task: responseTask, raw_task: currentTaskRaw.value }, task)
      }
    } catch {
      // Keep list item fallback to avoid blocking dialog.
    } finally {
      detailLoading.value = false
      detailLoadingTaskId.value = ''
    }
  }

  function toggleDetailRaw() { detailShowRaw.value = !detailShowRaw.value }
  async function confirmDelete(task) {
    taskToDelete.value = task
    forceDelete.value = false
    deleteFiles.value = true
    deleteLibraryFiles.value = false
    deleteMeta.hasLibraryFiles = false
    deleteMeta.libraryFilesCount = 0

    const taskId = task?.id || task?.task_data?.id || task?.torrent_hash || task?.hash || task?.info_hash || ''
    if (taskId) {
      try {
        const info = await checkTaskDelete(taskId)
        deleteMeta.hasLibraryFiles = !!info?.has_library_files
        deleteMeta.libraryFilesCount = Number(info?.library_files_count || 0)
      } catch {
        // Ignore; deletion can proceed without the extra prompt.
      }
    }

    deleteConfirmVisible.value = true
  }
  async function executeDelete() {
    if (!taskToDelete.value || deleteExecuting.value) return
    deleteExecuting.value = true
    try {
      await handleDelete(taskToDelete.value, {
        force: forceDelete.value,
        deleteLibraryFiles: deleteLibraryFiles.value,
        deleteFiles: deleteFiles.value,
      })
      deleteConfirmVisible.value = false
      taskToDelete.value = null
    } finally {
      deleteExecuting.value = false
    }
  }

  watch(detailVisible, (visible) => {
    if (!visible) {
      detailShowRaw.value = false
      detailLoading.value = false
      detailLoadingTaskId.value = ''
      currentTaskRaw.value = null
    }
  })

  watch(deleteConfirmVisible, (visible) => {
    if (!visible) {
      deleteExecuting.value = false
    }
  })
  return {
    detailVisible,
    currentTask,
    detailShowRaw,
    detailLoading,
    deleteConfirmVisible,
    taskToDelete,
    deleteExecuting,
    forceDelete,
    deleteFiles,
    deleteLibraryFiles,
    deleteMeta,
    deleteTargetLabel,
    prettyCurrentTask,
    currentTaskDetailUrl,
    currentTaskHash,
    currentTaskTracker,
    isCurrentTaskTv,
    currentTaskSeasonDisplay,
    currentTaskEpisodeDisplay,
    hasCurrentTaskSpecs,
    combinedTaskError,
    getTaskDetailUrl,
    showTaskDetail,
    toggleDetailRaw,
    confirmDelete,
    executeDelete,
  }
}
