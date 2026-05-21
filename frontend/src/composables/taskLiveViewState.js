function normalizeTaskStatus(value) {
  return value ? String(value).toLowerCase() : ''
}

function normalizeTorrentState(value) {
  return value ? String(value).toLowerCase() : ''
}

const ACTION_ORDER = ['view_detail', 'pause', 'resume', 'transfer', 'media_server_sync', 'danmu_generate', 'change_downloader', 'delete']

function shouldApplyRealtimeOverlay(task) {
  const status = normalizeTaskStatus(task?.status)
  return status === 'pending' || status === 'downloading' || status === 'paused'
}

function resolveOverlayPhase(task, realtimeState) {
  const status = normalizeTaskStatus(task?.status)
  if (!realtimeState) {
    return {
      phase: task?.phase || '',
      phaseGroup: task?.phase_group || '',
      phaseLabel: task?.phase_label || '',
      phaseLabelKey: task?.phase_label_key || '',
    }
  }

  if (status === 'pending') {
    if (realtimeState === 'downloading') {
      return { phase: 'downloading', phaseGroup: 'downloading', phaseLabel: '', phaseLabelKey: 'taskLive.status.downloading' }
    }
    if (realtimeState === 'paused') {
      return { phase: 'paused', phaseGroup: 'downloading', phaseLabel: '', phaseLabelKey: 'taskLive.status.paused' }
    }
  }

  if (status === 'downloading') {
    if (realtimeState === 'paused') {
      return { phase: 'paused', phaseGroup: 'downloading', phaseLabel: '', phaseLabelKey: 'taskLive.status.paused' }
    }
    return { phase: 'downloading', phaseGroup: 'downloading', phaseLabel: '', phaseLabelKey: 'taskLive.status.downloading' }
  }

  if (status === 'paused') {
    if (realtimeState === 'downloading') {
      return { phase: 'downloading', phaseGroup: 'downloading', phaseLabel: '', phaseLabelKey: 'taskLive.status.downloading' }
    }
    return { phase: 'paused', phaseGroup: 'downloading', phaseLabel: '', phaseLabelKey: 'taskLive.status.paused' }
  }

  return {
    phase: task?.phase || '',
    phaseGroup: task?.phase_group || '',
    phaseLabel: task?.phase_label || '',
    phaseLabelKey: task?.phase_label_key || '',
  }
}

function normalizeActionStates(task) {
  if (Array.isArray(task?.action_states) && task.action_states.length > 0) {
    return task.action_states.map((item) => ({ ...item }))
  }
  const actions = Array.isArray(task?.actions) ? task.actions : []
  return actions.map((action) => ({
    action,
    available: true,
    loading: false,
    disabled: false,
    disabled_reason_key: null,
    disabled_reason_params: {},
    active_command_id: null,
    active_command_type: null,
  }))
}

function applyActiveCommandToActionStates(actionStates, activeCommand) {
  const activeCommandId = activeCommand?.id || ''
  const activeCommandType = activeCommand?.type || ''
  if (!activeCommandId || !activeCommandType) return actionStates

  return actionStates.map((item) => {
    if (item.action === 'view_detail') return item
    return {
      ...item,
      loading: true,
      disabled: true,
      disabled_reason_key: item.disabled_reason_key || 'taskLive.taskProcessing',
      disabled_reason_params: item.disabled_reason_params || {},
      active_command_id: activeCommandId,
      active_command_type: activeCommandType,
    }
  })
}

function sortActionStates(actionStates) {
  return [...actionStates].sort((a, b) => (
    ACTION_ORDER.indexOf(a.action) - ACTION_ORDER.indexOf(b.action)
  ))
}

function resolveOverlayActionStates(task, realtimeState, activeCommand) {
  const activeCommandId = activeCommand?.id || task?.active_command_id || ''
  const activeCommandType = activeCommand?.type || task?.active_command_type || ''
  let actionStates = normalizeActionStates(task)
  if (activeCommandId) {
    actionStates = applyActiveCommandToActionStates(actionStates, {
      id: activeCommandId,
      type: activeCommandType,
    })
    return sortActionStates(actionStates)
  }

  if (!realtimeState) {
    return sortActionStates(actionStates)
  }

  actionStates = actionStates.filter((item) => item.action !== 'pause' && item.action !== 'resume')

  if (realtimeState === 'downloading') {
    actionStates.push({
      action: 'pause',
      available: true,
      loading: false,
      disabled: false,
      disabled_reason_key: null,
      disabled_reason_params: {},
      active_command_id: null,
      active_command_type: null,
    })
  } else if (realtimeState === 'paused') {
    actionStates.push({
      action: 'resume',
      available: true,
      loading: false,
      disabled: false,
      disabled_reason_key: null,
      disabled_reason_params: {},
      active_command_id: null,
      active_command_type: null,
    })
  }

  return sortActionStates(actionStates)
}

