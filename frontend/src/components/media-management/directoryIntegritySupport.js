import { formatAbsoluteDateTime, formatRelativeTime } from '@/utils/formatters'

export const DIRECTORY_REPAIR_COMMAND_TYPES = ['directory.integrity_repair']
export const DIRECTORY_SCAN_COMMAND_TYPES = ['directory.integrity_scan']
export const DIRECTORY_SCAN_TARGET_ID = 'directory_integrity'

export const ALL_DIRECTORY_INTEGRITY_ISSUE_TYPES = [
  'unmanaged_library_file',
  'missing_library_file',
  'task_missing_library_file',
  'library_file_missing_task',
  'unmanaged_download_entry',
  'missing_download_file',
  'missing_downloader_torrent',
  'unhealthy_downloader_torrent',
]

const ISSUE_COUNT_FIELDS = {
  unmanaged_library_file: 'unmanaged_library_files',
  missing_library_file: 'missing_library_files',
  task_missing_library_file: 'tasks_missing_library_files',
  library_file_missing_task: 'library_files_missing_tasks',
  unmanaged_download_entry: 'unmanaged_download_entries',
  missing_download_file: 'missing_download_files',
  missing_downloader_torrent: 'missing_downloader_torrents',
  unhealthy_downloader_torrent: 'unhealthy_downloader_torrents',
}

export function buildDirectoryIntegritySummaryCards(summary = {}, t, formatSizeBytes) {
  const total = Number(summary.total || 0)
  const repairable = Number(summary.repairable || 0)
  return [
    {
      key: 'physical_size',
      label: t('mediaManagement.directoryIntegrity.physicalSize'),
      value: formatSizeBytes(summary.physical_size || 0) || '0 B',
      valueClass: 'text-muted',
    },
    {
      key: 'logical_size',
      label: t('mediaManagement.directoryIntegrity.logicalSize'),
      value: formatSizeBytes(summary.logical_size || 0) || '0 B',
      valueClass: 'text-muted',
    },
    {
      key: 'total',
      label: t('mediaManagement.directoryIntegrity.total'),
      value: total,
      valueClass: total > 0 ? 'text-status-warning' : 'text-muted',
    },
    {
      key: 'repairable',
      label: t('mediaManagement.directoryIntegrity.repairable'),
      value: repairable,
      valueClass: repairable > 0 ? 'text-status-error' : 'text-muted',
    },
  ]
}

export function buildDirectoryIntegrityIssueCountTags(summary = {}, formatIntegrityIssueType) {
  return ALL_DIRECTORY_INTEGRITY_ISSUE_TYPES
    .map(issueType => ({
      issueType,
      count: Number(summary[ISSUE_COUNT_FIELDS[issueType]] || 0),
    }))
    .filter(item => item.count > 0)
    .map(item => ({
      issueType: item.issueType,
      label: `${formatIntegrityIssueType(item.issueType)} ${item.count}`,
    }))
}

export function buildDirectoryIntegrityCountSummary(items = []) {
  const summary = {
    total: items.length,
    repairable: items.filter(item => item.repairable).length,
  }
  for (const issueType of ALL_DIRECTORY_INTEGRITY_ISSUE_TYPES) {
    summary[ISSUE_COUNT_FIELDS[issueType]] = items.filter(item => item.issue_type === issueType).length
  }
  return summary
}

export function resolveDefaultDirectoryFilter(directorySummaries = []) {
  return directorySummaries[0]?.directory_id || ''
}

export function buildDirectoryOptionSummaries(directorySummaries = [], items = [], policyRows = []) {
  if (policyRows.length > 0) {
    const summaries = new Map(directorySummaries.map(directory => [directory.directory_id, directory]))
    return policyRows
      .filter(policy => policy.directory_enabled !== false)
      .map(policy => ({
        ...(summaries.get(policy.directory_id) || {}),
        directory_id: policy.directory_id,
        directory_name: policy.directory_name || policy.directory_id,
        media_type: policy.media_type || summaries.get(policy.directory_id)?.media_type || '',
      }))
  }
  if (directorySummaries.length > 0) return directorySummaries
  const summaries = []
  const seen = new Set()
  for (const item of items) {
    const directoryId = item.directory_id || ''
    if (!directoryId || seen.has(directoryId)) continue
    seen.add(directoryId)
    summaries.push({
      directory_id: directoryId,
      directory_name: item.directory_name || directoryId,
      media_type: item.media_type || '',
      physical_size: 0,
      total: items.filter(candidate => candidate.directory_id === directoryId).length,
    })
  }
  return summaries
}

