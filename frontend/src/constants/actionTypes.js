import { t } from '@/i18n'

export const ACTION_KIND_LABELS = {
  command: 'actions.kind.command',
  scheduler: 'actions.kind.scheduler',
  addon: 'actions.kind.addon',
}

export const ACTION_STATUS_META = {
  queued: { labelKey: 'operationCenter.status.queued', icon: 'pi pi-clock', tone: 'accent' },
  running: { labelKey: 'actions.status.running', icon: 'pi pi-sync', tone: 'accent' },
  completed: { labelKey: 'operationCenter.status.succeeded', icon: 'pi pi-check-circle', tone: 'success' },
  failed: { labelKey: 'operationCenter.status.failed', icon: 'pi pi-times-circle', tone: 'danger' },
  cancelled: { labelKey: 'operationCenter.status.cancelled', icon: 'pi pi-ban', tone: 'warn' },
  skipped: { labelKey: 'actions.status.skipped', icon: 'pi pi-forward', tone: 'warn' },
}

export const ACTION_NAME_LABELS = {
  'resource.search': 'operationCenter.types.resourceSearch',
  'subscription.run': 'operationCenter.types.subscriptionRun',
  'task.create': 'operationCenter.types.taskCreate',
  'pilot.episode': 'operationCenter.types.pilotEpisode',
  'task.pause': 'operationCenter.types.taskPause',
  'task.resume': 'operationCenter.types.taskResume',
  'task.transfer': 'operationCenter.types.taskTransfer',
  'task.storage_change': 'operationCenter.types.taskStorageChange',
  'task.media_server_sync': 'operationCenter.types.taskMediaServerSync',
  'task.danmu_generate': 'operationCenter.types.taskDanmuGenerate',
  'profile.refresh': 'operationCenter.types.profileRefresh',
  'directory.integrity_scan': 'operationCenter.types.directoryIntegrityScan',
  'directory.integrity_repair': 'operationCenter.types.directoryIntegrityRepair',
  'library_file.delete': 'operationCenter.types.libraryFileDelete',
  'library_file.storage_change': 'operationCenter.types.libraryFileStorageChange',
  'library_file.media_server_sync': 'operationCenter.types.libraryFileMediaServerSync',
  'library_file.danmu_generate': 'operationCenter.types.libraryFileDanmuGenerate',
  'task.delete': 'operationCenter.types.taskDelete',
  'danmu.generate': 'operationCenter.types.danmuGenerate',
  'addon.run': 'actions.names.addonRun',
  'notification.send': 'actions.names.notificationSend',
  sync_active_downloads: 'scheduler.jobs.syncActiveDownloads',
  process_completed_tasks: 'scheduler.jobs.processCompletedTasks',
  subscription_sweep: 'scheduler.jobs.subscriptionSweep',
  follow_reminder_sweep: 'scheduler.jobs.followReminderSweep',
  schedule_refresh_sweep: 'scheduler.jobs.scheduleRefreshSweep',
  cleanup_inactive_managed_media_profiles: 'scheduler.jobs.cleanupInactiveManagedMediaProfiles',
  directory_integrity_audit: 'scheduler.jobs.directoryIntegrityAudit',
  media_server_sync_incremental_sweep: 'scheduler.jobs.mediaServerSyncIncrementalSweep',
  cleanup_expired_sessions: 'scheduler.jobs.cleanupExpiredSessions',
  'media_server_sync.metadata_incremental_sync': 'scheduler.jobs.mediaServerSyncMetadataIncrementalSync',
  'danmu.backfill': 'scheduler.jobs.danmuBackfill',
}

export function resolveActionKindLabel(kind) {
  return ACTION_KIND_LABELS[kind] ? t(ACTION_KIND_LABELS[kind]) : (kind || t('actions.kind.trace'))
}

export function resolveActionStatusMeta(status) {
  const meta = ACTION_STATUS_META[status]
  return meta ? { ...meta, label: t(meta.labelKey) } : null
}

export function resolveActionNameLabel(actionName) {
  return ACTION_NAME_LABELS[actionName] ? t(ACTION_NAME_LABELS[actionName]) : (actionName || t('actions.names.unnamed'))
}

export function resolvePilotEpisodeActionLabel(mediaId) {
  return String(mediaId || '').includes(':movie:') ? t('actions.download') : t('operationCenter.types.pilotEpisode')
}
