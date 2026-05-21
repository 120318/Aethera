import { computed, nextTick, onUnmounted, ref, watch } from 'vue'
import { searchResources } from '@/api/resource'
import { useActionPrerequisites } from '@/composables/useActionPrerequisites'
import { useCommandRuntime } from '@/composables/useCommandRuntime'
import { useOperationsStore } from '@/stores/operations'
import { resolveLocalizedRecordMessage } from '@/utils/localizedMessage'
import { useI18n } from 'vue-i18n'

const TASK_REALTIME_OVERRIDE_TTL_MS = 3500
const TASK_CREATE_REFRESH_RETRY_COUNT = 4
const TASK_CREATE_REFRESH_RETRY_DELAY_MS = 500
const DOWNLOAD_CREATION_COMMAND_TYPES = ['task.create', 'pilot.episode']
const SUBSCRIPTION_COMMAND_TYPES = ['subscription.run']
const PROFILE_REFRESH_COMMAND_TYPES = ['profile.refresh']
const TASK_COMMAND_TYPES = ['task.pause', 'task.resume', 'task.transfer', 'task.media_server_sync', 'task.danmu_generate', 'task.storage_change', 'task.delete']
const LIBRARY_FILE_COMMAND_TYPES = ['library_file.delete', 'library_file.media_server_sync', 'library_file.danmu_generate']
const MEDIA_DETAIL_COMMAND_TYPES = [
  'resource.search',
  ...DOWNLOAD_CREATION_COMMAND_TYPES,
  ...SUBSCRIPTION_COMMAND_TYPES,
  ...PROFILE_REFRESH_COMMAND_TYPES,
  ...TASK_COMMAND_TYPES,
  ...LIBRARY_FILE_COMMAND_TYPES,
]

function isMovieMediaTarget(value) {
  return String(value || '').includes(':movie:')
}

function isTvMediaTarget(value) {
  return String(value || '').includes(':tv:')
}

function resolvePilotCommandLabel(command) {
  return isMovieMediaTarget(command?.target_id || command?.media_id || command?.payload?.media?.media_id)
    ? 'download'
    : 'pilot'
}

