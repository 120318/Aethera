import { t } from '@/i18n'

export const TASK_STATUS = {
  PENDING: 'pending',
  DOWNLOADING: 'downloading',
  PAUSED: 'paused',
  ERROR: 'error',
  FINISHED: 'finished',
  TRANSFERRING: 'transferring',
  MIGRATING: 'migrating',
  COMPLETED: 'completed',
  PARTIAL_MISSING: 'partial_missing',
  SEEDING_ABSENT: 'seeding_absent',
  FILE_MISSING: 'file_missing',
  VOID: 'void'
}

export const TORRENT_STATE = {
  DOWNLOADING: 'downloading',
  SEEDING: 'seeding',
  PAUSED: 'paused',
  QUEUED: 'queued',
  CHECKING: 'checking',
  MISSING: 'missing',
  ERROR: 'error',
  UNKNOWN: 'unknown'
}

const STATUS_GROUP_MAP = {
  [TASK_STATUS.PENDING]: 'pending',
  [TASK_STATUS.DOWNLOADING]: 'downloading',
  [TASK_STATUS.PAUSED]: 'paused',
  [TASK_STATUS.FINISHED]: 'processing',
  [TASK_STATUS.TRANSFERRING]: 'processing',
  [TASK_STATUS.MIGRATING]: 'processing',
  [TASK_STATUS.COMPLETED]: 'completed',
  [TASK_STATUS.PARTIAL_MISSING]: 'warning',
  [TASK_STATUS.SEEDING_ABSENT]: 'warning',
  [TASK_STATUS.FILE_MISSING]: 'warning',
  [TASK_STATUS.ERROR]: 'error',
  [TASK_STATUS.VOID]: 'other'
}

const STATUS_FILTER_GROUP_MAP = {
  pending: 'pending',
  downloading: 'downloading',
  paused: 'paused',
  processing: 'processing',
  completed: 'completed',
  warning: 'abnormal',
  error: 'abnormal',
  other: 'other',
  unknown: 'other'
}

const STATUS_PRIORITY_MAP = {
  error: 0,
  warning: 1,
  processing: 2,
  downloading: 3,
  pending: 4,
  paused: 5,
  completed: 6,
  other: 7,
  unknown: 8
}

const STATUS_TEXT_MAP = {
  [TASK_STATUS.PENDING]: 'taskStatus.status.pending',
  [TASK_STATUS.DOWNLOADING]: 'taskStatus.status.downloading',
  [TASK_STATUS.PAUSED]: 'taskStatus.status.paused',
  [TASK_STATUS.ERROR]: 'taskStatus.status.error',
  [TASK_STATUS.FINISHED]: 'taskStatus.status.finished',
  [TASK_STATUS.TRANSFERRING]: 'taskStatus.status.transferring',
  [TASK_STATUS.MIGRATING]: 'taskStatus.status.migrating',
  [TASK_STATUS.COMPLETED]: 'taskStatus.status.completed',
  [TASK_STATUS.PARTIAL_MISSING]: 'taskStatus.status.partialMissing',
  [TASK_STATUS.SEEDING_ABSENT]: 'taskStatus.status.seedingAbsent',
  [TASK_STATUS.FILE_MISSING]: 'taskStatus.status.fileMissing',
  [TASK_STATUS.VOID]: 'taskStatus.status.void'
}

const WARNING_MESSAGE_MAP = {
  [TASK_STATUS.PARTIAL_MISSING]: 'taskStatus.warning.partialMissing',
  [TASK_STATUS.SEEDING_ABSENT]: 'taskStatus.warning.seedingAbsent',
  [TASK_STATUS.FILE_MISSING]: 'taskStatus.warning.fileMissing',
}

function normalizeTaskStatus(status) {
  if (!status) return ''
  return String(status).toLowerCase()
}

export function getStatusGroup(status) {
  const normalized = normalizeTaskStatus(status)
  return STATUS_GROUP_MAP[normalized] || 'other'
}

export function getStatusFilterGroup(status) {
  const group = getStatusGroup(status)
  return STATUS_FILTER_GROUP_MAP[group] || 'other'
}

