import { ref, reactive, computed, watch, unref } from 'vue'
import { useNotificationStore } from '@/stores/notification'
import { getResourceSites, searchResources } from '@/api/resource'
import { buildMediaTarget, requireMediaExecutionSnapshot } from '@/composables/mediaIdentitySupport'
import { useCommandRuntime } from '@/composables/useCommandRuntime'
import { useOperationsStore } from '@/stores/operations'
import { t } from '@/i18n'
import { resolveLocalizedRecordMessage } from '@/utils/localizedMessage'

const DOWNLOAD_TASK_ALREADY_EXISTS_CODE = 10011
const COMPLETE_EPISODE_FILTER_VALUE = '__complete__'

function normalizeEpisodeNumber(value) {
  const number = Number(value)
  if (!Number.isInteger(number) || number <= 0) return null
  return number
}

function getResourceEpisodeNumbers(result) {
  const episodes = result?.attributes?.episodes
  if (!Array.isArray(episodes)) return []
  return [...new Set(episodes.map(normalizeEpisodeNumber).filter((episode) => episode !== null))]
    .sort((left, right) => left - right)
}

function parseResourceSizeBytes(value) {
  if (value === undefined || value === null || value === '') return 0
  if (typeof value === 'number') return Number.isFinite(value) ? value : 0

  const normalized = String(value).trim().replace(/,/g, '')
  const match = normalized.match(/^([\d.]+)\s*([KMGTPE]?I?B)?$/i)
  if (!match) return 0

  const amount = Number(match[1])
  if (!Number.isFinite(amount)) return 0

  const unit = (match[2] || 'B').toUpperCase()
  const unitPowerMap = {
    B: 0,
    KB: 1,
    KIB: 1,
    MB: 2,
    MIB: 2,
    GB: 3,
    GIB: 3,
    TB: 4,
    TIB: 4,
    PB: 5,
    PIB: 5,
    EB: 6,
    EIB: 6,
  }
  const power = unitPowerMap[unit]
  return power === undefined ? 0 : amount * (1024 ** power)
}

