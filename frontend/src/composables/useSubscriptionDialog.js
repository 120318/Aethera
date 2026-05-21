import { computed, nextTick, reactive, ref, watch } from 'vue'
import { saveSubscriptionDialog } from '@/api/subscription'
import { buildMediaTarget } from '@/composables/mediaIdentitySupport'
import { useSubscriptionDialogCatalogs } from '@/composables/useSubscriptionDialogCatalogs'
import {
  applySubscriptionConfigFilters, createDefaultUpgradePolicy, createEmptySubscriptionConfigFilters,
  createEmptyUnmatchedRule, getDefaultDirectoryId, hasMeaningfulSubscriptionFilters, subscriptionFilterModeCustom,
  subscriptionFilterModeOptions, subscriptionFilterModePreset, subscriptionFilterModePresetOverride, subscriptionConfigAudioChannelOptions,
  subscriptionConfigAudioCodecOptions, subscriptionConfigCodecOptions, subscriptionConfigColorDepthOptions, subscriptionConfigHdrOptions,
  subscriptionConfigResolutionOptions, subscriptionConfigSourceOptions, subscriptionConfigUpgradeLockModeOptions,
  buildSubscriptionDialogSavePayload, buildSubscriptionDialogTabs, buildSubscriptionModeOptions,
  cloneSubscriptionFilters, cloneSubscriptionUpgradePolicy, resolveSubscriptionFilterMode,
} from '@/composables/subscriptionConfigDialogSupport'
import { normalizeResourceFormsForKinds } from '@/constants/qualityOptions'
import { useNotificationStore } from '@/stores/notification'
import { useOperationsStore } from '@/stores/operations'
import { useI18n } from 'vue-i18n'
export function useSubscriptionDialog(props, emit) {
  const notification = useNotificationStore(); const operations = useOperationsStore()
  const { t } = useI18n()
  const saving = ref(false)
  const loadingInitialData = ref(false)
  const filterMode = ref(subscriptionFilterModePreset)
  const targetFilterMode = ref(subscriptionFilterModePreset)
  const targetFilterConfigId = ref(null)
  const lastFilterPresetId = ref(null)
  const lastTargetFilterPresetId = ref(null)
  const activeTab = ref('basic')
  const runAfterSave = ref(false)
  const upgradeMode = ref('off')
  const isUpdatingFromPreset = ref(false)
  const isSyncingUpgradePolicyMirror = ref(false)
  const isExplicitQualityProfile = ref(false)
  const mediaType = computed(() => {
    const [, type] = String(props.mediaId || '').split(':'); return type === 'movie' || type === 'tv' ? type : null
  })
  const isMovieMedia = computed(() => mediaType.value === 'movie')
  const form = reactive({
    active: false,
    followed: false,
    subscription_mode: 'first_release',
    upgrade_policy: createDefaultUpgradePolicy(),
    target_filters: createEmptySubscriptionConfigFilters(),
    directory_id: null,
    sites: [],
    filter_config_id: null,
    quality_profile_id: null,
    filters: createEmptySubscriptionConfigFilters(),
    unmatched_rules: [],
  })
  const {
    loadingDirs,
    directoryOptions,
    filterOptions,
    qualityProfileOptions,
    tagOptions,
    siteOptions,
    fetchDirectories,
    fetchFilterPresets,
    fetchQualityProfiles,
    fetchTags,
    fetchSites,
  } = useSubscriptionDialogCatalogs({ props, mediaType, form, notification, t })
  const subscriptionLabel = computed(() => (form.active ? t('subscription.subscribed') : t('subscription.notSubscribed')))
  const followLabel = computed(() => (form.followed ? t('subscription.followed') : t('subscription.notFollowed')))
  const subscriptionModeOptions = computed(() => buildSubscriptionModeOptions(t, isMovieMedia.value))
  const showAdvancedUpgradeSettings = computed(() => !isMovieMedia.value && form.subscription_mode === 'upgrade_continuous')
  const showTargetFilters = computed(() => form.subscription_mode === 'upgrade_continuous')
  const filterModeOptions = computed(() => subscriptionFilterModeOptions.map((option) => ({
    label: t(option.labelKey),
    value: option.value,
  })))
  const upgradeLockModeOptions = computed(() => subscriptionConfigUpgradeLockModeOptions.map((option) => ({
    label: t(option.labelKey),
    value: option.value,
  })))
  const showCustomFilters = computed(() => filterMode.value !== subscriptionFilterModePreset)
  const showBaseFilterPreset = computed(() => filterMode.value !== subscriptionFilterModeCustom)
  const showCustomTargetFilters = computed(() => targetFilterMode.value !== subscriptionFilterModePreset)
  const showTargetBasePreset = computed(() => targetFilterMode.value !== subscriptionFilterModeCustom)
  const canRunAfterSave = computed(() => !!form.active && !loadingInitialData.value)
  const primarySaveLabel = computed(() => (!props.initialState?.active && form.active ? t('subscription.saveAndSubscribe') : t('common.save')))
  const subscriptionDialogTabs = computed(() => buildSubscriptionDialogTabs(t, showTargetFilters.value))

  function getFilterPreset(filterConfigId) {
    return filterOptions.value.find((item) => item.id === filterConfigId) || null
  }

  async function syncFilterUpgradePolicyFromTopLevel() {
    isSyncingUpgradePolicyMirror.value = true
    form.filters.upgrade_policy = cloneSubscriptionUpgradePolicy(form.upgrade_policy)
    await nextTick()
    isSyncingUpgradePolicyMirror.value = false
  }

  async function syncDialogUpgradeModeFromPolicy() {
    const policy = cloneSubscriptionUpgradePolicy(form.upgrade_policy)
    form.upgrade_policy = policy
    isSyncingUpgradePolicyMirror.value = true
    form.filters.upgrade_policy = cloneSubscriptionUpgradePolicy(policy)
    upgradeMode.value = policy.enabled ? policy.strategy : 'off'
    await nextTick()
    isSyncingUpgradePolicyMirror.value = false
  }

  async function syncDialogUpgradePolicyFromMode() {
    if (upgradeMode.value === 'off') {
      form.upgrade_policy.enabled = false
    } else {
      form.upgrade_policy.enabled = true
      form.upgrade_policy.strategy = upgradeMode.value
    }
    await syncFilterUpgradePolicyFromTopLevel()
  }

  function getDefaultQualityProfileId() {
    return qualityProfileOptions.value.find((item) => item.active_default)?.id || qualityProfileOptions.value[0]?.id || null
  }

  function getQualityProfileName(profileId) {
    return qualityProfileOptions.value.find((item) => item.id === profileId)?.name || t('subscription.defaultQualityProfile')
  }

  function getPresetQualityProfileId(filterConfigId) {
    if (!filterConfigId) return getDefaultQualityProfileId()
    const preset = getFilterPreset(filterConfigId)
    return preset?.quality_profile_id || getDefaultQualityProfileId()
  }

  function getInheritedQualityProfileId() {
    return getPresetQualityProfileId(form.filter_config_id)
  }

  const qualityProfileDropdownOptions = computed(() => [
    {
      id: null,
      name: t('subscription.followFilterWithProfile', { name: getQualityProfileName(getInheritedQualityProfileId()) }),
    },
    ...qualityProfileOptions.value,
  ])
  const qualityProfileSelection = computed({
    get: () => (isExplicitQualityProfile.value ? form.quality_profile_id : null),
    set: (value) => {
      if (!value) {
        isExplicitQualityProfile.value = false
        form.quality_profile_id = getInheritedQualityProfileId()
        return
      }
      isExplicitQualityProfile.value = true
      form.quality_profile_id = value
    },
  })

  function getPreferredFilterPresetId(candidateId = null) {
    if (candidateId && getFilterPreset(candidateId)) return candidateId
    const activeDefault = filterOptions.value.find((item) => item.active_default)?.id
    if (activeDefault) return activeDefault
    return filterOptions.value[0]?.id || null
  }

  function getPreferredTargetFilterPresetId(candidateId = null) {
    return getPreferredFilterPresetId(candidateId)
  }

  function resetCustomFilters() {
    form.filters = createEmptySubscriptionConfigFilters()
  }

  async function runProtectedFilterUpdate(updater) {
    isUpdatingFromPreset.value = true
    updater()
    await nextTick()
    isUpdatingFromPreset.value = false
  }

  async function replaceCustomFilters(filters) {
    await runProtectedFilterUpdate(() => {
      resetCustomFilters()
      applySubscriptionConfigFilters(form, filters || {}, createDefaultUpgradePolicy())
    })
  }

  async function applyPresetFiltersToCustom(filterConfigId, { notify = false } = {}) {
    const preset = getFilterPreset(filterConfigId)
    await replaceCustomFilters(cloneSubscriptionFilters(preset?.filters || {}))
    if (notify) {
      notification.info(t('subscription.customFiltersReset'))
    }
  }

  function resetTargetFilters() {
    form.target_filters = createEmptySubscriptionConfigFilters()
  }

  async function replaceTargetFilters(filters) {
    resetTargetFilters()
    applySubscriptionConfigFilters({ filters: form.target_filters }, filters || {}, createDefaultUpgradePolicy())
    await nextTick()
  }

  async function applyPresetFiltersToTarget(filterConfigId, { notify = false } = {}) {
    const preset = getFilterPreset(filterConfigId)
    await replaceTargetFilters(cloneSubscriptionFilters(preset?.filters || {}))
    if (notify) {
      notification.info(t('subscription.targetFiltersReset'))
    }
  }

  function resetForm() {
    const state = props.initialState || null
    const config = props.initialConfig || null
    form.active = !!state?.active
    form.followed = !!state?.followed
    form.subscription_mode = state?.subscription_mode || (isMovieMedia.value ? 'first_release' : 'current_aired_complete')
    form.upgrade_policy = state?.upgrade_policy ? { ...state.upgrade_policy } : createDefaultUpgradePolicy()
    resetTargetFilters()
    resetCustomFilters()
    targetFilterConfigId.value = state?.target_filter_config_id || null
    lastTargetFilterPresetId.value = targetFilterConfigId.value
    targetFilterMode.value = resolveSubscriptionFilterMode({
      presetId: targetFilterConfigId.value,
      filters: state?.target_filters || null,
    })
    form.directory_id = config?.directory_id || null
    form.sites = Array.isArray(config?.sites) ? [...config.sites] : []
    form.filter_config_id = config?.filter_config_id || null
    lastFilterPresetId.value = form.filter_config_id
    filterMode.value = resolveSubscriptionFilterMode({
      presetId: form.filter_config_id,
      filters: config?.filters || null,
    })
    form.quality_profile_id = config?.quality_profile_id || null
    isExplicitQualityProfile.value = Boolean(config?.quality_profile_id)
    form.unmatched_rules = Array.isArray(config?.unmatched_rules)
      ? config.unmatched_rules.map((rule) => ({
          sites: Array.isArray(rule?.sites) ? [...rule.sites] : [],
          search_title: rule?.search_title || '',
          pattern: rule?.pattern || '',
        }))
      : []
    activeTab.value = 'basic'
    runAfterSave.value = false
  }

  async function applyDefaultActiveFilter() {
    const defaultFilterId = getPreferredFilterPresetId()
    if (!defaultFilterId) return
    filterMode.value = subscriptionFilterModePreset
    form.filter_config_id = defaultFilterId
    lastFilterPresetId.value = defaultFilterId
    await onFilterPresetChange(defaultFilterId)
  }

  async function onFilterPresetChange(filterConfigId = form.filter_config_id, { notify = false } = {}) {
    form.filter_config_id = filterConfigId || null
    if (form.filter_config_id) {
      lastFilterPresetId.value = form.filter_config_id
    }
    isExplicitQualityProfile.value = false
    form.quality_profile_id = getPresetQualityProfileId(form.filter_config_id)

    if (!form.filter_config_id) {
      if (filterMode.value === subscriptionFilterModePreset) {
        filterMode.value = subscriptionFilterModeCustom
      }
      return
    }

    if (filterMode.value === subscriptionFilterModePreset) {
      await replaceCustomFilters({})
      await syncFilterUpgradePolicyFromTopLevel()
      return
    }

    if (filterMode.value === subscriptionFilterModePresetOverride) {
      await applyPresetFiltersToCustom(form.filter_config_id, { notify })
      await syncFilterUpgradePolicyFromTopLevel()
    }
  }

  async function onFilterModeChange(event) {
    const nextMode = event?.value ?? event ?? subscriptionFilterModePreset
    filterMode.value = nextMode

    if (nextMode === subscriptionFilterModePreset) {
      const presetId = getPreferredFilterPresetId(form.filter_config_id || lastFilterPresetId.value)
      form.filter_config_id = presetId
      lastFilterPresetId.value = presetId
      await onFilterPresetChange(presetId)
      return
    }

    if (nextMode === subscriptionFilterModePresetOverride) {
      const presetId = getPreferredFilterPresetId(form.filter_config_id || lastFilterPresetId.value)
      form.filter_config_id = presetId
      lastFilterPresetId.value = presetId
      await onFilterPresetChange(presetId)
      return
    }

    if (form.filter_config_id) {
      lastFilterPresetId.value = form.filter_config_id
    }
    form.filter_config_id = null
    if (!isExplicitQualityProfile.value) {
      form.quality_profile_id = getDefaultQualityProfileId()
    }
  }

  async function onFilterPresetSelectionChange(event) {
    const nextPresetId = event?.value ?? event ?? null
    form.filter_config_id = nextPresetId
    lastFilterPresetId.value = nextPresetId
    await onFilterPresetChange(nextPresetId, {
      notify: filterMode.value === subscriptionFilterModePresetOverride,
    })
  }

  async function onTargetFilterModeChange(event) {
    const nextMode = event?.value ?? event ?? subscriptionFilterModePreset
    targetFilterMode.value = nextMode

    if (nextMode === subscriptionFilterModePreset) {
      const presetId = getPreferredTargetFilterPresetId(targetFilterConfigId.value || lastTargetFilterPresetId.value)
      targetFilterConfigId.value = presetId
      lastTargetFilterPresetId.value = presetId
      await applyPresetFiltersToTarget(presetId)
      return
    }

    if (nextMode === subscriptionFilterModePresetOverride) {
      const presetId = getPreferredTargetFilterPresetId(targetFilterConfigId.value || lastTargetFilterPresetId.value)
      targetFilterConfigId.value = presetId
      lastTargetFilterPresetId.value = presetId
      await applyPresetFiltersToTarget(presetId)
      return
    }

    if (targetFilterConfigId.value) {
      lastTargetFilterPresetId.value = targetFilterConfigId.value
    }
    targetFilterConfigId.value = null
  }

  async function onTargetFilterPresetSelectionChange(event) {
    const nextPresetId = event?.value ?? event ?? null
    targetFilterConfigId.value = nextPresetId
    lastTargetFilterPresetId.value = nextPresetId
    if (targetFilterMode.value === subscriptionFilterModePreset) {
      await applyPresetFiltersToTarget(nextPresetId)
      return
    }
    if (targetFilterMode.value === subscriptionFilterModePresetOverride) {
      await applyPresetFiltersToTarget(nextPresetId, { notify: true })
    }
  }

  function onQualityProfileChange(event) {
    if (!event?.value) {
      isExplicitQualityProfile.value = false
      form.quality_profile_id = getInheritedQualityProfileId()
      return
    }
    isExplicitQualityProfile.value = true
  }

  async function applyInitialConfig() {
    const state = props.initialState || null
    const config = props.initialConfig || null

    if (!config) {
      form.directory_id = getDefaultDirectoryId(mediaType.value, directoryOptions.value) || null
      form.quality_profile_id = getDefaultQualityProfileId()
      if (targetFilterMode.value !== subscriptionFilterModePreset) {
        await replaceTargetFilters(state?.target_filters || {})
      } else {
        await replaceTargetFilters({})
      }
      await applyDefaultActiveFilter()
      await syncFilterUpgradePolicyFromTopLevel()
      return
    }

    form.directory_id = config.directory_id || getDefaultDirectoryId(mediaType.value, directoryOptions.value) || null
    form.sites = Array.isArray(config.sites) ? [...config.sites] : []
    form.filter_config_id = config.filter_config_id || null
    lastFilterPresetId.value = form.filter_config_id
    filterMode.value = resolveSubscriptionFilterMode({
      presetId: config.filter_config_id || null,
      filters: config.filters || null,
    })
    form.quality_profile_id = config.quality_profile_id || getPresetQualityProfileId(config.filter_config_id || null)
    isExplicitQualityProfile.value = Boolean(config.quality_profile_id)

    targetFilterConfigId.value = state?.target_filter_config_id || null
    lastTargetFilterPresetId.value = targetFilterConfigId.value
    targetFilterMode.value = resolveSubscriptionFilterMode({
      presetId: targetFilterConfigId.value,
      filters: state?.target_filters || null,
    })

    if (targetFilterMode.value === subscriptionFilterModePresetOverride || targetFilterMode.value === subscriptionFilterModeCustom) {
      await replaceTargetFilters(state?.target_filters || {})
    } else {
      await replaceTargetFilters({})
    }

    if (filterMode.value === subscriptionFilterModePresetOverride || filterMode.value === subscriptionFilterModeCustom) {
      await replaceCustomFilters(config.filters || {})
    } else {
      await replaceCustomFilters({})
    }

    if (!form.filter_config_id && filterMode.value !== subscriptionFilterModeCustom && !hasMeaningfulSubscriptionFilters(config.filters || null)) {
      await applyDefaultActiveFilter()
    } else if (!isExplicitQualityProfile.value) {
      form.quality_profile_id = getInheritedQualityProfileId()
    }

    await syncFilterUpgradePolicyFromTopLevel()
  }

  function buildSavePayload() {
    return buildSubscriptionDialogSavePayload({
      form,
      isMovieMedia: isMovieMedia.value,
      showTargetFilters: showTargetFilters.value,
      targetFilterMode: targetFilterMode.value,
      targetFilterConfigId: targetFilterConfigId.value,
      filterMode: filterMode.value,
      isExplicitQualityProfile: isExplicitQualityProfile.value,
    })
  }

  async function runAfterSaveIfNeeded(saved) {
    if (!runAfterSave.value || !saved?.state?.active || !saved?.state?.sub_id) return
    try {
      const seasonNumber = mediaType.value === 'tv' ? props.seasonNumber || null : null
      const command = await operations.submitCommand({
        type: 'subscription.run',
        payload: {
          target: buildMediaTarget({
            media_id: props.mediaId,
            seasonNumber,
          }),
        },
      }, {
        dedupeKey: `media:${props.mediaId}:${seasonNumber || ''}:subscription.run`,
      })
      notification.success(t('subscription.refreshTaskSubmitted'))
      if (command) emit('command-submitted', command)
    } catch (error) {
      notification.error(error?.response?.data?.message || error?.message || t('subscription.submitRefreshTaskFailed'))
    }
  }

  async function initializeDialog() {
    loadingInitialData.value = true
    try {
      resetForm()
      await Promise.all([fetchDirectories(), fetchFilterPresets(), fetchQualityProfiles(), fetchTags(), fetchSites()])
      await syncDialogUpgradeModeFromPolicy()
      await applyInitialConfig()
    } finally {
      loadingInitialData.value = false
    }
  }

  async function save() {
    saving.value = true
    try {
      const saved = await saveSubscriptionDialog(props.mediaId, buildSavePayload(), props.seasonNumber || null)

      notification.success(t('subscription.saved'))
      emit('saved', { state: saved?.state || null, config: saved?.config || null })
      await runAfterSaveIfNeeded(saved)
      emit('update:visible', false)
    } catch (error) {
      console.error(t('subscription.saveSettingsFailed'), error)
      notification.error(t('common.saveFailed', { message: error.message || t('common.unknownError') }))
    } finally {
      saving.value = false
    }
  }

  watch(() => form.subscription_mode, (mode) => {
    if (mode !== 'upgrade_continuous') {
      if (activeTab.value === 'upgrade') {
        activeTab.value = 'basic'
      }
      return
    }
    if (upgradeMode.value !== 'off') return
    upgradeMode.value = 'consistent_allow_temp'
    void syncDialogUpgradePolicyFromMode()
  })

  watch(canRunAfterSave, (enabled) => { if (!enabled) runAfterSave.value = false })
  watch(() => [...(form.filters.resource_kind || [])], () => { form.filters.resource_form = normalizeResourceFormsForKinds(form.filters.resource_form, form.filters.resource_kind) })
  watch(() => [...(form.target_filters.resource_kind || [])], () => { form.target_filters.resource_form = normalizeResourceFormsForKinds(form.target_filters.resource_form, form.target_filters.resource_kind) })
  watch(() => props.visible, async (visible) => { if (visible) await initializeDialog() })

  return {
    saving,
    loadingInitialData,
    loadingDirs,
    directoryOptions,
    siteOptions,
    filterOptions,
    qualityProfileOptions,
    qualityProfileDropdownOptions,
    qualityProfileSelection,
    tagOptions,
    resolutionOptions: subscriptionConfigResolutionOptions, sourceOptions: subscriptionConfigSourceOptions,
    codecOptions: subscriptionConfigCodecOptions,
    hdrOptions: subscriptionConfigHdrOptions, audioCodecOptions: subscriptionConfigAudioCodecOptions,
    audioChannelOptions: subscriptionConfigAudioChannelOptions, colorDepthOptions: subscriptionConfigColorDepthOptions,
    upgradeLockModeOptions,
    form,
    filterMode,
    targetFilterMode,
    filterModeOptions,
    activeTab,
    subscriptionDialogTabs,
    runAfterSave,
    canRunAfterSave,
    primarySaveLabel,
    showBaseFilterPreset,
    showTargetBasePreset,
    targetFilterConfigId,
    upgradeMode,
    isMovieMedia,
    showTargetFilters,
    showCustomFilters,
    showCustomTargetFilters,
    subscriptionModeOptions,
    showAdvancedUpgradeSettings,
    subscriptionLabel,
    followLabel,
    onFilterPresetChange,
    onFilterModeChange,
    onFilterPresetSelectionChange,
    onTargetFilterModeChange,
    onTargetFilterPresetSelectionChange,
    onQualityProfileChange,
    syncUpgradePolicyFromMode: () => { void syncDialogUpgradePolicyFromMode() },
    save,
    addUnmatchedRule: () => { form.unmatched_rules.push(createEmptyUnmatchedRule()) },
    removeUnmatchedRule: (index) => { form.unmatched_rules.splice(index, 1) },
  }
}
