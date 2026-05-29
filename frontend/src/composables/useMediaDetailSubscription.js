import { computed, reactive, ref } from 'vue'
import {
  endCurrentSubscription,
  getMediaDownloadConfig,
  getSubscriptionState,
  updateMediaSubscriptionState,
} from '@/api/subscription'
import { downloadPilotEpisode } from '@/api/resource'
import { useActionPrerequisites } from '@/composables/useActionPrerequisites'
import { buildMediaTarget } from '@/composables/mediaIdentitySupport'
import {
  resolveDefaultDirectoryId,
  resolveEffectiveFilters,
  resolveFilterPresetName,
  resolveRouteMediaType,
} from '@/composables/mediaDetailSubscriptionFlowSupport'
import { useOperationsStore } from '@/stores/operations'
import { useI18n } from 'vue-i18n'

export function useMediaDetailSubscription(options = {}) {
  const { mediaId, detail, detailOverview, selectedSeasonNumber, notification, loadDetailOverview } = options
  const { t } = useI18n()
  const operations = useOperationsStore()
  const actionReadiness = computed(() => detailOverview?.value?.summary?.action_readiness || null)
  const { ensureSubscriptionReady } = useActionPrerequisites({ readinessSource: actionReadiness })

  const subscription = ref(null)
  const downloadConfig = ref(null)
  const loadingSubscription = ref(true)
  const checkingSubscription = ref(false)
  const subscriptionDialog = reactive({ visible: false })

  const routeMediaType = computed(() => resolveRouteMediaType(mediaId.value))
  const catalogs = computed(() => detailOverview?.value?.catalogs || {})
  const defaultFilterPreset = computed(() => (
    (Array.isArray(catalogs.value?.filters) ? catalogs.value.filters : []).find((item) => item.active_default) || null
  ))
  const defaultDirectoryId = computed(() => resolveDefaultDirectoryId({
    detail: detail.value,
    objectConfig: {
      directories: Array.isArray(catalogs.value?.directories) ? catalogs.value.directories : [],
    },
    routeMediaType: routeMediaType.value,
  }))

  const effectiveFilters = computed(() => resolveEffectiveFilters(downloadConfig.value, defaultFilterPreset.value))
  const filterPresetName = computed(() => resolveFilterPresetName(downloadConfig.value, defaultFilterPreset.value))
  const currentMediaType = computed(() => detail.value?.media_type || detail.value?.type)
  const activeSeasonNumber = computed(() => {
    const selected = Number(selectedSeasonNumber?.value)
    if (Number.isInteger(selected) && selected > 0) return selected
    const detailSeason = Number(detail.value?.season_number)
    return Number.isInteger(detailSeason) && detailSeason > 0 ? detailSeason : null
  })
  const hasRequiredSeasonContext = computed(() => currentMediaType.value !== 'tv' || !!activeSeasonNumber.value)

  function requireSeasonContext(actionLabel) {
    if (hasRequiredSeasonContext.value) return true
    notification.warn(t('mediaDetail.selectSeasonForAction', { action: actionLabel }))
    return false
  }

  function applySubscriptionSnapshot(state, config, snapshotMediaId = mediaId.value) {
    subscription.value = {
      media_id: snapshotMediaId,
      sub_id: state?.sub_id || config?.sub_id || null,
      active: !!state?.active,
      followed: !!state?.followed,
      subscription_mode: state?.subscription_mode || (routeMediaType.value === 'movie' ? 'first_release' : 'current_aired_complete'),
      upgrade_policy: state?.upgrade_policy || null,
      last_checked_at: state?.last_checked_at || state?.last_run_at || null,
      ended_reason: state?.ended_reason || null,
      ended_at: state?.ended_at || null,
    }
    downloadConfig.value = config || null
    loadingSubscription.value = false
  }

  async function handleCheckSubscription(options = {}) {
    const { preferOverview = true } = options
    loadingSubscription.value = true
    try {
      void preferOverview
      if (!hasRequiredSeasonContext.value) {
        subscription.value = null
        downloadConfig.value = null
        return
      }
      const [state, config] = await Promise.all([
        getSubscriptionState(mediaId.value, activeSeasonNumber.value),
        getMediaDownloadConfig(mediaId.value, activeSeasonNumber.value),
      ])
      applySubscriptionSnapshot(state, config)
    } finally {
      loadingSubscription.value = false
    }
  }

  async function handleSubscriptionToggle(options = {}) {
    const { overrideConfig = null } = options
    if (!requireSeasonContext(t('mediaDetail.subscribeAction'))) return
    const enabling = !subscription.value?.active
    if (enabling) {
      const canContinue = await ensureSubscriptionReady(currentMediaType.value)
      if (!canContinue) return
    }
    checkingSubscription.value = true
    try {
      const currentConfig = overrideConfig || downloadConfig.value || {}
      const nextState = enabling
        ? await updateMediaSubscriptionState(mediaId.value, {
          active: true,
          followed: !!subscription.value?.followed,
          subscription_mode: subscription.value?.subscription_mode || (routeMediaType.value === 'movie' ? 'first_release' : 'current_aired_complete'),
          upgrade_policy: subscription.value?.upgrade_policy || null,
        }, activeSeasonNumber.value)
        : await endCurrentSubscription(mediaId.value, activeSeasonNumber.value)
      if (overrideConfig) {
        downloadConfig.value = currentConfig
      }
      subscription.value = {
        media_id: mediaId.value,
        sub_id: nextState?.sub_id || currentConfig?.sub_id || subscription.value?.sub_id || null,
        active: !!nextState?.active,
        followed: !!nextState?.followed,
        subscription_mode: nextState?.subscription_mode || subscription.value?.subscription_mode || (routeMediaType.value === 'movie' ? 'first_release' : 'current_aired_complete'),
        upgrade_policy: nextState?.upgrade_policy || null,
        last_checked_at: nextState?.last_checked_at || nextState?.last_run_at || subscription.value?.last_checked_at || null,
        ended_reason: nextState?.ended_reason || null,
        ended_at: nextState?.ended_at || null,
      }
      if (loadDetailOverview) {
        await loadDetailOverview(mediaId.value, activeSeasonNumber.value)
      }
      notification.success(enabling ? t('subscription.subscribed') : t('mediaDetail.subscriptionCancelled'))
      return { completed: true }
    } finally {
      checkingSubscription.value = false
    }
  }

  async function handleRunSubscription() {
    if (!mediaId.value || !subscription.value?.active) return null
    if (!requireSeasonContext(t('mediaDetail.refreshSubscriptionAction'))) return null
    try {
      const seasonNumber = currentMediaType.value === 'tv' ? activeSeasonNumber.value : null
      const command = await operations.submitCommand({
        type: 'subscription.run',
        payload: {
          target: buildMediaTarget({
            media_id: mediaId.value,
            seasonNumber,
          }),
        },
      }, {
        dedupeKey: `media:${mediaId.value}:${seasonNumber || ''}:subscription.run`,
      })
      if (command) notification.success(t('subscription.refreshTaskSubmitted'))
      return command
    } catch (error) {
      notification.error(error?.response?.data?.message || error?.message || t('subscription.submitRefreshTaskFailed'))
      return null
    }
  }

  async function handlePilotEpisode() {
    if (!requireSeasonContext(currentMediaType.value === 'movie' ? t('mediaDetail.downloadAction') : t('mediaDetail.pilotAction'))) return null
    const canContinue = await ensureSubscriptionReady(currentMediaType.value)
    if (!canContinue) return null
    try {
      const response = await downloadPilotEpisode({
        target: buildMediaTarget({
          media_id: mediaId.value,
          seasonNumber: currentMediaType.value === 'tv' ? activeSeasonNumber.value : null,
        }),
      })
      return response?.command || response || null
    } catch {
      return null
    }
  }

  return {
    subscription,
    downloadConfig,
    loadingSubscription,
    checkingSubscription,
    subscriptionDialog,
    defaultFilterPreset,
    defaultDirectoryId,
    effectiveFilters,
    filterPresetName,
    handleCheckSubscription,
    applySubscriptionSnapshot,
    handleSubscriptionToggle,
    handleRunSubscription,
    handlePilotEpisode,
    canMutateSubscription: computed(() => hasRequiredSeasonContext.value && !!mediaId.value),
  }
}
