import { computed, ref } from 'vue'
import { attachSourceTMDBMapping, searchMedia } from '@/api/media'
import { useI18n } from 'vue-i18n'

export function useSourceMediaDetailMapping({ route, router, notification, reloadDetail }) {
  const { t } = useI18n()
  const sourceMappingRequired = ref(null)
  const sourceMappingCandidates = ref([])
  const sourceMappingCandidatesLoading = ref(false)
  let candidateSearchRequestId = 0
  const sourceContext = computed(() => {
    const source = typeof route.query.source === 'string' ? route.query.source : ''
    const sourceId = typeof route.query.source_id === 'string' ? route.query.source_id : ''
    const mediaType = typeof route.query.media_type === 'string' ? route.query.media_type : ''
    const title = typeof route.query.title === 'string' ? route.query.title : ''
    const year = Number(typeof route.query.year === 'string' ? route.query.year : '')
    if (!source || !sourceId || !mediaType) return null
    return {
      source,
      sourceId,
      mediaType,
      title,
      year: Number.isInteger(year) && year > 0 ? year : null,
    }
  })

  function tmdbCandidateUrl(candidate) {
    if (!candidate?.tmdbId || !candidate?.mediaType) return ''
    return `https://www.themoviedb.org/${candidate.mediaType}/${candidate.tmdbId}`
  }

  function normalizeCandidate(item) {
    const sourceId = String(item?.source_id || '').trim()
    const mediaIdParts = String(item?.media_id || '').split(':')
    const tmdbId = sourceId || (mediaIdParts[0] === 'tmdb' ? mediaIdParts[2] : '')
    if (!tmdbId) return null
    const mediaType = item?.media_type || mediaIdParts[1] || ''
    const year = item?.year ? String(item.year) : ''
    const rating = Number(item?.vote_average || 0)
    return {
      tmdbId,
      mediaType,
      title: item?.title || `TMDB ${tmdbId}`,
      year,
      rating: rating > 0 ? rating.toFixed(1) : '',
      overview: item?.overview || '',
      subtitle: item?.subtitle_line1 || item?.subtitle || '',
      label: [item?.title || `TMDB ${tmdbId}`, year].filter(Boolean).join(' · '),
    }
  }

  async function searchSourceTMDBCandidates(query) {
    const context = sourceContext.value
    const normalized = String(query || '').trim()
    const requestId = candidateSearchRequestId + 1
    candidateSearchRequestId = requestId
    if (!context || !normalized) {
      sourceMappingCandidates.value = []
      sourceMappingCandidatesLoading.value = false
      return []
    }
    sourceMappingCandidatesLoading.value = true
    try {
      const response = await searchMedia({
        query: normalized,
        source: 'tmdb',
        media_type: context.mediaType,
        count: 8,
      })
      const results = response?.results || response?.data?.results || []
      const candidates = results.map(normalizeCandidate).filter(Boolean)
      if (requestId !== candidateSearchRequestId) return []
      sourceMappingCandidates.value = candidates
      if (candidates.length === 0) {
        notification.info(t('mediaDetail.noTmdbCandidatesFound'))
      }
      return candidates
    } catch (error) {
      if (requestId !== candidateSearchRequestId) return []
      sourceMappingCandidates.value = []
      notification.error(error?.response?.data?.message || error?.message || t('mediaDetail.searchTmdbCandidatesFailed'))
      return []
    } finally {
      if (requestId === candidateSearchRequestId) {
        sourceMappingCandidatesLoading.value = false
      }
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

  async function handleAttachSourceTMDBMapping(tmdbIdInput, seasonNumberInput = null, episodeCountOverrideInput = null) {
    const context = sourceContext.value
    if (!context) return false
    const normalized = String(tmdbIdInput || '').trim()
    if (!/^\d+$/.test(normalized)) {
      notification.warn(t('mediaDetail.invalidTmdbId'))
      return false
    }
    const normalizedSeason = String(seasonNumberInput ?? '').trim()
    let seasonNumber = null
    if (context.mediaType === 'tv') {
      if (normalizedSeason) {
        if (!/^\d+$/.test(normalizedSeason) || Number(normalizedSeason) <= 0) {
          notification.warn(t('mediaDetail.invalidSeasonNumber'))
          return false
        }
        seasonNumber = Number(normalizedSeason)
      } else if (Number.isInteger(Number(sourceMappingRequired.value?.season_number)) && Number(sourceMappingRequired.value.season_number) > 0) {
        seasonNumber = Number(sourceMappingRequired.value.season_number)
      }
    }
    const episodeCountOverride = context.mediaType === 'tv' ? normalizeEpisodeCountOverride(episodeCountOverrideInput) : null
    if (episodeCountOverride === undefined) return false
    try {
      const response = await attachSourceTMDBMapping({
        source: context.source,
        sourceId: context.sourceId,
        mediaType: context.mediaType,
        tmdbId: Number(normalized),
        seasonNumber,
        episodeCountOverride,
      })
      const canonicalMediaId = response?.media_id
      if (!canonicalMediaId) return false
      notification.success(t('mediaDetail.tmdbMappingCreated'))
      await router.replace({
        name: 'MediaDetail',
        params: { mediaId: canonicalMediaId },
        query: seasonNumber ? { season: seasonNumber } : {},
      })
      await reloadDetail()
      return true
    } catch (error) {
      if (!error?.response && !error?.isAxiosError) {
        notification.error(error?.message || t('mediaDetail.updateTmdbMappingFailed'))
      }
      return false
    }
  }

  return {
    sourceContext,
    sourceMappingRequired,
    sourceMappingCandidates,
    sourceMappingCandidatesLoading,
    searchSourceTMDBCandidates,
    tmdbCandidateUrl,
    handleAttachSourceTMDBMapping,
  }
}
