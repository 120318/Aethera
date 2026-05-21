import {
  QUALITY_AUDIO_CHANNEL_VALUES,
  QUALITY_AUDIO_CODEC_VALUES,
  QUALITY_COLOR_DEPTH_VALUES,
  QUALITY_HDR_TYPE_VALUES,
  qualityResourceKindOptions,
  normalizeResourceFormsForKinds,
  resourceFormValuesForKinds,
  QUALITY_RESOLUTION_VALUES,
  QUALITY_SOURCE_VALUES,
  QUALITY_VIDEO_CODEC_VALUES,
} from '@/constants/qualityOptions'

export const subscriptionConfigResolutionOptions = [...QUALITY_RESOLUTION_VALUES]
export const subscriptionConfigSourceOptions = [...QUALITY_SOURCE_VALUES]
export const subscriptionConfigResourceKindOptions = [...qualityResourceKindOptions]
export const subscriptionConfigResourceFormOptions = resourceFormValuesForKinds(['video_file', 'original_disc'])
export const subscriptionConfigCodecOptions = [...QUALITY_VIDEO_CODEC_VALUES]
export const subscriptionConfigHdrOptions = [...QUALITY_HDR_TYPE_VALUES]
export const subscriptionConfigAudioCodecOptions = [...QUALITY_AUDIO_CODEC_VALUES]
export const subscriptionConfigAudioChannelOptions = [...QUALITY_AUDIO_CHANNEL_VALUES]
export const subscriptionConfigColorDepthOptions = [...QUALITY_COLOR_DEPTH_VALUES]
export const subscriptionConfigUpgradeLockModeOptions = [
  { labelKey: 'subscription.lockMode.off', value: 'off' },
  { labelKey: 'subscription.lockMode.firstDownload', value: 'first_download' },
  { labelKey: 'subscription.lockMode.bestExisting', value: 'best_existing' },
]
export const subscriptionFilterModePreset = 'preset'
export const subscriptionFilterModePresetOverride = 'preset_override'
export const subscriptionFilterModeCustom = 'custom'
export const subscriptionFilterModeOptions = [
  { labelKey: 'subscription.filterMode.preset', value: subscriptionFilterModePreset },
  { labelKey: 'subscription.filterMode.presetOverride', value: subscriptionFilterModePresetOverride },
  { labelKey: 'subscription.filterMode.custom', value: subscriptionFilterModeCustom },
]

export function createEmptySubscriptionConfigFilters() {
  return {
    resource_kind: ['video_file'],
    resolution: [],
    source: [],
    resource_form: [],
    codec: [],
    hdr_type: [],
    audio_codec: [],
    audio_channels: [],
    color_depth: [],
    include_keywords: [],
    exclude_keywords: [],
    tags: [],
    upgrade_policy: {
      enabled: false,
      strategy: 'consistent_allow_temp',
      min_upgrade_score_delta: 0,
      lock_mode: 'best_existing',
    },
  }
}

export function createDefaultQualityRankingOverride() {
  return null
}

export function createEmptyUnmatchedRule() {
  return {
    sites: [],
    search_title: '',
    pattern: '',
  }
}

export function createDefaultUpgradePolicy() {
  return {
    enabled: false,
    strategy: 'consistent_allow_temp',
    min_upgrade_score_delta: 0,
    lock_mode: 'best_existing',
  }
}

export function getDefaultDirectoryId(mediaType, directories) {
  const typedDirectories = mediaType
    ? (directories || []).filter((item) => item.media_type === mediaType)
    : (directories || [])
  const defaultDirectory = typedDirectories.find((item) => item.is_default)
  if (defaultDirectory) return defaultDirectory.id
  return typedDirectories[0]?.id || null
}

function getUpgradePolicyContainer(form) {
  if (form?.filters) return form.filters
  return form
}

