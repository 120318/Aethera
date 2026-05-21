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

export function buildNextDownloadConfig(currentDownload, download) {
  return {
    ...(currentDownload || {}),
    default_tag: String(download.default_tag ?? '').trim(),
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
