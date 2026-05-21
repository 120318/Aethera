import { computed, onMounted, reactive, ref, watch } from 'vue'
import { attachMediaTMDBMapping, getMediaDetailPage, refreshMediaProfile } from '@/api/media'
import { getLibraryFileDetail } from '@/api/resource'
import { useNotificationStore } from '@/stores/notification'
import { useOperationsStore } from '@/stores/operations'
import { buildMediaDetailOverviewCards } from '@/composables/mediaDetailOverviewCardsSupport'
import { useMediaDetailCommands } from '@/composables/useMediaDetailCommands'
import { useMediaDetailData } from '@/composables/useMediaDetailData'
import { useMediaDetailFollow } from '@/composables/useMediaDetailFollow'
import { useMediaDetailRouting } from '@/composables/useMediaDetailRouting'
import { useMediaDetailSubscription } from '@/composables/useMediaDetailSubscription'
import { useSourceMediaDetailMapping } from '@/composables/useSourceMediaDetailMapping'
import { parseMediaId } from '@/composables/mediaIdentitySupport'
import { t } from '@/i18n'
import { resolveLocalizedRecordMessage } from '@/utils/localizedMessage'
import {
  clearLibraryDetailDialog,
  createDeleteDialogState,
  createLibraryDetailDialogState,
  handleMediaSubscriptionClick,
  openLibraryDetailDialog,
  refreshMediaDetailTab,
  submitLibraryFileDelete,
} from '@/composables/mediaDetailPageSupport'

function toChineseNumber(value) {
  const num = Number(value)
  if (!Number.isInteger(num) || num <= 0 || num > 99) return ''
  const digits = ['', '一', '二', '三', '四', '五', '六', '七', '八', '九']
  if (num < 10) return digits[num]
  if (num === 10) return '十'
  if (num < 20) return `十${digits[num % 10]}`
  const ten = Math.floor(num / 10)
  const one = num % 10
  return `${digits[ten]}十${one ? digits[one] : ''}`
}

function normalizeSeasonLabel(value) {
  return String(value || '')
    .toLowerCase()
    .replace(/[（(]/g, '')
    .replace(/[）)]/g, '')
    .replace(/[\s,，.。:：_\-/]/g, '')
}

function isGenericSeasonName(name, seasonNumber) {
  const normalized = normalizeSeasonLabel(name)
  if (!normalized) return true
  const number = Number(seasonNumber)
  if (!Number.isInteger(number) || number <= 0) return false
  const chineseNumber = toChineseNumber(number)
  const padded = String(number).padStart(2, '0')
  const genericLabels = [
    `第${number}季`,
    `${number}季`,
    `season${number}`,
    `season${padded}`,
    `s${number}`,
    `s${padded}`,
    chineseNumber ? `第${chineseNumber}季` : '',
    chineseNumber ? `${chineseNumber}季` : '',
  ].filter(Boolean).map(normalizeSeasonLabel)

  let rest = normalized
  for (const label of genericLabels.sort((a, b) => b.length - a.length)) {
    rest = rest.replaceAll(label, '')
  }
  return rest.length === 0
}

function normalizePositiveInteger(value) {
  const normalized = Number(value)
  return Number.isInteger(normalized) && normalized > 0 ? normalized : null
}