export function ensureUpgradePolicy(form) {
  const container = getUpgradePolicyContainer(form)
  if (!container.upgrade_policy) {
    container.upgrade_policy = createDefaultUpgradePolicy()
    return
  }
  const policy = container.upgrade_policy
  if (policy.enabled === undefined) policy.enabled = false
  if (!policy.strategy) policy.strategy = 'consistent_allow_temp'
  if (policy.min_upgrade_score_delta === undefined || policy.min_upgrade_score_delta === null) {
    policy.min_upgrade_score_delta = 0
  }
  if (!policy.lock_mode) policy.lock_mode = 'best_existing'
}

export function syncUpgradeModeFromPolicy(form, upgradeMode) {
  ensureUpgradePolicy(form)
  const container = getUpgradePolicyContainer(form)
  upgradeMode.value = container.upgrade_policy.enabled ? container.upgrade_policy.strategy : 'off'
}

export function syncUpgradePolicyFromMode(form, upgradeMode) {
  ensureUpgradePolicy(form)
  const container = getUpgradePolicyContainer(form)
  if (upgradeMode.value === 'off') {
    container.upgrade_policy.enabled = false
    return
  }
  container.upgrade_policy.enabled = true
  container.upgrade_policy.strategy = upgradeMode.value
}

export function hasMeaningfulSubscriptionFilters(filters) {
  if (!filters) return false
  const categories = Array.isArray(filters.resource_kind) ? filters.resource_kind : ['video_file']
  if (categories.length > 0 && !(categories.length === 1 && categories[0] === 'video_file')) return true
  const listFields = [
    filters.resolution,
    filters.source,
    filters.resource_form,
    filters.codec,
    filters.hdr_type,
    filters.audio_codec,
    filters.audio_channels,
    filters.color_depth,
    filters.include_keywords,
    filters.exclude_keywords,
    filters.tags,
  ]
  if (listFields.some((items) => Array.isArray(items) && items.length > 0)) return true
  return !!filters.upgrade_policy?.enabled
}

export function cloneSubscriptionFilters(filters) {
  return JSON.parse(JSON.stringify(filters || {}))
}

export function cloneSubscriptionUpgradePolicy(policy) {
  return {
    enabled: !!policy?.enabled,
    strategy: policy?.strategy || 'consistent_allow_temp',
    min_upgrade_score_delta: Number(policy?.min_upgrade_score_delta || 0),
    lock_mode: policy?.lock_mode || 'best_existing',
  }
}

export function resolveSubscriptionFilterMode({ presetId, filters }) {
  if (presetId && hasMeaningfulSubscriptionFilters(filters)) return subscriptionFilterModePresetOverride
  if (presetId) return subscriptionFilterModePreset
  return hasMeaningfulSubscriptionFilters(filters) ? subscriptionFilterModeCustom : subscriptionFilterModePreset
}

export function buildSubscriptionUpgradePolicyPayload({ form, isMovieMedia }) {
  if (form.subscription_mode !== 'upgrade_continuous') return null
  if (isMovieMedia) {
    return {
      enabled: true,
      strategy: 'consistent_allow_temp',
      min_upgrade_score_delta: 0,
      lock_mode: 'best_existing',
    }
  }
  return cloneSubscriptionUpgradePolicy(form.upgrade_policy)
}

export function buildPersistedSubscriptionFilterPayload(source) {
  const cloned = cloneSubscriptionFilters(source)
  delete cloned.upgrade_policy
  return hasMeaningfulSubscriptionFilters(cloned) ? cloned : null
}

