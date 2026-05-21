import { i18n, t } from '@/i18n'
import { formatDurationMs } from '@/utils/formatters'

export const schedulerJobNameLabels = {
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

export const schedulerJobDescriptions = {
  sync_active_downloads: 'scheduler.descriptions.syncActiveDownloads',
  process_completed_tasks: 'scheduler.descriptions.processCompletedTasks',
  subscription_sweep: 'scheduler.descriptions.subscriptionSweep',
  follow_reminder_sweep: 'scheduler.descriptions.followReminderSweep',
  schedule_refresh_sweep: 'scheduler.descriptions.scheduleRefreshSweep',
  cleanup_inactive_managed_media_profiles: 'scheduler.descriptions.cleanupInactiveManagedMediaProfiles',
  directory_integrity_audit: 'scheduler.descriptions.directoryIntegrityAudit',
  media_server_sync_incremental_sweep: 'scheduler.descriptions.mediaServerSyncIncrementalSweep',
  cleanup_expired_sessions: 'scheduler.descriptions.cleanupExpiredSessions',
  'media_server_sync.metadata_incremental_sync': 'scheduler.descriptions.mediaServerSyncMetadataIncrementalSync',
  'danmu.backfill': 'scheduler.descriptions.danmuBackfill',
}

export function formatSchedulerJobName(job) {
  return schedulerJobNameLabels[job.id] ? t(schedulerJobNameLabels[job.id]) : (job.name || job.id)
}

export function formatSchedulerJobDescription(job) {
  if (schedulerJobDescriptions[job.id]) return t(schedulerJobDescriptions[job.id])
  if (job.source_type === 'addon') {
    return t('scheduler.addonDescription', { name: job.source_name || t('scheduler.unknownAddon') })
  }
  return t('scheduler.defaultDescription')
}

export function formatSchedulerSourceLabel(job) {
  if (job.source_type === 'addon') return t('scheduler.addonSource', { name: job.source_name })
  if (job.source_type === 'system') return t('scheduler.systemBuiltin')
  return job.source_name || t('common.unknown')
}

export function formatSchedulerInterval(seconds) {
  if (!seconds) return t('scheduler.seconds', { count: 0 })
  if (seconds % 3600 === 0) return t('scheduler.hours', { count: seconds / 3600 })
  if (seconds % 60 === 0) return t('scheduler.minutes', { count: seconds / 60 })
  return t('scheduler.seconds', { count: seconds })
}

export function formatSchedulerTriggerValue(job) {
  if (job.trigger_type === 'interval') {
    return formatSchedulerInterval(job.interval_seconds || 0)
  }
  const cron = job.cron || {}
  const parts = Object.entries(cron)
    .filter(([, value]) => value)
    .map(([key, value]) => `${key}: ${value}`)
  return parts.join(' / ') || t('scheduler.cronExpression')
}

export function formatSchedulerTriggerLabel(job) {
  if (job.trigger_type === 'interval') {
    return t('scheduler.intervalTrigger', { interval: formatSchedulerInterval(job.interval_seconds || 0) })
  }
  return t('scheduler.ruleTrigger', { rule: formatSchedulerTriggerValue(job) })
}

export function formatSchedulerDateTime(value) {
  if (!value) return '-'
  const date = new Date(value)
  if (Number.isNaN(date.getTime())) return '-'
  return date.toLocaleString(i18n.global.locale.value, {
    year: 'numeric',
    month: '2-digit',
    day: '2-digit',
    hour: '2-digit',
    minute: '2-digit',
    second: '2-digit',
  })
}

export function formatSchedulerDuration(value) {
  return formatDurationMs(value, t('scheduler.durationNotRecorded'))
}

export function formatSchedulerConfigSource(job) {
  if (job.config_scope === 'addon') {
    return t('scheduler.addonConfigSource', { name: job.source_name })
  }
  if (job.id === 'media_server_sync_incremental_sweep') {
    return t('scheduler.mediaServerSyncConfigSource')
  }
  return t('scheduler.systemConfigSource', { target: job.config_target })
}
