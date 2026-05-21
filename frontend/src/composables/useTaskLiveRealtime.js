import { computed, onUnmounted, ref, watch } from 'vue'
import { getTorrentProgress, syncFinishedTask } from '@/api/resource'
import { t } from '@/i18n'
import { getStatusGroup, hasSignificantStateChange } from '@/utils/taskStatus'

const ACTIVE_TASK_COMMAND_TYPES = ['task.pause', 'task.resume', 'task.transfer', 'task.media_server_sync', 'task.danmu_generate', 'task.storage_change', 'task.delete']

export function useTaskLiveRealtime(options = {}) {
  const {
    tasks,
    activeTab,
    operationCommands,
    emit,
    operations,
  } = options

  const realtimeData = ref({})
  const realtimeUnavailableTaskIds = ref({})
  const trackedCommandIds = ref([])
  const taskTargetIdMap = ref({})
  const resolvingTrackedCommandIds = new Set()
  const handledCommandIds = new Set()
  const syncingFinishedTaskIds = new Set()

  const usesScopedCommands = computed(() => Array.isArray(operationCommands.value))
  const scopedTaskCommands = computed(() => {
    if (!Array.isArray(operationCommands.value)) return []
    return operationCommands.value.filter((command) => (
      command?.target_type === 'task' && ACTIVE_TASK_COMMAND_TYPES.includes(command?.type)
    ))
  })
  const activeTaskCommandSource = computed(() => (
    usesScopedCommands.value ? scopedTaskCommands.value : operations.activeCommands
  ))
  const pollingTaskIds = computed(() => (
    tasks.value
      .filter((task) => {
        const group = getStatusGroup(task.status)
        return !!task?.id && (group === 'pending' || group === 'downloading' || group === 'paused')
      })
      .map((task) => task.id)
      .filter(Boolean)
  ))
  const pollingKey = computed(() => (
    activeTab.value === 'tasks' && (pollingTaskIds.value.length > 0 || hasPendingTaskCommands.value)
      ? `tasks:${pollingTaskIds.value.join(',')}:commands:${hasPendingTaskCommands.value ? '1' : '0'}`
      : ''
  ))

  function resolveTaskLookupKey(task) {
    return task?.id || task?.task_data?.id || task?.torrent_hash || task?.hash || task?.info_hash || ''
  }

  function resolveTaskTargetId(task) {
    const directId = task?.id || task?.task_data?.id
    if (directId) return directId
    const lookupKey = resolveTaskLookupKey(task)
    return taskTargetIdMap.value[lookupKey] || ''
  }

  function getTaskCommand(task, commandTypes = []) {
    const targetId = resolveTaskTargetId(task)
    if (targetId) {
      const directMatch = activeTaskCommandSource.value.find((command) => (
        command?.target_type === 'task'
        && command?.target_id === targetId
        && (commandTypes.length === 0 || commandTypes.includes(command.type))
      )) || null
      if (directMatch) return directMatch
    }

    const lookupCandidates = [
      task?.torrent_hash,
      task?.hash,
      task?.info_hash,
      task?.task_data?.id,
    ].filter(Boolean)

    for (const command of activeTaskCommandSource.value) {
      if (command?.target_type !== 'task') continue
      if (commandTypes.length > 0 && !commandTypes.includes(command.type)) continue
      if (lookupCandidates.includes(command?.payload?.task_id)) return command
    }

    return null
  }

  function isCommandForTask(command, task) {
    if (!command || command?.target_type !== 'task') return false

    const directId = task?.id || task?.task_data?.id
    if (directId && command.target_id === directId) return true

    const lookupCandidates = [
      task?.torrent_hash,
      task?.hash,
      task?.info_hash,
      task?.task_data?.id,
    ].filter(Boolean)

    return lookupCandidates.includes(command?.payload?.task_id)
  }

  function trackCommand(task, command) {
    if (!command?.id) return
    const lookupKey = resolveTaskLookupKey(task)
    if (lookupKey && command.target_id) {
      taskTargetIdMap.value = {
        ...taskTargetIdMap.value,
        [lookupKey]: command.target_id,
      }
    }
    trackedCommandIds.value = [...new Set([...trackedCommandIds.value, command.id])]
  }

  const hasPendingTaskCommands = computed(() => {
    if (trackedCommandIds.value.length > 0) {
      const trackedActive = trackedCommandIds.value.some((commandId) => {
        const command = operations.getCommandById(commandId)
        return command && (command.status === 'queued' || command.status === 'running')
      })
      if (trackedActive) return true
    }

    return tasks.value.some((task) => !!getTaskCommand(task))
  })

  async function syncFinishedTaskIfNeeded(task, realtime) {
    const taskId = task?.id
    if (!taskId || !realtime || syncingFinishedTaskIds.has(taskId)) return

    const status = String(task?.status || '').toLowerCase()
    const progress = typeof realtime?.progress === 'number' ? realtime.progress : 0
    if (!['pending', 'downloading', 'paused'].includes(status) || progress < 0.999) return
    if (String(task?.phase || '').toLowerCase() === 'ready_to_import') return
    if (getTaskCommand(task)) return

    syncingFinishedTaskIds.add(taskId)
    try {
      const response = await syncFinishedTask(taskId)
      if (response?.task) {
        emit('task-view-updated', response.task)
      }
    } catch (error) {
      console.warn(t('taskLive.finishedTaskSyncFailed'), error)
    } finally {
      syncingFinishedTaskIds.delete(taskId)
    }
  }

  async function fetchRealtimeData() {
    if (activeTab.value !== 'tasks') return

    const taskIds = pollingTaskIds.value
    if (taskIds.length === 0) {
      realtimeUnavailableTaskIds.value = {}
      return
    }

    try {
      const previousRealtime = { ...realtimeData.value }
      const response = await getTorrentProgress(taskIds)

      if (response?.torrents) {
        const isFirstLoad = Object.keys(realtimeData.value).length === 0
        const retainedRealtime = {}
        for (const taskId of taskIds) {
          if (taskId in realtimeData.value) {
            retainedRealtime[taskId] = realtimeData.value[taskId]
          }
        }
        const merged = { ...retainedRealtime, ...response.torrents }
        realtimeData.value = merged
        const nextUnavailable = { ...realtimeUnavailableTaskIds.value }
        for (const taskId of taskIds) {
          if (response.torrents[taskId]) {
            delete nextUnavailable[taskId]
          } else {
            nextUnavailable[taskId] = true
          }
        }
        for (const existingTaskId of Object.keys(nextUnavailable)) {
          if (!taskIds.includes(existingTaskId)) {
            delete nextUnavailable[existingTaskId]
          }
        }
        realtimeUnavailableTaskIds.value = nextUnavailable

        for (const task of tasks.value) {
          const taskId = task?.id
          if (!taskId) continue
          await syncFinishedTaskIfNeeded(task, merged[taskId])
        }

        if (isFirstLoad) {
          return
        }

        let shouldNotify = false
        for (const taskId of Object.keys(response.torrents)) {
          const prevRealtime = previousRealtime[taskId] || {}
          const nextRealtime = merged[taskId] || {}
          if (hasSignificantStateChange(prevRealtime, nextRealtime)) {
            shouldNotify = true
            break
          }
        }
        if (shouldNotify) emit('task-updated')
      }
    } catch (error) {
      realtimeUnavailableTaskIds.value = taskIds.reduce((acc, taskId) => {
        acc[taskId] = true
        return acc
      }, { ...realtimeUnavailableTaskIds.value })
      console.warn(t('taskLive.realtimeFetchFailed'), error)
    }
  }

  async function refreshTaskCommands() {
    if (usesScopedCommands.value) {
      syncTrackedCommands()
      return
    }
    await operations.refreshActiveCommands({
      target_type: 'task',
      types: ACTIVE_TASK_COMMAND_TYPES,
    })
    syncTrackedCommands()
  }

  function syncTrackedCommands() {
    for (const command of activeTaskCommandSource.value) {
      const matchedTask = tasks.value.find((task) => isCommandForTask(command, task))
      if (matchedTask) {
        trackCommand(matchedTask, command)
      }
    }
  }

  async function resolveTrackedCommands() {
    if (usesScopedCommands.value) return
    for (const commandId of trackedCommandIds.value) {
      if (handledCommandIds.has(commandId)) continue

      let command = operations.getCommandById(commandId)
      if (command && (command.status === 'queued' || command.status === 'running')) {
        continue
      }

      if (!command) {
        if (resolvingTrackedCommandIds.has(commandId)) continue
        resolvingTrackedCommandIds.add(commandId)
        command = await operations.fetchCommandById(commandId)
        resolvingTrackedCommandIds.delete(commandId)
      }
      if (!command) continue

      if (command.status === 'succeeded') {
        handledCommandIds.add(commandId)
        emit('task-updated')
        continue
      }

      if (command.status === 'failed' || command.status === 'cancelled') {
        handledCommandIds.add(commandId)
      }
    }
  }

  let pollTimer = null
  let pollInFlight = false

  async function runPollTick() {
    if (pollInFlight) return
    pollInFlight = true
    try {
      await fetchRealtimeData()
      if (hasPendingTaskCommands.value) {
        await refreshTaskCommands()
        await resolveTrackedCommands()
      }
    } finally {
      pollInFlight = false
    }
  }

  function startPolling() {
    if (pollTimer) return
    runPollTick()
    pollTimer = setInterval(runPollTick, 3000)
  }

  function stopPolling() {
    if (!pollTimer) return
    clearInterval(pollTimer)
    pollTimer = null
  }

  watch(() => tasks.value, (nextTasks) => {
    const nextTaskIds = new Set(
      nextTasks
        .filter((task) => {
          const group = getStatusGroup(task.status)
          return group === 'pending' || group === 'downloading' || group === 'paused'
        })
        .map((task) => task?.id)
        .filter(Boolean)
    )
    realtimeData.value = Object.fromEntries(
      Object.entries(realtimeData.value).filter(([taskId]) => nextTaskIds.has(taskId))
    )
    realtimeUnavailableTaskIds.value = Object.fromEntries(
      Object.entries(realtimeUnavailableTaskIds.value).filter(([taskId]) => nextTaskIds.has(taskId))
    )
  }, { deep: true })

  watch(pollingKey, async (nextKey, prevKey) => {
    if (activeTab.value === 'tasks') {
      await refreshTaskCommands()
    }

    if (nextKey) {
      if (nextKey !== prevKey) {
        stopPolling()
      }
      startPolling()
      return
    }
    stopPolling()
  }, { immediate: true })

  watch(
    () => operationCommands.value,
    () => {
      if (!usesScopedCommands.value) return
      syncTrackedCommands()
    },
    { deep: true }
  )

  watch(
    () => operations.allCommands,
    (commands) => {
      if (usesScopedCommands.value) return
      for (const commandId of trackedCommandIds.value) {
        if (handledCommandIds.has(commandId)) continue
        const command = commands.find((item) => item.id === commandId)
        if (!command) continue
        if (command.status === 'succeeded') {
          handledCommandIds.add(commandId)
          emit('task-updated')
        }
        if (command.status === 'failed' || command.status === 'cancelled') {
          handledCommandIds.add(commandId)
        }
      }
    },
    { deep: true }
  )

  onUnmounted(() => {
    stopPolling()
  })

  return {
    realtimeData,
    realtimeUnavailableTaskIds,
    getTaskCommand,
    trackCommand,
    fetchRealtimeData,
  }
}
