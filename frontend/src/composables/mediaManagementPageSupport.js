export function buildMediaManagementTypeOptions(t) {
  return [
    { label: t('mediaManagement.filters.allTypes'), value: '' },
    { label: t('mediaManagement.mediaType.movie'), value: 'movie' },
    { label: t('mediaManagement.mediaType.tv'), value: 'tv' },
  ]
}

export function buildMediaManagementStatusOptions(t) {
  return [
    { label: t('subscription.subscribed'), value: 'subscribed' },
    { label: t('subscription.followed'), value: 'followed' },
    { label: t('mediaManagement.status.downloading'), value: 'downloading' },
    { label: t('mediaManagement.status.downloaded'), value: 'downloaded' },
    { label: t('mediaManagement.status.inLibrary'), value: 'library' },
    { label: t('mediaManagement.status.issues'), value: 'issues' },
  ]
}

export function buildMediaManagementSortOptions(t) {
  return [
    { label: t('mediaManagement.sort.recentActivity'), value: 'activity' },
    { label: t('mediaManagement.sort.title'), value: 'title' },
    { label: t('mediaManagement.sort.tasks'), value: 'tasks' },
    { label: t('mediaManagement.sort.library'), value: 'library' },
    { label: t('mediaManagement.sort.issuesFirst'), value: 'issues' },
  ]
}

export function buildMediaManagementSummaryCards(summary, t) {
  const data = summary || {}
  return [
    { key: 'total', label: t('mediaManagement.summary.total'), value: data.total || 0, valueClass: 'text-muted' },
    { key: 'subscribed', label: t('subscription.subscribed'), value: data.subscribed || 0, valueClass: 'text-status-success' },
    { key: 'followed', label: t('subscription.followed'), value: data.followed || 0, valueClass: 'text-primary' },
    { key: 'downloading', label: t('mediaManagement.status.downloading'), value: data.downloading || 0, valueClass: 'text-status-warning' },
    { key: 'in_library', label: t('mediaManagement.status.inLibrary'), value: data.in_library || 0, valueClass: 'text-muted' },
    { key: 'issues', label: t('mediaManagement.summary.issues'), value: data.issues || 0, valueClass: 'text-status-error' },
  ]
}

export function getManagedItemActionLoading(actionLoading, item) {
  if (!item?.media_id || !actionLoading) return ''
  const [type, ...targetParts] = actionLoading.split(':')
  const targetKey = targetParts.join(':')
  const itemKey = getManagedItemKey(item)
  return targetKey === itemKey ? type : ''
}

export function getManagedItemKey(item) {
  if (!item?.media_id) return ''
  return `${item.media_id}:${item?.season_number || ''}`
}

export function matchesMediaManagementFilters(item, filters) {
  const current = filters || {}
  const query = String(current.query || '').trim().toLowerCase()
  if (query) {
    const haystacks = [
      item?.title,
      item?.media_id,
    ]
      .filter(Boolean)
      .map(value => String(value).toLowerCase())
    if (!haystacks.some(value => value.includes(query))) {
      return false
    }
  }

  if (current.mediaType && item?.media_type !== current.mediaType) {
    return false
  }

  const statuses = Array.isArray(current.statuses) ? current.statuses : []
  if (statuses.length === 0) return true

  const matchedStatuses = new Set()
  if (item?.monitor?.subscribed) matchedStatuses.add('subscribed')
  if (item?.monitor?.followed) matchedStatuses.add('followed')
  if ((item?.active_task_count || 0) > 0) matchedStatuses.add('downloading')
  if ((item?.task_count || 0) > 0 && (item?.active_task_count || 0) === 0 && (item?.library_count || 0) === 0) {
    matchedStatuses.add('downloaded')
  }
  if ((item?.library_count || 0) > 0) matchedStatuses.add('library')
  if (item?.issues?.has_issues) matchedStatuses.add('issues')

  return statuses.some(status => matchedStatuses.has(status))
}

export function shouldKeepManagedItem(item, filters) {
  const managed = Boolean(
    item?.monitor?.subscribed
    || item?.monitor?.followed
    || (item?.task_count || 0) > 0
    || (item?.library_count || 0) > 0
  )
  return managed && matchesMediaManagementFilters(item, filters)
}

export function cloneManagedItem(item) {
  return JSON.parse(JSON.stringify(item))
}

export function patchManagedItem(allItems, mediaId, updater, seasonNumber = null) {
  const index = allItems.findIndex((entry) => (
    entry.media_id === mediaId && (entry.season_number || null) === (seasonNumber || null)
  ))
  if (index === -1) return null

  const current = allItems[index]
  const next = updater(current)
  if (!next) {
    allItems.splice(index, 1)
    return null
  }

  allItems.splice(index, 1, next)
  return next
}

export function upsertManagedItem(allItems, item) {
  if (!item?.media_id) return null
  const index = allItems.findIndex((entry) => (
    entry.media_id === item.media_id && (entry.season_number || null) === (item.season_number || null)
  ))
  if (index === -1) {
    allItems.unshift(item)
    return item
  }
  allItems.splice(index, 1, item)
  return item
}
