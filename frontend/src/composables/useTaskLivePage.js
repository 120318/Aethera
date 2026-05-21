import { computed, ref } from 'vue'
import { changeTaskDownloader, previewTaskDownloaderChange } from '@/api/resource'
import { getDirectoriesTabConfig, getDownloadersTabConfig } from '@/api/config'
import { useResourceTags } from '@/composables/useResourceTags'
import { useTaskOperations } from '@/composables/useTaskOperations'
import { useTaskLiveDialogs } from '@/composables/useTaskLiveDialogs'
import { useTaskLiveFilters } from '@/composables/useTaskLiveFilters'
import { useTaskLivePresentation } from '@/composables/useTaskLivePresentation'
import { useTaskLiveRealtime } from '@/composables/useTaskLiveRealtime'
import { buildEnhancedTaskWithOverride } from '@/composables/taskLiveViewState'
import { useOperationsStore } from '@/stores/operations'
import { useNotificationStore } from '@/stores/notification'
import { useI18n } from 'vue-i18n'

const DIRECTORY_DEFAULT_DOWNLOADER_ID = '__directory_default__'

function normalizeMediaType(value) {
  const normalized = String(value || '').toLowerCase()
  if (normalized === 'movie' || normalized === 'tv') return normalized
  return ''
}

function resolveMediaTypeFromId(mediaId) {
  const value = String(mediaId || '')
  if (value.includes(':movie:')) return 'movie'
  if (value.includes(':tv:')) return 'tv'
  return ''
}

function resolveTaskMediaType(task) {
  const direct = normalizeMediaType(
    task?.media_type
    || task?.task_data?.media_type
    || task?.context?.media?.media_type
    || task?.task_data?.context?.media?.media_type
    || task?.media?.media_type
  )
  if (direct) return direct
  const mediaId = String(
    task?.media_id
    || task?.task_data?.media_id
    || task?.context?.media?.media_id
    || task?.task_data?.context?.media?.media_id
    || task?.media?.media_id
    || ''
  )
  return resolveMediaTypeFromId(mediaId)
}

function resolveTaskDirectoryId(task) {
  return task?.directory_id || task?.task_data?.context?.directory_id || ''
}

function resolveTaskDownloaderId(task) {
  return task?.downloader_id || task?.task_data?.downloader_id || ''
}

function resolveTaskOperationKey(task) {
  return task?.id || task?.task_data?.id || task?.torrent_hash || task?.hash || task?.info_hash || ''
}

function resolveTaskScopedCommand(task, commands) {
  const key = resolveTaskOperationKey(task)
  if (!key || !Array.isArray(commands)) return null
  return commands.find((command) => (
    command?.target_type === 'task'
    && command?.target_id === key
  )) || null
}

function resolveTaskOperationStoreCommand(task, commands) {
  const key = resolveTaskOperationKey(task)
  const lookupCandidates = [
    task?.id,
    task?.task_data?.id,
    task?.torrent_hash,
    task?.hash,
    task?.info_hash,
  ].filter(Boolean)

  if (key && Array.isArray(commands)) {
    const directMatch = commands.find((command) => (
      command?.target_type === 'task'
      && command?.target_id === key
    )) || null
    if (directMatch) return directMatch
  }

  if (!Array.isArray(commands) || lookupCandidates.length === 0) return null
  return commands.find((command) => (
    command?.target_type === 'task'
    && lookupCandidates.includes(command?.payload?.task_id)
  )) || null
}

function resolveTaskActiveCommand(task, scopedCommands, operationsStoreCommands) {
  if (Array.isArray(scopedCommands)) {
    const scopedCommand = resolveTaskScopedCommand(task, scopedCommands)
    if (scopedCommand) return scopedCommand
  }

  if (!Array.isArray(scopedCommands)) {
    const operationCommand = resolveTaskOperationStoreCommand(task, operationsStoreCommands)
    if (operationCommand) return operationCommand
  }

  const activeCommandType = task?.active_command_type || ''
  const activeCommandId = task?.active_command_id || ''
  if (!activeCommandType || !activeCommandId) return null

  return {
    id: activeCommandId,
    type: activeCommandType,
    target_type: 'task',
    target_id: resolveTaskOperationKey(task),
  }
}