export function buildDirectoryOptions(directorySummaries = [], { formatMediaType }) {
  return directorySummaries.map((directory) => {
    const value = directory.directory_id || ''
    const mediaType = formatMediaType(directory.media_type)
    const label = mediaType && mediaType !== '-' ? `${directory.directory_name || value} · ${mediaType}` : (directory.directory_name || value)
    return {
      label,
      value,
    }
  }).filter(option => option.value)
}

export function createDirectoryIntegritySupport(t, getScanContext) {
  function mediaDisplayTitle(item) {
    const title = String(item?.media_title || '').trim()
    if (!title) return ''
    return item.media_year ? `${title} (${item.media_year})` : title
  }

  function mediaDetailRoute(item) {
    const seasonNumber = Number(item?.season_number)
    if (String(item?.media_id || '').includes(':tv:') && (!Number.isInteger(seasonNumber) || seasonNumber <= 0)) return null
    return {
      name: 'MediaDetail',
      params: { mediaId: item.media_id },
      query: Number.isInteger(seasonNumber) && seasonNumber > 0 ? { season: seasonNumber } : {},
    }
  }

  function formatIntegrityIssueType(issueType) {
    return t(`mediaManagement.directoryIntegrity.issueTypes.${issueType}`, issueType || '-')
  }

  function formatIntegrityScope(scope) {
    return t(`mediaManagement.directoryIntegrity.scopes.${scope}`, scope || '-')
  }

  function formatIntegrityRepairAction(action) {
    return t(`mediaManagement.directoryIntegrity.actions.${action}`, action || '-')
  }

  function filteredTrackerMessages(item) {
    return Array.isArray(item?.tracker_messages)
      ? item.tracker_messages.filter(message => message && !isIgnoredTrackerMessage(message))
      : []
  }

  function isIgnoredTrackerMessage(message) {
    const text = String(message || '').trim().toLowerCase()
    if (!text) return true
    return (text.includes('private') && text.includes('torrent'))
      || (text.includes('私有') && (text.includes('torrent') || text.includes('种子')))
  }

  function formatDownloaderState(item) {
    const state = item?.downloader_status_message || item?.downloader_state || '-'
    return t('mediaManagement.directoryIntegrity.downloaderState', { state })
  }

  function formatDirectoryLabel(item) {
    const label = String(item?.directory_name || item?.directory_id || '').trim()
    return label.replace(/库$/u, '')
  }

  function formatFileCreatedAt(value) {
    return t('mediaManagement.directoryIntegrity.fileCreatedAt', { time: formatRelativeTime(value) })
  }

  function formatRecordCreatedAt(value) {
    return t('mediaManagement.directoryIntegrity.recordCreatedAt', { time: formatRelativeTime(value) })
  }

  function formatTaskCompletedAt(value) {
    return t('mediaManagement.directoryIntegrity.taskCompletedAt', { time: formatRelativeTime(value) })
  }

  function formatMediaType(mediaType) {
    return t(`mediaManagement.mediaType.${mediaType}`, mediaType || '-')
  }

  function detailSections(item) {
    if (!item) return []
    return [
      buildDetailSection('overview', [
        detailRow('issue_type', formatIntegrityIssueType(item.issue_type)),
        detailRow('scope', formatIntegrityScope(item.scope)),
        detailRow('directory', item.directory_name || item.directory_id),
        detailRow('display_name', item.display_name),
        detailRow('reason', item.reason),
        detailRow('repairable', formatBoolean(item.repairable)),
        detailRow('repair_action', item.repair_action ? formatIntegrityRepairAction(item.repair_action) : ''),
        detailRow('scan_id', getScanContext()?.scan_id, { mono: true }),
        detailRow('scanned_at', formatDetailTime(getScanContext()?.scanned_at)),
      ]),
      buildDetailSection('media', [
        detailRow('media_title', mediaDisplayTitle(item), {
          route: item.media_id && mediaDisplayTitle(item) ? mediaDetailRoute(item) : null,
        }),
        detailRow('media_id', item.media_id, { mono: true }),
        detailRow('media_year', item.media_year),
      ]),
      buildDetailSection('file', [
        detailRow('path', item.path, { mono: true }),
        detailRow('relative_path', item.relative_path, { mono: true }),
        detailRow('size', formatSizeBytes(item.size)),
        detailRow('library_file_name', item.library_file_name),
      ]),
      buildDetailSection('time', [
        detailRow('file_created_at', formatDetailTime(item.file_created_at)),
        detailRow('record_created_at', formatDetailTime(item.record_created_at)),
        detailRow('task_completed_at', formatDetailTime(item.task_completed_at)),
      ]),
      buildDetailSection('references', [
        detailRow('id', item.id, { mono: true }),
        detailRow('task_id', item.task_id, { mono: true }),
        detailRow('library_file_id', item.library_file_id, { mono: true }),
        detailRow('directory_id', item.directory_id, { mono: true }),
      ]),
      buildDetailSection('downloader', [
        detailRow('downloader_state', item.downloader_state),
        detailRow('downloader_status_message', item.downloader_status_message),
        detailRow('tracker_messages', filteredTrackerMessages(item), { mono: true }),
      ]),
    ].filter(section => section.rows.length > 0)
  }

  function buildDetailSection(key, rows = []) {
    return {
      key,
      title: t(`mediaManagement.directoryIntegrity.detailSections.${key}`),
      rows: rows.filter(row => hasDetailValue(row.value)),
    }
  }

  function detailRow(key, value, options = {}) {
    return {
      key,
      label: t(`mediaManagement.directoryIntegrity.detailFields.${key}`, key),
      value,
      mono: Boolean(options.mono),
      route: options.route || null,
    }
  }

  function formatBoolean(value) {
    if (value === true) return t('common.yes')
    if (value === false) return t('common.no')
    return ''
  }

  function formatDetailTime(value) {
    if (!value) return ''
    return `${formatRelativeTime(value)} (${formatAbsoluteDateTime(value)})`
  }

  function buildDetailRawPayload(item) {
    if (!item) return null
    return {
      scan_id: getScanContext()?.scan_id || null,
      scanned_at: getScanContext()?.scanned_at || null,
      item,
    }
  }

  return {
    buildDetailRawPayload,
    detailSections,
    filteredTrackerMessages,
    formatDirectoryLabel,
    formatDownloaderState,
    formatFileCreatedAt,
    formatFileCreatedAtTooltip: formatAbsoluteDateTime,
    formatIntegrityIssueType,
    formatIntegrityRepairAction,
    formatIntegrityScope,
    formatMediaType,
    formatRecordCreatedAt,
    formatRecordCreatedAtTooltip: formatAbsoluteDateTime,
    formatSizeBytes,
    formatTaskCompletedAt,
    formatTaskCompletedAtTooltip: formatAbsoluteDateTime,
    mediaDetailRoute,
    mediaDisplayTitle,
  }
}

