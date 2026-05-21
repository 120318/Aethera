import { buildMediaTarget } from '@/composables/mediaIdentitySupport'
import { t } from '@/i18n'

export function resolveMediaIdFromRoute(route) {
  return route.params.mediaId
    || route.params.media_id
    || route.params.id
    || route.query.media_id
    || route.query.id
}

export function createLibraryDetailDialogState() {
  return {
    visible: false,
    loading: false,
    resource: null,
    record: null,
    package: null,
  }
}

export function createDeleteDialogState() {
  return {
    visible: false,
    target: null,
    loading: false,
  }
}

export function clearLibraryDetailDialog(dialog) {
  dialog.loading = false
  dialog.resource = null
  dialog.record = null
  dialog.package = null
}

export async function openLibraryDetailDialog({ dialog, resource, notification, getLibraryFileDetail }) {
  if (!resource?.id) {
    notification.warn(t('mediaDetail.noViewableResourceDetail'))
    return
  }

  dialog.visible = true
  dialog.loading = true
  dialog.resource = resource
  dialog.record = null
  dialog.package = null

  try {
    const data = await getLibraryFileDetail(resource.id)
    dialog.record = data?.data || null
    dialog.package = data?.package || null
  } catch {
    notification.error(t('mediaDetail.loadLocalResourceDetailFailed'))
  } finally {
    dialog.loading = false
  }
}

export async function refreshMediaDetailTab({ mediaId, seasonNumber = null, activeTab, loadResourceInfo, loadDetailOverview, loadTaskInfo }) {
  if (!mediaId) return

  if (activeTab === 'resources') {
    await Promise.all([
      loadResourceInfo(mediaId, seasonNumber),
      loadDetailOverview(mediaId, seasonNumber),
    ])
    return
  }

  if (activeTab === 'tasks') {
    await loadTaskInfo(mediaId, seasonNumber)
  }
}

export async function submitLibraryFileDelete({
  target,
  mediaId,
  seasonNumber = null,
  submitCommand,
  handleCommandSubmitted,
}) {
  if (!target?.id) return

  const command = await submitCommand(
    {
      type: 'library_file.delete',
      payload: {
        file_id: target.id,
        target: buildMediaTarget({ media_id: mediaId, seasonNumber }),
        package_root: target.is_package ? target.package_root : '',
      },
    },
    { dedupeKey: `library_file:${target.is_package ? target.package_root || target.id : target.id}:library_file.delete` },
  )
  handleCommandSubmitted(command)
}

export async function handleMediaSubscriptionClick({ handleSubscriptionToggle }) {
  await handleSubscriptionToggle()
}