export function useTaskLivePage(props, emit) {
  const { t } = useI18n()
  const { getSortedTags } = useResourceTags()
  const tasksRef = computed(() => props.tasks || [])
  const operationCommandsRef = computed(() => props.operationCommands ?? null)
  const operationRealtimeOverridesRef = computed(() => props.operationRealtimeOverrides || {})
  const activeTabRef = computed(() => props.activeTab || 'resources')
  const operations = useOperationsStore()
  const notification = useNotificationStore()
  const downloaderChangeVisible = ref(false)
  const downloaderChangeTask = ref(null)
  const downloaderChangeLoading = ref(false)
  const downloaderChangeExecuting = ref(false)
  const downloaderChangePreview = ref(null)
  const downloaderChangeConfig = ref({ downloaders: [], directories: [] })
  const downloaderChangeForm = ref({
    target_downloader_id: '',
    target_directory_id: '',
  })
  const selectedDownloaderChangeDirectory = computed(() => (
    downloaderChangeConfig.value.directories.find((item) => item.id === downloaderChangeForm.value.target_directory_id) || null
  ))
  const downloaderChangeDownloaderOptions = computed(() => {
    const defaultDownloaderId = selectedDownloaderChangeDirectory.value?.downloader_id || ''
    const defaultDownloader = defaultDownloaderId
      ? downloaderChangeConfig.value.downloaders.find((item) => item.id === defaultDownloaderId)
      : null
    const defaultName = defaultDownloader?.name
      ? t('taskLive.changeDownloader.directoryDefaultDownloaderWithName', { name: defaultDownloader.name })
      : t('taskLive.changeDownloader.directoryDefaultDownloader')
    return [
      {
        id: DIRECTORY_DEFAULT_DOWNLOADER_ID,
        name: defaultName,
        disabled: !defaultDownloaderId,
      },
      ...downloaderChangeConfig.value.downloaders,
    ]
  })

  const {
    realtimeData,
    realtimeUnavailableTaskIds,
  } = useTaskLiveRealtime({
    tasks: tasksRef,
    activeTab: activeTabRef,
    operationCommands: operationCommandsRef,
    emit,
    operations,
  })

  const enhancedTasks = computed(() => (
    tasksRef.value.map((task) => {
      const taskKey = resolveTaskOperationKey(task)
      const realtimeOverride = taskKey ? operationRealtimeOverridesRef.value?.[taskKey] || null : null
      const activeCommand = resolveTaskActiveCommand(
        task,
        operationCommandsRef.value,
        operations.activeCommands,
      )
      return buildEnhancedTaskWithOverride(
        task,
        realtimeData.value,
        realtimeUnavailableTaskIds.value,
        realtimeOverride,
        activeCommand,
      )
    })
  ))

  const {
    currentFirst,
    localFilters,
    sortModel,
    statusOptions,
    sortOptions,
    episodeOptions,
    hasActiveFilters,
    paginatorPosition,
    filteredAndSortedTasks,
    clearFilters,
    rowsPerPage: ROWS_PER_PAGE,
  } = useTaskLiveFilters(enhancedTasks)

  const {
    isTaskPending,
    handlePause,
    handleResume,
    handleManualTransfer,
    handleMediaServerSync,
    handleDanmuGenerate,
    handleDelete,
  } = useTaskOperations(emit)

  async function loadDownloaderChangeConfig() {
    const [downloadersPayload, directoriesPayload] = await Promise.all([
      getDownloadersTabConfig(),
      getDirectoriesTabConfig(),
    ])
    const enabledDirectories = (directoriesPayload.directories || [])
      .filter((item) => item.enabled !== false)
    const currentDirectoryId = resolveTaskDirectoryId(downloaderChangeTask.value)
    const currentDirectory = enabledDirectories.find((item) => item.id === currentDirectoryId) || null
    const taskMediaType = normalizeMediaType(props.mediaType)
      || resolveMediaTypeFromId(props.mediaId)
      || resolveTaskMediaType(downloaderChangeTask.value)
      || normalizeMediaType(currentDirectory?.media_type)
    const directories = enabledDirectories
      .filter((item) => taskMediaType && normalizeMediaType(item.media_type) === taskMediaType)
    downloaderChangeConfig.value = {
      downloaders: (downloadersPayload.downloaders || []).filter((item) => item.enabled !== false),
      directories,
    }
  }

  function resolveTaskId(task) {
    return task?.id || task?.task_data?.id || ''
  }

  async function handleChangeDownloader(task) {
    downloaderChangeTask.value = task
    downloaderChangePreview.value = null
    downloaderChangeVisible.value = true
    downloaderChangeLoading.value = true
    try {
      await loadDownloaderChangeConfig()
      const directories = downloaderChangeConfig.value.directories
      const targetDirectory = directories[0] || null
      downloaderChangeForm.value = {
        target_downloader_id: DIRECTORY_DEFAULT_DOWNLOADER_ID,
        target_directory_id: targetDirectory?.id || '',
      }
    } catch (error) {
      notification.error(error?.message || t('taskLive.changeDownloader.loadFailed'))
    } finally {
      downloaderChangeLoading.value = false
    }
  }

  async function previewDownloaderChange() {
    const taskId = resolveTaskId(downloaderChangeTask.value)
    const payload = buildDownloaderChangePayload()
    if (!taskId || !payload) return
    downloaderChangeLoading.value = true
    try {
      downloaderChangePreview.value = await previewTaskDownloaderChange(taskId, payload)
    } catch (error) {
      notification.error(error?.response?.data?.message || error?.message || t('taskLive.changeDownloader.previewFailed'))
    } finally {
      downloaderChangeLoading.value = false
    }
  }

  async function executeDownloaderChange() {
    const taskId = resolveTaskId(downloaderChangeTask.value)
    const payload = buildDownloaderChangePayload()
    if (!taskId || !payload) return
    downloaderChangeExecuting.value = true
    try {
      const command = await changeTaskDownloader(taskId, payload)
      operations.registerSubmittedCommand(command)
      notification.success(t('taskLive.changeDownloader.success'))
      downloaderChangeVisible.value = false
      emit('command-submitted', command)
      emit('task-view-updated')
      emit('task-updated', { id: taskId })
    } catch {
      // API errors are already surfaced by the shared HTTP interceptor.
    } finally {
      downloaderChangeExecuting.value = false
    }
  }

  function resolveDownloaderChangePreviewMessage() {
    const preview = downloaderChangePreview.value
    if (!preview) return ''
    if (preview.blockers?.length) return t('taskLive.changeDownloader.previewBlocked')
    if (preview.warnings?.includes('target_directory_bound_to_different_downloader')) {
      return t('taskLive.changeDownloader.directoryDownloaderMismatch')
    }
    if (preview.warnings?.length) return t('taskLive.changeDownloader.previewWarning')
    return t('taskLive.changeDownloader.previewPassed')
  }

  function buildDownloaderChangePayload() {
    const targetDirectoryId = downloaderChangeForm.value.target_directory_id || ''
    let targetDownloaderId = downloaderChangeForm.value.target_downloader_id || ''
    if (targetDownloaderId === DIRECTORY_DEFAULT_DOWNLOADER_ID) {
      targetDownloaderId = selectedDownloaderChangeDirectory.value?.downloader_id || ''
    }
    if (!targetDirectoryId || !targetDownloaderId) return null
    if (
      targetDirectoryId === resolveTaskDirectoryId(downloaderChangeTask.value)
      && targetDownloaderId === resolveTaskDownloaderId(downloaderChangeTask.value)
    ) {
      return null
    }
    return {
      target_downloader_id: targetDownloaderId,
      target_directory_id: targetDirectoryId,
    }
  }

  const {
    detailVisible,
    currentTask,
    detailShowRaw,
    detailLoading,
    deleteConfirmVisible,
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
  } = useTaskLiveDialogs({
    handleDelete,
  })

  const {
    TASK_ACTIONS_CONFIG,
    getStatusButtonSeverity,
    getTaskStatusTooltip,
    getTaskStatusLabel,
    shouldShowStatusInfo,
    isActionVisible,
    isActionLoading,
    isActionDisabled,
  } = useTaskLivePresentation({
    showTaskDetail,
    confirmDelete,
    handlePause,
    handleResume,
    handleManualTransfer,
    handleMediaServerSync,
    handleDanmuGenerate,
    handleChangeDownloader,
    isTaskPending,
  })

  return {
    getSortedTags,
    currentFirst,
    localFilters,
    sortModel,
    statusOptions,
    sortOptions,
    episodeOptions,
    hasActiveFilters,
    paginatorPosition,
    filteredAndSortedTasks,
    clearFilters,
    ROWS_PER_PAGE,
    enhancedTasks,
    detailVisible,
    currentTask,
    detailShowRaw,
    detailLoading,
    deleteConfirmVisible,
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
    toggleDetailRaw,
    executeDelete,
    downloaderChangeVisible,
    downloaderChangeTask,
    downloaderChangeLoading,
    downloaderChangeExecuting,
    downloaderChangePreview,
    downloaderChangeConfig,
    downloaderChangeDownloaderOptions,
    downloaderChangeForm,
    previewDownloaderChange,
    executeDownloaderChange,
    resolveDownloaderChangePreviewMessage,
    TASK_ACTIONS_CONFIG,
    getStatusButtonSeverity,
    getTaskStatusTooltip,
    getTaskStatusLabel,
    shouldShowStatusInfo,
    isActionVisible,
    isActionLoading,
    isActionDisabled,
  }
}