export function buildEnhancedTask(task, realtimeData, realtimeUnavailableTaskIds) {
  return buildEnhancedTaskWithOverride(task, realtimeData, realtimeUnavailableTaskIds, null)
}

export function buildEnhancedTaskWithOverride(task, realtimeData, realtimeUnavailableTaskIds, realtimeOverride, activeCommand = null) {
  const taskId = task?.id || task?.task_data?.id || ''
  const appliesRealtimeOverlay = shouldApplyRealtimeOverlay(task)
  const polledRealtime = taskId && appliesRealtimeOverlay ? realtimeData[taskId] : null
  const polledRealtimeState = normalizeTorrentState(polledRealtime?.state)
  const backendRealtime = task?.realtime || {}
  const overrideRealtime = realtimeOverride || {}
  const overrideRealtimeState = normalizeTorrentState(overrideRealtime.state || overrideRealtime.torrent_state)
  const effectiveRealtimeMetrics = overrideRealtimeState ? { ...polledRealtime, ...overrideRealtime } : (polledRealtime || backendRealtime)
  const effectiveRealtimeState = overrideRealtimeState
    || polledRealtimeState
    || normalizeTorrentState(backendRealtime.torrent_state)
  const overlayRealtimeState = appliesRealtimeOverlay ? effectiveRealtimeState : ''
  const phase = resolveOverlayPhase(task, overlayRealtimeState)
  const actionStates = resolveOverlayActionStates(task, overlayRealtimeState, activeCommand)
  const actions = actionStates.filter((item) => item.available !== false).map((item) => item.action)
  const hasRealtimeUnavailable = taskId ? realtimeUnavailableTaskIds[taskId] === true : false

  return {
    ...task,
    phase: phase.phase,
    phase_group: phase.phaseGroup,
    phase_label: phase.phaseLabel,
    phase_label_key: phase.phaseLabelKey,
    actions,
    action_states: actionStates,
    progress: typeof effectiveRealtimeMetrics?.progress === 'number' ? effectiveRealtimeMetrics.progress : task.progress,
    dlspeed: typeof effectiveRealtimeMetrics?.download_speed === 'number' ? effectiveRealtimeMetrics.download_speed : (task.dlspeed || 0),
    upspeed: typeof effectiveRealtimeMetrics?.upload_speed === 'number' ? effectiveRealtimeMetrics.upload_speed : (task.upspeed || 0),
    eta: typeof effectiveRealtimeMetrics?.eta === 'number' ? effectiveRealtimeMetrics.eta : (task.eta || 0),
    num_seeds: typeof effectiveRealtimeMetrics?.num_seeds === 'number' ? effectiveRealtimeMetrics.num_seeds : (task.num_seeds || 0),
    num_leechs: typeof effectiveRealtimeMetrics?.num_leechs === 'number' ? effectiveRealtimeMetrics.num_leechs : (task.num_leechs || 0),
    state: effectiveRealtimeState || task.state || '',
    realtime_unavailable: appliesRealtimeOverlay ? hasRealtimeUnavailable : !!task.realtime_unavailable,
    realtime: {
      ...backendRealtime,
      available: appliesRealtimeOverlay
        ? (hasRealtimeUnavailable ? false : (polledRealtime ? true : (backendRealtime.available ?? false)))
        : (backendRealtime.available ?? false),
      torrent_state: effectiveRealtimeState || backendRealtime.torrent_state || null,
      progress: typeof polledRealtime?.progress === 'number' ? polledRealtime.progress : (backendRealtime.progress ?? task.progress),
      download_speed: typeof polledRealtime?.download_speed === 'number' ? polledRealtime.download_speed : (backendRealtime.download_speed || 0),
      upload_speed: typeof polledRealtime?.upload_speed === 'number' ? polledRealtime.upload_speed : (backendRealtime.upload_speed || 0),
      eta: typeof polledRealtime?.eta === 'number' ? polledRealtime.eta : (backendRealtime.eta || 0),
      num_seeds: typeof polledRealtime?.num_seeds === 'number' ? polledRealtime.num_seeds : (backendRealtime.num_seeds || 0),
      num_leechs: typeof polledRealtime?.num_leechs === 'number' ? polledRealtime.num_leechs : (backendRealtime.num_leechs || 0),
    },
  }
}

export function buildEnhancedTasks(tasks, realtimeData, realtimeUnavailableTaskIds) {
  return tasks.map((task) => buildEnhancedTask(task, realtimeData, realtimeUnavailableTaskIds))
}