export function useMediaDetailPage() {
  const notification = useNotificationStore()
  const operations = useOperationsStore()
  const {
    route,
    router,
    mediaId,
    routeSeasonNumber,
    activeTab,
    handleSeasonChange,
    syncRouteSeason,
    replaceWithCanonicalMedia,
    ensureSeasonQuery,
  } = useMediaDetailRouting()
  const {
    loading,
    detail,
    error,
    tabData,
    detailOverview,
    overview,
    dataLoaded,
    fetchDetail,
    loadResourceInfo,
    loadDetailOverview,
    loadTaskInfo,
    resetSeasonScopedData,
    applyDetailPageData,
    replaceTaskItem,
    markTaskDeleted,
    setDetailSeasonContext,
  } = useMediaDetailData()
  const isTvMedia = computed(() => (
    detail.value?.type === 'tv'
    || detail.value?.media_type === 'tv'
    || mediaId.value?.includes(':tv:')
  ))
  const seasonOptions = computed(() => {
    if (!isTvMedia.value || !Array.isArray(detail.value?.seasons)) return []
    return detail.value.seasons
      .map((season) => {
        const seasonNumber = Number(season.season_number)
        const fallbackLabel = t('calendar.seasonLabel', { number: seasonNumber })
        const name = String(season.name || '').trim()
        return {
          label: isGenericSeasonName(name, seasonNumber)
            ? fallbackLabel
            : `${name}（${fallbackLabel}）`,
          value: seasonNumber,
        }
      })
      .filter((season) => Number.isInteger(season.value) && season.value > 0)
  })
  const selectedSeasonNumber = computed(() => {
    if (!isTvMedia.value) return null
    if (routeSeasonNumber.value) return routeSeasonNumber.value
    const detailSeason = Number(detail.value?.season_number)
    if (Number.isInteger(detailSeason) && detailSeason > 0) return detailSeason
    return null
  })
  const currentSeasonEpisodeCountOverride = computed(() => {
    if (!isTvMedia.value || !detail.value) return null
    const seasonNumber = normalizePositiveInteger(selectedSeasonNumber.value || detail.value.season_number)
    const selectedSeason = Array.isArray(detail.value.seasons)
      ? detail.value.seasons.find((season) => normalizePositiveInteger(season?.season_number) === seasonNumber)
      : null
    const seasonOverride = normalizePositiveInteger(selectedSeason?.episode_count_override)
    if (seasonOverride !== null) return seasonOverride

    const detailOverride = normalizePositiveInteger(detail.value.episode_count_override)
    if (detailOverride === null) return null
    const detailSeason = normalizePositiveInteger(detail.value.season_number)
    if (!seasonNumber || !detailSeason || detailSeason === seasonNumber) return detailOverride
    return null
  })
  const libraryDetailDialog = reactive(createLibraryDetailDialogState())
  const {
    subscription,
    downloadConfig,
    loadingSubscription,
    checkingSubscription,
    subscriptionDialog,
    filterPresetName,
    canMutateSubscription,
    handleCheckSubscription,
    applySubscriptionSnapshot,
    handleSubscriptionToggle,
    handleRunSubscription: submitSubscriptionRunCommand,
    handlePilotEpisode,
  } = useMediaDetailSubscription({
    mediaId,
    detail,
    detailOverview,
    selectedSeasonNumber,
    notification,
    loadDetailOverview,
  })
  const {
    handleFollowToggle,
  } = useMediaDetailFollow({
    mediaId,
    detail,
    notification,
    subscription,
    checkingSubscription,
    loadDetailOverview,
    selectedSeasonNumber,
  })
  const {
    hasSearched,
    checkingSearch,
    activeCommands,
    searchTrigger,
    searchResultsRefreshTrigger,
    searchInProgress,
    taskCreatePending,
    taskCreatePlaceholderVisible,
    pendingTaskPreview,
    taskRealtimeOverrides,
    activeSearchCommand,
    activePilotCommand,
    pilotInProgress,
    profileRefreshInProgress,
    refreshActiveMediaCommands,
    refreshSearchResults,
    triggerSearch,
    resetSearchResultsForSeasonChange,
    onSearchComplete,
    handleSearchLoading,
    handleSearchDownload,
    handleCommandSubmitted,
    subscriptionRunInProgress,
  } = useMediaDetailCommands({
    mediaId,
    selectedSeasonNumber,
    activeTab,
    tabData,
    detailOverview,
    fetchDetail,
    handleCheckSubscription,
    loadResourceInfo: loadResourceInfoTracked,
    loadDetailOverview,
    loadTaskInfo,
    markTaskDeleted,
    notification,
  })
  const {
    sourceContext,
    sourceMappingRequired,
    sourceMappingCandidates,
    sourceMappingCandidatesLoading,
    searchSourceTMDBCandidates,
    tmdbCandidateUrl,
    handleAttachSourceTMDBMapping,
  } = useSourceMediaDetailMapping({
    route,
    router,
    notification,
    reloadDetail: handleFetchDetail,
  })
  const entrySourceContext = ref(sourceContext.value)
  const deleteDialog = reactive(createDeleteDialogState())
  const pilotSubmitting = ref(false)
  const suppressSeasonScopedRefresh = ref(false)
  const resourcesLoadedFor = ref({ mediaId: null, seasonNumber: null })
  const mergedPreviewResults = computed(() => {
    const manualResults = Array.isArray(tabData.search) ? tabData.search : []
    const seen = new Set()
    const merged = []
    for (const item of manualResults) {
      const detailUrl = item?.resource?.detail_url || item?.detail_url || ''
      const fallbackId = item?.resource?.result_id || item?.result_id || item?.resource?.id || item?.id || ''
      const dedupeKey = detailUrl || fallbackId
      if (!dedupeKey || seen.has(dedupeKey)) continue
      seen.add(dedupeKey)
      merged.push(item)
    }
    return merged
  })
  const hasPreviewResults = computed(() => mergedPreviewResults.value.length > 0)
  const currentMediaType = computed(() => detail.value?.media_type || detail.value?.type || (isTvMedia.value ? 'tv' : 'movie'))
  const quickDownloadLabel = computed(() => t(isTvMedia.value ? 'mediaDetail.pilotAction' : 'mediaDetail.downloadAction'))
  const detailOverviewSummary = computed(() => detailOverview.value?.summary || null)
  const detailOverviewCatalogs = computed(() => detailOverview.value?.catalogs || null)
  const movieHasLocalResource = computed(() => !isTvMedia.value && Number(overview.value?.library_file_count || overview.value?.collected_count || 0) > 0)
  const movieHasActiveTask = computed(() => !isTvMedia.value && Number(overview.value?.active_task_count || overview.value?.downloading_count || 0) > 0)
  const pilotDisabled = computed(() => {
    if (!dataLoaded.overview) return true
    if (!isTvMedia.value) return movieHasLocalResource.value || movieHasActiveTask.value
    const totalEpisodes = Number(overview.value?.total_episodes || detail.value?.episodes_count || 0)
    const pilotLimit = Math.min(totalEpisodes, 3)
    if (pilotLimit <= 0) return true

    const occupiedEpisodes = new Set([
      ...(Array.isArray(overview.value?.collected_episodes) ? overview.value.collected_episodes : []),
      ...(Array.isArray(overview.value?.downloading_episodes) ? overview.value.downloading_episodes : []),
    ].map((episode) => Number(episode)).filter((episode) => Number.isInteger(episode) && episode > 0))

    for (let episode = 1; episode <= pilotLimit; episode += 1) {
      if (!occupiedEpisodes.has(episode)) return false
    }
    return true
  })
  const pilotDisabledReason = computed(() => {
    if (!isTvMedia.value) {
      if (loading.value || loadingSubscription.value) return t('mediaDetail.disabledReason.loadingDownloadConfig')
      if (!dataLoaded.overview) return t('mediaDetail.disabledReason.loadingLocalOverview')
      if (pilotInProgress.value) return resolveLocalizedRecordMessage(activePilotCommand.value, t('mediaDetail.disabledReason.downloadRunning'))
      if (!canMutateSubscription.value) return t('mediaDetail.disabledReason.mediaIncompleteForDownload')
      if (movieHasLocalResource.value) return t('mediaDetail.disabledReason.movieAlreadyInLibrary')
      if (movieHasActiveTask.value) return t('mediaDetail.disabledReason.movieHasActiveTask')
      return null
    }
    if (loading.value || loadingSubscription.value) return t('mediaDetail.disabledReason.loadingSubscriptionConfig')
    if (!dataLoaded.overview) return t('mediaDetail.disabledReason.loadingLocalOverview')
    if (pilotInProgress.value) return resolveLocalizedRecordMessage(activePilotCommand.value, t('mediaDetail.disabledReason.pilotRunning'))
    if (!canMutateSubscription.value) return t('mediaDetail.disabledReason.mediaIncompleteForPilot')
    if (pilotDisabled.value) {
      const totalEpisodes = Number(overview.value?.total_episodes || detail.value?.episodes_count || 0)
      const pilotLimit = Math.min(totalEpisodes, 3)
      return pilotLimit > 0
        ? t('mediaDetail.disabledReason.pilotEpisodesOccupied', { limit: pilotLimit })
        : t('mediaDetail.disabledReason.missingPilotEpisodes')
    }
    return null
  })
  const detailOverviewCards = computed(() => buildMediaDetailOverviewCards({
    detailOverviewSummary,
    loading,
    loadingSubscription,
    dataLoaded,
    isTvMedia,
    subscription,
    detail,
    filterPresetName,
  }))
  const handleSubscriptionClick = async () => handleMediaSubscriptionClick({ handleSubscriptionToggle })

  function hydrateActiveCommands(commands = [], mediaIdValue = mediaId.value, seasonNumber = selectedSeasonNumber.value) {
    operations.hydrateActiveCommands(commands, {
      media_id: mediaIdValue,
      season_number: seasonNumber || null,
    })
  }

  function isTvMediaId(value) {
    return String(value || '').includes(':tv:')
  }

  function canLoadResources(mediaIdValue, seasonNumber = null) {
    if (!mediaIdValue) return false
    return !isTvMediaId(mediaIdValue) || !!seasonNumber
  }

  async function loadResourceInfoTracked(mediaIdValue, seasonNumber = null) {
    if (!canLoadResources(mediaIdValue, seasonNumber)) return
    await loadResourceInfo(mediaIdValue, seasonNumber)
    resourcesLoadedFor.value = { mediaId: mediaIdValue, seasonNumber: seasonNumber || null }
  }

  function hasLoadedResources(mediaIdValue, seasonNumber = null) {
    return (
      dataLoaded.resources
      && resourcesLoadedFor.value.mediaId === mediaIdValue
      && resourcesLoadedFor.value.seasonNumber === (seasonNumber || null)
    )
  }

  async function ensureResourcesLoaded(mediaIdValue, seasonNumber = null) {
    if (activeTab.value !== 'resources') return
    if (!canLoadResources(mediaIdValue, seasonNumber)) return
    if (hasLoadedResources(mediaIdValue, seasonNumber)) return
    await loadResourceInfoTracked(mediaIdValue, seasonNumber)
  }

  function resetResourceLoadMarker() {
    resourcesLoadedFor.value = { mediaId: null, seasonNumber: null }
  }

  async function applyDetailBootstrapPayload(payload) {
    const loadedDetail = applyDetailPageData(payload, activeTab.value)
    applySubscriptionSnapshot(payload.subscription, payload.download_config, loadedDetail?.media_id || mediaId.value)
    const effectiveSeasonNumber = payload.effective_season_number || loadedDetail?.season_number || null
    hydrateActiveCommands(payload.active_commands || [], loadedDetail?.media_id || mediaId.value, effectiveSeasonNumber)
    await ensureResourcesLoaded(loadedDetail?.media_id || mediaId.value, effectiveSeasonNumber)
    return { detail: loadedDetail, effectiveSeasonNumber }
  }

  async function handleFetchDetailWithBootstrap() {
    const detailPageRequest = getMediaDetailPage({
      mediaId: mediaId.value,
      seasonNumber: routeSeasonNumber.value,
      activeTab: activeTab.value,
    })
    let payload
    if (activeTab.value === 'resources' && canLoadResources(mediaId.value, routeSeasonNumber.value)) {
      const [detailPagePayload] = await Promise.all([
        detailPageRequest,
        loadResourceInfoTracked(mediaId.value, routeSeasonNumber.value),
      ])
      payload = detailPagePayload
    } else {
      payload = await detailPageRequest
    }
    return applyDetailBootstrapPayload(payload)
  }

  async function handleFetchSourceDetailWithBootstrap() {
    const context = sourceContext.value
    const payload = await getMediaDetailPage({
      source: context.source,
      sourceId: context.sourceId,
      mediaType: context.mediaType,
      title: context.title,
      year: context.year,
      activeTab: activeTab.value,
    })
    return applyDetailBootstrapPayload(payload)
  }

  async function handleFetchDetail() {
    sourceMappingRequired.value = null
    try {
      suppressSeasonScopedRefresh.value = true
      if (sourceContext.value && !mediaId.value) {
        const bootstrapResult = await handleFetchSourceDetailWithBootstrap()
        const sourceDetail = bootstrapResult?.detail
        const canonicalMediaId = sourceDetail?.media_id
        if (!canonicalMediaId) return
        await replaceWithCanonicalMedia(canonicalMediaId, sourceDetail?.season_number || null)
        await syncRouteSeason(canonicalMediaId, bootstrapResult?.effectiveSeasonNumber || sourceDetail?.season_number || null)
        return
      }
      const result = await handleFetchDetailWithBootstrap()
      await syncRouteSeason(mediaId.value, result?.effectiveSeasonNumber || null)
    } catch (error) {
      if (error?.code === 10024) {
        sourceMappingRequired.value = error.data || null
        return
      }
      console.error(t('mediaDetail.loadDetailFailed'), error)
    } finally {
      suppressSeasonScopedRefresh.value = false
    }
  }

  async function handleTabRefresh() {
    if (activeTab.value === 'resources' && !canLoadResources(mediaId.value, selectedSeasonNumber.value)) return
    await refreshMediaDetailTab({
      mediaId: mediaId.value,
      seasonNumber: selectedSeasonNumber.value,
      activeTab: activeTab.value,
      loadResourceInfo: loadResourceInfoTracked,
      loadDetailOverview,
      loadTaskInfo,
    })
  }

  const openDeleteModal = (resource) => { deleteDialog.target = resource; deleteDialog.visible = true }
  async function confirmDelete() {
    deleteDialog.loading = true
    try {
      await submitLibraryFileDelete({
        target: deleteDialog.target,
        mediaId: mediaId.value,
        seasonNumber: selectedSeasonNumber.value,
        submitCommand: operations.submitCommand,
        handleCommandSubmitted,
      })
      deleteDialog.visible = false
    } finally {
      deleteDialog.loading = false
    }
  }
  const handleViewDetails = (resource) => openLibraryDetailDialog({ dialog: libraryDetailDialog, resource, notification, getLibraryFileDetail })
  async function handleTaskUpdated() {
    if (!mediaId.value) return
    await Promise.all([
      loadTaskInfo(mediaId.value, selectedSeasonNumber.value),
      loadDetailOverview(mediaId.value, selectedSeasonNumber.value),
    ])
  }

  const handleTaskViewUpdated = (task) => replaceTaskItem(task)

  async function handlePilotEpisodeDownload() {
    pilotSubmitting.value = true
    try {
      const commands = await handlePilotEpisode()
      if (commands) {
        handleCommandSubmitted(commands)
      }
    } finally {
      pilotSubmitting.value = false
    }
  }

  function normalizeEpisodeCountOverride(value) {
    const normalized = String(value ?? '').trim()
    if (!normalized) return null
    if (!/^\d+$/.test(normalized) || Number(normalized) <= 0) {
      notification.warn(t('mediaDetail.invalidEpisodeCountOverride'))
      return undefined
    }
    return Number(normalized)
  }

  async function handleAttachTMDBMapping(tmdbIdInput, seasonNumberInput = null, episodeCountOverrideInput = null) {
    const normalized = String(tmdbIdInput || '').trim()
    if (!/^\d+$/.test(normalized)) {
      notification.warn(t('mediaDetail.invalidTmdbId'))
      return false
    }
    const isTv = currentMediaType.value === 'tv'
    const normalizedSeason = String(seasonNumberInput ?? '').trim()
    let seasonNumber = null
    if (isTv && normalizedSeason) {
      if (!/^\d+$/.test(normalizedSeason) || Number(normalizedSeason) <= 0) {
        notification.warn(t('mediaDetail.invalidSeasonNumber'))
        return false
      }
      seasonNumber = Number(normalizedSeason)
    } else if (isTv && Number.isInteger(Number(detail.value?.season_number)) && Number(detail.value?.season_number) > 0) {
      seasonNumber = Number(detail.value.season_number)
    }
    const episodeCountOverride = isTv ? normalizeEpisodeCountOverride(episodeCountOverrideInput) : null
    if (episodeCountOverride === undefined) return false
    const currentTmdbId = detail.value?.tmdb_id ? String(detail.value.tmdb_id) : ''
    const currentSeasonNumber = detail.value?.season_number ? String(detail.value.season_number) : ''
    const hasDoubanId = Boolean(String(detail.value?.douban_id || '').trim())
    const hasEpisodeCountOverride = currentSeasonEpisodeCountOverride.value !== null
    if (
      currentTmdbId === normalized
      && (!isTv || currentSeasonNumber === (seasonNumber ? String(seasonNumber) : ''))
      && detail.value?.primary_metadata_source === 'tmdb'
      && !hasDoubanId
      && !episodeCountOverride
      && !hasEpisodeCountOverride
    ) {
      return true
    }
    try {
      const response = await attachMediaTMDBMapping(mediaId.value, Number(normalized), seasonNumber, episodeCountOverride)
      const canonicalMediaId = response?.media_id
      const command = response?.command
      if (command) {
        handleCommandSubmitted(command)
      }
      if (canonicalMediaId && canonicalMediaId !== mediaId.value) {
        await replaceWithCanonicalMedia(canonicalMediaId, seasonNumber)
      }
      await handleFetchDetail()
      notification.success(t('mediaDetail.tmdbMappingCreated'))
      return true
    } catch (error) {
      if (!error?.response && !error?.isAxiosError) {
        notification.error(error?.message || t('mediaDetail.updateTmdbMappingFailed'))
      }
      return false
    }
  }

  async function handleRefreshMediaProfile() {
    const refreshMediaId = detail.value?.media_id || mediaId.value
    if (!parseMediaId(refreshMediaId)) {
      notification.warn(t('mediaDetail.invalidMediaIdForRefresh'))
      return false
    }
    try {
      const command = await refreshMediaProfile(refreshMediaId, selectedSeasonNumber.value || detail.value?.season_number || null)
      if (command) {
        handleCommandSubmitted(command)
      }
      notification.success(t('mediaDetail.profileRefreshSubmitted'))
      return true
    } catch (error) {
      notification.error(error?.response?.data?.message || error?.message || t('mediaDetail.profileRefreshSubmitFailed'))
      return false
    }
  }

  async function handleRunSubscription() {
    const command = await submitSubscriptionRunCommand()
    if (command) {
      handleCommandSubmitted(command)
    }
  }

  async function handleSubscriptionSaved() {
    await Promise.all([
      loadDetailOverview(mediaId.value, selectedSeasonNumber.value),
      handleCheckSubscription({ preferOverview: true }),
      hasSearched.value || hasPreviewResults.value ? refreshSearchResults() : Promise.resolve(),
    ])
  }

  async function refreshSeasonScopedData(seasonNumber) {
    if (!mediaId.value || !seasonNumber) return
    setDetailSeasonContext(seasonNumber)
    resetSeasonScopedData()
    resetResourceLoadMarker()
    resetSearchResultsForSeasonChange()
    await Promise.all([
      activeTab.value === 'resources' ? loadResourceInfoTracked(mediaId.value, seasonNumber) : Promise.resolve(),
      loadDetailOverview(mediaId.value, seasonNumber),
      loadTaskInfo(mediaId.value, seasonNumber),
      handleCheckSubscription(),
      refreshActiveMediaCommands(seasonNumber),
    ])
  }

  watch(activeTab, handleTabRefresh)
  watch(sourceContext, (nextSourceContext) => {
    if (!nextSourceContext) return
    entrySourceContext.value = nextSourceContext
  })
  watch(selectedSeasonNumber, async (seasonNumber, previous) => {
    if (suppressSeasonScopedRefresh.value) return
    if (!isTvMedia.value || !seasonNumber || seasonNumber === previous) return
    await ensureSeasonQuery(seasonNumber)
    await refreshSeasonScopedData(seasonNumber)
  })
  watch(() => libraryDetailDialog.visible, (visible) => { if (!visible) clearLibraryDetailDialog(libraryDetailDialog) })

  onMounted(() => {
    handleFetchDetail()
  })

  return {
    mediaId,
    selectedSeasonNumber,
    currentSeasonEpisodeCountOverride,
    seasonOptions,
    handleSeasonChange,
    entrySourceContext,
    sourceMappingRequired,
    sourceMappingCandidates,
    sourceMappingCandidatesLoading,
    searchSourceTMDBCandidates,
    tmdbCandidateUrl,
    activeTab,
    loading,
    detail,
    error,
    tabData,
    detailOverview,
    overview,
    dataLoaded,
    subscription,
    downloadConfig,
    loadingSubscription,
    checkingSubscription,
    subscriptionDialog,
    detailOverviewSummary,
    filterPresetName,
    canMutateSubscription,
    handleCheckSubscription,
    handleFollowToggle,
    handleRunSubscription,
    handlePilotEpisodeDownload,
    handleAttachTMDBMapping,
    handleAttachSourceTMDBMapping,
    handleRefreshMediaProfile,
    hasSearched,
    checkingSearch,
    activeCommands,
    resourcePreviewResults: mergedPreviewResults,
    hasPreviewResults,
    searchTrigger,
    searchResultsRefreshTrigger,
    searchInProgress,
    taskCreatePending,
    taskCreatePlaceholderVisible,
    pendingTaskPreview,
    taskRealtimeOverrides,
    activeSearchCommand,
    subscriptionRunInProgress,
    activePilotCommand,
    pilotInProgress: computed(() => pilotSubmitting.value || pilotInProgress.value),
    profileRefreshInProgress,
    pilotDisabled,
    pilotDisabledReason,
    quickDownloadLabel,
    detailOverviewCards,
    detailOverviewCatalogs,
    triggerSearch,
    onSearchComplete,
    handleSearchLoading,
    handleSearchDownload,
    handleCommandSubmitted,
    handleSubscriptionClick,
    handleFetchDetail,
    deleteDialog,
    openDeleteModal,
    confirmDelete,
    libraryDetailDialog,
    handleViewDetails,
    handleTaskUpdated,
    handleTaskViewUpdated,
    handleSubscriptionSaved,
  }
}