export function useResourceSearch(options = {}) {
  const notification = useNotificationStore()
  const operations = useOperationsStore()
  const hasExternalCommandSource = Object.prototype.hasOwnProperty.call(options, 'externalCommand')

  const searchState = reactive({
    media_id: '',
    keyword: '',
    site: [],
    loading: false,
    commandLoading: false,
    loadingText: ''
  })

  const searchResults = ref([])
  const torrenting = ref(new Set())
  const mediaInfo = ref(null)
  const siteOptions = ref([])

  const localFilters = ref({
    keyword: '',
    sites: [],
    matchState: '',
    categories: [],
    groups: [],
    sizeRange: '',
    seeders: '',
    promotions: [],
    resolutions: [],
    hdrTypes: [],
    sources: [],
    resourceForms: [],
    versions: [],
    tags: [],
    seasons: [],
    episodes: []
  })

  const sortState = ref({
    field: 'seeders',
    direction: 'desc'
  })

  const hasSearched = ref(false)
  const submittedSearchSiteIds = ref([])
  const suppressLocalRestore = ref(false)
  const searchRequestedAt = ref(null)
  const searchCompletedAt = ref(null)
  const searchDurationSeconds = ref(null)

  const commandRuntime = useCommandRuntime({
    scope: () => {
      if (hasExternalCommandSource || !searchState.media_id) return null
      return {
        mediaId: searchState.media_id,
        seasonNumber: resolveSearchSeasonNumber(),
      }
    },
    commandTypes: ['resource.search'],
    onTerminal: handleSearchCommandTerminal,
  })

  const fetchAvailableSites = async () => {
    const providedSites = unref(options.siteCatalog)
    if (Array.isArray(providedSites) && providedSites.length > 0) {
      siteOptions.value = providedSites
        .map((site) => ({ label: site?.name || site?.description || site?.id, value: site?.id }))
        .filter((site) => site.value)
      return
    }
    try {
      const data = await getResourceSites()
      if (data.sites && Array.isArray(data.sites)) {
        siteOptions.value = data.sites.map(s => ({ label: s.name || s.description || s.id, value: s.id }))
      }
    } catch (e) {
      console.error(t('resourceSearch.sitesLoadFailed'), e)
    }
  }

  function resolveSearchSeasonNumber(callOptions = {}) {
    const explicit = unref(callOptions.seasonNumber)
    if (explicit) return explicit
    return unref(options.seasonNumber) || null
  }

  const performSearch = async (callOptions = {}) => {
    if (!searchState.media_id) {
      notification.warn(t('resourceSearch.mediaIdRequired'))
      return
    }

    try {
      submittedSearchSiteIds.value = [...(searchState.site || [])]
      suppressLocalRestore.value = true
      searchRequestedAt.value = Date.now()
      searchResults.value = []
      const command = await operations.submitCommand({
        type: 'resource.search',
        payload: {
          target: buildMediaTarget({
            media_id: searchState.media_id,
            seasonNumber: resolveSearchSeasonNumber(callOptions),
          }),
          site_ids: submittedSearchSiteIds.value,
        },
      }, {
        dedupeKey: `media:${searchState.media_id}:${resolveSearchSeasonNumber(callOptions) || ''}:resource.search`,
      })
      if (!command) return null
      searchState.loading = true
      searchState.commandLoading = true
      searchState.loadingText = resolveLocalizedRecordMessage(command, t('resourceSearch.searchSubmitted'))
      commandRuntime.startPolling()
      return command
    } catch (error) {
      submittedSearchSiteIds.value = []
      suppressLocalRestore.value = false
      searchRequestedAt.value = null
      searchState.loading = false
      searchState.commandLoading = false
      searchState.loadingText = ''
      throw error
    }
  }

  const availableResolutions = computed(() => [...new Set(searchResults.value.map(r => r.attributes?.resolution).filter(Boolean))])
  const availableSites = computed(() => [...new Set(searchResults.value.map(r => r.resource?.site || r.site).filter(Boolean))])
  const availableSiteEntries = computed(() => {
    const seen = new Set()
    const entries = []
    for (const result of searchResults.value) {
      const siteId = result?.resource?.site || result?.site
      if (!siteId || seen.has(siteId)) continue
      seen.add(siteId)
      entries.push({
        value: siteId,
        label: result?.resource?.site_name || result?.site_name || siteId,
      })
    }
    return entries
  })
  const availableSources = computed(() => [...new Set(searchResults.value.flatMap(r => r.attributes?.sources || []).filter(Boolean))])
  const availableResourceForms = computed(() => [...new Set(searchResults.value.map(r => r.attributes?.resource_form).filter(Boolean))])
  const availableGroups = computed(() => [...new Set(searchResults.value.flatMap(r => r.attributes?.groups || []).filter(Boolean))])
  const availableSeasons = computed(() => [...new Set(searchResults.value.flatMap(r => r.attributes?.seasons || []).filter(Boolean))])
  const availableEpisodes = computed(() => (
    [...new Set(searchResults.value.flatMap((result) => getResourceEpisodeNumbers(result)))]
      .sort((left, right) => left - right)
  ))
  const hasCompleteEpisodeOption = computed(() => (
    searchResults.value.some((result) => getResourceEpisodeNumbers(result).length === 0)
  ))
  const availableEpisodeOptions = computed(() => {
    const options = availableEpisodes.value.map((episode) => ({
      label: String(episode),
      value: episode,
    }))
    if (hasCompleteEpisodeOption.value) {
      options.push({
        label: t('resourceSearch.completeSeason'),
        value: COMPLETE_EPISODE_FILTER_VALUE,
      })
    }
    return options
  })
  const availableHdrTypes = computed(() => [...new Set(searchResults.value.map(r => r.attributes?.hdr_type).filter(Boolean))])
  const availableVersions = computed(() => [...new Set(searchResults.value.flatMap(r => r.attributes?.versions || []).filter(Boolean))])
  const availableTags = computed(() => [...new Set(searchResults.value.flatMap(r => r.attributes?.tags || []).filter(Boolean))])
  
  const hasActiveFilters = computed(() => Object.values(localFilters.value).some(v => Array.isArray(v) ? v.length > 0 : !!v))

  const getResourceField = (result, field) => result?.resource?.[field] ?? result?.[field]
  const getResourceTitle = (result) => {
    const resourceTitle = getResourceField(result, 'title')
    return typeof resourceTitle === 'string' ? resourceTitle : ''
  }
  const getResourceDescription = (result) => {
    const description = getResourceField(result, 'description')
    if (typeof description === 'string' && description.trim()) return description
    const subtitle = result?.attributes?.subtitle
    return typeof subtitle === 'string' ? subtitle : ''
  }
  const getResourceSize = (result) => parseResourceSizeBytes(getResourceField(result, 'size'))
  const getResourceSeeders = (result) => Number(getResourceField(result, 'seeders') || 0)
  const getResourcePromotionState = (result) => {
    const downloadFactor = toNumber(getResourceField(result, 'download_volume_factor'))
    const uploadFactor = toNumber(getResourceField(result, 'upload_volume_factor'))
    if (downloadFactor === null) return ''
    if (downloadFactor === 0) {
      if (uploadFactor !== null && uploadFactor >= 2) return 'double_free'
      return 'free'
    }
    if (downloadFactor > 0 && downloadFactor < 1) return 'discount'
    return ''
  }
  const getResourceMatchedById = (result) => {
    const matched = getResourceField(result, 'matched_by_id')
    return matched === true
  }
  const getResourceMatchedUnmatchedRule = (result) => {
    return getResourceField(result, 'matched_unmatched_rule') === true
  }
  const getResourcePublishTimestamp = (result) => {
    const publishDate = getResourceField(result, 'publish_date')
    if (!publishDate) return 0
    const parsed = new Date(publishDate)
    return Number.isNaN(parsed.getTime()) ? 0 : parsed.getTime()
  }

  const filteredResults = computed(() => {
    const filtered = searchResults.value.filter((result) => {
      const title = getResourceTitle(result).toLowerCase()
      const description = getResourceDescription(result).toLowerCase()
      const resolution = result.attributes?.resolution
      const size = getResourceSize(result)
      const seeders = getResourceSeeders(result)
      const promotion = getResourcePromotionState(result)

      if (localFilters.value.keyword) {
        const keyword = localFilters.value.keyword.toLowerCase()
        if (!title.includes(keyword) && !description.includes(keyword)) return false
      }
      if (localFilters.value.matchState === 'matched_id' && !getResourceMatchedById(result)) return false
      if (localFilters.value.matchState === 'unmatched_id' && getResourceMatchedById(result)) return false
      if (localFilters.value.matchState === 'matched_rule' && !getResourceMatchedUnmatchedRule(result)) return false
      if (localFilters.value.resolutions.length > 0 && !localFilters.value.resolutions.includes(resolution)) return false
      if (localFilters.value.sites.length > 0 && !localFilters.value.sites.includes(getResourceField(result, 'site'))) return false
      if (localFilters.value.groups.length > 0 && !(result.attributes?.groups || []).some(group => localFilters.value.groups.includes(group))) return false
      if (localFilters.value.sources.length > 0 && !(result.attributes?.sources || []).some(source => localFilters.value.sources.includes(source))) return false
      if (localFilters.value.resourceForms.length > 0 && !localFilters.value.resourceForms.includes(result.attributes?.resource_form)) return false
      if (localFilters.value.seasons.length > 0 && !(result.attributes?.seasons || []).some(season => localFilters.value.seasons.includes(season))) return false
      if (localFilters.value.episodes.length > 0) {
        const selectedEpisodes = localFilters.value.episodes
          .map((episode) => (episode === COMPLETE_EPISODE_FILTER_VALUE ? episode : normalizeEpisodeNumber(episode)))
          .filter((episode) => episode !== null)
        const selectedEpisodeNumbers = selectedEpisodes.filter((episode) => episode !== COMPLETE_EPISODE_FILTER_VALUE)
        const selectedCompleteSeason = selectedEpisodes.includes(COMPLETE_EPISODE_FILTER_VALUE)
        const resourceEpisodes = getResourceEpisodeNumbers(result)
        const matchesEpisode = resourceEpisodes.some((episode) => selectedEpisodeNumbers.includes(episode))
        const matchesCompleteSeason = selectedCompleteSeason && resourceEpisodes.length === 0
        if (!matchesEpisode && !matchesCompleteSeason) return false
      }
      if (localFilters.value.hdrTypes.length > 0 && !localFilters.value.hdrTypes.includes(result.attributes?.hdr_type)) return false
      if (localFilters.value.versions.length > 0 && !(result.attributes?.versions || []).some(version => localFilters.value.versions.includes(version))) return false
      if (localFilters.value.tags.length > 0 && !(result.attributes?.tags || []).some(tag => localFilters.value.tags.includes(tag))) return false

      if (localFilters.value.sizeRange === 'small' && size >= 1024 ** 3) return false
      if (localFilters.value.sizeRange === 'medium' && (size < 1024 ** 3 || size >= 5 * 1024 ** 3)) return false
      if (localFilters.value.sizeRange === 'large' && (size < 5 * 1024 ** 3 || size >= 20 * 1024 ** 3)) return false
      if (localFilters.value.sizeRange === 'huge' && size < 20 * 1024 ** 3) return false

      if (localFilters.value.seeders === 'any' && seeders <= 0) return false
      if (localFilters.value.seeders === 'good' && seeders <= 5) return false
      if (localFilters.value.seeders === 'excellent' && seeders <= 20) return false
      if (localFilters.value.promotions.length > 0) {
        const matchesPromotion = localFilters.value.promotions.some((selectedPromotion) => {
          if (selectedPromotion === 'free') return ['free', 'double_free'].includes(promotion)
          return promotion === selectedPromotion
        })
        if (!matchesPromotion) return false
      }

      return true
    })

    const direction = sortState.value.direction === 'asc' ? 1 : -1

    return [...filtered].sort((left, right) => {
      if (sortState.value.field === 'title') {
        return getResourceTitle(left).localeCompare(getResourceTitle(right)) * direction
      }
      if (sortState.value.field === 'size') {
        return (getResourceSize(left) - getResourceSize(right)) * direction
      }
      if (sortState.value.field === 'publish_date') {
        return (getResourcePublishTimestamp(left) - getResourcePublishTimestamp(right)) * direction
      }
      return (getResourceSeeders(left) - getResourceSeeders(right)) * direction
    })
  })

  const addTorrent = async (resource, mInfo = {}, directoryId = null) => {
    const resId = resource.resource?.id || resource.id
    const resultId = resource.resource?.result_id || resource.result_id || resId
    torrenting.value.add(resId)
    try {
      const mediaIdentity = requireMediaExecutionSnapshot({
        media_id: mInfo.media_id || searchState.media_id,
        title: mInfo.title,
        year: mInfo.year,
        seasonNumber: resolveSearchSeasonNumber(),
        imdb_id: mInfo.imdb_id,
        douban_id: mInfo.douban_id,
        tmdb_id: mInfo.tmdb_id,
        seasons_count: mInfo.seasons_count,
        episodes_count: mInfo.episodes_count,
        aired_episode_count: mInfo.aired_episode_count,
      }, t('resourceSearch.mediaInfoIncomplete'))
      const command = await operations.submitCommand({
        type: 'task.create',
        payload: {
          media: mediaIdentity,
          result_id: resultId,
          directory_id: directoryId,
        },
      }, {
        dedupeKey: `resource:${resultId}:task.create`,
      })
      return command
    } catch (e) {
      const code = Number(e?.response?.data?.code || 0)
      const message = e?.response?.data?.message || e?.message || t('resourceSearch.taskAddFailed')
      if (code === DOWNLOAD_TASK_ALREADY_EXISTS_CODE) {
        notification.info(message)
      } else {
        notification.error(message)
      }
      return null
    } finally {
      torrenting.value.delete(resId)
    }
  }

  const toNumber = (value) => {
    if (value === undefined || value === null || value === '') return null
    const parsed = Number(value)
    return Number.isFinite(parsed) ? parsed : null
  }

  const clearAllFilters = () => {
    Object.keys(localFilters.value).forEach(k => {
      localFilters.value[k] = Array.isArray(localFilters.value[k]) ? [] : ''
    })
  }

  const setSearchResults = (results) => {
    searchResults.value = results
    hasSearched.value = true
  }

  const clearSearchResults = ({ keepHasSearched = true } = {}) => {
    searchResults.value = []
    searchRequestedAt.value = null
    if (!keepHasSearched) {
      hasSearched.value = false
    }
  }

  async function loadSearchResults(callOptions = {}) {
    const siteIds = Array.isArray(callOptions.siteIds)
      ? callOptions.siteIds
      : (Array.isArray(searchState.site) ? searchState.site : [])
    searchState.loading = searchResults.value.length === 0
    try {
      const params = {
        media_id: searchState.media_id,
        keyword: searchState.keyword,
      }
      const seasonNumber = resolveSearchSeasonNumber(callOptions)
      if (seasonNumber) params.season_number = seasonNumber
      if (siteIds.length > 0) params.site = siteIds.join(',')

      const data = await searchResources(params)
      searchResults.value = Array.isArray(data) ? data : (data.results || [])
      searchCompletedAt.value = data?.searched_at || null
      const duration = data?.search_duration_seconds == null
        ? null
        : Number(data.search_duration_seconds)
      searchDurationSeconds.value = duration !== null && Number.isFinite(duration) ? duration : null

      if (data.media_info) {
        mediaInfo.value = data.media_info
        searchState.media_id = data.media_info.media_id || data.media_info.id
      }

      hasSearched.value = true
    } finally {
      searchState.loading = false
      searchState.loadingText = ''
    }
  }

  const activeSearchCommand = computed(() => {
    if (hasExternalCommandSource) {
      return unref(options.externalCommand) || null
    }
    if (!searchState.media_id) return null
    return operations.getActiveCommandByTarget(
      'media',
      searchState.media_id,
      ['resource.search'],
      { seasonNumber: resolveSearchSeasonNumber() },
    )
  })

  async function handleSearchCommandTerminal(command) {
    searchState.loading = false
    searchState.commandLoading = false
    searchState.loadingText = ''

    if (command?.status === 'succeeded') {
      await loadSearchResults({ siteIds: submittedSearchSiteIds.value })
      notification.success(t('resourceSearch.resourcesFound', { count: searchResults.value.length }))
      submittedSearchSiteIds.value = []
      suppressLocalRestore.value = false
      return
    }

    submittedSearchSiteIds.value = []
    suppressLocalRestore.value = false
    searchRequestedAt.value = null
    searchCompletedAt.value = null
    searchDurationSeconds.value = null
    if (command?.status === 'failed') {
      notification.error(command.error || resolveLocalizedRecordMessage(command, t('resourceSearch.searchFailed')))
    }
  }

  watch(activeSearchCommand, (command) => {
    if (!command) {
      searchState.commandLoading = false
      return
    }
    if (!searchRequestedAt.value && command.created_at) {
      searchRequestedAt.value = command.created_at
    }
    searchState.loading = command.status === 'queued' || command.status === 'running'
    searchState.commandLoading = command.status === 'queued' || command.status === 'running'
    searchState.loadingText = resolveLocalizedRecordMessage(command, t('resourceSearch.searchProcessing'))
  }, { immediate: true })

  watch(
    () => unref(options.siteCatalog),
    (sites) => {
      if (!Array.isArray(sites) || sites.length === 0) return
      siteOptions.value = sites
        .map((site) => ({ label: site?.name || site?.description || site?.id, value: site?.id }))
        .filter((site) => site.value)
    },
    { immediate: true },
  )

  return {
    searchState,
    searchResults,
    torrenting,
    mediaInfo,
    localFilters,
    sortState,
    hasSearched,
    searchRequestedAt,
    searchCompletedAt,
    searchDurationSeconds,
    availableResolutions,
    availableSites,
    availableSiteEntries,
    availableSources,
    availableResourceForms,
    availableGroups,
    availableSeasons,
    availableEpisodes,
    availableEpisodeOptions,
    availableHdrTypes,
    availableVersions,
    availableTags,
    hasActiveFilters,
    filteredResults,
    performSearch,
    loadSearchResults,
    addTorrent,
    activeSearchCommand,
    siteOptions,
    fetchAvailableSites,
    clearAllFilters,
    setSearchResults,
    clearSearchResults,
  }
}