export function isCompletedTask(task) {
  return getStatusGroup(task.status) === 'completed'
}

export function isErrorStatus(status) {
  return getStatusGroup(status) === 'error'
}

export function isDownloadingOrPaused(task) {
  const group = getStatusGroup(task.status)
  return group === 'downloading' || group === 'paused'
}

export function getStatusPriority(status) {
  const group = getStatusGroup(status)
  return STATUS_PRIORITY_MAP[group] ?? 99
}

export function getDownloadStatusClass(status) {
  const group = getStatusGroup(status)
  if (group === 'warning') return 'status-warning'
  if (group === 'downloading') return 'status-downloading'
  if (group === 'paused') return 'status-stopped'
  if (group === 'processing') return 'text-primary'
  if (group === 'error') return 'status-error'
  if (group === 'completed') return 'status-complete'
  return ''
}

export function getStatusText(status) {
  const normalized = normalizeTaskStatus(status)
  const labelKey = STATUS_TEXT_MAP[normalized]
  return labelKey ? t(labelKey) : status || t('taskLive.unknownStatus')
}

export function getErrorStageText(stage) {
  const s = normalizeTaskStatus(stage)
  if (!s) return t('common.none')
  if (s === 'download') return t('taskStatus.stage.download')
  if (s === 'transfer') return t('taskStatus.stage.transfer')
  if (s === 'system') return t('taskStatus.stage.system')
  return stage
}

export function isWarningStatus(status) {
  return getStatusGroup(status) === 'warning'
}

export function getWarningMessage(status) {
  const normalized = normalizeTaskStatus(status)
  const labelKey = WARNING_MESSAGE_MAP[normalized]
  return labelKey ? t(labelKey) : ''
}

export function getTorrentState(task) {
  const state = task.realtime?.state
  return normalizeTaskStatus(state)
}

export function getTaskStatus(task) {
  const status = task.task_data?.status || task.status
  return normalizeTaskStatus(status)
}

export function canPause(task) {
  return getTorrentState(task) === TORRENT_STATE.DOWNLOADING
}

export function canResume(task) {
  return getTorrentState(task) === TORRENT_STATE.PAUSED
}

export function canManualTransfer(task) {
  const status = getTaskStatus(task)
  if ([
    TASK_STATUS.FINISHED,
    TASK_STATUS.COMPLETED,
    TASK_STATUS.PARTIAL_MISSING,
    TASK_STATUS.FILE_MISSING,
  ].includes(status)) return true
  if (status === TASK_STATUS.ERROR) {
    const stage = normalizeTaskStatus(task.task_data?.error_stage || task.error_stage)
    const progressSource = typeof task.progress === 'number' ? task.progress : (task.task_data?.progress || 0)
    return (stage === 'transfer' || !stage) && progressSource >= 0.999
  }
  return false
}

export function getTaskHash(task) {
  return task.task_data?.torrent_hash || task.info_hash || task.hash
}

export function hasSignificantStateChange(prev, curr) {
  const prevState = normalizeTaskStatus(prev.state)
  const currState = normalizeTaskStatus(curr.state)
  const prevProgress = typeof prev.progress === 'number' ? prev.progress : 0
  const currProgress = typeof curr.progress === 'number' ? curr.progress : 0

  const finishedStates = new Set([TORRENT_STATE.SEEDING, TORRENT_STATE.PAUSED, TORRENT_STATE.CHECKING, TORRENT_STATE.QUEUED])
  if (!finishedStates.has(prevState) && finishedStates.has(currState) && prevProgress < 0.999 && currProgress >= 0.999) {
    return true
  }

  const errorStates = new Set([TORRENT_STATE.ERROR, TORRENT_STATE.MISSING])
  if (!errorStates.has(prevState) && errorStates.has(currState)) {
    return true
  }
  return false
}

export function isActiveTask(task) {
  const group = getStatusGroup(task.status)
  return group === 'pending' || group === 'downloading' || group === 'paused' || group === 'processing'
}
