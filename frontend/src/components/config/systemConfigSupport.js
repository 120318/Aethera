import InputNumber from 'primevue/inputnumber'
import Select from 'primevue/select'

export function buildLoggingFieldDefinitions(t) {
  return [
  {
    key: 'logging-level',
    label: t('settings.system.loggingFields.level'),
    prop: 'level',
    component: Select,
    props: {
      options: [
        { label: t('backendLogs.levels.error'), value: 'ERROR' },
        { label: t('backendLogs.levels.warning'), value: 'WARNING' },
        { label: t('backendLogs.levels.info'), value: 'INFO' },
        { label: t('backendLogs.levels.debug'), value: 'DEBUG' },
        { label: t('backendLogs.levels.trace'), value: 'TRACE' },
      ],
      optionLabel: 'label',
      optionValue: 'value',
    },
    hint: t('settings.system.loggingFields.levelHint'),
  },
  {
    key: 'logging-server-retention-days',
    label: t('settings.system.loggingFields.retentionDays'),
    prop: 'server_retention_days',
    component: InputNumber,
    props: {
      min: 1,
    },
    hint: t('settings.system.loggingFields.retentionDaysHint'),
  },
  ]
}

export function syncAuthState(auth, value) {
  const next = value || {}
  auth.session_ttl_seconds = next.session_ttl_seconds === 0 ? 0 : (next.session_ttl_seconds ?? 86400)
}

export function syncLoggingState(logging, value) {
  const next = value || {}
  logging.level = next.level ?? 'INFO'
  logging.server_retention_days = next.server_retention_days ?? 7
}

export function syncDownloadState(download, value) {
  const next = value || {}
  download.default_tag = next.default_tag ?? 'Aethera'
}

export function syncSchedulerState(scheduler, value) {
  const next = value || {}
  scheduler.subscription_sweep_interval_seconds = Number(next.subscription_sweep_interval_seconds ?? 300)
  scheduler.subscription_resource_discovery_mode = next.subscription_resource_discovery_mode || 'rss_with_search_backfill'
  scheduler.subscription_search_interval_seconds = Number(next.subscription_search_interval_seconds ?? 600)
  scheduler.subscription_search_backfill_interval_seconds = Number(next.subscription_search_backfill_interval_seconds ?? 3600)
}

export function syncGeneralState(general, value) {
  const next = value || {}
  general.locale = next.locale || 'zh-CN'
  general.public_base_url = next.public_base_url || ''
}

export function buildNextGeneralSystemConfig(config, general, download) {
  return {
    ...(config || {}),
    locale: general.locale || 'zh-CN',
    public_base_url: String(general.public_base_url || '').trim().replace(/\/+$/, ''),
    download: {
      ...(config?.download || {}),
      default_tag: String(download.default_tag ?? '').trim(),
    },
  }
}

export function buildNextSchedulerConfig(config, scheduler) {
  const sweepInterval = Number(scheduler.subscription_sweep_interval_seconds ?? 300)
  const searchInterval = Number(scheduler.subscription_search_interval_seconds ?? 600)
  const backfillInterval = Number(scheduler.subscription_search_backfill_interval_seconds ?? 3600)
  return {
    ...(config || {}),
    subscription_sweep_interval_seconds: Math.max(60, sweepInterval || 300),
    subscription_resource_discovery_mode: scheduler.subscription_resource_discovery_mode || 'rss_with_search_backfill',
    subscription_search_interval_seconds: Math.max(60, searchInterval || 600),
    subscription_search_backfill_interval_seconds: Math.max(60, backfillInterval || 3600),
  }
}

export function buildNextSystemLoggingConfig(config, logging) {
  return {
    ...(config || {}),
    logging: {
      ...(config?.logging || {}),
      level: String(logging.level ?? 'INFO').toUpperCase(),
      server_retention_days: Number(logging.server_retention_days ?? 7),
    },
  }
}

export function buildNextAuthConfig(currentAuth, auth) {
  return {
    ...(currentAuth || {}),
    ...auth,
    enabled: true,
  }
}