export function buildPolicyRows(response = {}) {
  const policies = new Map((response.policies || []).map(policy => [policy.directory_id, policy]))
  return (response.directories || []).map((directory) => {
    const policy = policies.get(directory.id) || {}
    const hasIssueTypes = Array.isArray(policy.issue_types)
    return {
      directory_id: directory.id,
      directory_name: directory.name || directory.id,
      directory_enabled: Boolean(directory.enabled),
      media_type: directory.media_type || '',
      enabled: policy.enabled !== false,
      scan_library: policy.scan_library !== false,
      scan_download: policy.scan_download !== false,
      issue_types: hasIssueTypes
        ? policy.issue_types.filter(issueType => ALL_DIRECTORY_INTEGRITY_ISSUE_TYPES.includes(issueType))
        : [...ALL_DIRECTORY_INTEGRITY_ISSUE_TYPES],
    }
  })
}

function hasDetailValue(value) {
  if (Array.isArray(value)) return value.length > 0
  return value !== null && value !== undefined && value !== ''
}

function formatSizeBytes(value) {
  const bytes = Number(value || 0)
  if (!bytes) return ''
  const units = ['B', 'KB', 'MB', 'GB', 'TB']
  let size = bytes
  let index = 0
  while (size >= 1024 && index < units.length - 1) {
    size /= 1024
    index += 1
  }
  return index === 0 ? `${size} ${units[index]}` : `${size.toFixed(2)} ${units[index]}`
}