export function useMediaDetailCommands(options = {}) {
  const {
    mediaId,
    selectedSeasonNumber,
    activeTab,
    tabData,
    detailOverview,
    fetchDetail,
    handleCheckSubscription,
    loadResourceInfo,
    loadDetailOverview,
    loadTaskInfo,
    markTaskDeleted,
    notification,
  } = options
  const detailOverviewSummary = computed(() => detailOverview?.value?.summary || null)
  const { t } = useI18n()
  const operations = useOperationsStore()
  const actionReadiness = computed(() => detailOverviewSummary.value?.action_readiness || null)
  const { ensureSearchReady } = useActionPrerequisites({ readinessSource: actionReadiness })

  const checkingSearch = ref(false)
  const searchTrigger = ref(0)
  const searchResultsRefreshTrigger = ref(0)
  const searchInProgress = ref(false)
  const shouldAutoOpenSearchTab = ref(false)
  const taskCreatePending = ref(false)
  const pendingTaskPreview = ref(null)
  const taskCreateBaselineCount = ref(0)
  const taskRealtimeOverrides = ref({})
  const taskRealtimeOverrideTimers = new Map()
  const commandRuntime = useCommandRuntime({
    scope: () => ({
      mediaId: mediaId.value,
      seasonNumber: selectedSeasonNumber?.value || null,
    }),
    commandTypes: MEDIA_DETAIL_COMMAND_TYPES,
    onTerminal: handleCommandCompletion,
  })
  const activeCommands = commandRuntime.activeCommands

  const activeSearchCommand = computed(() => (
    activeCommands.value.find((command) => command?.type === 'resource.search') || null
  ))
  const activeSubscriptionRunCommand = computed(() => (
    activeCommands.value.find((command) => command?.type === 'subscription.run') || null
  ))
  const activeProfileRefreshCommand = computed(() => (
    activeCommands.value.find((command) => PROFILE_REFRESH_COMMAND_TYPES.includes(command?.type)) || null
  ))
  const profileRefreshInProgress = computed(() => (
    !!activeProfileRefreshCommand.value
  ))
  const subscriptionRunInProgress = computed(() => (
    !!activeSubscriptionRunCommand.value
  ))
  const activePilotCommands = computed(() => (
    activeCommands.value.filter((command) => command?.type === 'pilot.episode')
  ))
  const activePilotCommand = computed(() => (
    activePilotCommands.value[0] || null
  ))
  const activeDownloadCreationCommands = computed(() => (
    activeCommands.value.filter((command) => DOWNLOAD_CREATION_COMMAND_TYPES.includes(command?.type))
  ))
  const activeTaskCommands = computed(() => (
    activeCommands.value.filter((command) => (
      command?.target_type === 'task' && TASK_COMMAND_TYPES.includes(command?.type)
    ))
  ))
  const pilotInProgress = computed(() => (
    activePilotCommands.value.length > 0
  ))
  const hasSearched = computed(() => (
    !!detailOverviewSummary.value?.resource_discovery?.searched
    || (Array.isArray(tabData.search) && tabData.search.length > 0)
    || !!activeSearchCommand.value
  ))
  const taskCreatePlaceholderVisible = computed(() => {
    const currentTaskCount = Array.isArray(tabData.tasks) ? tabData.tasks.length : 0
    return taskCreatePending.value && currentTaskCount <= taskCreateBaselineCount.value
  })
  const hasRequiredSeasonContext = computed(() => !isTvMediaTarget(mediaId.value) || !!selectedSeasonNumber?.value)
  const activeLibraryFileCommands = computed(() => (
    activeCommands.value.filter((command) => (
      command?.target_type === 'library_file' && LIBRARY_FILE_COMMAND_TYPES.includes(command?.type)
    ))
  ))

  async function refreshActiveMediaCommands(seasonNumber = null) {
    if (!mediaId.value) return
    const params = { media_id: mediaId.value }
    const activeSeasonNumber = seasonNumber || selectedSeasonNumber?.value || null
    if (activeSeasonNumber) {
      params.season_number = activeSeasonNumber
    }
    params.types = MEDIA_DETAIL_COMMAND_TYPES
    await operations.refreshActiveCommands(params)
  }

  async function loadSearchResultsIntoTab(siteIds = []) {
    if (!mediaId.value) return
    const params = {
      media_id: mediaId.value,
    }
    if (selectedSeasonNumber?.value) {
      params.season_number = selectedSeasonNumber.value
    }
    if (Array.isArray(siteIds) && siteIds.length > 0) {
      params.site = siteIds.join(',')
    }
    const data = await searchResources(params)
    tabData.search = Array.isArray(data) ? data : (data?.results || [])
  }

  async function refreshSearchResults(siteIds = []) {
    await loadSearchResultsIntoTab(siteIds)
    searchResultsRefreshTrigger.value += 1
  }

  function currentTaskCount() {
    return Array.isArray(tabData.tasks) ? tabData.tasks.length : 0
  }

  function clearTaskCreatePlaceholder() {
    taskCreatePending.value = false
    pendingTaskPreview.value = null
  }

  async function waitForCreatedTaskList() {
    for (let attempt = 0; attempt < TASK_CREATE_REFRESH_RETRY_COUNT; attempt += 1) {
      await loadTaskInfo(mediaId.value, selectedSeasonNumber?.value || null)
      if (currentTaskCount() > taskCreateBaselineCount.value) return
      await new Promise(resolve => window.setTimeout(resolve, TASK_CREATE_REFRESH_RETRY_DELAY_MS))
    }
  }

  function resolveTaskCommandKey(command) {
    return command?.target_id || command?.payload?.resolved_task_id || command?.payload?.task_id || ''
  }

  function clearTaskRealtimeOverride(taskId) {
    if (!taskId) return
    const timer = taskRealtimeOverrideTimers.get(taskId)
    if (timer) {
      window.clearTimeout(timer)
      taskRealtimeOverrideTimers.delete(taskId)
    }
    if (!(taskId in taskRealtimeOverrides.value)) return
    const nextOverrides = { ...taskRealtimeOverrides.value }
    delete nextOverrides[taskId]
    taskRealtimeOverrides.value = nextOverrides
  }

  function setTaskRealtimeOverride(command) {
    const taskId = resolveTaskCommandKey(command)
    if (!taskId || !['task.pause', 'task.resume'].includes(command?.type)) return

    const nextOverrides = {
      ...taskRealtimeOverrides.value,
      [taskId]: {
        state: command.type === 'task.pause' ? 'paused' : 'downloading',
      },
    }
    taskRealtimeOverrides.value = nextOverrides

    const existingTimer = taskRealtimeOverrideTimers.get(taskId)
    if (existingTimer) {
      window.clearTimeout(existingTimer)
    }
    const timer = window.setTimeout(() => {
      clearTaskRealtimeOverride(taskId)
    }, TASK_REALTIME_OVERRIDE_TTL_MS)
    taskRealtimeOverrideTimers.set(taskId, timer)
  }

  function reconcileTaskRealtimeOverrides() {
    const entries = Object.entries(taskRealtimeOverrides.value)
    if (entries.length === 0) return

    for (const [taskId, override] of entries) {
      const task = tabData.tasks.find((item) => (
        item?.id === taskId
        || item?.task_data?.id === taskId
        || item?.torrent_hash === taskId
        || item?.hash === taskId
        || item?.info_hash === taskId
      ))
      if (!task) continue

      const realtimeState = String(
        task?.realtime?.torrent_state || task?.state || task?.status || ''
      ).toLowerCase()
      if (realtimeState === override.state) {
        clearTaskRealtimeOverride(taskId)
      }
    }
  }

  async function handleCommandCompletion(terminalCommand) {
    if (terminalCommand?.type === 'resource.search') {
        await Promise.all([
          loadSearchResultsIntoTab(terminalCommand?.payload?.site_ids || []),
          loadDetailOverview(mediaId.value, selectedSeasonNumber?.value || null),
        ])
        if (shouldAutoOpenSearchTab.value && tabData.search.length > 0) {
          activeTab.value = 'search'
        } else if (activeTab.value === 'search') {
          activeTab.value = 'resources'
        }
        shouldAutoOpenSearchTab.value = false
        searchResultsRefreshTrigger.value += 1
        return
      }

      if (DOWNLOAD_CREATION_COMMAND_TYPES.includes(terminalCommand?.type)) {
        const isPilotEpisode = terminalCommand?.type === 'pilot.episode'
        const commandLabel = t(`mediaDetail.command.${resolvePilotCommandLabel(terminalCommand)}`)
        if (terminalCommand?.status === 'succeeded') {
          await Promise.all([
            loadSearchResultsIntoTab(terminalCommand?.payload?.site_ids || []),
            loadDetailOverview(mediaId.value, selectedSeasonNumber?.value || null),
          ])
          searchResultsRefreshTrigger.value += 1
          if (activeTab.value === 'tasks') {
            await waitForCreatedTaskList()
          }
          clearTaskCreatePlaceholder()
          notification.success(isPilotEpisode ? t('mediaDetail.commandTaskCreated', { action: commandLabel }) : t('mediaDetail.downloadTaskCreated'))
          return
        }
        if (terminalCommand?.status === 'failed') {
          clearTaskCreatePlaceholder()
          notification.error(terminalCommand?.error || resolveLocalizedRecordMessage(terminalCommand, isPilotEpisode ? t('mediaDetail.commandTaskCreateFailed', { action: commandLabel }) : t('mediaDetail.downloadTaskCreateFailed')))
          return
        }
        if (terminalCommand?.status === 'cancelled') {
          clearTaskCreatePlaceholder()
          notification.warn(isPilotEpisode ? t('mediaDetail.commandTaskCancelled', { action: commandLabel }) : t('mediaDetail.downloadTaskCancelled'))
          return
        }
      }

      if (terminalCommand?.type === 'subscription.run') {
        if (terminalCommand?.status === 'succeeded') {
          await Promise.all([
            handleCheckSubscription?.({ preferOverview: true }),
            loadSearchResultsIntoTab(terminalCommand?.payload?.site_ids || []),
            loadDetailOverview(mediaId.value, selectedSeasonNumber?.value || null),
            refreshActiveMediaCommands(),
          ])
          searchResultsRefreshTrigger.value += 1
          notification.success(t('mediaDetail.subscriptionRefreshCompleted'))
          return
        }
        if (terminalCommand?.status === 'failed') {
          notification.error(terminalCommand?.error || resolveLocalizedRecordMessage(terminalCommand, t('mediaDetail.subscriptionRefreshFailed')))
          return
        }
        if (terminalCommand?.status === 'cancelled') {
          notification.warn(t('mediaDetail.subscriptionRefreshCancelled'))
          return
        }
      }

      if (terminalCommand?.type === 'profile.refresh') {
        if (terminalCommand?.status === 'succeeded') {
          await Promise.all([
            fetchDetail?.(mediaId.value, selectedSeasonNumber?.value || null),
            loadDetailOverview(mediaId.value, selectedSeasonNumber?.value || null),
            refreshActiveMediaCommands(),
          ])
          notification.success(t('mediaDetail.profileRefreshCompleted'))
          return
        }
        if (terminalCommand?.status === 'failed') {
          notification.error(terminalCommand?.error || resolveLocalizedRecordMessage(terminalCommand, t('mediaDetail.profileRefreshFailed')))
          return
        }
        if (terminalCommand?.status === 'cancelled') {
          notification.warn(t('mediaDetail.profileRefreshCancelled'))
          return
        }
      }

      if (terminalCommand?.status === 'succeeded') {
        if (terminalCommand?.type === 'library_file.delete') notification.success(t('mediaDetail.resourceDeleted'))
        if (terminalCommand?.type === 'library_file.media_server_sync') notification.success(t('mediaDetail.scrapeCompleted'))
        if (terminalCommand?.type === 'library_file.danmu_generate') notification.success(t('mediaDetail.danmuGenerateCompleted'))
        if (terminalCommand?.type === 'task.pause') notification.success(t('mediaDetail.taskPaused'))
        if (terminalCommand?.type === 'task.resume') notification.success(t('mediaDetail.taskResumed'))
        if (terminalCommand?.type === 'task.transfer') notification.success(t('mediaDetail.transferCompleted'))
        if (terminalCommand?.type === 'task.media_server_sync') notification.success(t('mediaDetail.scrapeCompleted'))
        if (terminalCommand?.type === 'task.danmu_generate') notification.success(t('mediaDetail.danmuGenerateCompleted'))
        if (terminalCommand?.type === 'task.delete') notification.success(t('mediaDetail.downloadTaskDeleted'))
      }

      if (terminalCommand?.status === 'failed') {
        notification.error(terminalCommand?.error || resolveLocalizedRecordMessage(terminalCommand, t('mediaDetail.taskExecutionFailed')))
      }

      if (terminalCommand?.status === 'cancelled') {
        notification.warn(t('mediaDetail.taskCancelled'))
      }

      if (LIBRARY_FILE_COMMAND_TYPES.includes(terminalCommand?.type) && activeTab.value === 'resources') {
        await Promise.all([
          loadResourceInfo(mediaId.value, selectedSeasonNumber?.value || null),
          loadDetailOverview(mediaId.value, selectedSeasonNumber?.value || null),
        ])
        return
      }

      if (TASK_COMMAND_TYPES.includes(terminalCommand?.type)) {
        await loadDetailOverview(mediaId.value, selectedSeasonNumber?.value || null)
        if (terminalCommand?.status === 'succeeded') {
          if (terminalCommand?.type === 'task.delete') {
            markTaskDeleted?.(resolveTaskCommandKey(terminalCommand))
          }
          setTaskRealtimeOverride(terminalCommand)
        }
        if (activeTab.value === 'tasks') {
          if (['task.pause', 'task.resume'].includes(terminalCommand?.type)) {
            return
          }
          await loadTaskInfo(mediaId.value, selectedSeasonNumber?.value || null)
          reconcileTaskRealtimeOverrides()
          return
        }
        if (activeTab.value === 'resources') {
          await loadResourceInfo(mediaId.value, selectedSeasonNumber?.value || null)
        }
    }
  }

  async function triggerSearch() {
    if (!hasRequiredSeasonContext.value) {
      notification.warn(t('mediaDetail.selectSeasonForSearch'))
      return
    }
    const canContinue = await ensureSearchReady()
    if (!canContinue) return
    shouldAutoOpenSearchTab.value = true
    tabData.search = []
    searchTrigger.value += 1
    nextTick(() => {
      activeTab.value = 'search'
    })
  }

  function resetSearchResultsForSeasonChange() {
    hasSearched.value = false
    checkingSearch.value = false
    tabData.search = []
    searchResultsRefreshTrigger.value += 1
  }

  function onSearchComplete(data) {
    if (data?.searchResults) {
      tabData.search = data.searchResults
    }
    if (shouldAutoOpenSearchTab.value && Array.isArray(tabData.search) && tabData.search.length > 0) {
      activeTab.value = 'search'
      shouldAutoOpenSearchTab.value = false
      return
    }
    if (activeTab.value === 'search') {
      activeTab.value = 'resources'
    }
    shouldAutoOpenSearchTab.value = false
  }

  function handleSearchLoading(isLoading) {
    if (activeSearchCommand.value?.status === 'queued' || activeSearchCommand.value?.status === 'running') {
      searchInProgress.value = true
      return
    }
    searchInProgress.value = !!isLoading
  }

  function handleSearchDownload(payload = null) {
    taskCreateBaselineCount.value = Array.isArray(tabData.tasks) ? tabData.tasks.length : 0
    taskCreatePending.value = true
    pendingTaskPreview.value = payload ? {
      title: payload?.resource?.resource?.title || payload?.resource?.title || payload?.mediaInfo?.title || t('taskLive.creatingDownloadTask'),
      description: payload?.resource?.resource?.description || payload?.resource?.description || '',
      site: payload?.resource?.resource?.site || payload?.resource?.site || '',
      size: Number(payload?.resource?.resource?.size || payload?.resource?.size || 0),
      attributes: payload?.resource?.attributes || {},
    } : null
    activeTab.value = 'tasks'
  }

  function handleCommandSubmitted(commandOrCommands) {
    const commands = Array.isArray(commandOrCommands) ? commandOrCommands : [commandOrCommands]
    const validCommands = commands.filter((command) => command?.id)
    if (validCommands.length === 0) return
    for (const command of validCommands) {
      if (command.type === 'resource.search') {
        searchTrigger.value = 0
      }
      if (DOWNLOAD_CREATION_COMMAND_TYPES.includes(command.type)) {
        const isPilotEpisode = command.type === 'pilot.episode'
        const commandLabel = t(`mediaDetail.command.${resolvePilotCommandLabel(command)}`)
        if (!taskCreatePending.value) {
          taskCreateBaselineCount.value = Array.isArray(tabData.tasks) ? tabData.tasks.length : 0
        }
        taskCreatePending.value = true
        if (!pendingTaskPreview.value) {
          pendingTaskPreview.value = {
            title: command.target_label || (isPilotEpisode ? t('mediaDetail.creatingCommandTask', { action: commandLabel }) : t('taskLive.creatingDownloadTask')),
            description: '',
            site: '',
            size: 0,
            attributes: {},
          }
        }
      }
      operations.registerSubmittedCommand(command)
    }
    commandRuntime.startPolling()
  }

  watch(
    () => [
      activeTab.value,
      activeSearchCommand.value?.id,
      activeSearchCommand.value?.status,
      activeSubscriptionRunCommand.value?.id,
      activeSubscriptionRunCommand.value?.status,
      activeProfileRefreshCommand.value?.id,
      activeProfileRefreshCommand.value?.status,
      activeDownloadCreationCommands.value.map((command) => `${command.id}:${command.status}`).join(','),
      activeTaskCommands.value.map((command) => `${command.id}:${command.status}`).join(','),
      activeLibraryFileCommands.value.map((command) => `${command.id}:${command.status}`).join(','),
    ],
    () => {
      const shouldPoll = activeCommands.value.length > 0
      if (shouldPoll) {
        commandRuntime.startPolling()
        return
      }
      commandRuntime.stopPolling()
    },
    { immediate: true }
  )

  watch(
    activeSearchCommand,
    (command) => {
      searchInProgress.value = command?.status === 'queued' || command?.status === 'running'
    },
    { immediate: true }
  )

  watch(
    activeDownloadCreationCommands,
    (commands) => {
      if (commands.length > 0) taskCreatePending.value = true
    },
    { immediate: true }
  )

  watch(
    () => tabData.tasks,
    () => {
      if (taskCreatePending.value && currentTaskCount() > taskCreateBaselineCount.value) {
        clearTaskCreatePlaceholder()
      }
      reconcileTaskRealtimeOverrides()
    },
    { deep: true }
  )

  onUnmounted(() => {
    commandRuntime.stopPolling()
    for (const timer of taskRealtimeOverrideTimers.values()) {
      window.clearTimeout(timer)
    }
    taskRealtimeOverrideTimers.clear()
  })

  return {
    hasSearched,
    checkingSearch,
    activeCommands,
    searchTrigger,
    searchResultsRefreshTrigger,
    searchInProgress,
    taskCreatePending,
    taskCreatePlaceholderVisible,
    pendingTaskPreview,
    taskRealtimeOverrides,
    activeSearchCommand,
    activeSubscriptionRunCommand,
    activeProfileRefreshCommand,
    subscriptionRunInProgress,
    activePilotCommands,
    activePilotCommand,
    pilotInProgress,
    profileRefreshInProgress,
    refreshActiveMediaCommands,
    refreshSearchResults,
    triggerSearch,
    resetSearchResultsForSeasonChange,
    onSearchComplete,
    handleSearchLoading,
    handleSearchDownload,
    handleCommandSubmitted,
  }
}
