import { formatSizeBytes } from '@/utils/formatters'
import { useI18n } from 'vue-i18n'

function isTaskCreatePlaceholder(task) {
  return !!task?._taskCreatePlaceholder
}

function resolveTaskPhaseLabel(task, t) {
  if (task?.phase_label_key) return t(task.phase_label_key, task.phase_label_params || {})
  return task?.phase_label || t('taskLive.unknownStatus')
}

export function useTaskLivePresentation(options = {}) {
  const { t } = useI18n()
  const {
    showTaskDetail,
    confirmDelete,
    handlePause,
    handleResume,
    handleManualTransfer,
    handleMediaServerSync,
    handleDanmuGenerate,
    handleChangeDownloader,
    isTaskPending,
  } = options

  const TASK_ACTIONS_CONFIG = [
    { id: 'detail', icon: 'pi pi-info-circle', tooltip: t('taskLive.actions.detail'), handler: (event, task) => showTaskDetail(task) },
    { id: 'pause', icon: 'pi pi-pause', severity: 'warn', tooltip: t('taskLive.actions.pause'), commandTypes: ['task.pause'], handler: (event, task) => handlePause(task) },
    { id: 'resume', icon: 'pi pi-play', severity: 'primary', tooltip: t('taskLive.actions.resume'), commandTypes: ['task.resume'], handler: (event, task) => handleResume(task) },
    { id: 'transfer', icon: 'pi pi-sync', severity: 'success', tooltip: t('taskLive.actions.transfer'), commandTypes: ['task.transfer'], handler: (event, task) => handleManualTransfer(task) },
    { id: 'media_server_sync', icon: 'pi pi-database', severity: 'secondary', label: t('taskLive.actions.mediaServerSync'), tooltip: t('taskLive.actions.mediaServerSync'), commandTypes: ['task.media_server_sync'], menuOnly: true, handler: (event, task) => handleMediaServerSync(task) },
    { id: 'danmu_generate', icon: 'pi pi-comments', severity: 'secondary', label: t('taskLive.actions.danmuGenerate'), tooltip: t('taskLive.actions.danmuGenerate'), commandTypes: ['task.danmu_generate'], menuOnly: true, handler: (event, task) => handleDanmuGenerate(task) },
    { id: 'change_downloader', icon: 'pi pi-arrow-right-arrow-left', severity: 'secondary', label: t('taskLive.actions.changeDownloader'), tooltip: t('taskLive.actions.changeDownloader'), commandTypes: ['task.storage_change'], menuOnly: true, handler: (event, task) => handleChangeDownloader(task) },
    { id: 'delete', icon: 'pi pi-trash', severity: 'danger', tooltip: t('taskLive.actions.delete'), commandTypes: ['task.delete'], handler: (event, task) => confirmDelete(task) },
  ]

  function resolveActionState(action, task) {
    const actionId = action.id === 'detail' ? 'view_detail' : action.id
    const states = Array.isArray(task?.action_states) ? task.action_states : []
    return states.find((item) => item?.action === actionId) || null
  }

  function getStatusButtonSeverity(task) {
    const group = task?.phase_group || task?.phase || ''
    if (group === 'failed') return 'danger'
    if (group === 'attention') return 'warn'
    if (group === 'downloading' || group === 'importing' || group === 'migrating') return 'primary'
    if (group === 'completed') return 'success'
    return 'secondary'
  }

  function getTaskStatusTooltip(task) {
    if (isTaskCreatePlaceholder(task)) {
      return t('taskLive.creatingDownloadTask')
    }
    const parts = [resolveTaskPhaseLabel(task, t), formatSizeBytes(task.size || 0)]
    if (task.attention_reason_key) parts.push(t(task.attention_reason_key, task.attention_reason_params || {}))
    if (task.error_key) parts.push(t(task.error_key, task.error_params || {}))
    if (task.realtime_unavailable) parts.push(t('taskLive.realtimeUnavailable'))
    if (task.phase_group === 'downloading') {
      parts.push(`${Number((task.progress || 0) * 100).toFixed(1)}%`)
    }
    return parts.filter(Boolean).join(' · ')
  }

  function getTaskStatusLabel(task) {
    if (isTaskCreatePlaceholder(task)) {
      return t('taskLive.waitingDownload')
    }
    return resolveTaskPhaseLabel(task, t)
  }

  function shouldShowStatusInfo(task) {
    return !isTaskCreatePlaceholder(task) && (
      !!task.attention_reason_key || !!task.error_key || !!task.realtime_unavailable
    )
  }

  function isActionVisible(action, task) {
    if (action.id === 'detail') return true
    const state = resolveActionState(action, task)
    if (state) return state.available !== false
    const actions = Array.isArray(task.actions) ? task.actions : []
    return actions.includes(action.id)
  }

  function isActionLoading(action, task) {
    if (isTaskPending?.(task)) return action.id !== 'detail'
    const state = resolveActionState(action, task)
    return !!state && isActionVisible(action, task) && state.loading === true
  }

  function isActionDisabled(action, task) {
    if (action.id === 'detail') return false
    if (isTaskPending?.(task)) return true
    if (task?.status === 'migrating' || task?.phase_group === 'migrating' || task?.phase === 'migrating') return true
    const state = resolveActionState(action, task)
    return !!state && state.disabled === true
  }

  return {
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
