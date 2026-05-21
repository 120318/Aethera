import { computed } from 'vue'

import { updateMediaSubscriptionState } from '@/api/subscription'
import { useActionPrerequisites } from '@/composables/useActionPrerequisites'
import { useI18n } from 'vue-i18n'

export function useMediaDetailFollow(options = {}) {
  const { mediaId, selectedSeasonNumber, notification, subscription, checkingSubscription, loadDetailOverview } = options
  const { ensureFollowReady } = useActionPrerequisites()
  const { t } = useI18n()

  async function handleFollowToggle() {
    if (!subscription.value?.followed) {
      const canContinue = await ensureFollowReady()
      if (!canContinue) return
    }
    checkingSubscription.value = true
    try {
      const followed = !!subscription.value?.followed
      const updated = await updateMediaSubscriptionState(mediaId.value, {
        active: !!subscription.value?.active,
        followed: !followed,
        subscription_mode: subscription.value?.subscription_mode || null,
        upgrade_policy: subscription.value?.upgrade_policy || null,
      }, selectedSeasonNumber?.value || null)
      subscription.value = {
        media_id: mediaId.value,
        sub_id: updated?.sub_id || subscription.value?.sub_id || null,
        active: !!updated?.active,
        followed: !!updated?.followed,
        subscription_mode: updated?.subscription_mode || subscription.value?.subscription_mode || null,
        upgrade_policy: updated?.upgrade_policy || null,
      }
      if (loadDetailOverview) {
        await loadDetailOverview(mediaId.value, selectedSeasonNumber?.value || null)
      }
      notification.success(followed ? t('mediaDetail.followCancelled') : t('mediaDetail.followed'))
    } finally {
      checkingSubscription.value = false
    }
  }

  return {
    handleFollowToggle,
    canMutateFollow: computed(() => !!mediaId.value),
  }
}