export function buildSubscriptionDialogSavePayload({
  form,
  isMovieMedia,
  showTargetFilters,
  targetFilterMode,
  targetFilterConfigId,
  filterMode,
  isExplicitQualityProfile,
}) {
  return {
    active: !!form.active,
    followed: !!form.followed,
    subscription_mode: form.subscription_mode,
    upgrade_policy: buildSubscriptionUpgradePolicyPayload({ form, isMovieMedia }),
    target_filters: showTargetFilters && targetFilterMode !== subscriptionFilterModePreset
      ? buildPersistedSubscriptionFilterPayload(form.target_filters)
      : null,
    target_filter_config_id: showTargetFilters && targetFilterMode !== subscriptionFilterModeCustom
      ? targetFilterConfigId
      : null,
    directory_id: form.directory_id,
    sites: Array.isArray(form.sites) && form.sites.length > 0 ? form.sites : null,
    filter_config_id: filterMode === subscriptionFilterModeCustom ? null : form.filter_config_id,
    quality_profile_id: isExplicitQualityProfile ? form.quality_profile_id : null,
    filters: filterMode === subscriptionFilterModePreset ? null : buildPersistedSubscriptionFilterPayload(form.filters),
    unmatched_rules: (form.unmatched_rules || [])
      .filter((rule) => (rule?.search_title || '').trim() || (rule?.pattern || '').trim())
      .map((rule) => ({
        sites: Array.isArray(rule?.sites) && rule.sites.length > 0 ? rule.sites : [],
        search_title: (rule?.search_title || '').trim() || null,
        pattern: (rule?.pattern || '').trim(),
      })),
  }
}

export function buildSubscriptionModeOptions(t, isMovieMedia) {
  if (isMovieMedia) {
    return [
      { label: t('subscription.modeFirstRelease'), value: 'first_release', description: t('subscription.modeFirstReleaseDescription') },
      { label: t('subscription.modeUpgradeContinuous'), value: 'upgrade_continuous', description: t('subscription.modeMovieUpgradeDescription') },
    ]
  }
  return [
    { label: t('subscription.modeCurrentAiredComplete'), value: 'current_aired_complete', description: t('subscription.modeCurrentAiredCompleteDescription') },
    { label: t('subscription.modeUpgradeContinuous'), value: 'upgrade_continuous', description: t('subscription.modeTvUpgradeDescription') },
  ]
}

export function buildSubscriptionDialogTabs(t, showTargetFilters) {
  const tabs = [
    { label: t('subscription.tabs.basic'), value: 'basic' },
    { label: t('subscription.tabs.quality'), value: 'quality' },
  ]
  if (showTargetFilters) {
    tabs.push({ label: t('subscription.tabs.upgrade'), value: 'upgrade' })
  }
  tabs.push({ label: t('subscription.tabs.unmatched'), value: 'unmatched' })
  return tabs
}

export function buildDirectoryOptions(mediaType, directories) {
  const typedDirectories = mediaType
    ? directories.filter((item) => item.enabled && item.media_type === mediaType)
    : directories.filter((item) => item.enabled)

  return typedDirectories.map((directory) => ({
    id: directory.id,
    path: directory.name || directory.alias || directory.path,
    download_path: directory.download_path,
    is_default: directory.is_default,
    media_type: directory.media_type,
  }))
}

export function buildTagOptions(tags) {
  return (tags || []).map((tag) => ({
    label: tag.name,
    value: tag.id,
  }))
}

export function applySubscriptionConfigFilters(form, filters, defaultUpgradePolicy) {
  form.filters.resource_kind = Array.isArray(filters.resource_kind) && filters.resource_kind.length > 0
    ? [...filters.resource_kind]
    : ['video_file']
  form.filters.resolution = filters.resolution || []
  form.filters.source = filters.source || []
  form.filters.resource_form = normalizeResourceFormsForKinds(filters.resource_form || [], form.filters.resource_kind)
  form.filters.codec = filters.codec || []
  form.filters.hdr_type = filters.hdr_type || []
  form.filters.audio_codec = filters.audio_codec || []
  form.filters.audio_channels = filters.audio_channels || []
  form.filters.color_depth = filters.color_depth || []
  form.filters.include_keywords = filters.include_keywords || []
  form.filters.exclude_keywords = filters.exclude_keywords || []
  form.filters.tags = filters.tags || []
  form.filters.upgrade_policy = filters.upgrade_policy
    ? { ...filters.upgrade_policy }
    : { ...defaultUpgradePolicy }
}
