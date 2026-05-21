export async function toggleManagedSubscription({
  item,
  actionLoading,
  patchItem,
  restoreItem,
  cloneItem,
  shouldKeepItem,
  endCurrentSubscription,
  notification,
  refreshSummary,
  t,
}) {
  if (!item?.media_id) return
  if (!item.monitor.subscribed) return

  actionLoading.value = `subscription:${item.media_id}:${item.season_number || ''}`
  const previousItem = cloneItem?.(item) ?? null
  try {
    const snapshot = await endCurrentSubscription(item.media_id, item.season_number || null)
    patchItem?.(item.media_id, (current) => {
      const next = {
        ...current,
        monitor: {
          ...current.monitor,
          subscribed: !!snapshot?.active,
          followed: !!snapshot?.followed,
          subscription_id: snapshot?.sub_id || null,
        },
      }
      return (shouldKeepItem?.(next) ?? true) ? next : null
    }, item.season_number || null)
    notification.success(t('mediaManagement.notifications.subscriptionCancelled'))
    await refreshSummary?.()
  } catch {
    restoreItem?.(previousItem)
    notification.error(t('mediaManagement.notifications.subscriptionCancelFailed'))
  } finally {
    actionLoading.value = ''
  }
}

export async function toggleManagedFollow({
  item,
  actionLoading,
  patchItem,
  restoreItem,
  cloneItem,
  shouldKeepItem,
  getSubscriptionState,
  updateMediaSubscriptionState,
  notification,
  refreshSummary,
  t,
}) {
  if (!item?.media_id) return
  if (!item.monitor.followed) return

  actionLoading.value = `follow:${item.media_id}:${item.season_number || ''}`
  const previousItem = cloneItem?.(item) ?? null

  try {
    const currentState = await getSubscriptionState(item.media_id, item.season_number || null)
    const updated = await updateMediaSubscriptionState(item.media_id, {
      active: !!currentState?.active,
      followed: false,
      upgrade_policy: currentState?.upgrade_policy || null,
    }, item.season_number || null)
    patchItem?.(item.media_id, (current) => {
      const next = {
        ...current,
        monitor: {
          ...current.monitor,
          subscribed: !!updated?.active,
          followed: !!updated?.followed,
          subscription_id: updated?.sub_id || null,
        },
      }
      return (shouldKeepItem?.(next) ?? true) ? next : null
    }, item.season_number || null)
    notification.success(t('mediaManagement.notifications.followCancelled'))
    await refreshSummary?.()
  } catch {
    restoreItem?.(previousItem)
    notification.error(t('mediaManagement.notifications.followCancelFailed'))
  } finally {
    actionLoading.value = ''
  }
}
