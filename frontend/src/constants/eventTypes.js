export const EVENT_TYPE_MAP = {
  download: {
    completed: { subjectKey: 'events.subject.download', actionKey: 'events.action.completed', icon: 'pi pi-check-circle', tone: 'success' },
    failed: { subjectKey: 'events.subject.download', actionKey: 'events.action.failed', icon: 'pi pi-times-circle', tone: 'danger' },
    'task.downloader_change_failed': { subjectKey: 'events.subject.downloadTask', actionKey: 'events.action.downloaderChangeFailed', icon: 'pi pi-times-circle', tone: 'danger' },
    'task.storage_change_failed': { subjectKey: 'events.subject.downloadTask', actionKey: 'events.action.storageChangeFailed', icon: 'pi pi-times-circle', tone: 'danger' },
  },
  media: {
    'import.completed': { subjectKey: 'events.subject.mediaImport', actionKey: 'events.action.completed', icon: 'pi pi-inbox', tone: 'success' },
    'import.failed': { subjectKey: 'events.subject.mediaImport', actionKey: 'events.action.failed', icon: 'pi pi-times-circle', tone: 'danger' },
    deleted: { subjectKey: 'events.subject.media', actionKey: 'events.action.deleted', icon: 'pi pi-trash', tone: 'warn' },
  },
  library: {
    'file.missing': { subjectKey: 'events.subject.libraryFile', actionKey: 'events.action.missing', icon: 'pi pi-exclamation-triangle', tone: 'warn' },
  },
  indexer: {
    'site.unhealthy': { subjectKey: 'events.subject.indexerSite', actionKey: 'events.action.unhealthy', icon: 'pi pi-exclamation-triangle', tone: 'warn' },
  },
  media_server_sync: {
    completed: { subjectKey: 'events.subject.mediaServerSync', actionKey: 'events.action.completed', icon: 'pi pi-check-circle', tone: 'success' },
    failed: { subjectKey: 'events.subject.mediaServerSync', actionKey: 'events.action.failed', icon: 'pi pi-times-circle', tone: 'danger' },
  },
  danmu: {
    'generate.completed': { subjectKey: 'events.subject.danmu', actionKey: 'events.action.completed', icon: 'pi pi-check-circle', tone: 'success' },
    'generate.failed': { subjectKey: 'events.subject.danmu', actionKey: 'events.action.failed', icon: 'pi pi-times-circle', tone: 'danger' },
  },
  subscription: {
    'ended.movie_completed': { subjectKey: 'events.subject.subscription', actionKey: 'events.action.movieCompleted', icon: 'pi pi-check-circle', tone: 'success' },
    'ended.movie_downloading_completed': { subjectKey: 'events.subject.subscription', actionKey: 'events.action.movieDownloadingCompleted', icon: 'pi pi-download', tone: 'accent' },
    'ended.movie_target_completed': { subjectKey: 'events.subject.subscription', actionKey: 'events.action.movieTargetCompleted', icon: 'pi pi-check-circle', tone: 'success' },
    'ended.tv_completed': { subjectKey: 'events.subject.subscription', actionKey: 'events.action.tvCompleted', icon: 'pi pi-check-circle', tone: 'success' },
    'ended.tv_upgrade_completed': { subjectKey: 'events.subject.subscription', actionKey: 'events.action.tvUpgradeCompleted', icon: 'pi pi-check-circle', tone: 'success' },
    'ended.tv_target_completed': { subjectKey: 'events.subject.subscription', actionKey: 'events.action.tvTargetCompleted', icon: 'pi pi-check-circle', tone: 'success' },
  },
  follow: {
    released: { subjectKey: '', actionKey: 'events.action.released', icon: 'pi pi-calendar', tone: 'success' },
    digital_released: { subjectKey: '', actionKey: 'events.action.digitalReleased', icon: 'pi pi-wifi', tone: 'success' },
    physical_released: { subjectKey: '', actionKey: 'events.action.physicalReleased', icon: 'pi pi-box', tone: 'success' },
  },
  addon: {
    'run.started': { subjectKey: 'events.subject.addonRun', actionKey: 'events.action.started', icon: 'pi pi-puzzle', tone: 'accent' },
    'run.completed': { subjectKey: 'events.subject.addonRun', actionKey: 'events.action.completed', icon: 'pi pi-check-circle', tone: 'success' },
    'run.failed': { subjectKey: 'events.subject.addonRun', actionKey: 'events.action.failed', icon: 'pi pi-times-circle', tone: 'danger' },
    'run.skipped': { subjectKey: 'events.subject.addonRun', actionKey: 'events.action.skipped', icon: 'pi pi-forward', tone: 'warn' },
  },
  notification: {
    sent: { subjectKey: 'events.subject.notification', actionKey: 'events.action.sent', icon: 'pi pi-send', tone: 'success' },
    failed: { subjectKey: 'events.subject.notification', actionKey: 'events.action.failed', icon: 'pi pi-times-circle', tone: 'danger' },
  },
}

export function resolveEventTypeMeta(type) {
  if (!type) return null
  const parts = type.split('.')
  const domain = parts[0]
  const rest = parts.slice(1).join('.')
  return EVENT_TYPE_MAP[domain]?.[rest] || null
}

export function isDanmuNotFoundEvent(event) {
  if (event?.type !== 'danmu.generate.failed') return false
  const params = event?.message_params || {}
  return params.error === 'no danmu comments returned' || params.error_key === 'runtimeReasons.danmuNotFound'
}

export function isDanmuDurationMismatchEvent(event) {
  if (event?.type !== 'danmu.generate.failed') return false
  const params = event?.message_params || {}
  return params.error === 'duration mismatch' || params.error_key === 'runtimeReasons.danmuDurationMismatch'
}
